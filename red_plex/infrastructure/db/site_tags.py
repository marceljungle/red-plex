"""Site tag mapping database operations."""

from typing import List

from red_plex.infrastructure.logger.logger import logger


class SiteTagDatabaseManager:
    """Manages site tag mapping database operations."""

    def __init__(self, conn):
        self.conn = conn

    def insert_site_tag_mapping(self, rating_key: str,
                                group_id: int,
                                site: str,
                                tags: List[str]) -> None:
        """
        Insert or update a site tag mapping with its associated tags.
        """
        logger.debug("Inserting site tag mapping: rating_key=%s, group_id=%s, site=%s",
                     rating_key, group_id, site)

        with self.conn:
            # Insert or ignore the mapping
            cur = self.conn.cursor()
            cur.execute("""
                INSERT OR IGNORE INTO rating_key_group_id_mappings(rating_key, group_id, site) 
                VALUES (?, ?, ?)
            """, (rating_key, group_id, site))

            # Get the mapping ID
            cur.execute("""
                SELECT id FROM rating_key_group_id_mappings 
                WHERE rating_key = ? AND group_id = ? AND site = ?
            """, (rating_key, group_id, site))
            mapping_id = cur.fetchone()[0]

            # Delete existing tag associations for this mapping
            cur.execute("DELETE FROM mapping_tags WHERE mapping_id = ?", (mapping_id,))

            if tags:
                # Insert tags if they don't exist
                self.conn.executemany(
                    "INSERT OR IGNORE INTO site_tags(tag_name) VALUES (?)",
                    [(tag,) for tag in tags]
                )

                # Get tag IDs
                tag_ids = dict(cur.execute(
                    f"SELECT tag_name, id FROM site_tags WHERE tag_name IN "
                    f"({','.join('?' * len(tags))})",
                    tags
                ))

                # Insert tag associations
                self.conn.executemany(
                    "INSERT INTO mapping_tags(mapping_id, tag_id) VALUES (?, ?)",
                    [(mapping_id, tag_ids[tag]) for tag in tags]
                )

    def get_rating_keys_by_tags(self, tags: List[str]) -> List[str]:
        """
        Get rating keys that have mappings containing all specified tags.
        """
        if not tags:
            return []

        cur = self.conn.cursor()

        placeholders = ','.join('?' * len(tags))
        cur.execute(f"""
            SELECT DISTINCT stm.rating_key
            FROM rating_key_group_id_mappings stm
            JOIN mapping_tags mt ON stm.id = mt.mapping_id
            JOIN site_tags st ON mt.tag_id = st.id
            WHERE st.tag_name IN ({placeholders})
            GROUP BY stm.rating_key
            HAVING COUNT(DISTINCT st.tag_name) = ?
        """, tags + [len(tags)])

        return [row[0] for row in cur.fetchall()]

    def get_unscanned_albums(self) -> List[str]:
        """
        Get rating keys from albums table that are not present in
        rating_key_group_id_mappings, ordered by most recently added.
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT a.album_id
            FROM albums a
            LEFT JOIN rating_key_group_id_mappings stm ON a.album_id = stm.rating_key
            WHERE stm.rating_key IS NULL
            ORDER BY a.added_at DESC
        """)

        return [row[0] for row in cur.fetchall()]

    def get_site_tags_stats(self):
        """
        Get statistics about site tag mappings.
        Returns a tuple of (mapped_albums, total_tags, total_mappings).
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT COUNT(DISTINCT stm.rating_key) as mapped_albums,
                   COUNT(DISTINCT st.tag_name) as total_tags,
                   COUNT(stm.id) as total_mappings
            FROM rating_key_group_id_mappings stm
            LEFT JOIN mapping_tags mt ON stm.id = mt.mapping_id
            LEFT JOIN site_tags st ON mt.tag_id = st.id
        """)
        stats = cur.fetchone()
        return (stats[0] or 0, stats[1] or 0, stats[2] or 0)

    def get_recent_site_tag_mappings(self, limit: int = 20):
        """
        Get recent site tag mappings for display.
        Returns a list of tuples (rating_key, group_id, site, tags).
        """
        cur = self.conn.cursor()
        cur.execute("""
            SELECT stm.rating_key, stm.group_id, stm.site, 
                   GROUP_CONCAT(st.tag_name, ', ') as tags
            FROM rating_key_group_id_mappings stm
            LEFT JOIN mapping_tags mt ON stm.id = mt.mapping_id
            LEFT JOIN site_tags st ON mt.tag_id = st.id
            GROUP BY stm.id
            ORDER BY stm.id DESC
            LIMIT ?
        """, (limit,))
        return cur.fetchall()

    def get_group_ids_by_rating_keys(self, rating_keys: List[str], site: str) -> List[str]:
        """
        Get group IDs for given rating keys from a specific site.
        
        Args:
            rating_keys: List of rating keys to look up
            site: Site to filter by
            
        Returns:
            List of group IDs as strings
        """
        if not rating_keys:
            return []

        cur = self.conn.cursor()
        placeholders = ','.join('?' * len(rating_keys))
        cur.execute(f"""
            SELECT DISTINCT group_id
            FROM rating_key_group_id_mappings
            WHERE rating_key IN ({placeholders}) AND site = ?
        """, rating_keys + [site])

        return [str(row[0]) for row in cur.fetchall()]

    def reset_tag_mappings(self):
        """
        Reset site tag mappings.
        """
        logger.info("Resetting site tag mappings")

        with self.conn:
            self.conn.execute("DELETE FROM mapping_tags")
            self.conn.execute("DELETE FROM rating_key_group_id_mappings")
            self.conn.execute("DELETE FROM site_tags")
