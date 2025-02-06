from infrastructure.services.collection_creator import CollectionCreator

def initialize_collection_creator(plex_manager, gazelle_api):
    """Initialize CollectionCreator using existing plex_manager and gazelle_api."""
    return CollectionCreator(plex_manager, gazelle_api)
