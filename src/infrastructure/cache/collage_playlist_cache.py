"""Module for playlist cache management."""

import os
import csv
import logging
from .utils.cache_utils import get_cache_directory, ensure_directory_exists

logger = logging.getLogger(__name__)

# pylint: disable=R0801
class CollagePlaylistCache:
    """Manages playlist cache using a CSV file.
    
    CSV format (one playlist per row):
    rating_key,playlist_name,site,collage_id,torrent_group_ids (comma-separated)
    """

    def __init__(self, csv_file=None):
        default_csv_path = os.path.join(get_cache_directory(), 'playlist_cache.csv')
        self.csv_file = csv_file if csv_file else default_csv_path
        ensure_directory_exists(os.path.dirname(self.csv_file))

    # pylint: disable=too-many-arguments, R0917
    def save_playlist(self, rating_key, playlist_name, site, collage_id, torrent_group_ids):
        """Saves or updates a single playlist entry in the cache."""
        playlists = self.get_all_playlists()

        # Check if this playlist is already in the cache
        updated = False
        for pl in playlists:
            if pl['rating_key'] == rating_key:
                pl['playlist_name'] = playlist_name
                pl['site'] = site
                pl['collage_id'] = collage_id
                pl['torrent_group_ids'] = torrent_group_ids
                updated = True
                break

        if not updated:
            playlists.append({
                'rating_key': rating_key,
                'playlist_name': playlist_name,
                'site': site,
                'collage_id': collage_id,
                'torrent_group_ids': torrent_group_ids
            })

        # Write back to CSV
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for pl in playlists:
                writer.writerow([
                    pl['rating_key'],
                    pl['playlist_name'],
                    pl['site'],
                    pl['collage_id'],
                    ','.join(map(str, pl['torrent_group_ids']))
                ])
        logger.info('Playlists saved to cache.')

    def get_playlist(self, rating_key):
        """Retrieve a single playlist by rating_key."""
        playlists = self.get_all_playlists()
        for pl in playlists:
            if pl['rating_key'] == rating_key:
                return pl
        return None

    def get_all_playlists(self):
        """Retrieve all playlists from the cache."""
        playlists = []
        if os.path.exists(self.csv_file):
            with open(self.csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) == 5:
                        rating_key_str, playlist_name, site, collage_id_str, group_ids_str = row
                        try:
                            rating_key = int(rating_key_str)
                        except ValueError:
                            continue
                        try:
                            collage_id = int(collage_id_str)
                        except ValueError:
                            collage_id = None
                        group_ids = [int(g.strip()) for g in group_ids_str.split(',') if g.strip()]
                        playlists.append({
                            'rating_key': rating_key,
                            'playlist_name': playlist_name,
                            'site': site,
                            'collage_id': collage_id,
                            'torrent_group_ids': group_ids
                        })
        return playlists

    def reset_cache(self):
        """Deletes the playlist cache file if it exists."""
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)
            logger.info('Playlist cache file deleted: %s', self.csv_file)
        else:
            logger.info('No playlist cache file found to delete.')
