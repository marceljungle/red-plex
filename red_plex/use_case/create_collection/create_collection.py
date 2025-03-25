"""Module for creating Plex collections from Gazelle collages or bookmarks."""

from domain.models import Collection, Album, TorrentGroup
from infrastructure.db.local_database import LocalDatabase
from infrastructure.plex.plex_manager import PlexManager
from infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from use_case.create_collection.album_fetch_mode import AlbumFetchMode
from use_case.create_collection.response.create_collection_response import CreateCollectionResponse


# pylint: disable=too-few-public-methods
class CollectionCreator:
    """
    Handles the creation and updating of Plex collections
    based on Gazelle collages or bookmarks.
    """

    def __init__(self, db: LocalDatabase,
                 plex_manager: PlexManager,
                 gazelle_api: GazelleAPI = None):
        self.plex_manager = plex_manager
        self.gazelle_api = gazelle_api
        self.db = db

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements, too-many-arguments
    # pylint: disable=R0917, E1121
    def create_or_update_collection_from_collage(
            self,
            collage_id: str = "",
            site: str = None,
            fetch_bookmarks=False,
            force_update=False,
            album_fetch_mode: AlbumFetchMode = AlbumFetchMode.NORMAL
    ) -> CreateCollectionResponse:
        """
        Creates or updates a Plex collection based on a Gazelle collage.

        Returns:
          - True if it was created/updated successfully.
          - False if the collection already existed and the update was not forced
            (leaves it to the CLI layer to decide what to do).
          - None if there is nothing to do or data could not be retrieved.
        """
        collage_data: Collection

        if fetch_bookmarks:
            collage_data = self.gazelle_api.get_bookmarks(site)
        else:
            collage_data = self.gazelle_api.get_collage(collage_id)

        if not collage_data:
            return CreateCollectionResponse(response_status=None,
                                            collection_data=collage_data)  # Nothing to update

        existing_collection = self.plex_manager.get_collection_by_name(collage_data.name)
        if existing_collection:
            # If it exists, and we are not forcing an update => notify that confirmation is needed
            if not force_update:
                return CreateCollectionResponse(response_status=False, collection_data=collage_data)

            # Is there stored data?
            if fetch_bookmarks:
                stored_collage_collection = (self.db
                                             .get_bookmark_collection(existing_collection.id))
            else:
                stored_collage_collection = (self.db
                                             .get_collage_collection(existing_collection.id))

            if stored_collage_collection:
                stored_group_ids = set(torrent_group.id for torrent_group
                                       in stored_collage_collection.torrent_groups)
            else:
                stored_group_ids = set()
        else:
            existing_collection = None
            stored_group_ids = set()

        # Calculate which groups are new (not in the db)
        group_ids = [torrent_group.id for torrent_group in collage_data.torrent_groups]
        new_group_ids = set(map(int, group_ids)) - stored_group_ids

        matched_rating_keys = set()
        processed_group_ids = set()

        for gid in new_group_ids:
            torrent_group = self.gazelle_api.get_torrent_group(str(gid))
            if torrent_group:
                group_matched = False
                for path in torrent_group.file_paths:
                    rating_keys = self.plex_manager.get_rating_keys(path, album_fetch_mode) or []
                    if rating_keys:
                        group_matched = True
                        matched_rating_keys.update(key for key in rating_keys)
                if group_matched:
                    processed_group_ids.add(gid)
        albums = []
        if matched_rating_keys:
            albums = [Album(id=rating_key) for rating_key in matched_rating_keys]
            if existing_collection:
                # Update existing collection
                self.plex_manager.add_items_to_collection(existing_collection, albums)

                # Update the db with the new groups
                updated_group_ids = stored_group_ids.union(processed_group_ids)
                collection_with_new_groups = Collection(id=existing_collection.id, site=site,
                                                        torrent_groups=[TorrentGroup(
                                                            id=group_id) for group_id in
                                                            updated_group_ids],
                                                        name=existing_collection.name,
                                                        external_id=collage_data.external_id)
                if fetch_bookmarks:
                    self.db.insert_or_update_bookmark_collection(collection_with_new_groups)
                else:
                    self.db.insert_or_update_collage_collection(collection_with_new_groups)
            else:
                # Create the new collection
                collection = self.plex_manager.create_collection(collage_data.name, albums)
                collection_with_new_groups = Collection(id=collection.id, site=site,
                                                        torrent_groups=[TorrentGroup(id=group_id)
                                                                        for group_id in
                                                                        processed_group_ids],
                                                        name=collection.name,
                                                        external_id=collage_data.external_id)
                if fetch_bookmarks:
                    self.db.insert_or_update_bookmark_collection(collection_with_new_groups)
                else:
                    self.db.insert_or_update_collage_collection(collection_with_new_groups)

        # If we reach this point, the creation or update was successful
        return CreateCollectionResponse(response_status=True,
                                        collection_data=collage_data, albums=albums)
