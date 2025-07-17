"""Extra CLI commands for advanced features."""

import click

from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.site_tags.site_tags_use_case import SiteTagsUseCase


@click.group()
def extras():
    """Extra features and advanced functionality."""
    pass


@extras.group('site-tags')
def site_tags():
    """Manage site tag mappings and collections."""
    pass


@site_tags.command('scan')
@click.option('--site', '-s',
              type=click.Choice(['red', 'ops'], case_sensitive=False),
              required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
@click.pass_context
def scan_albums(ctx, site: str):
    """
    Scan albums and create site tag mappings by searching filenames on the site.
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
            confirm_func=click.confirm
        )

    except Exception as e:
        logger.exception("Error during album scan: %s", e)
        click.echo(f"Error during album scan: {e}", err=True)
        ctx.exit(1)


@site_tags.command('convert')
@click.option('--site', '-s',
              type=click.Choice(['red', 'ops'], case_sensitive=False),
              required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
@click.option('--tags', '-t',
              required=True,
              help='Comma-separated list of tags to filter by.')
@click.option('--collection-name', '-n',
              required=True,
              help='Name for the Plex collection to create/update.')
@click.pass_context
def convert_tags_to_collection(ctx, site: str, tags: str, collection_name: str):
    """
    Create a Plex collection from albums matching the specified tags.
    """
    try:
        # Parse tags
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        if not tag_list:
            click.echo("Error: No valid tags provided.", err=True)
            ctx.exit(1)

        # Get dependencies from context
        local_database = ctx.obj.get('db')
        if not local_database:
            click.echo("Error: Database not initialized.", err=True)
            ctx.exit(1)

        # Initialize dependencies
        plex_manager = PlexManager(db=local_database)
        gazelle_api = GazelleAPI(site)

        # Create use case and execute conversion
        site_tags_use_case = SiteTagsUseCase(local_database, plex_manager, gazelle_api)
        success = site_tags_use_case.create_collection_from_tags(
            tags=tag_list,
            collection_name=collection_name,
            echo_func=click.echo
        )

        if success:
            click.echo("Collection creation completed successfully.")
        else:
            click.echo("Collection creation failed.", err=True)
            ctx.exit(1)

    except Exception as e:
        logger.exception("Error during collection creation: %s", e)
        click.echo(f"Error during collection creation: {e}", err=True)
        ctx.exit(1)


@site_tags.command('reset')
@click.option('--site', '-s',
              type=click.Choice(['red', 'ops'], case_sensitive=False),
              help='Specify the site to reset mappings for. If not provided, resets all sites.')
@click.pass_context
def reset_site_tag_mappings(ctx, site: str):
    """Reset site tag mappings. Use with caution!"""
    site_text = f" for site {site}" if site else " for all sites"
    if click.confirm(f'Are you sure you want to reset site tag mappings{site_text}?'):
        try:
            local_database = ctx.obj.get('db')
            if not local_database:
                click.echo("Error: Database not initialized.", err=True)
                ctx.exit(1)

            local_database.reset_tag_mappings(site)
            click.echo(f"Site tag mappings{site_text} have been reset successfully.")
        except Exception as e:
            logger.exception("Error resetting site tag mappings: %s", e)
            click.echo(f"Error resetting site tag mappings: {e}", err=True)
            ctx.exit(1)