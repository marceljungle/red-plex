"""Logger module"""

import logging
import os
import sys

# Create the logger
logger = logging.getLogger('plex_playlist_creator')

def configure_logger(log_level='INFO'):
    """Configures the logger with the specified log level."""
    # Define the log directory path
    log_dir = os.path.join('logs')
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
