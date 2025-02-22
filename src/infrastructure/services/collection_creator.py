"""Module for creating Plex collections from Gazelle collages or bookmarks."""

import click
from domain.models import TorrentGroup, Collection, Album
from typing import List
from infrastructure.cache.collage_collection_cache import CollageCollectionCache
from infrastructure.cache.bookmarks_collection_cache import BookmarksCollectionCache
from infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from infrastructure.plex.plex_manager import PlexManager
from infrastructure.logger.logger import logger
from infrastructure.rest.gazelle.config import initialize_gazelle_api

# pylint: disable=R0801
class CollectionCreator:
    """
    Handles the creation and updating of Plex collections
    based on Gazelle collages or bookmarks.
    """

    def __init__(self, plex_manager: PlexManager, gazelle_api: GazelleAPI = None, cache_file=None):
        self.plex_manager = plex_manager
        self.gazelle_api = gazelle_api
        self.collage_collection_cache = CollageCollectionCache(cache_file)
        self.bookmarks_collection_cache = BookmarksCollectionCache(cache_file)

    def create_collections_from_collages(self, site: str, collage_ids: List[str], fetch_bookmarks = False):
        if self.gazelle_api is None:
            return

        for collage_id in collage_ids:
            self._create_or_update_collection_from_collage(
                collage_id, site=site, fetch_bookmarks=fetch_bookmarks)

    def update_collections_from_collages(self, collages: List[Collection], fetch_bookmarks = False):
        for collage in collages:
            self.gazelle_api = initialize_gazelle_api(collage.site)
            self._create_or_update_collection_from_collage(
                collage.id, site=collage.site, fetch_bookmarks=fetch_bookmarks, force_update=True)

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def _create_or_update_collection_from_collage(self, collage_id: str = "", site: str = None, fetch_bookmarks = False, force_update = False):
        """Creates or updates a Plex collection based on a Gazelle collage."""
        collage_data: Collection

        if fetch_bookmarks:
            collage_data = self.gazelle_api.get_bookmarks(site)
        else:
            collage_data = self.gazelle_api.get_collage(collage_id)
        
        existing_collection = None
        if collage_data:
            existing_collection = self.plex_manager.get_collection_by_name(collage_data.name)

        if existing_collection:
            if fetch_bookmarks:
                cached_collage_collection = self.bookmarks_collection_cache.get_bookmark(existing_collection.id)
            else:
                cached_collage_collection = self.collage_collection_cache.get_collection(existing_collection.id)
            if cached_collage_collection:
                cached_group_ids = set([torrent_group.id
                                        for torrent_group
                                        in cached_collage_collection.torrent_groups])
            else:
                cached_group_ids = set()

            if not force_update:
                # Ask for confirmation if not forced
                response = click.confirm(
                    f'Collection "{collage_data.name}" already exists. '
                    'Do you want to update it with new items?',
                    default=True
                )
                if not response:
                    click.echo('Skipping collection update.')
                    return
        else:
            existing_collection = None
            cached_group_ids = set()
        group_ids = [torrent_group.id for torrent_group in collage_data.torrent_groups]
        new_group_ids = set(map(int, group_ids)) - cached_group_ids

        matched_rating_keys = set()
        processed_group_ids = set()
        torrent_group: TorrentGroup

        for gid in new_group_ids:
            torrent_group = self.gazelle_api.get_torrent_group(gid)

            if torrent_group:
                group_matched = False
                for path in torrent_group.file_paths:
                    rating_keys = self.plex_manager.get_rating_keys(path) or []
                    if rating_keys:
                        group_matched = True
                        matched_rating_keys.update(int(key) for key in rating_keys)
                if group_matched:
                    processed_group_ids.add(gid)

        if matched_rating_keys:
            albums = [Album(rating_key) for rating_key in list(matched_rating_keys)]
            if existing_collection:
                # Update existing collection
                self.plex_manager.add_items_to_collection(existing_collection, albums)
                
                # Update cache
                updated_group_ids = cached_group_ids.union(processed_group_ids)
                if fetch_bookmarks:
                    self.bookmarks_collection_cache.save_bookmarks(
                        existing_collection.id, site, list(
                            updated_group_ids)
                    )
                else:
                    self.collage_collection_cache.save_collection(
                        existing_collection.id, collage_data.name, site, collage_id, list(
                            updated_group_ids)
                    )
            else:
                # Create new collection
                collection = self.plex_manager.create_collection(collage_data.name, albums)
                
                # Save to cache
                if fetch_bookmarks:
                    self.bookmarks_collection_cache.save_bookmarks(
                        collection.id, site, list(processed_group_ids)
                    )
                else:
                    self.collage_collection_cache.save_collection(
                        collection.id, collage_data.name, site, collage_id, list(processed_group_ids)
                )
