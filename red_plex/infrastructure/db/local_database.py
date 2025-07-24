"""Defines the LocalDatabase class for managing a SQLite database."""

from typing import List, Optional

from red_plex.domain.models import Album, Collection
from red_plex.infrastructure.db.albums import AlbumDatabaseManager
from red_plex.infrastructure.db.base import BaseDatabaseManager
from red_plex.infrastructure.db.collection import CollectionDatabaseManager
from red_plex.infrastructure.db.site_tags import SiteTagDatabaseManager


# pylint: disable=R0904
class LocalDatabase(BaseDatabaseManager):
    """
    A class for managing local persistent storage in a SQLite database.
    It creates or reuses a 'red_plex.db' file and provides CRUD operations for:
    - albums
    - collage_collections
    - bookmark_collections
    - collection_torrent_groups (relational table for group IDs)
    - site tag mappings
    """

    def __init__(self):
        super().__init__()
        # Initialize specialized managers
        self._album_manager = AlbumDatabaseManager(self.conn)
        self._collection_manager = CollectionDatabaseManager(self.conn)
        self._site_tag_manager = SiteTagDatabaseManager(self.conn)

    # --------------------------------------------------------------------------
    #                               ALBUMS
    # --------------------------------------------------------------------------
    def insert_or_update_album(self, album: Album) -> None:
        """Insert or update an album, including its artists, in the database."""
        return self._album_manager.insert_or_update_album(album)

    def insert_albums_bulk(self, albums: List[Album]) -> None:
        """Inserts or updates a list of albums in bulk using a single transaction."""
        return self._album_manager.insert_albums_bulk(albums)

    def get_album(self, album_id: str) -> Optional[Album]:
        """Retrieve a single album by its ID, including its list of artists."""
        return self._album_manager.get_album(album_id)

    def get_all_albums(self) -> List[Album]:
        """Retrieve all albums from the database, including their lists of artists."""
        return self._album_manager.get_all_albums()

    def delete_album(self, album_id: str) -> None:
        """Delete an album."""
        return self._album_manager.delete_album(album_id)

    def reset_albums(self):
        """Deletes all records from 'albums', 'album_artists', and 'artists'."""
        self._album_manager.reset_albums()
        # Recreate tables after reset
        self._create_tables()

    # --------------------------------------------------------------------------
    #                      COLLAGE COLLECTIONS (and their groups)
    # --------------------------------------------------------------------------
    def insert_or_update_collage_collection(self, coll: Collection) -> None:
        """Insert or update a collage-based collection, along with its torrent groups."""
        return self._collection_manager.insert_or_update_collage_collection(coll)

    def get_collage_collection(self, rating_key: str) -> Optional[Collection]:
        """Retrieve a single collage-based collection by rating_key."""
        return self._collection_manager.get_collage_collection(rating_key)

    def get_all_collage_collections(self) -> List[Collection]:
        """Retrieve all collage-based collections from the DB."""
        return self._collection_manager.get_all_collage_collections()

    def delete_collage_collection(self, rating_key: str) -> None:
        """Delete a collage-based collection and associated torrent group mappings."""
        return self._collection_manager.delete_collage_collection(rating_key)

    def reset_collage_collections(self):
        """Deletes all records from 'collage_collections'."""
        return self._collection_manager.reset_collage_collections()

    # --------------------------------------------------------------------------
    #                           BOOKMARK COLLECTIONS
    # --------------------------------------------------------------------------
    def insert_or_update_bookmark_collection(self, coll: Collection) -> None:
        """Insert or update a bookmark-based collection."""
        return self._collection_manager.insert_or_update_bookmark_collection(coll)

    def get_bookmark_collection(self, rating_key: str) -> Optional[Collection]:
        """Retrieve a single bookmark collection by rating_key."""
        return self._collection_manager.get_bookmark_collection(rating_key)

    def get_all_bookmark_collections(self) -> List[Collection]:
        """Retrieve all bookmark collections from the DB."""
        return self._collection_manager.get_all_bookmark_collections()

    def delete_bookmark_collection(self, rating_key: str) -> None:
        """Delete a bookmark-based collection and associated torrent group mappings."""
        return self._collection_manager.delete_bookmark_collection(rating_key)

    def reset_bookmark_collections(self):
        """Deletes all records from 'bookmark_collections'."""
        return self._collection_manager.reset_bookmark_collections()

    # --------------------------------------------------------------------------
    #                           SITE TAG MAPPINGS
    # --------------------------------------------------------------------------
    def insert_site_tag_mapping(self, rating_key: str,
                                group_id: int,
                                site: str,
                                tags: List[str]) -> None:
        """Insert or update a site tag mapping with its associated tags."""
        return self._site_tag_manager.insert_site_tag_mapping(rating_key, group_id, site, tags)

    def get_rating_keys_by_tags(self, tags: List[str]) -> List[str]:
        """Get rating keys that have mappings containing all specified tags."""
        return self._site_tag_manager.get_rating_keys_by_tags(tags)

    def get_group_ids_by_rating_keys(self, rating_keys: List[str], site: str) -> List[str]:
        """Get group IDs for given rating keys from a specific site."""
        return self._site_tag_manager.get_group_ids_by_rating_keys(rating_keys, site)

    def get_rating_keys_by_collection_id(self, collection_id: str) -> List[str]:
        """Get rating keys for a collection from the collections table."""
        return self._site_tag_manager.get_rating_keys_by_collection_id(collection_id)

    def get_unscanned_albums(self) -> List[str]:
        """Get rating keys from albums table that are not present in mappings."""
        return self._site_tag_manager.get_unscanned_albums()

    def get_site_tags_stats(self):
        """Get statistics about site tag mappings."""
        return self._site_tag_manager.get_site_tags_stats()

    def get_recent_site_tag_mappings(self, limit: int = 20):
        """Get recent site tag mappings for display."""
        return self._site_tag_manager.get_recent_site_tag_mappings(limit)

    def reset_tag_mappings(self):
        """Reset site tag mappings."""
        return self._site_tag_manager.reset_tag_mappings()
