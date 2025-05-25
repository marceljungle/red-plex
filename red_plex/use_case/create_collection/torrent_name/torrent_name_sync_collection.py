"""Module for creating Plex collections using torrent names/paths."""

from typing import List, Optional, Set, Tuple

from red_plex.domain.models import Collection, Album, TorrentGroup
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.create_collection.response.create_collection_response import (
    CreateCollectionResponse)


# pylint: disable=too-few-public-methods, too-many-arguments
# pylint: disable=R0917
class TorrentNameCollectionCreatorUseCase:
    """
    Handles creating/updating Plex collections by matching
    torrent file paths from Gazelle with Plex library paths.
    """

    def __init__(self, db: LocalDatabase, plex_manager: PlexManager, gazelle_api: GazelleAPI):
        self.plex_manager = plex_manager
        self.gazelle_api = gazelle_api
        self.db = db

    def execute(
            self,
            collage_id: str = "",
            site: str = None,
            fetch_bookmarks=False,
            force_update=False
    ) -> CreateCollectionResponse:
        """
        Orchestrates the process of creating or updating a Plex collection
        using the torrent name/path strategy.
        """
        # 1. Fetch data from the source (Gazelle)
        source_collection = self._fetch_source_data(collage_id, site, fetch_bookmarks)
        if not source_collection:
            return CreateCollectionResponse(response_status=None,
                                            collection_data=None)

        # 2. Handle existing collection in Plex and DB
        plex_collection = self.plex_manager.get_collection_by_name(source_collection.name)
        db_group_ids = set()

        if plex_collection:
            if not force_update:
                # Collection exists, and update is not forced; confirmation is needed.
                return CreateCollectionResponse(response_status=False,
                                                collection_data=source_collection)
            db_group_ids = self._get_stored_group_ids(plex_collection.id, fetch_bookmarks)

        # 3. Identify and find new albums in Plex using paths
        source_group_ids = {int(tg.id) for tg in source_collection.torrent_groups}
        new_group_ids = source_group_ids - db_group_ids

        matched_rating_keys, processed_group_ids = self._find_new_plex_albums_by_path(new_group_ids)

        # 4. Create or update if albums were found
        if not matched_rating_keys:
            # No new albums found or nothing to do.
            return CreateCollectionResponse(response_status=True,
                                            collection_data=source_collection,
                                            albums=[])

        albums_to_add = [Album(id=rk) for rk in matched_rating_keys]

        if plex_collection:
            self._update_existing_collection(
                plex_collection, albums_to_add, processed_group_ids, db_group_ids,
                site, fetch_bookmarks, source_collection.external_id
            )
        else:
            self._create_new_collection(
                source_collection, albums_to_add, processed_group_ids,
                site, fetch_bookmarks
            )

        # 5. Success
        return CreateCollectionResponse(
            response_status=True, collection_data=source_collection, albums=albums_to_add
        )

    def _fetch_source_data(self, collage_id: str,
                           site: str,
                           fetch_bookmarks: bool) -> Optional[Collection]:
        """Fetches collection data from Gazelle (collage or bookmarks)."""
        if fetch_bookmarks:
            return self.gazelle_api.get_bookmarks(site)
        return self.gazelle_api.get_collage(collage_id)

    def _get_stored_group_ids(self, collection_id: str, fetch_bookmarks: bool) -> Set[int]:
        """Retrieves stored torrent group IDs from the local database."""
        if fetch_bookmarks:
            stored_collection = self.db.get_bookmark_collection(collection_id)
        else:
            stored_collection = self.db.get_collage_collection(collection_id)

        return {int(tg.id)
                for tg
                in stored_collection.torrent_groups} if stored_collection else set()

    def _find_new_plex_albums_by_path(self, new_group_ids: Set[int]) -> Tuple[Set[str], Set[int]]:
        """
        Finds matching albums in Plex for new group IDs by checking file paths.
        Fetches full torrent group data as needed.
        Returns a tuple of (matched_rating_keys, processed_group_ids).
        """
        matched_rating_keys = set()
        processed_group_ids = set()

        for group_id in new_group_ids:
            # Fetch full group details (this makes an API call per group)
            torrent_group = self.gazelle_api.get_torrent_group(str(group_id))
            if not torrent_group:
                continue

            group_matched_in_plex = False
            for path in torrent_group.file_paths:
                # Search Plex using the file path
                rating_keys = self.plex_manager.get_rating_keys(path)
                if rating_keys:
                    matched_rating_keys.update(rating_keys)
                    group_matched_in_plex = True

            if group_matched_in_plex:
                processed_group_ids.add(group_id)

        return matched_rating_keys, processed_group_ids

    def _update_existing_collection(
            self,
            plex_collection,  # Assuming this is a Plex Collection object
            albums_to_add: List[Album],
            newly_processed_ids: Set[int],
            existing_db_ids: Set[int],
            site: str,
            fetch_bookmarks: bool,
            external_id: str
    ):
        """Updates an existing Plex collection and the local database."""
        self.plex_manager.add_items_to_collection(plex_collection, albums_to_add)

        updated_group_ids = existing_db_ids.union(newly_processed_ids)
        # Create TorrentGroup objects with only ID, as per original logic
        torrent_groups = [TorrentGroup(id=gid) for gid in updated_group_ids]

        collection_to_save = Collection(
            id=plex_collection.id,
            site=site,
            torrent_groups=torrent_groups,
            name=plex_collection.name,
            external_id=external_id
        )
        self._save_to_db(collection_to_save, fetch_bookmarks)

    def _create_new_collection(
            self,
            source_collection: Collection,
            albums_to_add: List[Album],
            processed_group_ids: Set[int],
            site: str,
            fetch_bookmarks: bool
    ):
        """Creates a new Plex collection and saves it to the local database."""
        new_plex_collection = self.plex_manager.create_collection(
            source_collection.name, albums_to_add
        )
        # Create TorrentGroup objects with only ID, as per original logic
        torrent_groups = [TorrentGroup(id=gid) for gid in processed_group_ids]

        collection_to_save = Collection(
            id=new_plex_collection.id,
            site=site,
            torrent_groups=torrent_groups,
            name=new_plex_collection.name,
            external_id=source_collection.external_id
        )
        self._save_to_db(collection_to_save, fetch_bookmarks)

    def _save_to_db(self, collection: Collection, fetch_bookmarks: bool):
        """Saves or updates the collection data in the local database."""
        if fetch_bookmarks:
            self.db.insert_or_update_bookmark_collection(collection)
        else:
            self.db.insert_or_update_collage_collection(collection)
