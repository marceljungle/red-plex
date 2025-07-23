"""Configuration route handlers."""
from flask import render_template, request, redirect, url_for, flash

from red_plex.infrastructure.config.config import load_config, save_config
from red_plex.infrastructure.config.models import Configuration


def register_config_routes(app):
    """Register configuration-related routes."""

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