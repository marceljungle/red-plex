"""Site tags route handlers."""

from flask import render_template, request, flash

from red_plex.infrastructure.gui.routes.utils import (
    get_mapping_stats_and_recent,
    execute_background_task)
from red_plex.infrastructure.plex.plex_manager import PlexManager
from red_plex.use_case.site_tags.site_tags_use_case import SiteTagsUseCase


# pylint: disable=W0718,R0915
def register_site_tags_routes(app, socketio, get_db):
    """Register site tags-related routes."""

    @app.route('/site-tags')
    def site_tags():
        """View site tags functionality."""
        stats, recent_mappings, _ = get_mapping_stats_and_recent(get_db)
        return render_template('site_tags.html',
                               stats=stats,
                               recent_mappings=recent_mappings)

    @app.route('/site-tags/convert', methods=['GET', 'POST'])
    def site_tags_convert():
        """Convert tags to Plex collections."""
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

                # Define the task function
                def convert_task(thread_db, web_echo):
                    plex_manager = PlexManager(db=thread_db)
                    site_tags_use_case = SiteTagsUseCase(thread_db, plex_manager)
                    return site_tags_use_case.create_collection_from_tags(
                        tags=tag_list,
                        collection_name=collection_name,
                        echo_func=web_echo
                    )

                # Execute background task
                execute_background_task(
                    socketio=socketio,
                    app=app,
                    task_func=convert_task,
                    success_message="Collection created successfully!",
                    error_prefix="Collection creation"
                )

                flash('Collection creation started! '
                      'Check the log monitor below for progress.', 'info')
                return render_template('site_tags_convert.html',
                                       processing=True)

            except Exception as e:
                flash(f'Error starting collection creation: {str(e)}', 'error')

        return render_template('site_tags_convert.html')
