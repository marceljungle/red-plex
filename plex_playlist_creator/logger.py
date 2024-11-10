"""Logger class"""

import logging
import os

# Define the log directory path
log_dir = os.path.join('logs')
os.makedirs(log_dir, exist_ok=True)

# Define the log file path
log_file_path = os.path.join(log_dir, 'application.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
