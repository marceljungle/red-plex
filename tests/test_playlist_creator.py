"""Unit tests for the PlaylistCreator class."""

import unittest
from unittest.mock import MagicMock
import tempfile
import os
from src.playlist_creator import PlaylistCreator

# pylint: disable=duplicate-code
class TestPlaylistCreator(unittest.TestCase):
    """Test cases for the PlaylistCreator class."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory and cache file to prevent modifying the real cache
        self.test_dir = tempfile.TemporaryDirectory() # pylint: disable=consider-using-with
        self.cache_file = os.path.join(self.test_dir.name, 'playlist_cache.csv')

        # Mock the PlexManager and GazelleAPI
        self.mock_plex_manager = MagicMock()
        self.mock_gazelle_api = MagicMock()

        # Initialize PlaylistCreator with mocks and temporary cache file
        self.playlist_creator = PlaylistCreator(
            self.mock_plex_manager,
            self.mock_gazelle_api,
            cache_file=self.cache_file
        )

    def tearDown(self):
        """Clean up after tests."""
        self.test_dir.cleanup()

    def test_create_playlist_from_collage(self):
        """Test creating a playlist from a collage."""
        # Mock data returned by get_collage
        self.mock_gazelle_api.get_collage.return_value = {
            'response': {
                'name': 'Test Collage',
                'torrentGroupIDList': [456]
            }
        }

        # Mock the cache to be empty
        self.playlist_creator.playlist_cache.load_cache = MagicMock(return_value={})

        # Mock get_torrent_group to return torrent group data
        self.mock_gazelle_api.get_torrent_group.return_value = {
            'response': {
                'torrents': [
                    {'filePath': 'path/to/album'}
                ]
            }
        }

        # Mock get_rating_keys to return a rating key
        self.mock_plex_manager.get_rating_keys.return_value = [789]

        # Mock fetch_albums_by_keys to return album objects
        self.mock_plex_manager.fetch_albums_by_keys.return_value = ['Album Object']

        # Mock create_playlist to return a playlist with a ratingKey
        mock_playlist = MagicMock()
        mock_playlist.ratingKey = 12345
        self.mock_plex_manager.create_playlist.return_value = mock_playlist

        # Mock get_playlist_by_name to return None (simulate playlist does not exist)
        self.mock_plex_manager.get_playlist_by_name.return_value = None

        # Run the method under test
        self.playlist_creator.create_or_update_playlist_from_collage(123)

        # Assertions
        self.mock_gazelle_api.get_torrent_group.assert_called_with(456)

if __name__ == '__main__':
    unittest.main()
