"""Remote mappings route handlers."""
import logging

from flask import render_template, request, flash

from red_plex.infrastructure.gui.routes.utils import (
    get_mapping_stats_and_recent,
    execute_background_task)
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.site_tags.site_tags_use_case import SiteTagsUseCase


# pylint: disable=W0718,R0915
def register_remote_mappings_routes(app, socketio, get_db):
    """Register remote mappings-related routes."""

    @app.route('/remote-mappings')
    def remote_mappings():
        """View remote mappings."""
        stats, recent_mappings, _ = get_mapping_stats_and_recent(get_db)
        return render_template('remote_mappings.html',
                               stats=stats,
                               recent_mappings=recent_mappings)

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

                # Define the scan task function
                def scan_task(thread_db, web_echo):
                    logger = logging.getLogger('red_plex')

                    logger.info("Connecting to Plex server...")
                    plex_manager = PlexManager(db=thread_db)

                    logger.info("Updating album database from Plex...")
                    plex_manager.populate_album_table()

                    gazelle_api = GazelleAPI(site)
                    site_tags_use_case = SiteTagsUseCase(thread_db, plex_manager, gazelle_api)

                    def web_confirm(message):
                        logger.info('Auto-confirming: %s', message)
                        return True

                    return site_tags_use_case.scan_albums_for_site_tags(
                        echo_func=web_echo,
                        confirm_func=web_confirm,
                        always_skip=always_skip
                    )

                # Execute background task
                execute_background_task(
                    socketio=socketio,
                    app=app,
                    task_func=scan_task,
                    success_message="Remote mappings scan completed successfully!",
                    error_prefix="Remote mappings scan"
                )

                flash('Remote mappings scan started! Check the status below.', 'info')
                return render_template('remote_mappings_scan.html',
                                       processing=True)

            except Exception as e:
                flash(f'Error starting remote mappings scan: {str(e)}', 'error')

        return render_template('remote_mappings_scan.html')
