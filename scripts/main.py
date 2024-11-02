from plex_playlist_creator.plex_manager import PlexManager
from plex_playlist_creator.redacted_api import RedactedAPI
from plex_playlist_creator.playlist_creator import PlaylistCreator
from plex_playlist_creator.config import (
    PLEX_URL, PLEX_TOKEN, SECTION_NAME, RED_API_KEY, COLLAGE_IDS
)
from plex_playlist_creator.logger import logger

def main():
    if not PLEX_TOKEN or not RED_API_KEY:
        logger.error('PLEX_TOKEN and RED_API_KEY must be set in the environment variables.')
        return

    # Initialize managers
    plex_manager = PlexManager(PLEX_URL, PLEX_TOKEN, SECTION_NAME)
    redacted_api = RedactedAPI(RED_API_KEY)
    playlist_creator = PlaylistCreator(plex_manager, redacted_api)

    # Create playlists for each collage
    for collage_id in COLLAGE_IDS:
        try:
            playlist_creator.create_playlist_from_collage(collage_id)
        except Exception as e:
            logger.exception(f'Failed to create playlist for collage {collage_id}: {e}')

if __name__ == '__main__':
    main()