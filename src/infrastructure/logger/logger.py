"""Logger module"""

import logging
import os
import sys
from pathlib import Path

# Create the logger
logger = logging.getLogger('src')

def configure_logger(log_level='INFO'):
    """Configures the logger with the specified log level."""
    # Determine the log directory path based on the OS
    if os.name == 'nt':  # Windows
        log_dir = os.path.join(os.getenv('APPDATA'), 'red-plex', 'logs')
    else:  # Linux/macOS
        log_dir = os.path.join(Path.home(), '.cache', 'red-plex', 'logs')

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

    # Log where the logs are being saved for transparency
    logger.info("Logs are being saved to: [%s]", log_file_path)
