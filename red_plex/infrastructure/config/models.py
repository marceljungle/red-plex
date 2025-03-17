""" This module contains the configuration models used in the project. """

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class RateLimitConfiguration:
    """
    Represents the rate limit configuration of a site.
    """
    calls: int = 0
    seconds: int = 0


@dataclass
class SiteConfiguration:
    """
    Represents the configuration of a site.
    """
    api_key: str = ""
    base_url: str = ""
    rate_limit: RateLimitConfiguration = None


@dataclass
class Configuration:
    """
    Represents the configuration used in the project.
    """
    plex_url: str = ""
    plex_token: str = ""
    section_name: str = ""
    log_level: str = ""
    site_configurations: Dict[str, SiteConfiguration] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "Configuration":
        """
        Returns a new Configuration instance with default values.
        """
        return cls(
            plex_url="http://localhost:32400",
            plex_token="",
            section_name="Music",
            log_level="INFO",
            site_configurations={
                "RED": SiteConfiguration(
                    api_key="",
                    base_url="https://redacted.sh",
                    rate_limit=RateLimitConfiguration(calls=10, seconds=10)
                ),
                "OPS": SiteConfiguration(
                    api_key="",
                    base_url="https://orpheus.network",
                    rate_limit=RateLimitConfiguration(calls=4, seconds=15)
                )
            }
        )

    @classmethod
    def from_dict(cls, data: dict) -> "Configuration":
        """
        Build a Configuration object from a raw dictionary structure
        (e.g., from YAML or JSON).
        """
        # Basic fields
        plex_url = data.get('PLEX_URL', 'http://localhost:32400')
        plex_token = data.get('PLEX_TOKEN', '')
        section_name = data.get('SECTION_NAME', 'Music')
        log_level = data.get('LOG_LEVEL', 'INFO')

        # Parse site data (assuming exactly two sites: RED and OPS)
        # Migrate to a different structure if more sites are needed
        red_data = data.get('RED', {})
        ops_data = data.get('OPS', {})

        site_configurations = {
            "RED": SiteConfiguration(
                api_key=red_data.get('API_KEY', ''),
                base_url=red_data.get('BASE_URL', 'https://redacted.sh'),
                rate_limit=RateLimitConfiguration(
                    calls=red_data.get('RATE_LIMIT', {}).get('calls', 10),
                    seconds=red_data.get('RATE_LIMIT', {}).get('seconds', 10)
                )
            ),
            "OPS": SiteConfiguration(
                api_key=ops_data.get('API_KEY', ''),
                base_url=ops_data.get('BASE_URL', 'https://orpheus.network'),
                rate_limit=RateLimitConfiguration(
                    calls=ops_data.get('RATE_LIMIT', {}).get('calls', 4),
                    seconds=ops_data.get('RATE_LIMIT', {}).get('seconds', 15)
                )
            )
        }

        return cls(
            plex_url=plex_url,
            plex_token=plex_token,
            section_name=section_name,
            log_level=log_level,
            site_configurations=site_configurations
        )

    def to_dict(self) -> dict:
        """
        Convert this Configuration to a dict
        that can be easily dumped to YAML or JSON.
        """
        red = self.site_configurations.get("RED", SiteConfiguration())
        ops = self.site_configurations.get("OPS", SiteConfiguration())

        return {
            'PLEX_URL': self.plex_url,
            'PLEX_TOKEN': self.plex_token,
            'SECTION_NAME': self.section_name,
            'LOG_LEVEL': self.log_level,
            'RED': {
                'API_KEY': red.api_key,
                'BASE_URL': red.base_url,
                'RATE_LIMIT': {
                    'calls': red.rate_limit.calls if red.rate_limit else 10,
                    'seconds': red.rate_limit.seconds if red.rate_limit else 10
                }
            },
            'OPS': {
                'API_KEY': ops.api_key,
                'BASE_URL': ops.base_url,
                'RATE_LIMIT': {
                    'calls': ops.rate_limit.calls if ops.rate_limit else 4,
                    'seconds': ops.rate_limit.seconds if ops.rate_limit else 15
                }
            }
        }
