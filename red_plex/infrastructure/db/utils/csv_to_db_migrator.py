"""This module contains a class for migrating data from CSV to a SQLite database."""

import csv
import os
import sqlite3
from datetime import datetime
from typing import List

from red_plex.domain.models import Album, Collection, TorrentGroup
from red_plex.infrastructure.logger.logger import logger


# pylint: disable=too-few-public-methods
class CsvToDbMigrator:
    """Migrates data from CSV to a SQLite database."""

    def __init__(self, db_file_path: str):
        self.csv_path = self._get_cache_directory()
        self.db_file_path = db_file_path

    def migrate_from_csv_to_db(self):
        """Migrates data from CSV to a SQLite database."""
        db_file_path = self.db_file_path
        albums_file_path = os.path.join(self.csv_path, 'plex_albums_cache.csv')
        collages_file_path = os.path.join(self.csv_path, 'collage_collection_cache.csv')
        bookmarks_file_path = os.path.join(self.csv_path, 'bookmarks_collection_cache.csv')

        conn = sqlite3.connect(db_file_path)

        if os.path.isfile(albums_file_path):
            logger.info('Migrating albums from CSV to db...')
            albums = self._load_albums(albums_file_path)
            for album in albums:
                conn.execute(
                    "INSERT INTO albums(album_id, path, added_at) VALUES(?, ?, ?)",
                    (album.id, album.path, album.added_at.isoformat())
                )
            conn.commit()
            logger.info('Albums successfully migrated to db.')
        if os.path.isfile(collages_file_path):
            logger.info('Migrating collages from CSV to db...')
            collages = self._load_collage_collections(collages_file_path)
            for collage in collages:
                conn.execute(
                    "INSERT INTO collage_collections(rating_key, name, site, external_id) "
                    "VALUES(?, ?, ?, ?)",
                    (collage.id, collage.name, collage.site, collage.external_id)
                )

                # Now insert the torrent group IDs of each collection
                for group in collage.torrent_groups:
                    conn.execute(
                        "INSERT INTO collection_torrent_groups(rating_key, group_id) VALUES(?, ?)",
                        (collage.id, group.id)
                    )
            conn.commit()
            logger.info('Collages successfully migrated to db.')
        if os.path.isfile(bookmarks_file_path):
            logger.info('Migrating bookmarks from CSV to db...')
            bookmarks = self._load_bookmark_collections(bookmarks_file_path)
            for bookmark in bookmarks:
                conn.execute(
                    "INSERT INTO bookmark_collections(rating_key, site) VALUES(?, ?)",
                    (bookmark.id, bookmark.site)
                )

                # Now insert the torrent group IDs of each collection
                for group in bookmark.torrent_groups:
                    conn.execute(
                        "INSERT INTO collection_torrent_groups(rating_key, group_id) VALUES(?, ?)",
                        (bookmark.id, group.id)
                    )
            conn.commit()
            logger.info('Bookmarks successfully migrated to db.')

    @staticmethod
    def _load_albums(csv_file: str) -> List[Album]:
        """Loads album data from the CSV file."""
        albums: List[Album]
        albums = []
        # pylint: disable=duplicate-code
        if os.path.exists(csv_file):
            with open(csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) == 3:
                        album_id, folder_name, added_at_str = row
                        added_at = datetime.fromisoformat(added_at_str)
                    else:
                        # Handle old db files without added_at
                        album_id, folder_name = row
                        added_at = datetime.min  # Assign a default date
                    albums.append(Album(
                        id=album_id,
                        path=folder_name,
                        added_at=added_at
                    ))
            logger.info('Albums loaded from db.')
        else:
            logger.info('Cache file not found.')
        return albums

    @staticmethod
    def _load_collage_collections(csv_file: str) -> List[Collection]:
        """Retrieve all collections from the db."""
        collections = []
        if os.path.exists(csv_file):
            with open(csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) == 5:
                        rating_key_str, collection_name, site, collage_id_str, group_ids_str = row
                        try:
                            rating_key = rating_key_str
                        except ValueError:
                            continue
                        try:
                            collage_id = int(collage_id_str)
                        except ValueError:
                            collage_id = None
                        group_ids = [int(g.strip()) for g in group_ids_str.split(',') if g.strip()]

                        collections.append(Collection(
                            rating_key,
                            str(collage_id),
                            collection_name,
                            [TorrentGroup(id=gid) for gid in group_ids],
                            site
                        ))
        return collections

    @staticmethod
    def _load_bookmark_collections(csv_file: str) -> List[Collection]:
        """Retrieve all bookmarks from the db."""
        bookmarks = []
        if os.path.exists(csv_file):
            with open(csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) == 3:
                        rating_key_str, site, group_ids_str = row
                        try:
                            rating_key = rating_key_str
                        except ValueError:
                            continue
                        group_ids = [int(g.strip()) for g in group_ids_str.split(',') if g.strip()]
                        bookmarks.append(Collection(
                            id=rating_key,
                            name=f"{site.upper()} Bookmarks",
                            site=site,
                            torrent_groups=[TorrentGroup(id=gid) for gid in group_ids]
                        ))
        return bookmarks

    @staticmethod
    def _get_cache_directory():
        """Return the db directory path based on the OS."""
        if os.name == 'nt':  # Windows
            return os.path.join(os.getenv('LOCALAPPDATA',
                                          os.path.expanduser('~\\AppData\\Local')), 'red-plex')
        if os.uname().sysname == 'Darwin':  # macOS
            return os.path.join(os.path.expanduser('~/Library/Caches'), 'red-plex')
        return os.path.join(os.path.expanduser('~/.cache'), 'red-plex')  # Linux and others
