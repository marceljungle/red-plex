from src.infrastructure.config.config import load_config
from src.infrastructure.logger.logger import logger
from src.infrastructure.plex.plex_manager import PlexManager

def initialize_plex_manager():
    """Initialize PlexManager without populating cache."""
    config_data = load_config()
    plex_token = config_data.get('PLEX_TOKEN')
    plex_url = config_data.get('PLEX_URL', 'http://localhost:32400')
    section_name = config_data.get('SECTION_NAME', 'Music')

    if not plex_token:
        message = 'PLEX_TOKEN must be set in the config file.'
        logger.error(message)
        return None

    return PlexManager(plex_url, plex_token, section_name)
