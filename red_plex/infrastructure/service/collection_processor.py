"""This module contains the CollectionProcessingService class, which is responsible for
orchestrating the processing of collages or bookmarks into Plex collections."""

import logging
from typing import Callable, List, Optional, Union

from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode
from red_plex.use_case.create_collection.query.query_sync_collection import (
    QuerySyncCollectionUseCase)
from red_plex.use_case.create_collection.response.create_collection_response import (
    CreateCollectionResponse)
from red_plex.use_case.create_collection.torrent_name.torrent_name_sync_collection import (
    TorrentNameCollectionCreatorUseCase)

logger = logging.getLogger(__name__)

UseCaseType = Union[TorrentNameCollectionCreatorUseCase, QuerySyncCollectionUseCase]


# pylint: disable=too-many-arguments, duplicate-code
# pylint: disable=R0913, R0917
class CollectionProcessingService:
    """Orchestrates processing collages or bookmarks into Plex collections."""

    def __init__(self, db: LocalDatabase, plex_manager: PlexManager, gazelle_api: GazelleAPI):
        self.db = db
        self.plex_manager = plex_manager
        self.gazelle_api = gazelle_api

        # Initialize both use cases
        self.use_cases = {
            AlbumFetchMode.TORRENT_NAME: TorrentNameCollectionCreatorUseCase(db,
                                                                             plex_manager,
                                                                             gazelle_api),
            AlbumFetchMode.QUERY: QuerySyncCollectionUseCase(db,
                                                             plex_manager,
                                                             gazelle_api),
        }
        self.site = gazelle_api.site  # Store site for messages

    def _select_use_case(self, album_fetch_mode: AlbumFetchMode) -> Optional[UseCaseType]:
        """Selects the appropriate use case based on the fetch mode."""
        return self.use_cases.get(album_fetch_mode)

    @staticmethod
    def _display_result(result: CreateCollectionResponse,
                        source_desc: str,
                        echo_func: Callable,
                        forced: bool = False):
        """Helper to display results using the echo_func."""
        context = " when forced" if forced else ""

        if result.response_status is True:
            action = "updated" if forced or (result.albums and forced) else "created/updated"
            # Ensure we have collection_data before accessing its name
            name = result.collection_data.name if result.collection_data else "Unknown"
            count = len(result.albums) if result.albums else 0
            echo_func(
                f'Collection "{name}" from {source_desc} '
                f'{action} successfully with {count} entries.'
            )
        elif result.response_status is None:
            echo_func(f'No valid data found or nothing to do for {source_desc}{context}.')
        else:  # Should not happen if initial False is handled
            echo_func(f'Something unexpected happened for {source_desc}{context}.')

    def _process_single_request(
            self,
            use_case: UseCaseType,
            echo_func: Callable,
            confirm_func: Callable,
            source_description: str,
            collage_id: Optional[str] = None,
            fetch_bookmarks: bool = False
    ):
        """
        Handles the core logic for a single request (collage or bookmark),
        including confirmation.
        """
        site_upper = self.site.upper()

        # 1) First try, without forcing
        initial_result = use_case.execute(
            collage_id=collage_id or "",
            site=site_upper,
            fetch_bookmarks=fetch_bookmarks,
            force_update=False
        )

        if initial_result.response_status is False:
            # Collection exists, ask for confirmation
            collection_name = initial_result.collection_data.name
            if confirm_func(
                    f'Collection "{collection_name}" from {source_description} '
                    'already exists. Do you want to update it with new items?'
            ):
                # 2) If user says yes, do the forced call
                forced_result = use_case.execute(
                    collage_id=collage_id or "",
                    site=site_upper,
                    fetch_bookmarks=fetch_bookmarks,
                    force_update=True
                )
                self._display_result(forced_result, source_description, echo_func, forced=True)
            else:
                echo_func(f'Skipping collection update for "{collection_name}".')
        else:
            self._display_result(initial_result, source_description, echo_func)

    def process_collages(
            self,
            collage_ids: List[str],
            album_fetch_mode: AlbumFetchMode,
            echo_func: Callable,
            confirm_func: Callable
    ):
        """Processes a list of collage IDs."""
        use_case = self._select_use_case(album_fetch_mode)
        if not use_case:
            echo_func(f"Error: Unsupported fetch mode '{album_fetch_mode.name}'.")
            return

        echo_func(f"Using '{album_fetch_mode.name}' fetch mode for collages.")
        self.plex_manager.populate_album_table()

        for collage_id in collage_ids:
            logger.info('Processing collage ID "%s"...', collage_id)
            self._process_single_request(
                use_case=use_case,
                echo_func=echo_func,
                confirm_func=confirm_func,
                source_description=f'collage "{collage_id}"',
                collage_id=collage_id,
                fetch_bookmarks=False
            )

    def process_bookmarks(
            self,
            album_fetch_mode: AlbumFetchMode,
            echo_func: Callable,
            confirm_func: Callable
    ):
        """Processes bookmarks for the site."""
        use_case = self._select_use_case(album_fetch_mode)
        if not use_case:
            echo_func(f"Error: Unsupported fetch mode '{album_fetch_mode.name}'.")
            return

        echo_func(f"Using '{album_fetch_mode.name}' fetch mode for bookmarks.")
        self.plex_manager.populate_album_table()

        logger.info('Processing bookmarks for site "%s"...', self.site)
        self._process_single_request(
            use_case=use_case,
            echo_func=echo_func,
            confirm_func=confirm_func,
            source_description=f'bookmarks on site "{self.site.upper()}"',
            collage_id=None,
            fetch_bookmarks=True
        )
