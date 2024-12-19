"""Module for interacting with Gazelle-based APIs."""

import html
import time
import re
import asyncio
from inspect import isawaitable
import requests
from pyrate_limiter import Limiter, Rate, Duration
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed
from src.infrastructure.logger.logger import logger

# pylint: disable=W0718
class GazelleAPI:
    """Handles API interactions with Gazelle-based services."""

    def __init__(self, base_url, api_key, rate_limit=None):
        self.base_url = base_url.rstrip('/') + '/ajax.php?action='
        self.headers = {'Authorization': api_key}

        # Initialize the rate limiter: default to 10 calls per 10 seconds if not specified
        rate_limit = rate_limit or Rate(10, Duration.SECOND * 10)
        self.rate_limit = rate_limit  # Store rate_limit for calculations
        self.limiter = Limiter(rate_limit, raise_when_fail=False)

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

        while True:
            # Try to acquire permission to make the API call
            did_acquire = self.limiter.try_acquire('api_call')
            if did_acquire:
                # Permission acquired; make the API call
                response = requests.get(formatted_url, headers=self.headers, timeout=10)
                response.raise_for_status()
                return response.json()

            # Rate limit exceeded; calculate delay and retry
            delay_ms = self.get_retry_after()
            delay_seconds = delay_ms / 1000.0

            if delay_seconds > 0.001:  # Only sleep if delay is more than 1 millisecond
                logger.warning('Rate limit exceeded. Sleeping for %.2f seconds.', delay_seconds)
                time.sleep(delay_seconds)
            else:
                # Delay is zero or negligible; retry immediately
                # Optionally, you can add a small sleep to prevent tight loop
                time.sleep(0.001)  # Sleep for 1 millisecond to yield CPU

    def get_retry_after(self):
        """Calculates the time to wait until another request can be made."""
        buckets = self.limiter.bucket_factory.get_buckets()
        if not buckets:
            return 0  # No buckets, no need to wait

        bucket = buckets[0]
        now = int(time.time() * 1000)  # Current time in milliseconds

        # Check if the bucket is asynchronous
        count = bucket.count()
        if isawaitable(count):
            count = asyncio.run(count)

        if count > 0:
            # Get the time of the oldest item relevant to the limit
            index = max(0, bucket.rates[0].limit - 1)
            earliest_item = bucket.peek(index)

            if isawaitable(earliest_item):
                earliest_item = asyncio.run(earliest_item)

            if earliest_item:
                earliest_time = earliest_item.timestamp
                wait_time = (earliest_time + bucket.rates[0].interval) - now
                if wait_time < 0:
                    return 0
                return wait_time
            # If unable to get the item, wait for the full interval
            return bucket.rates[0].interval
        # If no items in the bucket, no need to wait
        return 0

    def get_collage(self, collage_id):
        """Retrieves collage data."""
        params = {'id': str(collage_id), 'showonlygroups': 'true'}
        json_data = self.api_call('collage', params)
        logger.info('Retrieved collage data for collage_id %s', collage_id)
        return json_data

    def get_torrent(self, torrent_id):
        """Retrieves full torrent entity."""
        params = {'id': str(torrent_id)}
        json_data = self.api_call('torrent', params)
        logger.info('Retrieved full torrent data for torrent id %s', torrent_id)
        return json_data

    def get_torrent_group(self, torrent_group_id):
        """Retrieves torrent group data."""
        params = {'id': str(torrent_group_id)}
        json_data = self.api_call('torrentgroup', params)
        logger.info('Retrieved torrent group information for group_id %s', torrent_group_id)
        return json_data

    def get_file_paths_from_torrent_group(self, torrent_group):
        """Extracts file paths from a torrent group."""
        logger.debug('Extracting file paths from torrent group response.')
        try:
            torrents = torrent_group.get('response', {}).get('torrents', [])
            file_paths = [torrent.get('filePath') for torrent in torrents if 'filePath' in torrent]
            normalized_file_paths = [self.normalize(path) for path in file_paths if path]
            logger.info('Extracted file paths: %s', normalized_file_paths)
            return normalized_file_paths
        except Exception as e:
            logger.exception('Error extracting file paths from torrent group: %s', e)
            return []

    def get_bookmarks(self):
        """Retrieves user bookmarks."""
        logger.debug('Retrieving user bookmarks...')
        bookmarks_response = self.api_call('bookmarks', {})
        bookmarks = bookmarks_response.get('response', {})
        logger.info('Retrieved user bookmarks')
        return bookmarks

    def get_group_ids_from_bookmarks(self, bookmarks):
        """Extracts file paths from user bookmarks."""
        logger.debug('Extracting file paths from bookmarks response.')
        try:
            # Bookmarks are at the group level
            bookmarked_group_ids = [bookmark.get('id')
                                    for bookmark in bookmarks.get('bookmarks', [])]
            logger.debug('Bookmarked group IDs: %s', bookmarked_group_ids)
            return bookmarked_group_ids
        except Exception as e:
            logger.exception('Error extracting group ids from bookmarks: %s', e)
            return []

    def normalize(self, text):
        """Unescape text and remove direction control unicode characters."""
        unescaped_text = html.unescape(text)
        # Remove control characters
        cleaned_text = re.sub(r'[\u200e\u200f\u202a-\u202e]', '', unescaped_text)
        return cleaned_text
