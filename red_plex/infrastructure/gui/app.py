"""Flask web application for red-plex GUI."""
import os
import threading
import logging
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, g
from flask_socketio import SocketIO, emit
import yaml

from red_plex.infrastructure.config.config import (
    CONFIG_FILE_PATH,
    load_config,
    save_config,
    ensure_config_exists
)
from red_plex.infrastructure.config.models import Configuration
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger, configure_logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.infrastructure.service.collection_processor import CollectionProcessingService
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode
from red_plex.infrastructure.cli.cli import update_collections_from_collages


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
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    # Set up WebSocket logging handler
    ws_handler = WebSocketHandler(socketio, app)
    ws_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ws_handler.setFormatter(formatter)
    
    @app.teardown_appcontext
    def close_db(error):
        """Close database connection."""
        db = g.pop('db', None)
        if db is not None:
            db.close()
    
    def map_fetch_mode(fetch_mode_str) -> AlbumFetchMode:
        """Map the fetch mode string to an AlbumFetchMode enum."""
        if fetch_mode_str == 'query':
            return AlbumFetchMode.QUERY
        return AlbumFetchMode.TORRENT_NAME

    @app.route('/')
    def index():
        """Home page."""
        return render_template('index.html')

    @app.route('/config')
    def config_view():
        """View configuration."""
        try:
            config_data = load_config()
            return render_template('config.html', config=config_data.to_dict())
        except Exception as e:
            flash(f'Error loading configuration: {str(e)}', 'error')
            return render_template('config.html', config={})

    @app.route('/config/edit', methods=['GET', 'POST'])
    def config_edit():
        """Edit configuration."""
        if request.method == 'POST':
            try:
                config_data = request.form.to_dict()
                
                # Convert nested structure for site configs
                sites_config = {}
                for key, value in config_data.items():
                    if key.startswith('RED_') or key.startswith('OPS_'):
                        site, field = key.split('_', 1)
                        if site not in sites_config:
                            sites_config[site] = {}
                        if field == 'RATE_LIMIT_CALLS':
                            sites_config[site].setdefault('RATE_LIMIT', {})['calls'] = int(value)
                        elif field == 'RATE_LIMIT_SECONDS':
                            sites_config[site].setdefault('RATE_LIMIT', {})['seconds'] = int(value)
                        else:
                            sites_config[site][field] = value
                
                # Build final config
                final_config = {
                    'LOG_LEVEL': config_data.get('LOG_LEVEL', 'INFO'),
                    'PLEX_URL': config_data.get('PLEX_URL', ''),
                    'PLEX_TOKEN': config_data.get('PLEX_TOKEN', ''),
                    'SECTION_NAME': config_data.get('SECTION_NAME', 'Music'),
                }
                final_config.update(sites_config)
                
                # Save configuration
                config = Configuration.from_dict(final_config)
                save_config(config)
                
                flash('Configuration saved successfully!', 'success')
                return redirect(url_for('config_view'))
            except Exception as e:
                flash(f'Error saving configuration: {str(e)}', 'error')
        
        try:
            config_data = load_config()
            return render_template('config_edit.html', config=config_data.to_dict())
        except Exception as e:
            flash(f'Error loading configuration: {str(e)}', 'error')
            return render_template('config_edit.html', config={})

    @app.route('/collages')
    def collages():
        """View collages."""
        try:
            db = get_db()
            collages = db.get_all_collage_collections()
            return render_template('collages.html', collages=collages)
        except Exception as e:
            flash(f'Error loading collages: {str(e)}', 'error')
            return render_template('collages.html', collages=[])

    @app.route('/collages/convert', methods=['GET', 'POST'])
    def collages_convert():
        """Convert collages."""
        if request.method == 'POST':
            try:
                collage_ids = request.form.get('collage_ids', '').split()
                site = request.form.get('site')
                fetch_mode = request.form.get('fetch_mode', 'torrent_name')
                
                if not collage_ids:
                    flash('Please provide at least one collage ID.', 'error')
                    return render_template('collages_convert.html')
                
                if not site:
                    flash('Please select a site.', 'error')
                    return render_template('collages_convert.html')
                
                # Start processing in background
                def process_collages():
                    red_plex_logger = None
                    root_logger = None
                    thread_db = None
                    try:
                        # Create new database connection for this thread
                        thread_db = LocalDatabase()
                        album_fetch_mode = map_fetch_mode(fetch_mode)
                        
                        with app.app_context():
                            socketio.emit('status_update', {'message': 'Starting collage conversion process...'})
                        
                        # Set up logging to capture all messages BEFORE any logging happens
                        # Add handler to the red_plex logger (where PlexManager logs go)
                        red_plex_logger = logging.getLogger('red_plex')
                        # Ensure the handler isn't already added to avoid duplicates
                        if ws_handler not in red_plex_logger.handlers:
                            red_plex_logger.addHandler(ws_handler)
                            # Make sure logger level is not higher than INFO
                            if red_plex_logger.level > logging.INFO:
                                red_plex_logger.setLevel(logging.INFO)
                        
                        # Also add to root logger to catch any other messages
                        root_logger = logging.getLogger()
                        if ws_handler not in root_logger.handlers:
                            root_logger.addHandler(ws_handler)
                            if root_logger.level > logging.INFO:
                                root_logger.setLevel(logging.INFO)
                        
                        # Test WebSocket logging is working
                        with app.app_context():
                            socketio.emit('status_update', {'message': 'WebSocket logging configured'})
                        
                        # Test that red_plex logger is working via WebSocket
                        red_plex_logger.info('Testing red_plex logger WebSocket integration')
                        
                        # Try to create PlexManager - this might fail if Plex server is not accessible
                        with app.app_context():
                            socketio.emit('status_update', {'message': 'Connecting to Plex server...'})
                        
                        try:
                            plex_manager = PlexManager(db=thread_db)
                        except Exception as e:
                            with app.app_context():
                                socketio.emit('status_update', {
                                    'message': f'Failed to connect to Plex server: {str(e)}', 
                                    'error': True
                                })
                            logger.error(f'Failed to initialize PlexManager: {str(e)}')
                            return
                        
                        with app.app_context():
                            socketio.emit('status_update', {'message': 'Successfully connected to Plex server'})
                        
                        gazelle_api = GazelleAPI(site)
                        processor = CollectionProcessingService(thread_db, plex_manager, gazelle_api)
                        
                        # Custom echo function for web interface
                        def web_echo(message):
                            with app.app_context():
                                socketio.emit('status_update', {'message': message})
                            logger.info(message)
                        
                        def web_confirm(message):
                            # For web interface, we'll assume 'yes' for confirmations
                            web_echo(f"Auto-confirming: {message}")
                            return True
                        
                        processor.process_collages(
                            collage_ids=collage_ids,
                            album_fetch_mode=album_fetch_mode,
                            echo_func=web_echo,
                            confirm_func=web_confirm
                        )
                        
                        with app.app_context():
                            socketio.emit('status_update', {
                                'message': 'Collage processing completed successfully!', 
                                'finished': True
                            })
                        
                        # Remove the handler to avoid memory leaks
                        if red_plex_logger:
                            red_plex_logger.removeHandler(ws_handler)
                        if root_logger:
                            root_logger.removeHandler(ws_handler)
                        if thread_db:
                            thread_db.close()
                    except Exception as e:
                        with app.app_context():
                            socketio.emit('status_update', {
                                'message': f'Error: {str(e)}', 
                                'error': True
                            })
                        # Clean up resources
                        if red_plex_logger:
                            red_plex_logger.removeHandler(ws_handler)
                        if root_logger:
                            root_logger.removeHandler(ws_handler)
                        if thread_db:
                            thread_db.close()
                
                thread = threading.Thread(target=process_collages)
                thread.daemon = True
                thread.start()
                
                flash('Processing started! Check the status below.', 'info')
                return render_template('collages_convert.html', processing=True)
                
            except Exception as e:
                flash(f'Error starting collage conversion: {str(e)}', 'error')
        
        return render_template('collages_convert.html')

    @app.route('/bookmarks')
    def bookmarks():
        """View bookmarks."""
        try:
            db = get_db()
            bookmarks = db.get_all_bookmark_collections()
            return render_template('bookmarks.html', bookmarks=bookmarks)
        except Exception as e:
            flash(f'Error loading bookmarks: {str(e)}', 'error')
            return render_template('bookmarks.html', bookmarks=[])

    @app.route('/bookmarks/convert', methods=['GET', 'POST'])
    def bookmarks_convert():
        """Convert bookmarks."""
        if request.method == 'POST':
            try:
                site = request.form.get('site')
                fetch_mode = request.form.get('fetch_mode', 'torrent_name')
                
                if not site:
                    flash('Please select a site.', 'error')
                    return render_template('bookmarks_convert.html')
                
                # Start processing in background
                def process_bookmarks():
                    red_plex_logger = None
                    root_logger = None
                    thread_db = None
                    try:
                        # Create new database connection for this thread
                        thread_db = LocalDatabase()
                        album_fetch_mode = map_fetch_mode(fetch_mode)
                        
                        with app.app_context():
                            socketio.emit('status_update', {'message': 'Starting bookmark conversion process...'})
                        
                        # Set up logging to capture all messages BEFORE any logging happens
                        # Add handler to the red_plex logger (where PlexManager logs go)
                        red_plex_logger = logging.getLogger('red_plex')
                        # Ensure the handler isn't already added to avoid duplicates
                        if ws_handler not in red_plex_logger.handlers:
                            red_plex_logger.addHandler(ws_handler)
                            # Make sure logger level is not higher than INFO
                            if red_plex_logger.level > logging.INFO:
                                red_plex_logger.setLevel(logging.INFO)
                        
                        # Also add to root logger to catch any other messages
                        root_logger = logging.getLogger()
                        if ws_handler not in root_logger.handlers:
                            root_logger.addHandler(ws_handler)
                            if root_logger.level > logging.INFO:
                                root_logger.setLevel(logging.INFO)
                        
                        # Test WebSocket logging is working
                        with app.app_context():
                            socketio.emit('status_update', {'message': 'WebSocket logging configured'})
                        
                        # Test that red_plex logger is working via WebSocket
                        red_plex_logger.info('Testing red_plex logger WebSocket integration')
                        
                        # Try to create PlexManager - this might fail if Plex server is not accessible
                        with app.app_context():
                            socketio.emit('status_update', {'message': 'Connecting to Plex server...'})
                        
                        try:
                            plex_manager = PlexManager(db=thread_db)
                        except Exception as e:
                            with app.app_context():
                                socketio.emit('status_update', {
                                    'message': f'Failed to connect to Plex server: {str(e)}', 
                                    'error': True
                                })
                            logger.error(f'Failed to initialize PlexManager: {str(e)}')
                            return
                        
                        with app.app_context():
                            socketio.emit('status_update', {'message': 'Successfully connected to Plex server'})
                        
                        gazelle_api = GazelleAPI(site)
                        processor = CollectionProcessingService(thread_db, plex_manager, gazelle_api)
                        
                        # Custom echo function for web interface
                        def web_echo(message):
                            with app.app_context():
                                socketio.emit('status_update', {'message': message})
                            logger.info(message)
                        
                        def web_confirm(message):
                            # For web interface, we'll assume 'yes' for confirmations
                            web_echo(f"Auto-confirming: {message}")
                            return True
                        
                        processor.process_bookmarks(
                            album_fetch_mode=album_fetch_mode,
                            echo_func=web_echo,
                            confirm_func=web_confirm
                        )
                        
                        with app.app_context():
                            socketio.emit('status_update', {
                                'message': 'Bookmark processing completed successfully!', 
                                'finished': True
                            })
                        
                        # Remove the handler to avoid memory leaks
                        if red_plex_logger:
                            red_plex_logger.removeHandler(ws_handler)
                        if root_logger:
                            root_logger.removeHandler(ws_handler)
                        if thread_db:
                            thread_db.close()
                    except Exception as e:
                        with app.app_context():
                            socketio.emit('status_update', {
                                'message': f'Error: {str(e)}', 
                                'error': True
                            })
                        # Clean up resources
                        if red_plex_logger:
                            red_plex_logger.removeHandler(ws_handler)
                        if root_logger:
                            root_logger.removeHandler(ws_handler)
                        if thread_db:
                            thread_db.close()
                
                thread = threading.Thread(target=process_bookmarks)
                thread.daemon = True
                thread.start()
                
                flash('Processing started! Check the status below.', 'info')
                return render_template('bookmarks_convert.html', processing=True)
                
            except Exception as e:
                flash(f'Error starting bookmark conversion: {str(e)}', 'error')
        
        return render_template('bookmarks_convert.html')

    @app.route('/database')
    def database():
        """View database status."""
        try:
            db = get_db()
            db_path = db.db_path
            db_exists = os.path.exists(db_path)
            
            # Get some basic stats
            stats = {}
            if db_exists:
                try:
                    stats['albums'] = len(db.get_all_albums())
                    stats['collages'] = len(db.get_all_collage_collections())
                    stats['bookmarks'] = len(db.get_all_bookmark_collections())
                except:
                    stats = {'albums': 0, 'collages': 0, 'bookmarks': 0}
            else:
                stats = {'albums': 0, 'collages': 0, 'bookmarks': 0}
            
            return render_template('database.html', 
                                 db_path=db_path, 
                                 db_exists=db_exists, 
                                 stats=stats)
        except Exception as e:
            flash(f'Error loading database status: {str(e)}', 'error')
            return render_template('database.html', 
                                 db_path="Unknown", 
                                 db_exists=False, 
                                 stats={})

    @app.route('/database/albums/update', methods=['POST'])
    def database_albums_update():
        """Update albums from Plex and update collections from collages."""
        try:
            def update_albums():
                red_plex_logger = None
                root_logger = None
                thread_db = None
                try:
                    # Create new database connection for this thread
                    thread_db = LocalDatabase()
                    
                    with app.app_context():
                        socketio.emit('status_update', {'message': 'Starting albums update from Plex...'})
                    
                    # Set up logging to capture all messages BEFORE any logging happens
                    # Add handler to the red_plex logger (where PlexManager logs go)
                    red_plex_logger = logging.getLogger('red_plex')
                    # Ensure the handler isn't already added to avoid duplicates
                    if ws_handler not in red_plex_logger.handlers:
                        red_plex_logger.addHandler(ws_handler)
                        # Make sure logger level is not higher than INFO
                        if red_plex_logger.level > logging.INFO:
                            red_plex_logger.setLevel(logging.INFO)
                    
                    # Also add to root logger to catch any other messages
                    root_logger = logging.getLogger()
                    if ws_handler not in root_logger.handlers:
                        root_logger.addHandler(ws_handler)
                        if root_logger.level > logging.INFO:
                            root_logger.setLevel(logging.INFO)
                    
                    # Test WebSocket logging is working
                    with app.app_context():
                        socketio.emit('status_update', {'message': 'WebSocket logging configured'})
                    
                    # Test that red_plex logger is working via WebSocket
                    red_plex_logger.info('Testing red_plex logger WebSocket integration')
                    
                    # Try to create PlexManager - this might fail if Plex server is not accessible
                    with app.app_context():
                        socketio.emit('status_update', {'message': 'Connecting to Plex server...'})
                    
                    try:
                        plex_manager = PlexManager(db=thread_db)
                    except Exception as e:
                        with app.app_context():
                            socketio.emit('status_update', {
                                'message': f'Failed to connect to Plex server: {str(e)}', 
                                'error': True
                            })
                        logger.error(f'Failed to initialize PlexManager: {str(e)}')
                        return
                    
                    with app.app_context():
                        socketio.emit('status_update', {'message': 'Successfully connected to Plex server'})
                    
                    # Step 1: Update albums from Plex
                    plex_manager.populate_album_table()
                    
                    with app.app_context():
                        socketio.emit('status_update', {'message': 'Albums update completed. Starting collections update...'})
                    
                    # Step 2: Update collections from stored collages (same as CLI update command)
                    all_collages = thread_db.get_all_collage_collections()
                    if all_collages:
                        with app.app_context():
                            socketio.emit('status_update', {'message': f'Updating {len(all_collages)} collage collections...'})
                        
                        update_collections_from_collages(
                            local_database=thread_db,
                            collage_list=all_collages,
                            plex_manager=plex_manager,
                            fetch_bookmarks=False,
                            fetch_mode=AlbumFetchMode.TORRENT_NAME
                        )
                        
                        with app.app_context():
                            socketio.emit('status_update', {'message': 'Collections update completed!'})
                    else:
                        with app.app_context():
                            socketio.emit('status_update', {'message': 'No stored collages found to update.'})
                    
                    with app.app_context():
                        socketio.emit('status_update', {
                            'message': 'Albums and collections update completed successfully!', 
                            'finished': True
                        })
                    
                    # Remove the handler to avoid memory leaks
                    if red_plex_logger:
                        red_plex_logger.removeHandler(ws_handler)
                    if root_logger:
                        root_logger.removeHandler(ws_handler)
                    if thread_db:
                        thread_db.close()
                except Exception as e:
                    with app.app_context():
                        socketio.emit('status_update', {
                            'message': f'Error updating albums: {str(e)}', 
                            'error': True
                        })
                    # Clean up resources
                    if red_plex_logger:
                        red_plex_logger.removeHandler(ws_handler)
                    if root_logger:
                        root_logger.removeHandler(ws_handler)
                    if thread_db:
                        thread_db.close()
            
            thread = threading.Thread(target=update_albums)
            thread.daemon = True
            thread.start()
            
            flash('Albums and collections update started!', 'info')
        except Exception as e:
            flash(f'Error starting albums update: {str(e)}', 'error')
        
        return redirect(url_for('database'))

    @app.route('/database/<table>/reset', methods=['POST'])
    def database_reset(table):
        """Reset database table."""
        try:
            db = get_db()
            if table == 'albums':
                db.reset_albums()
                flash('Albums table reset successfully!', 'success')
            elif table == 'collages':
                db.reset_collage_collections()
                flash('Collages table reset successfully!', 'success')
            elif table == 'bookmarks':
                db.reset_bookmark_collections()
                flash('Bookmarks table reset successfully!', 'success')
            else:
                flash(f'Unknown table: {table}', 'error')
        except Exception as e:
            flash(f'Error resetting {table} table: {str(e)}', 'error')
        
        return redirect(url_for('database'))

    @socketio.on('connect')
    def handle_connect():
        """Handle WebSocket connection."""
        emit('status_update', {'message': 'Connected to red-plex server'})

    return app, socketio


def run_gui(host='127.0.0.1', port=5000, debug=False):
    """Run the Flask GUI application."""
    configure_logger()
    app, socketio = create_app()
    
    print(f"Starting red-plex GUI server at http://{host}:{port}")
    print("Press Ctrl+C to stop the server")
    
    try:
        socketio.run(app, host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error running server: {e}")


if __name__ == '__main__':
    run_gui(debug=True)