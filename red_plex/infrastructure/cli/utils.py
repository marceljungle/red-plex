"""Shared utilities for CLI commands."""
from typing import List

from red_plex.domain.models import Collection
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode
from red_plex.use_case.create_collection.query.query_sync_collection import (
    QuerySyncCollectionUseCase)
from red_plex.use_case.create_collection.torrent_name.torrent_name_sync_collection import (
    TorrentNameCollectionCreatorUseCase)


def map_fetch_mode(fetch_mode: str) -> AlbumFetchMode:
    """Map the fetch mode string to an AlbumFetchMode enum."""
    if fetch_mode == 'query':
        return AlbumFetchMode.QUERY
    return AlbumFetchMode.TORRENT_NAME


def update_collections_from_collages(local_database: LocalDatabase,
                                     collage_list: List[Collection],
                                     plex_manager: PlexManager,
                                     fetch_bookmarks=False,
                                     fetch_mode: AlbumFetchMode = AlbumFetchMode.TORRENT_NAME):
    """
    Forces the update of each collage (force_update=True)
    """

    for collage in collage_list:
        logger.info('Updating collection for collage "%s"...', collage.name)
        gazelle_api = GazelleAPI(collage.site)

        if AlbumFetchMode.TORRENT_NAME == fetch_mode:
            collection_creator = TorrentNameCollectionCreatorUseCase(local_database,
                                                                     plex_manager,
                                                                     gazelle_api)
            result = collection_creator.execute(
                collage_id=collage.external_id,
                site=collage.site,
                fetch_bookmarks=fetch_bookmarks,
                force_update=True
            )
        else:
            collection_creator = QuerySyncCollectionUseCase(local_database,
                                                            plex_manager,
                                                            gazelle_api)
            result = collection_creator.execute(
                collage_id=collage.external_id,
                site=collage.site,
                fetch_bookmarks=fetch_bookmarks,
                force_update=True
            )

        if result.response_status is None:
            logger.info('No valid data found for collage "%s".', collage.name)
        else:
            logger.info('Collection for collage "%s" created/updated successfully with %s entries.',
                        collage.name, len(result.albums))