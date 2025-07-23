"""Bookmark route handlers."""
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

# pylint: disable=R0801,W0718
def register_bookmarks_routes(app, socketio, get_db):
    """Register bookmark-related routes."""

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
                    logger = logging.getLogger('red_plex')
                    thread_db = None
                    try:
                        thread_db = LocalDatabase()
                        album_fetch_mode = map_fetch_mode(fetch_mode)

                        with app.app_context():
                            socketio.emit('status_update',
                                          {'message': 'Starting bookmark conversion process...'})

                        gazelle_api = GazelleAPI(site)
                        plex_manager = PlexManager(db=thread_db)
                        processor = CollectionProcessingService(thread_db,
                                                                plex_manager,
                                                                gazelle_api)

                        def web_echo(message):
                            logger.info(message)

                        def web_confirm(message):
                            logger.info('Auto-confirming: %s', message)
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
                    except Exception as e:
                        logger.critical(
                            'An unhandled error occurred during bookmark processing: %s',
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

                socketio.start_background_task(target=process_bookmarks)

                flash('Processing started! Check the status below.', 'info')
                return render_template('bookmarks_convert.html',
                                       processing=True)

            except Exception as e:
                flash(f'Error starting bookmark conversion: {str(e)}', 'error')

        return render_template('bookmarks_convert.html')
