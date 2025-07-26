"""Database management CLI commands."""

import os

import click

from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.site_tags.site_tags_use_case import SiteTagsUseCase


@click.group()
def db():
    """Manage database."""


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


@db.group('albums')
def db_albums():
    """Manage albums inside database."""


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
    except Exception as exc:  # pylint: disable=W0703
        click.echo(f"An error occurred while updating the album table: {exc}")


@db.group('collections')
def db_collections():
    """Manage albums inside database."""


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


@db.group('bookmarks')
def db_bookmarks():
    """Manage bookmarks inside database."""


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


@db.group('remote-mappings')
def db_remote_mappings():
    """Manage core remote mappings between Plex items and site group IDs."""


@db_remote_mappings.command('scan')
@click.option('--site', '-s',
              type=click.Choice(['red', 'ops'], case_sensitive=False),
              required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
@click.option('--always-skip', is_flag=True, help='Always skip albums with multiple matches.')
@click.pass_context
def scan_albums(ctx, site: str, always_skip: bool):
    """
    Scan albums and create remote mappings by searching filenames on the site.
    This is an incremental process - only unscanned albums will be processed.
    """
    try:
        # Get dependencies from context
        local_database = ctx.obj.get('db')
        if not local_database:
            click.echo("Error: Database not initialized.", err=True)
            ctx.exit(1)

        # Initialize dependencies
        plex_manager = PlexManager(db=local_database)
        gazelle_api = GazelleAPI(site)

        # Ensure albums table is populated
        click.echo("Updating album database from Plex...")
        plex_manager.populate_album_table()

        # Create use case and execute scan
        site_tags_use_case = SiteTagsUseCase(local_database, plex_manager, gazelle_api)
        site_tags_use_case.scan_albums_for_site_tags(
            echo_func=click.echo,
            confirm_func=click.confirm,
            always_skip=always_skip
        )

    except Exception as e:  # pylint: disable=W0703
        logger.exception("Error during album scan: %s", e)
        click.echo(f"Error during album scan: {e}", err=True)
        ctx.exit(1)





@db_remote_mappings.command('reset')
@click.pass_context
def reset_remote_mappings(ctx):
    """Reset remote mappings. Use with caution!"""
    if click.confirm('Are you sure you want to reset remote mappings?'):
        try:
            local_database = ctx.obj.get('db')
            if not local_database:
                click.echo("Error: Database not initialized.", err=True)
                ctx.exit(1)

            local_database.reset_tag_mappings()
            click.echo("Remote mappings have been reset successfully.")
        except Exception as e:  # pylint: disable=W0703
            logger.exception("Error resetting remote mappings: %s", e)
            click.echo(f"Error resetting remote mappings: {e}", err=True)
            ctx.exit(1)
