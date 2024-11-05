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
from plex_playlist_creator.playlist_creator import PlaylistCreator
from plex_playlist_creator.logger import logger


@click.group()
def cli():
    """A CLI tool for creating Plex playlists from RED collages."""


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
def config_group():
    """View or edit configuration settings."""


@config_group.command('show')
def show_config():
    """Display the current configuration."""
    config_data = load_config()
    click.echo(yaml.dump(config_data, default_flow_style=False))


@config_group.command('edit')
def edit_config():
    """Open the configuration file in the default editor."""
    # Ensure the configuration file exists
    ensure_config_exists()

    # Default to 'nano' if EDITOR is not set
    editor = os.environ.get('EDITOR', 'nano')
    click.echo(f"Opening config file at {CONFIG_FILE_PATH}...")
    subprocess.call([editor, CONFIG_FILE_PATH])


@config_group.command('reset')
def reset_config():
    """Reset the configuration to default values."""
    save_config(DEFAULT_CONFIG)
    click.echo(f"Configuration reset to default values at {CONFIG_FILE_PATH}")


if __name__ == '__main__':
    cli()
