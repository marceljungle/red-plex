"""Unit tests for the PlaylistCreator class."""

import unittest
from unittest.mock import MagicMock
from plex_playlist_creator.playlist_creator import PlaylistCreator

class TestPlaylistCreator(unittest.TestCase):
    """Test cases for the PlaylistCreator class."""

    def setUp(self):
        """Set up the test environment."""
        # Mock PlexManager and RedactedAPI
        self.mock_plex_manager = MagicMock()
        self.mock_redacted_api = MagicMock()
        self.playlist_creator = PlaylistCreator(self.mock_plex_manager, self.mock_redacted_api)

    def test_create_playlist_from_collage(self):
        """Test creating a playlist from a collage."""
        collage_id = 123
        # Mock collage data
        collage_data = {
            'response': {
                'name': 'Test Collage',
                'torrentGroupIDList': [456]
            }
        }
        self.mock_redacted_api.get_collage.return_value = collage_data

        # Mock torrent group data
        torrent_group_data = {
            'response': {
                'torrents': [{'filePath': 'Test Album'}]
            }
        }
        self.mock_redacted_api.get_torrent_group.return_value = torrent_group_data
        self.mock_redacted_api.get_file_paths_from_torrent_group.return_value = ['Test Album']

        # Mock PlexManager methods
        self.mock_plex_manager.get_rating_key.return_value = 789
        self.mock_plex_manager.fetch_albums_by_keys.return_value = ['album_object']
        self.mock_plex_manager.create_playlist.return_value = 'playlist_object'

        # Call the method
        self.playlist_creator.create_playlist_from_collage(collage_id)

        # Assertions
        self.mock_redacted_api.get_collage.assert_called_with(collage_id)
        self.mock_redacted_api.get_torrent_group.assert_called_with(456)
        self.mock_redacted_api.get_file_paths_from_torrent_group.assert_called_with(
            torrent_group_data)
        self.mock_plex_manager.get_rating_key.assert_called_with('Test Album')
        self.mock_plex_manager.fetch_albums_by_keys.assert_called_with([789])
        self.mock_plex_manager.create_playlist.assert_called_with('Test Collage', ['album_object'])

if __name__ == '__main__':
    unittest.main()
