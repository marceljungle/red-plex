"""Extra CLI commands for advanced features."""

import click

from red_plex.infrastructure.logger.logger import logger
from red_plex.use_case.site_tags.site_tags_use_case import SiteTagsUseCase
from red_plex.infrastructure.cli.utils import get_database_from_context, create_plex_manager


@click.group()
def extras():
    """Extra features and advanced functionality."""

@extras.group('site-tags')
def site_tags():
    """Site tags functionality for creating collections from tagged albums."""


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

        # Get dependencies from context using shared utility
        local_database = get_database_from_context(ctx)
        plex_manager = create_plex_manager(local_database)

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
