# GitHub Copilot Instructions for red-plex

## Project Overview
**red-plex** is a Python CLI and web GUI tool for creating Plex collections from RED (Redacted) and OPS (Orpheus) collages and bookmarks. It bridges the gap between private music tracker sites and Plex media servers, allowing users to automatically create collections based on curated music lists.

## Architecture & Design Patterns

### Clean Architecture
The project follows a **clean architecture** pattern with clear separation of concerns:

- **`domain/`**: Core business models (`Album`, `TorrentGroup`, `Collection`)
- **`infrastructure/`**: External adapters (CLI, GUI, DB, REST APIs, configuration)
- **`use_case/`**: Business logic orchestration (collection creation, site tags, upstream sync)

### Key Components
- **CLI Interface**: Built with Click for command-line operations
- **Web GUI**: Flask-based web interface with real-time updates via Socket.IO
- **Database**: SQLite for local data persistence
- **API Integration**: Gazelle API client for RED/OPS communication
- **Plex Integration**: PlexAPI for media server communication

## Development Guidelines

### Python Standards
- **Target Python 3.8+** (specified in setup.py)
- Use **type hints** throughout the codebase
- Follow **PEP 8** coding standards
- Maintain **10/10 pylint score** (current standard)
- Use **dataclasses** for immutable domain models with `frozen=True`
- Leverage **Click** for CLI command structure

### Code Quality Standards
- **Pylint**: Maintain perfect 10/10 score
- **Type Safety**: Use type hints and handle Optional types properly
- **Error Handling**: Graceful degradation with proper logging
- **Rate Limiting**: Respect API rate limits using pyrate-limiter
- **Logging**: Use structured logging with configurable levels

### Dependency Management
- Core dependencies: `plexapi`, `requests`, `click`, `flask`, `pyyaml`
- Rate limiting: `pyrate-limiter`, `tenacity`
- Web features: `flask-socketio`, `gunicorn`, `eventlet`
- Text matching: `thefuzz[speedup]` with rapidfuzz backend

## Project Structure & Conventions

### Directory Organization
```
red_plex/
├── domain/              # Business models and entities
│   └── models.py       # Album, TorrentGroup, Collection classes
├── infrastructure/     # External interfaces and adapters
│   ├── cli/           # Command-line interface (Click commands)
│   ├── config/        # Configuration management
│   ├── db/           # Database operations (SQLite)
│   ├── gui/          # Web interface (Flask + Socket.IO)
│   ├── plex/         # Plex API integration
│   ├── rest/         # External API clients (Gazelle)
│   └── service/      # Infrastructure services
└── use_case/         # Business logic orchestration
    ├── create_collection/ # Collection creation workflows
    ├── site_tags/        # Site tag processing
    └── upstream_sync/    # Upstream synchronization
```

### CLI Command Structure
- **Main groups**: `collages`, `bookmarks`, `config`, `db`, `extras`, `gui`
- **Command pattern**: `red-plex <group> <action> [options]`
- **Fetch modes**: `torrent_name` (default) vs `query` (Beets/Lidarr friendly)
- **Site support**: `red` (Redacted) and `ops` (Orpheus)

### Configuration Management
- **Default location**: `~/.config/red-plex/config.yml`
- **Format**: YAML with API keys, rate limits, Plex settings
- **Required configs**: Plex URL/token, RED/OPS API keys
- **Optional configs**: Rate limiting, log levels, section names

## API Integration Patterns

### Gazelle API Client
- **Base class**: `GazelleAPI` handles both RED and OPS
- **Rate limiting**: Built-in with configurable limits per site
- **Authentication**: API key-based with proper headers
- **Error handling**: Graceful failures with retry logic
- **Text normalization**: Unicode handling for proper matching

### Plex API Integration
- **Library**: PlexAPI for all Plex interactions
- **Collection management**: Create, update, and maintain collections
- **Album matching**: Two modes for different library organizations
- **Section handling**: Configurable music section name

## Web Interface Guidelines

### Flask Application Structure
- **Templates**: Jinja2 templates in `infrastructure/gui/templates/`
- **Real-time updates**: Socket.IO for progress notifications
- **Bootstrap UI**: Responsive design with Bootstrap components
- **Form handling**: Server-side validation and error handling

### UI/UX Patterns
- **Progress indicators**: Real-time feedback for long operations
- **Help documentation**: Contextual help for complex features
- **Error display**: User-friendly error messages with guidance
- **Mobile responsive**: Works across different screen sizes

## Testing & Quality Assurance

### Current Testing Status
- **No existing test suite** - this is an area for improvement
- **Manual testing**: CLI and web interface functionality
- **Linting**: Perfect pylint score maintained

### Testing Recommendations
- **Unit tests**: Domain models and core business logic
- **Integration tests**: API clients and database operations
- **CLI testing**: Click testing utilities for command validation
- **Web testing**: Flask test client for web interface

## GitHub Copilot Specific Guidelines

### Code Generation Best Practices
- **Follow existing patterns**: Match the architectural style
- **Type annotations**: Always include proper type hints
- **Error handling**: Include appropriate exception handling
- **Logging**: Add structured logging for debugging
- **Documentation**: Include docstrings for complex functions

### Common Development Tasks
- **Adding new CLI commands**: Follow Click group/command pattern
- **Extending API clients**: Inherit from base classes and add error handling
- **Database operations**: Use existing LocalDatabase patterns
- **Configuration updates**: Update YAML schema and validation
- **Web interface changes**: Follow Bootstrap + Socket.IO patterns

### Code Review Checklist
- ✅ Maintains 10/10 pylint score
- ✅ Includes proper type hints
- ✅ Follows existing architectural patterns
- ✅ Handles errors gracefully
- ✅ Includes appropriate logging
- ✅ Respects API rate limits
- ✅ Updates documentation if needed
- ✅ Tests manually before committing

### Performance Considerations
- **Rate limiting**: Always respect external API limits
- **Database efficiency**: Use appropriate indexes and queries
- **Memory usage**: Handle large collections efficiently
- **Async operations**: Use for I/O-bound operations where appropriate

## Release & Deployment

### Version Management
- **Current version**: 0.0.0 (in development)
- **Location**: `red_plex/__init__.py`
- **PyPI packaging**: Via setup.py with proper metadata

### CI/CD Pipeline
- **GitHub Actions**: Pylint checks on Python 3.8, 3.9, 3.10
- **Release process**: Automated PyPI uploads on tags
- **Quality gates**: Must maintain perfect pylint score

## Security Considerations

### API Key Management
- **Never commit API keys** to version control
- **Configuration file**: Store in user config directory
- **Environment variables**: Support for containerized deployments
- **Key validation**: Verify API key format and permissions

### Data Privacy
- **Local storage**: All data stored locally by default
- **API communication**: HTTPS only for external services
- **User data**: No tracking or analytics collection
- **Logs**: Avoid logging sensitive information

## Contributing Guidelines

### Development Setup
```bash
git clone https://github.com/marceljungle/red-plex.git
cd red-plex
pip install -e .
red-plex config edit  # Configure API keys
```

### Pull Request Requirements
- **Pylint score**: Must maintain 10/10 rating
- **Type hints**: Required for all new code
- **Documentation**: Update README for user-facing changes
- **Testing**: Manual testing of affected functionality
- **Architecture**: Follow existing patterns and structure

### Issue Reporting
- **Bug reports**: Include logs and reproduction steps
- **Feature requests**: Describe use case and expected behavior
- **API changes**: Consider impact on existing workflows
- **Documentation**: Update relevant documentation

This project bridges the gap between music discovery on private trackers and personal media organization in Plex, making it easier for users to curate and maintain their music collections.