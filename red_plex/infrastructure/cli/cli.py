"""Collection creator CLI."""
import os
import subprocess
from typing import List

import click
import yaml

from domain.models import Collection
from infrastructure.db.local_database import LocalDatabase
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
@click.pass_context
def cli(ctx):
    """A CLI tool for creating Plex collections from RED and OPS collages."""
    if 'db' not in ctx.obj:
        ctx.obj['db'] = LocalDatabase()


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


# collages
@cli.group('collages')
def collages():
    """Possible operations with site collages."""


# collages update
@collages.command('update')
@click.pass_context
def update_collages(ctx):
    """Synchronize all stored collections with their source collages."""
    try:
        local_database = ctx.obj.get('db', None)
        local_database: LocalDatabase
        all_collages = local_database.get_all_collage_collections()

        if not all_collages:
            click.echo("No collages found in the db.")
            return

        # Initialize PlexManager once, populate its db once
        plex_manager = PlexManager(local_database)
        if not plex_manager:
            return
        plex_manager.populate_album_table()

        update_collections_from_collages(
            local_database, all_collages, plex_manager, fetch_bookmarks=False)
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update stored collections: %s', exc)
        click.echo(f"An error occurred while updating stored collections: {exc}")


# convert collection
@collages.command('convert')
@click.argument('collage_ids', nargs=-1)
@click.option('--site', '-s', type=click.Choice(['red', 'ops']), required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
@click.pass_context
def convert_collages(ctx, collage_ids, site):
    """
    Create Plex collections from given COLLAGE_IDS.
    If the collection already exists, confirmation will be requested to update it.
    """
    if not collage_ids:
        click.echo("Please provide at least one COLLAGE_ID.")
        return

    local_database = ctx.obj.get('db', None)
    local_database: LocalDatabase
    plex_manager = PlexManager(db=local_database)
    if not plex_manager:
        return

    plex_manager.populate_album_table()

    gazelle_api = GazelleAPI(site)
    if not gazelle_api:
        return

    collection_creator = CollectionCreator(local_database, plex_manager, gazelle_api)

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


# bookmarks
@cli.group()
def bookmarks():
    """Possible operations with your site bookmarks."""


# bookmarks update
@bookmarks.command('update')
@click.pass_context
def update_bookmarks_collection(ctx):
    """Synchronize all stored bookmarks with their source collages."""
    try:
        local_database = ctx.obj.get('db', None)
        local_database: LocalDatabase
        all_bookmarks = local_database.get_all_bookmark_collections()

        if not all_bookmarks:
            click.echo("No bookmarks found in the db.")
            return

        plex_manager = PlexManager(local_database)
        if not plex_manager:
            return
        plex_manager.populate_album_table()

        update_collections_from_collages(
            local_database, all_bookmarks, plex_manager, fetch_bookmarks=True)

    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update stored bookmarks: %s', exc)
        click.echo(f"An error occurred while updating stored bookmarks: {exc}")


# bookmarks convert
@bookmarks.command('convert')
@click.pass_context
@click.option('--site', '-s', type=click.Choice(['red', 'ops']), required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
def convert_collection_from_bookmarks(ctx, site: str):
    """
    Create a Plex collection based on your site bookmarks.
    If the collection already exists, ask for confirmation to update.
    """
    local_database = ctx.obj.get('db', None)
    local_database: LocalDatabase
    plex_manager = PlexManager(db=local_database)
    plex_manager.populate_album_table()
    gazelle_api = GazelleAPI(site)
    collection_creator = CollectionCreator(local_database, plex_manager, gazelle_api)

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


# db
@cli.group()
def db():
    """Manage database."""


# db location
@db.command('location')
@click.pass_context
def db_location(ctx):
    """Returns the location to the database."""
    local_database = ctx.obj.get('db', None)
    local_database: LocalDatabase
    db_path = local_database.db_path
    if os.path.exists(db_path):
        click.echo(f"Database exists at: {db_path}")
    else:
        click.echo("Database file does not exist.")


# db albums
@db.group('albums')
def db_albums():
    """Manage albums inside database."""


# db albums reset
@db_albums.command('reset')
@click.pass_context
def db_albums_reset(ctx):
    """Resets albums table from database."""
    if click.confirm('Are you sure you want to reset the db?'):
        try:
            local_database = ctx.obj.get('db', None)
            local_database: LocalDatabase
            local_database.reset_albums()
            click.echo("Albums table has been reset successfully.")
        except Exception as exc:  # pylint: disable=W0718
            click.echo(f"An error occurred while resetting the album table: {exc}")


@db_albums.command('update')
@click.pass_context
def db_albums_update(ctx):
    """Updates albums table from Plex."""
    try:
        local_database = ctx.obj.get('db', None)
        local_database: LocalDatabase
        plex_manager = PlexManager(db=local_database)
        plex_manager.populate_album_table()
        click.echo("Albums table has been updated successfully.")
    except Exception as exc: # pylint: disable=W0703
        click.echo(f"An error occurred while updating the album table: {exc}")


# db collections
@db.group('collections')
def db_collections():
    """Manage albums inside database."""


# db collections reset
@db_collections.command('reset')
@click.pass_context
def db_collections_reset(ctx):
    """Resets collections table from database."""
    if click.confirm('Are you sure you want to reset the collection db?'):
        try:
            local_database = ctx.obj.get('db', None)
            local_database: LocalDatabase
            local_database.reset_collage_collections()
            click.echo("Collage collection db has been reset successfully.")
        except Exception as exc:  # pylint: disable=W0718
            logger.exception('Failed to reset collage collection db: %s', exc)
            click.echo(
                f"An error occurred while resetting the collage collection db: {exc}")


# db bookmarks
@db.group('bookmarks')
def db_bookmarks():
    """Manage bookmarks inside database."""


# db bookmarks reset
@db_bookmarks.command('reset')
@click.pass_context
def db_bookmarks_reset(ctx):
    """Resets bookmarks table from database."""
    if click.confirm('Are you sure you want to reset the collection bookmarks db?'):
        try:
            local_database = ctx.obj.get('db', None)
            local_database: LocalDatabase
            local_database.reset_bookmark_collections()
            click.echo("Collection bookmarks db has been reset successfully.")
        except Exception as exc:  # pylint: disable=W0718
            logger.exception('Failed to reset collection bookmarks db: %s', exc)
            click.echo(f"An error occurred while resetting the collection bookmarks db: {exc}")


def update_collections_from_collages(local_database: LocalDatabase,
                                     collage_list: List[Collection],
                                     plex_manager: PlexManager,
                                     fetch_bookmarks=False):
    """
    Forces the update of each collage (force_update=True)
    """
    for collage in collage_list:
        logger.info('Updating collection for collage "%s"...', collage.name)
        gazelle_api = GazelleAPI(collage.site)
        collection_creator = CollectionCreator(local_database, plex_manager, gazelle_api)
        result = collection_creator.create_or_update_collection_from_collage(
            collage.external_id, site=collage.site,
            fetch_bookmarks=fetch_bookmarks, force_update=True
        )

        if result.response_status is None:
            logger.info('No valid data found for collage "%s".', collage.name)
        else:
            logger.info('Collection for collage "%s" created/updated successfully with %s entries.',
                        collage.name, len(result.albums))


@cli.result_callback()
@click.pass_context
def finalize_cli(ctx, _result, *_args, **_kwargs):
    """Close the DB when all commands have finished."""
    local_database = ctx.obj.get('db', None)
    if local_database:
        local_database.close()


def main():
    """Actual entry point for the CLI when installed."""
    configure_logger()
    cli(obj={})  # pylint: disable=no-value-for-parameter


if __name__ == '__main__':
    configure_logger()
    main()
