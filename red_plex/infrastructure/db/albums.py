"""Album database operations."""

from collections import defaultdict
from datetime import datetime
from typing import List, Optional

from red_plex.domain.models import Album
from red_plex.infrastructure.logger.logger import logger


class AlbumDatabaseManager:
    """Manages album-related database operations."""

    def __init__(self, conn):
        self.conn = conn

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
        # Note: We need to recreate tables elsewhere since this manager
        # doesn't handle table creation
