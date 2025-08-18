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
from red_plex.use_case.show_missing.show_missing_use_case import ShowMissingUseCase


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
            logger.info("Pushing local collection updates to upstream collages...")
            if collage_ids:
                logger.info("Processing specific collages: %s",
                            ', '.join(c.name for c in target_collages))
            success = push_collections_to_upstream(
                local_database=local_database,
                collage_list=target_collages,
                plex_manager=plex_manager
            )
            if success:
                logger.info("All collections successfully synced to upstream.")
            else:
                logger.info("Some collections failed to sync. Check logs for details.")
        else:
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


@collages.command('show-missing')
@click.pass_context
@click.argument('collage_id')
def show_missing(ctx, collage_id):
    """
    Show missing torrent groups from the local collection compared to the site collage.
    
    COLLAGE_ID is the external ID of the collage to check.
    """
    local_database = ctx.obj.get('db')
    if not local_database:
        click.echo("Error: Database not initialized.", err=True)
        return

    # Get the local collection to determine which site to use
    local_collection = local_database.get_collage_collection_by_external_id(collage_id)
    if not local_collection:
        click.echo(
            f"Error: No local collection found for collage ID {collage_id}. "
            f"You may need to convert it first using "
            f"'red-plex collages convert {collage_id} --site <site>'", err=True)
        return

    site = local_collection.site

    # Initialize Gazelle API
    try:
        gazelle_api = GazelleAPI(site)
    except Exception as e: # pylint: disable=W0718
        logger.error("Failed to initialize Gazelle API: %s", e, exc_info=True)
        click.echo(f"Error: Failed to initialize API for {site.upper()} - {e}", err=True)
        return

    # Use the show missing use case
    use_case = ShowMissingUseCase(local_database, gazelle_api)
    result = use_case.execute(collage_id)

    if not result.success:
        click.echo(f"Error: {result.error_message}", err=True)
        return

    click.echo(f"Checking collage '{result.collage_name}' "
               f"(ID: {collage_id}) on {result.site.upper()}...")

    if not result.has_missing_groups:
        click.echo("✓ No missing groups found! "
                   "Your local collection is up to date.")
        return

    click.echo(f"\nFound {len(result.missing_groups)} missing group(s) "
               "in your local collection:")
    click.echo("=" * 80)

    # Display missing groups
    for i, missing_group in enumerate(result.missing_groups, 1):
        artists_str = ", ".join(missing_group.artist_names)
        click.echo(f"{i:3d}. {artists_str} - {missing_group.album_name}")
        click.echo(f"     Link: {missing_group.torrent_url}")
        if i < len(result.missing_groups):  # Don't add extra line after last item
            click.echo()

    click.echo("=" * 80)
