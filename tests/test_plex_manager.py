"""Unit tests for the PlexManager class."""

import unittest
from unittest.mock import patch, MagicMock, mock_open
from plex_playlist_creator.plex_manager import PlexManager

class TestPlexManager(unittest.TestCase):
    """Tests for the PlexManager class."""

    def setUp(self):
        """Set up PlexManager with mocked PlexServer and test data."""

        # Initialize PlexManager with mock data
        self.url = 'http://localhost:32400'
        self.token = 'mock_token'
        self.section_name = 'Music'
        self.csv_file = 'data/test_plex_albums_cache.csv'

        self.plex_manager = PlexManager(self.url, self.token, self.section_name, self.csv_file)

    def test_load_albums_from_csv(self):
        """Test loading album data from a CSV file."""
        with patch('os.path.exists', return_value=True):
            # Mock open to read mock CSV data
            mock_csv_data = '123,Album1\n456,Album2\n'
            with patch('builtins.open', mock_open(read_data=mock_csv_data)):
                album_data = self.plex_manager.load_albums_from_csv()
                expected_data = {123: 'Album1', 456: 'Album2'}
                self.assertEqual(album_data, expected_data)

    def test_get_rating_key(self):
        """Test retrieving a rating key based on album name."""
        self.plex_manager.album_data = {123: 'Album1', 456: 'Album2'}

        rating_key = self.plex_manager.get_rating_key('Album1')
        self.assertEqual(rating_key, 123)

        rating_key = self.plex_manager.get_rating_key('NonExistentAlbum')
        self.assertIsNone(rating_key)

    @patch('plex_playlist_creator.plex_manager.PlexServer.fetchItems')
    def test_fetch_albums_by_keys(self, mock_fetch_items):
        """Test fetching albums by rating keys."""
        mock_fetch_items.return_value = ['AlbumObject1', 'AlbumObject2']

        albums = self.plex_manager.fetch_albums_by_keys([123, 456])
        mock_fetch_items.assert_called_with([123, 456])
        self.assertEqual(albums, ['AlbumObject1', 'AlbumObject2'])

    @patch('plex_playlist_creator.plex_manager.PlexServer.createPlaylist')
    def test_create_playlist(self, mock_create_playlist):
        """Test creating a playlist in Plex."""
        mock_create_playlist.return_value = 'MockPlaylistObject'

        playlist = self.plex_manager\
            .create_playlist('Test Playlist', ['AlbumObject1', 'AlbumObject2'])
        mock_create_playlist.assert_called_with('Test Playlist', ['AlbumObject1', 'AlbumObject2'])
        self.assertEqual(playlist, 'MockPlaylistObject')

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('plex_playlist_creator.plex_manager.os.path.exists')
    @patch('plex_playlist_creator.plex_manager.os.listdir')
    @patch('plex_playlist_creator.plex_manager.PlexServer')
    def test_save_albums_to_csv(self, mock_listdir, mock_exists, mock_plex_server, mock_file, _):
        """Test saving album data to a CSV file."""
        mock_exists.return_value = False
        mock_plex_server = mock_plex_server.return_value

        mock_album = MagicMock()
        mock_album.ratingKey = 123
        mock_album.leafCount = 10
        mock_album.tracks.return_value = [MagicMock()]
        mock_album.title = 'Test Album'

        mock_track = mock_album.tracks.return_value[0]
        mock_media = MagicMock()
        mock_part = MagicMock()
        mock_part.file = '/path/to/album/song.mp3'
        mock_media.parts = [mock_part]
        mock_track.media = [mock_media]

        mock_listdir.return_value = ['song.mp3']

        mock_library_section = mock_plex_server.library.section.return_value
        mock_library_section.searchAlbums.return_value = [mock_album]

        with patch('plex_playlist_creator.plex_manager.os.path.dirname',
                   return_value='/path/to/album'), \
             patch('plex_playlist_creator.plex_manager.os.path.basename', return_value='album'):
            self.plex_manager.save_albums_to_csv()
            mock_file.assert_called_with(self.csv_file, 'w', newline='', encoding='utf-8')

if __name__ == '__main__':
    unittest.main()
