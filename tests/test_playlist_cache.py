"""Unit tests for the PlaylistCache class."""

import os
import unittest
import tempfile
from src.infrastructure.cache.collage_playlist_cache import CollagePlaylistCache

class TestPlaylistCache(unittest.TestCase):
    """Test cases for the PlaylistCache class."""

    def setUp(self):
        """Set up a temporary file for testing."""
        # pylint: disable=consider-using-with
        self.test_dir = tempfile.TemporaryDirectory()
        self.csv_file = os.path.join(self.test_dir.name, 'playlist_cache.csv')
        self.cache = CollagePlaylistCache(csv_file=self.csv_file)

    def tearDown(self):
        """Clean up the temporary file."""
        self.test_dir.cleanup()

    def test_save_and_load_playlist(self):
        """Test saving and loading playlists."""
        playlist_id = 12345
        playlist_name = 'Test Playlist'
        torrent_group_ids = [1, 2, 3, 4, 5]

        # Save the playlist with dummy site and collage_id
        self.cache.save_playlist(
            rating_key=playlist_id,
            playlist_name=playlist_name,
            site='red',
            collage_id=9999,
            torrent_group_ids=torrent_group_ids
        )

        all_playlists = self.cache.get_all_playlists()
        # Find the playlist by rating_key
        found = next((p for p in all_playlists if p['rating_key'] == playlist_id), None)
        self.assertIsNotNone(found)
        self.assertEqual(found['playlist_name'], playlist_name)
        self.assertEqual(found['torrent_group_ids'], torrent_group_ids)

    def test_get_playlist(self):
        """Test retrieving a playlist by ID."""
        playlist_id = 12345
        playlist_name = 'Test Playlist'
        torrent_group_ids = [1, 2, 3]

        self.cache.save_playlist(
            rating_key=playlist_id,
            playlist_name=playlist_name,
            site='red',
            collage_id=9999,
            torrent_group_ids=torrent_group_ids
        )

        playlist = self.cache.get_playlist(playlist_id)
        self.assertIsNotNone(playlist)
        self.assertEqual(playlist['playlist_name'], playlist_name)
        self.assertEqual(playlist['torrent_group_ids'], torrent_group_ids)

    def test_get_playlist_by_name(self):
        """Test retrieving a playlist by name (simulated by searching all)."""
        playlist_id = 67890
        playlist_name = 'Another Playlist'
        torrent_group_ids = [10, 20, 30]

        self.cache.save_playlist(
            rating_key=playlist_id,
            playlist_name=playlist_name,
            site='red',
            collage_id=9999,
            torrent_group_ids=torrent_group_ids
        )

        # Since get_playlist_by_name no longer exists, we simulate it:
        all_playlists = self.cache.get_all_playlists()
        found_entry = None
        found_id = None
        for p in all_playlists:
            if p['playlist_name'] == playlist_name:
                found_entry = p
                found_id = p['rating_key']
                break

        self.assertIsNotNone(found_id)
        self.assertEqual(found_id, playlist_id)
        self.assertIsNotNone(found_entry)
        self.assertEqual(found_entry['playlist_name'], playlist_name)
        self.assertEqual(found_entry['torrent_group_ids'], torrent_group_ids)

    def test_reset_cache(self):
        """Test resetting the cache."""
        playlist_id = 11111
        playlist_name = 'Playlist to Reset'
        torrent_group_ids = [100, 200, 300]

        self.cache.save_playlist(
            rating_key=playlist_id,
            playlist_name=playlist_name,
            site='red',
            collage_id=9999,
            torrent_group_ids=torrent_group_ids
        )

        # Ensure the cache file exists
        self.assertTrue(os.path.exists(self.csv_file))

        # Reset the cache
        self.cache.reset_cache()

        # Verify the cache file is deleted
        self.assertFalse(os.path.exists(self.csv_file))

        # After reset, no playlists should be found
        all_playlists = self.cache.get_all_playlists()
        self.assertEqual(len(all_playlists), 0)

    def test_multiple_playlists(self):
        """Test saving and loading multiple playlists."""
        playlists = [
            (123, 'Playlist One', [1, 2, 3]),
            (456, 'Playlist Two', [4, 5, 6]),
            (789, 'Playlist Three', [7, 8, 9]),
        ]

        # Save all playlists
        for pid, name, group_ids in playlists:
            self.cache.save_playlist(
                rating_key=pid,
                playlist_name=name,
                site='red',
                collage_id=9999,
                torrent_group_ids=group_ids
            )

        all_playlists = self.cache.get_all_playlists()
        self.assertEqual(len(all_playlists), 3)
        # Check each one
        for pid, name, group_ids in playlists:
            found = next((p for p in all_playlists if p['rating_key'] == pid), None)
            self.assertIsNotNone(found)
            self.assertEqual(found['playlist_name'], name)
            self.assertEqual(found['torrent_group_ids'], group_ids)

    def test_playlist_not_found(self):
        """Test retrieving a non-existent playlist."""
        # Attempt to retrieve a playlist that doesn't exist by ID
        playlist = self.cache.get_playlist(99999)
        self.assertIsNone(playlist)

        # Attempt to find by name (simulate as done before)
        all_playlists = self.cache.get_all_playlists()
        found = any(p for p in all_playlists if p['playlist_name'] == 'Nonexistent Playlist')
        self.assertFalse(found)


if __name__ == '__main__':
    unittest.main()
