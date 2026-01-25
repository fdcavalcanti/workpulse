"""Command-line interface for workpulse."""

import argparse
import signal
import sys
import time
from pathlib import Path

from .database import Database
from .homeassistant import generate_yaml_config
from .mqtt_client import MQTTClient
from .mqtt_config import create_default_config, load_config
from .service import ServiceManager
from .tracker import WorkTracker


class WorkPulseCLI:
    """Command-line interface for workpulse."""

    def __init__(self) -> None:
        """Initialize the CLI."""
        self.service_manager = ServiceManager()

    def install(self) -> int:
        """Install workpulse: initialize database and install systemd timer.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Installing workpulse...")

        # Initialize database
        try:
            db = Database()
            db.connect()
            db.close()
            print("✓ Database initialized")
        except Exception as e:
            print(f"ERROR: Failed to initialize database: {e}")
            return 1

        # Create default MQTT config file if it doesn't exist
        try:
            config_path = create_default_config()
            print(f"✓ MQTT configuration file created: {config_path}")
            print("  NOTE: Please edit the file to set your MQTT broker IP address")
        except OSError as e:
            print(f"WARNING: Failed to create MQTT configuration file: {e}")

        # Install systemd timer
        if not self.service_manager.install_timer():
            print("ERROR: Failed to install systemd timer")
            return 1
        print("✓ Timer file installed")

        # Reload daemon
        if not self.service_manager.reload_daemon():
            print("WARNING: Failed to reload systemd daemon")
        else:
            print("✓ Systemd daemon reloaded")

        # Enable timer
        if not self.service_manager.enable_timer():
            print("ERROR: Failed to enable timer")
            return 1
        print("✓ Timer enabled")

        # Start timer
        if not self.service_manager.start_timer():
            print("ERROR: Failed to start timer")
            return 1
        print("✓ Timer started")

        print("\nworkpulse has been installed and started successfully!")
        print("The timer will update your working time every minute.")
        return 0

    def stop(self) -> int:
        """Stop the workpulse timer.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Stopping workpulse timer...")

        if not self.service_manager.is_timer_installed():
            print("ERROR: Timer is not installed")
            return 1

        if not self.service_manager.stop_timer():
            print("ERROR: Failed to stop timer")
            return 1

        if not self.service_manager.disable_timer():
            print("WARNING: Failed to disable timer")
        else:
            print("✓ Timer stopped and disabled")

        print("workpulse timer has been stopped.")
        return 0

    def start(self) -> int:
        """Start the workpulse timer.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Starting workpulse timer...")

        if not self.service_manager.is_timer_installed():
            print("ERROR: Timer is not installed")
            print("Run 'workpulse install' to set up the timer first.")
            return 1

        if not self.service_manager.start_timer():
            print("ERROR: Failed to start timer")
            return 1

        print("✓ Timer started")

        # Optionally enable it if not already enabled
        if not self.service_manager.is_timer_enabled():
            if self.service_manager.enable_timer():
                print("✓ Timer enabled (will run automatically)")
            else:
                print("WARNING: Timer started but failed to enable")

        print("workpulse timer is now running.")
        return 0

    def uninstall(self) -> int:
        """Uninstall workpulse: stop timer and remove files.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Uninstalling workpulse...")

        if not self.service_manager.is_timer_installed():
            print("Timer is not installed. Nothing to uninstall.")
            return 0

        # Stop and disable timer first
        if self.service_manager.is_timer_running():
            if not self.service_manager.stop_timer():
                print("WARNING: Failed to stop timer")
            else:
                print("✓ Timer stopped")

        if self.service_manager.is_timer_enabled():
            if not self.service_manager.disable_timer():
                print("WARNING: Failed to disable timer")
            else:
                print("✓ Timer disabled")

        # Uninstall timer (removes timer file)
        if not self.service_manager.uninstall_timer():
            print("ERROR: Failed to uninstall timer")
            return 1
        print("✓ Timer file removed")

        # Reload daemon
        if not self.service_manager.reload_daemon():
            print("WARNING: Failed to reload systemd daemon")
        else:
            print("✓ Systemd daemon reloaded")

        print("\nworkpulse has been uninstalled successfully!")
        print("Note: Database files in ~/.workpulse/ were not removed.")
        print("      To remove them manually, delete ~/.workpulse/ directory.")
        return 0

    def status(self) -> int:
        """Show current tracking status.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        # Check timer status
        if not self.service_manager.is_timer_installed():
            print("Timer status: Not installed")
            print("\nRun 'workpulse install' to set up tracking.")
            return 1

        is_running = self.service_manager.is_timer_running()
        is_enabled = self.service_manager.is_timer_enabled()

        print("Timer status:")
        print(f"  Installed: Yes")
        print(f"  Enabled: {'Yes' if is_enabled else 'No'}")
        print(f"  Running: {'Yes' if is_running else 'No'}")

        # Get current status
        tracker = WorkTracker()
        try:
            status_str, total_seconds = tracker.get_current_status()

            print("\nCurrent state:")
            print(f"  Status: {status_str}")

            # Get today's summary
            db = Database()
            today_log = db.get_today_log()
            db.close()

            print("\nToday's summary:")
            hours = int(today_log.total_active_time // 3600)
            minutes = int((today_log.total_active_time % 3600) // 60)
            last_update = today_log.last_update.strftime("%H:%M")
            print(f"  Total active time: {hours:02d}:{minutes:02d}")
            print(f"  Last update: {last_update}")

        except Exception as e:
            print(f"\nERROR: Failed to get status: {e}")
            return 1

        return 0

    def update(self) -> int:
        """Update time tracking (called by systemd timer every minute).

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        # Setup logging
        import logging

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        tracker = WorkTracker()
        try:
            tracker.update_time()
            return 0
        except Exception as e:
            logging.error(f"Update error: {e}", exc_info=True)
            return 1

    def mqtt_install(self) -> int:
        """Install and set up MQTT publisher systemd service.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Installing MQTT publisher service...")

        # Create default MQTT config file if it doesn't exist
        try:
            config_path = create_default_config()
            print(f"✓ MQTT configuration file created: {config_path}")
            print("  NOTE: Please edit the file to set your MQTT broker IP address")
        except OSError as e:
            print(f"WARNING: Failed to create MQTT configuration file: {e}")

        # Install service if not already installed
        if not self.service_manager.is_mqtt_service_installed():
            print("Installing MQTT service unit...")
            if not self.service_manager.install_mqtt_service():
                print("ERROR: Failed to install MQTT service")
                return 1
            print("✓ MQTT service installed")

            # Reload daemon
            if not self.service_manager.reload_daemon():
                print("WARNING: Failed to reload systemd daemon")
            else:
                print("✓ Systemd daemon reloaded")
        else:
            print("✓ MQTT service already installed")

        # Enable service
        if not self.service_manager.enable_mqtt_service():
            print("ERROR: Failed to enable MQTT service")
            return 1
        print("✓ MQTT service enabled")

        # Start service
        if not self.service_manager.start_mqtt_service():
            print("ERROR: Failed to start MQTT service")
            return 1
        print("✓ MQTT service started")

        print("\nMQTT publisher service has been installed and started successfully!")
        print("Use 'workpulse mqtt status' to check service status.")
        return 0

    def mqtt_start(self, as_service: bool = False) -> int:
        """Start the MQTT publisher daemon.

        Args:
            as_service: If True, start as systemd service. If False, run in foreground.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        if as_service:
            return self._mqtt_start_service()
        else:
            return self._mqtt_start_foreground()

    def _mqtt_start_foreground(self) -> int:
        """Start MQTT publisher in foreground.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Starting MQTT publisher...")

        try:
            config = load_config()
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            return 1
        except ValueError as e:
            print(f"ERROR: Invalid configuration: {e}")
            return 1

        tracker = WorkTracker()
        client = MQTTClient(config, tracker)

        if not client.start():
            print("ERROR: Failed to start MQTT publisher")
            return 1

        print("✓ MQTT publisher started")
        print("Press Ctrl+C to stop...")

        # Handle graceful shutdown
        def signal_handler(sig, frame):
            print("\nStopping MQTT publisher...")
            client.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Keep running until interrupted
        try:
            while client.is_running():
                time.sleep(1)
        except KeyboardInterrupt:
            signal_handler(None, None)

        return 0

    def _mqtt_start_service(self) -> int:
        """Start MQTT publisher as systemd service.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Starting MQTT publisher as systemd service...")

        # Install service if not already installed
        if not self.service_manager.is_mqtt_service_installed():
            print("Installing MQTT service...")
            if not self.service_manager.install_mqtt_service():
                print("ERROR: Failed to install MQTT service")
                return 1
            print("✓ MQTT service installed")

            # Reload daemon
            if not self.service_manager.reload_daemon():
                print("WARNING: Failed to reload systemd daemon")
            else:
                print("✓ Systemd daemon reloaded")

        # Enable service
        if not self.service_manager.enable_mqtt_service():
            print("ERROR: Failed to enable MQTT service")
            return 1
        print("✓ MQTT service enabled")

        # Start service
        if not self.service_manager.start_mqtt_service():
            print("ERROR: Failed to start MQTT service")
            return 1
        print("✓ MQTT service started")

        print("\nMQTT publisher service is now running.")
        print("Use 'workpulse mqtt status' to check service status.")
        return 0

    def mqtt_stop(self) -> int:
        """Stop the MQTT publisher service.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Stopping MQTT publisher service...")

        if not self.service_manager.is_mqtt_service_installed():
            print("ERROR: MQTT service is not installed")
            return 1

        if not self.service_manager.stop_mqtt_service():
            print("ERROR: Failed to stop MQTT service")
            return 1

        if not self.service_manager.disable_mqtt_service():
            print("WARNING: Failed to disable MQTT service")
        else:
            print("✓ MQTT service stopped and disabled")

        print("MQTT publisher service has been stopped.")
        return 0

    def mqtt_uninstall(self) -> int:
        """Uninstall the MQTT publisher service.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Uninstalling MQTT publisher service...")

        if not self.service_manager.is_mqtt_service_installed():
            print("MQTT service is not installed. Nothing to uninstall.")
            return 0

        # Stop and disable service first
        if self.service_manager.is_mqtt_service_running():
            if not self.service_manager.stop_mqtt_service():
                print("WARNING: Failed to stop MQTT service")
            else:
                print("✓ MQTT service stopped")

        if self.service_manager.is_mqtt_service_enabled():
            if not self.service_manager.disable_mqtt_service():
                print("WARNING: Failed to disable MQTT service")
            else:
                print("✓ MQTT service disabled")

        # Remove service file
        if not self.service_manager.uninstall_mqtt_service():
            print("ERROR: Failed to uninstall MQTT service")
            return 1

        # Reload daemon
        if not self.service_manager.reload_daemon():
            print("WARNING: Failed to reload systemd daemon")
        else:
            print("✓ Systemd daemon reloaded")

        print("MQTT publisher service has been uninstalled successfully!")
        return 0

    def mqtt_status(self) -> int:
        """Show MQTT publisher status.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        try:
            config = load_config()
            print("MQTT Configuration:")
            print(f"  Broker: {config.broker_ip}:{config.port}")
            print(f"  Topic prefix: {config.topic_prefix}")
            print(f"  Update interval: {config.update_interval}s")
            print(f"  QoS: {config.qos}")
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            return 1
        except ValueError as e:
            print(f"ERROR: Invalid configuration: {e}")
            return 1

        # Check MQTT service status
        print("\nMQTT Service Status:")
        if self.service_manager.is_mqtt_service_installed():
            is_running = self.service_manager.is_mqtt_service_running()
            is_enabled = self.service_manager.is_mqtt_service_enabled()
            print(f"  Installed: Yes")
            print(f"  Enabled: {'Yes' if is_enabled else 'No'}")
            print(f"  Running: {'Yes' if is_running else 'No'}")
        else:
            print(f"  Installed: No")
            print(f"  Enabled: No")
            print(f"  Running: No")

        print("\nUsage:")
        print("  'workpulse mqtt start service' - Start MQTT publisher as service")
        print("  'workpulse mqtt stop' - Stop MQTT publisher service")
        return 0

    def mqtt_publish(self) -> int:
        """Manually publish current status to MQTT broker (for testing).

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Publishing status to MQTT broker...")

        try:
            config = load_config()
        except FileNotFoundError as e:
            print(f"ERROR: {e}")
            return 1
        except ValueError as e:
            print(f"ERROR: Invalid configuration: {e}")
            return 1

        tracker = WorkTracker()
        client = MQTTClient(config, tracker)

        if not client.connect():
            print("ERROR: Failed to connect to MQTT broker")
            return 1

        if client.publish_status():
            print("✓ Status published successfully")
            client.disconnect()
            return 0
        else:
            print("ERROR: Failed to publish status")
            client.disconnect()
            return 1

    def mqtt_yaml(self) -> int:
        """Generate Home Assistant YAML configuration.

        Generates complete YAML configuration with hostname automatically filled in.
        Output can be copied and pasted directly into Home Assistant's configuration.yaml.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        yaml_config = generate_yaml_config()

        print("Home Assistant YAML Configuration:")
        print("=" * 60)
        print(yaml_config)
        print("=" * 60)
        print("\nInstructions:")
        print("1. Copy the YAML configuration above")
        print("2. Paste it into your Home Assistant configuration.yaml file")
        print("3. Restart Home Assistant (or reload MQTT integration)")
        print("4. Ensure WorkPulse MQTT publisher is running: workpulse mqtt start")

        return 0


def main() -> int:
    """Main entry point for workpulse CLI.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="WorkPulse - Track working time using systemd login information"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Install command
    install_parser = subparsers.add_parser(
        "install", help="Install and start workpulse"
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop workpulse timer")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start workpulse timer")

    # Uninstall command
    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Uninstall workpulse timer"
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Show current tracking status")

    # Update command (called by systemd timer)
    update_parser = subparsers.add_parser(
        "update", help="Updates the tracked time (called by systemd timer)"
    )

    # MQTT commands
    mqtt_parser = subparsers.add_parser("mqtt", help="MQTT publisher commands")
    mqtt_subparsers = mqtt_parser.add_subparsers(
        dest="mqtt_command", help="MQTT command"
    )

    mqtt_install_parser = mqtt_subparsers.add_parser(
        "install", help="Install and set up MQTT publisher service"
    )
    mqtt_start_parser = mqtt_subparsers.add_parser(
        "start", help="Start MQTT publisher (specify 'local' or 'service')"
    )
    mqtt_start_subparsers = mqtt_start_parser.add_subparsers(
        dest="mqtt_start_mode", help="Start mode (required)", required=True
    )
    mqtt_start_subparsers.add_parser(
        "local", help="Run MQTT publisher in foreground (local terminal)"
    )
    mqtt_start_subparsers.add_parser(
        "service", help="Run MQTT publisher as systemd service (background)"
    )

    mqtt_stop_parser = mqtt_subparsers.add_parser(
        "stop", help="Stop MQTT publisher service"
    )
    mqtt_uninstall_parser = mqtt_subparsers.add_parser(
        "uninstall", help="Uninstall MQTT publisher service"
    )
    mqtt_status_parser = mqtt_subparsers.add_parser(
        "status", help="Show MQTT configuration and service status"
    )
    mqtt_publish_parser = mqtt_subparsers.add_parser(
        "publish", help="Manually publish status (for testing)"
    )
    mqtt_yaml_parser = mqtt_subparsers.add_parser(
        "yaml", help="Generate Home Assistant YAML configuration"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    cli = WorkPulseCLI()

    if args.command == "install":
        return cli.install()
    elif args.command == "stop":
        return cli.stop()
    elif args.command == "start":
        return cli.start()
    elif args.command == "uninstall":
        return cli.uninstall()
    elif args.command == "status":
        return cli.status()
    elif args.command == "update":
        return cli.update()
    elif args.command == "mqtt":
        if not args.mqtt_command:
            mqtt_parser.print_help()
            return 1
        elif args.mqtt_command == "install":
            return cli.mqtt_install()
        elif args.mqtt_command == "start":
            as_service = args.mqtt_start_mode == "service"
            return cli.mqtt_start(as_service=as_service)
        elif args.mqtt_command == "stop":
            return cli.mqtt_stop()
        elif args.mqtt_command == "uninstall":
            return cli.mqtt_uninstall()
        elif args.mqtt_command == "status":
            return cli.mqtt_status()
        elif args.mqtt_command == "publish":
            return cli.mqtt_publish()
        elif args.mqtt_command == "yaml":
            return cli.mqtt_yaml()
        else:
            mqtt_parser.print_help()
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
