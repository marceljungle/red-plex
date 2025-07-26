"""Remote mappings route handlers."""
import logging

from flask import render_template, request, flash

from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.site_tags.site_tags_use_case import SiteTagsUseCase


# pylint: disable=W0718,R0915
def register_remote_mappings_routes(app, socketio, get_db):
    """Register remote mappings-related routes."""

    @app.route('/remote-mappings')
    def remote_mappings():
        """View remote mappings."""
        try:
            db = get_db()
            # Get basic stats about remote mappings
            mapped_albums, total_tags, total_mappings = db.get_site_tags_stats()
            stats = {
                'mapped_albums': mapped_albums,
                'total_tags': total_tags,
                'total_mappings': total_mappings
            }

            # Get recent mappings for display
            recent_mappings = db.get_recent_site_tag_mappings(limit=20)

            return render_template('remote_mappings.html',
                                   stats=stats,
                                   recent_mappings=recent_mappings)
        except Exception as e:
            flash(f'Error loading remote mappings: {str(e)}', 'error')
            return render_template('remote_mappings.html',
                                   stats={'mapped_albums': 0, 'total_tags': 0, 'total_mappings': 0},
                                   recent_mappings=[])

    @app.route('/remote-mappings/scan', methods=['GET', 'POST'])
    def remote_mappings_scan():
        """Scan albums for remote mappings."""
        if request.method == 'POST':
            try:
                site = request.form.get('site')
                always_skip = request.form.get('always_skip') == 'on'

                if not site:
                    flash('Please select a site.', 'error')
                    return render_template('remote_mappings_scan.html')

                # Start processing in background
                def process_scan():
                    logger = logging.getLogger('red_plex')
                    thread_db = None
                    try:
                        thread_db = LocalDatabase()

                        with app.app_context():
                            socketio.emit('status_update',
                                          {'message': 'Starting remote mappings scan process...'})

                        logger.info("Connecting to Plex server...")
                        plex_manager = PlexManager(db=thread_db)

                        logger.info("Updating album database from Plex...")
                        plex_manager.populate_album_table()

                        gazelle_api = GazelleAPI(site)
                        site_tags_use_case = SiteTagsUseCase(thread_db, plex_manager, gazelle_api)

                        def web_echo(message):
                            logger.info(message)

                        def web_confirm(message):
                            logger.info('Auto-confirming: %s', message)
                            return True

                        site_tags_use_case.scan_albums_for_site_tags(
                            echo_func=web_echo,
                            confirm_func=web_confirm,
                            always_skip=always_skip
                        )

                        with app.app_context():
                            socketio.emit('status_update', {
                                'message': 'Remote mappings scan completed successfully!',
                                'finished': True
                            })

                    except Exception as e:
                        logger.critical('An unhandled error occurred during remote mappings scan: %s',
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

                socketio.start_background_task(target=process_scan)

                flash('Remote mappings scan started! Check the status below.', 'info')
                return render_template('remote_mappings_scan.html',
                                       processing=True)

            except Exception as e:
                flash(f'Error starting remote mappings scan: {str(e)}', 'error')

        return render_template('remote_mappings_scan.html')

