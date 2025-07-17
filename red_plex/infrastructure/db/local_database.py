"""Defines the LocalDatabase class for managing a SQLite database."""

import os
import sqlite3
from collections import defaultdict
from datetime import datetime
from typing import List, Optional

from red_plex.domain.models import Album, Collection, TorrentGroup
from red_plex.infrastructure.db.utils.csv_to_db_migrator import CsvToDbMigrator
from red_plex.infrastructure.logger.logger import logger


# pylint: disable=R0904
class LocalDatabase:
    """
    A class for managing local persistent storage in a SQLite database.
    It creates or reuses a 'red_plex.db' file and provides CRUD operations for:
    - albums
    - collage_collections
    - bookmark_collections
    - collection_torrent_groups (relational table for group IDs)
    """

    def __init__(self):
        self.db_path = self._get_database_directory()
        os.makedirs(self.db_path, exist_ok=True)
        db_file_path = os.path.join(self.db_path, 'red_plex.db')

        # If the database file doesn't exist, create and run migrations
        if not os.path.isfile(db_file_path):
            # Create a temp connection for initialization
            self.conn = sqlite3.connect(db_file_path)
            self.conn.execute("PRAGMA journal_mode=WAL;")
            # Migrate existing CSV data into the new DB
            # This can be removed in future releases
            migrator = CsvToDbMigrator(db_file_path=db_file_path)
            migrator.migrate_from_csv_to_db()
            self.conn.commit()
        else:
            self.conn = sqlite3.connect(db_file_path)
            self.conn.execute("PRAGMA journal_mode=WAL;")
        self._create_tables()

    def _create_tables(self):
        """Create necessary tables if they do not exist."""
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS albums (
          album_id TEXT PRIMARY KEY,
          name TEXT,
          path TEXT NOT NULL,
          added_at TEXT
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            artist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name TEXT NOT NULL UNIQUE
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS album_artists (
            album_id TEXT,
            artist_id INTEGER,
            PRIMARY KEY (album_id, artist_id),
            FOREIGN KEY (album_id) REFERENCES albums(album_id) ON DELETE CASCADE,
            FOREIGN KEY (artist_id) REFERENCES artists(artist_id) ON DELETE CASCADE
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS collage_collections (
          rating_key TEXT PRIMARY KEY,
          name TEXT,
          site TEXT,
          external_id TEXT
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS bookmark_collections (
          rating_key TEXT PRIMARY KEY,
          site TEXT
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS collection_torrent_groups (
          rating_key TEXT,
          group_id INTEGER
        );
        """)

        # Tables for site tag mappings
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS site_tag_mappings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          rating_key TEXT NOT NULL,
          group_id INTEGER NOT NULL,
          site TEXT NOT NULL,
          UNIQUE(rating_key, group_id, site)
        );
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS site_tags (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tag_name TEXT NOT NULL UNIQUE
        );
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS mapping_tags (
          mapping_id INTEGER,
          tag_id INTEGER,
          PRIMARY KEY (mapping_id, tag_id),
          FOREIGN KEY (mapping_id) REFERENCES site_tag_mappings(id) ON DELETE CASCADE,
          FOREIGN KEY (tag_id) REFERENCES site_tags(id) ON DELETE CASCADE
        );
        """)

        self.conn.execute("DROP TABLE IF EXISTS beets_mappings;")

    @staticmethod
    def _get_database_directory():
        """
        Return the directory path where the database file should live,
        based on each OS's convention for local application data.
        """
        if os.name == 'nt':  # Windows
            # Typically, LOCALAPPDATA or APPDATA for user-level application data
            return os.path.join(
                os.getenv('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local')),
                'red-plex'
            )
        try:
            if os.uname().sysname == 'Darwin':  # macOS

                # Commonly used for persistent data:
                return os.path.join(os.path.expanduser('~/Library/Application Support'), 'red-plex')
        except ImportError:
            pass

        # Linux / other Unix: use ~/.local/share/red-plex by XDG spec
        data_home = os.getenv('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        return os.path.join(data_home, 'red-plex')

    def close(self):
        """Close the database connection."""
        self.conn.close()

    # --------------------------------------------------------------------------
    #                               ALBUMS
    # --------------------------------------------------------------------------
    def insert_or_update_album(self, album: Album) -> None:
        """
        Insert or update an album, including its artists, in the database.
        Uses a transaction to ensure atomicity.
        """
        logger.debug("Inserting/updating album with ID %s", album.id)
        with self.conn:
            # 1. Insert or replace the album itself
            self.conn.execute(
                """
                INSERT OR REPLACE INTO albums(album_id, name, path, added_at)
                VALUES (?, ?, ?, ?)
                """,
                (album.id,
                 album.name,
                 album.path,
                 album.added_at.isoformat() if album.added_at else None)
            )

            # 2. Delete old artist associations for this album
            self.conn.execute("DELETE FROM album_artists WHERE album_id = ?", (album.id,))

            # 3. Insert artists and their new associations
            if album.artists:
                # Insert artists if they don't exist (IGNORE on conflict)
                self.conn.executemany(
                    "INSERT OR IGNORE INTO artists(artist_name) VALUES (?)",
                    [(artist,) for artist in album.artists]
                )

                # Get artist IDs
                cur = self.conn.cursor()
                artist_ids = dict(cur.execute(
                    f"SELECT artist_name, artist_id FROM artists WHERE artist_name IN "
                    f"({','.join('?' * len(album.artists))})",
                    album.artists
                ))

                # Insert into linking table
                self.conn.executemany(
                    "INSERT INTO album_artists(album_id, artist_id) VALUES (?, ?)",
                    [(album.id, artist_ids[name]) for name in album.artists]
                )

    def insert_albums_bulk(self, albums: List[Album]) -> None:
        """
        Inserts or updates a list of albums in bulk using a single transaction.
        Handles albums, artists, and their relationships efficiently.
        """
        logger.debug("Inserting/updating %d albums in bulk.", len(albums))

        album_rows = []
        all_artists = set()
        album_id_to_artists = {}

        for album in albums:
            album_rows.append((
                album.id,
                album.name,
                album.path,
                album.added_at.isoformat() if album.added_at else None
            ))
            if album.artists:
                all_artists.update(album.artists)
                album_id_to_artists[album.id] = album.artists

        with self.conn:
            # 1. Insert/update all albums
            self.conn.executemany(
                "INSERT OR REPLACE INTO albums(album_id, name, path, added_at) VALUES (?, ?, ?, ?)",
                album_rows
            )

            album_ids = [album.id for album in albums]

            # 2. Delete all existing artist links for the albums being updated
            self.conn.execute(
                f"DELETE FROM album_artists WHERE album_id IN ({','.join('?' * len(album_ids))})",
                album_ids
            )

            # 3. Insert all new unique artists
            if all_artists:
                self.conn.executemany(
                    "INSERT OR IGNORE INTO artists(artist_name) VALUES (?)",
                    [(artist,) for artist in all_artists]
                )

                # 4. Get all required artist IDs in one query
                cur = self.conn.cursor()
                artist_name_to_id = dict(cur.execute(
                    f"SELECT artist_name, artist_id FROM artists WHERE artist_name IN "
                    f"({','.join('?' * len(all_artists))})",
                    list(all_artists)
                ))

                # 5. Prepare and insert all album-artist links
                album_artist_links = []
                for album_id, artist_names in album_id_to_artists.items():
                    for name in artist_names:
                        album_artist_links.append((album_id, artist_name_to_id[name]))

                self.conn.executemany(
                    "INSERT INTO album_artists(album_id, artist_id) VALUES (?, ?)",
                    album_artist_links
                )

    def get_album(self, album_id: str) -> Optional[Album]:
        """
        Retrieve a single album by its ID, including its list of artists.
        """
        cur = self.conn.cursor()

        # Get album details
        cur.execute("SELECT album_id, name, path, added_at "
                    "FROM albums WHERE album_id = ?", (album_id,))
        row = cur.fetchone()
        if not row:
            return None

        _id, _name, _path, _added_at_str = row
        added_at = datetime.fromisoformat(_added_at_str) if _added_at_str else None

        # Get associated artists
        cur.execute("""
            SELECT ar.artist_name
            FROM artists ar
            JOIN album_artists aa ON ar.artist_id = aa.artist_id
            WHERE aa.album_id = ?
        """, (album_id,))
        artists = [row[0] for row in cur.fetchall()]

        return Album(id=_id, name=_name, path=_path, added_at=added_at, artists=artists)

    def get_all_albums(self) -> List[Album]:
        """
        Retrieve all albums from the database, including their lists of artists.
        This is done efficiently to avoid the N+1 query problem.
        """
        cur = self.conn.cursor()

        # 1. Fetch all albums
        cur.execute("SELECT album_id, name, path, added_at FROM albums")
        album_rows = cur.fetchall()
        if not album_rows:
            return []

        # 2. Fetch all artist relationships in a single query
        artist_map = defaultdict(list)
        cur.execute("""
            SELECT aa.album_id, ar.artist_name
            FROM album_artists aa
            JOIN artists ar ON aa.artist_id = ar.artist_id
        """)
        for album_id, artist_name in cur.fetchall():
            artist_map[album_id].append(artist_name)

        # 3. Construct Album objects
        albums = []
        for _id, _name, _path, _added_at_str in album_rows:
            added_at = datetime.fromisoformat(_added_at_str) if _added_at_str else None
            albums.append(
                Album(id=_id, name=_name, path=_path, added_at=added_at, artists=artist_map[_id])
            )
        return albums

    def delete_album(self, album_id: str) -> None:
        """
        Delete an album. Associated artist links are removed automatically
        due to 'ON DELETE CASCADE' in the foreign key constraint.
        """
        logger.debug("Deleting album with ID %s", album_id)
        with self.conn:
            self.conn.execute("DELETE FROM albums WHERE album_id = ?", (album_id,))
            # Note: We might want to clean up orphan artists later, but for now, this is fine.

    def reset_albums(self):
        """
        Deletes all records from 'albums', 'album_artists', and 'artists'.
        """
        logger.info("Resetting albums: dropping and recreating tables.")
        with self.conn:
            self.conn.execute("DROP TABLE IF EXISTS album_artists")
            self.conn.execute("DROP TABLE IF EXISTS artists")
            self.conn.execute("DROP TABLE IF EXISTS albums")
        self._create_tables()
        logger.info("Album-related tables have been successfully reset.")

    # --------------------------------------------------------------------------
    #                      COLLAGE COLLECTIONS (and their groups)
    # --------------------------------------------------------------------------
    def insert_or_update_collage_collection(self, coll: Collection) -> None:
        """
        Insert or update a collage-based collection, along with its torrent groups.
        We'll do an upsert in collage_collections, then remove all old group_ids
        from collection_torrent_groups for that rating_key, and re-insert them.
        """
        logger.debug("Inserting/updating collage collection with rating_key %s", coll.id)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO collage_collections(rating_key, name, site, external_id)
            VALUES (?, ?, ?, ?)
            """,
            (coll.id, coll.name, coll.site, coll.external_id)
        )
        # Remove old group_ids for that rating_key
        self.conn.execute(
            "DELETE FROM collection_torrent_groups WHERE rating_key = ?",
            (coll.id,)
        )
        # Insert new group_ids
        if coll.torrent_groups:
            for tg in coll.torrent_groups:
                self.conn.execute(
                    "INSERT INTO collection_torrent_groups(rating_key, group_id) VALUES(?, ?)",
                    (coll.id, tg.id)
                )
        self.conn.commit()

    def get_collage_collection(self, rating_key: str) -> Optional[Collection]:
        """
        Retrieve a single collage-based collection (and associated group_ids) by rating_key.
        Returns a Collection or None if not found.
        """
        cur = self.conn.cursor()
        # Get collage collection fields
        cur.execute(
            """
            SELECT rating_key, name, site, external_id
            FROM collage_collections
            WHERE rating_key = ?
            """,
            (rating_key,)
        )
        row = cur.fetchone()
        if not row:
            return None
        rating_key_val, name, site, external_id = row
        # Get associated group_ids
        group_ids = self._get_torrent_group_ids_for(rating_key_val)
        return Collection(
            id=rating_key_val,
            external_id=external_id,
            name=name,
            torrent_groups=[TorrentGroup(id=gid) for gid in group_ids],
            site=site
        )

    def get_all_collage_collections(self) -> List[Collection]:
        """
        Retrieve all collage-based collections from the DB,
        along with their torrent groups.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT rating_key, name, site, external_id FROM collage_collections")
        rows = cur.fetchall()
        collections = []
        for (rk, name, site, external_id) in rows:
            group_ids = self._get_torrent_group_ids_for(rk)
            collections.append(Collection(
                id=rk,
                external_id=external_id,
                name=name,
                torrent_groups=[TorrentGroup(id=gid) for gid in group_ids],
                site=site
            ))
        return collections

    def delete_collage_collection(self, rating_key: str) -> None:
        """
        Delete a collage-based collection and associated torrent group mappings.
        """
        logger.debug("Deleting collage collection with rating_key %s", rating_key)
        self.conn.execute(
            "DELETE FROM collage_collections WHERE rating_key = ?",
            (rating_key,)
        )
        self.conn.execute(
            "DELETE FROM collection_torrent_groups WHERE rating_key = ?",
            (rating_key,)
        )
        self.conn.commit()

    def reset_collage_collections(self):
        """
        Deletes all records from 'collage_collections' and
        their associated rows in 'collection_torrent_groups'.
        """
        logger.info("Resetting collage collections (deleting all rows in 'collage_collections').")
        self.conn.execute("DELETE FROM collage_collections")
        logger.info("Removing associated torrent groups for collage collections.")
        self.conn.execute("""
            DELETE FROM collection_torrent_groups
            WHERE rating_key NOT IN (SELECT rating_key FROM bookmark_collections)
        """)

        self.conn.commit()

    # --------------------------------------------------------------------------
    #                           BOOKMARK COLLECTIONS
    # --------------------------------------------------------------------------
    def insert_or_update_bookmark_collection(self, coll: Collection) -> None:
        """
        Insert or update a bookmark-based collection (in bookmark_collections),
        then remove all old group_ids from 'collection_torrent_groups' for that rating_key
        and re-insert them.
        """
        logger.debug("Inserting/updating bookmark collection with rating_key %s", coll.id)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO bookmark_collections(rating_key, site)
            VALUES (?, ?)
            """,
            (coll.id, coll.site)
        )
        # Remove old group_ids for that rating_key
        self.conn.execute(
            "DELETE FROM collection_torrent_groups WHERE rating_key = ?",
            (coll.id,)
        )
        # Insert new group_ids
        if coll.torrent_groups:
            for tg in coll.torrent_groups:
                self.conn.execute(
                    "INSERT INTO collection_torrent_groups(rating_key, group_id) VALUES(?, ?)",
                    (coll.id, tg.id)
                )
        self.conn.commit()

    def get_bookmark_collection(self, rating_key: str) -> Optional[Collection]:
        """
        Retrieve a single bookmark collection (plus group_ids) by rating_key.
        Returns a Collection or None if not found.
        """
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT rating_key, site
            FROM bookmark_collections
            WHERE rating_key = ?
            """,
            (rating_key,)
        )
        row = cur.fetchone()
        if not row:
            return None
        rating_key_val, site = row
        group_ids = self._get_torrent_group_ids_for(rating_key_val)
        # We can store the name as something like f"{site.upper()} Bookmarks"
        return Collection(
            id=rating_key_val,
            name=f"{site.upper()} Bookmarks",
            site=site,
            torrent_groups=[TorrentGroup(id=gid) for gid in group_ids]
        )

    def get_all_bookmark_collections(self) -> List[Collection]:
        """
        Retrieve all bookmark collections from the DB,
        along with their torrent groups.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT rating_key, site FROM bookmark_collections")
        rows = cur.fetchall()
        bookmarks = []
        for (rk, site) in rows:
            group_ids = self._get_torrent_group_ids_for(rk)
            bookmarks.append(Collection(
                id=rk,
                name=f"{site.upper()} Bookmarks",
                site=site,
                torrent_groups=[TorrentGroup(id=gid) for gid in group_ids]
            ))
        return bookmarks

    def delete_bookmark_collection(self, rating_key: str) -> None:
        """
        Delete a bookmark-based collection and associated torrent group mappings.
        """
        logger.debug("Deleting bookmark collection with rating_key %s", rating_key)
        self.conn.execute(
            "DELETE FROM bookmark_collections WHERE rating_key = ?",
            (rating_key,)
        )
        self.conn.execute(
            "DELETE FROM collection_torrent_groups WHERE rating_key = ?",
            (rating_key,)
        )
        self.conn.commit()

    def reset_bookmark_collections(self):
        """
        Deletes all records from 'bookmark_collections' and
        their associated rows in 'collection_torrent_groups'.
        """
        logger.info("Resetting bookmark collections (deleting all rows in 'bookmark_collections').")
        self.conn.execute("DELETE FROM bookmark_collections")
        logger.info("Removing associated torrent groups for bookmark collections.")
        self.conn.execute("""
            DELETE FROM collection_torrent_groups
            WHERE rating_key NOT IN (SELECT rating_key FROM collage_collections)
        """)

        self.conn.commit()

    # --------------------------------------------------------------------------
    #                HELPER: TORRENT GROUPS FOR A GIVEN RATING_KEY
    # --------------------------------------------------------------------------
    def _get_torrent_group_ids_for(self, rating_key: str) -> List[int]:
        """
        Retrieve all group_ids for a given rating_key from collection_torrent_groups.
        """
        cur = self.conn.cursor()
        cur.execute(
            "SELECT group_id FROM collection_torrent_groups WHERE rating_key = ?",
            (rating_key,)
        )
        rows = cur.fetchall()
        return [row[0] for row in rows]

    # --------------------------------------------------------------------------
    #                           SITE TAG MAPPINGS
    # --------------------------------------------------------------------------
    def insert_site_tag_mapping(self, rating_key: str,
                                group_id: int,
                                site: str,
                                tags: List[str]) -> None:
        """
        Insert or update a site tag mapping with its associated tags.
        """
        logger.debug("Inserting site tag mapping: rating_key=%s, group_id=%s, site=%s",
                     rating_key, group_id, site)

        with self.conn:
            # Insert or ignore the mapping
            cur = self.conn.cursor()
            cur.execute("""
                INSERT OR IGNORE INTO site_tag_mappings(rating_key, group_id, site) 
                VALUES (?, ?, ?)
            """, (rating_key, group_id, site))

            # Get the mapping ID
            cur.execute("""
                SELECT id FROM site_tag_mappings 
                WHERE rating_key = ? AND group_id = ? AND site = ?
            """, (rating_key, group_id, site))
            mapping_id = cur.fetchone()[0]

            # Delete existing tag associations for this mapping
            cur.execute("DELETE FROM mapping_tags WHERE mapping_id = ?", (mapping_id,))

            if tags:
                # Insert tags if they don't exist
                self.conn.executemany(
                    "INSERT OR IGNORE INTO site_tags(tag_name) VALUES (?)",
                    [(tag,) for tag in tags]
                )

                # Get tag IDs
                tag_ids = dict(cur.execute(
                    f"SELECT tag_name, id FROM site_tags WHERE tag_name IN "
                    f"({','.join('?' * len(tags))})",
                    tags
                ))

                # Insert tag associations
                self.conn.executemany(
                    "INSERT INTO mapping_tags(mapping_id, tag_id) VALUES (?, ?)",
                    [(mapping_id, tag_ids[tag]) for tag in tags]
                )

    def get_rating_keys_by_tags(self, tags: List[str]) -> List[str]:
        """
        Get rating keys that have mappings containing all specified tags.
        """
        if not tags:
            return []

        cur = self.conn.cursor()

        placeholders = ','.join('?' * len(tags))
        cur.execute(f"""
            SELECT DISTINCT stm.rating_key
            FROM site_tag_mappings stm
            JOIN mapping_tags mt ON stm.id = mt.mapping_id
            JOIN site_tags st ON mt.tag_id = st.id
            WHERE st.tag_name IN ({placeholders})
            GROUP BY stm.rating_key
            HAVING COUNT(DISTINCT st.tag_name) = ?
        """, tags + [len(tags)])

        return [row[0] for row in cur.fetchall()]

    def get_unscanned_albums(self) -> List[str]:
        """
        Get rating keys from albums table that are not present in site_tag_mappings.
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT a.album_id
            FROM albums a
            LEFT JOIN site_tag_mappings stm ON a.album_id = stm.rating_key
            WHERE stm.rating_key IS NULL
        """)

        return [row[0] for row in cur.fetchall()]

    def reset_tag_mappings(self):
        """
        Reset site tag mappings.
        """
        logger.info("Resetting site tag mappings")

        with self.conn:
            self.conn.execute("DELETE FROM mapping_tags")
            self.conn.execute("DELETE FROM site_tag_mappings")
            self.conn.execute("DELETE FROM site_tags")
