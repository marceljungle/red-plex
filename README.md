# red-plex

**red-plex** is a command-line tool for creating Plex playlists based on collages from RED. It allows users to generate playlists in their Plex Media Server by matching music albums from specified collages.

## Table of Contents

1. [Features](#features)
2. [Requirements](#requirements)
   - [Python modules](#python-modules)
3. [Installation](#installation)
4. [Configuration](#configuration)
   - [Steps to configure](#steps-to-configure)
     - [Viewing Configuration](#viewing-configuration)
     - [Resetting Configuration](#resetting-configuration)
5. [Usage](#usage)
   - [Commands](#commands)
   - [Examples](#examples)
6. [Considerations](#considerations)

### Features

- Create Plex playlists from RED collages.
- Support for multiple collage IDs.
- Easy configuration using a config.yml file.
- Command-line interface (CLI) for seamless interaction.
- Handles rate limiting and retries for API calls.
- Compatible with Python 3.7 and above.

### Requirements

- Python 3.7 or higher
- Plex Media Server with accessible API
- RED API key

#### Python modules
- plexapi
- requests
- click
- pyrate-limiter
- tenacity
- pyyaml

### Installation

You can install **red-plex** using pip:
```
pip install red-plex
```

Alternatively, you can install it using pipx to isolate the package and its dependencies:
```
pipx install red-plex
```

### Configuration
Before using red-plex, you need to configure it with your Plex and REDacted API credentials.

#### Steps to configure

1. Edit the Configuration File
   
   Run the following command to open the configuration file in your default editor:
   ```
   red-plex config edit
   ```
   If it’s the first time you’re running this command, it will create a default configuration file at `~/.config/red-plex/config.yml`.

2. Update Configuration Settings
   In the `config.yml` file, update the following settings:
   ```
   PLEX_URL: 'http://localhost:32400'   # URL of your Plex Media Server
   PLEX_TOKEN: 'your_plex_token_here'   # Your Plex API token
   SECTION_NAME: 'Music'                # The name of your music library section in Plex
   RED_API_KEY: 'your_red_api_key_here' # Your REDacted API key 
   ```
   - **PLEX_URL**: The URL where your Plex server is accessible. Defaults to http://localhost:32400.
   - **PLEX_TOKEN**: Your Plex API token. You can obtain this from the Plex web app under account settings.
   - **SECTION_NAME**: The name of your music library in Plex. Defaults to Music.
   - **RED_API_KEY**: Your API key from the REDacted tracker.

3. Save and Close the Configuration File
   After updating the configuration, save the file and close the editor.
   ##### Viewing Configuration
   You can view your current configuration settings by running:
   ```
   red-plex config show
   ```
   
   ##### Resetting Configuration
   To reset your configuration to the default values:
   ```
   red-plex config reset
   ```

### Usage

#### Commands

**red-plex** provides the following commands:

- `red-plex convert [COLLAGE_IDS]`: Creates Plex playlists from the specified RED collage IDs.
- `red-plex config show`: Displays the current configuration settings.
- `red-plex config edit`: Opens the configuration file in your default editor.
- `red-plex config reset`: Resets the configuration to default values.

#### Examples

#### Creating Playlists from Collages

To create playlists from one or more collage IDs:

`red-plex convert 12345 67890`

This command will:

- Fetch the collages with IDs 12345 and 67890 from RED.
- Match the albums in the collages with your Plex music library.
- Create playlists in Plex named after the collages.

#### Viewing Configuration

`red-plex config show`

#### Editing Configuration

`red-plex config edit`

#### Resetting Configuration

`red-plex config reset`

### Considerations

- Bad tagged albums won't be counted in some cases.
- It has to be run on the host which has Plex Server running. (For now)
