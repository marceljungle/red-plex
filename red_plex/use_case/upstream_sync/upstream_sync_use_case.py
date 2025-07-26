"""Upstream sync use case for syncing collections to site collages."""
import logging
from typing import List, Dict, Any, Optional

from red_plex.domain.models import Collection
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.upstream_sync.response import (
    UpstreamSyncPreviewResponse, UpstreamSyncResponse, 
    CollagePreviewData, AlbumSyncInfo
)


class UpstreamSyncUseCase:
    """Use case for syncing local Plex collections to upstream site collages."""
    
    def __init__(self, local_database: LocalDatabase, plex_manager: PlexManager):
        """Initialize the upstream sync use case.
        
        Args:
            local_database: Database instance for local data
            plex_manager: Plex manager for collection access
        """
        self.db = local_database
        self.plex_manager = plex_manager
        self.logger = logging.getLogger('red_plex')
    
    def get_sync_preview(self, collages: List[Collection]) -> UpstreamSyncPreviewResponse:
        """Get preview of what would be synced for the given collages.
        
        Args:
            collages: List of collages to preview sync for
            
        Returns:
            Preview response with data about what would be synced
        """
        preview_data = []
        errors = []
        
        for collage in collages:
            try:
                collage_preview = self._get_collage_preview(collage)
                if collage_preview and collage_preview.albums_to_add:
                    preview_data.append(collage_preview)
            except Exception as e:
                error_msg = f'Error getting preview for collage "{collage.name}": {str(e)}'
                self.logger.error(error_msg)
                errors.append(error_msg)
        
        return UpstreamSyncPreviewResponse(
            preview_data=preview_data,
            success=len(errors) == 0,
            error_message='; '.join(errors) if errors else None
        )
    
    def sync_collections_upstream(self, 
                                 collages: List[Collection],
                                 selected_albums: Optional[Dict[str, List[str]]] = None) -> UpstreamSyncResponse:
        """Sync the given collections to their upstream collages.
        
        Args:
            collages: List of collages to sync
            selected_albums: Optional dict mapping collage_id to list of selected group_ids
                           If None, all missing albums will be synced
            
        Returns:
            Response with sync results
        """
        sync_results = {}
        errors = []
        success_count = 0
        
        for collage in collages:
            try:
                result = self._sync_single_collage(collage, selected_albums)
                sync_results[collage.id] = result
                
                if result.get('success', False):
                    success_count += 1
                else:
                    errors.append(f'Failed to sync collage "{collage.name}": {result.get("error", "Unknown error")}')
                    
            except Exception as e:
                error_msg = f'Error syncing collage "{collage.name}": {str(e)}'
                self.logger.error(error_msg)
                errors.append(error_msg)
                sync_results[collage.id] = {'success': False, 'error': str(e)}
        
        return UpstreamSyncResponse(
            success=len(errors) == 0,
            synced_collages=success_count,
            total_collages=len(collages),
            errors=errors,
            sync_results=sync_results
        )
    
    def _get_collage_preview(self, collage: Collection) -> Optional[CollagePreviewData]:
        """Get preview data for a single collage."""
        try:
            gazelle_api = GazelleAPI(collage.site)
            
            # Verify user ownership
            if not self._verify_collage_ownership(gazelle_api, collage):
                return None
            
            # Get missing group IDs
            missing_group_ids = self._get_missing_group_ids(gazelle_api, collage)
            if not missing_group_ids:
                return None
            
            # Get album details
            albums_to_add = []
            for group_id in missing_group_ids:
                album_info = self._get_album_info(gazelle_api, group_id)
                albums_to_add.append(album_info)
            
            return CollagePreviewData(
                collage_id=collage.id,
                collage_name=collage.name,
                external_id=collage.external_id,
                site=collage.site,
                albums_to_add=albums_to_add
            )
            
        except Exception as e:
            self.logger.error('Error getting preview for collage "%s": %s', collage.name, e)
            return None
    
    def _sync_single_collage(self, collage: Collection, 
                           selected_albums: Optional[Dict[str, List[str]]]) -> Dict[str, Any]:
        """Sync a single collage to upstream."""
        try:
            gazelle_api = GazelleAPI(collage.site)
            
            # Verify ownership
            if not self._verify_collage_ownership(gazelle_api, collage):
                return {'success': False, 'error': 'User does not own this collage'}
            
            # Get group IDs to sync
            if selected_albums and collage.id in selected_albums:
                group_ids_to_sync = selected_albums[collage.id]
            else:
                # Sync all missing group IDs
                group_ids_to_sync = self._get_missing_group_ids(gazelle_api, collage)
            
            if not group_ids_to_sync:
                self.logger.info('Collage "%s" is already up to date', collage.name)
                return {'success': True, 'message': 'Already up to date', 'added': 0, 'rejected': 0, 'duplicated': 0}
            
            # Add groups to collage
            self.logger.info('Adding %d items to collage "%s"', len(group_ids_to_sync), collage.name)
            add_result = gazelle_api.add_to_collage(collage.external_id, group_ids_to_sync)
            
            if add_result and add_result.get('status') == 'success':
                response_data = add_result.get('response', {})
                added_count = len(response_data.get('groupsadded', []))
                rejected_count = len(response_data.get('groupsrejected', []))
                duplicated_count = len(response_data.get('groupsduplicated', []))
                
                self.logger.info('Successfully synced collage "%s": %d added, %d rejected, %d duplicated',
                               collage.name, added_count, rejected_count, duplicated_count)
                
                return {
                    'success': True,
                    'added': added_count,
                    'rejected': rejected_count,
                    'duplicated': duplicated_count
                }
            else:
                error_msg = f'API call failed: {add_result}'
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _verify_collage_ownership(self, gazelle_api: GazelleAPI, collage: Collection) -> bool:
        """Verify that the user owns the given collage."""
        try:
            # Get user info
            user_info = gazelle_api.get_user_info()
            if not user_info or not user_info.get('id'):
                return False
            
            # Get user's collages
            user_collages = gazelle_api.get_user_collages(str(user_info['id']))
            if not user_collages:
                return False
            
            # Check ownership
            return any(uc.external_id == collage.external_id for uc in user_collages)
            
        except Exception as e:
            self.logger.error('Error verifying ownership for collage "%s": %s', collage.name, e)
            return False
    
    def _get_missing_group_ids(self, gazelle_api: GazelleAPI, collage: Collection) -> List[str]:
        """Get list of group IDs that are missing from the upstream collage."""
        try:
            # Get Plex collection items
            plex_collection = self.plex_manager.get_collection_by_rating_key(collage.id)
            if not plex_collection:
                self.logger.warning('Plex collection with rating key "%s" not found', collage.id)
                return []
            
            # Get rating keys from collection
            collection_items = plex_collection.items()
            current_rating_keys = [item.ratingKey for item in collection_items]
            
            if not current_rating_keys:
                return []
            
            # Get group IDs for rating keys
            group_ids = self.db.get_group_ids_by_rating_keys(current_rating_keys, collage.site.upper())
            if not group_ids:
                self.logger.warning('No group ID mappings found for collection "%s" on site %s',
                                  collage.name, collage.site)
                return []
            
            # Get current collage content
            current_collage_data = gazelle_api.get_collage(collage.external_id)
            if not current_collage_data:
                return []
            
            # Find missing group IDs
            current_group_ids = {str(tg.id) for tg in current_collage_data.torrent_groups}
            missing_group_ids = [gid for gid in group_ids if gid not in current_group_ids]
            
            return missing_group_ids
            
        except Exception as e:
            self.logger.error('Error getting missing group IDs for collage "%s": %s', collage.name, e)
            return []
    
    def _get_album_info(self, gazelle_api: GazelleAPI, group_id: str) -> AlbumSyncInfo:
        """Get album information for the given group ID."""
        try:
            torrent_group = gazelle_api.get_torrent_group(group_id)
            if torrent_group:
                artists_str = ', '.join(torrent_group.artists) if torrent_group.artists else 'Unknown Artist'
                display_name = f'{artists_str} - {torrent_group.album_name}'
                return AlbumSyncInfo(
                    group_id=group_id,
                    display_name=display_name,
                    artists=torrent_group.artists,
                    album_name=torrent_group.album_name
                )
            else:
                display_name = f'Group ID {group_id} (unable to get details)'
                return AlbumSyncInfo(group_id=group_id, display_name=display_name)
                
        except Exception as e:
            self.logger.debug('Error getting details for group %s: %s', group_id, e)
            display_name = f'Group ID {group_id} (unable to get details)'
            return AlbumSyncInfo(group_id=group_id, display_name=display_name)