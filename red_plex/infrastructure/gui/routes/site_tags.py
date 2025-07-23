"""Site tags route handlers."""
import logging

from flask import render_template, request, flash

from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.site_tags.site_tags_use_case import SiteTagsUseCase


def register_site_tags_routes(app, socketio, get_db):
    """Register site tags-related routes."""

    @app.route('/site-tags')
    def site_tags():
        """View site tags mappings."""
        try:
            db = get_db()
            # Get basic stats about site tag mappings
            mapped_albums, total_tags, total_mappings = db.get_site_tags_stats()
            stats = {
                'mapped_albums': mapped_albums,
                'total_tags': total_tags,
                'total_mappings': total_mappings
            }

            # Get recent mappings for display
            recent_mappings = db.get_recent_site_tag_mappings(limit=20)

            return render_template('site_tags.html',
                                   stats=stats,
                                   recent_mappings=recent_mappings)
        except Exception as e:
            flash(f'Error loading site tags: {str(e)}', 'error')
            return render_template('site_tags.html',
                                   stats={'mapped_albums': 0, 'total_tags': 0, 'total_mappings': 0},
                                   recent_mappings=[])

    @app.route('/site-tags/scan', methods=['GET', 'POST'])
    def site_tags_scan():
        """Scan albums for site tag mappings."""
        if request.method == 'POST':
            try:
                site = request.form.get('site')
                always_skip = request.form.get('always_skip') == 'on'

                if not site:
                    flash('Please select a site.', 'error')
                    return render_template('site_tags_scan.html')

                # Start processing in background
                def process_scan():
                    logger = logging.getLogger('red_plex')
                    thread_db = None
                    try:
                        thread_db = LocalDatabase()

                        with app.app_context():
                            socketio.emit('status_update',
                                          {'message': 'Starting site tags scan process...'})

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
                                'message': 'Site tags scan completed successfully!',
                                'finished': True
                            })

                    except Exception as e:
                        logger.critical('An unhandled error occurred during site tags scan: %s',
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

                flash('Site tags scan started! Check the status below.', 'info')
                return render_template('site_tags_scan.html',
                                       processing=True)

            except Exception as e:
                flash(f'Error starting site tags scan: {str(e)}', 'error')

        return render_template('site_tags_scan.html')

    @app.route('/site-tags/convert', methods=['GET', 'POST'])
    def site_tags_convert():
        """Convert site tags to Plex collections."""
        if request.method == 'POST':
            try:
                tags = request.form.get('tags', '').strip()
                collection_name = request.form.get('collection_name', '').strip()

                if not tags:
                    flash('Please provide tags.', 'error')
                    return render_template('site_tags_convert.html')

                if not collection_name:
                    flash('Please provide a collection name.', 'error')
                    return render_template('site_tags_convert.html')

                # Parse tags
                tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]

                # Start processing in background
                def process_convert():
                    logger = logging.getLogger('red_plex')
                    thread_db = None
                    try:
                        thread_db = LocalDatabase()

                        with app.app_context():
                            socketio.emit('status_update',
                                          {'message':
                                               'Starting site tags to collection conversion...'})

                        logger.info("Connecting to Plex server...")
                        plex_manager = PlexManager(db=thread_db)

                        site_tags_use_case = SiteTagsUseCase(thread_db, plex_manager)

                        def web_echo(message):
                            logger.info(message)

                        success = site_tags_use_case.create_collection_from_tags(
                            tags=tag_list,
                            collection_name=collection_name,
                            echo_func=web_echo
                        )

                        if success:
                            with app.app_context():
                                socketio.emit('status_update', {
                                    'message': 'Collection created successfully!',
                                    'finished': True
                                })
                        else:
                            with app.app_context():
                                socketio.emit('status_update', {
                                    'message': 'Collection creation failed.',
                                    'error': True
                                })

                    except Exception as e:
                        logger.critical('An unhandled error occurred during conversion: %s',
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

                socketio.start_background_task(target=process_convert)

                flash('Collection creation started! Check the status below.', 'info')
                return render_template('site_tags_convert.html',
                                       processing=True)

            except Exception as e:
                flash(f'Error starting collection creation: {str(e)}', 'error')

        return render_template('site_tags_convert.html')