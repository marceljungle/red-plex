# Site Tags Feature Usage

This document explains how to use the new site tags functionality to create Plex collections based on site tags.

## Overview

The site tags feature allows you to:
1. Scan your Plex albums and map them to site groups based on filename searches
2. Create Plex collections from albums that match specific tags

## Prerequisites

1. Ensure your Plex server is configured and accessible
2. Configure your RED/OPS API credentials in the config file
3. Populate your albums database with `red-plex db albums update`

## Usage

### 1. Scan Albums for Site Tags

This command scans your albums and creates mappings to site groups:

```bash
# Scan albums for RED
red-plex extras site-tags scan --site red

# Scan albums for OPS  
red-plex extras site-tags scan --site ops
```

The scan process:
- Fetches track file paths from each album in Plex
- Searches the site using filenames
- If multiple matches are found, prompts you to choose
- Creates mappings between Plex rating_key and site group_id + tags
- Is incremental - only processes albums not yet scanned

### 2. Create Collections from Tags

Create Plex collections based on tag filters:

```bash
# Create a collection of electronic music
red-plex extras site-tags convert --site red --tags "electronic" --collection-name "Electronic Music"

# Create a collection with multiple tag requirements
red-plex extras site-tags convert --site red --tags "drum.and.bass,liquid" --collection-name "Liquid DNB"
```

### 3. Reset Site Tag Mappings

If you need to reset the mappings:

```bash
# Reset mappings for a specific site
red-plex extras site-tags reset --site red

# Reset all mappings
red-plex extras site-tags reset
```

## Examples

### Example Workflow

1. **Initial scan:**
   ```bash
   red-plex db albums update
   red-plex extras site-tags scan --site red
   ```

2. **Create genre-based collections:**
   ```bash
   red-plex extras site-tags convert --site red --tags "electronic" --collection-name "Electronic"
   red-plex extras site-tags convert --site red --tags "jazz" --collection-name "Jazz"
   red-plex extras site-tags convert --site red --tags "rock" --collection-name "Rock"
   ```

3. **Create specific sub-genre collections:**
   ```bash
   red-plex extras site-tags convert --site red --tags "drum.and.bass,liquid" --collection-name "Liquid DNB"
   red-plex extras site-tags convert --site red --tags "ambient,dark" --collection-name "Dark Ambient"
   ```

## Notes

- The scan process handles filename variations (e.g., removes track numbers like "1. " from the beginning)
- Multiple matches require user confirmation to ensure accuracy
- Collections are created/updated in Plex - existing collections with the same name will be replaced
- The tag matching uses AND logic - all specified tags must be present for an album to match