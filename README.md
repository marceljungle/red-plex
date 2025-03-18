# red-plex

**red-plex** is a command-line tool for creating and updating **Plex collections** based on collages and bookmarks from Gazelle-based music trackers like Redacted (RED) and Orpheus Network (OPS). It allows users to generate collections in their Plex Media Server by matching music albums from specified collages or personal bookmarks, and provides ways to synchronize previously created items with updated information.

---

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Commands](#commands)
  - [Convert (Create) Collections](#convert-create-collections)
  - [Collections Management](#collections-management)
  - [Bookmarks Management](#bookmarks-management)
  - [Album Cache Management](#album-cache-management)
  - [Configuration Commands](#configuration-commands)
- [Examples](#examples)
  - [Creating Collections](#creating-collections)
  - [Updating Existing Items](#updating-existing-items)
- [Configuration Details](#configuration-details)
  - [Configuration Tips](#configuration-tips)
- [Considerations](#considerations)

---

## Overview

- **Library Scanning**: The application scans your Plex music library, extracting album paths into a local cache for quick matching.
- **Fetching Collages/Bookmarks**: It connects to a Gazelle-based site using your API credentials to fetch collages or your personal bookmarks, retrieving torrent paths for the albums listed.
- **Matching Albums**: The tool compares the torrent paths from the site with album paths in your Plex library, matching based on folder names or partial matches.
- **Creating Collections**: For each collage or set of bookmarks, `red-plex` creates a corresponding Plex collection containing all matched albums.
- **Incremental Updates**: Previously created collections can be synchronized later to add newly found albums or reflect changes from the site.
- **Cache Management**: Album, bookmark, and collection data are cached to avoid repeated full scans, enable incremental updates, and speed up usage.

---

## Features

- **Multi-Site Support**: Create Plex collections from both Redacted (“red”) and Orpheus Network (“ops”).
- **Multiple Collage IDs**: Process multiple collages in one command:

  ```bash
  red-plex convert collection 12345 67890 --site red
  ```

- **Bookmarks Integration**: Create or update collections from your bookmarked releases.
- **Optimized Album Caching**: Maintain a timestamped album cache to scan only newly added albums in Plex.
- **Collection Caching**: Track processed collages or bookmarks to allow incremental synchronization.
- **Configurable Logging**: Control the verbosity via a YAML config file.
- **Rate Limiting and Retries**: Respects the site’s API rate limits and retries on network/HTTP errors.
- **User Confirmation**: Prompts for confirmation when a collection already exists.
- **Python 3 Compatible**: Runs on Python 3.8+ (tested through 3.10+).
- **Command-Line Interface**: Provides clear and organized CLI commands for all major operations.

---

## Installation

You can install **red-plex** using pip:

```bash
pip install red-plex
```

Alternatively, you can install it using `pipx` to isolate the package and its dependencies:

```bash
pipx install red-plex
```

---

## Commands

Below is a summary of the main commands. For detailed usage, run `red-plex --help` or any subcommand with `--help`.

### Convert (Create) Collections

```bash
# Create collections from one or more collages
red-plex convert collection [COLLAGE_IDS] --site [red|ops]
```

If the collection already exists in Plex, the tool asks if you want to update it (add new matched albums).

### Collections Management

```bash
# Show the location of the collections cache file
red-plex collections cache show

# Reset (delete) the collections cache
red-plex collections cache reset

# Update all cached collections (force synchronization with the source collages)
red-plex collections update
```

### Bookmarks Management

```bash
# Create a Plex collection from your bookmarks on RED or OPS
red-plex bookmarks create --site [red|ops]

# Update all cached bookmark collections (force synchronization)
red-plex bookmarks update

# Show the bookmarks cache file location
red-plex bookmarks cache show

# Reset (delete) the bookmarks cache
red-plex bookmarks cache reset
```

### Album Cache Management

```bash
# Show the location of the album cache
red-plex album-cache show

# Reset (delete) the album cache
red-plex album-cache reset

# Update (scan) the album cache with the latest info from Plex
red-plex album-cache update
```

### Configuration Commands

```bash
# Show current configuration
red-plex config show

# Edit configuration in your default editor
red-plex config edit

# Reset configuration to defaults
red-plex config reset
```

---

## Examples

### Creating Collections

Create a Plex collection from a collage (on Redacted):

```bash
red-plex convert collection 12345 --site red
```

Create from multiple collages (on Orpheus):

```bash
red-plex convert collection 1111 2222 3333 --site ops
```

Create a Plex collection from personal bookmarks:

```bash
red-plex bookmarks create --site red
```

(Will prompt if a collection already exists.)

### Updating Existing Items

```bash
# Update all cached collections
red-plex collections update

# Update all cached bookmarks
red-plex bookmarks update

# Manually reset and re-update the album cache
red-plex album-cache reset
red-plex album-cache update
```

---

## Configuration Details

The configuration file (`~/.config/red-plex/config.yml` on Linux/macOS) should look like this:

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

On Windows, the config path is typically `%APPDATA%\red-plex\config.yml`.

---

## Configuration Tips

If you run into issues with `http://localhost:32400`, you may need the secure HTTPS URL. You can retrieve it from:

```bash
https://plex.tv/api/resources?includeHttps=1&X-Plex-Token={YOUR_TOKEN}
```

This call returns an XML with a `<Device>` entry containing `uri="https://192-168-..."`. Use that URI in your config (e.g., `"https://192-168-x-x.plex.direct:32400"`).

---

## Considerations

- **Album Matching**: Ensure the physical folder names in your Plex library are reasonably close to the torrent folder names.
- **Cache Management**: Regularly updating the cache helps performance and accuracy.
- **API Rate Limits**: `red-plex` uses built-in limiters and retries to avoid hitting site rate limits. Adjust them in `config.yml`.
- **Logging Levels**: Default is `INFO`. Set `log_level: "DEBUG"` for more detailed logs or `"WARNING"` for fewer messages.
- **Interactive Prompts**: When the collection already exists, `red-plex` will prompt to confirm updating.
- **Multiple Collages**: You can list multiple collage IDs after the `collection` subcommand.
- **Python Versions**: Tested on Python 3.8 to 3.12.
- **Bookmarks**: Bookmarks are handled similarly to collages but stored separately.

