"""Bookmark management CLI commands."""

import click

from red_plex.infrastructure.cli.utils import update_collections_from_collages, map_fetch_mode
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.infrastructure.service.collection_processor import CollectionProcessingService
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode


@click.group()
def bookmarks():
    """Possible operations with your site bookmarks."""


@bookmarks.command('update')
@click.pass_context
@click.option(
    '--fetch-mode', '-fm',
    type=click.Choice(['torrent_name', 'query']),
    default='torrent_name',
    show_default=True,
    help=(
            '(Optional) Album lookup strategy:\n'
            '\n- torrent_name: uses torrent dir name to search in Plex, '
            'if you don\'t use Beets/Lidarr \n'
            '\n- query: uses queries to Plex instead of searching by path name '
            '(if you use Beets/Lidarr)\n'
    )
)
# pylint: disable=R0801
def update_bookmarks_collection(ctx, fetch_mode: str):
    """Synchronize all stored bookmarks with their source collages."""
    # Import here to avoid circular imports with cli.py

    fetch_mode = map_fetch_mode(fetch_mode)
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
            local_database,
            all_bookmarks,
            plex_manager,
            fetch_bookmarks=True)

    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update stored bookmarks: %s', exc)
        click.echo(f"An error occurred while updating stored bookmarks: {exc}")


@bookmarks.command('convert')
@click.option('--site', '-s',
              type=click.Choice(['red', 'ops'], case_sensitive=False),
              required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
@click.option(
    '--fetch-mode', '-fm',
    type=click.Choice(['torrent_name', 'query'], case_sensitive=False),
    default='torrent_name',
    show_default=True,
    help=(
            '(Optional) Album lookup strategy:\n'
            '\n- torrent_name: uses torrent dir name (original behavior).\n'
            '\n- query: uses Plex queries (Beets/Lidarr friendly).\n'
    )
)
@click.pass_context
# pylint: disable=R0801
def convert_collection_from_bookmarks(ctx, site: str, fetch_mode: str):
    """
    Create/Update a Plex collection based on your site bookmarks.
    """
    album_fetch_mode_enum = map_fetch_mode(fetch_mode)

    # --- Dependency Setup ---
    local_database = ctx.obj.get('db')
    if not local_database:
        click.echo("Error: Database not initialized.", err=True)
        ctx.exit(1)

    plex_manager, gazelle_api = None, None
    try:
        plex_manager = PlexManager(db=local_database)
        gazelle_api = GazelleAPI(site)  # Create GazelleAPI based on site
    except Exception as e:  # pylint: disable=W0718
        logger.error("Failed to initialize dependencies: %s", e, exc_info=True)
        click.echo(f"Error: Failed to initialize dependencies - {e}", err=True)
        ctx.exit(1)

    # --- Service Instantiation and Execution ---
    processor = CollectionProcessingService(local_database, plex_manager, gazelle_api)

    try:
        # Call the specific bookmark processing method
        processor.process_bookmarks(
            album_fetch_mode=album_fetch_mode_enum,
            echo_func=click.echo,
            confirm_func=click.confirm
        )
    except Exception as exc:  # pylint: disable=W0718
        logger.exception(
            'Failed to create collection from bookmarks on site %s: %s',
            site.upper(), exc
        )
        click.echo(
            f'Failed to create collection from bookmarks on site {site.upper()}: {exc}',
            err=True
        )
        ctx.exit(1)

    click.echo("Bookmark processing finished.")
