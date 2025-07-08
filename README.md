# red-plex

[![PyPI version](https://badge.fury.io/py/red-plex.svg)](https://badge.fury.io/py/red-plex)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A command-line tool for creating and updating Plex collections based on collages and bookmarks from Gazelle-based music trackers like **Redacted** ("RED") and **Orpheus Network** ("OPS"). 

red-plex bridges the gap between your curated music collections on private trackers and your personal Plex media server, automatically creating and maintaining Plex collections that mirror your tracker collages and bookmarks.

## Quick Start

1. **Install red-plex**: `pip install red-plex`
2. **Configure your API keys**: `red-plex config edit`
3. **Create your first collection**: `red-plex collages convert 12345 --site red`

## What are RED and OPS?

- **Redacted (RED)**: A private music tracker focused on high-quality audio files
- **Orpheus Network (OPS)**: Another private music tracker with curated content
- Both use the Gazelle framework and offer "collages" (curated collections) and personal bookmarks

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Getting API Keys](#getting-api-keys)
- [Configuration](#configuration)
- [Overview](#overview)
- [Features](#features)
- [Usage & Commands](#usage--commands)
  - [Configuration Commands](#configuration-commands)
  - [Collages](#collages)
  - [Bookmarks](#bookmarks)
  - [Fetch Mode (-fm)](#fetch-mode--fm)
  - [Database Commands](#database-commands)
- [Examples](#examples)
  - [Creating Collections](#creating-collections)
  - [Updating Collections](#updating-collections)
  - [Using Query Fetch Mode](#using-query-fetch-mode)
- [Configuration Details](#configuration-details)
- [Configuration Tips](#configuration-tips)
- [Troubleshooting](#troubleshooting)
- [Important Considerations](#important-considerations)
- [Contributing](#contributing)
- [License](#license)

---

## Prerequisites

- **Python 3.8 or higher**
- **Plex Media Server** with a configured music library
- **Active account** on RED and/or OPS with API access
- **Music library** organized in your Plex server

## Installation

### Using pip (recommended)

```bash
pip install red-plex
```

### Using pipx (isolated environment)

```bash
pipx install red-plex
```

### From source

```bash
git clone https://github.com/marceljungle/red-plex.git
cd red-plex
pip install -e .
```

## Getting API Keys

### For Redacted (RED)
1. Log into your RED account
2. Go to your profile settings
3. Navigate to "Access Settings" or "API"
4. Generate a new API key
5. **Keep this key secure and private**

### For Orpheus Network (OPS)
1. Log into your OPS account
2. Go to your user settings
3. Find the API section
4. Generate a new API key
5. **Keep this key secure and private**

## Configuration

After installation, you need to configure red-plex with your credentials:

```bash
# Open configuration file in your default editor
red-plex config edit
```

Edit the configuration file with your details:

```yaml
LOG_LEVEL: INFO
PLEX_URL: http://localhost:32400
PLEX_TOKEN: your_plex_token_here
SECTION_NAME: Music
RED:
  API_KEY: your_red_api_key_here
  BASE_URL: https://redacted.sh
  RATE_LIMIT:
    calls: 10
    seconds: 10
OPS:
  API_KEY: your_ops_api_key_here
  BASE_URL: https://orpheus.network
  RATE_LIMIT:
    calls: 4
    seconds: 15
```

### Getting Your Plex Token

Visit: https://plex.tv/api/resources?includeHttps=1&X-Plex-Token={YOUR_TOKEN}

## Overview

- **Stores Data in SQLite**: Instead of CSV-based "caches," red-plex now stores albums, collages, and bookmarks in a lightweight SQLite database.
- **Collages & Bookmarks**: Fetch and manage torrent-based "collages" or personal "bookmarks" from Gazelle-based sites.
- **Plex Integration**: Compare the torrent group info with your Plex music library to create or update Plex collections.
- **Flexible Album Matching**: Match albums in Plex using either the original `torrent_name` (directory name) or a query-based approach (`Artist/Album`), ideal for organized libraries (e.g., Beets/Lidarr).
- **Incremental Updating**: Update previously created collections as new albums become available or site data changes.

## Features

- **Multi-Site**: Works with Redacted ("red") and Orpheus Network ("ops").
- **Collections from Collages/Bookmarks**: Create or update entire Plex collections for each collage or bookmarked set.
- **Local SQLite Database**: All data (albums, collages, bookmarks) is kept in one DB, no more CSV.
- **Two Fetch Modes**: Choose between `torrent_name` (default) for direct path matching or `query` for metadata-based searches in Plex.
- **Configurable Logging**: Choose between INFO, DEBUG, etc., in `config.yml`.
- **Rate Limiting**: Respects site rate limits and retries on errors.
- **Simple CLI**: All major tasks are accessed via subcommands like `collages`, `bookmarks`, `db`, etc.
- **Python 3.8+ Compatible**: Runs on modern Python versions with no external database dependencies.

## Usage & Commands

Type `red-plex --help` for detailed usage. Below is a summary of the main commands.

### Configuration Commands

```bash
# Show current configuration (YAML)
red-plex config show

# Edit configuration in your default editor
red-plex config edit

# Reset configuration to default values
red-plex config reset
```

### Collages

```bash
# Create Plex collections for specific collage IDs
red-plex collages convert [COLLAGE_IDS] --site [red|ops] --fetch-mode [normal|query]

# Update all collages in the database, re-checking the site data
red-plex collages update --fetch-mode [torrent_name|query]
```

### Bookmarks

```bash
# Create Plex collections from your bookmarked releases
red-plex bookmarks convert --site [red|ops] --fetch-mode [torrent_name|query]

# Update all bookmarks in the database
red-plex bookmarks update --fetch-mode [torrent_name|query]
```

### Fetch Mode (-fm)

The `--fetch-mode` (or `-fm`) option controls how red-plex locates albums in Plex:

#### For `collages convert`:
- **normal** (default): Searches for directories matching the torrent folder name
- **query**: Searches using `Artist` and `Album` metadata, ideal for organized libraries managed by tools like Beets or Lidarr

#### For other commands (`collages update`, `bookmarks convert`, `bookmarks update`):
- **torrent_name** (default): Searches for directories matching the torrent folder name
- **query**: Searches using `Artist` and `Album` metadata, ideal for organized libraries managed by tools like Beets or Lidarr

> **Note**: There's a terminology difference between commands - `collages convert` uses "normal" while other commands use "torrent_name", but both refer to the same functionality.

### Database Commands

```bash
# Show database location
red-plex db location

# Manage albums table
red-plex db albums reset        # Clear all album records
red-plex db albums update       # Pull fresh album info from Plex

# Manage collections table
red-plex db collections reset   # Clear the collage collections table

# Manage bookmarks table
red-plex db bookmarks reset     # Clear the bookmark collections table
```

## Examples

### Creating Collections

```bash
# Single collage (Redacted), default mode
red-plex collages convert 12345 --site red

# Multiple collages (Orpheus), default mode
red-plex collages convert 1111 2222 3333 --site ops

# From bookmarks (RED or OPS), default mode
red-plex bookmarks convert --site red
```

### Updating Collections

```bash
# Update all stored collages
red-plex collages update

# Update all stored bookmarks
red-plex bookmarks update

# Update albums from Plex
red-plex db albums update
```

### Using Query Fetch Mode

```bash
# Create a collection using query mode (for Beets/Lidarr organized libraries)
red-plex collages convert 12345 --site red --fetch-mode query

# Update all bookmarks using query mode
red-plex bookmarks update --site ops -fm query
```

### Complete Workflow Example

```bash
# 1. First time setup
red-plex config edit  # Add your API keys and Plex details

# 2. Update your local album database from Plex
red-plex db albums update

# 3. Create collections from specific collages
red-plex collages convert 12345 67890 --site red

# 4. Create collection from your bookmarks
red-plex bookmarks convert --site red

# 5. Later, update all collections with new releases
red-plex collages update
red-plex bookmarks update
```

## Configuration Details

By default, configuration is stored in `~/.config/red-plex/config.yml`:

```yaml
LOG_LEVEL: INFO
OPS:
  API_KEY: your_ops_api_key_here
  BASE_URL: https://orpheus.network
  RATE_LIMIT:
    calls: 4
    seconds: 15
PLEX_TOKEN: your_plex_token_here
PLEX_URL: http://localhost:32400
RED:
  API_KEY: your_red_api_key_here
  BASE_URL: https://redacted.sh
  RATE_LIMIT:
    calls: 10
    seconds: 10
SECTION_NAME: Music
```

## Configuration Tips

- If HTTP fails, fetch an HTTPS URL:
  ```
  https://plex.tv/api/resources?includeHttps=1&X-Plex-Token={YOUR_TOKEN}
  ```
- Look for the `<Device>` node in the XML for a `uri`, use this `plex.direct` address.
- Use `DEBUG` log level for verbose debugging information
- Use `WARNING` log level for minimal output

## Troubleshooting

### Common Issues

#### "No module named 'plexapi'" Error
```bash
pip install plexapi
# or
pip install red-plex --upgrade
```

#### Authentication Errors
- Verify your API keys are correct in `config.yml`
- Check that your Plex token is valid
- Ensure you have access to the sites you're trying to use

#### No Albums Found
- Run `red-plex db albums update` to refresh your Plex library
- Check that your Plex music library is properly configured
- Verify the `SECTION_NAME` in your config matches your Plex music library name

#### Rate Limiting Issues
- The tool respects site rate limits automatically
- If you encounter issues, try reducing the rate limit values in your config

#### Fetch Mode Issues
- Use `torrent_name`/`normal` mode if your library structure matches torrent folder names
- Use `query` mode if you use Beets, Lidarr, or have renamed your music files
- Try both modes to see which works better for your library

### Getting Help

1. Check the logs with `LOG_LEVEL: DEBUG` in your config
2. Verify your configuration with `red-plex config show`
3. Test your Plex connection by running `red-plex db albums update`
4. Open an issue on GitHub with detailed error messages

## Important Considerations

- **Album Matching Strategy**:
  - `torrent_name`/`normal` (default): Matches albums by comparing torrent folder names with Plex directory paths
  - `query`: Uses artist and album metadata for matching, ideal for libraries organized by Beets, Lidarr, or other tools that rename files
- **Database Management**: All data is stored in `red_plex.db`. Use database reset commands (`db albums reset`, etc.) to clear specific tables when needed
- **Site Credentials**: Ensure your API keys are valid and have proper permissions
- **Rate Limiting**: The tool automatically respects site-specific rate limits to avoid being banned
- **Logging Levels**: 
  - `DEBUG`: Verbose output for troubleshooting
  - `INFO`: Standard information (default)
  - `WARNING`: Minimal output
- **Collection Updates**: When you run `collages update` or `bookmarks update`, new albums are added to existing Plex collections, but removed items from tracker collages are not automatically removed from Plex collections

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

```bash
git clone https://github.com/marceljungle/red-plex.git
cd red-plex
pip install -e .
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Disclaimer**: This tool is for personal use with your own music library and tracker accounts. Respect the rules and terms of service of the private trackers you use.