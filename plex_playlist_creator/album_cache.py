"""Module for album cache managing."""

import os
import csv
import logging

logger = logging.getLogger(__name__)

class AlbumCache:
    """Manages album cache using a CSV file."""

    def __init__(self, csv_file=None):
        # Define the default CSV file path
        default_csv_path = os.path.join('data', 'plex_albums_cache.csv')
        self.csv_file = csv_file if csv_file else default_csv_path

    def save_albums(self, album_data):
        """Saves album data to the CSV file."""
        # Ensure the directory for the CSV file exists
        os.makedirs(os.path.dirname(self.csv_file), exist_ok=True)
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for album_id, folder_name in album_data.items():
                writer.writerow([album_id, folder_name])
        logger.info('Albums saved to cache.')

    def load_albums(self):
        """Loads album data from the CSV file."""
        album_data = {}
        if os.path.exists(self.csv_file):
            with open(self.csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    album_id, folder_name = row
                    album_data[int(album_id)] = folder_name
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
