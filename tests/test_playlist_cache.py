"""Unit tests for the PlaylistCache class."""

import os
import unittest
import tempfile
from plex_playlist_creator.playlist_cache import PlaylistCache

# pylint: disable=consider-using-with, duplicate-code
class TestPlaylistCache(unittest.TestCase):
    """Test cases for the PlaylistCache class."""

    def setUp(self):
        """Set up a temporary file for testing."""
        # Create a temporary directory
        self.test_dir = tempfile.TemporaryDirectory()
        # Path to a temporary CSV file
        self.csv_file = os.path.join(self.test_dir.name, 'playlist_cache.csv')
        # Instantiate the PlaylistCache with the temporary file
        self.cache = PlaylistCache(csv_file=self.csv_file)

    def tearDown(self):
        """Clean up the temporary file."""
        # Close and remove the temporary directory and its contents
        self.test_dir.cleanup()

    def test_save_and_load_playlist(self):
        """Test saving and loading playlists."""
        # Define test data
        playlist_id = 12345
        playlist_name = 'Test Playlist'
        torrent_group_ids = [1, 2, 3, 4, 5]

        # Save the playlist
        self.cache.save_playlist(playlist_id, playlist_name, torrent_group_ids)

        # Load the cache and verify contents
        loaded_cache = self.cache.load_cache()
        self.assertIn(playlist_id, loaded_cache)
        self.assertEqual(loaded_cache[playlist_id]['name'], playlist_name)
        self.assertEqual(loaded_cache[playlist_id]['torrent_group_ids'], torrent_group_ids)

    def test_get_playlist(self):
        """Test retrieving a playlist by ID."""
        # Define test data
        playlist_id = 12345
        playlist_name = 'Test Playlist'
        torrent_group_ids = [1, 2, 3]

        # Save the playlist
        self.cache.save_playlist(playlist_id, playlist_name, torrent_group_ids)

        # Retrieve the playlist by ID
        playlist = self.cache.get_playlist(playlist_id)
        self.assertIsNotNone(playlist)
        self.assertEqual(playlist['name'], playlist_name)
        self.assertEqual(playlist['torrent_group_ids'], torrent_group_ids)

    def test_get_playlist_by_name(self):
        """Test retrieving a playlist by name."""
        # Define test data
        playlist_id = 67890
        playlist_name = 'Another Playlist'
        torrent_group_ids = [10, 20, 30]

        # Save the playlist
        self.cache.save_playlist(playlist_id, playlist_name, torrent_group_ids)

        # Retrieve the playlist by name
        pid, playlist = self.cache.get_playlist_by_name(playlist_name)
        self.assertIsNotNone(pid)
        self.assertEqual(pid, playlist_id)
        self.assertIsNotNone(playlist)
        self.assertEqual(playlist['name'], playlist_name)
        self.assertEqual(playlist['torrent_group_ids'], torrent_group_ids)

    def test_reset_cache(self):
        """Test resetting the cache."""
        # Define test data
        playlist_id = 11111
        playlist_name = 'Playlist to Reset'
        torrent_group_ids = [100, 200, 300]

        # Save the playlist
        self.cache.save_playlist(playlist_id, playlist_name, torrent_group_ids)

        # Ensure the cache file exists
        self.assertTrue(os.path.exists(self.csv_file))

        # Reset the cache
        self.cache.reset_cache()

        # Verify the cache file is deleted
        self.assertFalse(os.path.exists(self.csv_file))

        # Load the cache and verify it's empty
        loaded_cache = self.cache.load_cache()
        self.assertEqual(len(loaded_cache), 0)

    def test_multiple_playlists(self):
        """Test saving and loading multiple playlists."""
        # Define test data
        playlists = [
            (123, 'Playlist One', [1, 2, 3]),
            (456, 'Playlist Two', [4, 5, 6]),
            (789, 'Playlist Three', [7, 8, 9]),
        ]

        # Save all playlists
        for pid, name, group_ids in playlists:
            self.cache.save_playlist(pid, name, group_ids)

        # Load the cache and verify contents
        loaded_cache = self.cache.load_cache()
        self.assertEqual(len(loaded_cache), 3)
        for pid, name, group_ids in playlists:
            self.assertIn(pid, loaded_cache)
            self.assertEqual(loaded_cache[pid]['name'], name)
            self.assertEqual(loaded_cache[pid]['torrent_group_ids'], group_ids)

    def test_playlist_not_found(self):
        """Test retrieving a non-existent playlist."""
        # Attempt to retrieve a playlist that doesn't exist
        playlist = self.cache.get_playlist(99999)
        self.assertIsNone(playlist)

        pid, playlist = self.cache.get_playlist_by_name('Nonexistent Playlist')
        self.assertIsNone(pid)
        self.assertIsNone(playlist)

if __name__ == '__main__':
    unittest.main()
