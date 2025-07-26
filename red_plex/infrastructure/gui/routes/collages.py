"""Collage route handlers."""
import json
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


# pylint: disable=R0801,W0718,R0914,R1702,R0915,R0912,R0911,R1705,R1702
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

                    # Get preview data for each collage
                    preview_data = []
                    for collage in selected_collages:
                        try:
                            gazelle_api = GazelleAPI(collage.site)

                            # Get user info and verify ownership
                            user_info = gazelle_api.get_user_info()
                            if not user_info:
                                continue

                            user_id = user_info.get('id')
                            if not user_id:
                                continue

                            user_collages = gazelle_api.get_user_collages(str(user_id))
                            if not user_collages:
                                continue

                            # Check ownership
                            owns_collage = any(uc.external_id == collage.external_id
                                               for uc in user_collages)
                            if not owns_collage:
                                continue

                            # Get Plex collection items
                            plex_collection = plex_manager.get_collection_by_rating_key(collage.id)
                            if not plex_collection:
                                continue

                            collection_items = plex_collection.items()
                            current_rating_keys = [item.ratingKey for item in collection_items]

                            if not current_rating_keys:
                                continue

                            # Get group IDs for rating keys
                            group_ids = db.get_group_ids_by_rating_keys(current_rating_keys,
                                                                        collage.site.upper())
                            if not group_ids:
                                continue

                            # Get current collage content
                            current_collage_data = gazelle_api.get_collage(collage.external_id)
                            if not current_collage_data:
                                continue

                            current_group_ids = {str(tg.id)
                                                 for tg in current_collage_data.torrent_groups}
                            missing_group_ids = [gid
                                                 for gid in group_ids
                                                 if gid not in current_group_ids]

                            if missing_group_ids:
                                # Get album details for preview
                                album_details = []
                                for group_id in missing_group_ids:
                                    try:
                                        torrent_group = gazelle_api.get_torrent_group(group_id)
                                        if torrent_group:
                                            artists_str = ', '.join(torrent_group.artists) if (
                                                torrent_group.artists) else 'Unknown Artist'
                                            album_info = (f'{artists_str} - '
                                                          f'{torrent_group.album_name}')
                                        else:
                                            album_info = (f'Group ID '
                                                          f'{group_id} (unable to get details)')
                                    except Exception:
                                        album_info = (f'Group ID '
                                                      f'{group_id} (unable to get details)')

                                    album_details.append({
                                        'group_id': group_id,
                                        'display_name': album_info
                                    })

                                preview_data.append({
                                    'collage': collage,
                                    'album_details': album_details
                                })

                        except Exception as e:
                            logging.getLogger('red_plex').error(
                                'Error getting preview for collage %s: %s',
                                collage.name,
                                e)
                            continue

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
                        logger = logging.getLogger('red_plex')
                        thread_db = None
                        try:
                            thread_db = LocalDatabase()

                            with app.app_context():
                                socketio.emit('status_update',
                                              {'message': 'Starting upstream sync process...'})

                            # Process each collage
                            for collage_id, group_ids in albums_data.items():
                                collage = thread_db.get_collage_collection(collage_id)
                                if not collage:
                                    continue

                                logger.info('Syncing collage "%s" with %d albums...',
                                            collage.name, len(group_ids))

                                try:
                                    gazelle_api = GazelleAPI(collage.site)
                                    result = gazelle_api.add_to_collage(collage.external_id,
                                                                        group_ids)

                                    if result and result.get('status') == 'success':
                                        response_data = result.get('response', {})
                                        added_count = len(response_data.get('groupsadded',
                                                                            []))
                                        rejected_count = len(response_data.get('groupsrejected',
                                                                               []))
                                        duplicated_count = len(response_data.get('groupsduplicated',
                                                                                 []))

                                        logger.info('Collage "%s": %d added, '
                                                    '%d rejected, %d duplicated',
                                                    collage.name,
                                                    added_count,
                                                    rejected_count,
                                                    duplicated_count)
                                    else:
                                        logger.error('Failed to sync collage "%s": %s',
                                                     collage.name, result)

                                except Exception as e:
                                    logger.error('Error syncing collage "%s": %s', collage.name, e)

                            with app.app_context():
                                socketio.emit('status_update', {
                                    'message': 'Upstream sync completed!',
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
                    return render_template('collages_upstream_sync.html',
                                           collages=[],
                                           processing=True)

            except Exception as e:
                flash(f'Error in upstream sync: {str(e)}', 'error')

        return render_template('collages_upstream_sync.html', collages=[])
