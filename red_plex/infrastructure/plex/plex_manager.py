"""Module for managing Plex albums and playlists."""

import os
import re
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
        except Exception as e:  # pylint: disable=W0718
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
        # pylint: disable=broad-except
        # pylint: disable=W0718
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
    def _get_album_transformations(album_name: str) -> List[str]:
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

        tags = [
            "EP", "E.P", "E.P.", "Single", "Album", "Soundtrack", "Anthology",
            "Compilation", "Live Album", "Remix", "Bootleg", "Interview",
            "Mixtape", "Demo", "Concert Recording", "DJ Mix", "Original Mix",
            "Remastered", "Deluxe Edition", "Limited Edition", "Bonus Track",
            "Instrumental", "Acapella"
        ]
        suffixes = sorted(tags, key=len, reverse=True)

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
