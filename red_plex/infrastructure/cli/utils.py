"""Shared utilities for CLI commands."""
from typing import Dict, List

import click

from red_plex.domain.models import Collection
from red_plex.infrastructure.constants.constants import MultiMatchMode
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode
from red_plex.use_case.create_collection.query.query_sync_collection import (
    QuerySyncCollectionUseCase)
from red_plex.use_case.create_collection.torrent_name.torrent_name_sync_collection import (
    TorrentNameCollectionCreatorUseCase)
from red_plex.use_case.upstream_sync.upstream_sync_use_case import UpstreamSyncUseCase


def get_database_from_context(ctx) -> LocalDatabase:
    """
    Get database instance from Click context with error handling.

    Args:
        ctx: Click context object

    Returns:
        LocalDatabase instance

    Raises:
        SystemExit: If database is not initialized
    """
    local_database = ctx.obj.get('db')
    if not local_database:
        click.echo("Error: Database not initialized.", err=True)
        ctx.exit(1)
    return local_database


def create_plex_manager(local_database: LocalDatabase) -> PlexManager:
    """
    Create a PlexManager instance.

    Args:
        local_database: LocalDatabase instance

    Returns:
        PlexManager instance
    """
    return PlexManager(db=local_database)


def map_fetch_mode(fetch_mode: str) -> AlbumFetchMode:
    """Map the fetch mode string to an AlbumFetchMode enum."""
    if fetch_mode == 'query':
        return AlbumFetchMode.QUERY
    return AlbumFetchMode.TORRENT_NAME


def map_multi_match_mode(mode: str) -> MultiMatchMode:
    """Map the multi-match mode string to a MultiMatchMode enum."""
    mode_lower = mode.lower()
    if mode_lower == 'all':
        return MultiMatchMode.ALL
    if mode_lower == 'none':
        return MultiMatchMode.NONE
    return MultiMatchMode.ASK


def update_collections_from_collages(local_database: LocalDatabase,
                                     collage_list: List[Collection],
                                     plex_manager: PlexManager,
                                     fetch_bookmarks=False,
                                     fetch_mode: AlbumFetchMode = AlbumFetchMode.TORRENT_NAME):
    """
    Forces the update of each collage (force_update=True)
    """

    # Reuse one API client per site so its rate limiter is shared across the whole run
    gazelle_apis: Dict[str, GazelleAPI] = {}
    processed_collages = set()

    for collage in collage_list:
        # Skip duplicated entries of the same collage within a run
        collage_key = ((collage.site or '').lower(), str(collage.external_id))
        if collage_key in processed_collages:
            logger.info('Skipping duplicated entry for collage "%s" (id: %s, site: %s).',
                        collage.name, collage.external_id, collage.site)
            continue
        processed_collages.add(collage_key)

        logger.info('Updating collection for collage "%s"...', collage.name)
        try:
            site_key = (collage.site or '').lower()
            if site_key not in gazelle_apis:
                gazelle_apis[site_key] = GazelleAPI(collage.site)
            gazelle_api = gazelle_apis[site_key]

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
        except Exception as exc:  # pylint: disable=W0718
            logger.exception('Failed to update collection for collage "%s": %s',
                             collage.name, exc)
            continue

        if result.response_status is None:
            logger.info('No valid data found for collage "%s".', collage.name)
        else:
            logger.info('Collection for collage "%s" created/updated successfully with %s entries.',
                        collage.name, len(result.albums))


# pylint: disable=R0914,W0718,R0912,R0915
def push_collections_to_upstream(local_database: LocalDatabase,
                                 collage_list: List[Collection],
                                 plex_manager: PlexManager) -> bool:
    """
    Push local collection updates back to upstream collages.
    
    Args:
        local_database: Database instance
        collage_list: List of collections to sync upstream
        plex_manager: Plex manager instance
        
    Returns:
        True if all syncs were successful, False otherwise
    """
    # Initialize upstream sync use case
    upstream_sync = UpstreamSyncUseCase(local_database, plex_manager)

    # Get preview of what would be synced
    preview_response = upstream_sync.get_sync_preview(collage_list)

    if not preview_response.success:
        logger.error('Failed to get sync preview: %s', preview_response.error_message)
        return False

    if not preview_response.preview_data:
        logger.info('No collages need syncing - all are up to date')
        return True

    # Show confirmation dialog for each collage
    selected_albums = {}

    for collage_preview in preview_response.preview_data:
        click.echo(
            f'\nCollage "{collage_preview.collage_name}" ({collage_preview.external_id}) '
            f'will have {len(collage_preview.albums_to_add)} new items added:')

        # Show albums with numbers
        for i, album in enumerate(collage_preview.albums_to_add, 1):
            click.echo(f'  {i}. {album.display_name}')

        # Ask for album selection
        click.echo('\nSpecify which albums to add (e.g., "1,3,4" for albums 1, 3, and 4)')
        click.echo('Leave empty to add all albums, or "skip" to skip this collage:')

        selection = click.prompt('Albums to add', type=str, default='', show_default=False)
        selection = selection.strip()

        if selection.lower() == 'skip':
            click.echo('Skipping this collage.')
            continue

        # Parse selection
        selected_group_ids = [album.group_id
                              for album in collage_preview.albums_to_add]  # Default to all
        if selection:
            try:
                # Parse comma-separated numbers
                selected_indices = [int(x.strip()) - 1 for x in selection.split(',')
                                    if x.strip().isdigit()]

                # Validate indices
                valid_indices = [i for i in selected_indices
                                 if 0 <= i < len(collage_preview.albums_to_add)]

                if not valid_indices:
                    click.echo('No valid album numbers specified. Adding all albums.')
                else:
                    selected_group_ids = [collage_preview.albums_to_add[i].group_id
                                          for i in valid_indices]
                    click.echo(f'Selected {len(selected_group_ids)} album(s) to add.')

            except ValueError:
                click.echo('Invalid selection format. Adding all albums.')

        selected_albums[collage_preview.collage_id] = selected_group_ids

    if not selected_albums:
        logger.info('No albums selected for sync')
        return True

    # Filter collages to only sync those with selected albums
    collages_to_sync = [c for c in collage_list if c.id in selected_albums]

    # Perform the sync
    sync_response = upstream_sync.sync_collections_upstream(collages_to_sync, selected_albums)

    # Log results
    logger.info('Upstream sync completed: %d/%d collections synced successfully',
                sync_response.synced_collages, sync_response.total_collages)

    if sync_response.errors:
        for error in sync_response.errors:
            logger.error(error)

    return sync_response.success
