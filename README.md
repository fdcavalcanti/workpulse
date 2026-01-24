# WorkTracker

A Python-based tool for tracking daily working time using systemd login information. WorkTracker automatically monitors your active session and logs working time, excluding periods when your system is suspended, locked, or hibernated. Also, this tool is able to sync the data to your Home Assistant using MQTT.

## Features

- **Automatic Time Tracking**: Monitors active working time using systemd login session data
- **Smart Exclusion**: Automatically excludes suspend, locked, and hibernation periods
- **Daily Logs**: Stores daily active time summaries in a simple SQLite database
- **Systemd Integration**: Runs as a systemd user timer, updating every minute
- **Simple CLI**: Easy-to-use command-line interface
- **Lightweight**: Minimal dependencies, no external services required
- **Home Assistant**: Integrates to Home Assistant using MQTT

## Requirements

- **Python 3.10+**
- **systemd**: Linux system with systemd-logind (most modern Linux distributions)
- **loginctl**: Command-line tool for querying systemd login manager (usually pre-installed)

## Installation

### From PyPI

```bash
pip install worktracker
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

View current tracking status and today's summary:

```bash
worktracker status
```

If needed, you can uninstall:

```bash
worktracker uninstall
```

This removes the systemd timer and service files. Note: The database files in `~/.worktracker/` are not removed automatically. To completely remove all data, manually delete the `~/.worktracker/` directory.


## Home Assistant Integration

WorkTracker can publish daily time tracking data to Home Assistant via MQTT, allowing you to monitor your working time directly in your Home Assistant dashboard.

### Setup

1. **Configure MQTT in WorkTracker:**

   During installation, WorkTracker creates a default MQTT configuration file at `~/.worktracker/mqtt_config.toml`. Edit this file to set your MQTT broker details:

   ```toml
   broker = "192.168.1.100"  # Your MQTT broker IP address
   port = 1883
   username = ""  # Optional: MQTT username
   password = ""  # Optional: MQTT password
   topic_prefix = "worktracker"
   update_interval = 60  # Publish updates every 60 seconds
   ```

2. **Generate Home Assistant YAML Configuration:**

   ```bash
   worktracker mqtt yaml
   ```

   This command generates the Home Assistant YAML configuration with your hostname automatically filled in.

3. **Add Configuration to Home Assistant:**

   - Copy the generated YAML configuration
   - Paste it into your Home Assistant `configuration.yaml` file
   - Restart Home Assistant or reload the MQTT integration

4. **Start the MQTT Publisher:**

   ```bash
   worktracker mqtt start
   ```

   The publisher will run in the foreground. To run it as a background service, you can use `systemd` or a process manager.

The integration creates a single sensor that displays your daily total active time formatted as hours and minutes (e.g., "2h 30m" or "45m"). The sensor updates automatically as WorkTracker publishes new data.

### MQTT Commands

- `worktracker mqtt start` - Start the MQTT publisher daemon
- `worktracker mqtt stop` - Stop the MQTT publisher
- `worktracker mqtt status` - Show MQTT configuration status
- `worktracker mqtt publish` - Manually publish status (for testing)
- `worktracker mqtt yaml` - Generate Home Assistant YAML configuration


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
