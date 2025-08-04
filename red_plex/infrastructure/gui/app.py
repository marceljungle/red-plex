"""Flask web application for red-plex GUI."""
import logging
import os

from flask import Flask, render_template, g
from flask_socketio import SocketIO

from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.gui.routes.bookmarks import register_bookmarks_routes
from red_plex.infrastructure.gui.routes.collages import register_collages_routes
from red_plex.infrastructure.gui.routes.config import register_config_routes
from red_plex.infrastructure.gui.routes.database import register_database_routes
from red_plex.infrastructure.gui.routes.remote_mappings import register_remote_mappings_routes
from red_plex.infrastructure.gui.routes.site_tags import register_site_tags_routes
from red_plex.infrastructure.logger.logger import configure_logger


# pylint: disable=W0703,W0718,R0914,R0915,W0511
class WebSocketHandler(logging.Handler):
    """Custom logging handler that sends log messages via WebSocket."""

    def __init__(self, socketio_instance, app_instance):
        super().__init__()
        self.socketio = socketio_instance
        self.app = app_instance

    def emit(self, record):
        """Emit a log record via WebSocket."""
        try:
            msg = self.format(record)
            with self.app.app_context():
                self.socketio.emit('status_update', {'message': msg})
        except Exception:
            # Avoid recursion if there's an error in the handler
            pass


def get_db():
    """Get database connection for current thread."""
    if 'db' not in g:
        g.db = LocalDatabase()
    return g.db


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.secret_key = os.urandom(24)
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

    configure_logger()

    logger = logging.getLogger('red_plex')

    ws_handler = WebSocketHandler(socketio, app)

    if logger.handlers:
        ws_handler.setFormatter(logger.handlers[0].formatter)
    ws_handler.setLevel(logger.level)

    logger.addHandler(ws_handler)

    logger.propagate = False

    @app.teardown_appcontext
    def close_db(error):
        """Close database connection."""
        db = g.pop('db', None)
        if db is not None:
            db.close()

        if error is not None:
            logger.error("Error during request teardown: %s", error)

    @app.route('/')
    def index():
        """Home page."""
        return render_template('index.html')

    # Register all route modules
    register_config_routes(app)
    register_collages_routes(app, socketio, get_db)
    register_bookmarks_routes(app, socketio, get_db)
    register_remote_mappings_routes(app, socketio, get_db)
    register_site_tags_routes(app, socketio, get_db)
    register_database_routes(app, socketio, get_db)

    @socketio.on('connect')
    def handle_connect():
        """Handle WebSocket connection."""

    return app, socketio
