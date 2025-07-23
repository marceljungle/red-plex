"""Collection creator CLI."""
import sys
from typing import List

import click

from red_plex.domain.models import Collection
from red_plex.infrastructure.cli.commands.bookmarks import bookmarks
from red_plex.infrastructure.cli.commands.collages import collages
from red_plex.infrastructure.cli.commands.config import config
from red_plex.infrastructure.cli.commands.db import db
from red_plex.infrastructure.cli.commands.extras import extras
from red_plex.infrastructure.cli.commands.gui import gui
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger, configure_logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode
from red_plex.use_case.create_collection.query.query_sync_collection import (
    QuerySyncCollectionUseCase)
from red_plex.use_case.create_collection.torrent_name.torrent_name_sync_collection import (
    TorrentNameCollectionCreatorUseCase)


@click.group()
@click.pass_context
def cli(ctx):
    """A CLI tool for creating Plex collections from RED and OPS collages."""
    if 'db' not in ctx.obj:
        ctx.obj['db'] = LocalDatabase()


# Add all command groups
cli.add_command(config)
cli.add_command(collages)
cli.add_command(bookmarks)
cli.add_command(db)
cli.add_command(gui)
cli.add_command(extras)


def update_collections_from_collages(local_database: LocalDatabase,
                                     collage_list: List[Collection],
                                     plex_manager: PlexManager,
                                     fetch_bookmarks=False,
                                     fetch_mode: AlbumFetchMode = AlbumFetchMode.TORRENT_NAME):
    """
    Forces the update of each collage (force_update=True)
    """

    for collage in collage_list:
        logger.info('Updating collection for collage "%s"...', collage.name)
        gazelle_api = GazelleAPI(collage.site)

        if AlbumFetchMode.TORRENT_NAME == fetch_mode:
            collection_creator = TorrentNameCollectionCreatorUseCase(local_database,
                                                                     plex_manager,
                                                                     gazelle_api)
            result = collection_creator.execute(
                collage_id=collage.external_id,
                site=collage.site,
                fetch_bookmarks=fetch_bookmarks,
                force_update=True
            )
        else:
            collection_creator = QuerySyncCollectionUseCase(local_database,
                                                            plex_manager,
                                                            gazelle_api)
            result = collection_creator.execute(
                collage_id=collage.external_id,
                site=collage.site,
                fetch_bookmarks=fetch_bookmarks,
                force_update=True
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
    if 'gui' not in sys.argv:
        configure_logger()
    cli(obj={})  # pylint: disable=no-value-for-parameter


if __name__ == '__main__':
    main()
