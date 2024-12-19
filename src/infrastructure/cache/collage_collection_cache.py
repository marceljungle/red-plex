"""Module for collection cache management."""

import os
import csv
import logging
from .utils.cache_utils import get_cache_directory, ensure_directory_exists

logger = logging.getLogger(__name__)

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
    def save_collection(self, rating_key, collection_name, site, collage_id, torrent_group_ids):
        """Saves or updates a single collection entry in the cache."""
        collections = self.get_all_collections()

        # Check if this collection is already in the cache
        updated = False
        for coll in collections:
            if coll['rating_key'] == rating_key:
                coll['collection_name'] = collection_name
                coll['site'] = site
                coll['collage_id'] = collage_id
                coll['torrent_group_ids'] = torrent_group_ids
                updated = True
                break

        if not updated:
            collections.append({
                'rating_key': rating_key,
                'collection_name': collection_name,
                'site': site,
                'collage_id': collage_id,
                'torrent_group_ids': torrent_group_ids
            })

        # Write back to CSV
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for coll in collections:
                writer.writerow([
                    coll['rating_key'],
                    coll['collection_name'],
                    coll['site'],
                    coll['collage_id'],
                    ','.join(map(str, coll['torrent_group_ids']))
                ])
        logger.info('Collections saved to cache.')

    def get_collection(self, rating_key):
        """Retrieve a single collection by rating_key."""
        collections = self.get_all_collections()
        for coll in collections:
            if coll['rating_key'] == rating_key:
                return coll
        return None

    def get_all_collections(self):
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
                        collections.append({
                            'rating_key': rating_key,
                            'collection_name': collection_name,
                            'site': site,
                            'collage_id': collage_id,
                            'torrent_group_ids': group_ids
                        })
        return collections

    def reset_cache(self):
        """Deletes the collection cache file if it exists."""
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)
            logger.info('Collection cache file deleted: %s', self.csv_file)
        else:
            logger.info('No collection cache file found to delete.')
