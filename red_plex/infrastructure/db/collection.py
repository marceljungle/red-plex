"""Collection database operations for collage and bookmark collections."""

from typing import List, Optional, Set

from red_plex.domain.models import Collection, TorrentGroup
from red_plex.infrastructure.logger.logger import logger


class CollectionDatabaseManager:
    """Manages collection-related database operations."""

    def __init__(self, conn):
        self.conn = conn

    def insert_or_update_collage_collection(self, coll: Collection) -> None:
        """
        Insert or update a collage-based collection, along with its torrent groups.
        We'll do an upsert in collage_collections, then remove all old group_ids
        from collection_torrent_groups for that rating_key, and re-insert them.
        """
        logger.debug("Inserting/updating collage collection with rating_key %s", coll.id)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO collage_collections(rating_key, name, site, external_id)
            VALUES (?, ?, ?, ?)
            """,
            (coll.id, coll.name, coll.site, coll.external_id)
        )
        # Remove old group_ids for that rating_key
        self.conn.execute(
            "DELETE FROM collection_torrent_groups WHERE rating_key = ?",
            (coll.id,)
        )
        # Insert new group_ids
        if coll.torrent_groups:
            group_data = [(coll.id, tg.id) for tg in coll.torrent_groups]
            self.conn.executemany(
                "INSERT INTO collection_torrent_groups(rating_key, group_id) VALUES(?, ?)",
                group_data
            )
        self.conn.commit()

    def merge_torrent_groups_for_collage_collection(self, rating_key: str,
                                                    new_group_ids: Set[int]) -> None:
        """
        Merges a new set of torrent group IDs with the existing ones for a collage collection.

        This method fetches the current torrent groups for a given collection,
        merges them with the new set of group IDs provided, and updates the
        database with the combined list, ensuring no duplicates.

        Args:
            rating_key: The ID of the collage collection to update.
            new_group_ids: A set of new torrent group IDs to merge.
        """
        logger.debug(
            "Merging torrent groups for collage collection with rating_key %s",
            rating_key
        )

        # First, ensure the collage collection exists.
        cur = self.conn.cursor()
        cur.execute(
            "SELECT 1 FROM collage_collections WHERE rating_key = ?", (rating_key,)
        )
        if not cur.fetchone():
            logger.warning(
                "Attempted to merge torrent groups for a non-existent collage collection: %s",
                rating_key
            )
            return

        # Get existing group IDs and form a merged set to handle duplicates.
        existing_group_ids = set(self._get_torrent_group_ids_for(rating_key))
        merged_group_ids = existing_group_ids.union(new_group_ids)

        # If there's no change, we can skip the database write.
        if merged_group_ids == existing_group_ids:
            logger.debug(
                "No new torrent groups to add for rating_key %s. Skipping update.",
                rating_key
            )
            return

        # Use a transaction to perform the delete and bulk insert atomically.
        try:
            # Remove all old group_ids for the rating_key
            self.conn.execute(
                "DELETE FROM collection_torrent_groups WHERE rating_key = ?",
                (rating_key,)
            )

            # Insert the new merged set of group_ids
            if merged_group_ids:
                data_to_insert = [(rating_key, group_id) for group_id in merged_group_ids]
                self.conn.executemany(
                    "INSERT INTO collection_torrent_groups(rating_key, group_id) VALUES(?, ?)",
                    data_to_insert
                )

            self.conn.commit()
            logger.debug(
                "Successfully merged and updated torrent groups for rating_key %s. "
                "Total groups: %d",
                rating_key,
                len(merged_group_ids)
            )
        except self.conn.Error as e:
            self.conn.rollback()
            logger.error(
                "Database error while merging torrent groups for rating_key %s: %s",
                rating_key,
                e
            )
            raise e

    def get_collage_collection(self, rating_key: str) -> Optional[Collection]:
        """
        Retrieve a single collage-based collection (and associated group_ids) by rating_key.
        Returns a Collection or None if not found.
        """
        cur = self.conn.cursor()
        # Get collage collection fields
        cur.execute(
            """
            SELECT rating_key, name, site, external_id
            FROM collage_collections
            WHERE rating_key = ?
            """,
            (rating_key,)
        )
        row = cur.fetchone()
        if not row:
            return None
        rating_key_val, name, site, external_id = row
        # Get associated group_ids
        group_ids = self._get_torrent_group_ids_for(rating_key_val)
        return Collection(
            id=rating_key_val,
            external_id=external_id,
            name=name,
            torrent_groups=[TorrentGroup(id=gid) for gid in group_ids],
            site=site
        )

    def get_all_collage_collections(self) -> List[Collection]:
        """
        Retrieve all collage-based collections from the DB,
        along with their torrent groups.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT rating_key, name, site, external_id FROM collage_collections")
        rows = cur.fetchall()
        collections = []
        for (rk, name, site, external_id) in rows:
            group_ids = self._get_torrent_group_ids_for(rk)
            collections.append(Collection(
                id=rk,
                external_id=external_id,
                name=name,
                torrent_groups=[TorrentGroup(id=gid) for gid in group_ids],
                site=site
            ))
        return collections

    def delete_collage_collection(self, rating_key: str) -> None:
        """
        Delete a collage-based collection and associated torrent group mappings.
        """
        logger.debug("Deleting collage collection with rating_key %s", rating_key)
        self.conn.execute(
            "DELETE FROM collage_collections WHERE rating_key = ?",
            (rating_key,)
        )
        self.conn.execute(
            "DELETE FROM collection_torrent_groups WHERE rating_key = ?",
            (rating_key,)
        )
        self.conn.commit()

    def reset_collage_collections(self):
        """
        Deletes all records from 'collage_collections' and
        their associated rows in 'collection_torrent_groups'.
        """
        logger.info("Resetting collage collections (deleting all rows in 'collage_collections').")
        self.conn.execute("DELETE FROM collage_collections")
        logger.info("Removing associated torrent groups for collage collections.")
        self.conn.execute("""
            DELETE FROM collection_torrent_groups
            WHERE rating_key NOT IN (SELECT rating_key FROM bookmark_collections)
        """)

        self.conn.commit()

    def insert_or_update_bookmark_collection(self, coll: Collection) -> None:
        """
        Insert or update a bookmark-based collection (in bookmark_collections),
        then remove all old group_ids from 'collection_torrent_groups' for that rating_key
        and re-insert them.
        """
        logger.debug("Inserting/updating bookmark collection with rating_key %s", coll.id)
        self.conn.execute(
            """
            INSERT OR REPLACE INTO bookmark_collections(rating_key, site)
            VALUES (?, ?)
            """,
            (coll.id, coll.site)
        )
        # Remove old group_ids for that rating_key
        self.conn.execute(
            "DELETE FROM collection_torrent_groups WHERE rating_key = ?",
            (coll.id,)
        )
        # Insert new group_ids
        if coll.torrent_groups:
            group_data = [(coll.id, tg.id) for tg in coll.torrent_groups]
            self.conn.executemany(
                "INSERT INTO collection_torrent_groups(rating_key, group_id) VALUES(?, ?)",
                group_data
            )
        self.conn.commit()

    def get_bookmark_collection(self, rating_key: str) -> Optional[Collection]:
        """
        Retrieve a single bookmark collection (plus group_ids) by rating_key.
        Returns a Collection or None if not found.
        """
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT rating_key, site
            FROM bookmark_collections
            WHERE rating_key = ?
            """,
            (rating_key,)
        )
        row = cur.fetchone()
        if not row:
            return None
        rating_key_val, site = row
        group_ids = self._get_torrent_group_ids_for(rating_key_val)
        # We can store the name as something like f"{site.upper()} Bookmarks"
        return Collection(
            id=rating_key_val,
            name=f"{site.upper()} Bookmarks",
            site=site,
            torrent_groups=[TorrentGroup(id=gid) for gid in group_ids]
        )

    def get_all_bookmark_collections(self) -> List[Collection]:
        """
        Retrieve all bookmark collections from the DB,
        along with their torrent groups.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT rating_key, site FROM bookmark_collections")
        rows = cur.fetchall()
        bookmarks = []
        for (rk, site) in rows:
            group_ids = self._get_torrent_group_ids_for(rk)
            bookmarks.append(Collection(
                id=rk,
                name=f"{site.upper()} Bookmarks",
                site=site,
                torrent_groups=[TorrentGroup(id=gid) for gid in group_ids]
            ))
        return bookmarks

    def delete_bookmark_collection(self, rating_key: str) -> None:
        """
        Delete a bookmark-based collection and associated torrent group mappings.
        """
        logger.debug("Deleting bookmark collection with rating_key %s", rating_key)
        self.conn.execute(
            "DELETE FROM bookmark_collections WHERE rating_key = ?",
            (rating_key,)
        )
        self.conn.execute(
            "DELETE FROM collection_torrent_groups WHERE rating_key = ?",
            (rating_key,)
        )
        self.conn.commit()

    def reset_bookmark_collections(self):
        """
        Deletes all records from 'bookmark_collections' and
        their associated rows in 'collection_torrent_groups'.
        """
        logger.info("Resetting bookmark collections (deleting all rows in 'bookmark_collections').")
        self.conn.execute("DELETE FROM bookmark_collections")
        logger.info("Removing associated torrent groups for bookmark collections.")
        self.conn.execute("""
            DELETE FROM collection_torrent_groups
            WHERE rating_key NOT IN (SELECT rating_key FROM collage_collections)
        """)

        self.conn.commit()

    def _get_torrent_group_ids_for(self, rating_key: str) -> List[int]:
        """
        Retrieve all group_ids for a given rating_key from collection_torrent_groups.
        """
        cur = self.conn.cursor()
        cur.execute(
            "SELECT group_id FROM collection_torrent_groups WHERE rating_key = ?",
            (rating_key,)
        )
        rows = cur.fetchall()
        return [row[0] for row in rows]
