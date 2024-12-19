"""Playlist creator CLI."""

import os
import subprocess
import yaml
import click
from pyrate_limiter import Rate, Duration
from src.infrastructure.config.config import (
    CONFIG_FILE_PATH,
    DEFAULT_CONFIG,
    load_config,
    save_config,
    ensure_config_exists
)
from src.infrastructure.plex.plex_manager import PlexManager
from src.infrastructure.rest.gazelle_api import GazelleAPI
from src.infrastructure.cache.album_cache import AlbumCache
from src.infrastructure.cache.collage_playlist_cache import CollagePlaylistCache
from src.infrastructure.cache.collage_collection_cache import CollageCollectionCache
from src.infrastructure.cache.bookmarks_playlist_cache import BookmarksPlaylistCache
from src.infrastructure.cache.bookmarks_collection_cache import BookmarksCollectionCache
from src.playlist_creator import PlaylistCreator
from src.collection_creator import CollectionCreator
from src.infrastructure.logger.logger import logger, configure_logger


def initialize_plex_manager():
    """Initialize PlexManager without populating cache."""
    config_data = load_config()
    plex_token = config_data.get('PLEX_TOKEN')
    plex_url = config_data.get('PLEX_URL', 'http://localhost:32400')
    section_name = config_data.get('SECTION_NAME', 'Music')

    if not plex_token:
        message = 'PLEX_TOKEN must be set in the config file.'
        logger.error(message)
        click.echo(message)
        return None

    return PlexManager(plex_url, plex_token, section_name)


def initialize_gazelle_api(site):
    """Initialize GazelleAPI for a given site."""
    config_data = load_config()
    site_config = config_data.get(site.upper())
    if not site_config or not site_config.get('API_KEY'):
        message = f'API_KEY for {site.upper()} must be set in the config file under {site.upper()}.'
        logger.error(message)
        click.echo(message)
        return None

    api_key = site_config.get('API_KEY')
    base_url = site_config.get('BASE_URL')
    rate_limit_config = site_config.get('RATE_LIMIT', {'calls': 10, 'seconds': 10})
    rate_limit = Rate(rate_limit_config['calls'], Duration.SECOND * rate_limit_config['seconds'])

    return GazelleAPI(base_url, api_key, rate_limit)


def initialize_playlist_creator(plex_manager, gazelle_api):
    """Initialize PlaylistCreator using existing plex_manager and gazelle_api."""
    return PlaylistCreator(plex_manager, gazelle_api)

def initialize_collection_creator(plex_manager, gazelle_api):
    """Initialize CollectionCreator using existing plex_manager and gazelle_api."""
    return CollectionCreator(plex_manager, gazelle_api)


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

# convert
@cli.group()
def convert():
    """Conversion methods."""

# convert playlist
@convert.command()
@click.argument('collage_ids', nargs=-1)
@click.option('--site', '-s', type=click.Choice(['red', 'ops']), required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
def playlist(collage_ids, site):
    """Create Plex playlists from given COLLAGE_IDS."""
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

    playlist_creator = initialize_playlist_creator(plex_manager, gazelle_api)

    for collage_id in collage_ids:
        try:
            playlist_creator.create_or_update_playlist_from_collage(
                collage_id, site=site)
        except Exception as exc:  # pylint: disable=W0718
            logger.exception(
                'Failed to create playlist for collage %s on site %s: %s',
                collage_id, site.upper(), exc)
            click.echo(
                f'Failed to create playlist for collage {collage_id} on site {site.upper()}: {exc}'
            )

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

    for collage_id in collage_ids:
        try:
            collection_creator.create_or_update_collection_from_collage(
                collage_id, site=site)
        except Exception as exc:  # pylint: disable=W0718
            logger.exception(
                'Failed to create collection for collage %s on site %s: %s',
                collage_id, site.upper(), exc)
            click.echo(
                f'Failed to create collection for collage\
                      {collage_id} on site {site.upper()}: {exc}'
            )

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

# playlists
@cli.group('playlists')
def playlists():
    """Manage playlists."""

# playlists cache
@playlists.group('cache')
def playlists_cache():
    """Manage playlist cache."""

# playlists cache show
@playlists_cache.command('show')
def show_playlist_cache():
    """Shows the location of the playlist cache file if it exists."""
    try:
        playlist_cache = CollagePlaylistCache()
        cache_file = playlist_cache.csv_file

        if os.path.exists(cache_file):
            click.echo(f"Playlist cache file exists at: {os.path.abspath(cache_file)}")
        else:
            click.echo("Playlist cache file does not exist.")
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to show playlist cache: %s', exc)
        click.echo(f"An error occurred while showing the playlist cache: {exc}")

# playlists cache reset
@playlists_cache.command('reset')
def reset_playlist_cache():
    """Resets the saved playlist cache."""
    if click.confirm('Are you sure you want to reset the playlist cache?'):
        try:
            playlist_cache = CollagePlaylistCache()
            playlist_cache.reset_cache()
            click.echo("Playlist cache has been reset successfully.")
        except Exception as exc:  # pylint: disable=W0718
            logger.exception('Failed to reset playlist cache: %s', exc)
            click.echo(f"An error occurred while resetting the playlist cache: {exc}")

# playlists update
@playlists.command('update')
def update_playlists():
    """Synchronize all cached playlists with their source collages."""
    try:
        pc = CollagePlaylistCache()
        all_playlists = pc.get_all_playlists()

        if not all_playlists:
            click.echo("No playlists found in the cache.")
            return

        # Initialize PlexManager once, populate its cache once
        plex_manager = initialize_plex_manager()
        if not plex_manager:
            return
        plex_manager.populate_album_cache()

        # Loop through playlists
        for pl in all_playlists:
            site = pl['site']
            collage_id = pl['collage_id']
            playlist_name = pl['playlist_name']

            gazelle_api = initialize_gazelle_api(site)
            if not gazelle_api:
                click.echo(f"Skipping playlist '{playlist_name}' due to initialization issues.")
                continue

            playlist_creator = initialize_playlist_creator(plex_manager, gazelle_api)

            click.echo(
                f"Updating playlist '{playlist_name}' (Collage ID: {collage_id}, Site: {site})...")
            playlist_creator.create_or_update_playlist_from_collage(
                collage_id, site=site, force_update=True)

        click.echo("All cached playlists have been updated.")
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update cached playlists: %s', exc)
        click.echo(f"An error occurred while updating cached playlists: {exc}")

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

        # Loop through playlists
        for coll in all_collages:
            site = coll['site']
            collage_id = coll['collage_id']
            collection_name = coll['collection_name']

            gazelle_api = initialize_gazelle_api(site)
            if not gazelle_api:
                click.echo(f"Skipping collection '{collection_name}' due to initialization issues.")
                continue

            collection_creator = initialize_collection_creator(plex_manager, gazelle_api)

            click.echo(
                f"Updating collection '{collection_name}'\
                     (Collage ID: {collage_id}, Site: {site})...")
            collection_creator.create_or_update_collection_from_collage(
                collage_id, site=site, force_update=True)

        click.echo("All cached collections have been updated.")
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update cached collections: %s', exc)
        click.echo(f"An error occurred while updating cached collections: {exc}")

# bookmarks
@cli.group()
def bookmarks():
    """Manage playlists based on your site bookmarks."""

# bookmarks update
@bookmarks.group('update')
def update_bookmarks():
    """Update playlists/collections based on your site bookmarks."""

# bookmarks update playlist
@update_bookmarks.command('playlist')
def update_bookmarks_playlist():
    """Synchronize all cached bookmarks with their source collages."""
    try:
        pc = BookmarksPlaylistCache()
        all_bookmarks = pc.get_all_bookmarks()

        if not all_bookmarks:
            click.echo("No bookmarks found in the cache.")
            return

        plex_manager = initialize_plex_manager()
        if not plex_manager:
            return
        plex_manager.populate_album_cache()

        # Loop through bookmarks
        for bookmrk in all_bookmarks:
            site = bookmrk['site']

            gazelle_api = initialize_gazelle_api(site)
            if not gazelle_api:
                click.echo(f"Skipping '{site.upper()}' bookmarks due to initialization issues.")
                continue
            site_bookmarks = gazelle_api.get_bookmarks()

            playlist_creator = initialize_playlist_creator(plex_manager, gazelle_api)

            click.echo(
                f"Updating '{site.upper()}' bookmarks...")
            playlist_creator.create_or_update_playlist_from_bookmarks(
                site_bookmarks, site, force_update=True)

        click.echo("All cached playlists have been updated.")
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update cached playlists: %s', exc)
        click.echo(f"An error occurred while updating cached playlists: {exc}")

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

        # Loop through bookmarks
        for bookmrk in all_bookmarks:
            site = bookmrk['site']

            gazelle_api = initialize_gazelle_api(site)
            if not gazelle_api:
                click.echo(f"Skipping '{site.upper()}' bookmarks due to initialization issues.")
                continue
            site_bookmarks = gazelle_api.get_bookmarks()

            collection_creator = initialize_collection_creator(plex_manager, gazelle_api)

            click.echo(
                f"Updating '{site.upper()}' bookmarks...")
            collection_creator.create_or_update_collection_from_bookmarks(
                site_bookmarks, site, force_update=True)

        click.echo("All cached collections have been updated.")
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update cached collections: %s', exc)
        click.echo(f"An error occurred while updating cached collections: {exc}")

# bookmarks create
@bookmarks.group('create')
def create():
    """Create playlists/collections based on your site bookmarks."""

# bookmarks create playlist
@create.command('playlist')
@click.option('--site', '-s', type=click.Choice(['red', 'ops']), required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
def create_playlist_from_bookmarks(site):
    """Create a Plex playlist based on your site bookmarks."""
    plex_manager = initialize_plex_manager()
    if not plex_manager:
        return
    plex_manager.populate_album_cache()

    gazelle_api = initialize_gazelle_api(site)
    if not gazelle_api:
        return

    playlist_creator = initialize_playlist_creator(plex_manager, gazelle_api)

    try:
        bookmarks_data = gazelle_api.get_bookmarks()
        playlist_creator.create_or_update_playlist_from_bookmarks(bookmarks_data, site.upper())
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to create playlist from bookmarks on site %s: %s',
                         site.upper(), exc)
        click.echo(f'Failed to create playlist from bookmarks on site {site.upper()}: {exc}')

# bookmarks create collection
@create.command('collection')
@click.option('--site', '-s', type=click.Choice(['red', 'ops']), required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
def create_collection_from_bookmarks(site):
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
        bookmarks_data = gazelle_api.get_bookmarks()
        collection_creator.create_or_update_collection_from_bookmarks(bookmarks_data, site.upper())
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to create collection from bookmarks on site %s: %s',
                         site.upper(), exc)
        click.echo(f'Failed to create collection from bookmarks on site {site.upper()}: {exc}')

# bookmarks cache
@bookmarks.group('cache')
def bookmarks_cache():
    """Manage bookmarks cache."""

# bookmarks cache playlist
@bookmarks_cache.group('playlist')
def bookmarks_cache_playlist():
    """Manage playlist bookmarks cache."""

# bookmarks cache playlist show
@bookmarks_cache_playlist.command('show')
def show_bookmarks_cache_playlist():
    """Shows the location of the bookmarks cache file if it exists."""
    try:
        bookmarks_cache_manager = BookmarksPlaylistCache()
        cache_file = bookmarks_cache_manager.csv_file

        if os.path.exists(cache_file):
            click.echo(f"Playlist bookmarks cache file exists at: {os.path.abspath(cache_file)}")
        else:
            click.echo("Playlist bookmarks cache file does not exist.")
    except Exception as exc: # pylint: disable=W0718
        logger.exception('Failed to show the playlist bookmarks cache: %s', exc)
        click.echo(f"An error occurred while showing the playlist bookmarks cache: {exc}")

# bookmarks cache playlist reset
@bookmarks_cache_playlist.command('reset')
def reset_bookmarks_cache_playlist():
    """Resets the saved bookmarks cache."""
    if click.confirm('Are you sure you want to reset the playlist bookmarks cache?'):
        try:
            bookmarks_cache_manager = BookmarksPlaylistCache()
            bookmarks_cache_manager.reset_cache()
            click.echo("Playlist bookmarks cache has been reset successfully.")
        except Exception as exc: # pylint: disable=W0718
            logger.exception('Failed to reset playlist bookmarks cache: %s', exc)
            click.echo(f"An error occurred while resetting the playlist bookmarks cache: {exc}")

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
