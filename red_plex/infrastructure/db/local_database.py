"""Defines the LocalDatabase class for managing a SQLite database."""

import os
import sqlite3
from datetime import datetime
from typing import List, Optional

from domain.models import Album, Collection, TorrentGroup
from infrastructure.beets.model.beets_data import BeetsData
from infrastructure.db.utils.csv_to_db_migrator import CsvToDbMigrator
from infrastructure.logger.logger import logger


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
            self._create_tables()
            # Migrate existing CSV data into the new DB
            # This can be removed in future releases
            migrator = CsvToDbMigrator(db_file_path=db_file_path)
            migrator.migrate_from_csv_to_db()
            self.conn.commit()
        else:
            self.conn = sqlite3.connect(db_file_path)
            self.conn.execute("PRAGMA journal_mode=WAL;")

    def _create_tables(self):
        """Create necessary tables if they do not exist."""
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS albums (
          album_id TEXT PRIMARY KEY,
          path TEXT NOT NULL,
          added_at TEXT
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
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS beets_mappings (
          source TEXT,
          destination TEXT
        );
        """)

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
        Insert or update an album in the 'albums' table.
        Uses INSERT OR REPLACE to handle upsert logic.
        """
        logger.debug("Inserting/updating album with ID %s", album.id)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO albums(album_id, path, added_at)
            VALUES (?, ?, ?)
            """,
            (album.id, album.path, album.added_at.isoformat() if album.added_at else None)
        )
        self.conn.commit()

    def insert_albums_bulk(self, albums: List[Album]) -> None:
        """
        Inserts or updates a list of albums in bulk, using a single transaction.
        It uses INSERT OR REPLACE logic to handle upsert behavior for each Album.
        """
        logger.debug("Inserting/updating %d albums in bulk.", len(albums))
        # Prepare rows for executemany
        album_rows = [
            (album.id, album.path, album.added_at.isoformat() if album.added_at else None)
            for album in albums
        ]
        # Use a transaction via a context manager (with self.conn:)
        with self.conn:
            self.conn.executemany(
                """
                INSERT OR REPLACE INTO albums (album_id, path, added_at)
                VALUES (?, ?, ?)
                """,
                album_rows
            )
        # The transaction is committed automatically
        # at the end of the 'with' block if no exceptions occur.

    def get_album(self, album_id: str) -> Optional[Album]:
        """
        Retrieve a single album by its ID.
        Returns an Album object or None if not found.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT album_id, path, added_at FROM albums WHERE album_id = ?", (album_id,))
        row = cur.fetchone()
        if not row:
            return None
        _id, _path, _added_at_str = row
        added_at = datetime.fromisoformat(_added_at_str) if _added_at_str else None
        return Album(id=_id, path=_path, added_at=added_at)

    def get_all_albums(self) -> List[Album]:
        """
        Retrieve all albums from the 'albums' table.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT album_id, path, added_at FROM albums")
        rows = cur.fetchall()
        albums = []
        for (_id, _path, _added_at_str) in rows:
            added_at = datetime.fromisoformat(_added_at_str) if _added_at_str else None
            albums.append(Album(id=_id, path=_path, added_at=added_at))
        return albums

    def delete_album(self, album_id: str) -> None:
        """
        Delete an album from the 'albums' table.
        """
        logger.debug("Deleting album with ID %s", album_id)
        self.conn.execute("DELETE FROM albums WHERE album_id = ?", (album_id,))
        self.conn.commit()

    def reset_albums(self):
        """
        Deletes all records from the 'albums' table.
        """
        logger.info("Resetting albums (deleting all rows in 'albums').")
        self.conn.execute("DELETE FROM albums")
        self.conn.commit()

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
    #                           BEETS MAPPINGS
    # --------------------------------------------------------------------------
    def insert_or_update_beets_mapping(self, source: str, destination: str) -> None:
        """
        Insert or update beets source-destination relation in the 'beets_mappings' table.
        Uses INSERT OR REPLACE to handle upsert logic.
        """
        logger.debug("Inserting/updating beets mapping with source "
                     "%s and destination %s", source, destination)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO beets_mappings(source, destination)
            VALUES (?, ?)
            """,
            (source, destination)
        )
        self.conn.commit()

    def get_all_beets_mappings(self) -> BeetsData:
        """
        Retrieve all beets mappings from the DB,
        """
        cur = self.conn.cursor()
        cur.execute("SELECT source, destination FROM beets_mappings")
        rows = cur.fetchall()
        beets_data = BeetsData({})
        for (source, destination) in rows:
            beets_data.source_destination.update({source: destination})
        return beets_data

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
