from plex_playlist_creator.logger import logger

class PlaylistCreator:
    def __init__(self, plex_manager, redacted_api):
        self.plex_manager = plex_manager
        self.redacted_api = redacted_api

    def create_playlist_from_collage(self, collage_id):
        """Creates a Plex playlist based on a RED collage."""
        collage_data = self.redacted_api.get_collage(collage_id)
        collage_name = collage_data.get('response', {}).get('name', f'Collage {collage_id}')
        group_ids = collage_data.get('response', {}).get('torrentGroupIDList', [])

        matched_rating_keys = set()
        for group_id in group_ids:
            torrent_group = self.redacted_api.get_torrent_group(group_id)
            file_paths = self.redacted_api.get_file_paths_from_torrent_group(torrent_group)
            for path in file_paths:
                rating_key = self.plex_manager.get_rating_key(path)
                if rating_key:
                    matched_rating_keys.add(int(rating_key))

        if matched_rating_keys:
            albums = self.plex_manager.fetch_albums_by_keys(list(matched_rating_keys))
            self.plex_manager.create_playlist(collage_name, albums)
        else:
            logger.warning(f'No matching albums found for collage "{collage_name}".')