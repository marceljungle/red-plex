"""Module for playlist cache management."""

import os
import csv
import logging

logger = logging.getLogger(__name__)


class PlaylistCache:
    """Manages playlist cache using a CSV file."""

    def __init__(self, csv_file=None):
        # Define the default CSV file path
        default_csv_path = os.path.join('data', 'playlist_cache.csv')
        self.csv_file = csv_file if csv_file else default_csv_path

    def save_playlist(self, playlist_id, playlist_name, torrent_group_ids):
        """Saves playlist data to the CSV file."""
        # Ensure the directory for the CSV file exists
        os.makedirs(os.path.dirname(self.csv_file), exist_ok=True)
        # Load existing cache
        cache = self.load_cache()
        # Update cache with the playlist
        cache[playlist_id] = {
            'name': playlist_name,
            'torrent_group_ids': torrent_group_ids
        }
        # Write the cache back to file
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for pid, data in cache.items():
                writer.writerow([pid, data['name'], ','.join(map(str, data['torrent_group_ids']))])
        logger.info('Playlist saved to cache.')

    def load_cache(self):
        """Loads playlist data from the CSV file."""
        cache = {}
        # pylint: disable=duplicate-code
        if os.path.exists(self.csv_file):
            with open(self.csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) == 3:
                        playlist_id, name, group_ids_str = row
                        torrent_group_ids = list(
                            map(int, group_ids_str.split(','))) if group_ids_str else []
                        cache[int(playlist_id)] = {
                            'name': name,
                            'torrent_group_ids': torrent_group_ids
                        }
            logger.info('Playlists loaded from cache.')
        else:
            logger.info('Playlist cache file not found.')
        return cache

    def get_playlist(self, playlist_id):
        """Retrieves playlist data from the cache by ID."""
        cache = self.load_cache()
        return cache.get(playlist_id)

    def get_playlist_by_name(self, playlist_name):
        """Retrieves playlist data from the cache by name."""
        cache = self.load_cache()
        for pid, data in cache.items():
            if data['name'] == playlist_name:
                return pid, data
        return None, None

    def reset_cache(self):
        """Deletes the playlist cache file if it exists."""
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)
            logger.info('Playlist cache file deleted: %s', self.csv_file)
        else:
            logger.info('No playlist cache file found to delete.')
