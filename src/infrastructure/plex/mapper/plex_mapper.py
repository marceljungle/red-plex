
from src.domain.models import Album
from typing import List
from plexapi.base import MediaContainer

class PlexMapper:
    """Maps Plex API responses to domain models"""

    @staticmethod
    def map_album_domain_to_dto(albums: List[Album]) -> List[MediaContainer]:
        """Convert Album domain object to API DTO"""
        if albums:
            return [album.id for album in albums]

        return None

    @staticmethod
    def map_album_domain_to_dto(albums: List[Album]) -> List[MediaContainer]:
        """Convert Album domain object to API DTO"""
        if albums:
            return [album.id for album in albums]

        return None
    
    @staticmethod
    def _fetch_albums_by_keys(self, rating_keys):
        """Fetches album objects from Plex using their rating keys."""
        logger.info('Fetching albums from Plex using rating keys: %s', rating_keys)
        return self.plex.fetchItems(rating_keys)