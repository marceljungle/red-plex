"""Module for creating Plex playlists from Gazelle collages or bookmarks."""

import html
from plex_playlist_creator.logger import logger

# pylint: disable=W0718
class PlaylistCreator:
    """Handles the creation of Plex playlists based on Gazelle collages or bookmarks."""

    def __init__(self, plex_manager, gazelle_api):
        self.plex_manager = plex_manager
        self.gazelle_api = gazelle_api

    def create_playlist_from_collage(self, collage_id):
        """Creates a Plex playlist based on a Gazelle collage."""
        try:
            collage_data = self.gazelle_api.get_collage(collage_id)
        except Exception as exc:
            logger.exception('Failed to retrieve collage %s: %s', collage_id, exc)
            return
        collage_name = html.unescape(
            collage_data.get('response', {}).get('name', f'Collage {collage_id}')
        )
        group_ids = collage_data.get('response', {}).get('torrentGroupIDList', [])

        matched_rating_keys = set()
        for group_id in group_ids:
            try:
                torrent_group = self.gazelle_api.get_torrent_group(group_id)
                file_paths = self.gazelle_api.get_file_paths_from_torrent_group(torrent_group)
            except Exception as exc:
                logger.exception('Failed to retrieve torrent group %s: %s', group_id, exc)
                continue
            matched_rating_keys.update(
                int(key)
                for path in file_paths
                for key in (self.plex_manager.get_rating_keys(path) or [])
            )

        if matched_rating_keys:
            albums = self.plex_manager.fetch_albums_by_keys(list(matched_rating_keys))
            self.plex_manager.create_playlist(collage_name, albums)
        else:
            message = f'No matching albums found for collage "{collage_name}".'
            logger.warning(message)
            print(message)

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
