import unittest
from unittest.mock import patch, MagicMock
from plex_playlist_creator.redacted_api import RedactedAPI

class TestRedactedAPI(unittest.TestCase):
    def setUp(self):
        self.api_key = 'mock_api_key'
        self.red_api = RedactedAPI(self.api_key)

    @patch('plex_playlist_creator.redacted_api.requests.get')
    def test_api_call(self, mock_get):
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {'status': 'success', 'response': {}}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Call the api_call method
        action = 'test_action'
        params = {'param1': 'value1'}
        result = self.red_api.api_call(action, params)

        # Verify the constructed URL
        expected_url = f'{self.red_api.BASE_URL}{action}&param1=value1'
        mock_get.assert_called_with(expected_url, headers={'Authorization': self.api_key})

        # Verify the result
        self.assertEqual(result, {'status': 'success', 'response': {}})

    @patch.object(RedactedAPI, 'api_call')
    def test_get_collage(self, mock_api_call):
        # Mock api_call response
        mock_api_call.return_value = {'status': 'success', 'response': 'collage_data'}

        collage_id = '123'
        result = self.red_api.get_collage(collage_id)

        # Verify api_call was called with correct parameters
        mock_api_call.assert_called_with('collage', {'id': '123', 'showonlygroups': 'true'})
        self.assertEqual(result, {'status': 'success', 'response': 'collage_data'})

    @patch.object(RedactedAPI, 'api_call')
    def test_get_torrent_group(self, mock_api_call):
        # Mock api_call response
        mock_api_call.return_value = {'status': 'success', 'response': 'torrent_group_data'}

        group_id = '456'
        result = self.red_api.get_torrent_group(group_id)

        # Verify api_call was called with correct parameters
        mock_api_call.assert_called_with('torrentgroup', {'id': '456'})
        self.assertEqual(result, {'status': 'success', 'response': 'torrent_group_data'})

    def test_get_file_paths_from_torrent_group(self):
        torrent_group = {
            'response': {
                'torrents': [
                    {'filePath': 'Album1'},
                    {'filePath': 'Album2'},
                    {'filePath': None},  # Simulate missing filePath
                ]
            }
        }

        file_paths = self.red_api.get_file_paths_from_torrent_group(torrent_group)
        self.assertEqual(file_paths, ['Album1', 'Album2'])

if __name__ == '__main__':
    unittest.main()