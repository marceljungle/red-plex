"""Logger module"""

import logging
import os
import sys
from pathlib import Path
from red_plex.infrastructure.config.config import load_config

# Create the logger
logger = logging.getLogger('red_plex')


def configure_logger():
    """Configures the logger with the specified log level."""

    # Load configuration
    config_data = load_config()

    # Get log level from configuration, default to 'INFO' if not set
    log_level = config_data.log_level.upper()

    # Validate log level
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if log_level not in valid_log_levels:
        print(f"Invalid LOG_LEVEL '{log_level}' in configuration. Defaulting to 'INFO'.")

    # Determine the log directory path based on the OS
    if os.name == 'nt':  # Windows
        log_dir = os.path.join(os.getenv('APPDATA'), 'red-plex', 'logs')
    else:  # Linux/macOS
        log_dir = os.path.join(Path.home(), '.db', 'red-plex', 'logs')

    # Ensure the log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # Define the log file path
    log_file_path = os.path.join(log_dir, 'application.log')

    # Remove existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # Set the logger level using the log_level parameter
    logger.setLevel(log_level.upper())

    # Define the log format
    log_format = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    # Create a FileHandler with UTF-8 encoding to properly handle Unicode characters
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(log_level.upper())  # Set handler level
    file_handler.setFormatter(log_format)

    # Create a StreamHandler to output logs to stdout
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level.upper())  # Set handler level
    stream_handler.setFormatter(log_format)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
