"""Tests for service module."""

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from worktracker.service import ServiceManager


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
        assert service_manager.timer_path == expected_dir / "worktracker.timer"
        assert service_manager.service_path == expected_dir / "worktracker.service"

    @patch("worktracker.service.shutil.which")
    def test_get_python_executable_finds_python3(self, mock_which, service_manager):
        """Test _get_python_executable finds python3."""
        mock_which.return_value = "/usr/bin/python3"
        assert service_manager._get_python_executable() == "/usr/bin/python3"
        mock_which.assert_called_once_with("python3")

    @patch("worktracker.service.shutil.which")
    def test_get_python_executable_falls_back_to_python(self, mock_which, service_manager):
        """Test _get_python_executable falls back to python."""
        mock_which.side_effect = lambda cmd: "/usr/bin/python" if cmd == "python" else None
        assert service_manager._get_python_executable() == "/usr/bin/python"

    @patch("worktracker.service.shutil.which")
    def test_get_python_executable_defaults_to_python3(self, mock_which, service_manager):
        """Test _get_python_executable defaults to python3 string."""
        mock_which.return_value = None
        assert service_manager._get_python_executable() == "python3"

    @patch("worktracker.service.shutil.which")
    def test_get_worktracker_command_finds_worktracker(self, mock_which, service_manager):
        """Test _get_worktracker_command finds worktracker in PATH."""
        mock_which.side_effect = lambda cmd: "/usr/bin/worktracker" if cmd == "worktracker" else "/usr/bin/python3"
        assert service_manager._get_worktracker_command() == "/usr/bin/worktracker update"

    @patch("worktracker.service.shutil.which")
    def test_get_worktracker_command_falls_back_to_python_module(self, mock_which, service_manager):
        """Test _get_worktracker_command falls back to python -m worktracker."""
        mock_which.side_effect = lambda cmd: "/usr/bin/python3" if cmd == "python3" else None
        assert service_manager._get_worktracker_command() == "/usr/bin/python3 -m worktracker update"

    def test_generate_service_unit(self, service_manager):
        """Test generate_service_unit creates correct content."""
        with patch.object(service_manager, "_get_worktracker_command", return_value="worktracker update"):
            content = service_manager.generate_service_unit()

            assert "[Unit]" in content
            assert "Description=WorkTracker - Track working time using systemd timer" in content
            assert "[Service]" in content
            assert "Type=oneshot" in content
            assert "ExecStart=worktracker update" in content
            assert "StandardOutput=journal" in content
            assert "StandardError=journal" in content

    def test_generate_timer_unit(self, service_manager):
        """Test generate_timer_unit creates correct content."""
        content = service_manager.generate_timer_unit()

        assert "[Unit]" in content
        assert "Description=WorkTracker Timer - Update working time every minute" in content
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

    @patch("worktracker.service.subprocess.run")
    def test_enable_timer_success(self, mock_subprocess, service_manager):
        """Test enable_timer succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.enable_timer() is True
        mock_subprocess.assert_called_once_with(
            ["systemctl", "--user", "enable", "worktracker.timer"],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("worktracker.service.subprocess.run")
    def test_enable_timer_failure(self, mock_subprocess, service_manager):
        """Test enable_timer fails when systemctl returns non-zero."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.enable_timer() is False

    @patch("worktracker.service.subprocess.run")
    def test_disable_timer_success(self, mock_subprocess, service_manager):
        """Test disable_timer succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.disable_timer() is True

    @patch("worktracker.service.subprocess.run")
    def test_start_timer_success(self, mock_subprocess, service_manager):
        """Test start_timer succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.start_timer() is True

    @patch("worktracker.service.subprocess.run")
    def test_stop_timer_success(self, mock_subprocess, service_manager):
        """Test stop_timer succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.stop_timer() is True

    @patch("worktracker.service.subprocess.run")
    def test_get_timer_status_active(self, mock_subprocess, service_manager):
        """Test get_timer_status returns active."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "active\n"
        mock_subprocess.return_value = mock_result

        assert service_manager.get_timer_status() == "active"

    @patch("worktracker.service.subprocess.run")
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

    @patch("worktracker.service.subprocess.run")
    def test_is_timer_enabled_true(self, mock_subprocess, service_manager):
        """Test is_timer_enabled returns True when enabled."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "enabled\n"
        mock_subprocess.return_value = mock_result

        assert service_manager.is_timer_enabled() is True

    @patch("worktracker.service.subprocess.run")
    def test_is_timer_enabled_false(self, mock_subprocess, service_manager):
        """Test is_timer_enabled returns False when not enabled."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.is_timer_enabled() is False

    @patch("worktracker.service.subprocess.run")
    def test_is_timer_running_true(self, mock_subprocess, service_manager):
        """Test is_timer_running returns True when active."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "active\n"
        mock_subprocess.return_value = mock_result

        assert service_manager.is_timer_running() is True

    @patch("worktracker.service.subprocess.run")
    def test_is_timer_running_false(self, mock_subprocess, service_manager):
        """Test is_timer_running returns False when not active."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.is_timer_running() is False

    @patch("worktracker.service.subprocess.run")
    def test_reload_daemon_success(self, mock_subprocess, service_manager):
        """Test reload_daemon succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        assert service_manager.reload_daemon() is True

    @patch("worktracker.service.subprocess.run")
    def test_reload_daemon_failure(self, mock_subprocess, service_manager):
        """Test reload_daemon fails when systemctl returns non-zero."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        assert service_manager.reload_daemon() is False
