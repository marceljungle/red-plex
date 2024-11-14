"""Module for interacting with Gazelle-based APIs."""

import html
import time
import requests
from pyrate_limiter import Limiter, Rate, Duration
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed
from plex_playlist_creator.logger import logger

class GazelleAPI:
    """Handles API interactions with Gazelle-based services."""

    def __init__(self, base_url, api_key, rate_limit=None):
        self.base_url = base_url.rstrip('/') + '/ajax.php?action='
        self.headers = {'Authorization': api_key}

        # Initialize the rate limiter: default to 10 calls per 10 seconds if not specified
        rate_limit = rate_limit or Rate(10, Duration.SECOND * 10)
        # Set raise_when_fail=False to handle delays instead of raising exceptions
        # Set max_delay=None to allow unlimited delay
        self.limiter = Limiter(rate_limit, raise_when_fail=False, max_delay=float('inf'))

    @retry(
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_fixed(2)
    )
    def api_call(self, action, params):
        """Makes a rate-limited API call to the Gazelle-based service with retries."""
        formatted_params = '&' + '&'.join(f'{key}={value}' for key, value in params.items())
        formatted_url = f'{self.base_url}{action}{formatted_params}'
        logger.info('Calling API: %s', formatted_url)

        # Use the limiter to enforce rate limiting
        while True:
            # Try to acquire permission to make the API call
            did_acquire = self.limiter.try_acquire('api_call')
            if did_acquire:
                # Permission acquired; make the API call
                response = requests.get(formatted_url, headers=self.headers, timeout=10)
                response.raise_for_status()
                return response.json()
            # Rate limit exceeded; limiter will handle delay automatically
            delay = self.limiter.bucket_factory.last_delay
            logger.warning('Rate limit exceeded. Sleeping for %.2f seconds.', delay / 1000)
            time.sleep(delay / 1000)

    def get_collage(self, collage_id):
        """Retrieves collage data."""
        params = {'id': str(collage_id), 'showonlygroups': 'true'}
        json_data = self.api_call('collage', params)
        logger.info('Retrieved collage data for collage_id %s', collage_id)
        return json_data

    def get_torrent_group(self, torrent_group_id):
        """Retrieves torrent group data."""
        params = {'id': torrent_group_id}
        json_data = self.api_call('torrentgroup', params)
        logger.info('Retrieved torrent group information for group_id %s', torrent_group_id)
        return json_data

    def get_file_paths_from_torrent_group(self, torrent_group):
        """Extracts file paths from a torrent group."""
        logger.debug(
            "Extracting file paths from torrent group response: %s",
            torrent_group
        )
        file_paths = [
            torrent.get("filePath")
            for torrent in torrent_group.get("response", {}).get("torrents", [])
        ]
        normalized_file_paths = [self.normalize(path) for path in file_paths if path]
        logger.info('Extracted file paths: %s', normalized_file_paths)
        return normalized_file_paths

    def normalize(self, text):
        """Unescape text and remove direction control unicode characters."""
        unescaped_text = html.unescape(text)
        removed_direction_control = unescaped_text.replace("\u200e", "")
        return removed_direction_control
