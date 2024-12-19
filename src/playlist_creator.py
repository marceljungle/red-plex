"""Module for creating Plex playlists from Gazelle collages or bookmarks."""

import html
import logging
import click
import requests
from src.infrastructure.cache.collage_playlist_cache import CollagePlaylistCache
from src.infrastructure.cache.bookmarks_playlist_cache import BookmarksPlaylistCache

logger = logging.getLogger(__name__)

# pylint: disable=R0801
class PlaylistCreator:
    """
    Handles the creation and updating of Plex playlists
    based on Gazelle collages or bookmarks.
    """

    def __init__(self, plex_manager, gazelle_api, cache_file=None):
        self.plex_manager = plex_manager
        self.gazelle_api = gazelle_api
        self.playlist_cache = CollagePlaylistCache(cache_file)
        self.bookmarks_cache = BookmarksPlaylistCache(cache_file)

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def create_or_update_playlist_from_collage(self, collage_id, site=None, force_update=False):
        """Creates or updates a Plex playlist based on a Gazelle collage."""
        try:
            collage_data = self.gazelle_api.get_collage(collage_id)
        except requests.exceptions.RequestException as exc:
            logger.exception('Failed to retrieve collage %s: %s', collage_id, exc)
            return

        collage_name = html.unescape(
            collage_data.get('response', {}).get('name', f'Collage {collage_id}')
        )
        group_ids = collage_data.get('response', {}).get('torrentGroupIDList', [])

        existing_playlist = self.plex_manager.get_playlist_by_name(collage_name)
        if existing_playlist:
            playlist_rating_key = existing_playlist.ratingKey
            cached_playlist = self.playlist_cache.get_playlist(playlist_rating_key)
            if cached_playlist:
                cached_group_ids = set(cached_playlist['torrent_group_ids'])
            else:
                cached_group_ids = set()

            if not force_update:
                # Ask for confirmation if not forced
                response = click.confirm(
                    f'Playlist "{collage_name}" already exists. '
                    'Do you want to update it with new items?',
                    default=True
                )
                if not response:
                    click.echo('Skipping playlist update.')
                    return
        else:
            existing_playlist = None
            cached_group_ids = set()

        new_group_ids = set(map(int, group_ids)) - cached_group_ids
        if not new_group_ids:
            click.echo(f'No new items to add to playlist "{collage_name}".')
            return

        matched_rating_keys = set()
        processed_group_ids = set()
        for gid in new_group_ids:
            try:
                torrent_group = self.gazelle_api.get_torrent_group(gid)
                file_paths = self.gazelle_api.get_file_paths_from_torrent_group(torrent_group)
            except requests.exceptions.RequestException as exc:
                logger.exception('Failed to retrieve torrent group %s: %s', gid, exc)
                continue

            group_matched = False
            for path in file_paths:
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
            if existing_playlist:
                # Update existing playlist
                self.plex_manager.add_items_to_playlist(existing_playlist, albums)
                logger.info('Playlist "%s" updated with %d new albums.', collage_name, len(albums))
                # Update cache
                updated_group_ids = cached_group_ids.union(processed_group_ids)
                self.playlist_cache.save_playlist(
                    existing_playlist.ratingKey, collage_name, site, collage_id, list(
                        updated_group_ids)
                )
                click.echo(f'Playlist "{collage_name}" updated with {len(albums)} new albums.')
            else:
                # Create new playlist
                playlist = self.plex_manager.create_playlist(collage_name, albums)
                logger.info('Playlist "%s" created with %d albums.', collage_name, len(albums))
                # Save to cache
                self.playlist_cache.save_playlist(
                    playlist.ratingKey, collage_name, site, collage_id, list(processed_group_ids)
                )
                click.echo(f'Playlist "{collage_name}" created with {len(albums)} albums.')
        else:
            message = f'No matching albums found for new items in collage "{collage_name}".'
            logger.warning(message)
            click.echo(message)

    def create_or_update_playlist_from_bookmarks(self, bookmarks, site, force_update=False):
        """Creates a Plex playlist based on the user's bookmarks from a Gazelle-based site."""
        bookmarks_playlist_name = f"{site.upper()} Bookmarks"
        bookmarks_group_ids = self.gazelle_api.get_group_ids_from_bookmarks(bookmarks)
        existing_playlist = self.plex_manager.get_playlist_by_name(bookmarks_playlist_name)
        if existing_playlist:
            playlist_rating_key = existing_playlist.ratingKey
            cached_playlist = self.bookmarks_cache.get_bookmark(playlist_rating_key)
            if cached_playlist:
                cached_group_ids = set(cached_playlist['torrent_group_ids'])
            else:
                cached_group_ids = set()

            if not force_update:
                # Ask for confirmation if not forced
                response = click.confirm(
                    f'Playlist "{bookmarks_playlist_name}" already exists. '
                    'Do you want to update it with new items?',
                    default=True
                )
                if not response:
                    click.echo('Skipping playlist update.')
                    return
        else:
            existing_playlist = None
            cached_group_ids = set()

        new_group_ids = set(map(int, bookmarks_group_ids)) - cached_group_ids
        if not new_group_ids:
            click.echo(f'No new items to add to playlist "{bookmarks_playlist_name}".')
            return

        matched_rating_keys = set()
        processed_group_ids = set()
        for gid in new_group_ids:
            try:
                torrent_group = self.gazelle_api.get_torrent_group(gid)
                file_paths = self.gazelle_api.get_file_paths_from_torrent_group(torrent_group)
            except requests.exceptions.RequestException as exc:
                logger.exception('Failed to retrieve torrent group %s: %s', gid, exc)
                continue

            group_matched = False
            for path in file_paths:
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
            if existing_playlist:
                # Update existing playlist
                self.plex_manager.add_items_to_playlist(existing_playlist, albums)
                logger.info(
                    'Playlist "%s" updated with %d new albums.',
                        bookmarks_playlist_name, len(albums))
                # Update cache
                updated_group_ids = cached_group_ids.union(processed_group_ids)
                self.bookmarks_cache.save_bookmarks(
                    existing_playlist.ratingKey, site, list(
                        updated_group_ids)
                )
                click.echo(
                    f'Playlist "{bookmarks_playlist_name}" updated with {len(albums)} new albums.')
            else:
                # Create new playlist
                playlist = self.plex_manager.create_playlist(bookmarks_playlist_name, albums)
                logger.info(
                    'Playlist "%s" created with %d albums.', bookmarks_playlist_name, len(albums))
                # Save to cache
                self.bookmarks_cache.save_bookmarks(
                    playlist.ratingKey, site, list(processed_group_ids)
                )
                click.echo(
                    f'Playlist "{bookmarks_playlist_name}" created with {len(albums)} albums.')
        else:
            message = (
                f'No matching albums found for new items in collage "{bookmarks_playlist_name}".')
            logger.warning(message)
            click.echo(message)
