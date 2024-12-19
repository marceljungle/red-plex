"""Unit tests for the BookmarksCache class."""

import os
import unittest
import tempfile
from src.infrastructure.cache.bookmarks_playlist_cache import BookmarksPlaylistCache

class TestBookmarksCache(unittest.TestCase):
    """Test cases for the BookmarksCache class."""

    def setUp(self):
        """Set up a temporary file for testing."""
        # pylint: disable=consider-using-with
        self.test_dir = tempfile.TemporaryDirectory()
        self.csv_file = os.path.join(self.test_dir.name, 'bookmarks_cache.csv')
        self.cache = BookmarksPlaylistCache(csv_file=self.csv_file)

    def tearDown(self):
        """Clean up the temporary file."""
        self.test_dir.cleanup()

    def test_save_and_load_bookmark(self):
        """Test saving and loading bookmarks."""
        bookmark_id = 12345
        site = 'red'
        torrent_group_ids = [1, 2, 3, 4, 5]

        # Save the bookmark
        self.cache.save_bookmarks(
            rating_key=bookmark_id,
            site=site,
            torrent_group_ids=torrent_group_ids
        )

        all_bookmarks = self.cache.get_all_bookmarks()
        # Find the bookmark by rating_key
        found = next((b for b in all_bookmarks if b['rating_key'] == bookmark_id), None)
        self.assertIsNotNone(found)
        self.assertEqual(found['site'], site)
        self.assertEqual(found['torrent_group_ids'], torrent_group_ids)

    def test_get_bookmark(self):
        """Test retrieving a bookmark by ID."""
        bookmark_id = 12345
        site = 'red'
        torrent_group_ids = [1, 2, 3]

        self.cache.save_bookmarks(
            rating_key=bookmark_id,
            site=site,
            torrent_group_ids=torrent_group_ids
        )

        bookmark = self.cache.get_bookmark(bookmark_id)
        self.assertIsNotNone(bookmark)
        self.assertEqual(bookmark['site'], site)
        self.assertEqual(bookmark['torrent_group_ids'], torrent_group_ids)

    def test_reset_cache(self):
        """Test resetting the cache."""
        bookmark_id = 11111
        site = 'red'
        torrent_group_ids = [100, 200, 300]

        self.cache.save_bookmarks(
            rating_key=bookmark_id,
            site=site,
            torrent_group_ids=torrent_group_ids
        )

        # Ensure the cache file exists
        self.assertTrue(os.path.exists(self.csv_file))

        # Reset the cache
        self.cache.reset_cache()

        # Verify the cache file is deleted
        self.assertFalse(os.path.exists(self.csv_file))

        # After reset, no bookmarks should be found
        all_bookmarks = self.cache.get_all_bookmarks()
        self.assertEqual(len(all_bookmarks), 0)

    def test_multiple_bookmarks(self):
        """Test saving and loading multiple bookmarks."""
        bookmarks = [
            (123, 'red', [1, 2, 3]),
            (456, 'ops', [4, 5, 6]),
            (789, 'red', [7, 8, 9]),
        ]

        # Save all bookmarks
        for bid, site, group_ids in bookmarks:
            self.cache.save_bookmarks(
                rating_key=bid,
                site=site,
                torrent_group_ids=group_ids
            )

        all_bookmarks = self.cache.get_all_bookmarks()
        self.assertEqual(len(all_bookmarks), 3)
        # Check each one
        for bid, site, group_ids in bookmarks:
            found = next((b for b in all_bookmarks if b['rating_key'] == bid), None)
            self.assertIsNotNone(found)
            self.assertEqual(found['site'], site)
            self.assertEqual(found['torrent_group_ids'], group_ids)

    def test_bookmark_not_found(self):
        """Test retrieving a non-existent bookmark."""
        # Attempt to retrieve a bookmark that doesn't exist by ID
        bookmark = self.cache.get_bookmark(99999)
        self.assertIsNone(bookmark)

        # Attempt to find non-existent bookmarks
        all_bookmarks = self.cache.get_all_bookmarks()
        found = any(b for b in all_bookmarks if b['site'] == 'Nonexistent Site')
        self.assertFalse(found)


if __name__ == '__main__':
    unittest.main()
