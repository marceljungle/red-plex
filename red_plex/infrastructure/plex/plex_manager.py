"""Module for managing Plex albums and playlists."""

import os
import re
import time
from datetime import datetime, timezone
from typing import List
from typing import Optional

import click
from plexapi.audio import Album as PlexAlbum
from plexapi.base import MediaContainer
from plexapi.collection import Collection as PlexCollection
from plexapi.library import MusicSection
from plexapi.server import PlexServer
from plexapi.exceptions import PlexApiException
from requests.exceptions import ConnectionError, Timeout, RequestException

from red_plex.domain.models import Collection, Album
from red_plex.infrastructure.config.config import load_config
from red_plex.infrastructure.constants.constants import ALBUM_TAGS
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.mapper.plex_mapper import PlexMapper

# pylint: disable=W0718
class PlexManager:
    """Handles operations related to Plex."""

    def __init__(self, db: LocalDatabase):
        # Load configuration
        config_data = load_config()

        self.url = config_data.plex_url
        self.token = config_data.plex_token
        self.section_name = config_data.section_name
        # Increase timeout to 30 minutes for large operations
        self.plex = PlexServer(self.url, self.token, timeout=2600)

        self.library_section: MusicSection
        self.library_section = self.plex.library.section(self.section_name)

        # Initialize the album db
        self.local_database = db
        self.album_data = self.local_database.get_all_albums()

    def _retry_with_backoff(self, func, max_retries=3, base_delay=1):
        """Retry a function with exponential backoff."""
        for attempt in range(max_retries):
            try:
                return func()
            except (ConnectionError, Timeout, RequestException, PlexApiException) as e:
                if attempt == max_retries - 1:
                    raise e
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay} seconds...")
                time.sleep(delay)

    def _get_album_path_safely(self, album: PlexAlbum) -> Optional[str]:
        """Safely get album path with retry logic."""
        def _get_tracks():
            return album.tracks()

        try:
            tracks = self._retry_with_backoff(_get_tracks)
            if tracks and tracks[0].media and tracks[0].media[0].parts:
                media_path = tracks[0].media[0].parts[0].file
                return os.path.dirname(media_path)
        except Exception as e:
            logger.warning(f"Failed to get path for album {album.title} (ID: {album.ratingKey}): {e}")

        # Fallback: try to construct path from album metadata if available
        try:
            if hasattr(album, 'locations') and album.locations:
                return album.locations[0]
        except Exception:
            pass

        return None

    def populate_album_table(self):
        """Fetches new albums from Plex and updates the db."""
        logger.info('Updating album db...')

        # Determine the latest addedAt date from the existing db
        if self.album_data:
            latest_added_at = max(album.added_at for album in self.album_data)
            logger.info('Latest album added at: %s', latest_added_at)
        else:
            latest_added_at = datetime(1970, 1, 1, tzinfo=timezone.utc)
            logger.info('No existing albums in db. Fetching all albums.')

        # Fetch albums added after the latest date in db
        filters = {"addedAt>>": latest_added_at}
        new_albums = self.get_albums_given_filter(filters)
        logger.info('Found %d new albums added after %s.', len(new_albums), latest_added_at)

        # Update the album_data list with new albums
        self.album_data.extend(new_albums)

        # Save new albums to the db
        self.local_database.insert_albums_bulk(new_albums)

    def get_albums_given_filter(self, plex_filter: dict) -> List[Album]:
        """Returns a list of albums that match the specified filter."""
        def _search_albums():
            return self.library_section.searchAlbums(filters=plex_filter)

        try:
            albums = self._retry_with_backoff(_search_albums)
        except Exception as e:
            logger.error('Failed to fetch albums after retries: %s', e)
            return []

        domain_albums: List[Album] = []
        batch_size = 100  # Process albums in batches
        total_albums = len(albums)

        for i, album in enumerate(albums):
            try:
                # Log progress every 100 albums
                if i % batch_size == 0:
                    logger.info(f'Processing album {i + 1}/{total_albums}: {album.title}')

                album_path = self._get_album_path_safely(album)

                # Create album even if path is None (we'll skip those with None paths later)
                domain_album = Album(
                    id=album.ratingKey,
                    name=album.title,
                    artists=[album.parentTitle] if album.parentTitle else [],
                    added_at=album.addedAt,
                    path=album_path
                )

                domain_albums.append(domain_album)

                # Small delay every 50 albums to be nice to the server
                if i % 50 == 0 and i > 0:
                    time.sleep(0.1)

            except Exception as e:
                logger.warning(f'Error processing album {album.title} (ID: {album.ratingKey}): {e}')
                continue

        logger.info(f'Successfully processed {len(domain_albums)} out of {total_albums} albums')
        return domain_albums

    def get_album_by_rating_key(self, rating_key: int) -> Optional[Album]:
        """ Queries Plex for the album that matches the given rating_key """
        album = self.library_section.fetchItem(rating_key)
        if album:
            return PlexMapper.map_plex_album_to_domain(album)
        return None

    # If multiple matches are found, prompt the user to choose
    def query_for_albums(self, album_name: str, artists: List[str]) -> List[Album]:
        """Queries Plex for the rating keys of albums that match the given name and artists."""
        logger.debug('Querying Plex for album name: %s', album_name)
        logger.debug('Artists: %s', artists)
        album_names = self._get_album_transformations(album_name)
        artist_names = self._get_artist_transformations(artists)
        filters = {"album.title": album_names, "artist.title": artist_names}
        try:
            albums = self.library_section.search(libtype='album', filters=filters)
            if not albums and len(artists) > 1:
                # Try searching with various artists (bad-tagged albums)
                albums = self.library_section.search(libtype='album',
                                                     filters={"album.title": album_names,
                                                              "artist.title": 'Various Artists'})
            domain_albums = [PlexMapper.map_plex_album_to_domain(album) for album in albums]
            # No matches found
            if not domain_albums:
                return []
            logger.debug('Found album(s): %s', domain_albums)
            # Single match found
            if len(domain_albums) == 1:
                return domain_albums
            # Multiple matches found, prompt the user
            print(f"Multiple matches found for album '{album_name}' by {', '.join(artists)}:")
            for i, album in enumerate(domain_albums, 1):
                print(f"{i}. {album.name} by {', '.join(album.artists)}")
            while True:
                choice = click.prompt(
                    "Select the numbers of the matches you want to keep, separated by commas "
                    "(or enter 'A' for all, 'N' for none)",
                    default="A",
                )
                choice_up = choice.strip().upper()
                if choice_up == "A":
                    return domain_albums
                if choice_up == "N":
                    return []
                try:
                    selected_indices = [int(x) for x in choice.split(",")]
                    if all(1 <= idx <= len(domain_albums) for idx in selected_indices):
                        return [domain_albums[idx - 1] for idx in selected_indices]
                except ValueError:
                    pass
                logger.error(
                    "Invalid input. Please enter valid numbers separated by commas or 'A' for all, "
                    "'N' to select none."
                )
        except Exception as e:
            logger.warning('An error occurred while searching for albums: %s', e)
            return []

    def get_rating_keys(self, path: str) -> List[str]:
        """Returns the rating keys if the path matches part of an album folder."""
        # Validate the input path
        if not self.validate_path(path):
            logger.warning("The provided path is either empty or too short to be valid.")
            return []

        rating_keys = {}

        rating_keys.update(self.find_matching_rating_keys(path))

        # No matches found
        if not rating_keys:
            logger.debug("No matches found for path: %s", path)
            return []

        # Single match found
        if len(rating_keys) == 1:
            return list(rating_keys.keys())

        # Multiple matches found, prompt the user
        print(f"Multiple matches found for path: {path}")
        for i, (_, folder_path) in enumerate(rating_keys.items(), 1):
            print(f"{i}. {folder_path}")

        # Ask the user to choose which matches to keep
        while True:
            choice: str
            choice = click.prompt(
                "Select the numbers of the matches you want to keep, separated by commas "
                "(or enter/'A' to select all, 'N' to select none)",
                default="A",
            )

            if choice.strip().upper() == "A":
                return list(rating_keys.keys())  # Return all matches

            if choice.strip().upper() == "N":
                return []  # Return an empty list if the user selects none

            # Validate the user's input
            try:
                selected_indices = [int(x) for x in choice.split(",")]
                if all(1 <= idx <= len(rating_keys) for idx in selected_indices):
                    return [
                        list(rating_keys.keys())[idx - 1] for idx in selected_indices
                    ]  # Return selected matches

            except ValueError:
                pass

            logger.error(
                "Invalid input. Please enter valid "
                "numbers separated by commas or 'A' for all, 'N' to select none.")

    def find_matching_rating_keys(self, path):
        """Find matching rating keys using the album_data."""
        matched_rating_keys = {}
        # Iterate over album_data and find matches
        for album in self.album_data:
            normalized_folder_path = os.path.normpath(album.path)  # Normalize path
            folder_parts = normalized_folder_path.split(os.sep)  # Split path into parts

            # Check if the path matches any part of folder_path
            if path in folder_parts:
                matched_rating_keys[album.id] = normalized_folder_path
        return matched_rating_keys

    def _fetch_albums_by_keys(self, albums: List[Album]) -> List[MediaContainer]:
        """Fetches album objects from Plex in batches using their rating keys."""
        if not albums:
            return []

        logger.debug('Preparing to fetch %d albums from Plex.', len(albums))
        rating_keys = [int(album.id) for album in albums]
        all_fetched_albums = []
        batch_size = 1000

        for i in range(0, len(rating_keys), batch_size):
            batch_keys = rating_keys[i:i + batch_size]
            logger.debug('Fetching batch of %d albums, starting from index %d.', len(batch_keys), i)

            try:
                # The API call and error handling are now in one place
                fetched_batch = self.plex.fetchItems(batch_keys)
                if fetched_batch:
                    all_fetched_albums.extend(fetched_batch)
                else:
                    logger.warning('No albums found for rating keys in this batch.')
            except Exception as e:
                logger.warning('An error occurred while fetching a batch of albums: %s', e)

        logger.debug('Finished fetching. Total albums retrieved: %d.', len(all_fetched_albums))
        return all_fetched_albums

    def create_collection(self, name: str, albums: List[Album]) -> Optional[Collection]:
        """
        Creates a collection in Plex, adding albums in batches to avoid request limits.
        """
        if not albums:
            logger.warning('Cannot create a collection with no albums.')
            return None

        logger.info('Creating collection "%s" with %d total albums.', name, len(albums))
        batch_size = 1000

        # Step 1: Create the collection with the first batch of albums.
        first_batch = albums[:batch_size]
        albums_media = self._fetch_albums_by_keys(first_batch)

        if not albums_media:
            logger.error('Failed to fetch initial batch of albums. Aborting collection creation.')
            return None
        created_collection: Optional[Collection] = None
        try:
            logger.debug('Creating collection with the first %d items.', len(albums_media))
            plex_collection_obj = self.library_section.createCollection(name, items=albums_media)
            created_collection = PlexMapper.map_plex_collection_to_domain(plex_collection_obj)
        except Exception as e:
            logger.error('An error occurred while creating the collection '
                         'with the first batch: %s', e)
            return None

        # Step 2: If there are more albums, add them in subsequent batches.
        if len(albums) > batch_size:
            for i in range(batch_size, len(albums), batch_size):
                remaining_batch = albums[i:i + batch_size]
                logger.debug('Adding batch of %d albums to collection "%s".',
                             len(remaining_batch), name)
                try:
                    self.add_items_to_collection(created_collection,
                                                 remaining_batch)
                except Exception as e:
                    logger.warning(
                        'Failed to add a batch to collection "%s". '
                        'The collection may be incomplete. Error: %s',
                        name, e
                    )

        logger.info('Successfully finished processing collection "%s".', name)
        return created_collection

    def get_collection_by_name(self, name: str) -> Optional[Collection]:
        """Finds a collection by name."""
        collection: Optional[PlexCollection]
        try:
            collection = self.library_section.collection(name)
        # pylint: disable=broad-except

        except Exception:
            # If the collection doesn't exist, collection will be set to None
            collection = None
        if collection:
            return Collection(
                name=collection.title,
                id=str(collection.ratingKey)
            )
        logger.info('No existing collection found with name "%s" in Plex.', name)
        return None

    def get_collection_by_rating_key(self, rating_key: str) -> Optional[PlexCollection]:
        """Finds a Plex collection by rating key."""
        try:
            collection = self.library_section.fetchItem(int(rating_key))
            if collection and hasattr(collection, 'TYPE') and collection.TYPE == 'collection':
                return collection
            logger.warning('Item with rating key "%s" is not a collection or does not exist.', rating_key)
            return None
        except Exception as e:
            logger.error('Error fetching collection with rating key "%s": %s', rating_key, e)
            return None

    def add_items_to_collection(self, collection: Collection, albums: List[Album]) -> None:
        """Adds albums to an existing collection."""
        logger.debug('Adding %d albums to collection "%s".', len(albums), collection.name)

        collection_from_plex: Optional[PlexCollection]
        try:
            collection_from_plex = self.library_section.collection(collection.name)
        except Exception as e:
            logger.warning('An error occurred while trying to fetch the collection: %s', e)
            collection_from_plex = None
        if collection_from_plex:
            collection_from_plex.addItems(self._fetch_albums_by_keys(albums))
        else:
            logger.warning('Collection "%s" not found.', collection.name)

    def _get_album_transformations(self, album_name: str) -> List[str]:
        """
        Returns a list of album name transformations for use in Plex queries,
        increasing the chances of a successful match.

        Includes:
        - Splitting names containing "/" (e.g., "Track A / Track B").
        - Removal of common suffixes (EP, Single, etc.).
        - Removal of content within parentheses (e.g., (Original Mix)).
        """
        album_name = album_name.strip()
        if not album_name:
            return []

        suffixes = sorted(ALBUM_TAGS, key=len, reverse=True)

        transforms = [album_name]
        seen = {album_name.lower()}

        i = 0
        while i < len(transforms):
            name = transforms[i]

            # 1. Split by "/"
            # If the name contains a slash, split it and add each part.
            if '/' in name:
                parts = name.split('/')
                for part in parts:
                    new_name_split = part.strip()
                    # Add the new transformation if it's valid and not seen before
                    if new_name_split and new_name_split.lower() not in seen:
                        transforms.append(new_name_split)
                        seen.add(new_name_split.lower())

            # 2. Remove known suffixes
            for suffix in suffixes:
                # Check if the name ends with the suffix (case-insensitive)
                if name.lower().endswith(f" {suffix.lower()}") or name.lower() == suffix.lower():
                    # If it ends with " suffix", remove it
                    if name.lower().endswith(f" {suffix.lower()}"):
                        new_name = name[:-len(suffix)].strip()
                    # If it's exactly the suffix (unlikely but possible), it becomes empty
                    else:
                        new_name = ""

                    # Add the new transformation if it's valid and not seen before
                    if new_name and new_name.lower() not in seen:
                        transforms.append(new_name)
                        seen.add(new_name.lower())

            # 3. Remove text within parentheses (e.g., " (Original Mix)")
            new_name_paren = re.sub(r'\s*\([^)]*\)', '', name).strip()

            # Add the new transformation if it's different, valid, and not seen before
            if (new_name_paren and new_name_paren.lower() != name.lower()
                    and new_name_paren.lower() not in seen):
                transforms.append(new_name_paren)
                seen.add(new_name_paren.lower())

            i += 1

        return list(dict.fromkeys(transforms))

    @staticmethod
    def _get_artist_transformations(artists: List[str]) -> List[str]:
        """
        Returns a list of artist name transformations for use in Plex queries.
        Includes comma/ampersand splitting, and removal
        of any content within parentheses.
        """
        transformations: List[str] = []
        seen_lower: set = set()

        def add_artist_with_transforms(name_to_add: str):
            """
            Internal helper to add an artist and its transformations
            (including parenthesis removal) if they haven't been seen yet.
            """
            # 1. Clean and check if empty
            name = name_to_add.strip()
            if not name:
                return

            # 2. Add the original name if new
            lower_name = name.lower()
            if lower_name not in seen_lower:
                transformations.append(name)
                seen_lower.add(lower_name)

            # 3. Create and add the parenthesis-removed version
            paren_removed_name = re.sub(r'\s*\([^)]*\)', '', name).strip()

            # Ensure it's different and not empty before adding
            if paren_removed_name and paren_removed_name.lower() != lower_name:
                lower_paren_removed = paren_removed_name.lower()
                if lower_paren_removed not in seen_lower:
                    transformations.append(paren_removed_name)
                    seen_lower.add(lower_paren_removed)

        # Process each artist from the input list
        for artist_name in artists:
            cleaned_name = artist_name.strip()
            # Add the full name (and its parenthesis-removed version)
            add_artist_with_transforms(cleaned_name)

            # Process comma-separated segments
            for segment in cleaned_name.split(','):
                segment = segment.strip()
                # Add the segment (and its parenthesis-removed version)
                add_artist_with_transforms(segment)

                # Process ampersand-separated collaborators within a segment
                for collaborator in segment.split('&'):
                    collaborator = collaborator.strip()
                    # Add the collaborator (and its parenthesis-removed version)
                    add_artist_with_transforms(collaborator)

        return transformations

    @staticmethod
    def validate_path(path: str) -> bool:
        """Validates that the path is correct."""
        if (not path) or (len(path) == 1):
            return False
        return True
