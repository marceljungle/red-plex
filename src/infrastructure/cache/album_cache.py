"""Module for album cache managing."""

import os
import csv
import logging
from datetime import datetime
from .utils.cache_utils import get_cache_directory, ensure_directory_exists

logger = logging.getLogger(__name__)

class AlbumCache:
    """Manages album cache using a CSV file."""

    def __init__(self, csv_file=None):
        # Define the default CSV file path in the cache directory
        default_csv_path = os.path.join(get_cache_directory(), 'plex_albums_cache.csv')
        self.csv_file = csv_file if csv_file else default_csv_path

        # Ensure the cache directory exists
        ensure_directory_exists(os.path.dirname(self.csv_file))

    def save_albums(self, album_data):
        """Saves album data to the CSV file."""
        # Ensure the directory for the CSV file exists
        os.makedirs(os.path.dirname(self.csv_file), exist_ok=True)
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for album_id, (folder_name, added_at) in album_data.items():
                writer.writerow([album_id, folder_name, added_at.isoformat()])
        logger.info('Albums saved to cache.')

    def load_albums(self):
        """Loads album data from the CSV file."""
        album_data = {}
        # pylint: disable=duplicate-code
        if os.path.exists(self.csv_file):
            with open(self.csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) == 3:
                        album_id, folder_name, added_at_str = row
                        added_at = datetime.fromisoformat(added_at_str)
                    else:
                        # Handle old cache files without added_at
                        album_id, folder_name = row
                        added_at = datetime.min  # Assign a default date
                    album_data[int(album_id)] = (folder_name, added_at)
            logger.info('Albums loaded from cache.')
        else:
            logger.info('Cache file not found.')
        return album_data

    def reset_cache(self):
        """Deletes the cache file if it exists."""
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)
            logger.info('Cache file deleted: %s', self.csv_file)
        else:
            logger.info('No cache file found to delete.')
