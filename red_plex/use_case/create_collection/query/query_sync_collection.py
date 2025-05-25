"""This module contains the CollectionProcessingService class, which is responsible for
orchestrating the processing of collages or bookmarks into Plex collections."""


from typing import List, Optional, Set, Tuple

from red_plex.domain.models import Collection, Album, TorrentGroup
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.create_collection.response.create_collection_response import (
    CreateCollectionResponse)

# pylint: disable=too-few-public-methods, too-many-arguments, duplicate-code
# pylint: disable=R0917, R0913
class QuerySyncCollectionUseCase:
    """
    Handles the logic to create or update a Plex collection based on
    a Gazelle collage or bookmarks.
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
        Orchestrates the process of creating or updating a Plex collection.
        """
        # 1. Fetch data from the source (Gazelle)
        source_collection = self._fetch_source_data(collage_id, site, fetch_bookmarks)
        if not source_collection:
            return CreateCollectionResponse(response_status=None,
                                            collection_data=None)

        # 2. Handle existing collection in Plex and DB
        plex_collection = self.plex_manager.get_collection_by_name(source_collection.name)
        db_torrents = set()

        if plex_collection:
            if not force_update:
                # The collection exists and update is not forced, confirmation is needed.
                return CreateCollectionResponse(response_status=False,
                                                collection_data=source_collection)
            db_torrents = self._get_stored_torrents(plex_collection.id, fetch_bookmarks)

        # 3. Identify and search for new albums in Plex
        new_torrents = self._filter_new_torrents(source_collection.torrent_groups, db_torrents)
        matched_albums, matched_torrents = self._find_new_plex_albums(new_torrents)

        # 4. Create or update if albums were found
        if not matched_albums:
            # No new albums found or nothing to do.
            return CreateCollectionResponse(response_status=True,
                                            collection_data=source_collection,
                                            albums=[])

        if plex_collection:
            self._update_existing_collection(
                plex_collection, matched_albums, matched_torrents, db_torrents,
                site, fetch_bookmarks, source_collection.external_id
            )
        else:
            self._create_new_collection(
                source_collection, matched_albums, matched_torrents,
                site, fetch_bookmarks
            )

        # 5. Success
        return CreateCollectionResponse(
            response_status=True, collection_data=source_collection, albums=list(matched_albums)
        )

    def _fetch_source_data(self, collage_id: str,
                           site: str,
                           fetch_bookmarks: bool) -> Optional[Collection]:
        """Fetches collection data from Gazelle (collage or bookmarks)."""
        if fetch_bookmarks:
            return self.gazelle_api.get_bookmarks(site)
        return self.gazelle_api.get_collage(collage_id)

    def _get_stored_torrents(self, collection_id: str, fetch_bookmarks: bool) -> Set[TorrentGroup]:
        """Retrieves stored torrent groups from the local database."""
        if fetch_bookmarks:
            stored_collection = self.db.get_bookmark_collection(collection_id)
        else:
            stored_collection = self.db.get_collage_collection(collection_id)

        return set(stored_collection.torrent_groups) if stored_collection else set()

    @staticmethod
    def _filter_new_torrents(
            source_torrents: List[TorrentGroup],
            db_torrents: Set[TorrentGroup]
    ) -> List[TorrentGroup]:
        """Filters out torrent groups that are already stored in the database."""
        db_torrent_ids = {int(t.id) for t in db_torrents}
        return [
            torrent for torrent in source_torrents
            if torrent and int(torrent.id) not in db_torrent_ids
        ]

    def _find_new_plex_albums(
            self,
            new_torrents: List[TorrentGroup]
    ) -> Tuple[Set[Album], Set[TorrentGroup]]:
        """Finds matching albums in Plex for the given new torrent groups."""
        matched_albums = set()
        matched_torrents = set()

        for torrent_group in new_torrents:
            found_albums = self._search_plex_for_album(torrent_group)
            if found_albums:
                matched_albums.update(found_albums)
                matched_torrents.add(torrent_group)

        return matched_albums, matched_torrents

    def _update_existing_collection(
            self,
            plex_collection,  # Assuming this is a Plex Collection object
            matched_albums: Set[Album],
            newly_matched_torrents: Set[TorrentGroup],
            existing_db_torrents: Set[TorrentGroup],
            site: str,
            fetch_bookmarks: bool,
            external_id: str
    ):
        """Updates an existing Plex collection and the local database."""
        self.plex_manager.add_items_to_collection(plex_collection, list(matched_albums))
        updated_torrents = existing_db_torrents.union(newly_matched_torrents)
        collection_to_save = Collection(
            id=plex_collection.id,
            site=site,
            torrent_groups=list(updated_torrents),
            name=plex_collection.name,
            external_id=external_id
        )
        self._save_to_db(collection_to_save, fetch_bookmarks)

    def _create_new_collection(
            self,
            source_collection: Collection,
            matched_albums: Set[Album],
            matched_torrents: Set[TorrentGroup],
            site: str,
            fetch_bookmarks: bool
    ):
        """Creates a new Plex collection and saves it to the local database."""
        new_plex_collection = self.plex_manager.create_collection(
            source_collection.name, list(matched_albums)
        )
        collection_to_save = Collection(
            id=new_plex_collection.id,
            site=site,
            torrent_groups=list(matched_torrents),
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

    def _search_plex_for_album(self, torrent_group: TorrentGroup) -> List[Album]:
        """Searches Plex for the album and returns the rating keys if found."""
        return self.plex_manager.query_for_albums(torrent_group.album_name, torrent_group.artists)
