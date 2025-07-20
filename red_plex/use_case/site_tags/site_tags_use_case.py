"""Use case for managing site tag mappings and collections."""

import re
from typing import List, Optional, Callable

import click

from red_plex.domain.models import Album, TorrentGroup
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI

# pylint: disable=R0912,W0718,W0613,R0913,R0917
class SiteTagsUseCase:
    """Use case for managing site tag mappings and creating collections from tags."""

    def __init__(self, local_database: LocalDatabase,
                 plex_manager: PlexManager,
                 gazelle_api: GazelleAPI = None):
        self.local_database = local_database
        self.plex_manager = plex_manager
        self.gazelle_api = gazelle_api

    def scan_albums_for_site_tags(self, echo_func: Callable[[str], None],
                                  confirm_func: Callable[[str], bool],
                                  always_skip: bool = False):
        """
        Scan albums and create site tag mappings by searching filenames on the site.
        """
        site = self.gazelle_api.site
        echo_func(f"Starting scan for site: {site}")

        # Get unscanned albums for this site
        unscanned_rating_keys = self.local_database.get_unscanned_albums()

        if not unscanned_rating_keys:
            echo_func("No unscanned albums found.")
            return

        echo_func(f"Found {len(unscanned_rating_keys)} unscanned albums.")

        processed_count = 0
        success_count = 0

        for rating_key in unscanned_rating_keys:
            try:
                processed_count += 1
                echo_func(f"Processing album {processed_count}/"
                          f"{len(unscanned_rating_keys)}: {rating_key}")

                # Fetch album from Plex
                domain_album = self.plex_manager.get_album_by_rating_key(int(rating_key))

                match_data = self._search_by_album_and_artist_names(album_name=domain_album.name,
                                                                    artists=domain_album.artists)

                if match_data:
                    # Process the match
                    if self._process_search_results(rating_key=rating_key,
                                                    torrent_groups=match_data,
                                                    domain_album=domain_album,
                                                    echo_func=echo_func,
                                                    confirm_func=confirm_func,
                                                    always_skip=always_skip):
                        success_count += 1

            except Exception as e:
                logger.exception("Error processing album %s: %s", rating_key, e)
                echo_func(f"  Error processing album {rating_key}: {e}")

        echo_func(f"Scan completed. Processed: {processed_count}, Successful: {success_count}")

    def _search_by_album_and_artist_names(self,
                                          album_name: str,
                                          artists: List[str]) -> Optional[List[TorrentGroup]]:
        """Search torrent groups matching the album and artist names."""
        try:
            if (album_name is None or album_name == '') or (artists is None or artists == []):
                return None
            artists = self._parse_plex_artists(artists[0])
            response = self.gazelle_api.browse_by_album_and_artist_names(album_name, artists)
            return response
        except Exception:
            return None

    def _process_search_results(self, rating_key: str, torrent_groups: List[TorrentGroup],
                                domain_album: Album,
                                echo_func: Callable[[str], None],
                                confirm_func: Callable[[str], bool],
                                always_skip: bool = False) -> bool:
        """Process search results and handle user confirmation for multiple matches."""
        if not torrent_groups:
            return False

        if len(torrent_groups) == 1:
            # Single match, process it
            torrent_group = torrent_groups[0]
            return self._create_site_tag_mapping(rating_key, torrent_group, echo_func)

        if always_skip:
            echo_func(f"  Skipping due to multiple matches ({len(torrent_groups)}) "
                      f"for album [{domain_album.name}] and --always-skip flag.")
            return False

        # Multiple matches, ask user to choose
        echo_func(
            f"  Found {len(torrent_groups)} matches for album name "
            f"[{domain_album.name}] and artists {domain_album.artists}:")
        for i, torrent_group in enumerate(torrent_groups):
            artists = torrent_group.artists
            if isinstance(artists, list):
                artists = ', '.join(artists)
            group_name = torrent_group.album_name
            echo_func(f"    {i + 1}. {artists} - {group_name}")

        while True:
            try:
                choice = click.prompt(
                    f"  Choose a match (1-{len(torrent_groups)}) or 's' to skip",
                                      type=str).strip().lower()
                if choice == 's':
                    return False
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(torrent_groups):
                    return self._create_site_tag_mapping(rating_key,
                                                         torrent_groups[choice_idx],
                                                         echo_func)
                echo_func("  Invalid choice. Please try again.")
            except (ValueError, click.Abort):
                echo_func("  Invalid input. Please try again.")
            except KeyboardInterrupt:
                echo_func("  Scan interrupted by user.")
                return False

    def _create_site_tag_mapping(self, rating_key: str, torrent_group: TorrentGroup,
                                 echo_func: Callable[[str], None]) -> bool:
        """Create a site tag mapping from the search result."""
        try:
            site = self.gazelle_api.site

            # Insert the mapping
            self.local_database.insert_site_tag_mapping(rating_key,
                                                        torrent_group.id,
                                                        site,
                                                        torrent_group.tags)

            artists = torrent_group.artists
            if isinstance(artists, list):
                artists = ', '.join(artists)
            group_name = torrent_group.album_name
            echo_func(f"  ✓ Mapped: {artists} - {group_name} "
                      f"(Group ID: {torrent_group.id}, "
                      f"Tags: {', '.join(torrent_group.tags)})")

            return True

        except Exception as e:
            logger.exception("Error creating site tag mapping for rating_key %s: %s", rating_key, e)
            echo_func(f"  Error creating mapping: {e}")
            return False

    def create_collection_from_tags(self, tags: List[str], collection_name: str,
                                    echo_func: Callable[[str], None]) -> bool:
        """Create a Plex collection from albums matching the specified tags."""
        echo_func(f"Creating collection '{collection_name}' with tags: {', '.join(tags)}")

        # Get rating keys that match all specified tags
        matching_rating_keys = self.local_database.get_rating_keys_by_tags(tags)

        if not matching_rating_keys:
            echo_func("No albums found matching the specified tags.")
            return False

        echo_func(f"Found {len(matching_rating_keys)} matching albums.")

        try:
            # Get or create the collection in Plex
            collections = self.plex_manager.library_section.collections()
            existing_collection = None

            for collection in collections:
                if collection.title == collection_name:
                    existing_collection = collection
                    break

            if existing_collection:
                echo_func(f"Collection {collection_name} already exists.")
                return False

            # Fetch Plex albums
            matching_albums = [Album(id=rating_key) for rating_key in matching_rating_keys]

            # Create the collection
            self.plex_manager.create_collection(collection_name, matching_albums)

            echo_func(f"✓ Collection '{collection_name}' "
                      f"created/updated with {len(matching_rating_keys)} albums.")
            return True

        except Exception as e:
            logger.exception("Error creating collection: %s", e)
            echo_func(f"Error creating collection: {e}")
            return False

    @staticmethod
    def _parse_plex_artists(artist_str: str) -> List[str]:
        """
        Parses an artist string, returning a list of individual artists
        and the original combined string if it contains separators.
        """
        if not artist_str:
            return []

        # Store the original, clean string to add it later
        original_artist = artist_str.strip()

        separators = r'\s*;\s*|\s*x\s*|\s*\+\s*|\s*&\s*|\s*,\s*|\s*/\s*|\s+and\s+'

        # Get the split parts
        split_artists = re.split(separators, original_artist)

        # Use a set to easily combine and remove duplicates
        final_artists = {art for art in split_artists if art}

        # If the name was split into more than one part, add the original as well
        if len(final_artists) > 1:
            final_artists.add(original_artist)

        return list(final_artists)
