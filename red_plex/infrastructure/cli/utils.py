"""Shared utilities for CLI commands."""
from typing import List, Optional

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
    success_count = 0
    total_count = len(collage_list)
    
    for collage in collage_list:
        logger.info('Pushing collection updates for collage "%s" to upstream...', collage.name)
        
        try:
            # Initialize API for this site
            gazelle_api = GazelleAPI(collage.site)
            
            # Get user info to verify we can access the API
            user_info = gazelle_api.get_user_info()
            if not user_info:
                logger.error('Failed to get user info for site %s, skipping collage "%s"', 
                           collage.site, collage.name)
                continue
                
            user_id = user_info.get('id')
            if not user_id:
                logger.error('No user ID found in user info for site %s, skipping collage "%s"', 
                           collage.site, collage.name)
                continue
            
            # Get user's collages to verify this collage belongs to the user
            user_collages = gazelle_api.get_user_collages(str(user_id))
            if user_collages is None:
                logger.error('Failed to get user collages for site %s, skipping collage "%s"', 
                           collage.site, collage.name)
                continue
            
            # Check if the collage exists and belongs to this user
            target_collage = None
            for user_collage in user_collages:
                if str(user_collage.get('id')) == collage.external_id:
                    target_collage = user_collage
                    break
                    
            if not target_collage:
                logger.warning('Collage "%s" (ID: %s) not found in user\'s collages on site %s. '
                             'User may not own this collage or it may not exist.', 
                             collage.name, collage.external_id, collage.site)
                continue
            
            # Get the Plex collection to find what rating keys are currently in it
            plex_collection = plex_manager.get_collection_by_rating_key(collage.id)
            if not plex_collection:
                logger.warning('Plex collection with rating key "%s" not found. '
                             'This may happen if:\n'
                             '  1. The collection was deleted from Plex\n'
                             '  2. The collection ID in the database is outdated\n'
                             'To fix this, you can:\n'
                             '  1. Re-run "convert" command for collage ID %s to recreate the collection\n'
                             '  2. Or remove this entry from the database if no longer needed',
                             collage.id, collage.external_id)
                continue
                
            # Get rating keys from the collection
            collection_items = plex_collection.items()
            current_rating_keys = [item.ratingKey for item in collection_items]
            
            if not current_rating_keys:
                logger.info('No items found in Plex collection "%s", nothing to sync', collage.name)
                success_count += 1  # Consider empty collection as successful sync
                continue
            
            # Get group IDs for these rating keys from our database
            group_ids = local_database.get_group_ids_by_rating_keys(current_rating_keys, collage.site.upper())
            
            if not group_ids:
                logger.warning('No group ID mappings found for collection "%s" rating keys on site %s. '
                             'You may need to run site tag scanning first.', 
                             collage.name, collage.site)
                continue
            
            # Get current collage content to see what's already there
            current_collage_data = gazelle_api.get_collage(collage.external_id)
            if not current_collage_data:
                logger.error('Failed to get current collage data for "%s" (ID: %s)', 
                           collage.name, collage.external_id)
                continue
            
            # Extract current group IDs from collage
            current_group_ids = {str(tg.id) for tg in current_collage_data.torrent_groups}
            
            # Find missing group IDs that need to be added
            missing_group_ids = [gid for gid in group_ids if gid not in current_group_ids]
            
            if not missing_group_ids:
                logger.info('Collage "%s" is already up to date (no new items to add)', collage.name)
                success_count += 1
                continue
            
            # Add missing groups to the collage
            logger.info('Adding %d new items to collage "%s"', len(missing_group_ids), collage.name)
            add_result = gazelle_api.add_to_collage(collage.external_id, missing_group_ids)
            
            if add_result and add_result.get('status') == 'success':
                response_data = add_result.get('response', {})
                added_count = len(response_data.get('groupsadded', []))
                rejected_count = len(response_data.get('groupsrejected', []))
                duplicated_count = len(response_data.get('groupsduplicated', []))
                
                logger.info('Successfully synced collage "%s": %d added, %d rejected, %d duplicated',
                          collage.name, added_count, rejected_count, duplicated_count)
                success_count += 1
            else:
                logger.error('Failed to add groups to collage "%s": %s', collage.name, add_result)
                
        except Exception as e:
            logger.error('Error pushing collection "%s" to upstream: %s', collage.name, e)
    
    logger.info('Upstream sync completed: %d/%d collections synced successfully', 
                success_count, total_count)
    return success_count == total_count
