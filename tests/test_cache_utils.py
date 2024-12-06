import unittest
from unittest.mock import patch
from plex_playlist_creator.cache_utils import get_cache_directory

class TestCacheUtils(unittest.TestCase):

    @patch("os.name", "nt")
    @patch("os.getenv", return_value="AppData\\Local\\red-plex")
    def test_get_cache_directory_windows(self, mock_getenv):
        cache_dir = get_cache_directory()
        self.assertIn("AppData\\Local\\red-plex", cache_dir)

    @patch("os.uname")
    def test_get_cache_directory_macos(self, mock_uname):
        mock_uname.return_value.sysname = "Darwin"
        cache_dir = get_cache_directory()
        self.assertIn("Library/Caches/red-plex", cache_dir)

    @patch("os.uname")
    def test_get_cache_directory_linux(self, mock_uname):
        mock_uname.return_value.sysname = "Linux"
        cache_dir = get_cache_directory()
        self.assertIn(".cache/red-plex", cache_dir)
