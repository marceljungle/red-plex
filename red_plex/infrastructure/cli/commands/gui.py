"""GUI launcher CLI command."""

import subprocess
import sys

import click


@click.command()
@click.option('--host', '-h', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
@click.option('--port', '-p', default=8000, type=int, help='Port to bind to (default: 8000)')
@click.option('--debug', is_flag=True, help='Run in debug mode with auto-reloading.')
def gui(host, port, debug):
    """Launches the web interface using the Gunicorn production server."""

    # Build the bind address for Gunicorn
    bind_address = f"{host}:{port}"

    click.echo(f"🚀 Launching Gunicorn server at http://{bind_address}")

    # Create the list of arguments for the Gunicorn command
    command = [
        'gunicorn',
        '--worker-class', 'eventlet',
        '-w', '1',
        '--bind', bind_address,
    ]

    # If the --debug flag is passed, add Gunicorn's reload option
    if debug:
        click.echo("   -> Debug mode on (auto-reload enabled).")
        command.append('--reload')

    command.append('wsgi:app')

    try:
        # Execute the Gunicorn command
        subprocess.run(command, check=True)
    except FileNotFoundError:
        click.echo(
            "Error: 'gunicorn' command not found.",
            err=True
        )
        click.echo(
            "Please make sure you have installed it with: pip install gunicorn eventlet",
            err=True
        )
        sys.exit(1)
