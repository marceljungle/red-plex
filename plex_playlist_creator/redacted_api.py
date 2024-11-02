import requests
import html
from ratelimit import limits, sleep_and_retry
from retrying import retry
from plex_playlist_creator.logger import logger

class RedactedAPI:
    BASE_URL = 'https://redacted.ch/ajax.php?action='

    def __init__(self, api_key):
        self.headers = {'Authorization': api_key}

    @staticmethod
    def retry_if_connection_error(exception):
        return isinstance(exception, ConnectionError)

    @retry(retry_on_exception=retry_if_connection_error, wait_fixed=2000)
    @sleep_and_retry
    @limits(calls=10, period=10)
    def api_call(self, action, params):
        """Makes a rate-limited API call to RED."""
        formatted_params = '&' + '&'.join(f'{key}={value}' for key, value in params.items())
        formatted_url = f'{self.BASE_URL}{action}{formatted_params}'
        logger.info(f'Calling RED API: {formatted_url}')
        response = requests.get(formatted_url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_collage(self, collage_id):
        """Retrieves collage data from RED."""
        params = {'id': str(collage_id), 'showonlygroups': 'true'}
        return self.api_call('collage', params)

    def get_torrent_group(self, torrent_group_id):
        """Retrieves torrent group data from RED."""
        params = {'id': torrent_group_id}
        return self.api_call('torrentgroup', params)

    def get_file_paths_from_torrent_group(self, torrent_group):
        """Extracts file paths from a torrent group."""
        file_paths = [
            torrent.get("filePath") 
            for torrent in torrent_group.get("response", {}).get("torrents", [])
        ]
        return [html.unescape(path) for path in file_paths if path]