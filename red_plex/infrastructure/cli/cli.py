"""Collection creator CLI."""
import os
import subprocess
from typing import List

import click
import yaml

from domain.models import Collection
from infrastructure.cache.album_cache import AlbumCache
from infrastructure.cache.bookmarks_collection_cache import BookmarksCollectionCache
from infrastructure.cache.collage_collection_cache import CollageCollectionCache
from infrastructure.config.config import (
    CONFIG_FILE_PATH,
    load_config,
    save_config,
    ensure_config_exists
)
from infrastructure.config.models import Configuration
from infrastructure.logger.logger import logger, configure_logger
from infrastructure.plex.plex_manager import PlexManager
from infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from use_case.create_collection.create_collection import CollectionCreator


@click.group()
def cli():
    """A CLI tool for creating Plex collections from RED and OPS collages."""


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
    """
    Create Plex collections from given COLLAGE_IDS.
    If the collection already exists, confirmation will be requested to update it.
    """
    if not collage_ids:
        click.echo("Please provide at least one COLLAGE_ID.")
        return

    plex_manager = PlexManager()
    if not plex_manager:
        return

    plex_manager.populate_album_cache()

    gazelle_api = GazelleAPI(site)
    if not gazelle_api:
        return

    collection_creator = CollectionCreator(plex_manager, gazelle_api)

    for collage_id in collage_ids:
        logger.info('Processing collage ID "%s"...', collage_id)
        # 1) First try, without forcing
        initial_result = collection_creator.create_or_update_collection_from_collage(
            collage_id=collage_id,
            site=site,
            fetch_bookmarks=False,
            force_update=False
        )

        if initial_result.response_status is False:
            # That means the collection exists but wasn't forced => ask user
            if click.confirm(
                    f'Collection "{initial_result.collection_data.name}" already exists. '
                    'Do you want to update it with new items?',
                    default=True
            ):
                # 2) If user says yes, do the forced call
                forced_result = collection_creator.create_or_update_collection_from_collage(
                    collage_id=collage_id,
                    site=site,
                    fetch_bookmarks=False,
                    force_update=True
                )
                # Now show forced_result
                if forced_result.response_status is True:
                    click.echo(
                        f'Collection for collage "{forced_result.collection_data.name}" '
                        f'was updated successfully with {len(forced_result.albums)} entries.'
                    )
                elif forced_result.response_status is None:
                    click.echo(f'No valid data found for collage "{collage_id}" when forced.')
                else:
                    # This shouldn't happen
                    click.echo('Something unexpected happened.')
            else:
                click.echo(f'Skipping collection update for '
                           f'"{initial_result.collection_data.name}".')

        elif initial_result.response_status is None:
            click.echo(f'No valid data found for collage "{collage_id}".')

        else:
            # response_status == True => successfully created/updated
            click.echo(
                f'Collection for collage "{initial_result.collection_data.name}" '
                f'created/updated successfully with {len(initial_result.albums)} entries.'
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
            yaml.dump(config_data.to_dict(), default_flow_style=False)
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
        save_config(Configuration.default())
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
        # Initialize & update cache using PlexManager
        plex_manager = PlexManager()
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
        plex_manager = PlexManager()
        if not plex_manager:
            return
        plex_manager.populate_album_cache()

        update_collections_from_collages(all_collages, plex_manager, fetch_bookmarks=False)
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update cached collections: %s', exc)
        click.echo(f"An error occurred while updating cached collections: {exc}")


# bookmarks
@cli.group()
def bookmarks():
    """Manage collection based on your site bookmarks."""


# bookmarks update
@bookmarks.command('update')
def update_bookmarks_collection():
    """Synchronize all cached bookmarks with their source collages."""
    try:
        ccc = BookmarksCollectionCache()
        all_bookmarks = ccc.get_all_bookmarks()

        if not all_bookmarks:
            click.echo("No bookmarks found in the cache.")
            return

        plex_manager = PlexManager()
        if not plex_manager:
            return
        plex_manager.populate_album_cache()

        update_collections_from_collages(all_bookmarks, plex_manager, fetch_bookmarks=True)

    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update cached bookmarks: %s', exc)
        click.echo(f"An error occurred while updating cached bookmarks: {exc}")


# bookmarks create
@bookmarks.command('create')
@click.option('--site', '-s', type=click.Choice(['red', 'ops']), required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
def create_collection_from_bookmarks(site: str):
    """
    Create a Plex collection based on your site bookmarks.
    If the collection already exists, ask for confirmation to update.
    """
    plex_manager = PlexManager()
    plex_manager.populate_album_cache()
    gazelle_api = GazelleAPI(site)
    collection_creator = CollectionCreator(plex_manager, gazelle_api)

    try:
        # First attempt without forcing
        initial_result = collection_creator.create_or_update_collection_from_collage(
            site=site.upper(),
            fetch_bookmarks=True,
            force_update=False
        )

        if initial_result.response_status is False:
            # The collection already exists but wasn't forced => ask the user
            if click.confirm(
                    f'Collection from bookmarks on site "{site.upper()}" already exists. '
                    'Do you want to update it with new items?',
                    default=True
            ):
                # Second call with force_update=True
                forced_result = collection_creator.create_or_update_collection_from_collage(
                    site=site.upper(),
                    fetch_bookmarks=True,
                    force_update=True
                )
                if forced_result.response_status is True:
                    click.echo(
                        f'Bookmark-based collection for site {site.upper()} '
                        f'was updated successfully with {len(forced_result.albums)} entries.'
                    )
                elif forced_result.response_status is None:
                    click.echo(
                        f"No valid bookmark data found for site {site.upper()} when forced."
                    )
                else:
                    # If forced_result.response_status is False again (unlikely),
                    # or any other scenario
                    click.echo("Something unexpected happened.")
            else:
                click.echo(
                    f'Skipping bookmark-based collection update for "{site.upper()}".'
                )

        elif initial_result.response_status is None:
            click.echo(f"No valid bookmark data found for site {site.upper()}.")
        else:
            # response_status == True => successfully created/updated
            click.echo(
                f"Bookmark-based collection for site {site.upper()} "
                f"created or updated successfully with {len(initial_result.albums)} entries."
                )

    except Exception as exc:  # pylint: disable=W0718
        logger.exception(
            'Failed to create collection from bookmarks on site %s: %s',
            site.upper(), exc
        )
        click.echo(
            f'Failed to create collection from bookmarks on site {site.upper()}: {exc}'
        )


# bookmarks cache
@bookmarks.group('cache')
def bookmarks_cache():
    """Manage bookmarks cache."""


# bookmarks cache show
@bookmarks_cache.command('show')
def show_bookmarks_cache_collection():
    """Shows the location of the bookmarks cache file if it exists."""
    try:
        bookmarks_cache_manager = BookmarksCollectionCache()
        cache_file = bookmarks_cache_manager.csv_file

        if os.path.exists(cache_file):
            click.echo(f"Collection bookmarks cache file exists at: {os.path.abspath(cache_file)}")
        else:
            click.echo("Collection bookmarks cache file does not exist.")
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to show collection bookmarks cache: %s', exc)
        click.echo(f"An error occurred while showing the collection bookmarks cache: {exc}")


# bookmarks cache reset
@bookmarks_cache.command('reset')
def reset_bookmarks_cache_collection():
    """Resets the saved bookmarks cache."""
    if click.confirm('Are you sure you want to reset the collection bookmarks cache?'):
        try:
            bookmarks_cache_manager = BookmarksCollectionCache()
            bookmarks_cache_manager.reset_cache()
            click.echo("Collection bookmarks cache has been reset successfully.")
        except Exception as exc:  # pylint: disable=W0718
            logger.exception('Failed to reset collection bookmarks cache: %s', exc)
            click.echo(f"An error occurred while resetting the collection bookmarks cache: {exc}")


def update_collections_from_collages(
        collages: List[Collection], plex_manager: PlexManager, fetch_bookmarks=False):
    """
    Forces the update of each collage (force_update=True)
    """
    for collage in collages:
        logger.info('Updating collection for collage "%s"...', collage.name)
        gazelle_api = GazelleAPI(collage.site)
        collection_creator = CollectionCreator(plex_manager, gazelle_api)
        result = collection_creator.create_or_update_collection_from_collage(
            collage.external_id, site=collage.site,
            fetch_bookmarks=fetch_bookmarks, force_update=True
        )

        if result.response_status is None:
            logger.info('No valid data found for collage "%s".', collage.name)
        else:
            logger.info('Collection for collage "%s" created/updated successfully with %s entries.',
                        collage.name, len(result.albums))


def main():
    """Actual entry point for the CLI when installed."""
    configure_logger()
    cli()


if __name__ == '__main__':
    configure_logger()
    main()
