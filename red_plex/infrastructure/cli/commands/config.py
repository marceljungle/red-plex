"""Configuration management CLI commands."""

import os
import subprocess

import click
import yaml

from red_plex.infrastructure.config.config import (
    CONFIG_FILE_PATH,
    load_config,
    save_config,
    ensure_config_exists
)
from red_plex.infrastructure.config.models import Configuration
from red_plex.infrastructure.logger.logger import logger


@click.group()
def config():
    """View or edit configuration settings."""


@config.command('show')
def show_config():
    """Display the current configuration."""
    config_data = load_config()
    path_with_config = (
            f"Configuration path: {CONFIG_FILE_PATH}\n\n" +
            yaml.dump(config_data.to_dict(), default_flow_style=False)
    )
    click.echo(path_with_config)


@config.command('edit')
def edit_config():
    """Open the configuration file in the default editor."""
    # Ensure the configuration file exists
    ensure_config_exists()

    # Default to 'nano' if EDITOR is not set
    editor = os.environ.get('EDITOR', 'notepad' if os.name == 'nt' else 'nano')
    click.echo(f"Opening config file at {CONFIG_FILE_PATH}...")
    try:
        subprocess.call([editor, CONFIG_FILE_PATH])
    except FileNotFoundError:
        message = f"Editor '{editor}' not found. \
            Please set the EDITOR environment variable to a valid editor."
        logger.error(message)
        click.echo(message)
    except Exception as exc:  # pylint: disable=W0718
        logger.exception('Failed to open editor: %s', exc)
        click.echo(f"An error occurred while opening the editor: {exc}")


@config.command('reset')
def reset_config():
    """Reset the configuration to default values."""
    if click.confirm('Are you sure you want to reset the configuration to default values?'):
        save_config(Configuration.default())
        click.echo(f"Configuration reset to default values at {CONFIG_FILE_PATH}")