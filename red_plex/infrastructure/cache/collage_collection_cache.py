"""Module for collection cache management."""

import csv
import os
from typing import List

from domain.models import TorrentGroup, Collection
from infrastructure.cache.utils.cache_utils import get_cache_directory, ensure_directory_exists
from infrastructure.logger.logger import logger


# pylint: disable=R0801
class CollageCollectionCache:
    """Manages collection cache using a CSV file.
    
    CSV format (one collection per row):
    rating_key,collection_name,site,collage_id,torrent_group_ids (comma-separated)
    """

    def __init__(self, csv_file=None):
        default_csv_path = os.path.join(get_cache_directory(), 'collage_collection_cache.csv')
        self.csv_file = csv_file if csv_file else default_csv_path
        ensure_directory_exists(os.path.dirname(self.csv_file))

    # pylint: disable=too-many-arguments, R0917
    def save_collection(self, rating_key, collection_name, site,
                        collage_id, torrent_group_list) -> None:
        """Saves or updates a single collection entry in the cache."""
        collections = self.get_all_collections()

        # Check if this collection is already in the cache
        updated = False
        for coll in collections:
            if coll.external_id == rating_key:
                coll.name = collection_name
                coll.site = site
                coll.external_id = collage_id
                coll.torrent_groups = [TorrentGroup(id=gid) for gid in torrent_group_list]
                updated = True
                break

        if not updated:
            collections.append(Collection(
                rating_key,
                collage_id,
                collection_name,
                [TorrentGroup(id=gid) for gid in torrent_group_list],
                site
            ))

        # Write back to CSV
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for coll in collections:
                writer.writerow([
                    coll.id,
                    coll.name,
                    coll.site,
                    coll.external_id,
                    ','.join(map(str, [group.id for group in coll.torrent_groups])),
                ])
        logger.info('Collections saved to cache.')

    def get_collection(self, rating_key) -> Collection:
        """Retrieve a single collection by rating_key."""
        return next((coll for coll in self.get_all_collections() if coll.id == rating_key), None)

    def get_all_collections(self) -> List[Collection]:
        """Retrieve all collections from the cache."""
        collections = []
        if os.path.exists(self.csv_file):
            with open(self.csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) == 5:
                        rating_key_str, collection_name, site, collage_id_str, group_ids_str = row
                        try:
                            rating_key = int(rating_key_str)
                        except ValueError:
                            continue
                        try:
                            collage_id = int(collage_id_str)
                        except ValueError:
                            collage_id = None
                        group_ids = [int(g.strip()) for g in group_ids_str.split(',') if g.strip()]

                        collections.append(Collection(
                            rating_key,
                            collage_id,
                            collection_name,
                            [TorrentGroup(id=gid) for gid in group_ids],
                            site
                        ))
        return collections

    def reset_cache(self) -> None:
        """Deletes the collection cache file if it exists."""
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)
            logger.info('Collection cache file deleted: %s', self.csv_file)
        else:
            logger.info('No collection cache file found to delete.')
