"""Logger class"""

import logging
import os
import sys

# Define the log directory path
log_dir = os.path.join('logs')
os.makedirs(log_dir, exist_ok=True)

# Define the log file path
log_file_path = os.path.join(log_dir, 'application.log')

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

log_format = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

# Create a FileHandler with UTF-8 encoding to properly handle Unicode characters
file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
file_handler.setFormatter(log_format)

# Create a StreamHandler to output logs
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(stream_handler)
