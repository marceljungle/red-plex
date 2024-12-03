"""Module for creating Plex playlists from Gazelle collages or bookmarks."""

import html
import logging
import click
import requests

from plex_playlist_creator.playlist_cache import PlaylistCache

logger = logging.getLogger(__name__)

class PlaylistCreator:
    """Handles the creation of Plex playlists based on Gazelle collages or bookmarks."""
    # pylint: disable=too-few-public-methods

    def __init__(self, plex_manager, gazelle_api, cache_file=None):
        self.plex_manager = plex_manager
        self.gazelle_api = gazelle_api
        self.playlist_cache = PlaylistCache(cache_file)

    def create_playlist_from_collage(self, collage_id):
        """Creates or updates a Plex playlist based on a Gazelle collage."""
        # pylint: disable=too-many-locals, too-many-branches, too-many-statements
        try:
            collage_data = self.gazelle_api.get_collage(collage_id)
        except requests.exceptions.RequestException as exc:
            logger.exception('Failed to retrieve collage %s: %s', collage_id, exc)
            return

        collage_name = html.unescape(
            collage_data.get('response', {}).get('name', f'Collage {collage_id}')
        )
        group_ids = collage_data.get('response', {}).get('torrentGroupIDList', [])

        # Check if the playlist already exists in Plex
        existing_playlist = self.plex_manager.get_playlist_by_name(collage_name)
        if existing_playlist:
            # Playlist exists
            playlist_rating_key = existing_playlist.ratingKey
            # Check if we have cached data for this playlist
            cached_playlist = self.playlist_cache.get_playlist(playlist_rating_key)
            if cached_playlist:
                # Playlist exists in cache
                cached_group_ids = set(cached_playlist['torrent_group_ids'])
            else:
                # No cache for existing playlist
                cached_group_ids = set()
            # Ask user if they want to update
            response = click.confirm(
                f'Playlist "{collage_name}" already exists. '
                'Do you want to update it with new items?',
                default=True
            )
            if not response:
                click.echo('Skipping playlist update.')
                return
        else:
            # Playlist does not exist
            existing_playlist = None
            cached_group_ids = set()

        # Find new group IDs (those not in cached_group_ids)
        new_group_ids = set(map(int, group_ids)) - cached_group_ids
        if not new_group_ids:
            click.echo(f'No new items to add to playlist "{collage_name}".')
            return

        matched_rating_keys = set()
        processed_group_ids = set()
        for group_id in new_group_ids:
            try:
                torrent_group = self.gazelle_api.get_torrent_group(group_id)
                file_paths = self.gazelle_api.get_file_paths_from_torrent_group(torrent_group)
            except requests.exceptions.RequestException as exc:
                logger.exception('Failed to retrieve torrent group %s: %s', group_id, exc)
                continue

            group_matched = False
            for path in file_paths:
                rating_keys = self.plex_manager.get_rating_keys(path) or []
                if rating_keys:
                    group_matched = True
                    matched_rating_keys.update(int(key) for key in rating_keys)

            if group_matched:
                processed_group_ids.add(group_id)
                logger.info('Matched torrent group %s with albums in Plex.', group_id)
            else:
                logger.info('No matching albums found for torrent group %s; skipping.', group_id)

        if matched_rating_keys:
            albums = self.plex_manager.fetch_albums_by_keys(list(matched_rating_keys))
            if existing_playlist:
                # Update existing playlist
                self.plex_manager.add_items_to_playlist(existing_playlist, albums)
                logger.info('Playlist "%s" updated with %d new albums.', collage_name, len(albums))
                # Update cache
                updated_group_ids = cached_group_ids.union(processed_group_ids)
                self.playlist_cache.save_playlist(
                    existing_playlist.ratingKey, collage_name, list(updated_group_ids)
                )
                click.echo(f'Playlist "{collage_name}" updated with {len(albums)} new albums.')
            else:
                # Create new playlist
                playlist = self.plex_manager.create_playlist(collage_name, albums)
                logger.info('Playlist "%s" created with %d albums.', collage_name, len(albums))
                # Save to cache
                self.playlist_cache.save_playlist(
                    playlist.ratingKey, collage_name, list(processed_group_ids)
                )
                click.echo(f'Playlist "{collage_name}" created with {len(albums)} albums.')
        else:
            message = f'No matching albums found for new items in collage "{collage_name}".'
            logger.warning(message)
            click.echo(message)

    def create_playlist_from_bookmarks(self, file_paths, site):
        """Creates a Plex playlist based on the user's bookmarks from a Gazelle-based site."""
        matched_rating_keys = {
            int(key)
            for path in file_paths
            for key in (self.plex_manager.get_rating_keys(path) or [])
        }

        if matched_rating_keys:
            albums = self.plex_manager.fetch_albums_by_keys(list(matched_rating_keys))
            playlist_name = f'{site} Bookmarks'
            self.plex_manager.create_playlist(playlist_name, albums)
        else:
            message = f'No matching albums found for bookmarks on "{site}".'
            logger.warning(message)
            print(message)
