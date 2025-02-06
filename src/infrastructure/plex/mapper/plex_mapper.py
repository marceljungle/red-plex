
from domain.models import Album, Collection
from typing import List
from plexapi.base import MediaContainer
from plexapi.collection import Collection as PlexCollection

class PlexMapper:
    """Maps Plex API responses to domain models"""

    @staticmethod
    def map_plex_collection_to_domain(collections: List[PlexCollection]) -> List[Collection]:
        """Convert Plex collections objects to domain collections"""
        if collections:
            return [Collection(
                id=collection.ratingKey,
                name=collection.title,
            ) for collection in collections]
        return None

    @staticmethod
    def map_album_domain_to_dto(albums: List[Album]) -> List[MediaContainer]:
        """Convert Album domain object to API DTO"""
        if albums:
            return [album.id for album in albums]

        return None
