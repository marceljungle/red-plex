"""Base database functionality for LocalDatabase."""

import os
import sqlite3

from red_plex.infrastructure.db.utils.csv_to_db_migrator import CsvToDbMigrator


#pylint: disable=R0903
class BaseDatabaseManager:
    """Base database manager with connection and table creation functionality."""

    def __init__(self):
        self.db_path = self._get_database_directory()
        os.makedirs(self.db_path, exist_ok=True)
        db_file_path = os.path.join(self.db_path, 'red_plex.db')

        # If the database file doesn't exist, create and run migrations
        if not os.path.isfile(db_file_path):
            # Create a temp connection for initialization
            self.conn = sqlite3.connect(db_file_path)
            self.conn.execute("PRAGMA journal_mode=WAL;")
            # Migrate existing CSV data into the new DB
            # This can be removed in future releases
            migrator = CsvToDbMigrator(db_file_path=db_file_path)
            migrator.migrate_from_csv_to_db()
            self.conn.commit()
        else:
            self.conn = sqlite3.connect(db_file_path)
            self.conn.execute("PRAGMA journal_mode=WAL;")
        self._create_tables()

    def _create_tables(self):
        """Create necessary tables if they do not exist."""
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS albums (
          album_id TEXT PRIMARY KEY,
          name TEXT,
          path TEXT NOT NULL,
          added_at TEXT
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            artist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist_name TEXT NOT NULL UNIQUE
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS album_artists (
            album_id TEXT,
            artist_id INTEGER,
            PRIMARY KEY (album_id, artist_id),
            FOREIGN KEY (album_id) REFERENCES albums(album_id) ON DELETE CASCADE,
            FOREIGN KEY (artist_id) REFERENCES artists(artist_id) ON DELETE CASCADE
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS collage_collections (
          rating_key TEXT PRIMARY KEY,
          name TEXT,
          site TEXT,
          external_id TEXT
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS bookmark_collections (
          rating_key TEXT PRIMARY KEY,
          site TEXT
        );
        """)
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS collection_torrent_groups (
          rating_key TEXT,
          group_id INTEGER
        );
        """)

        # Tables for site tag mappings
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS rating_key_group_id_mappings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          rating_key TEXT NOT NULL,
          group_id INTEGER NOT NULL,
          site TEXT NOT NULL,
          UNIQUE(rating_key, group_id, site)
        );
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS site_tags (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tag_name TEXT NOT NULL UNIQUE
        );
        """)

        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS mapping_tags (
          mapping_id INTEGER,
          tag_id INTEGER,
          PRIMARY KEY (mapping_id, tag_id),
          FOREIGN KEY (mapping_id) REFERENCES rating_key_group_id_mappings(id) ON DELETE CASCADE,
          FOREIGN KEY (tag_id) REFERENCES site_tags(id) ON DELETE CASCADE
        );
        """)

        self.conn.execute("DROP TABLE IF EXISTS beets_mappings;")

    @staticmethod
    def _get_database_directory():
        """
        Return the directory path where the database file should live,
        based on each OS's convention for local application data.
        """
        if os.name == 'nt':  # Windows
            # Typically, LOCALAPPDATA or APPDATA for user-level application data
            return os.path.join(
                os.getenv('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local')),
                'red-plex'
            )
        try:
            if os.uname().sysname == 'Darwin':  # macOS

                # Commonly used for persistent data:
                return os.path.join(os.path.expanduser('~/Library/Application Support'), 'red-plex')
        except ImportError:
            pass

        # Linux / other Unix: use ~/.local/share/red-plex by XDG spec
        data_home = os.getenv('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        return os.path.join(data_home, 'red-plex')

    def close(self):
        """Close the database connection."""
        self.conn.close()
