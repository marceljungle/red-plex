"""Collection creator CLI."""
import sys
from typing import List

import click

from red_plex.infrastructure.cli.commands.bookmarks import bookmarks
from red_plex.infrastructure.cli.commands.collages import collages
from red_plex.infrastructure.cli.commands.config import config
from red_plex.infrastructure.cli.commands.db import db
from red_plex.infrastructure.cli.commands.extras import extras
from red_plex.infrastructure.cli.commands.gui import gui
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import configure_logger


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
