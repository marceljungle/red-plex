"""Database management CLI commands."""

import os

import click

from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode


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