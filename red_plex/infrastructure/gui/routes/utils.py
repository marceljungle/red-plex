"""Shared utilities for GUI routes to reduce code duplication."""
import logging
from typing import Callable

from flask import flash

from red_plex.infrastructure.db.local_database import LocalDatabase


# pylint: disable=W0718
def get_mapping_stats_and_recent(get_db: Callable, limit: int = 20) -> tuple:
    """
    Get mapping statistics and recent mappings for display.

    Returns:
        Tuple of (stats_dict, recent_mappings_list, error_occurred)
    """
    try:
        db = get_db()
        # Get basic stats about mappings
        mapped_albums, total_tags, total_mappings = db.get_site_tags_stats()
        stats = {
            'mapped_albums': mapped_albums,
            'total_tags': total_tags,
            'total_mappings': total_mappings
        }

        # Get recent mappings for display
        recent_mappings = db.get_recent_site_tag_mappings(limit=limit)

        return stats, recent_mappings, False

    except Exception as e:
        flash(f'Error loading data: {str(e)}', 'error')
        default_stats = {'mapped_albums': 0, 'total_tags': 0, 'total_mappings': 0}
        return default_stats, [], True


def execute_background_task(
        socketio,
        app,
        task_func: Callable[[LocalDatabase, Callable], bool],
        success_message: str = "Operation completed successfully!",
        error_prefix: str = "Error"
) -> None:
    """
    Execute a background task with standardized error handling and status updates.

    Args:
        socketio: The SocketIO instance
        app: The Flask app instance
        task_func: Function that takes (db, echo_func) and returns success boolean
        success_message: Message to emit on success
        error_prefix: Prefix for error messages
    """

    def process_task():
        logger = logging.getLogger('red_plex')
        thread_db = None
        try:
            thread_db = LocalDatabase()

            with app.app_context():
                socketio.emit('status_update', {
                    'message': f'Starting {error_prefix.lower()}...'
                })

            def web_echo(message):
                logger.info(message)
                with app.app_context():
                    socketio.emit('status_update', {'message': message})

            success = task_func(thread_db, web_echo)

            if success:
                with app.app_context():
                    socketio.emit('status_update', {
                        'message': success_message,
                        'finished': True
                    })
            else:
                with app.app_context():
                    socketio.emit('status_update', {
                        'message': f'{error_prefix} failed.',
                        'error': True
                    })

        except Exception as e:
            logger.critical('An unhandled error occurred during %s: %s',
                            error_prefix.lower(),
                            e,
                            exc_info=True)
            with app.app_context():
                socketio.emit('status_update', {
                    'message': f'Error: {str(e)}',
                    'error': True
                })
        finally:
            if thread_db:
                thread_db.close()

    socketio.start_background_task(target=process_task)
