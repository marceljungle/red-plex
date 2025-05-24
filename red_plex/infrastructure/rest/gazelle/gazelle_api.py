"""Module for interacting with Gazelle-based APIs."""

import asyncio
import time
from inspect import isawaitable
from typing import Dict, Any, Optional

import requests
from pyrate_limiter import Limiter, Rate, Duration
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from red_plex.domain.models import Collection, TorrentGroup
from red_plex.infrastructure.config.config import load_config
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.rest.gazelle.mapper.gazelle_mapper import GazelleMapper


# pylint: disable=W0718
class GazelleAPI:
    """Handles API interactions with Gazelle-based services."""

    def __init__(self, site: str):
        config_data = load_config()
        site_config = config_data.site_configurations.get(site.upper())

        api_key = site_config.api_key
        base_url = site_config.base_url
        rate_limit_config = site_config.rate_limit
        rate_limit = Rate(
            rate_limit_config.calls, Duration.SECOND * rate_limit_config.seconds)

        self.base_url = base_url.rstrip('/') + '/ajax.php?action='
        self.headers = {'Authorization': api_key}

        # Initialize the rate limiter: default to 10 calls per 10 seconds if not specified
        rate_limit = rate_limit or Rate(10, Duration.SECOND * 10)
        self.rate_limit = rate_limit  # Store rate_limit for calculations
        self.limiter = Limiter(rate_limit, raise_when_fail=False)

    @retry(
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        stop=stop_after_attempt(5),
        wait=wait_fixed(4),
        reraise=True
    )
    def api_call(self, action: str, params: Dict[str, str]) -> Dict[str, Any]:
        """
        Makes a rate-limited API call to the Gazelle-based service with retries.
        Rate limit is handled in a loop, while network/HTTP errors trigger a retry.
        """
        formatted_params = '&' + '&'.join(f'{k}={v}' for k, v in params.items()) if params else ''
        formatted_url = f'{self.base_url}{action}{formatted_params}'
        logger.debug('Calling API: %s', formatted_url)

        while True:
            did_acquire = self.limiter.try_acquire('api_call')
            if did_acquire:
                response = requests.get(formatted_url, headers=self.headers, timeout=10)
                response.raise_for_status()
                return response.json()
            delay_ms = self.get_retry_after()
            delay_seconds = delay_ms / 1000.0
            if delay_seconds > 0.001:
                logger.debug('Rate limit exceeded. Sleeping for %.2f seconds.', delay_seconds)
                time.sleep(delay_seconds)
            else:
                time.sleep(0.001)

    def get_retry_after(self) -> int:
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

    def get_collage(self, collage_id: str) -> Optional[Collection]:
        """Retrieves collage data as domain object"""
        params = {'id': str(collage_id), 'showonlygroups': 'true'}
        try:
            json_data = self.api_call('collage', params)
        except Exception as e:  # pylint: disable=W0703
            logger.error('Error retrieving collage data for collage_id %s: %s', collage_id, e)
            return None
        logger.debug('Retrieved collage data for collage_id %s', collage_id)
        return GazelleMapper.map_collage(json_data)

    def get_torrent_group(self, torrent_group_id: str) -> Optional[TorrentGroup]:
        """Retrieves torrent group data."""
        params = {'id': str(torrent_group_id)}
        try:
            json_data = self.api_call('torrentgroup', params)
        except Exception as e:  # pylint: disable=W0703
            logger.error('Error retrieving torrent group data '
                         'for group_id %s: %s', torrent_group_id, e)
            return None
        logger.debug('Retrieved torrent group information for group_id %s', torrent_group_id)
        return GazelleMapper.map_torrent_group(json_data)

    def get_bookmarks(self, site: str) -> Optional[Collection]:
        """Retrieves user bookmarks."""
        logger.debug('Retrieving user bookmarks...')
        try:
            bookmarks_response = self.api_call('bookmarks', {})
        except Exception as e:  # pylint: disable=W0703
            logger.error('Error retrieving user bookmarks: %s', e)
            return None
        logger.debug('Retrieved user bookmarks')
        return GazelleMapper.map_bookmarks(bookmarks_response, site)
