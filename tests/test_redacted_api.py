"""Unit tests for the RedactedAPI class."""

import unittest
from unittest.mock import MagicMock, patch
from plex_playlist_creator.redacted_api import RedactedAPI

class TestRedactedAPI(unittest.TestCase):
    """Test cases for the RedactedAPI class."""

    def setUp(self):
        """Set up the test environment."""
        self.api_key = 'dummy_api_key'
        self.red_api = RedactedAPI(self.api_key)

    @patch('plex_playlist_creator.redacted_api.requests.get')
    def test_api_call(self, mock_get):
        """Test making an API call to RED."""
        # Mock response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'response': 'data'}
        mock_get.return_value = mock_response

        # Call the method
        result = self.red_api.api_call('action', {'param1': 'value1'})

        # Assertions
        self.assertEqual(result, {'response': 'data'})
        mock_get.assert_called_once()

    def test_normalize(self):
        """Test normalizing text."""
        text = 'Test\u200eText &amp; More'
        normalized_text = self.red_api.normalize(text)
        self.assertEqual(normalized_text, 'TestText & More')

    @patch.object(RedactedAPI, 'api_call')
    def test_get_collage(self, mock_api_call):
        """Test retrieving a collage from RED."""
        mock_api_call.return_value = {'response': 'collage_data'}
        collage_id = 123
        result = self.red_api.get_collage(collage_id)
        mock_api_call.assert_called_with('collage', {'id': '123', 'showonlygroups': 'true'})
        self.assertEqual(result, {'response': 'collage_data'})

    @patch.object(RedactedAPI, 'api_call')
    def test_get_torrent_group(self, mock_api_call):
        """Test retrieving a torrent group from RED."""
        mock_api_call.return_value = {'response': 'torrent_group_data'}
        group_id = 456
        result = self.red_api.get_torrent_group(group_id)
        mock_api_call.assert_called_with('torrentgroup', {'id': 456})
        self.assertEqual(result, {'response': 'torrent_group_data'})

    def test_get_file_paths_from_torrent_group(self):
        """Test extracting file paths from a torrent group."""
        torrent_group = {
            'response': {
                'torrents': [
                    {'filePath': 'Path1'},
                    {'filePath': 'Path2'}
                ]
            }
        }
        result = self.red_api.get_file_paths_from_torrent_group(torrent_group)
        self.assertEqual(result, ['Path1', 'Path2'])

if __name__ == '__main__':
    unittest.main()
