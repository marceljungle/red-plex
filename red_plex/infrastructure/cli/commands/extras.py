"""Extra CLI commands for advanced features."""

import click

from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.site_tags.site_tags_use_case import SiteTagsUseCase


@click.group()
def extras():
    """Extra features and advanced functionality."""


@extras.group('site-tags')
def site_tags():
    """Manage site tag mappings and collections."""


@site_tags.command('scan')
@click.option('--site', '-s',
              type=click.Choice(['red', 'ops'], case_sensitive=False),
              required=True,
              help='Specify the site: red (Redacted) or ops (Orpheus).')
@click.option('--always-skip', is_flag=True, help='Always skip albums with multiple matches.')
@click.pass_context
def scan_albums(ctx, site: str, always_skip: bool):
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
            confirm_func=click.confirm,
            always_skip = always_skip
        )

    except Exception as e:  # pylint: disable=W0703
        logger.exception("Error during album scan: %s", e)
        click.echo(f"Error during album scan: {e}", err=True)
        ctx.exit(1)


@site_tags.command('convert')
@click.option('--tags', '-t',
              required=True,
              help='Comma-separated list of tags to filter by.')
@click.option('--collection-name', '-n',
              required=True,
              help='Name for the Plex collection to create/update.')
@click.pass_context
def convert_tags_to_collection(ctx, tags: str, collection_name: str):
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

        # Create the use case and execute conversion
        # No need of gazelle_api here since we're using the local database
        site_tags_use_case = SiteTagsUseCase(local_database=local_database,
                                             plex_manager=plex_manager)
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

    except Exception as e:  # pylint: disable=W0703
        logger.exception("Error during collection creation: %s", e)
        click.echo(f"Error during collection creation: {e}", err=True)
        ctx.exit(1)


@site_tags.command('reset')
@click.pass_context
def reset_site_tag_mappings(ctx):
    """Reset site tag mappings. Use with caution!"""
    if click.confirm('Are you sure you want to reset site tag mappings?'):
        try:
            local_database = ctx.obj.get('db')
            if not local_database:
                click.echo("Error: Database not initialized.", err=True)
                ctx.exit(1)

            local_database.reset_tag_mappings()
            click.echo("Tag mappings have been reset successfully.")
        except Exception as e:  # pylint: disable=W0703
            logger.exception("Error resetting site tag mappings: %s", e)
            click.echo(f"Error resetting site tag mappings: {e}", err=True)
            ctx.exit(1)
