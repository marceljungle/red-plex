"""Collection creator CLI."""

import os
import subprocess
import yaml
import click
from infrastructure.config.config import (
    CONFIG_FILE_PATH,
    DEFAULT_CONFIG,
    load_config,
    save_config,
    ensure_config_exists
)
from infrastructure.plex.plex_manager import PlexManager
from infrastructure.cache.album_cache import AlbumCache
from infrastructure.cache.collage_collection_cache import CollageCollectionCache
from infrastructure.cache.bookmarks_collection_cache import BookmarksCollectionCache
from infrastructure.plex.config import initialize_plex_manager
from infrastructure.rest.gazelle.config import initialize_gazelle_api
from infrastructure.services.config import initialize_collection_creator
from infrastructure.logger.logger import logger, configure_logger

@click.group()
def cli():
    """A CLI tool for creating Plex collections from RED and OPS collages."""
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

# convert
@cli.group()
def convert():
    """Conversion methods."""

# convert collection
@convert.command()
@click.argument('collage_ids', nargs=-1)
@click.option('--site', '-s', type=click.Choice(['red', 'ops']), required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
def collection(collage_ids, site):
    """Create Plex collections from given COLLAGE_IDS."""
    if not collage_ids:
        click.echo("Please provide at least one COLLAGE_ID.")
        return

    plex_manager = initialize_plex_manager()
    if not plex_manager:
        return

    # Populate album cache once after initializing plex_manager
    plex_manager.populate_album_cache()

    gazelle_api = initialize_gazelle_api(site)
    if not gazelle_api:
        return

    collection_creator = initialize_collection_creator(plex_manager, gazelle_api)
    collection_creator.create_collections_from_collages(site, collage_ids)

# config
@cli.group()
def config():
    """View or edit configuration settings."""

# config show
@config.command('show')
def show_config():
    """Display the current configuration."""
    config_data = load_config()
    path_with_config = (
        f"Configuration path: {CONFIG_FILE_PATH}\n\n" +
        yaml.dump(config_data, default_flow_style=False)
    )
    click.echo(path_with_config)

# config edit
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

# config reset
@config.command('reset')
def reset_config():
    """Reset the configuration to default values."""
    if click.confirm('Are you sure you want to reset the configuration to default values?'):
        save_config(DEFAULT_CONFIG)
        click.echo(f"Configuration reset to default values at {CONFIG_FILE_PATH}")

# album-cache
@cli.group()
def album_cache():
    """Manage saved albums cache."""

# album-cache show
@album_cache.command('show')
def show_cache():
    """Show the location of the cache file if it exists."""
    try:
        album_cache_instance = AlbumCache()
        cache_file = album_cache_instance.csv_file

        if os.path.exists(cache_file):
            click.echo(f"Cache file exists at: {os.path.abspath(cache_file)}")
        else:
            click.echo("Cache file does not exist.")
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to show cache: %s', exc)
        click.echo(f"An error occurred while showing the cache: {exc}")

# album-cache reset
@album_cache.command('reset')
def reset_cache():
    """Reset the saved albums cache."""
    if click.confirm('Are you sure you want to reset the cache?'):
        try:
            album_cache_instance = AlbumCache()
            album_cache_instance.reset_cache()
            click.echo("Cache has been reset successfully.")
        except Exception as exc:  # pylint: disable=W0718
            logger.exception('Failed to reset cache: %s', exc)
            click.echo(f"An error occurred while resetting the cache: {exc}")

# album-cache update
@album_cache.command('update')
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
        plex_manager = PlexManager(plex_url, plex_token, section_name)
        plex_manager.populate_album_cache()
        click.echo("Cache has been updated successfully.")
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update cache: %s', exc)
        click.echo(f"An error occurred while updating the cache: {exc}")

# collections
@cli.group('collections')
def collections():
    """Manage collections."""

# collections cache
@collections.group('cache')
def collections_cache():
    """Manage collections cache."""

# collections cache show
@collections_cache.command('show')
def show_collection_cache():
    """Shows the location of the collection cache file if it exists."""
    try:
        collection_cache = CollageCollectionCache()
        cache_file = collection_cache.csv_file

        if os.path.exists(cache_file):
            click.echo(f"Collection cache file exists at: {os.path.abspath(cache_file)}")
        else:
            click.echo("Collection cache file does not exist.")
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to show collection cache: %s', exc)
        click.echo(f"An error occurred while showing the collection cache: {exc}")

# collections cache reset
@collections_cache.command('reset')
def reset_collection_cache():
    """Resets the saved collection cache."""
    if click.confirm('Are you sure you want to reset the collection cache?'):
        try:
            collection_cache = CollageCollectionCache()
            collection_cache.reset_cache()
            click.echo("Collage collection cache has been reset successfully.")
        except Exception as exc:  # pylint: disable=W0718
            logger.exception('Failed to reset collage collection cache: %s', exc)
            click.echo(
                f"An error occurred while resetting the collage collection cache: {exc}")

# collections update
@collections.command('update')
def update_collections():
    """Synchronize all cached collections with their source collages."""
    try:
        ccc = CollageCollectionCache()
        all_collages = ccc.get_all_collections()

        if not all_collages:
            click.echo("No collages found in the cache.")
            return

        # Initialize PlexManager once, populate its cache once
        plex_manager = initialize_plex_manager()
        if not plex_manager:
            return
        plex_manager.populate_album_cache()

        collection_creator = initialize_collection_creator(plex_manager, None)
        collection_creator.update_collections_from_collages(all_collages, fetch_bookmarks=False)
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update cached collections: %s', exc)
        click.echo(f"An error occurred while updating cached collections: {exc}")

# bookmarks
@cli.group()
def bookmarks():
    """Manage collection based on your site bookmarks."""

# bookmarks update
@bookmarks.group('update')
def update_bookmarks():
    """Update collections based on your site bookmarks."""

# bookmarks update collection
@update_bookmarks.command('collection')
def update_bookmarks_collection():
    """Synchronize all cached bookmarks with their source collages."""
    try:
        ccc = BookmarksCollectionCache()
        all_bookmarks = ccc.get_all_bookmarks()

        if not all_bookmarks:
            click.echo("No bookmarks found in the cache.")
            return

        plex_manager = initialize_plex_manager()
        if not plex_manager:
            return
        plex_manager.populate_album_cache()

        collection_creator = initialize_collection_creator(plex_manager, None)
        collection_creator.update_collections_from_collages(all_bookmarks, fetch_bookmarks=True)

    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update cached bookmarks: %s', exc)
        click.echo(f"An error occurred while updating cached bookmarks: {exc}")

# bookmarks create
@bookmarks.group('create')
def create():
    """Create collections based on your site bookmarks."""

# bookmarks create collection
@create.command('collection')
@click.option('--site', '-s', type=click.Choice(['red', 'ops']), required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
def create_collection_from_bookmarks(site: str):
    """Create a Plex collection based on your site bookmarks."""
    plex_manager = initialize_plex_manager()
    if not plex_manager:
        return
    plex_manager.populate_album_cache()

    gazelle_api = initialize_gazelle_api(site)
    if not gazelle_api:
        return

    collection_creator = initialize_collection_creator(plex_manager, gazelle_api)

    try:
        collection_creator.create_collections_from_collages(site = site.upper(), fetch_bookmarks=True)
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to create collection from bookmarks on site %s: %s',
                         site.upper(), exc)
        click.echo(f'Failed to create collection from bookmarks on site {site.upper()}: {exc}')

# bookmarks cache
@bookmarks.group('cache')
def bookmarks_cache():
    """Manage bookmarks cache."""

 # bookmarks cache collection
@bookmarks_cache.group('collection')
def bookmarks_cache_collection():
    """Manage collection bookmarks cache."""

# bookmarks cache collection show
@bookmarks_cache_collection.command('show')
def show_bookmarks_cache_collection():
    """Shows the location of the bookmarks cache file if it exists."""
    try:
        bookmarks_cache_manager = BookmarksCollectionCache()
        cache_file = bookmarks_cache_manager.csv_file

        if os.path.exists(cache_file):
            click.echo(f"Collection bookmarks cache file exists at: {os.path.abspath(cache_file)}")
        else:
            click.echo("Collection bookmarks cache file does not exist.")
    except Exception as exc: # pylint: disable=W0718
        logger.exception('Failed to show collection bookmarks cache: %s', exc)
        click.echo(f"An error occurred while showing the collection bookmarks cache: {exc}")

# bookmarks cache collection reset
@bookmarks_cache_collection.command('reset')
def reset_bookmarks_cache_collection():
    """Resets the saved bookmarks cache."""
    if click.confirm('Are you sure you want to reset the collection bookmarks cache?'):
        try:
            bookmarks_cache_manager = BookmarksCollectionCache()
            bookmarks_cache_manager.reset_cache()
            click.echo("Collection bookmarks cache has been reset successfully.")
        except Exception as exc: # pylint: disable=W0718
            logger.exception('Failed to reset collection bookmarks cache: %s', exc)
            click.echo(f"An error occurred while resetting the collection bookmarks cache: {exc}")

if __name__ == '__main__':
    configure_logger()
    cli()
