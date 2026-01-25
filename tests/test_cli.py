"""Tests for CLI module."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from worktracker.cli import WorkTrackerCLI


class TestWorkTrackerCLI:
    """Test suite for WorkTrackerCLI class."""

    @pytest.fixture
    def cli(self):
        """Create a WorkTrackerCLI instance."""
        return WorkTrackerCLI()

    # MQTT Install Tests
    @patch("worktracker.cli.create_default_config")
    def test_mqtt_install_success(self, mock_create_config, cli, capsys):
        """Test mqtt_install succeeds with all steps."""
        mock_create_config.return_value = Path(
            "/home/user/.config/worktracker/mqtt.yaml"
        )
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=False)
        cli.service_manager.install_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.reload_daemon = MagicMock(return_value=True)
        cli.service_manager.enable_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.start_mqtt_service = MagicMock(return_value=True)

        result = cli.mqtt_install()

        assert result == 0
        mock_create_config.assert_called_once()
        cli.service_manager.install_mqtt_service.assert_called_once()
        cli.service_manager.reload_daemon.assert_called_once()
        cli.service_manager.enable_mqtt_service.assert_called_once()
        cli.service_manager.start_mqtt_service.assert_called_once()
        captured = capsys.readouterr()
        assert (
            "MQTT publisher service has been installed and started successfully"
            in captured.out
        )

    @patch("worktracker.cli.create_default_config")
    def test_mqtt_install_already_installed(self, mock_create_config, cli, capsys):
        """Test mqtt_install when service is already installed."""
        mock_create_config.return_value = Path(
            "/home/user/.config/worktracker/mqtt.yaml"
        )
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=True)
        cli.service_manager.enable_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.start_mqtt_service = MagicMock(return_value=True)

        result = cli.mqtt_install()

        assert result == 0
        cli.service_manager.install_mqtt_service = MagicMock()
        captured = capsys.readouterr()
        assert "MQTT service already installed" in captured.out

    @patch("worktracker.cli.create_default_config")
    def test_mqtt_install_install_fails(self, mock_create_config, cli, capsys):
        """Test mqtt_install fails when installation fails."""
        mock_create_config.return_value = Path(
            "/home/user/.config/worktracker/mqtt.yaml"
        )
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=False)
        cli.service_manager.install_mqtt_service = MagicMock(return_value=False)

        result = cli.mqtt_install()

        assert result == 1
        captured = capsys.readouterr()
        assert "ERROR: Failed to install MQTT service" in captured.out

    @patch("worktracker.cli.create_default_config")
    def test_mqtt_install_enable_fails(self, mock_create_config, cli, capsys):
        """Test mqtt_install fails when enabling fails."""
        mock_create_config.return_value = Path(
            "/home/user/.config/worktracker/mqtt.yaml"
        )
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=False)
        cli.service_manager.install_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.reload_daemon = MagicMock(return_value=True)
        cli.service_manager.enable_mqtt_service = MagicMock(return_value=False)

        result = cli.mqtt_install()

        assert result == 1
        captured = capsys.readouterr()
        assert "ERROR: Failed to enable MQTT service" in captured.out

    @patch("worktracker.cli.create_default_config")
    def test_mqtt_install_start_fails(self, mock_create_config, cli, capsys):
        """Test mqtt_install fails when starting fails."""
        mock_create_config.return_value = Path(
            "/home/user/.config/worktracker/mqtt.yaml"
        )
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=False)
        cli.service_manager.install_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.reload_daemon = MagicMock(return_value=True)
        cli.service_manager.enable_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.start_mqtt_service = MagicMock(return_value=False)

        result = cli.mqtt_install()

        assert result == 1
        captured = capsys.readouterr()
        assert "ERROR: Failed to start MQTT service" in captured.out

    # MQTT Start Tests
    @patch("worktracker.cli.load_config")
    @patch("worktracker.cli.MQTTClient")
    def test_mqtt_start_foreground(self, mock_mqtt_client, mock_load_config, cli):
        """Test mqtt_start runs in foreground mode."""
        mock_config = MagicMock()
        mock_load_config.return_value = mock_config
        mock_client = MagicMock()
        mock_client.is_running.side_effect = [True, False]  # Run once then stop
        mock_mqtt_client.return_value = mock_client
        mock_client.start.return_value = True

        result = cli.mqtt_start(as_service=False)

        assert result == 0
        mock_client.start.assert_called_once()
        mock_mqtt_client.assert_called_once()

    @patch("worktracker.cli.create_default_config")
    def test_mqtt_start_service_mode(self, mock_create_config, cli):
        """Test mqtt_start with as_service=True."""
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=False)
        cli.service_manager.install_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.reload_daemon = MagicMock(return_value=True)
        cli.service_manager.enable_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.start_mqtt_service = MagicMock(return_value=True)

        result = cli.mqtt_start(as_service=True)

        assert result == 0
        cli.service_manager.install_mqtt_service.assert_called_once()
        cli.service_manager.start_mqtt_service.assert_called_once()

    # MQTT Stop Tests
    def test_mqtt_stop_success(self, cli, capsys):
        """Test mqtt_stop succeeds."""
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=True)
        cli.service_manager.stop_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.disable_mqtt_service = MagicMock(return_value=True)

        result = cli.mqtt_stop()

        assert result == 0
        cli.service_manager.stop_mqtt_service.assert_called_once()
        cli.service_manager.disable_mqtt_service.assert_called_once()
        captured = capsys.readouterr()
        assert "MQTT publisher service has been stopped" in captured.out

    def test_mqtt_stop_not_installed(self, cli, capsys):
        """Test mqtt_stop fails when service not installed."""
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=False)

        result = cli.mqtt_stop()

        assert result == 1
        captured = capsys.readouterr()
        assert "ERROR: MQTT service is not installed" in captured.out

    def test_mqtt_stop_fails(self, cli, capsys):
        """Test mqtt_stop fails when stop fails."""
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=True)
        cli.service_manager.stop_mqtt_service = MagicMock(return_value=False)

        result = cli.mqtt_stop()

        assert result == 1
        captured = capsys.readouterr()
        assert "ERROR: Failed to stop MQTT service" in captured.out

    # MQTT Uninstall Tests
    def test_mqtt_uninstall_success(self, cli, capsys):
        """Test mqtt_uninstall succeeds."""
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=True)
        cli.service_manager.is_mqtt_service_running = MagicMock(return_value=True)
        cli.service_manager.stop_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.is_mqtt_service_enabled = MagicMock(return_value=True)
        cli.service_manager.disable_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.uninstall_mqtt_service = MagicMock(return_value=True)
        cli.service_manager.reload_daemon = MagicMock(return_value=True)

        result = cli.mqtt_uninstall()

        assert result == 0
        cli.service_manager.stop_mqtt_service.assert_called_once()
        cli.service_manager.disable_mqtt_service.assert_called_once()
        cli.service_manager.uninstall_mqtt_service.assert_called_once()
        cli.service_manager.reload_daemon.assert_called_once()
        captured = capsys.readouterr()
        assert (
            "MQTT publisher service has been uninstalled successfully" in captured.out
        )

    def test_mqtt_uninstall_not_installed(self, cli, capsys):
        """Test mqtt_uninstall when service not installed."""
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=False)

        result = cli.mqtt_uninstall()

        assert result == 0
        captured = capsys.readouterr()
        assert "Nothing to uninstall" in captured.out

    def test_mqtt_uninstall_uninstall_fails(self, cli, capsys):
        """Test mqtt_uninstall fails when uninstall fails."""
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=True)
        cli.service_manager.is_mqtt_service_running = MagicMock(return_value=False)
        cli.service_manager.is_mqtt_service_enabled = MagicMock(return_value=False)
        cli.service_manager.uninstall_mqtt_service = MagicMock(return_value=False)

        result = cli.mqtt_uninstall()

        assert result == 1
        captured = capsys.readouterr()
        assert "ERROR: Failed to uninstall MQTT service" in captured.out

    # MQTT Status Tests
    @patch("worktracker.cli.load_config")
    def test_mqtt_status_service_running(self, mock_load_config, cli, capsys):
        """Test mqtt_status shows service running."""
        mock_config = MagicMock()
        mock_config.broker_ip = "192.168.1.100"
        mock_config.port = 1883
        mock_config.topic_prefix = "worktracker"
        mock_config.update_interval = 60
        mock_config.qos = 1
        mock_load_config.return_value = mock_config
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=True)
        cli.service_manager.is_mqtt_service_running = MagicMock(return_value=True)
        cli.service_manager.is_mqtt_service_enabled = MagicMock(return_value=True)

        result = cli.mqtt_status()

        assert result == 0
        captured = capsys.readouterr()
        assert "MQTT Configuration:" in captured.out
        assert "192.168.1.100:1883" in captured.out
        assert "MQTT Service Status:" in captured.out
        assert "Installed: Yes" in captured.out
        assert "Running: Yes" in captured.out
        assert "Enabled: Yes" in captured.out

    @patch("worktracker.cli.load_config")
    def test_mqtt_status_service_not_installed(self, mock_load_config, cli, capsys):
        """Test mqtt_status shows service not installed."""
        mock_config = MagicMock()
        mock_config.broker_ip = "192.168.1.100"
        mock_config.port = 1883
        mock_config.topic_prefix = "worktracker"
        mock_config.update_interval = 60
        mock_config.qos = 1
        mock_load_config.return_value = mock_config
        cli.service_manager.is_mqtt_service_installed = MagicMock(return_value=False)

        result = cli.mqtt_status()

        assert result == 0
        captured = capsys.readouterr()
        assert "Installed: No" in captured.out
        assert "Running: No" in captured.out
        assert "Enabled: No" in captured.out

    @patch("worktracker.cli.load_config")
    def test_mqtt_status_config_error(self, mock_load_config, cli, capsys):
        """Test mqtt_status fails on config error."""
        mock_load_config.side_effect = FileNotFoundError("Config not found")

        result = cli.mqtt_status()

        assert result == 1
        captured = capsys.readouterr()
        assert "ERROR" in captured.out
