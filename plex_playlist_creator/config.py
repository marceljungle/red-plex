import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Plex configuration
PLEX_URL = os.getenv('PLEX_URL', 'http://localhost:32400')
PLEX_TOKEN = os.getenv('PLEX_TOKEN')
SECTION_NAME = os.getenv('SECTION_NAME', 'Music')

# RED configuration
RED_API_KEY = os.getenv('RED_API_KEY')
COLLAGE_IDS = os.getenv('COLLAGE_IDS', '34966').split(',')