"""Tests for mqtt_client module."""

import json
import socket
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from workpulse.database import Database
from workpulse.mqtt_client import MQTTClient
from workpulse.mqtt_config import MQTTConfig
from workpulse.tracker import WorkTracker


class TestMQTTClient:
    """Test suite for MQTTClient class."""

    @pytest.fixture
    def mqtt_config(self):
        """Create a test MQTTConfig."""
        return MQTTConfig(broker_ip="localhost", port=1883)

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)
        db = Database(db_path=db_path)
        db.connect()
        yield db
        db.close()
        db_path.unlink(missing_ok=True)

    @pytest.fixture
    def tracker(self, temp_db):
        """Create a WorkTracker instance with temporary database."""
        return WorkTracker(database=temp_db)

    @pytest.fixture
    def mqtt_client(self, mqtt_config, tracker):
        """Create an MQTTClient instance."""
        return MQTTClient(mqtt_config, tracker)

    @patch("workpulse.mqtt_client.socket.gethostname")
    def test_init(self, mock_gethostname, mqtt_config):
        """Test MQTTClient initialization."""
        mock_gethostname.return_value = "testhost"
        client = MQTTClient(mqtt_config)

        assert client.config == mqtt_config
        assert client.tracker is not None
        assert client.client is None
        assert client._running is False
        assert client._hostname == "testhost"

    def test_init_with_tracker(self, mqtt_config, tracker):
        """Test MQTTClient initialization with custom tracker."""
        client = MQTTClient(mqtt_config, tracker)

        assert client.tracker == tracker

    def test_get_hostname(self, mqtt_client):
        """Test _get_hostname method."""
        hostname = mqtt_client._get_hostname()
        assert isinstance(hostname, str)
        assert len(hostname) > 0

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_connect_success(self, mock_client_class, mqtt_client):
        """Test successful connection to MQTT broker."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client_class.return_value = mock_client

        result = mqtt_client.connect()

        assert result is True
        mock_client.connect.assert_called_once()
        mock_client.loop_start.assert_called_once()

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_connect_already_connected(self, mock_client_class, mqtt_client):
        """Test connect when already connected."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client_class.return_value = mock_client

        # First connection
        mqtt_client.connect()
        # Second connection should return immediately
        result = mqtt_client.connect()

        assert result is True
        # connect should only be called once
        assert mock_client.connect.call_count == 1

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_connect_with_credentials(self, mock_client_class, mqtt_config):
        """Test connection with username/password."""
        mqtt_config.username = "user"
        mqtt_config.password = "pass"
        client = MQTTClient(mqtt_config)

        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client_class.return_value = mock_client

        client.connect()

        mock_client.username_pw_set.assert_called_once_with("user", "pass")

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_connect_failure(self, mock_client_class, mqtt_client):
        """Test connection failure handling."""
        mock_client = MagicMock()
        mock_client.connect.side_effect = Exception("Connection failed")
        mock_client_class.return_value = mock_client

        result = mqtt_client.connect()

        assert result is False

    def test_on_connect_success(self, mqtt_client):
        """Test _on_connect callback with success."""
        mock_client = MagicMock()
        mqtt_client._on_connect(mock_client, None, {}, 0)

        # Should not raise any exceptions

    def test_on_connect_failure(self, mqtt_client):
        """Test _on_connect callback with failure."""
        mock_client = MagicMock()
        mqtt_client._on_connect(mock_client, None, {}, 1)

        # Should not raise any exceptions

    def test_on_disconnect_normal(self, mqtt_client):
        """Test _on_disconnect callback with normal disconnect."""
        mock_client = MagicMock()
        mqtt_client._on_disconnect(mock_client, None, 0)

        # Should not raise any exceptions

    def test_on_disconnect_unexpected(self, mqtt_client):
        """Test _on_disconnect callback with unexpected disconnect."""
        mock_client = MagicMock()
        mqtt_client._on_disconnect(mock_client, None, 1)

        # Should not raise any exceptions

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_disconnect(self, mock_client_class, mqtt_client):
        """Test disconnecting from MQTT broker."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client_class.return_value = mock_client
        mqtt_client.connect()

        mqtt_client.disconnect()

        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()
        assert mqtt_client.client is None

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_disconnect_not_connected(self, mock_client_class, mqtt_client):
        """Test disconnect when not connected."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = False
        mock_client_class.return_value = mock_client
        mqtt_client.client = mock_client

        mqtt_client.disconnect()

        mock_client.loop_stop.assert_not_called()
        assert mqtt_client.client is None

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_publish_status_success(self, mock_client_class, mqtt_client, temp_db):
        """Test successful status publication."""
        # Add some time to the database
        temp_db.increment_daily_time(3600.0)  # 1 hour

        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_publish_result = MagicMock()
        mock_publish_result.rc = 0  # MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_publish_result
        mock_client_class.return_value = mock_client
        mqtt_client.client = mock_client

        result = mqtt_client.publish_status()

        assert result is True
        mock_client.publish.assert_called_once()
        # Verify topic and payload
        call_args = mock_client.publish.call_args
        topic = call_args[0][0]
        payload = call_args[0][1]
        assert "workpulse" in topic
        assert "status" in topic

        # Verify payload structure
        message = json.loads(payload)
        assert "total_time" in message
        assert "date" in message
        assert "timestamp" in message
        assert message["total_time"] == 3600.0

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_publish_status_not_connected(self, mock_client_class, mqtt_client):
        """Test publish_status when not connected."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = False
        mock_client_class.return_value = mock_client
        mqtt_client.client = mock_client

        # Mock connect to return False
        with patch.object(mqtt_client, "connect", return_value=False):
            result = mqtt_client.publish_status()

        assert result is False

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_publish_status_publish_failure(self, mock_client_class, mqtt_client):
        """Test publish_status when publish fails."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_publish_result = MagicMock()
        mock_publish_result.rc = 1  # MQTT error
        mock_client.publish.return_value = mock_publish_result
        mock_client_class.return_value = mock_client
        mqtt_client.client = mock_client

        result = mqtt_client.publish_status()

        assert result is False

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_publish_status_with_last_update(
        self, mock_client_class, mqtt_client, temp_db
    ):
        """Test publish_status includes last_update when available."""
        # Add time to create a last_update timestamp
        temp_db.increment_daily_time(60.0)

        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_publish_result = MagicMock()
        mock_publish_result.rc = 0
        mock_client.publish.return_value = mock_publish_result
        mock_client_class.return_value = mock_client
        mqtt_client.client = mock_client

        result = mqtt_client.publish_status()

        assert result is True
        call_args = mock_client.publish.call_args
        payload = json.loads(call_args[0][1])
        assert "last_update" in payload
        # last_update should be a string (ISO format) or None
        assert payload["last_update"] is None or isinstance(payload["last_update"], str)

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_publish_status_exception(self, mock_client_class, mqtt_client):
        """Test publish_status exception handling."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client.publish.side_effect = Exception("Publish error")
        mock_client_class.return_value = mock_client
        mqtt_client.client = mock_client

        result = mqtt_client.publish_status()

        assert result is False

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_start_success(self, mock_client_class, mqtt_client):
        """Test starting the MQTT publisher daemon."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client_class.return_value = mock_client

        result = mqtt_client.start()

        assert result is True
        assert mqtt_client._running is True
        assert mqtt_client._thread is not None
        assert mqtt_client._thread.is_alive()

        # Cleanup
        mqtt_client.stop()

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_start_already_running(self, mock_client_class, mqtt_client):
        """Test starting when already running."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client_class.return_value = mock_client

        mqtt_client._running = True

        result = mqtt_client.start()

        assert result is True

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_start_connection_failure(self, mock_client_class, mqtt_client):
        """Test start when connection fails."""
        mock_client = MagicMock()
        mock_client.connect.side_effect = Exception("Connection failed")
        mock_client_class.return_value = mock_client

        with patch.object(mqtt_client, "connect", return_value=False):
            result = mqtt_client.start()

        assert result is False
        assert mqtt_client._running is False

    @patch("workpulse.mqtt_client.mqtt.Client")
    def test_stop(self, mock_client_class, mqtt_client):
        """Test stopping the MQTT publisher daemon."""
        mock_client = MagicMock()
        mock_client.is_connected.return_value = True
        mock_client_class.return_value = mock_client

        mqtt_client._running = True
        mqtt_client._thread = Mock()
        mqtt_client._thread.join = Mock()
        mqtt_client.client = mock_client

        mqtt_client.stop()

        assert mqtt_client._running is False
        assert mqtt_client._thread is None
        mock_client.loop_stop.assert_called_once()
        mock_client.disconnect.assert_called_once()

    def test_stop_not_running(self, mqtt_client):
        """Test stop when not running."""
        mqtt_client._running = False

        # Should not raise any exceptions
        mqtt_client.stop()

    def test_is_running(self, mqtt_client):
        """Test is_running method."""
        assert mqtt_client.is_running() is False

        mqtt_client._running = True
        assert mqtt_client.is_running() is True

        mqtt_client._running = False
        assert mqtt_client.is_running() is False
