"""Systemd timer management for workpulse."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional


class ServiceManager:
    """Manages systemd user timer and service installation and control."""

    TIMER_NAME = "workpulse.timer"
    SERVICE_NAME = "workpulse.service"
    SERVICE_DESCRIPTION = "WorkPulse - Track working time using systemd timer"

    MQTT_SERVICE_NAME = "workpulse-mqtt.service"
    MQTT_SERVICE_DESCRIPTION = "WorkPulse MQTT Publisher"

    def __init__(self) -> None:
        """Initialize the service manager."""
        self.systemd_user_dir = Path.home() / ".config" / "systemd" / "user"
        self.timer_path = self.systemd_user_dir / self.TIMER_NAME
        self.service_path = self.systemd_user_dir / self.SERVICE_NAME
        self.mqtt_service_path = self.systemd_user_dir / self.MQTT_SERVICE_NAME

    def _get_python_executable(self) -> str:
        """Get the Python executable path.

        Returns:
            Path to Python executable
        """
        return shutil.which("python3") or shutil.which("python") or "python3"

    def _get_workpulse_command(self) -> str:
        """Get the workpulse command to run.

        Returns:
            Command string to run workpulse update
        """
        python = self._get_python_executable()
        # Try to find workpulse in PATH first
        workpulse_cmd = shutil.which("workpulse")
        if workpulse_cmd:
            return f"{workpulse_cmd} update"

        # Fallback to python -m workpulse
        return f"{python} -m workpulse update"

    def generate_service_unit(self) -> str:
        """Generate systemd user service unit file content.

        Returns:
            Service unit file content as string
        """
        command = self._get_workpulse_command()

        unit_content = f"""[Unit]
Description={self.SERVICE_DESCRIPTION}

[Service]
Type=oneshot
ExecStart={command}
StandardOutput=journal
StandardError=journal
"""
        return unit_content

    def generate_timer_unit(self) -> str:
        """Generate systemd user timer unit file content.

        Returns:
            Timer unit file content as string
        """
        unit_content = f"""[Unit]
Description=WorkPulse Timer - Update working time every minute
Requires={self.SERVICE_NAME}

[Timer]
OnCalendar=*:0/1
AccuracySec=1s

[Install]
WantedBy=timers.target
"""
        return unit_content

    def install_timer(self) -> bool:
        """Install the systemd user timer and service.

        Returns:
            True if installation succeeded, False otherwise
        """
        try:
            # Create systemd user directory if it doesn't exist
            self.systemd_user_dir.mkdir(parents=True, exist_ok=True)

            # Generate and write service unit
            service_content = self.generate_service_unit()
            self.service_path.write_text(service_content)
            self.service_path.chmod(0o644)

            # Generate and write timer unit
            timer_content = self.generate_timer_unit()
            self.timer_path.write_text(timer_content)
            self.timer_path.chmod(0o644)

            return True
        except Exception as e:
            print(f"Error installing timer: {e}")
            return False

    def uninstall_timer(self) -> bool:
        """Uninstall the systemd user timer and service.

        Returns:
            True if uninstallation succeeded, False otherwise
        """
        try:
            # Stop and disable first
            self.stop_timer()
            self.disable_timer()

            # Remove timer file
            if self.timer_path.exists():
                self.timer_path.unlink()

            # Remove service file
            if self.service_path.exists():
                self.service_path.unlink()

            return True
        except Exception as e:
            print(f"Error uninstalling timer: {e}")
            return False

    def enable_timer(self) -> bool:
        """Enable the systemd user timer.

        Returns:
            True if enabling succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "enable", self.TIMER_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error enabling timer: {e}")
            return False

    def disable_timer(self) -> bool:
        """Disable the systemd user timer.

        Returns:
            True if disabling succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "disable", self.TIMER_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error disabling timer: {e}")
            return False

    def start_timer(self) -> bool:
        """Start the systemd user timer.

        Returns:
            True if starting succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "start", self.TIMER_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error starting timer: {e}")
            return False

    def stop_timer(self) -> bool:
        """Stop the systemd user timer.

        Returns:
            True if stopping succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "stop", self.TIMER_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error stopping timer: {e}")
            return False

    def get_timer_status(self) -> Optional[str]:
        """Get the status of the systemd user timer.

        Returns:
            Status string if available, None otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", self.TIMER_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return "inactive"
        except Exception:
            return None

    def is_timer_installed(self) -> bool:
        """Check if the timer is installed.

        Returns:
            True if timer file exists, False otherwise
        """
        return self.timer_path.exists()

    def is_timer_enabled(self) -> bool:
        """Check if the timer is enabled.

        Returns:
            True if timer is enabled, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-enabled", self.TIMER_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0 and "enabled" in result.stdout
        except Exception:
            return False

    def is_timer_running(self) -> bool:
        """Check if the timer is currently running.

        Returns:
            True if timer is active, False otherwise
        """
        status = self.get_timer_status()
        return status == "active"

    def reload_daemon(self) -> bool:
        """Reload systemd daemon to pick up timer changes.

        Returns:
            True if reload succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error reloading daemon: {e}")
            return False

    # MQTT Service methods
    def generate_mqtt_service_unit(self) -> str:
        """Generate systemd user MQTT service unit file content.

        Returns:
            Service unit file content as string
        """
        python = self._get_python_executable()
        workpulse_cmd = shutil.which("workpulse")
        if workpulse_cmd:
            mqtt_start_cmd = f"{workpulse_cmd} mqtt start local"
        else:
            mqtt_start_cmd = f"{python} -m workpulse mqtt start local"

        unit_content = f"""[Unit]
Description={self.MQTT_SERVICE_DESCRIPTION}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={mqtt_start_cmd}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
"""
        return unit_content

    def install_mqtt_service(self) -> bool:
        """Install the systemd user MQTT service.

        Returns:
            True if installation succeeded, False otherwise
        """
        try:
            # Create systemd user directory if it doesn't exist
            self.systemd_user_dir.mkdir(parents=True, exist_ok=True)

            # Generate and write MQTT service unit
            mqtt_service_content = self.generate_mqtt_service_unit()
            self.mqtt_service_path.write_text(mqtt_service_content)
            self.mqtt_service_path.chmod(0o644)

            return True
        except Exception as e:
            print(f"Error installing MQTT service: {e}")
            return False

    def uninstall_mqtt_service(self) -> bool:
        """Uninstall the systemd user MQTT service.

        Returns:
            True if uninstallation succeeded, False otherwise
        """
        try:
            # Stop and disable first
            self.stop_mqtt_service()
            self.disable_mqtt_service()

            # Remove service file
            if self.mqtt_service_path.exists():
                self.mqtt_service_path.unlink()

            return True
        except Exception as e:
            print(f"Error uninstalling MQTT service: {e}")
            return False

    def enable_mqtt_service(self) -> bool:
        """Enable the systemd user MQTT service.

        Returns:
            True if enabling succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "enable", self.MQTT_SERVICE_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error enabling MQTT service: {e}")
            return False

    def disable_mqtt_service(self) -> bool:
        """Disable the systemd user MQTT service.

        Returns:
            True if disabling succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "disable", self.MQTT_SERVICE_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error disabling MQTT service: {e}")
            return False

    def start_mqtt_service(self) -> bool:
        """Start the systemd user MQTT service.

        Returns:
            True if starting succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "start", self.MQTT_SERVICE_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error starting MQTT service: {e}")
            return False

    def stop_mqtt_service(self) -> bool:
        """Stop the systemd user MQTT service.

        Returns:
            True if stopping succeeded, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "stop", self.MQTT_SERVICE_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            print(f"Error stopping MQTT service: {e}")
            return False

    def is_mqtt_service_installed(self) -> bool:
        """Check if the MQTT service is installed.

        Returns:
            True if MQTT service file exists, False otherwise
        """
        return self.mqtt_service_path.exists()

    def is_mqtt_service_enabled(self) -> bool:
        """Check if the MQTT service is enabled.

        Returns:
            True if MQTT service is enabled, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-enabled", self.MQTT_SERVICE_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0 and "enabled" in result.stdout
        except Exception:
            return False

    def is_mqtt_service_running(self) -> bool:
        """Check if the MQTT service is currently running.

        Returns:
            True if MQTT service is active, False otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", self.MQTT_SERVICE_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0 and "active" in result.stdout
        except Exception:
            return False

    def get_mqtt_service_status(self) -> Optional[str]:
        """Get the status of the systemd user MQTT service.

        Returns:
            Status string if available, None otherwise
        """
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", self.MQTT_SERVICE_NAME],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return "inactive"
        except Exception:
            return None
