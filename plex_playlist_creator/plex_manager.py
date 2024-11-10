"""Module for managing Plex albums and playlists."""

import os
import csv
from plexapi.server import PlexServer
from plex_playlist_creator.logger import logger

class PlexManager:
    """Handles operations related to Plex albums and playlists."""

    def __init__(self, url, token, section_name, csv_file=None):
        self.url = url
        self.token = token
        self.section_name = section_name

        # Define CSV file location based on OS
        default_csv_path = os.path.join('data', 'plex_albums_cache.csv')
        self.csv_file = csv_file if csv_file else default_csv_path

        self.plex = PlexServer(self.url, self.token)
        self.album_data = self.load_albums_from_csv()

    def save_albums_to_csv(self):
        """Saves minimal album information to a CSV file."""
        music_library = self.plex.library.section(self.section_name)
        all_albums = music_library.searchAlbums()

        # Ensure the directory for CSV file exists
        os.makedirs(os.path.dirname(self.csv_file), exist_ok=True)

        with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for album in all_albums:
                tracks = album.tracks()
                if tracks:
                    media_path = tracks[0].media[0].parts[0].file
                    num_files_in_directory = len(os.listdir(os.path.dirname(media_path)))
                    if num_files_in_directory < album.leafCount:
                        album_folder = os.path\
                            .basename(os.path.dirname(os.path.dirname(media_path)))
                    else:
                        album_folder = os.path.basename(os.path.dirname(media_path))
                    writer.writerow([album.ratingKey, album_folder])
                else:
                    logger.warning('Skipping album with no tracks: %s', album.title)
        logger.info('Albums cached successfully.')

    def load_albums_from_csv(self):
        """Loads album data from the CSV file."""
        album_data = {}
        if os.path.exists(self.csv_file):
            with open(self.csv_file, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    album_id, folder_name = row
                    album_data[int(album_id)] = folder_name
            logger.info('Albums loaded from cache.')
        else:
            logger.info('Cache not found, generating new cache.')
            self.save_albums_to_csv()
            album_data = self.load_albums_from_csv()
        return album_data

    def get_rating_key(self, path):
        """Returns the rating key if the path matches an album folder."""
        logger.info('Matched album folder name: %s, returning rating key...', path)
        return next((key for key, folder in self.album_data.items() if path in folder), None)

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
