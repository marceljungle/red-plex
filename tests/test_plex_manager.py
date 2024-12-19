"""Unit tests for the PlexManager class."""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from src.infrastructure.plex.plex_manager import PlexManager
from src.infrastructure.cache.album_cache import AlbumCache

class TestPlexManager(unittest.TestCase):
    """Test cases for the PlexManager class."""

    def setUp(self):
        """Set up the test environment."""
        # Patch PlexServer and AlbumCache
        patcher1 = patch('src.infrastructure.plex.plex_manager.PlexServer')
        patcher2 = patch('src.infrastructure.plex.plex_manager.AlbumCache')
        self.addCleanup(patcher1.stop)
        self.addCleanup(patcher2.stop)
        mock_plex_server_class = patcher1.start()
        mock_album_cache_class = patcher2.start()

        # Mock the AlbumCache instance
        self.mock_album_cache = MagicMock(spec=AlbumCache)
        mock_album_cache_class.return_value = self.mock_album_cache
        self.mock_album_cache.load_albums.return_value = {}

        # Create the full mock chain BEFORE creating PlexManager
        self.mock_music_library = MagicMock(name='mock_music_library')
        self.mock_library = MagicMock(name='mock_library')
        self.mock_library.section.return_value = self.mock_music_library

        # Set up the PlexServer instance with the proper chain
        self.mock_plex_server = MagicMock()
        self.mock_plex_server.library = self.mock_library
        mock_plex_server_class.return_value = self.mock_plex_server

        # Initialize PlexManager with mocks
        self.plex_manager = PlexManager(
            url='http://localhost:32400',
            token='dummy_token',
            section_name='Music'
        )

    def test_populate_album_cache(self):
        """Test populating the album cache."""

        # Reset the call count of save_albums
        self.mock_album_cache.save_albums.reset_mock()

        # Create a specific datetime for testing
        test_date = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Create a mock album with all required attributes
        mock_album = MagicMock()
        mock_album.ratingKey = "123"
        mock_album.addedAt = test_date
        mock_album.title = "Test Album"

        # Mock the track hierarchy
        mock_track = MagicMock()
        mock_media = MagicMock()
        mock_part = MagicMock()
        mock_part.file = '/path/to/music/Test Album/file.mp3'
        mock_media.parts = [mock_part]
        mock_track.media = [mock_media]
        mock_album.tracks.return_value = [mock_track]

        # Set up the search results
        self.mock_music_library.searchAlbums.return_value = [mock_album]

        # Call the method
        self.plex_manager.populate_album_cache()

        # Verify searchAlbums was called with the correct filter
        expected_filters = {"addedAt>>": datetime(1970, 1, 1, tzinfo=timezone.utc)}
        self.mock_music_library.searchAlbums.assert_called_once_with(filters=expected_filters)

        # Verify the album data structure
        expected_album_data = {
            123: ('/path/to/music/Test Album', test_date)
        }

        # Assertions
        self.mock_album_cache.save_albums.assert_called_once_with(expected_album_data)
        self.assertEqual(self.plex_manager.album_data, expected_album_data)

    def test_get_rating_keys(self):
        """Test retrieving the rating key for a given album path."""
        test_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        # Set up album data with the correct structure
        self.plex_manager.album_data = {
            123: ('/path/to/music/Test Album', test_date)
        }

        # Test with a path that should match
        rating_keys = self.plex_manager.get_rating_keys('Test Album')
        self.assertEqual(rating_keys, [123])

        # Test with a path that shouldn't match
        rating_keys = self.plex_manager.get_rating_keys('Non Existent Album')
        self.assertEqual(rating_keys, [])

    def test_fetch_albums_by_keys(self):
        """Test fetching albums by their rating keys."""
        mock_albums = [MagicMock(), MagicMock()]
        self.mock_plex_server.fetchItems.return_value = mock_albums

        albums = self.plex_manager.fetch_albums_by_keys([123, 456])

        self.mock_plex_server.fetchItems.assert_called_with([123, 456])
        self.assertEqual(albums, mock_albums)

    def test_create_playlist(self):
        """Test creating a playlist in Plex."""
        mock_albums = [MagicMock(), MagicMock()]
        mock_playlist = MagicMock()
        self.mock_plex_server.createPlaylist.return_value = mock_playlist

        result = self.plex_manager.create_playlist('Test Playlist', mock_albums)

        self.mock_plex_server.createPlaylist.assert_called_with(
            'Test Playlist', 
            'Music', 
            mock_albums
        )
        self.assertEqual(result, mock_playlist)

if __name__ == '__main__':
    unittest.main()
