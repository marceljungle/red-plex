# plex_playlist_creator/redacted_api.py

import requests
import html
import time
from pyrate_limiter import Limiter, Rate, Duration, BucketFullException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed
from plex_playlist_creator.logger import logger

class RedactedAPI:
    BASE_URL = 'https://redacted.ch/ajax.php?action='

    def __init__(self, api_key):
        self.headers = {'Authorization': api_key}
        # Initialize the rate limiter: max 10 calls per 10 seconds
        rate = Rate(10, Duration.SECOND * 10)
        # Set raise_when_fail=False to handle delays instead of raising exceptions
        # Set max_delay=None to allow unlimited delay
        self.limiter = Limiter(rate, raise_when_fail=False, max_delay=float('inf'))

    @retry(
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_fixed(2)
    )
    def api_call(self, action, params):
        """Makes a rate-limited API call to RED with retries."""
        formatted_params = '&' + '&'.join(f'{key}={value}' for key, value in params.items())
        formatted_url = f'{self.BASE_URL}{action}{formatted_params}'
        logger.info(f'Calling RED API: {formatted_url}')

        # Use the limiter to enforce rate limiting
        while True:
            # Try to acquire permission to make the API call
            did_acquire = self.limiter.try_acquire('api_call')
            if did_acquire:
                # Permission acquired; make the API call
                response = requests.get(formatted_url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            else:
                # Rate limit exceeded; limiter will handle delay automatically
                delay = self.limiter.bucket_factory.last_delay
                logger.warning(f'Rate limit exceeded. Sleeping for {delay / 1000:.2f} seconds.')
                time.sleep(delay / 1000)

    def get_collage(self, collage_id):
        """Retrieves collage data from RED."""
        params = {'id': str(collage_id), 'showonlygroups': 'true'}
        json_data = self.api_call('collage', params)
        logger.info(f'Retrieved collage data for collage_id {collage_id}')
        return json_data

    def get_torrent_group(self, torrent_group_id):
        """Retrieves torrent group data from RED."""
        params = {'id': torrent_group_id}
        json_data = self.api_call('torrentgroup', params)
        logger.info(f'Retrieved torrent group information for group_id {torrent_group_id}')
        return json_data

    def get_file_paths_from_torrent_group(self, torrent_group):
        """Extracts file paths from a torrent group."""
        file_paths = [
            torrent.get("filePath")
            for torrent in torrent_group.get("response", {}).get("torrents", [])
        ]
        unescaped_file_paths = [html.unescape(path) for path in file_paths if path]
        logger.info(f'Extracted file paths: {unescaped_file_paths}')
        return unescaped_file_paths