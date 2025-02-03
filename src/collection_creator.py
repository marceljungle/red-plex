"""Module for creating Plex collections from Gazelle collages or bookmarks."""

import html
import logging
import click
import requests
from src.domain.models import TorrentGroup, Collection, Album
from src.infrastructure.cache.collage_collection_cache import CollageCollectionCache
from src.infrastructure.cache.bookmarks_collection_cache import BookmarksCollectionCache
from src.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from src.infrastructure.plex.plex_manager import PlexManager

logger = logging.getLogger(__name__)

# pylint: disable=R0801
class CollectionCreator:
    """
    Handles the creation and updating of Plex collections
    based on Gazelle collages or bookmarks.
    """

    def __init__(self, plex_manager: PlexManager, gazelle_api: GazelleAPI, cache_file=None):
        self.plex_manager = plex_manager
        self.gazelle_api = gazelle_api
        self.collage_collection_cache = CollageCollectionCache(cache_file)
        self.bookmarks_collection_cache = BookmarksCollectionCache(cache_file)

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def create_or_update_collection_from_collage(self, collage_id: str, site: str = None, force_update = False):
        """Creates or updates a Plex collection based on a Gazelle collage."""
        try:
            collage_data: Collection
            collage_data = self.gazelle_api.get_collage(collage_id)
        except requests.exceptions.RequestException as exc:
            logger.exception('Failed to retrieve collage %s: %s', collage_id, exc)
            return
        
        existing_collection = self.plex_manager.get_collection_by_name(collage_data.name)
        if existing_collection:
            cached_collage_collection = self.collage_collection_cache.get_collection(
                existing_collection.id)
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
        if not new_group_ids:
            click.echo(f'No new items to add to collection "{collage_data.name}".')
            return

        matched_rating_keys = set()
        processed_group_ids = set()
        torrent_group: TorrentGroup

        for gid in new_group_ids:
            try:
                torrent_group = self.gazelle_api.get_torrent_group(gid)
            except requests.exceptions.RequestException as exc:
                logger.exception('Failed to retrieve torrent group %s: %s', gid, exc)
                continue

            group_matched = False
            for path in torrent_group.file_paths:
                rating_keys = self.plex_manager.get_rating_keys(path) or []
                if rating_keys:
                    group_matched = True
                    matched_rating_keys.update(int(key) for key in rating_keys)

            if group_matched:
                processed_group_ids.add(gid)
                logger.info('Matched torrent group %s with albums in Plex.', gid)
            else:
                logger.info('No matching albums found for torrent group %s; skipping.', gid)

        if matched_rating_keys:
            albums = [Album(rating_key) for rating_key in list(matched_rating_keys)]
            if existing_collection:
                # Update existing collection
                self.plex_manager.add_items_to_collection(existing_collection, albums)
                logger.info(
                    'Collection "%s" updated with %d new albums.', collage_data.name, len(albums))
                # Update cache
                updated_group_ids = cached_group_ids.union(processed_group_ids)
                self.collage_collection_cache.save_collection(
                    existing_collection.id, collage_data.name, site, collage_id, list(
                        updated_group_ids)
                )
            else:
                # Create new collection
                collection = self.plex_manager.create_collection(collage_data.name, albums)
                logger.info('Collection "%s" created with %d albums.', collage_data.name, len(albums))
                # Save to cache
                self.collage_collection_cache.save_collection(
                    collection.id, collage_data.name, site, collage_id, list(processed_group_ids)
                )
                click.echo(f'Collection "{collage_data.name}" created with {len(albums)} albums.')
        else:
            message = f'No matching albums found for new items in collage "{collage_data.name}".'
            logger.warning(message)
            click.echo(message)

    def create_or_update_collection_from_bookmarks(self, bookmarks, site, force_update=False):
        """Creates a Plex collection based on the user's bookmarks from a Gazelle-based site."""
        bookmarks_collection_name = f"{site.upper()} Bookmarks"
        bookmarks_group_ids = self.gazelle_api.get_group_ids_from_bookmarks(bookmarks)
        existing_collection = self.plex_manager.get_collection_by_name(bookmarks_collection_name)
        if existing_collection:
            collection_rating_key = existing_collection.ratingKey
            cached_collection = self.bookmarks_collection_cache.get_bookmark(collection_rating_key)
            if cached_collection:
                cached_group_ids = set(cached_collection['torrent_group_ids'])
            else:
                cached_group_ids = set()

            if not force_update:
                # Ask for confirmation if not forced
                response = click.confirm(
                    f'Collection "{bookmarks_collection_name}" already exists. '
                    'Do you want to update it with new items?',
                    default=True
                )
                if not response:
                    click.echo('Skipping collection update.')
                    return
        else:
            existing_collection = None
            cached_group_ids = set()

        new_group_ids = set(map(int, bookmarks_group_ids)) - cached_group_ids
        if not new_group_ids:
            click.echo(f'No new items to add to collection "{bookmarks_collection_name}".')
            return

        matched_rating_keys = set()
        processed_group_ids = set()
        torrent_group: TorrentGroup

        for gid in new_group_ids:
            try:
                torrent_group = self.gazelle_api.get_torrent_group(gid)
            except requests.exceptions.RequestException as exc:
                logger.exception('Failed to retrieve torrent group %s: %s', gid, exc)
                continue

            group_matched = False
            for path in torrent_group.file_paths:
                rating_keys = self.plex_manager.get_rating_keys(path) or []
                if rating_keys:
                    group_matched = True
                    matched_rating_keys.update(int(key) for key in rating_keys)

            if group_matched:
                processed_group_ids.add(gid)
                logger.info('Matched torrent group %s with albums in Plex.', gid)
            else:
                logger.info('No matching albums found for torrent group %s; skipping.', gid)

        if matched_rating_keys:
            albums = self.plex_manager.fetch_albums_by_keys(list(matched_rating_keys))
            if existing_collection:
                # Update existing collection
                self.plex_manager.add_items_to_collection(existing_collection, albums)
                logger.info(
                    'Collection "%s" updated with %d new albums.',
                        bookmarks_collection_name, len(albums))
                # Update cache
                updated_group_ids = cached_group_ids.union(processed_group_ids)
                self.bookmarks_collection_cache.save_bookmarks(
                    existing_collection.ratingKey, site, list(
                        updated_group_ids)
                )
                click.echo(
                    f'Collection "{bookmarks_collection_name}"\
                          updated with {len(albums)} new albums.')
            else:
                # Create new collection
                collection = self.plex_manager.create_collection(
                    bookmarks_collection_name, albums)
                logger.info(
                    'Collection "%s" created with %d albums.',
                      bookmarks_collection_name, len(albums))
                # Save to cache
                self.bookmarks_collection_cache.save_bookmarks(
                    collection.ratingKey, site, list(processed_group_ids)
                )
                click.echo(
                    f'Collection "{bookmarks_collection_name}" created with {len(albums)} albums.')
        else:
            message = (
                f'No matching albums found for new items in collage "{bookmarks_collection_name}".')
            logger.warning(message)
            click.echo(message)
