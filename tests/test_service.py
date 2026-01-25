"""Tests for service module."""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from workpulse.service import ServiceManager


class TestServiceManager:
    """Test suite for ServiceManager class."""

    @pytest.fixture
    def service_manager(self, tmp_path, monkeypatch):
        """Create a ServiceManager instance with temporary paths."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        return ServiceManager()

    def test_init(self, service_manager, tmp_path):
        """Test ServiceManager initialization."""
        expected_dir = tmp_path / ".config" / "systemd" / "user"
        assert service_manager.systemd_user_dir == expected_dir
        assert service_manager.timer_path == expected_dir / "workpulse.timer"
        assert service_manager.service_path == expected_dir / "workpulse.service"
        assert (
            service_manager.mqtt_service_path == expected_dir / "workpulse-mqtt.service"
        )

    @patch("workpulse.service.shutil.which")
    def test_get_python_executable_finds_python3(self, mock_which, service_manager):
        """Test _get_python_executable finds python3."""
        mock_which.return_value = "/usr/bin/python3"
        assert service_manager._get_python_executable() == "/usr/bin/python3"
        mock_which.assert_called_once_with("python3")

    @patch("workpulse.service.shutil.which")
    def test_get_python_executable_falls_back_to_python(
        self, mock_which, service_manager
    ):
        """Test _get_python_executable falls back to python."""
        mock_which.side_effect = (
            lambda cmd: "/usr/bin/python" if cmd == "python" else None
        )
        assert service_manager._get_python_executable() == "/usr/bin/python"

    @patch("workpulse.service.shutil.which")
    def test_get_python_executable_defaults_to_python3(
        self, mock_which, service_manager
    ):
        """Test _get_python_executable defaults to python3 string."""
        mock_which.return_value = None
        assert service_manager._get_python_executable() == "python3"

    @patch("workpulse.service.shutil.which")
    def test_get_workpulse_command_finds_workpulse(self, mock_which, service_manager):
        """Test _get_workpulse_command finds workpulse in PATH."""
        mock_which.side_effect = (
            lambda cmd: "/usr/bin/workpulse"
            if cmd == "workpulse"
            else "/usr/bin/python3"
        )
        assert service_manager._get_workpulse_command() == "/usr/bin/workpulse update"

    @patch("workpulse.service.shutil.which")
    def test_get_workpulse_command_falls_back_to_python_module(
        self, mock_which, service_manager
    ):
        """Test _get_workpulse_command falls back to python -m workpulse."""
        mock_which.side_effect = (
            lambda cmd: "/usr/bin/python3" if cmd == "python3" else None
        )
        assert (
            service_manager._get_workpulse_command()
            == "/usr/bin/python3 -m workpulse update"
        )

    def test_generate_service_unit(self, service_manager):
        """Test generate_service_unit creates correct content."""
        with patch.object(
            service_manager,
            "_get_workpulse_command",
            return_value="workpulse update",
        ):
            content = service_manager.generate_service_unit()

            assert "[Unit]" in content
            assert (
                "Description=WorkPulse - Track working time using systemd timer"
                in content
            )
            assert "[Service]" in content
            assert "Type=oneshot" in content
            assert "ExecStart=workpulse update" in content
            assert "StandardOutput=journal" in content
            assert "StandardError=journal" in content

    def test_generate_timer_unit(self, service_manager):
        """Test generate_timer_unit creates correct content."""
        content = service_manager.generate_timer_unit()

        assert "[Unit]" in content
        assert (
            "Description=WorkPulse Timer - Update working time every minute" in content
        )
        assert f"Requires={service_manager.SERVICE_NAME}" in content
        assert "[Timer]" in content
        assert "OnCalendar=*:0/1" in content
        assert "AccuracySec=1s" in content
        assert "[Install]" in content
        assert "WantedBy=timers.target" in content

    def test_install_timer_creates_files(self, service_manager):
        """Test install_timer creates timer and service files."""
        assert service_manager.install_timer() is True
        assert service_manager.timer_path.exists()
        assert service_manager.service_path.exists()
        assert service_manager.timer_path.stat().st_mode & 0o777 == 0o644
        assert service_manager.service_path.stat().st_mode & 0o777 == 0o644

    def test_install_timer_creates_directory(self, service_manager):
        """Test install_timer creates systemd user directory if it doesn't exist."""
        assert not service_manager.systemd_user_dir.exists()
        assert service_manager.install_timer() is True
        assert service_manager.systemd_user_dir.exists()

    def test_uninstall_timer_removes_files(self, service_manager):
        """Test uninstall_timer removes timer and service files."""
        # Install first
        service_manager.install_timer()
        assert service_manager.timer_path.exists()
        assert service_manager.service_path.exists()

        # Uninstall
        with patch.object(service_manager, "stop_timer", return_value=True):
            with patch.object(service_manager, "disable_timer", return_value=True):
                assert service_manager.uninstall_timer() is True

        assert not service_manager.timer_path.exists()
        assert not service_manager.service_path.exists()

    @patch("workpulse.service.subprocess.run")
    def test_enable_timer_success(self, mock_subprocess, service_manager):
        """Test enable_timer succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.enable_timer() is True
        mock_subprocess.assert_called_once_with(
            ["systemctl", "--user", "enable", "workpulse.timer"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("workpulse.service.subprocess.run")
    def test_enable_timer_failure(self, mock_subprocess, service_manager):
        """Test enable_timer fails when systemctl returns non-zero."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.enable_timer() is False

    @patch("workpulse.service.subprocess.run")
    def test_disable_timer_success(self, mock_subprocess, service_manager):
        """Test disable_timer succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.disable_timer() is True

    @patch("workpulse.service.subprocess.run")
    def test_start_timer_success(self, mock_subprocess, service_manager):
        """Test start_timer succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.start_timer() is True

    @patch("workpulse.service.subprocess.run")
    def test_stop_timer_success(self, mock_subprocess, service_manager):
        """Test stop_timer succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.stop_timer() is True

    @patch("workpulse.service.subprocess.run")
    def test_get_timer_status_active(self, mock_subprocess, service_manager):
        """Test get_timer_status returns active."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "active\n"
        mock_subprocess.return_value = mock_result

        assert service_manager.get_timer_status() == "active"

    @patch("workpulse.service.subprocess.run")
    def test_get_timer_status_inactive(self, mock_subprocess, service_manager):
        """Test get_timer_status returns inactive when not active."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.get_timer_status() == "inactive"

    def test_is_timer_installed_true(self, service_manager):
        """Test is_timer_installed returns True when timer exists."""
        service_manager.install_timer()
        assert service_manager.is_timer_installed() is True

    def test_is_timer_installed_false(self, service_manager):
        """Test is_timer_installed returns False when timer doesn't exist."""
        assert service_manager.is_timer_installed() is False

    @patch("workpulse.service.subprocess.run")
    def test_is_timer_enabled_true(self, mock_subprocess, service_manager):
        """Test is_timer_enabled returns True when enabled."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "enabled\n"
        mock_subprocess.return_value = mock_result

        assert service_manager.is_timer_enabled() is True

    @patch("workpulse.service.subprocess.run")
    def test_is_timer_enabled_false(self, mock_subprocess, service_manager):
        """Test is_timer_enabled returns False when not enabled."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.is_timer_enabled() is False

    @patch("workpulse.service.subprocess.run")
    def test_is_timer_running_true(self, mock_subprocess, service_manager):
        """Test is_timer_running returns True when active."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "active\n"
        mock_subprocess.return_value = mock_result

        assert service_manager.is_timer_running() is True

    @patch("workpulse.service.subprocess.run")
    def test_is_timer_running_false(self, mock_subprocess, service_manager):
        """Test is_timer_running returns False when not active."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.is_timer_running() is False

    @patch("workpulse.service.subprocess.run")
    def test_reload_daemon_success(self, mock_subprocess, service_manager):
        """Test reload_daemon succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.reload_daemon() is True

    @patch("workpulse.service.subprocess.run")
    def test_reload_daemon_failure(self, mock_subprocess, service_manager):
        """Test reload_daemon fails when systemctl returns non-zero."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.reload_daemon() is False

    # MQTT Service Tests
    @patch("workpulse.service.shutil.which")
    def test_generate_mqtt_service_unit_with_workpulse_in_path(
        self, mock_which, service_manager
    ):
        """Test generate_mqtt_service_unit when workpulse is in PATH."""
        mock_which.side_effect = lambda cmd: (
            "/usr/local/bin/workpulse" if cmd == "workpulse" else None
        )
        content = service_manager.generate_mqtt_service_unit()
        assert "[Unit]" in content
        assert "WorkPulse MQTT Publisher" in content
        assert "ExecStart=/usr/local/bin/workpulse mqtt start" in content
        assert "Type=simple" in content
        assert "Restart=on-failure" in content

    @patch("workpulse.service.shutil.which")
    def test_generate_mqtt_service_unit_fallback_to_python(
        self, mock_which, service_manager
    ):
        """Test generate_mqtt_service_unit falls back to python -m."""
        mock_which.return_value = None
        service_manager._get_python_executable = MagicMock(
            return_value="/usr/bin/python3"
        )
        content = service_manager.generate_mqtt_service_unit()
        assert "python3 -m workpulse mqtt start" in content

    def test_install_mqtt_service(self, service_manager, tmp_path):
        """Test install_mqtt_service creates service file."""
        assert service_manager.install_mqtt_service() is True
        assert service_manager.mqtt_service_path.exists()
        content = service_manager.mqtt_service_path.read_text()
        assert "[Unit]" in content
        assert "[Service]" in content

    def test_uninstall_mqtt_service(self, service_manager):
        """Test uninstall_mqtt_service removes service file."""
        service_manager.mqtt_service_path.parent.mkdir(parents=True, exist_ok=True)
        service_manager.mqtt_service_path.write_text("[Unit]\nDescription=Test")
        assert service_manager.mqtt_service_path.exists()
        with patch.object(service_manager, "stop_mqtt_service", return_value=True):
            with patch.object(
                service_manager, "disable_mqtt_service", return_value=True
            ):
                assert service_manager.uninstall_mqtt_service() is True
        assert not service_manager.mqtt_service_path.exists()

    @patch("workpulse.service.subprocess.run")
    def test_enable_mqtt_service_success(self, mock_subprocess, service_manager):
        """Test enable_mqtt_service succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.enable_mqtt_service() is True
        mock_subprocess.assert_called_once_with(
            ["systemctl", "--user", "enable", "workpulse-mqtt.service"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("workpulse.service.subprocess.run")
    def test_enable_mqtt_service_failure(self, mock_subprocess, service_manager):
        """Test enable_mqtt_service fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.enable_mqtt_service() is False

    @patch("workpulse.service.subprocess.run")
    def test_disable_mqtt_service_success(self, mock_subprocess, service_manager):
        """Test disable_mqtt_service succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.disable_mqtt_service() is True

    @patch("workpulse.service.subprocess.run")
    def test_disable_mqtt_service_failure(self, mock_subprocess, service_manager):
        """Test disable_mqtt_service fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.disable_mqtt_service() is False

    @patch("workpulse.service.subprocess.run")
    def test_start_mqtt_service_success(self, mock_subprocess, service_manager):
        """Test start_mqtt_service succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.start_mqtt_service() is True

    @patch("workpulse.service.subprocess.run")
    def test_start_mqtt_service_failure(self, mock_subprocess, service_manager):
        """Test start_mqtt_service fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.start_mqtt_service() is False

    @patch("workpulse.service.subprocess.run")
    def test_stop_mqtt_service_success(self, mock_subprocess, service_manager):
        """Test stop_mqtt_service succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.stop_mqtt_service() is True

    @patch("workpulse.service.subprocess.run")
    def test_stop_mqtt_service_failure(self, mock_subprocess, service_manager):
        """Test stop_mqtt_service fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.stop_mqtt_service() is False

    def test_is_mqtt_service_installed_true(self, service_manager):
        """Test is_mqtt_service_installed returns True when file exists."""
        service_manager.mqtt_service_path.parent.mkdir(parents=True, exist_ok=True)
        service_manager.mqtt_service_path.write_text("[Unit]\nDescription=Test")
        assert service_manager.is_mqtt_service_installed() is True

    def test_is_mqtt_service_installed_false(self, service_manager):
        """Test is_mqtt_service_installed returns False when file doesn't exist."""
        assert service_manager.is_mqtt_service_installed() is False

    @patch("workpulse.service.subprocess.run")
    def test_is_mqtt_service_enabled_true(self, mock_subprocess, service_manager):
        """Test is_mqtt_service_enabled returns True when enabled."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "enabled\n"
        mock_subprocess.return_value = mock_result

        assert service_manager.is_mqtt_service_enabled() is True

    @patch("workpulse.service.subprocess.run")
    def test_is_mqtt_service_enabled_false(self, mock_subprocess, service_manager):
        """Test is_mqtt_service_enabled returns False when not enabled."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.is_mqtt_service_enabled() is False

    @patch("workpulse.service.subprocess.run")
    def test_is_mqtt_service_running_true(self, mock_subprocess, service_manager):
        """Test is_mqtt_service_running returns True when active."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "active\n"
        mock_subprocess.return_value = mock_result

        assert service_manager.is_mqtt_service_running() is True

    @patch("workpulse.service.subprocess.run")
    def test_is_mqtt_service_running_false(self, mock_subprocess, service_manager):
        """Test is_mqtt_service_running returns False when not active."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.is_mqtt_service_running() is False

    @patch("workpulse.service.subprocess.run")
    def test_get_mqtt_service_status_active(self, mock_subprocess, service_manager):
        """Test get_mqtt_service_status returns active."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "active\n"
        mock_subprocess.return_value = mock_result

        assert service_manager.get_mqtt_service_status() == "active"

    @patch("workpulse.service.subprocess.run")
    def test_get_mqtt_service_status_inactive(self, mock_subprocess, service_manager):
        """Test get_mqtt_service_status returns inactive."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.get_mqtt_service_status() == "inactive"
