"""Collage route handlers."""
import logging

from flask import render_template, request, flash

from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.infrastructure.service.collection_processor import CollectionProcessingService
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode


def map_fetch_mode(fetch_mode_str) -> AlbumFetchMode:
    """Map the fetch mode string to an AlbumFetchMode enum."""
    if fetch_mode_str == 'query':
        return AlbumFetchMode.QUERY
    return AlbumFetchMode.TORRENT_NAME


def register_collages_routes(app, socketio, get_db):
    """Register collage-related routes."""

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
                    logger = logging.getLogger('red_plex')
                    thread_db = None
                    try:
                        thread_db = LocalDatabase()
                        album_fetch_mode = map_fetch_mode(fetch_mode)

                        with app.app_context():
                            socketio.emit('status_update',
                                          {'message': 'Starting collage conversion process...'})

                        logger.info("WebSocket logging is configured and ready.")
                        logger.info("Connecting to Plex server...")

                        try:
                            plex_manager = PlexManager(db=thread_db)
                        except Exception as e:
                            logger.error('Failed to initialize PlexManager: %s', e)
                            with app.app_context():
                                socketio.emit('status_update', {
                                    'message': f'Failed to connect to Plex server: {str(e)}',
                                    'error': True
                                })
                            return

                        logger.info("Successfully connected to Plex server.")

                        gazelle_api = GazelleAPI(site)
                        processor = CollectionProcessingService(thread_db,
                                                                plex_manager,
                                                                gazelle_api)

                        def web_echo(message):
                            logger.info(message)

                        def web_confirm(message):
                            logger.info('Auto-confirming: %s', message)
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

                    except Exception as e:
                        logger.critical('An unhandled error occurred: %s', e, exc_info=True)
                        with app.app_context():
                            socketio.emit('status_update', {
                                'message': f'Error: {str(e)}',
                                'error': True
                            })
                    finally:
                        if thread_db:
                            thread_db.close()

                socketio.start_background_task(target=process_collages)

                flash('Processing started! Check the status below.', 'info')
                return render_template('collages_convert.html',
                                       processing=True)

            except Exception as e:
                flash(f'Error starting collage conversion: {str(e)}', 'error')

        return render_template('collages_convert.html')