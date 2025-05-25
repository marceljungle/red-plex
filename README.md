# red-plex

red-plex is a command-line tool for creating and updating Plex collections based on collages and bookmarks from Gazelle-based music trackers (Redacted “RED” and Orpheus “OPS”). It stores all data in a local SQLite database and provides commands to synchronize your music library with Plex and the torrent data from these trackers.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
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
- [Considerations](#considerations)

---

## Overview

- **Stores Data in SQLite**: Instead of CSV-based “caches,” red-plex now stores albums, collages, and bookmarks in a lightweight SQLite database.
- **Collages & Bookmarks**: Fetch and manage torrent-based “collages” or personal “bookmarks” from Gazelle-based sites.
- **Plex Integration**: Compare the torrent group info with your Plex music library to create or update Plex collections.
- **Flexible Album Matching**: Match albums in Plex using either the original `torrent_name` (directory name) or a query-based approach (`Artist/Album`), ideal for organized libraries (e.g., Beets/Lidarr).
- **Incremental Updating**: Update previously created collections as new albums become available or site data changes.

## Features

- **Multi-Site**: Works with Redacted (“red”) and Orpheus Network (“ops”).
- **Collections from Collages/Bookmarks**: Create or update entire Plex collections for each collage or bookmarked set.
- **Local SQLite Database**: All data (albums, collages, bookmarks) is kept in one DB, no more CSV.
- **Two Fetch Modes**: Choose between `torrent_name` (default) for direct path matching or `query` for metadata-based searches in Plex.
- **Configurable Logging**: Choose between INFO, DEBUG, etc., in `config.yml`.
- **Rate Limiting**: Respects site rate limits and retries on errors.
- **Simple CLI**: All major tasks are accessed via subcommands like `collages`, `bookmarks`, `db`, etc.
- **Python 3.8+ Compatible**: Runs on modern Python versions with no external database dependencies.

## Installation

Install via pip:

```bash
pip install red-plex
```

Or use pipx for an isolated environment:

```bash
pipx install red-plex
```

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
red-plex collages convert [COLLAGE_IDS] --site [red|ops] --fetch-mode [torrent_name|query]

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

- **torrent_name** (default): Searches for directories matching the torrent folder name.
- **query**: Searches using `Artist` and `Album` metadata, ideal for organized libraries managed by tools like Beets or Lidarr.

This option applies to `collages convert`, `collages update`, `bookmarks convert`, and `bookmarks update`. Defaults to `torrent_name` if omitted.

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
# Create a collection using query mode
red-plex collages convert 12345 --site red --fetch-mode query

# Update all bookmarks using query mode
red-plex bookmarks update --site ops -fm query
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

## Considerations

- **Album Matching**:
  - `torrent_name` (default): Matches folder paths.
  - `query`: Uses metadata for reliable matching in renamed libraries.
- **Database**: All data in `red_plex.db`. Reset tables with `db albums reset`, etc.
- **Site Credentials**: Ensure valid API keys in `config.yml`.
- **Rate Limits**: Adheres to site-specific settings.
- **Logging**: Use `DEBUG` for verbose logs or `WARNING` for less output.
- **Updates**: `collages update` and `bookmarks update` add new albums but do not remove existing items in Plex.
