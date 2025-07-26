"""Module for interacting with Gazelle-based APIs."""

import asyncio
import re
import time
import unicodedata
from inspect import isawaitable
from typing import Dict, Any, Optional, List

import requests
from pyrate_limiter import Limiter, Rate, Duration
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed
from thefuzz import process, fuzz

from red_plex.domain.models import Collection, TorrentGroup
from red_plex.infrastructure.config.config import load_config
from red_plex.infrastructure.constants.constants import ALBUM_TAGS, VARIOUS_ARTISTS_TAGS
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.rest.gazelle.mapper.gazelle_mapper import GazelleMapper


# pylint: disable=W0718,R0914,R0913,R0917,R0912
class GazelleAPI:
    """Handles API interactions with Gazelle-based services."""

    def __init__(self, site: str):
        self.site = site
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

    def _wait_for_rate_limit(self):
        """Handle rate limiting by waiting if necessary."""
        while True:
            did_acquire = self.limiter.try_acquire('api_call')
            if did_acquire:
                return
            delay_ms = self.get_retry_after()
            delay_seconds = delay_ms / 1000.0
            if delay_seconds > 0.001:
                logger.debug('Rate limit exceeded. Sleeping for %.2f seconds.', delay_seconds)
                time.sleep(delay_seconds)
            else:
                time.sleep(0.001)

    @retry(
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        stop=stop_after_attempt(5),
        wait=wait_fixed(4),
        reraise=True
    )
    def get_call(self, action: str, params: Dict[str, str]) -> Dict[str, Any]:
        """
        Makes a rate-limited GET API call to the Gazelle-based service with retries.
        Rate limit is handled in a loop, while network/HTTP errors trigger a retry.
        """
        formatted_params = '&' + '&'.join(f'{k}={v}' for k, v in params.items()) if params else ''
        formatted_url = f'{self.base_url}{action}{formatted_params}'
        logger.debug('Calling GET API: %s', formatted_url)

        self._wait_for_rate_limit()
        response = requests.get(formatted_url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.json()

    @retry(
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        stop=stop_after_attempt(5),
        wait=wait_fixed(4),
        reraise=True
    )
    def post_call(self, action: str,
                  params: Dict[str, str] = None,
                  data: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Makes a rate-limited POST API call to the Gazelle-based service with retries.
        Rate limit is handled in a loop, while network/HTTP errors trigger a retry.
        """
        url = f'{self.base_url}{action}'
        logger.debug('Calling POST API: %s', url)

        self._wait_for_rate_limit()
        response = requests.post(url, headers=self.headers, params=params, data=data, timeout=10)
        response.raise_for_status()
        return response.json()

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
            json_data = self.get_call('collage', params)
        except Exception as e:  # pylint: disable=W0703
            logger.error('Error retrieving collage data for collage_id %s: %s', collage_id, e)
            return None
        logger.debug('Retrieved collage data for collage_id %s', collage_id)
        return GazelleMapper.map_collage(json_data)

    def get_torrent_group(self, torrent_group_id: str) -> Optional[TorrentGroup]:
        """Retrieves torrent group data."""
        params = {'id': str(torrent_group_id)}
        try:
            json_data = self.get_call('torrentgroup', params)
        except Exception as e:  # pylint: disable=W0703
            logger.error('Error retrieving torrent group data '
                         'for group_id %s: %s', torrent_group_id, e)
            return None
        logger.debug('Retrieved torrent group information for group_id %s', torrent_group_id)
        torrent_group_data = json_data.get('response', {}).get('group', {})
        torrents = json_data.get('response', {}).get('torrents', [])
        return GazelleMapper.map_torrent_group(torrent_group_data, torrents)

    def get_bookmarks(self, site: str) -> Optional[Collection]:
        """Retrieves user bookmarks."""
        logger.debug('Retrieving user bookmarks...')
        try:
            bookmarks_response = self.get_call('bookmarks', {})
        except Exception as e:  # pylint: disable=W0703
            logger.error('Error retrieving user bookmarks: %s', e)
            return None
        logger.debug('Retrieved user bookmarks')
        return GazelleMapper.map_bookmarks(bookmarks_response, site)

    def _fetch_groups_from_api(self, album_name: str, artists: List[str]) -> List[TorrentGroup]:
        """
        Helper method to fetch torrent groups from the API for a given album and artists.
        """
        found_groups = []
        params = {}
        for artist in artists:
            # If the artist name is 'various artists', we skip it
            if artist.lower() in VARIOUS_ARTISTS_TAGS:
                params = {'groupname': album_name}
            else:
                params = {'groupname': album_name, 'artistname': artist}
            try:
                response = self.get_call('browse', params)
                results = response.get('response', {}).get('results', [])
                if results:
                    domain_tgs = [GazelleMapper.map_torrent_group(tg) for tg in results]
                    found_groups.extend(domain_tgs)
            except Exception as e:
                logger.error('Error during API call for [%s]-[%s]: %s', album_name, artist, e)
                # We continue here instead of returning None to be more resilient
        return found_groups

    def _get_fallback_album_name(self, album_name: str) -> str:
        """
        Cleans an album name by removing tags and parenthesized content for a fallback search.
        """
        # 1: Remove content in parentheses
        clean_name = re.sub(r'\s*\([^)]*\)', '', album_name)

        # 2: Remove dots and commas from the result
        clean_name = re.sub(r'[.,]', '', clean_name).strip()

        # 3. Remove common tags like EP, Single, etc.
        # This regex looks for whole words at the end of the string
        tag_pattern = r'\s+\b(?:' + '|'.join(re.escape(tag) for tag in ALBUM_TAGS) + r')\b$'
        clean_name = re.sub(tag_pattern, '', clean_name, flags=re.IGNORECASE).strip()

        return clean_name

    def browse_by_album_and_artist_names(self,
                                         album_name: str,
                                         artists: List[str]) -> Optional[List[TorrentGroup]]:
        """
        Searches for torrents by finding the best fuzzy match from all possible results,
        including an initial, a fallback, and an album-only search.
        """
        logger.debug('Initiating search for album [%s] and artists [%s]', album_name, artists)

        # --- PHASE 1: Comprehensive Data Fetching ---

        # 1. Initial search with the original album name and artists
        initial_groups = self._fetch_groups_from_api(album_name, artists)

        # 2. Fallback search with the cleaned album name and artists
        fallback_album_name = self._get_fallback_album_name(album_name)
        fallback_groups = []
        if fallback_album_name.lower() != album_name.lower():
            logger.debug("Performing fallback search with cleaned name: [%s]", fallback_album_name)
            fallback_groups = self._fetch_groups_from_api(fallback_album_name, artists)

        # 3. Combine initial and fallback results, removing duplicates
        combined_groups = {group.id: group for group in initial_groups}
        for group in fallback_groups:
            combined_groups[group.id] = group

        all_possible_groups = list(combined_groups.values())

        # --- PHASE 1.5: Final Fallback Search (Album Name Only) ---
        # If we still haven't found anything, try one last time searching only by album name.
        if not all_possible_groups:
            logger.info("No results found. Trying a final search with album name only.")
            try:
                params = {'groupname': album_name}
                response = self.get_call('browse', params)
                results = response.get('response', {}).get('results', [])
                if results:
                    all_possible_groups = [GazelleMapper.map_torrent_group(tg) for tg in results]
            except Exception as e:
                logger.error('Error during album-only fallback search for [%s]: %s', album_name, e)
                return None  # Fail on API error

        # If after all attempts there are still no results, exit.
        if not all_possible_groups:
            logger.debug("No potential matches found after all searches.")
            return []

        # --- PHASE 2: Single Fuzzy Matching Stage on All Collected Results ---

        choices: Dict[str, TorrentGroup] = {}
        for group in all_possible_groups:
            artist_str = ', '.join(group.artists) if group.artists else ''
            choice_string = (f"{self._normalize_string(artist_str)} - "
                             f"{self._normalize_string(group.album_name)}")
            choices[choice_string] = group

        overall_best_match = None
        highest_score = 0

        if len(artists) > 1:
            artist_candidates = artists + ['Various Artists']
        else:
            artist_candidates = artists

        for artist_variation in artist_candidates:
            query_string = (f"{self._normalize_string(artist_variation)} - "
                            f"{self._normalize_string(album_name)}")
            current_match = process.extractOne(query_string,
                                               choices.keys(),
                                               scorer=fuzz.token_set_ratio)
            if current_match:
                _, current_score = current_match
                if current_score > highest_score:
                    highest_score = current_score
                    overall_best_match = current_match

        if not overall_best_match:
            logger.info("Fuzzy matching could not determine a best match from all results.")
            return all_possible_groups

        best_choice_str, score = overall_best_match
        confidence_threshold = 90
        logger.info("Highest fuzzy match score found: '%s' with %d%%", best_choice_str, score)

        if score >= confidence_threshold:
            logger.info("Confidence score is high. Returning the best match.")
            best_group = choices[best_choice_str]
            return [best_group]

        logger.info("Best match score is below threshold. Returning all potential results.")
        return all_possible_groups

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Retrieves current user information including user ID."""
        try:
            response = self.get_call('index', {})
            if response.get('status') == 'success':
                return response.get('response', {})
            logger.error('Failed to get user info: %s', response)
            return None
        except Exception as e:
            logger.error('Error retrieving user info: %s', e)
            return None

    def get_user_collages(self, user_id: str) -> Optional[List[Collection]]:
        """Retrieves collages created by the specified user."""
        params = {'userid': str(user_id)}
        try:
            response = self.get_call('collages', params)
            if response.get('status') == 'success':
                collages_data = response.get('response', [])
                # Map to Collection domain objects
                collections = []
                for collage_dict in collages_data:
                    collection = Collection(
                        id="",  # No local ID yet
                        external_id=str(collage_dict.get('id', '')),
                        name=collage_dict.get('name', ''),
                        torrent_groups=[],
                        site=self.site.lower()
                    )
                    collections.append(collection)
                return collections
            logger.error('Failed to get user collages: %s', response)
            return None
        except Exception as e:
            logger.error('Error retrieving user collages for user_id %s: %s', user_id, e)
            return None

    def add_to_collage(self, collage_id: str,
                       group_ids: List[str]) -> Optional[Dict[str, Any]]:
        """
        Adds group IDs to a collage.
        
        Args:
            collage_id: The ID of the collage to add to
            group_ids: List of group IDs to add
            
        Returns:
            Response dict containing status and results, or None on error
        """
        if not group_ids:
            logger.warning('No group IDs provided to add to collage %s', collage_id)
            return None

        # Format group IDs as comma-separated string
        group_ids_str = ','.join(group_ids)

        params = {'collageid': str(collage_id)}
        data = {'groupids': group_ids_str}

        logger.debug('Adding groups %s to collage %s', group_ids_str, collage_id)

        try:
            result = self.post_call('addtocollage', params, data)

            if result.get('status') == 'success':
                logger.info('Successfully added groups to collage '
                            '%s: added=%s, rejected=%s, duplicated=%s',
                            collage_id,
                            result.get('response', {}).get('groupsadded', []),
                            result.get('response', {}).get('groupsrejected', []),
                            result.get('response', {}).get('groupsduplicated', []))
            return result

        except Exception as e:
            logger.error('Error adding groups %s to collage %s: %s', group_ids_str, collage_id, e)
            return None

    @staticmethod
    def _normalize_string(text: str) -> str:
        """
        Normalizes a string to a simple, comparable form.
        """
        if not text:
            return ""

        # Step 1: Replace dashes
        text = text.replace('–', '-').replace('—', '-')

        # Step 2: Normalize unicode characters (accents, etc.)
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')

        # Step 3: Normalize whitespace
        # Replaces multiple spaces with a single space and strips ends
        text = re.sub(r'\s+', ' ', text).strip()

        # Step 4: Convert to lowercase
        return text.lower()
