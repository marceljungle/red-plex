"""Unit tests for the PlexManager class."""

import unittest
from unittest.mock import MagicMock, patch
from plex_playlist_creator.plex_manager import PlexManager
from plex_playlist_creator.album_cache import AlbumCache

class TestPlexManager(unittest.TestCase):
    """Test cases for the PlexManager class."""

    def setUp(self):
        """Set up the test environment."""
        # Patch PlexServer and AlbumCache
        patcher1 = patch('plex_playlist_creator.plex_manager.PlexServer')
        patcher2 = patch('plex_playlist_creator.plex_manager.AlbumCache')
        self.addCleanup(patcher1.stop)
        self.addCleanup(patcher2.stop)
        mock_plex_server_class = patcher1.start()
        mock_album_cache_class = patcher2.start()

        # Mock the AlbumCache instance
        self.mock_album_cache = MagicMock(spec=AlbumCache)
        mock_album_cache_class.return_value = self.mock_album_cache
        self.mock_album_cache.load_albums.return_value = {}

        # Mock the PlexServer instance
        self.mock_plex_server = MagicMock()
        mock_plex_server_class.return_value = self.mock_plex_server

        # Initialize PlexManager with mocks
        self.plex_manager = PlexManager(
            url='http://localhost:32400', token='dummy_token', section_name='Music'
            )

    def test_populate_album_cache(self):
        """Test populating the album cache."""
        with patch('plex_playlist_creator.plex_manager.os.listdir') as mock_listdir:
            # Mock the return value of os.listdir
            mock_listdir.return_value = ['file1.mp3', 'file2.mp3']

            # Reset the call count of save_albums
            self.mock_album_cache.save_albums.reset_mock()

            # Mock library and albums
            mock_music_library = MagicMock()
            self.mock_plex_server.library.section.return_value = mock_music_library
            mock_album = MagicMock()
            mock_album.ratingKey = 123
            mock_album.leafCount = 10
            mock_album.title = "Test Album"
            mock_album.tracks.return_value = [MagicMock()]
            mock_track = mock_album.tracks()[0]
            mock_track.media = [MagicMock()]
            mock_media = mock_track.media[0]
            mock_media.parts = [MagicMock()]
            mock_media_part = mock_media.parts[0]
            mock_media_part.file = '/path/to/music/file.mp3'
            mock_music_library.searchAlbums.return_value = [mock_album]

            # Call the method
            self.plex_manager.populate_album_cache()

            # Assertions
            self.mock_album_cache.save_albums.assert_called_once()
            self.assertIn(123, self.plex_manager.album_data)

    def test_reset_album_cache(self):
        """Test resetting the album cache."""
        self.plex_manager.reset_album_cache()
        self.mock_album_cache.reset_cache.assert_called_once()
        self.assertEqual(self.plex_manager.album_data, {})

    def test_get_rating_key(self):
        """Test retrieving the rating key for a given album path."""
        # Set up album data
        self.plex_manager.album_data = {123: 'Test Album'}
        rating_key = self.plex_manager.get_rating_key('Test Album')
        self.assertEqual(rating_key, 123)

    def test_fetch_albums_by_keys(self):
        """Test fetching albums by their rating keys."""
        # Mock fetchItems
        self.mock_plex_server.fetchItems.return_value = ['album1', 'album2']
        albums = self.plex_manager.fetch_albums_by_keys([123, 456])
        self.mock_plex_server.fetchItems.assert_called_with([123, 456])
        self.assertEqual(albums, ['album1', 'album2'])

    def test_create_playlist(self):
        """Test creating a playlist in Plex."""
        # Mock albums
        albums = ['album1', 'album2']
        # Mock createPlaylist
        self.mock_plex_server.createPlaylist.return_value = 'playlist_object'
        result = self.plex_manager.create_playlist('Test Playlist', albums)
        self.mock_plex_server.createPlaylist.assert_called_with('Test Playlist', 'Music', albums)
        self.assertEqual(result, 'playlist_object')

if __name__ == '__main__':
    unittest.main()
