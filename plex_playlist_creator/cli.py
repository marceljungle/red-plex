"""Playlist creator CLI."""

import os
import subprocess
import yaml
import click
from pyrate_limiter import Rate, Duration
from plex_playlist_creator.config import (
    CONFIG_FILE_PATH,
    DEFAULT_CONFIG,
    load_config,
    save_config,
    ensure_config_exists
)
from plex_playlist_creator.plex_manager import PlexManager
from plex_playlist_creator.gazelle_api import GazelleAPI
from plex_playlist_creator.album_cache import AlbumCache
from plex_playlist_creator.playlist_cache import PlaylistCache
from plex_playlist_creator.playlist_creator import PlaylistCreator
from plex_playlist_creator.logger import logger, configure_logger


def initialize_managers(site):
    """Helper function to initialize managers."""
    config_data = load_config()
    plex_token = config_data.get('PLEX_TOKEN')
    plex_url = config_data.get('PLEX_URL', 'http://localhost:32400')
    section_name = config_data.get('SECTION_NAME', 'Music')

    if not plex_token:
        message = 'PLEX_TOKEN must be set in the config file.'
        logger.error(message)
        click.echo(message)
        return None, None, None

    # Get site-specific configuration
    site_config = config_data.get(site.upper())
    if not site_config or not site_config.get('API_KEY'):
        message = f'API_KEY for {site.upper()} must be set in the config file under {site.upper()}.'
        logger.error(message)
        click.echo(message)
        return None, None, None

    api_key = site_config.get('API_KEY')
    base_url = site_config.get('BASE_URL')
    rate_limit_config = site_config.get('RATE_LIMIT', {'calls': 10, 'seconds': 10})
    rate_limit = Rate(rate_limit_config['calls'], Duration.SECOND * rate_limit_config['seconds'])

    plex_manager = PlexManager(plex_url, plex_token, section_name)
    gazelle_api = GazelleAPI(base_url, api_key, rate_limit)
    playlist_creator = PlaylistCreator(plex_manager, gazelle_api)

    return plex_manager, gazelle_api, playlist_creator


@click.group()
def cli():
    """A CLI tool for creating Plex playlists from RED and OPS collages."""
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
@click.option('--site', '-s', type=click.Choice(['red', 'ops']), required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
def convert(collage_ids, site):
    """Create Plex playlists from given COLLAGE_IDS."""
    if not collage_ids:
        click.echo("Please provide at least one COLLAGE_ID.")
        return

    plex_manager, gazelle_api, playlist_creator = initialize_managers(site)
    if not all([plex_manager, gazelle_api, playlist_creator]):
        return

    # Create playlists for each collage ID provided
    for collage_id in collage_ids:
        try:
            playlist_creator.create_playlist_from_collage(collage_id)
        except Exception as exc:  # pylint: disable=W0718
            logger.exception(
                'Failed to create playlist for collage %s on site %s: %s',
                collage_id, site.upper(), exc)
            click.echo(
                f'Failed to create playlist for collage {collage_id} on site {site.upper()}: {exc}'
            )


@cli.group()
def config():
    """View or edit configuration settings."""


@config.command('show')
def show_config():
    """Display the current configuration."""
    config_data = load_config()
    path_with_config = (
        f"Configuration path: {CONFIG_FILE_PATH}\n\n" +
        yaml.dump(config_data, default_flow_style=False)
    )
    click.echo(path_with_config)


@config.command('edit')
def edit_config():
    """Open the configuration file in the default editor."""
    # Ensure the configuration file exists
    ensure_config_exists()

    # Default to 'nano' if EDITOR is not set
    editor = os.environ.get('EDITOR', 'notepad' if os.name == 'nt' else 'nano')
    click.echo(f"Opening config file at {CONFIG_FILE_PATH}...")
    try:
        subprocess.call([editor, CONFIG_FILE_PATH])
    except FileNotFoundError:
        message = f"Editor '{editor}' not found. \
            Please set the EDITOR environment variable to a valid editor."
        logger.error(message)
        click.echo(message)
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to open editor: %s', exc)
        click.echo(f"An error occurred while opening the editor: {exc}")


@config.command('reset')
def reset_config():
    """Reset the configuration to default values."""
    if click.confirm('Are you sure you want to reset the configuration to default values?'):
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
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to show cache: %s', exc)
        click.echo(f"An error occurred while showing the cache: {exc}")


@cache.command('reset')
def reset_cache():
    """Reset the saved albums cache."""
    if click.confirm('Are you sure you want to reset the cache?'):
        try:
            album_cache = AlbumCache()
            album_cache.reset_cache()
            click.echo("Cache has been reset successfully.")
        except Exception as exc:  # pylint: disable=W0718
            logger.exception('Failed to reset cache: %s', exc)
            click.echo(f"An error occurred while resetting the cache: {exc}")


@cache.command('update')
def update_cache():
    """Update the saved albums cache with the latest albums from Plex."""
    try:
        # Load configuration
        config_data = load_config()
        plex_token = config_data.get('PLEX_TOKEN')
        plex_url = config_data.get('PLEX_URL', 'http://localhost:32400')
        section_name = config_data.get('SECTION_NAME', 'Music')

        if not plex_token:
            message = 'PLEX_TOKEN must be set in the config file.'
            logger.error(message)
            click.echo(message)
            return

        # Initialize & update cache using PlexManager
        PlexManager(plex_url, plex_token, section_name)
        click.echo("Cache has been updated successfully.")
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update cache: %s', exc)
        click.echo(f"An error occurred while updating the cache: {exc}")


@cli.group('playlist-cache')
def playlist_cache():
    """Manage playlist cache."""


@playlist_cache.command('show')
def show_playlist_cache():
    """Shows the location of the playlist cache file if it exists."""
    try:
        # pylint: disable=redefined-outer-name
        playlist_cache = PlaylistCache()
        cache_file = playlist_cache.csv_file

        if os.path.exists(cache_file):
            click.echo(f"Playlist cache file exists at: {os.path.abspath(cache_file)}")
        else:
            click.echo("Playlist cache file does not exist.")
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to show playlist cache: %s', exc)
        click.echo(f"An error occurred while showing the playlist cache: {exc}")


@playlist_cache.command('reset')
def reset_playlist_cache():
    """Resets the saved playlist cache."""
    if click.confirm('Are you sure you want to reset the playlist cache?'):
        try:
            # pylint: disable=redefined-outer-name
            playlist_cache = PlaylistCache()
            playlist_cache.reset_cache()
            click.echo("Playlist cache has been reset successfully.")
        except Exception as exc:  # pylint: disable=W0718
            logger.exception('Failed to reset playlist cache: %s', exc)
            click.echo(f"An error occurred while resetting the playlist cache: {exc}")


@cli.group()
def bookmarks():
    """Manage playlists based on your site bookmarks."""


@bookmarks.command('create-playlist')
@click.option('--site', '-s', type=click.Choice(['red', 'ops']), required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
def create_playlist_from_bookmarks(site):
    """Create a Plex playlist based on your site bookmarks."""
    plex_manager, gazelle_api, playlist_creator = initialize_managers(site)
    if not all([plex_manager, gazelle_api, playlist_creator]):
        return

    try:
        bookmarks_data = gazelle_api.get_bookmarks()
        file_paths = gazelle_api.get_file_paths_from_bookmarks(bookmarks_data)
        playlist_creator.create_playlist_from_bookmarks(file_paths, site.upper())
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to create playlist from bookmarks on site %s: %s',
                         site.upper(), exc)
        click.echo(f'Failed to create playlist from bookmarks on site {site.upper()}: {exc}')


if __name__ == '__main__':
    configure_logger()
    cli()
