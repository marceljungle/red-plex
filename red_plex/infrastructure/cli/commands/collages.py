"""Collage management CLI commands."""

import click

from red_plex.infrastructure.cli.cli import update_collections_from_collages
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.infrastructure.service.collection_processor import CollectionProcessingService
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode


def map_fetch_mode(fetch_mode) -> AlbumFetchMode:
    """Map the fetch mode string to an AlbumFetchMode enum."""
    if fetch_mode == 'query':
        return AlbumFetchMode.QUERY
    return AlbumFetchMode.TORRENT_NAME


@click.group('collages')
def collages():
    """Possible operations with site collages."""


@collages.command('update')
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
def update_collages(ctx, fetch_mode: str):
    """Synchronize all stored collections with their source collages."""
    # Import here to avoid circular imports with cli.py

    fetch_mode = map_fetch_mode(fetch_mode)
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
            local_database=local_database,
            collage_list=all_collages,
            plex_manager=plex_manager,
            fetch_bookmarks=False,
            fetch_mode=fetch_mode)
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to update stored collections: %s', exc)
        click.echo(f"An error occurred while updating stored collections: {exc}")


@collages.command('convert')
@click.argument('collage_ids', nargs=-1)
@click.option('--site', '-s',
              type=click.Choice(['red', 'ops']),
              required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
@click.option(
    '--fetch-mode', '-fm',
    type=click.Choice(['torrent_name', 'query'], case_sensitive=False),  # Added case_sensitive
    default='torrent_name',
    show_default=True,
    help=(
            '(Optional) Album lookup strategy:\n'
            '\n- torrent_name: uses torrent dir name (original behavior).\n'
            '\n- query: uses Plex queries (Beets/Lidarr friendly).\n'
    )
)
@click.pass_context
def convert_collages(ctx, collage_ids, site, fetch_mode):
    """
    Create/Update Plex collections from given COLLAGE_IDS.
    """
    if not collage_ids:
        click.echo("Please provide at least one COLLAGE_ID.")
        ctx.exit(1)  # Exit with an error code

    album_fetch_mode_enum = map_fetch_mode(fetch_mode)

    # --- Dependency Setup ---
    local_database = ctx.obj.get('db')
    if not local_database:
        click.echo("Error: Database not initialized.", err=True)
        ctx.exit(1)

    plex_manager, gazelle_api = None, None
    try:
        plex_manager = PlexManager(db=local_database)
        gazelle_api = GazelleAPI(site)
    except Exception as e:  # pylint: disable=W0718
        logger.error("Failed to initialize dependencies: %s", e, exc_info=True)
        click.echo(f"Error: Failed to initialize dependencies - {e}", err=True)
        ctx.exit(1)

    # --- Service Instantiation and Execution ---
    processor = CollectionProcessingService(local_database, plex_manager, gazelle_api)

    # Call the service, passing the necessary functions from click
    processor.process_collages(
        collage_ids=collage_ids,
        album_fetch_mode=album_fetch_mode_enum,
        echo_func=click.echo,
        confirm_func=click.confirm  # Pass the actual click.confirm
    )

    click.echo("Processing finished.")
