"""Configuration class"""

import os
import yaml

# Determine the path to the user's config directory
CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.config', 'red-plex')
CONFIG_FILE_PATH = os.path.join(CONFIG_DIR, 'config.yml')

# Default configuration values
DEFAULT_CONFIG = {
    'PLEX_URL': 'http://localhost:32400',
    'PLEX_TOKEN': '',
    'SECTION_NAME': 'Music',
    'RED_API_KEY': ''
}

def load_config():
    """Load configuration from the config.yml file."""
    if not os.path.exists(CONFIG_FILE_PATH):
        # If the config file doesn't exist, create it with default values
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

    with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as config_file:
        config = yaml.safe_load(config_file)
        if not config:
            config = DEFAULT_CONFIG
    return config

def save_config(config):
    """Save configuration to the config.yml file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as config_file:
        yaml.dump(config, config_file, default_flow_style=False)

def ensure_config_exists():
    """Ensure the configuration file exists, creating it with default values if it doesn't."""
    if not os.path.exists(CONFIG_FILE_PATH):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        save_config(DEFAULT_CONFIG)
