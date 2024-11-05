import click
import os
import subprocess
import yaml
from plex_playlist_creator.config import (
    CONFIG_FILE_PATH,
    DEFAULT_CONFIG,
    load_config,
    save_config,
)
from plex_playlist_creator.plex_manager import PlexManager
from plex_playlist_creator.redacted_api import RedactedAPI
from plex_playlist_creator.playlist_creator import PlaylistCreator
from plex_playlist_creator.logger import logger

@click.group()
def cli():
    """A CLI tool for creating Plex playlists from RED collages."""
    pass

@cli.command()
@click.argument('collage_ids', nargs=-1)
def convert(collage_ids):
    """Create Plex playlists from given COLLAGE_IDS."""
    if not collage_ids:
        click.echo("Please provide at least one COLLAGE_ID.")
        return

    config = load_config()
    plex_token = config.get('PLEX_TOKEN')
    red_api_key = config.get('RED_API_KEY')
    plex_url = config.get('PLEX_URL', 'http://localhost:32400')
    section_name = config.get('SECTION_NAME', 'Music')

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
        except Exception as e:
            logger.exception(f'Failed to create playlist for collage {collage_id}: {e}')

@cli.group()
def config():
    """View or edit configuration settings."""
    pass

@config.command('show')
def show_config():
    """Display the current configuration."""
    config = load_config()
    click.echo(yaml.dump(config, default_flow_style=False))

@config.command('edit')
def edit_config():
    """Open the configuration file in the default editor."""
    editor = os.environ.get('EDITOR', 'nano')  # Default to 'nano' if EDITOR is not set
    click.echo(f"Opening config file at {CONFIG_FILE_PATH}...")
    subprocess.call([editor, CONFIG_FILE_PATH])

@config.command('reset')
def reset_config():
    """Reset the configuration to default values."""
    save_config(DEFAULT_CONFIG)
    click.echo(f"Configuration reset to default values at {CONFIG_FILE_PATH}")

if __name__ == '__main__':
    cli()