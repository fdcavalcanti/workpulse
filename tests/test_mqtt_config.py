"""Tests for mqtt_config module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from workpulse.mqtt_config import MQTTConfig, create_default_config, load_config


class TestMQTTConfig:
    """Test suite for MQTTConfig class."""

    def test_init_minimal(self):
        """Test MQTTConfig initialization with minimal required fields."""
        config = MQTTConfig(broker_ip="192.168.1.1")

        assert config.broker_ip == "192.168.1.1"
        assert config.port == 1883
        assert config.username is None
        assert config.password is None
        assert config.topic_prefix == "workpulse"
        assert config.update_interval == 60
        assert config.qos == 0

    def test_init_full(self):
        """Test MQTTConfig initialization with all fields."""
        config = MQTTConfig(
            broker_ip="192.168.1.1",
            port=8883,
            username="user",
            password="pass",
            topic_prefix="custom",
            update_interval=30,
            qos=1,
        )

        assert config.broker_ip == "192.168.1.1"
        assert config.port == 8883
        assert config.username == "user"
        assert config.password == "pass"
        assert config.topic_prefix == "custom"
        assert config.update_interval == 30
        assert config.qos == 1

    def test_init_empty_broker_ip(self):
        """Test that empty broker_ip raises ValueError."""
        with pytest.raises(ValueError, match="broker_ip is required"):
            MQTTConfig(broker_ip="")

    def test_init_invalid_port_low(self):
        """Test that port < 1 raises ValueError."""
        with pytest.raises(ValueError, match="port must be between"):
            MQTTConfig(broker_ip="192.168.1.1", port=0)

    def test_init_invalid_port_high(self):
        """Test that port > 65535 raises ValueError."""
        with pytest.raises(ValueError, match="port must be between"):
            MQTTConfig(broker_ip="192.168.1.1", port=65536)

    def test_init_invalid_update_interval(self):
        """Test that update_interval < 1 raises ValueError."""
        with pytest.raises(ValueError, match="update_interval must be at least"):
            MQTTConfig(broker_ip="192.168.1.1", update_interval=0)

    def test_init_invalid_qos(self):
        """Test that invalid qos raises ValueError."""
        with pytest.raises(ValueError, match="qos must be 0, 1, or 2"):
            MQTTConfig(broker_ip="192.168.1.1", qos=3)

    def test_get_topic_default_prefix(self):
        """Test get_topic with default topic prefix."""
        config = MQTTConfig(broker_ip="192.168.1.1")
        topic = config.get_topic("myhost")

        assert topic == "workpulse/myhost/status"

    def test_get_topic_custom_prefix(self):
        """Test get_topic with custom topic prefix."""
        config = MQTTConfig(broker_ip="192.168.1.1", topic_prefix="custom")
        topic = config.get_topic("myhost")

        assert topic == "custom/myhost/status"


class TestCreateDefaultConfig:
    """Test suite for create_default_config function."""

    def test_create_default_config_custom_path(self, tmp_path):
        """Test creating config file at custom path."""
        config_path = tmp_path / "test_config.json"
        result_path = create_default_config(config_path)

        assert result_path == config_path
        assert config_path.exists()

        # Verify file contents
        with open(config_path, "r") as f:
            config_data = json.load(f)

        assert config_data["broker_ip"] == "localhost"
        assert config_data["port"] == 1883
        assert config_data["username"] is None
        assert config_data["password"] is None
        assert config_data["topic_prefix"] == "workpulse"
        assert config_data["update_interval"] == 60
        assert config_data["qos"] == 0

    @patch("workpulse.mqtt_config.Path.home")
    def test_create_default_config_default_path(self, mock_home, tmp_path):
        """Test creating config file at default path."""
        mock_home.return_value = tmp_path
        expected_path = tmp_path / ".workpulse" / "mqtt_config.json"

        result_path = create_default_config()

        assert result_path == expected_path
        assert expected_path.exists()
        assert expected_path.parent.exists()

    def test_create_default_config_does_not_overwrite(self, tmp_path):
        """Test that create_default_config doesn't overwrite existing file."""
        config_path = tmp_path / "existing_config.json"
        config_path.write_text('{"broker_ip": "existing"}')

        result_path = create_default_config(config_path)

        assert result_path == config_path
        # Verify original content is preserved
        with open(config_path, "r") as f:
            content = f.read()
        assert "existing" in content
        assert "localhost" not in content

    def test_create_default_config_file_permissions(self, tmp_path):
        """Test that created config file has correct permissions."""
        config_path = tmp_path / "test_config.json"
        create_default_config(config_path)

        # Check that file is readable/writable by owner
        stat = config_path.stat()
        # Mode 0o600 = rw------- (owner read/write, no others)
        assert stat.st_mode & 0o777 == 0o600


class TestLoadConfig:
    """Test suite for load_config function."""

    def test_load_config_valid(self, tmp_path):
        """Test loading valid configuration file."""
        config_path = tmp_path / "config.json"
        config_data = {
            "broker_ip": "192.168.1.100",
            "port": 1883,
            "username": "user",
            "password": "pass",
            "topic_prefix": "custom",
            "update_interval": 30,
            "qos": 1,
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = load_config(config_path)

        assert config.broker_ip == "192.168.1.100"
        assert config.port == 1883
        assert config.username == "user"
        assert config.password == "pass"
        assert config.topic_prefix == "custom"
        assert config.update_interval == 30
        assert config.qos == 1

    def test_load_config_minimal(self, tmp_path):
        """Test loading minimal configuration file."""
        config_path = tmp_path / "config.json"
        config_data = {"broker_ip": "192.168.1.100"}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = load_config(config_path)

        assert config.broker_ip == "192.168.1.100"
        assert config.port == 1883  # Default value

    @patch("workpulse.mqtt_config.Path.home")
    def test_load_config_default_path(self, mock_home, tmp_path):
        """Test loading config from default path."""
        mock_home.return_value = tmp_path
        config_path = tmp_path / ".workpulse" / "mqtt_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)

        config_data = {"broker_ip": "192.168.1.100"}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = load_config()

        assert config.broker_ip == "192.168.1.100"

    def test_load_config_file_not_found(self, tmp_path):
        """Test that loading non-existent config raises FileNotFoundError."""
        config_path = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            load_config(config_path)

    def test_load_config_missing_broker_ip(self, tmp_path):
        """Test that config without broker_ip raises ValueError."""
        config_path = tmp_path / "config.json"
        config_data = {"port": 1883}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        with pytest.raises(ValueError, match="must contain 'broker_ip'"):
            load_config(config_path)

    def test_load_config_invalid_json(self, tmp_path):
        """Test that invalid JSON raises ValueError."""
        config_path = tmp_path / "config.json"
        config_path.write_text("invalid json content")

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_config(config_path)

    def test_load_config_invalid_field(self, tmp_path):
        """Test that config with invalid field raises ValueError."""
        config_path = tmp_path / "config.json"
        config_data = {"broker_ip": "192.168.1.1", "invalid_field": "value"}
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        # MQTTConfig will raise TypeError for unknown fields, which is caught and re-raised as ValueError
        with pytest.raises(ValueError, match="Invalid configuration field"):
            load_config(config_path)
