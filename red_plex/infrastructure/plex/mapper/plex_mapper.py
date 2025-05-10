"""Module for mapping Plex API responses to domain models and vice versa."""

from typing import List, Optional

from plexapi.collection import Collection as PlexCollection

from red_plex.domain.models import Collection


class PlexMapper:
    """Maps Plex API responses to domain models"""

    @staticmethod
    def map_plex_collections_to_domain(
            collections: List[PlexCollection]) -> Optional[List[Collection]]:
        """Convert Plex collections objects to domain collections"""
        if collections:
            return [PlexMapper.map_plex_collection_to_domain(collection)
                    for collection in collections]
        return None

    @staticmethod
    def map_plex_collection_to_domain(collection: PlexCollection) -> Optional[Collection]:
        """Convert Plex collections objects to domain collections"""
        if collection:
            return Collection(
                id=str(collection.ratingKey),
                name=collection.title,
            )
        return None
