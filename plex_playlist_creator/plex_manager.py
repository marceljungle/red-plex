"""Module for managing Plex albums and playlists."""

import os
from plexapi.server import PlexServer
from plex_playlist_creator.logger import logger
from plex_playlist_creator.album_cache import AlbumCache

class PlexManager:
    """Handles operations related to Plex."""

    def __init__(self, url, token, section_name, csv_file=None):
        self.url = url
        self.token = token
        self.section_name = section_name
        self.plex = PlexServer(self.url, self.token)

        # Initialize the album cache
        self.album_cache = AlbumCache(csv_file)
        self.album_data = self.album_cache.load_albums()

        if not self.album_data:
            self.populate_album_cache()

    def populate_album_cache(self):
        """Fetches albums from Plex and saves them to the cache."""
        music_library = self.plex.library.section(self.section_name)
        all_albums = music_library.searchAlbums()
        album_data = {}

        for album in all_albums:
            tracks = album.tracks()
            if tracks:
                media_path = tracks[0].media[0].parts[0].file
                num_files_in_directory = len(os.listdir(os.path.dirname(media_path)))
                if num_files_in_directory < album.leafCount:
                    # Determine album folder name when files are in subdirectories
                    album_folder = os.path.basename(os.path.dirname(os.path.dirname(media_path)))
                else:
                    album_folder = os.path.basename(os.path.dirname(media_path))
                album_data[int(album.ratingKey)] = album_folder
            else:
                logger.warning('Skipping album with no tracks: %s', album.title)

        self.album_cache.save_albums(album_data)
        self.album_data = album_data

    def reset_album_cache(self):
        """Resets the album cache by deleting the cache file."""
        self.album_cache.reset_cache()
        self.album_data = {}

    def get_rating_key(self, path):
        """Returns the rating key if the path matches an album folder."""
        rating_key = next((key for key, folder in self.album_data.items() if path in folder), None)
        if rating_key:
            logger.info('Matched album folder name: %s, returning rating key %s...', path,
                         rating_key)
        return rating_key

    def fetch_albums_by_keys(self, rating_keys):
        """Fetches album objects from Plex using their rating keys."""
        logger.info('Fetching albums from Plex using rating keys: %s', rating_keys)
        return self.plex.fetchItems(rating_keys)

    def create_playlist(self, name, albums):
        """Creates a playlist in Plex."""
        logger.info('Creating playlist with name "%s" and %d albums.', name, len(albums))
        playlist = self.plex.createPlaylist(name, self.section_name, albums)
        logger.info('Playlist "%s" created with %d albums.', name, len(albums))
        return playlist
