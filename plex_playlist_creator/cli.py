"""Playlist creator class"""

import os
import subprocess
import yaml
import click
from plex_playlist_creator.config import (
    CONFIG_FILE_PATH,
    DEFAULT_CONFIG,
    load_config,
    save_config,
    ensure_config_exists
)
from plex_playlist_creator.plex_manager import PlexManager
from plex_playlist_creator.redacted_api import RedactedAPI
from plex_playlist_creator.album_cache import AlbumCache
from plex_playlist_creator.playlist_creator import PlaylistCreator
from plex_playlist_creator.logger import logger, configure_logger

@click.group()
def cli():
    """A CLI tool for creating Plex playlists from RED collages."""
    # Load configuration
    config_data = load_config()

    # Get log level from configuration, default to 'INFO' if not set
    log_level = config_data.get('LOG_LEVEL', 'INFO').upper()

    # Validate log level
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if log_level not in valid_log_levels:
        print(f"Invalid LOG_LEVEL '{log_level}' in configuration. Defaulting to 'INFO'.")
        log_level = 'INFO'

    # Configure logger
    configure_logger(log_level)


@cli.command()
@click.argument('collage_ids', nargs=-1)
def convert(collage_ids):
    """Create Plex playlists from given COLLAGE_IDS."""
    if not collage_ids:
        click.echo("Please provide at least one COLLAGE_ID.")
        return

    config_data = load_config()
    plex_token = config_data.get('PLEX_TOKEN')
    red_api_key = config_data.get('RED_API_KEY')
    plex_url = config_data.get('PLEX_URL', 'http://localhost:32400')
    section_name = config_data.get('SECTION_NAME', 'Music')

    if not plex_token or not red_api_key:
        logger.error('PLEX_TOKEN and RED_API_KEY must be set in the config file.')
        return

    # Initialize managers
    plex_manager = PlexManager(plex_url, plex_token, section_name)
    redacted_api = RedactedAPI(red_api_key)
    playlist_creator = PlaylistCreator(plex_manager, redacted_api)

    # Create playlists for each collage ID provided
    for collage_id in collage_ids:
        try:
            playlist_creator.create_playlist_from_collage(collage_id)
        except Exception as exc:  # pylint: disable=W0718
            logger.exception(
                'Failed to create playlist for collage %s: %s', collage_id, exc)


@cli.group()
def config():
    """View or edit configuration settings."""


@config.command('show')
def show_config():
    """Display the current configuration."""
    config_data = load_config()
    path_with_config = (
    "Configuration path: " + str(CONFIG_FILE_PATH) + "\n\n" +
    yaml.dump(config_data, default_flow_style=False))
    click.echo(path_with_config)


@config.command('edit')
def edit_config():
    """Open the configuration file in the default editor."""
    # Ensure the configuration file exists
    ensure_config_exists()

    # Default to 'nano' if EDITOR is not set
    editor = os.environ.get('EDITOR', 'notepad' if os.name == 'nt' else 'nano')
    click.echo(f"Opening config file at {CONFIG_FILE_PATH}...")
    subprocess.call([editor, CONFIG_FILE_PATH])


@config.command('reset')
def reset_config():
    """Reset the configuration to default values."""
    save_config(DEFAULT_CONFIG)
    click.echo(f"Configuration reset to default values at {CONFIG_FILE_PATH}")

@cli.group()
def cache():
    """Manage saved albums cache."""

@cache.command('show')
def show_cache():
    """Show the location of the cache file if it exists."""
    try:
        album_cache = AlbumCache()
        cache_file = album_cache.csv_file

        if os.path.exists(cache_file):
            click.echo(f"Cache file exists at: {os.path.abspath(cache_file)}")
        else:
            click.echo("Cache file does not exist.")
    except Exception as exc: # pylint: disable=W0718
        logger.exception('Failed to show cache: %s', exc)
        click.echo(f"An error occurred while showing the cache: {exc}")

@cache.command('reset')
def reset_cache():
    """Reset the saved albums cache."""
    try:
        album_cache = AlbumCache()
        album_cache.reset_cache()
        click.echo("Cache has been reset successfully.")
    except Exception as exc: # pylint: disable=W0718
        logger.exception('Failed to reset cache: %s', exc)
        click.echo(f"An error occurred while resetting the cache: {exc}")

if __name__ == '__main__':
    cli()
