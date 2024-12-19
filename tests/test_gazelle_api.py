"""Unit tests for the GazelleAPI class."""

import unittest
from unittest.mock import MagicMock, patch
from src.infrastructure.rest.gazelle_api import GazelleAPI

class TestGazelleAPI(unittest.TestCase):
    """Test cases for the GazelleAPI class."""

    def setUp(self):
        """Set up the test environment."""
        self.api_key = 'dummy_api_key'
        self.base_url = 'https://example.com'
        self.gazelle_api = GazelleAPI(self.base_url, self.api_key)

    @patch('src.infrastructure.rest.gazelle_api.requests.get')
    def test_api_call(self, mock_get):
        """Test making an API call to the Gazelle-based service."""
        # Mock response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'response': 'data'}
        mock_get.return_value = mock_response

        # Call the method
        result = self.gazelle_api.api_call('action', {'param1': 'value1'})

        # Assertions
        self.assertEqual(result, {'response': 'data'})
        mock_get.assert_called_once()
        expected_url = f'{self.base_url.rstrip("/")}/ajax.php?action=action&param1=value1'
        mock_get.assert_called_with(
            expected_url,
            headers={'Authorization': self.api_key},
            timeout=10
        )

    def test_normalize(self):
        """Test normalizing text."""
        text = 'Test\u200eText &amp; More'
        normalized_text = self.gazelle_api.normalize(text)
        self.assertEqual(normalized_text, 'TestText & More')

    @patch.object(GazelleAPI, 'api_call')
    def test_get_collage(self, mock_api_call):
        """Test retrieving a collage from the Gazelle-based service."""
        mock_api_call.return_value = {'response': 'collage_data'}
        collage_id = 123
        result = self.gazelle_api.get_collage(collage_id)
        mock_api_call.assert_called_with('collage', {'id': '123', 'showonlygroups': 'true'})
        self.assertEqual(result, {'response': 'collage_data'})

    @patch('src.infrastructure.rest.gazelle_api.GazelleAPI.api_call')
    def test_get_torrent_group(self, mock_api_call):
        """Test retrieving a torrent group from the Gazelle-based service."""
        mock_api_call.return_value = {'response': {'group': 'group data'}}
        result = self.gazelle_api.get_torrent_group(456)  # Corrected to self.gazelle_api
        self.assertEqual(result, {'response': {'group': 'group data'}})
        mock_api_call.assert_called_with('torrentgroup', {'id': '456'})

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
        result = self.gazelle_api.get_file_paths_from_torrent_group(torrent_group)
        self.assertEqual(result, ['Path1', 'Path2'])

if __name__ == '__main__':
    unittest.main()
