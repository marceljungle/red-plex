"""Tests for the cache_utils module."""

import unittest
from unittest.mock import patch
from src.infrastructure.cache.utils.cache_utils import get_cache_directory

class TestCacheUtils(unittest.TestCase):
    """Test cases for the cache_utils module."""

    @patch("os.name", "nt")
    @patch("os.getenv", return_value="AppData\\Local\\red-plex")
    def test_get_cache_directory_windows(self, _):
        """Test get_cache_directory on Windows."""
        cache_dir = get_cache_directory()
        self.assertIn("AppData\\Local\\red-plex", cache_dir)

    @patch("os.uname")
    def test_get_cache_directory_macos(self, mock_uname):
        """Test get_cache_directory on macOS."""
        mock_uname.return_value.sysname = "Darwin"
        cache_dir = get_cache_directory()
        self.assertIn("Library/Caches/red-plex", cache_dir)

    @patch("os.uname")
    def test_get_cache_directory_linux(self, mock_uname):
        """Test get_cache_directory on Linux."""
        mock_uname.return_value.sysname = "Linux"
        cache_dir = get_cache_directory()
        self.assertIn(".cache/red-plex", cache_dir)

if __name__ == '__main__':
    unittest.main()
