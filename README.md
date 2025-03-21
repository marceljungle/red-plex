# red-plex

**red-plex** is a command-line tool for creating and updating **Plex collections** based on collages and bookmarks from Gazelle-based music trackers (Redacted “RED” and Orpheus “OPS”). It stores all data in a local SQLite database and provides commands to synchronize your music library with Plex and the torrent data from these trackers.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage & Commands](#usage--commands)
  - [Configuration](#configuration-commands)
  - [Collages](#collages)
  - [Bookmarks](#bookmarks)
  - [Database Commands](#database-commands)
- [Examples](#examples)
  - [Creating Collections](#creating-collections)
  - [Updating Collections](#updating-collections)
- [Configuration Details](#configuration-details)
  - [Configuration Tips](#configuration-tips)
- [Considerations](#considerations)

---

## Overview

- **Stores Data in SQLite**: Instead of CSV-based “caches,” red-plex now stores albums, collages, and bookmarks in a lightweight SQLite database.  
- **Collages & Bookmarks**: Fetch and manage torrent-based “collages” or personal “bookmarks” from Gazelle-based sites.  
- **Plex Integration**: Compare the torrent group info with your Plex music library to create or update Plex collections.  
- **Incremental Updating**: Update previously created collections as new albums become available or site data changes.

---

## Features

- **Multi-Site**: Works with Redacted (“red”) and Orpheus Network (“ops”).  
- **Collections from Collages/Bookmarks**: Create or update entire Plex collections for each collage or bookmarked set.  
- **Local SQLite Database**: All data (albums, collages, bookmarks) is kept in one DB—no more CSV.  
- **Configurable Logging**: Choose between INFO, DEBUG, etc., in `config.yml`.  
- **Rate Limiting**: Respects site rate limits and retries on errors.  
- **Simple CLI**: All major tasks are accessed via subcommands like `collages`, `bookmarks`, `db`, etc.  
- **Python 3.8+ Compatible**: Runs on modern Python versions with no external database dependencies.

---

## Installation

You can install **red-plex** using **pip**:

```bash
pip install red-plex
```

Or install in an isolated environment with `pipx`:

```bash
pipx install red-plex
```

---

## Usage & Commands

Below is a brief overview of the main commands. Type `red-plex --help` for more details.

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
red-plex collages create [COLLAGE_IDS] --site [red|ops]

# Update all collages in the database, re-checking the site data
red-plex collages update
```

### Bookmarks

```bash
# Create Plex collections from your bookmarked releases
red-plex bookmarks create --site [red|ops]

# Update all bookmarks in the database
red-plex bookmarks update
```

### Database Commands

```bash
# Show or manage the SQLite database

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

---

## Examples

### Creating Collections

From a single collage (on Redacted):

```bash
red-plex collages create 12345 --site red
```

From multiple collages (on Orpheus):

```bash
red-plex collages create 1111 2222 3333 --site ops
```

From your bookmarks (on RED or OPS):

```bash
red-plex bookmarks create --site red
```

_(Prompts if a collection already exists.)_

### Updating Collections

Update all stored collages:

```bash
red-plex collages update
```

Update all stored bookmarks:

```bash
red-plex bookmarks update
```

Update albums from Plex:

```bash
red-plex db albums update
```

---

## Configuration Details

Your configuration is kept in a YAML file (by default `~/.config/red-plex/config.yml` on Linux/macOS). Example:

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

### Configuration Tips

If accessing Plex via HTTP fails, you can fetch an HTTPS URL by calling:

```bash
https://plex.tv/api/resources?includeHttps=1&X-Plex-Token={YOUR_TOKEN}
```

The result includes an XML `<Device>` node with a secure `uri=...`. That `plex.direct` address can be used as your `plex_url`.

---

## Considerations

- **Album Matching**: File and folder naming must be consistent enough to match the torrent’s path with your Plex library’s path.  
- **Database**: All data (albums, collages, bookmarks) is in `red_plex.db`. You can reset specific tables with `db albums reset`, etc.  
- **Site Credentials**: Provide valid API keys for each site in `config.yml`.  
- **Rate Limits**: The tool respects each site’s call/seconds settings to avoid spamming.  
- **Logging**: Set `log_level` to `"DEBUG"` for more details, `"WARNING"` or higher for fewer logs.  
- **Updates**: Running `collages update` or `bookmarks update` adds newly matched albums, but won’t remove items from Plex collections unless you specifically handle that scenario.  
