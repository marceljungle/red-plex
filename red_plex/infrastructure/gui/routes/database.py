"""Database route handlers."""
import logging
import os

from flask import render_template, flash, redirect, url_for

from red_plex.infrastructure.cli.utils import update_collections_from_collages
from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.use_case.create_collection.album_fetch_mode import AlbumFetchMode


def register_database_routes(app, socketio, get_db):
    """Register database-related routes."""

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

                    # Get site tags stats
                    cur = db.conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM rating_key_group_id_mappings")
                    stats['site_tags'] = cur.fetchone()[0]
                except Exception as e:
                    logger.warning('Error getting database stats: %s', e)
                    stats = {'albums': 0, 'collages': 0, 'bookmarks': 0, 'site_tags': 0}
            else:
                stats = {'albums': 0, 'collages': 0, 'bookmarks': 0, 'site_tags': 0}

            return render_template('database.html',
                                   db_path=db_path,
                                   db_exists=db_exists,
                                   stats=stats)
        except Exception as e:
            flash(f'Error loading database status: {str(e)}', 'error')
            return render_template('database.html',
                                   db_path="Unknown",
                                   db_exists=False,
                                   stats={'albums': 0,
                                          'collages': 0,
                                          'bookmarks': 0,
                                          'site_tags': 0})

    @app.route('/database/albums/update', methods=['POST'])
    def database_albums_update():
        """Update albums from Plex and update collections from collages."""
        try:
            def update_albums():
                logger = logging.getLogger('red_plex')
                thread_db = None
                try:
                    thread_db = LocalDatabase()

                    with app.app_context():
                        socketio.emit('status_update',
                                      {'message': 'Starting albums update from Plex...'})

                    plex_manager = PlexManager(db=thread_db)

                    plex_manager.populate_album_table()

                    with app.app_context():
                        socketio.emit('status_update',
                                      {'message': 'Albums update completed. '
                                                  'Starting collections update...'})

                    all_collages = thread_db.get_all_collage_collections()
                    if all_collages:
                        logger.info('Updating %s collage collections...', len(all_collages))

                        update_collections_from_collages(
                            local_database=thread_db,
                            collage_list=all_collages,
                            plex_manager=plex_manager,
                            fetch_bookmarks=False,
                            fetch_mode=AlbumFetchMode.TORRENT_NAME
                        )
                        logger.info('Collections update from collages completed!')
                    else:
                        logger.info('No stored collages found to update.')

                    with app.app_context():
                        socketio.emit('status_update', {
                            'message': 'Albums and collections update completed successfully!',
                            'finished': True
                        })
                except Exception as e:
                    logger.critical('An unhandled error occurred during album update: %s',
                                    e,
                                    exc_info=True)
                    with app.app_context():
                        socketio.emit('status_update', {
                            'message': f'Error updating albums: {str(e)}',
                            'error': True
                        })
                finally:
                    if thread_db:
                        thread_db.close()

            socketio.start_background_task(target=update_albums)

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
            elif table == 'site-tags':
                db.reset_tag_mappings()
                flash('Site tags mappings reset successfully!', 'success')
            else:
                flash(f'Unknown table: {table}', 'error')
        except Exception as e:
            flash(f'Error resetting {table} table: {str(e)}', 'error')

        return redirect(url_for('database'))