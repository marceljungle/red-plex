"""Configuration class"""

import os

import yaml

from infrastructure.config.models import Configuration

# Determine the path to the user's config directory based on OS
home_dir = os.getenv('APPDATA') if os.name == 'nt' else os.path.expanduser('~/.config')
CONFIG_DIR = os.path.join(home_dir, 'red-plex')
CONFIG_FILE_PATH = os.path.join(CONFIG_DIR, 'config.yml')


def load_config() -> Configuration:
    """Load config from file (YAML), returning a Configuration object."""
    if not os.path.exists(CONFIG_FILE_PATH):
        cfg = Configuration.default()
        save_config(cfg)
        return cfg

    with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
        raw_dict = yaml.safe_load(f) or {}
        return Configuration.from_dict(raw_dict)


def save_config(cfg: Configuration) -> None:
    """Save the given Configuration to YAML."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
        yaml.dump(cfg.to_dict(), f, default_flow_style=False)


def ensure_config_exists():
    """Ensure the config file exists, creating it with default values if not."""
    if not os.path.exists(CONFIG_FILE_PATH):
        save_config(Configuration.default())
