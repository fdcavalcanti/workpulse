"""Command-line interface for worktracker."""

import argparse
import signal
import sys
import time
from pathlib import Path

from .database import Database
from .mqtt_client import MQTTClient
from .mqtt_config import create_default_config, load_config
from .service import ServiceManager
from .tracker import WorkTracker


class WorkTrackerCLI:
    """Command-line interface for worktracker."""

    def __init__(self) -> None:
        """Initialize the CLI."""
        self.service_manager = ServiceManager()

    def install(self) -> int:
        """Install worktracker: initialize database and install systemd timer.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Installing worktracker...")

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

        print("\nworktracker has been installed and started successfully!")
        print("The timer will update your working time every minute.")
        return 0

    def stop(self) -> int:
        """Stop the worktracker timer.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Stopping worktracker timer...")

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

        print("worktracker timer has been stopped.")
        return 0

    def start(self) -> int:
        """Start the worktracker timer.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Starting worktracker timer...")

        if not self.service_manager.is_timer_installed():
            print("ERROR: Timer is not installed")
            print("Run 'worktracker install' to set up the timer first.")
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

        print("worktracker timer is now running.")
        return 0

    def uninstall(self) -> int:
        """Uninstall worktracker: stop timer and remove files.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Uninstalling worktracker...")

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

        print("\nworktracker has been uninstalled successfully!")
        print("Note: Database files in ~/.worktracker/ were not removed.")
        print("      To remove them manually, delete ~/.worktracker/ directory.")
        return 0

    def status(self) -> int:
        """Show current tracking status.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        # Check timer status
        if not self.service_manager.is_timer_installed():
            print("Timer status: Not installed")
            print("\nRun 'worktracker install' to set up tracking.")
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

    def mqtt_start(self) -> int:
        """Start the MQTT publisher daemon.

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

    def mqtt_stop(self) -> int:
        """Stop the MQTT publisher daemon.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        print("Stopping MQTT publisher...")
        print("NOTE: If MQTT publisher is running in another terminal, use Ctrl+C there.")
        print("      This command is for future systemd service integration.")
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

        print("\nNOTE: Use 'worktracker mqtt start' to run the publisher.")
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


def main() -> int:
    """Main entry point for worktracker CLI.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Track working time using systemd login information"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Install command
    install_parser = subparsers.add_parser("install", help="Install and start worktracker")

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop worktracker timer")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start worktracker timer")

    # Uninstall command
    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Uninstall worktracker timer"
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Show current tracking status")

    # Update command (internal, called by systemd timer)
    # Hidden from help - users shouldn't need to call this directly
    update_parser = subparsers.add_parser(
        "update", help=argparse.SUPPRESS
    )

    # MQTT commands
    mqtt_parser = subparsers.add_parser("mqtt", help="MQTT publisher commands")
    mqtt_subparsers = mqtt_parser.add_subparsers(dest="mqtt_command", help="MQTT command")

    mqtt_start_parser = mqtt_subparsers.add_parser("start", help="Start MQTT publisher daemon")
    mqtt_stop_parser = mqtt_subparsers.add_parser("stop", help="Stop MQTT publisher daemon")
    mqtt_status_parser = mqtt_subparsers.add_parser("status", help="Show MQTT configuration status")
    mqtt_publish_parser = mqtt_subparsers.add_parser("publish", help="Manually publish status (for testing)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    cli = WorkTrackerCLI()

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
        elif args.mqtt_command == "start":
            return cli.mqtt_start()
        elif args.mqtt_command == "stop":
            return cli.mqtt_stop()
        elif args.mqtt_command == "status":
            return cli.mqtt_status()
        elif args.mqtt_command == "publish":
            return cli.mqtt_publish()
        else:
            mqtt_parser.print_help()
            return 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
