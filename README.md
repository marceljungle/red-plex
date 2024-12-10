
# red-plex

**red-plex** is a command-line tool for creating and updating Plex playlists based on collages and bookmarks from Gazelle-based music trackers like Redacted (RED) and Orpheus Network (OPS). It allows users to generate playlists in their Plex Media Server by matching music albums from specified collages or personal bookmarks, and now also provides a way to synchronize previously created playlists with updated collage information.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Python Modules](#python-modules)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Steps to Configure](#steps-to-configure)
  - [Viewing Configuration](#viewing-configuration)
  - [Resetting Configuration](#resetting-configuration)
- [Usage](#usage)
  - [Commands](#commands)
  - [Examples](#examples)
- [Considerations](#considerations)

## Overview

- **Library Scanning**: The application scans the folder structure of your Plex music library, extracting album paths to create a local cache for efficient matching.
- **Fetching Collages**: It connects to a Gazelle-based site (like Redacted or Orpheus) using API credentials to fetch collages or bookmarks, retrieving torrent paths for the albums listed.
- **Matching Albums**: The app compares the torrent paths from the site with the album paths in the Plex library. It identifies matching albums based on folder names.
- **Creating Playlists**: For each collage or bookmark, it creates a corresponding Plex playlist containing all matched albums.
- **Cache Management**: Both album and playlist data are cached to avoid redundant scanning and to enable incremental updates.

## Features

- **Multi-Site Support**: Create Plex playlists from collages and bookmarks on both Redacted and Orpheus Network.
- **Create Playlists from Bookmarks**: Generate Plex playlists based on your personal bookmarks from Gazelle-based sites.
- **Multiple Collage IDs**: Support for processing multiple collage IDs in a single command.
- **Optimized Album Caching**: The album cache now includes timestamps to allow incremental updates, reducing the need to scan the entire library each time.
- **Playlist Cache Management**: Keeps track of processed playlists, including site and collage IDs, to enable automatic updating of existing playlists without re-specifying collage IDs.
- **New Playlist Update Feature**: Automatically synchronize all cached playlists with their source collages, ensuring that they stay up-to-date with new albums you've acquired.
- **Configurable Logging**: Adjust the logging level via the configuration file.
- **Easy Configuration**: Simple setup using a `config.yml` file.
- **Command-Line Interface**: Seamless interaction through a user-friendly CLI.
- **Rate Limiting and Retries**: Handles API rate limiting and implements retries for failed calls.
- **Python 3 Compatible**: Works with Python 3.7 and above.

## Requirements

- Python 3.7 or higher
- Plex Media Server with accessible API
- API Keys for the Gazelle-based sites you want to use (e.g., RED, OPS)

## Python Modules

- `plexapi`
- `requests`
- `click`
- `pyrate-limiter`
- `tenacity`
- `pyyaml`

## Installation

You can install red-plex using pip:

```bash
pip install red-plex
```

Alternatively, you can install it using pipx to isolate the package and its dependencies:

```bash
pipx install red-plex
```

## Configuration

Before using red-plex, you need to configure it with your Plex and Gazelle-based site API credentials.

### Steps to Configure

1. **Edit the Configuration File**  
   Run the following command to open the configuration file in your default editor:

   ```bash
   red-plex config edit
   ```

   If it's the first time you're running this command, it will create a default configuration file at `~/.config/red-plex/config.yml`.

2. **Update Configuration Settings**  
   In the `config.yml` file, update the following settings:

   ```yaml
   PLEX_URL: 'http://localhost:32400'  # URL of your Plex Media Server
   PLEX_TOKEN: 'your_plex_token_here'  # Your Plex API token
   SECTION_NAME: 'Music'               # The name of your music library section in Plex
   LOG_LEVEL: 'INFO'                   # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

   RED:
     API_KEY: 'your_red_api_key_here'  # Your RED API key
     BASE_URL: 'https://redacted.sh'   # Base URL for RED
     RATE_LIMIT:
       calls: 10                       # Number of API calls allowed
       seconds: 10                     # Time window in seconds

   OPS:
     API_KEY: 'your_ops_api_key_here'  # Your OPS API key
     BASE_URL: 'https://orpheus.network'  # Base URL for OPS
     RATE_LIMIT:
       calls: 4                        # Number of API calls allowed
       seconds: 15                     # Time window in seconds
   ```

3. **Save and Close the Configuration File**  
   After updating the configuration, save the file and close the editor.

### Viewing Configuration

You can view your current configuration settings by running:

```bash
red-plex config show
```

### Resetting Configuration

To reset your configuration to the default values:

```bash
red-plex config reset
```

## Usage

### Commands

- **Create Playlists from Collages**  
  ```bash
  red-plex convert [COLLAGE_IDS] --site SITE
  ```
  Creates Plex playlists from the specified collage IDs on the specified site.

  Options:
  - `--site`, `-s` (Required): Specify the site to use. Choices are `red` for Redacted or `ops` for Orpheus Network.

- **Create Playlists from Bookmarks**  
  ```bash
  red-plex bookmarks create-playlist --site SITE
  ```
  Creates a Plex playlist based on your personal bookmarks on the specified site.

  Options:
  - `--site`, `-s` (Required): Specify the site to use (`red` or `ops`).

- **Album Cache Management**  
  - `red-plex cache show`: Shows the location of the album cache file if it exists.
  - `red-plex cache reset`: Resets the saved albums cache.
  - `red-plex cache update`: Updates the album cache with new albums added since the last update.

- **Playlist Cache Management**  
  The playlist cache stores site and collage IDs for each playlist, enabling automatic updates without manually providing collage IDs again.
  
  - `red-plex playlists cache show`: Shows the location of the playlist cache file if it exists.
  - `red-plex playlists cache reset`: Resets the saved playlist cache.

- **Synchronize Existing Playlists with Collages**  
  ```bash
  red-plex playlists update
  ```
  Automatically updates all cached playlists by retrieving new albums from their associated collages and adding them to the existing Plex playlists. This command uses the stored site and collage IDs in the playlist cache, so you don’t need to re-enter collage IDs every time you want to sync.

- **Configuration Commands**  
  - `red-plex config show`: Displays the current configuration settings.
  - `red-plex config edit`: Opens the configuration file in your default editor.
  - `red-plex config reset`: Resets the configuration to default values.

### Examples

- **Creating Playlists from Collages**  
  ```bash
  red-plex convert 12345 67890 --site red
  ```
  This will create or update playlists in Plex for the given collage IDs from Redacted.

- **Creating Playlists from Bookmarks**  
  ```bash
  red-plex bookmarks create-playlist --site red
  ```
  This creates a playlist in Plex from your Redacted bookmarks.

- **Updating the Album Cache**  
  ```bash
  red-plex cache update
  ```
  Updates the album cache with newly added albums in your Plex library.

- **Synchronizing All Cached Playlists**  
  ```bash
  red-plex playlists update
  ```
  Updates all your cached playlists from their respective collages, ensuring your Plex playlists stay current with new additions.

## Considerations

- **Album Matching**: Ensure your music library is properly organized and that folder names match the expected formats.
- **Incremental Album Cache Updates**: Updates only new albums, reducing processing time.
- **API Rate Limits**: Be mindful of the API rate limits for each site.
- **Required Credentials**: Ensure valid API keys are correctly entered in the configuration file.
- **Cache Management**: Regularly updating the album cache improves performance and accuracy.
- **Site Specification**: The `--site` option is mandatory when using the `convert` and `bookmarks` commands.
- **Logging**: Adjust the verbosity of logging in your `config.yml` file as needed.
- **Playlist Cache**: The playlist cache now stores `site` and `collage_id` for each playlist, allowing the new `red-plex playlists update` command to refresh all playlists without manual input of collage IDs.
