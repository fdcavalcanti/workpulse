# WorkTracker

A Python-based tool for tracking daily working time using systemd login information. WorkTracker automatically monitors your active session and logs working time, excluding periods when your system is suspended, locked, or hibernated.

## Features

- **Automatic Time Tracking**: Monitors active working time using systemd login session data
- **Smart Exclusion**: Automatically excludes suspend, locked, and hibernation periods
- **Daily Logs**: Stores daily active time summaries in a simple SQLite database
- **Systemd Integration**: Runs as a systemd user timer, updating every minute
- **Simple CLI**: Easy-to-use command-line interface
- **Lightweight**: Minimal dependencies, no external services required

## Requirements

- **Python 3.10+**
- **systemd**: Linux system with systemd-logind (most modern Linux distributions)
- **loginctl**: Command-line tool for querying systemd login manager (usually pre-installed)

## Installation

### From PyPI

```bash
pip install worktracker
```

### From Source

```bash
git clone <repository-url>
cd worktimer
pip install -e .
```

## Usage

### Initial Setup

Install and start tracking:

```bash
worktracker install
```

This command will:
- Initialize the SQLite database in `~/.worktracker/worktracker.db`
- Create and install a systemd user timer (`worktracker.timer`)
- Enable and start the timer to begin tracking
- The timer will automatically start when you log in

### Check Status

View current tracking status and today's summary:

```bash
worktracker status
```

This displays:
- Timer installation status (installed, enabled, running)
- Current session state (active/inactive)
- Today's total active time (hours:minutes)

### Control the Timer

**Start tracking:**
```bash
worktracker start
```

**Stop tracking:**
```bash
worktracker stop
```

**Uninstall:**
```bash
worktracker uninstall
```

This removes the systemd timer and service files. Note: The database files in `~/.worktracker/` are not removed automatically. To completely remove all data, manually delete the `~/.worktracker/` directory.

## How It Works

WorkTracker uses a systemd user timer that runs every minute. Each minute, it:

1. Checks if your session is active using `loginctl`
2. Verifies the session is not locked
3. Confirms the system is not suspended/hibernated
4. If all conditions are met, adds 60 seconds to today's total active time

The tracking is based on systemd login session state, which provides accurate information about:
- Session activity (active/inactive)
- Screen lock status
- System power state

### Database Structure

The database stores daily totals in a simple schema:

- **Table**: `daily_totals`
- **Columns**:
  - `date` (PRIMARY KEY): Date in YYYY-MM-DD format
  - `total_seconds` (REAL): Total active time in seconds for that day

The database is located at `~/.worktracker/worktracker.db`.

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd worktimer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode
pip install -e .

# Install development dependencies
pip install pytest pytest-cov
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov

# Run specific test file
pytest tests/test_database.py

# Run with verbose output
pytest -v
```

### Test Coverage

The project maintains **87%+ test coverage** (excluding CLI module). Coverage reports are generated in HTML format in the `htmlcov/` directory.

### Project Structure

```
worktimer/
├── src/
│   └── worktracker/
│       ├── __init__.py
│       ├── cli.py              # Command-line interface
│       ├── database.py         # SQLite database operations
│       ├── models.py           # Data models (SessionState, Session, DailyLog)
│       ├── service.py          # Systemd timer/service management
│       ├── state_checker.py   # User activity checking via loginctl
│       └── tracker.py         # Core tracking logic
├── tests/
│   ├── test_database.py
│   ├── test_models.py
│   ├── test_service.py
│   ├── test_state_checker.py
│   └── test_tracker.py
├── pyproject.toml
├── .coveragerc
└── README.md
```

## Troubleshooting

### Timer Not Starting

If the timer doesn't start automatically after installation:

1. Check if systemd user services are enabled:
   ```bash
   systemctl --user status worktracker.timer
   ```

2. Manually start the timer:
   ```bash
   worktracker start
   ```

3. Check systemd logs:
   ```bash
   journalctl --user -u worktracker.service
   ```

### No Time Being Tracked

If time isn't being logged:

1. Verify your session is active:
   ```bash
   loginctl list-sessions
   ```

2. Check if the timer is running:
   ```bash
   worktracker status
   ```

3. Verify the database exists and is writable:
   ```bash
   ls -la ~/.worktracker/
   ```

### Permission Issues

If you encounter permission errors:

- Ensure you have write access to `~/.worktracker/`
- Verify systemd user services are available (most Linux distributions have this enabled by default)

## Limitations

- **Linux Only**: Requires systemd, which is primarily available on Linux
- **User Sessions Only**: Tracks only graphical/login sessions, not SSH sessions
- **No Historical Data Import**: Cannot import time data from other sources
- **Manual Database Access**: No built-in query interface; use SQLite tools for advanced queries

## Contributing

Contributions are welcome! Please ensure:

- All tests pass (`pytest`)
- Code coverage remains above 80%
- Code follows PEP 8 style guidelines
- New features include appropriate tests

## License

MIT License - see LICENSE file for details.

## Version

Current version: **0.1.0**
