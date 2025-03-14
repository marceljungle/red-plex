from pyrate_limiter import Rate, Duration

from infrastructure.config.config import load_config
from infrastructure.logger.logger import logger
from infrastructure.rest.gazelle.gazelle_api import GazelleAPI


def initialize_gazelle_api(site: str):
    """Initialize GazelleAPI for a given site."""
    config_data = load_config()
    site_config = config_data.get(site.upper())
    if not site_config or not site_config.get('API_KEY'):
        message = f'API_KEY for {site.upper()} must be set in the config file under {site.upper()}.'
        logger.error(message)
        return None

    api_key = site_config.get('API_KEY')
    base_url = site_config.get('BASE_URL')
    rate_limit_config = site_config.get('RATE_LIMIT', {'calls': 10, 'seconds': 10})
    rate_limit = Rate(rate_limit_config['calls'], Duration.SECOND * rate_limit_config['seconds'])

    return GazelleAPI(base_url, api_key, rate_limit)
