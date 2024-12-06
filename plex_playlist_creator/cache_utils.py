import os

def get_cache_directory():
    """Return the cache directory path based on the OS."""
    if os.name == 'nt':  # Windows
        return os.path.join(os.getenv('LOCALAPPDATA', os.path.expanduser('~\\AppData\\Local')), 'red-plex')
    elif os.uname().sysname == 'Darwin':  # macOS
        return os.path.join(os.path.expanduser('~/Library/Caches'), 'red-plex')
    else:  # Linux and others
        return os.path.join(os.path.expanduser('~/.cache'), 'red-plex')

def ensure_directory_exists(directory):
    """Ensure that a directory exists, creating it if necessary."""
    os.makedirs(directory, exist_ok=True)
