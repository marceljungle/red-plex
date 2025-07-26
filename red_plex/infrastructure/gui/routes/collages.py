"""Collage route handlers."""
import json
import logging

from flask import render_template, request, flash

from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.infrastructure.service.collection_processor import CollectionProcessingService
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode
from red_plex.use_case.upstream_sync.upstream_sync_use_case import UpstreamSyncUseCase

logger = logging.getLogger('red_plex')


def map_fetch_mode(fetch_mode_str) -> AlbumFetchMode:
    """Map the fetch mode string to an AlbumFetchMode enum."""
    if fetch_mode_str == 'query':
        return AlbumFetchMode.QUERY
    return AlbumFetchMode.TORRENT_NAME


# pylint: disable=R0801,W0718,R0914,R1702,R0915,R0912,R0911,R1705,R1702
def register_collages_routes(app, socketio, get_db):
    """Register collage-related routes."""

    @app.route('/collages')
    def collages():
        """View collages."""
        try:
            db = get_db()
            collages = db.get_all_collage_collections()

            # Determine which collages the user owns for each site
            user_owned_collages = {}  # site -> set of external_ids

            # Group collages by site to minimize API calls
            collages_by_site = {}
            for collage in collages:
                site = collage.site
                if site not in collages_by_site:
                    collages_by_site[site] = []
                collages_by_site[site].append(collage)

            # For each site, check user ownership
            for site, _ in collages_by_site.items():
                try:
                    api = GazelleAPI(site)
                    user_info = api.get_user_info()

                    if user_info and 'id' in user_info:
                        user_id = str(user_info['id'])
                        user_collages = api.get_user_collages(user_id)

                        if user_collages is not None:
                            # Extract external IDs of owned collages
                            owned_external_ids = {uc.external_id for uc in user_collages}
                            user_owned_collages[site] = owned_external_ids
                        else:
                            # get_user_collages returned None (not supported for this site)
                            user_owned_collages[site] = set()
                    else:
                        # Failed to get user info
                        user_owned_collages[site] = set()

                except Exception as e:
                    logger.error('Error checking collage ownership for site %s: %s', site, e)
                    # On error, assume no ownership
                    user_owned_collages[site.upper()] = set()
            return render_template('collages.html',
                                   collages=collages,
                                   user_owned_collages=user_owned_collages)
        except Exception as e:
            flash(f'Error loading collages: {str(e)}', 'error')
            logger.error('Error loading collages: %s', e, exc_info=True)
            return render_template('collages.html', collages=[], user_owned_collages={})

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

    @app.route('/collages/upstream-sync', methods=['GET', 'POST'])
    def collages_upstream_sync():
        """Sync collections to upstream collages."""
        if request.method == 'GET':
            try:
                db = get_db()
                collages = db.get_all_collage_collections()

                # Get collage_ids from query parameters for specific collages
                collage_ids_param = request.args.get('collage_ids', '')
                selected_collage_ids = []
                if collage_ids_param:
                    selected_collage_ids = collage_ids_param.split(',')

                return render_template('collages_upstream_sync.html',
                                       collages=collages,
                                       selected_collage_ids=selected_collage_ids)
            except Exception as e:
                flash(f'Error loading collages: {str(e)}', 'error')
                return render_template('collages_upstream_sync.html', collages=[])

        elif request.method == 'POST':
            try:
                action = request.form.get('action')

                if action == 'get_preview':
                    # Get preview of what would be synced
                    collage_ids = request.form.getlist('collage_ids')
                    if not collage_ids:
                        flash('Please select at least one collage.', 'error')
                        return render_template('collages_upstream_sync.html', collages=[])

                    db = get_db()
                    plex_manager = PlexManager(db=db)

                    # Get selected collages
                    selected_collages = []
                    for collage_id in collage_ids:
                        # collage_id is actually the rating_key (Collection.id)
                        collage = db.get_collage_collection(collage_id)
                        if collage:
                            selected_collages.append(collage)

                    # Use the upstream sync use case to get preview
                    logger.info('Getting upstream sync preview for collages: %s', collage_ids)
                    upstream_sync = UpstreamSyncUseCase(db, plex_manager)
                    preview_response = upstream_sync.get_sync_preview(selected_collages)

                    if not preview_response.success:
                        flash(f'Error getting sync preview: {preview_response.error_message}',
                              'error')
                        return render_template('collages_upstream_sync.html',
                                               collages=db.get_all_collage_collections())

                    # Convert response to template format
                    preview_data = []
                    for collage_preview in preview_response.preview_data:
                        collage = db.get_collage_collection(collage_preview.collage_id)
                        if collage:
                            album_details = [
                                {
                                    'group_id': album.group_id,
                                    'display_name': album.display_name
                                }
                                for album in collage_preview.albums_to_add
                            ]
                            preview_data.append({
                                'collage': collage,
                                'album_details': album_details
                            })

                    return render_template('collages_upstream_sync.html',
                                           collages=db.get_all_collage_collections(),
                                           preview_data=preview_data,
                                           show_confirmation=True)

                elif action == 'confirm_sync':
                    # Perform the actual sync with selected albums
                    selected_albums = request.form.get('selected_albums', '')

                    if not selected_albums:
                        flash('No albums selected for sync.', 'info')
                        return render_template('collages_upstream_sync.html', collages=[])

                    # Parse selected albums data (JSON format)
                    try:
                        albums_data = json.loads(selected_albums)
                    except json.JSONDecodeError:
                        flash('Invalid album selection data.', 'error')
                        return render_template('collages_upstream_sync.html', collages=[])

                    # Start sync process in background
                    def process_upstream_sync():
                        thread_db = None
                        try:
                            thread_db = LocalDatabase()
                            plex_manager = PlexManager(db=thread_db)

                            with app.app_context():
                                socketio.emit('status_update',
                                              {'message': 'Starting upstream sync process...'})

                            # Get collages to sync
                            collages_to_sync = []
                            for collage_id in albums_data.keys():
                                collage = thread_db.get_collage_collection(collage_id)
                                if collage:
                                    collages_to_sync.append(collage)

                            if not collages_to_sync:
                                logger.warning('No valid collages found for sync')
                                return

                            # Use upstream sync use case
                            upstream_sync = UpstreamSyncUseCase(thread_db, plex_manager)
                            sync_response = upstream_sync.sync_collections_upstream(
                                collages_to_sync, albums_data)

                            # Log results
                            for collage_id, result in sync_response.sync_results.items():
                                collage = thread_db.get_collage_collection(collage_id)
                                collage_name = collage.name if collage else collage_id

                                if result.get('success', False):
                                    added = result.get('added', 0)
                                    rejected = result.get('rejected', 0)
                                    duplicated = result.get('duplicated', 0)
                                    logger.info('Collage "%s": %d added, %d rejected, '
                                                '%d duplicated',
                                                collage_name, added, rejected, duplicated)
                                else:
                                    logger.error('Failed to sync collage "%s": %s',
                                                 collage_name, result.get('error', 'Unknown error'))

                            with app.app_context():
                                socketio.emit('status_update', {
                                    'message': f'Upstream sync completed! '
                                               f'{sync_response.synced_collages}'
                                               f'/{sync_response.total_collages}'
                                               f' collages synced successfully.',
                                    'finished': True
                                })

                        except Exception as e:
                            logger.critical('Error in upstream sync: %s', e, exc_info=True)
                            with app.app_context():
                                socketio.emit('status_update', {
                                    'message': f'Error: {str(e)}',
                                    'error': True
                                })
                        finally:
                            if thread_db:
                                thread_db.close()

                    socketio.start_background_task(target=process_upstream_sync)
                    flash('Upstream sync started! Check the status below.', 'info')
                    db = LocalDatabase()
                    all_collages = db.get_all_collage_collections()
                    db.close()
                    return render_template('collages_upstream_sync.html',
                                           collages=all_collages,
                                           processing=True)

            except Exception as e:
                flash(f'Error in upstream sync: {str(e)}', 'error')

        return render_template('collages_upstream_sync.html', collages=[])
