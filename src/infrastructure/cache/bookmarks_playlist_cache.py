"""Module for bookmarks cache management."""

import os
import csv
import logging
from .utils.cache_utils import get_cache_directory, ensure_directory_exists

logger = logging.getLogger(__name__)

# pylint: disable=R0801
class BookmarksPlaylistCache:
    """Manages playlist bookmarks cache using a CSV file.
    
    CSV format (one bookmark per row):
    rating_key,site,torrent_group_ids (comma-separated)
    """

    def __init__(self, csv_file=None):
        default_csv_path = os.path.join(get_cache_directory(), 'bookmarks_cache.csv')
        self.csv_file = csv_file if csv_file else default_csv_path
        ensure_directory_exists(os.path.dirname(self.csv_file))

    # pylint: disable=too-many-arguments, R0917
    def save_bookmarks(self, rating_key, site, torrent_group_ids):
        """Saves or updates a single bookmark entry in the cache."""
        bookmarks = self.get_all_bookmarks()

        # Check if this bookmark is already in the cache
        updated = False
        for bookmrk in bookmarks:
            if bookmrk['rating_key'] == rating_key:
                bookmrk['site'] = site
                bookmrk['torrent_group_ids'] = torrent_group_ids
                updated = True
                break

        if not updated:
            bookmarks.append({
                'rating_key': rating_key,
                'site': site,
                'torrent_group_ids': torrent_group_ids
            })

        # Write back to CSV
        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for bookmrk in bookmarks:
                writer.writerow([
                    bookmrk['rating_key'],
                    bookmrk['site'],
                    ','.join(map(str, bookmrk['torrent_group_ids']))
                ])
        logger.info('%s bookmarks saved to playlist cache.', site.upper())

    def get_bookmark(self, rating_key):
        """Retrieve a bookmark by rating_key."""
        bookmarks = self.get_all_bookmarks()
        for bookmrk in bookmarks:
            if bookmrk['rating_key'] == rating_key:
                return bookmrk
        return None

    def get_all_bookmarks(self):
        """Retrieve all bookmarks from the playlist cache."""
        bookmarks = []
        if os.path.exists(self.csv_file):
            with open(self.csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) == 3:
                        rating_key_str, site, group_ids_str = row
                        try:
                            rating_key = int(rating_key_str)
                        except ValueError:
                            continue
                        group_ids = [int(g.strip()) for g in group_ids_str.split(',') if g.strip()]
                        bookmarks.append({
                            'rating_key': rating_key,
                            'site': site,
                            'torrent_group_ids': group_ids
                        })
        return bookmarks

    def reset_cache(self):
        """Deletes the bookmarks playlist cache file if it exists."""
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)
            logger.info('Bookmarks playlist cache file deleted: %s', self.csv_file)
        else:
            logger.info('No bookmarks playlist cache file found to delete.')
