
from src.domain.models import Album

class PlexMapper:
    """Maps Plex API responses to domain models"""

    @staticmethod
    def map_album() -> Album:
        return None