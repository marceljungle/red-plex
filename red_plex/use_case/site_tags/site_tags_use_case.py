"""Use case for managing site tag mappings and collections."""

import os
import re
import urllib.parse
from typing import List, Optional, Callable, Dict, Any

import click

from red_plex.domain.models import Album
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI


class SiteTagsUseCase:
    """Use case for managing site tag mappings and creating collections from tags."""

    def __init__(self, local_database: LocalDatabase, plex_manager: PlexManager, gazelle_api: GazelleAPI):
        self.local_database = local_database
        self.plex_manager = plex_manager
        self.gazelle_api = gazelle_api

    def scan_albums_for_site_tags(self, echo_func: Callable[[str], None], 
                                 confirm_func: Callable[[str], bool]) -> None:
        """
        Scan albums and create site tag mappings by searching filenames on the site.
        """
        site = self.gazelle_api.site
        echo_func(f"Starting scan for site: {site}")
        
        # Get unscanned albums for this site
        unscanned_rating_keys = self.local_database.get_unscanned_albums(site)
        
        if not unscanned_rating_keys:
            echo_func("No unscanned albums found.")
            return
            
        echo_func(f"Found {len(unscanned_rating_keys)} unscanned albums.")
        
        processed_count = 0
        success_count = 0
        
        for rating_key in unscanned_rating_keys:
            try:
                processed_count += 1
                echo_func(f"Processing album {processed_count}/{len(unscanned_rating_keys)}: {rating_key}")
                
                # Fetch album from Plex
                plex_album = self.plex_manager.library_section.fetchItem(rating_key)
                if not plex_album:
                    logger.warning("Could not fetch album with rating_key: %s", rating_key)
                    continue
                
                # Get track file paths
                file_paths = []
                for track in plex_album.tracks():
                    for media in track.media:
                        for part in media.parts:
                            if part.file:
                                file_paths.append(part.file)
                
                if not file_paths:
                    logger.warning("No file paths found for album: %s", rating_key)
                    continue
                
                # Try to find matches for each file
                found_match = False
                for file_path in file_paths:
                    filename = os.path.basename(file_path)
                    
                    # Try searching with the original filename
                    match_data = self._search_filename(filename)
                    
                    # If no match and filename starts with a number and dot, try without it
                    if not match_data and re.match(r'^\d+\.?\s*', filename):
                        modified_filename = re.sub(r'^\d+\.?\s*', '', filename)
                        echo_func(f"  Trying modified filename: {modified_filename}")
                        match_data = self._search_filename(modified_filename)
                    
                    if match_data:
                        # Process the match
                        if self._process_search_results(rating_key, match_data, echo_func, confirm_func):
                            found_match = True
                            success_count += 1
                            break  # Found a match, no need to check other files
                
                if not found_match:
                    echo_func(f"  No matches found for album: {rating_key}")
                    
            except Exception as e:
                logger.exception("Error processing album %s: %s", rating_key, e)
                echo_func(f"  Error processing album {rating_key}: {e}")
        
        echo_func(f"Scan completed. Processed: {processed_count}, Successful: {success_count}")

    def _search_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """Search for a filename on the site."""
        try:
            # URL encode the filename for the search
            encoded_filename = urllib.parse.quote_plus(filename)
            response = self.gazelle_api.browse_by_filelist(encoded_filename)
            return response
        except Exception as e:
            logger.error("Error searching filename %s: %s", filename, e)
            return None

    def _process_search_results(self, rating_key: str, search_data: Dict[str, Any], 
                               echo_func: Callable[[str], None], 
                               confirm_func: Callable[[str], bool]) -> bool:
        """Process search results and handle user confirmation for multiple matches."""
        if not search_data or search_data.get('status') != 'success':
            return False
            
        response_data = search_data.get('response', {})
        results = response_data.get('results', [])
        
        if not results:
            return False
            
        if len(results) == 1:
            # Single match, process it
            result = results[0]
            return self._create_site_tag_mapping(rating_key, result, echo_func)
        else:
            # Multiple matches, ask user to choose
            echo_func(f"  Found {len(results)} matches:")
            for i, result in enumerate(results):
                artists = result.get('artist', 'Unknown')
                if isinstance(artists, list):
                    artists = ', '.join(artists)
                group_name = result.get('groupName', 'Unknown')
                year = result.get('groupYear', 'Unknown')
                echo_func(f"    {i + 1}. {artists} - {group_name} ({year})")
            
            while True:
                try:
                    choice = click.prompt(f"  Choose a match (1-{len(results)}) or 's' to skip", type=str).strip().lower()
                    if choice == 's':
                        return False
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(results):
                        return self._create_site_tag_mapping(rating_key, results[choice_idx], echo_func)
                    else:
                        echo_func("  Invalid choice. Please try again.")
                except (ValueError, click.Abort):
                    echo_func("  Invalid input. Please try again.")
                except KeyboardInterrupt:
                    echo_func("  Scan interrupted by user.")
                    return False

    def _create_site_tag_mapping(self, rating_key: str, result: Dict[str, Any], 
                                echo_func: Callable[[str], None]) -> bool:
        """Create a site tag mapping from search result."""
        try:
            group_id = result.get('groupId')
            tags = result.get('tags', [])
            site = self.gazelle_api.site
            
            if not group_id:
                logger.warning("No group ID found in result for rating_key: %s", rating_key)
                return False
                
            # Insert the mapping
            self.local_database.insert_site_tag_mapping(rating_key, group_id, site, tags)
            
            artists = result.get('artist', 'Unknown')
            if isinstance(artists, list):
                artists = ', '.join(artists)
            group_name = result.get('groupName', 'Unknown')
            echo_func(f"  ✓ Mapped: {artists} - {group_name} (Group ID: {group_id}, Tags: {', '.join(tags)})")
            
            return True
            
        except Exception as e:
            logger.exception("Error creating site tag mapping for rating_key %s: %s", rating_key, e)
            echo_func(f"  Error creating mapping: {e}")
            return False

    def create_collection_from_tags(self, tags: List[str], collection_name: str, 
                                   echo_func: Callable[[str], None]) -> bool:
        """Create a Plex collection from albums matching the specified tags."""
        site = self.gazelle_api.site
        echo_func(f"Creating collection '{collection_name}' with tags: {', '.join(tags)}")
        
        # Get rating keys that match all specified tags
        matching_rating_keys = self.local_database.get_rating_keys_by_tags(tags, site)
        
        if not matching_rating_keys:
            echo_func("No albums found matching the specified tags.")
            return False
            
        echo_func(f"Found {len(matching_rating_keys)} matching albums.")
        
        try:
            # Get or create the collection in Plex
            collections = self.plex_manager.library_section.collections()
            existing_collection = None
            
            for collection in collections:
                if collection.title == collection_name:
                    existing_collection = collection
                    break
            
            if existing_collection:
                echo_func(f"Updating existing collection: {collection_name}")
                # Clear existing items
                for item in existing_collection.items():
                    existing_collection.removeItems(item)
            else:
                echo_func(f"Creating new collection: {collection_name}")
            
            # Fetch Plex albums and add to collection
            plex_albums = []
            for rating_key in matching_rating_keys:
                try:
                    plex_album = self.plex_manager.library_section.fetchItem(rating_key)
                    if plex_album:
                        plex_albums.append(plex_album)
                    else:
                        logger.warning("Could not fetch album with rating_key: %s", rating_key)
                except Exception as e:
                    logger.warning("Error fetching album %s: %s", rating_key, e)
            
            if not plex_albums:
                echo_func("No valid albums found to add to collection.")
                return False
            
            # Create or update the collection
            if existing_collection:
                existing_collection.addItems(plex_albums)
            else:
                self.plex_manager.library_section.createCollection(collection_name, plex_albums)
            
            echo_func(f"✓ Collection '{collection_name}' created/updated with {len(plex_albums)} albums.")
            return True
            
        except Exception as e:
            logger.exception("Error creating collection: %s", e)
            echo_func(f"Error creating collection: {e}")
            return False