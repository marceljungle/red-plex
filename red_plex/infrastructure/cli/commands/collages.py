"""Collage management CLI commands."""

import click

from red_plex.infrastructure.cli.utils import (update_collections_from_collages,
                                               map_fetch_mode,
                                               push_collections_to_upstream)
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.infrastructure.service.collection_processor import CollectionProcessingService


@click.group('collages')
def collages():
    """Possible operations with site collages."""


@collages.command('update')
@click.pass_context
@click.argument('collage_ids', nargs=-1)
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
@click.option(
    '--push', '--update-upstream',
    is_flag=True,
    default=False,
    help='Push local collection changes back to upstream collages on the site'
)
# pylint: disable=R0912
def update_collages(ctx, collage_ids, fetch_mode: str, push: bool):
    """
    Synchronize stored collections with their source collages.
    
    If COLLAGE_IDS are provided, only those collages will be processed.
    If no COLLAGE_IDS are provided, all stored collages will be processed.
    """
    # Import here to avoid circular imports with cli.py

    fetch_mode = map_fetch_mode(fetch_mode)
    try:
        local_database = ctx.obj.get('db', None)
        local_database: LocalDatabase

        if collage_ids:
            # Filter to only the specified collage IDs
            all_collages = local_database.get_all_collage_collections()
            collage_ids_set = set(collage_ids)
            filtered_collages = [c for c in all_collages if c.external_id in collage_ids_set]

            if not filtered_collages:
                click.echo(f"No collages found in the database with IDs: {', '.join(collage_ids)}")
                return

            # Check if any requested IDs were not found
            found_ids = {c.external_id for c in filtered_collages}
            missing_ids = collage_ids_set - found_ids
            if missing_ids:
                click.echo(f"Warning: Collage IDs not found in database: {', '.join(missing_ids)}")

            target_collages = filtered_collages
        else:
            # Process all collages
            target_collages = local_database.get_all_collage_collections()

        if not target_collages:
            click.echo("No collages found to process.")
            return

        # Initialize PlexManager once, populate its db once
        plex_manager = PlexManager(local_database)
        if not plex_manager:
            return
        plex_manager.populate_album_table()

        if push:
            # Push mode: sync local collections to upstream
            click.echo("Pushing local collection updates to upstream collages...")
            if collage_ids:
                click.echo(f"Processing specific collages: "
                           f"{', '.join(c.name for c in target_collages)}")
            success = push_collections_to_upstream(
                local_database=local_database,
                collage_list=target_collages,
                plex_manager=plex_manager
            )
            if success:
                click.echo("All collections successfully synced to upstream.")
            else:
                click.echo("Some collections failed to sync. Check logs for details.")

        # Always update local collections
        if collage_ids:
            click.echo(f"Updating specific collages: "
                       f"{', '.join(c.name for c in target_collages)}")
        update_collections_from_collages(
            local_database=local_database,
            collage_list=target_collages,
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
