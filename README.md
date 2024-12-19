# red-plex

**red-plex** is a command-line tool for creating and updating Plex playlists and collections based on collages and bookmarks from Gazelle-based music trackers like Redacted (RED) and Orpheus Network (OPS). It allows users to generate playlists and collections in their Plex Media Server by matching music albums from specified collages or personal bookmarks, and provides ways to synchronize previously created items with updated information.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Commands](#commands)
  - [Convert Commands](#convert-commands)
  - [Playlist Management](#playlist-management)
  - [Collection Management](#collection-management)
  - [Bookmark Management](#bookmark-management)
  - [Album Cache Management](#album-cache-management)
  - [Configuration](#configuration-commands)
- [Examples](#examples)
  - [Creating Playlists and Collections](#creating-playlists-and-collections)
  - [Updating Existing Items](#updating-existing-items)
- [Configuration](#configuration-root)
  - [Configuration Tips](#configuration-tips)
- [Considerations](#considerations)

## Overview

- **Library Scanning**: The application scans the folder structure of your Plex music library, extracting album paths to create a local cache for efficient matching.
- **Fetching Collages**: It connects to a Gazelle-based site using API credentials to fetch collages or bookmarks, retrieving torrent paths for the albums listed.
- **Matching Albums**: The app compares the torrent paths from the site with the album paths in the Plex library, identifying matching albums based on folder names.
- **Creating Playlists/Collections**: For each collage or bookmark, it creates corresponding Plex playlists or collections containing all matched albums.
- **Cache Management**: Album, playlist, and collection data are cached to avoid redundant scanning and enable incremental updates.

## Features

- **Multi-Site Support**: Create Plex playlists and collections from both Redacted and Orpheus Network
- **Playlist and Collection Creation**: Generate both playlists and collections from collages and bookmarks
- **Multiple Collage IDs**: Support for processing multiple collage IDs in a single command
- **Optimized Album Caching**: Album cache includes timestamps for incremental updates
- **Cache Management**: Track processed playlists and collections for automatic updating
- **Automatic Updates**: Synchronize all cached items with their source collages
- **Configurable Logging**: Adjust logging level via configuration file
- **Easy Configuration**: Simple setup using a `config.yml` file
- **Command-Line Interface**: User-friendly CLI with comprehensive commands
- **Rate Limiting and Retries**: Handles API rate limiting with retries for failed calls
- **Python 3 Compatible**: Works with Python 3.7 and above

## Commands

### Convert Commands
```bash
# Create playlist from collage
red-plex convert playlist [COLLAGE_IDS] --site SITE

# Create collection from collage
red-plex convert collection [COLLAGE_IDS] --site SITE
```

### Playlist Management
```bash
# Show playlist cache location
red-plex playlists cache show

# Reset playlist cache
red-plex playlists cache reset

# Update all cached playlists
red-plex playlists update
```

### Collection Management
```bash
# Show collection cache location
red-plex collections cache show

# Reset collection cache
red-plex collections cache reset

# Update all cached collections
red-plex collections update
```

### Bookmark Management
```bash
# Create playlist from bookmarks
red-plex bookmarks create playlist --site SITE

# Create collection from bookmarks
red-plex bookmarks create collection --site SITE

# Update bookmark playlists
red-plex bookmarks update playlist

# Update bookmark collections
red-plex bookmarks update collection

# Show bookmark cache (playlist)
red-plex bookmarks cache playlist show

# Reset bookmark cache (playlist)
red-plex bookmarks cache playlist reset

# Show bookmark cache (collection)
red-plex bookmarks cache collection show

# Reset bookmark cache (collection)
red-plex bookmarks cache collection reset
```

### Album Cache Management
```bash
# Show cache location
red-plex album-cache show

# Reset cache
red-plex album-cache reset

# Update cache
red-plex album-cache update
```

### Configuration (Commands)
```bash
# Show current configuration
red-plex config show

# Edit configuration
red-plex config edit

# Reset configuration
red-plex config reset
```

## Examples

### Creating Playlists and Collections
```bash
# Create playlists from collages
red-plex convert playlist 12345 67890 --site red

# Create collections from collages
red-plex convert collection 12345 67890 --site red

# Create playlist from bookmarks
red-plex bookmarks create playlist --site red

# Create collection from bookmarks
red-plex bookmarks create collection --site red
```

### Updating Existing Items
```bash
# Update all playlists
red-plex playlists update

# Update all collections
red-plex collections update

# Update bookmark playlists
red-plex bookmarks update playlist

# Update bookmark collections
red-plex bookmarks update collection
```

## Configuration (Root)

The configuration file (`~/.config/red-plex/config.yml`) should contain:

```yaml
PLEX_URL: 'http://localhost:32400'
PLEX_TOKEN: 'your_plex_token_here'
SECTION_NAME: 'Music'
LOG_LEVEL: 'INFO'

RED:
  API_KEY: 'your_red_api_key_here'
  BASE_URL: 'https://redacted.sh'
  RATE_LIMIT:
    calls: 10
    seconds: 10

OPS:
  API_KEY: 'your_ops_api_key_here'
  BASE_URL: 'https://orpheus.network'
  RATE_LIMIT:
    calls: 4
    seconds: 15
```

### Configuration Tips
If you encounter issues accessing your Plex server via `http`, like this exception:

```xml
requests.exceptions.ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
```

You can use the following method to retrieve the secure `https` URL for local access without additional configuration:

Use the following API call, replacing `{TOKEN}` with your Plex token:
```text
https://plex.tv/api/resources?includeHttps=1&X-Plex-Token={TOKEN}
```

This will return an XML response, including the full https URL:
```xml
<MediaContainer size="5">
  <Device name="Your Server Name" product="Plex Media Server" ...>
    <Connection protocol="https" address="192.168.x.x" port="32400" 
      uri="https://192-168-x-x.0123456789abcdef0123456789abcdef.plex.direct:32400" local="1"/>
    ...
  </Device>
  ...
</MediaContainer>
```
Thanks anonysmussi for pointing this out!

## Considerations

- **Album Matching**: Ensure proper music library organization with matching folder names
- **Cache Management**: Regular cache updates improve performance and accuracy
- **API Rate Limits**: Be mindful of site-specific rate limits
- **Required Credentials**: Valid API keys needed in configuration
- **Site Specification**: The `--site` option is mandatory for relevant commands
- **Logging Levels**: Adjust verbosity in configuration as needed
- **Cache Tracking**: Separate caches for playlists, collections, and bookmarks enable independent updates
- **Update Process**: Updates add new items while maintaining existing ones
