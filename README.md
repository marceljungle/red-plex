# red-plex

**red-plex** is a command-line tool for creating Plex playlists based on collages from Gazelle-based music trackers like **Redacted (RED)** and **Orpheus Network (OPS)**. It allows users to generate playlists in their Plex Media Server by matching music albums from specified collages.

## Table of Contents

1. [Features](#features)
2. [Requirements](#requirements)
   - [Python Modules](#python-modules)
3. [Installation](#installation)
4. [Configuration](#configuration)
   - [Steps to Configure](#steps-to-configure)
     - [Viewing Configuration](#viewing-configuration)
     - [Resetting Configuration](#resetting-configuration)
5. [Usage](#usage)
   - [Commands](#commands)
   - [Examples](#examples)
6. [Considerations](#considerations)

### Features

- **Multi-Site Support**: Create Plex playlists from collages on both **Redacted** and **Orpheus Network**.
- **Multiple Collage IDs**: Support for processing multiple collage IDs in a single command.
- **Configurable Logging**: Adjust the logging level via the configuration file.
- **Easy Configuration**: Simple setup using a `config.yml` file.
- **Command-Line Interface**: Seamless interaction through a user-friendly CLI.
- **Rate Limiting and Retries**: Handles API rate limiting and implements retries for failed calls.
- **Album Cache Management**: Manage cached album data for improved performance.
- **Python 3 Compatible**: Works with Python 3.7 and above.

### Requirements

- **Python 3.7** or higher
- **Plex Media Server** with accessible API
- **API Keys** for the Gazelle-based sites you want to use (e.g., RED, OPS)

#### Python Modules

- `plexapi`
- `requests`
- `click`
- `pyrate-limiter`
- `tenacity`
- `pyyaml`

### Installation

You can install **red-plex** using pip:

```bash
pip install red-plex
```

Alternatively, you can install it using pipx to isolate the package and its dependencies:

```bash
pipx install red-plex
```

### Configuration

Before using **red-plex**, you need to configure it with your Plex and Gazelle-based site API credentials.

#### Steps to Configure

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

   - **PLEX_URL**: The URL where your Plex server is accessible. Defaults to `http://localhost:32400`.
   - **PLEX_TOKEN**: Your Plex API token. You can obtain this from the Plex web app under account settings.
   - **SECTION_NAME**: The name of your music library in Plex. Defaults to `Music`.
   - **LOG_LEVEL**: The logging level for the application. Options are `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. Defaults to `INFO`.
   - **RED**:
     - **API_KEY**: Your API key from Redacted.
     - **BASE_URL**: The base URL for Redacted's API. Defaults to `https://redacted.sh`.
     - **RATE_LIMIT**: API rate limiting settings for Redacted.
   - **OPS**:
     - **API_KEY**: Your API key from Orpheus Network.
     - **BASE_URL**: The base URL for Orpheus Network's API. Defaults to `https://orpheus.network`.
     - **RATE_LIMIT**: API rate limiting settings for Orpheus Network.

3. **Save and Close the Configuration File**

   After updating the configuration, save the file and close the editor.

##### Viewing Configuration

You can view your current configuration settings by running:

```bash
red-plex config show
```

##### Resetting Configuration

To reset your configuration to the default values:

```bash
red-plex config reset
```

### Usage

#### Commands

**red-plex** provides the following commands:

- **Convert Collages to Playlists**

  ```bash
  red-plex convert [COLLAGE_IDS] --site SITE
  ```

  Creates Plex playlists from the specified collage IDs on the specified site.

  - **Options**:
    - `--site`, `-s` **(Required)**: Specify the site to use. Choices are `red` for Redacted or `ops` for Orpheus Network.

- **Configuration Commands**

  - `red-plex config show`: Displays the current configuration settings.
  - `red-plex config edit`: Opens the configuration file in your default editor.
  - `red-plex config reset`: Resets the configuration to default values.

- **Cache Management Commands**

  - `red-plex cache show`: Shows the location of the album cache file if it exists.
  - `red-plex cache reset`: Resets the saved albums cache.

#### Examples

##### Creating Playlists from Collages

To create playlists from one or more collage IDs on **Redacted**:

```bash
red-plex convert 12345 67890 --site red
```

To create playlists from collages on **Orpheus Network**:

```bash
red-plex convert 23456 78901 --site ops
```

This command will:

- Fetch the specified collages from the chosen site.
- Match the albums in the collages with your Plex music library.
- Create playlists in Plex named after the collages.

**Note**: The `--site` (`-s`) option is **required**. You must specify either `red` or `ops`.

##### Viewing Configuration

```bash
red-plex config show
```

##### Editing Configuration

```bash
red-plex config edit
```

##### Resetting Configuration

```bash
red-plex config reset
```

##### Managing the Album Cache

To view the location of the album cache file:

```bash
red-plex cache show
```

To reset the album cache:

```bash
red-plex cache reset
```

### Considerations

- **Album Matching**: The tool matches albums based on the folder names in your Plex library. Ensure that your music library is properly organized and tagged for the best results.
- **Logging**: You can adjust the verbosity of the application's logging by setting the `LOG_LEVEL` in your configuration file.
- **API Rate Limits**: Be mindful of the API rate limits for each site. The defaults are set in the configuration, but you may need to adjust them based on your usage and the site's policies.
- **Required Credentials**: Make sure you have valid API keys for the sites you wish to use and that they are correctly entered in the configuration file.
- **Site Specification**: The `--site` option is now mandatory when using the `convert` command. You must specify the site (`red` or `ops`) to ensure the correct API is used.
