"""Unit tests for the PlaylistCreator class."""

import unittest
from unittest.mock import MagicMock
from plex_playlist_creator.playlist_creator import PlaylistCreator

class TestPlaylistCreator(unittest.TestCase):
    """Tests for the PlaylistCreator class."""

    def setUp(self):
        """Set up mocks for PlexManager and RedactedAPI."""
        self.mock_plex_manager = MagicMock()
        self.mock_red_api = MagicMock()
        self.playlist_creator = PlaylistCreator(self.mock_plex_manager, self.mock_red_api)

    def test_create_playlist_from_collage(self):
        """Test creating a playlist from a collage ID."""
        collage_id = '123'
        collage_name = 'Test Collage'
        group_ids = ['1', '2']
        rating_keys = [111, 222]

        # Mock the return values of RedactedAPI methods
        self.mock_red_api.get_collage.return_value = {
            'response': {
                'name': collage_name,
                'torrentGroupIDList': group_ids
            }
        }
        self.mock_red_api.get_torrent_group.side_effect = [
            {'response': {'torrents': [{'filePath': 'Album1'}]}},
            {'response': {'torrents': [{'filePath': 'Album2'}]}}
        ]
        self.mock_red_api.get_file_paths_from_torrent_group.side_effect = [
            ['Album1'],
            ['Album2']
        ]

        # Mock the return values of PlexManager methods
        self.mock_plex_manager.get_rating_key.side_effect = rating_keys
        self.mock_plex_manager.fetch_albums_by_keys.return_value = ['AlbumObject1', 'AlbumObject2']
        self.mock_plex_manager.create_playlist.return_value = 'MockPlaylistObject'

        # Call the method under test
        self.playlist_creator.create_playlist_from_collage(collage_id)

        # Assertions to verify correct calls
        self.mock_red_api.get_collage.assert_called_with(collage_id)
        self.assertEqual(self.mock_red_api.get_torrent_group.call_count, 2)
        self.assertEqual(self.mock_red_api.get_file_paths_from_torrent_group.call_count, 2)
        self.assertEqual(self.mock_plex_manager.get_rating_key.call_count, 2)
        self.mock_plex_manager.fetch_albums_by_keys.assert_called_with([111, 222])
        self.mock_plex_manager.create_playlist\
            .assert_called_with(collage_name, ['AlbumObject1', 'AlbumObject2'])

if __name__ == '__main__':
    unittest.main()
