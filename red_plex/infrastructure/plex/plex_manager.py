"""Module for managing Plex albums and playlists."""

import os
from datetime import datetime, timezone
from typing import List
from typing import Optional

import click
from plexapi.audio import Album as PlexAlbum
from plexapi.base import MediaContainer
from plexapi.collection import Collection as PlexCollection
from plexapi.library import MusicSection
from plexapi.server import PlexServer

from red_plex.domain.models import Collection, Album
from red_plex.infrastructure.config.config import load_config
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.mapper.plex_mapper import PlexMapper
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode


class PlexManager:
    """Handles operations related to Plex."""

    def __init__(self, db: LocalDatabase):
        # Load configuration
        config_data = load_config()

        self.url = config_data.plex_url
        self.token = config_data.plex_token
        self.section_name = config_data.section_name
        self.plex = PlexServer(self.url, self.token, timeout=1200)

        self.library_section: MusicSection
        self.library_section = self.plex.library.section(self.section_name)

        # Initialize the album db
        self.local_database = db
        self.album_data = self.local_database.get_all_albums()

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
        albums: List[PlexAlbum]
        try:
            albums = self.library_section.searchAlbums(filters=plex_filter)
        except Exception as e:  # pylint: disable=W0718
            logger.warning('An error occurred while fetching albums given filter: %s', e)
            return []
        domain_albums: List[Album]
        domain_albums = []
        for album in albums:
            tracks = album.tracks()
            if tracks:
                media_path = tracks[0].media[0].parts[0].file
                album_folder_path = os.path.dirname(media_path)
                domain_albums.append(Album(album.ratingKey, album.addedAt, album_folder_path))
        return domain_albums

    def get_rating_keys(self, path: str, album_fetch_mode: AlbumFetchMode) -> List[str]:
        """Returns the rating keys if the path matches part of an album folder."""
        # Validate the input path
        if not self.validate_path(path):
            logger.warning("The provided path is either empty or too short to be valid.")
            return []

        rating_keys = {}

        if album_fetch_mode in (AlbumFetchMode.EXTERNAL, AlbumFetchMode.MIXED):
            rating_keys.update(self.find_matching_rating_keys_using_beets(path))

        if album_fetch_mode in (AlbumFetchMode.NORMAL, AlbumFetchMode.MIXED):
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

    # pylint: disable=too-many-locals
    def find_matching_rating_keys_using_beets(self, path):
        """Find matching rating keys using beets mappings."""
        matched_rating_keys = {}
        albums_locations = self.local_database.get_all_beets_mappings()

        folder_pairs = set()

        for src, dst in albums_locations.source_destination.items():
            src_folder = os.path.dirname(src)
            dst_folder = os.path.dirname(dst)
            folder_pairs.add((src_folder, dst_folder))
        albums_locations_simplified = dict(folder_pairs)

        album_sources = albums_locations_simplified.keys()
        for source in album_sources:
            normalized_folder_path = os.path.normpath(source)  # Normalize path
            folder_parts = normalized_folder_path.split(os.sep)  # Split path into parts

            # Check if the path matches any part of folder_path
            if path in folder_parts:
                real_path = albums_locations_simplified[source]
                normalized_real_path = os.path.normpath(real_path)  # Normalize path

                # Iterate the whole Plex library
                for album in self.album_data:
                    normalized_album_path = os.path.normpath(album.path)
                    if normalized_real_path.startswith(normalized_album_path):
                        matched_rating_keys[album.id] = album.path
        return matched_rating_keys

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
        """Fetches album objects from Plex using their rating keys."""
        logger.debug('Fetching albums from Plex: %s', albums)
        rating_keys = [int(album.id) for album in albums]
        try:
            fetched_albums = self.plex.fetchItems(rating_keys)
        except Exception as e:  # pylint: disable=W0718
            logger.warning('An error occurred while fetching albums: %s', e)
            return []
        return fetched_albums

    def create_collection(self, name: str, albums: List[Album]) -> Optional[Collection]:
        """Creates a collection in Plex."""
        logger.info('Creating collection with name "%s" and %d albums.', name, len(albums))
        albums_media = self._fetch_albums_by_keys(albums)

        try:
            collection = self.library_section.createCollection(name, items=albums_media)
        except Exception as e:  # pylint: disable=W0718
            logger.warning('An error occurred while creating the collection: %s', e)
            return None
        return PlexMapper.map_plex_collection_to_domain(collection)

    def get_collection_by_name(self, name: str) -> Optional[Collection]:
        """Finds a collection by name."""
        collection: Optional[PlexCollection]
        try:
            collection = self.library_section.collection(name)
        except Exception as e:  # pylint: disable=W0718
            logger.warning('An error occurred while trying to fetch '
                           'the collection from Plex: %s', e)
            collection = None
        if collection:
            return Collection(
                name=collection.title,
                id=str(collection.ratingKey)
            )
        logger.info('No existing collection found with name "%s" in Plex.', name)
        return None

    def add_items_to_collection(self, collection: Collection, albums: List[Album]) -> None:
        """Adds albums to an existing collection."""
        logger.debug('Adding %d albums to collection "%s".', len(albums), collection.name)

        collection_from_plex: Optional[PlexCollection]
        try:
            collection_from_plex = self.library_section.collection(collection.name)
        except Exception as e:  # pylint: disable=W0718
            logger.warning('An error occurred while trying to fetch the collection: %s', e)
            collection_from_plex = None
        if collection_from_plex:
            collection_from_plex.addItems(self._fetch_albums_by_keys(albums))
        else:
            logger.warning('Collection "%s" not found.', collection.name)

    @staticmethod
    def validate_path(path: str) -> bool:
        """Validates that the path is correct."""
        if (not path) or (len(path) == 1):
            return False
        return True
