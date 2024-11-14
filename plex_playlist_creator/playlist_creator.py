"""Module for creating Plex playlists from RED collages."""

import html
from plex_playlist_creator.logger import logger

class PlaylistCreator: # pylint: disable=R0903
    """Handles the creation of Plex playlists based on Gazelle collages."""

    def __init__(self, plex_manager, gazelle_api):
        self.plex_manager = plex_manager
        self.gazelle_api = gazelle_api

    def create_playlist_from_collage(self, collage_id):
        """Creates a Plex playlist based on a Gazelle collage."""
        collage_data = self.gazelle_api.get_collage(collage_id)
        collage_name = html.unescape(
            collage_data.get('response', {}).get('name', f'Collage {collage_id}')
        )
        group_ids = collage_data.get('response', {}).get('torrentGroupIDList', [])

        matched_rating_keys = set()
        for group_id in group_ids:
            torrent_group = self.gazelle_api.get_torrent_group(group_id)
            file_paths = self.gazelle_api.get_file_paths_from_torrent_group(torrent_group)
            for path in file_paths:
                rating_key = self.plex_manager.get_rating_key(path)
                if rating_key:
                    matched_rating_keys.add(int(rating_key))

        if matched_rating_keys:
            albums = self.plex_manager.fetch_albums_by_keys(list(matched_rating_keys))
            self.plex_manager.create_playlist(collage_name, albums)
        else:
            logger.warning('No matching albums found for collage "%s".', collage_name)
