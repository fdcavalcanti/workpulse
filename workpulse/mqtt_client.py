"""MQTT client for publishing work tracking updates."""

import json
import logging
import socket
import threading
import time
from datetime import datetime
from typing import Optional

import paho.mqtt.client as mqtt

from .mqtt_config import MQTTConfig
from .tracker import WorkTracker

logger = logging.getLogger(__name__)


class MQTTClient:
    """MQTT client for publishing work tracking status updates."""

    def __init__(
        self, config: MQTTConfig, tracker: Optional[WorkTracker] = None
    ) -> None:
        """Initialize the MQTT client.

        Args:
            config: MQTT configuration
            tracker: WorkTracker instance. If None, creates a new one.
        """
        self.config = config
        self.tracker = tracker or WorkTracker()
        self.client: Optional[mqtt.Client] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._hostname = socket.gethostname()

    def _get_hostname(self) -> str:
        """Get the hostname for topic construction.

        Returns:
            Hostname string
        """
        return self._hostname

    def connect(self) -> bool:
        """Connect to the MQTT broker with retry logic.

        Returns:
            True if connection succeeded, False otherwise
        """
        if self.client is not None and self.client.is_connected():
            logger.debug("Already connected to MQTT broker")
            return True

        try:
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect

            # Set credentials if provided
            if self.config.username and self.config.password:
                self.client.username_pw_set(self.config.username, self.config.password)

            logger.info(
                f"Connecting to MQTT broker at {self.config.broker_ip}:{self.config.port}"
            )
            self.client.connect(self.config.broker_ip, self.config.port, 60)
            self.client.loop_start()
            return True

        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def _on_connect(
        self, client: mqtt.Client, userdata: None, flags: dict, rc: int
    ) -> None:
        """Callback for when the client receives a CONNACK response from the server.

        Args:
            client: The client instance
            userdata: User data (unused)
            flags: Response flags
            rc: Connection result code
        """
        if rc == 0:
            logger.info("Connected to MQTT broker")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")

    def _on_disconnect(self, client: mqtt.Client, userdata: None, rc: int) -> None:
        """Callback for when the client disconnects from the server.

        Args:
            client: The client instance
            userdata: User data (unused)
            rc: Disconnect result code
        """
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection, return code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        if self.client is not None:
            if self.client.is_connected():
                self.client.loop_stop()
                self.client.disconnect()
                logger.info("Disconnected from MQTT broker")
            self.client = None

    def publish_status(self) -> bool:
        """Publish current work tracking status to MQTT broker.

        Gets the current status from WorkTracker and publishes a JSON message
        with fields: last_update, total_time, timestamp, date.

        Returns:
            True if publish succeeded, False otherwise
        """
        if self.client is None or not self.client.is_connected():
            logger.warning("Not connected to MQTT broker, attempting to connect")
            if not self.connect():
                return False

        try:
            # Get today's log from database
            today_log = self.tracker.database.get_today_log()

            # Prepare message payload
            timestamp = datetime.now()
            message = {
                "last_update": (
                    today_log.last_update.isoformat() if today_log.last_update else None
                ),
                "total_time": today_log.total_active_time,
                "timestamp": timestamp.isoformat(),
                "date": today_log.date.isoformat(),
            }

            # Convert to JSON
            payload = json.dumps(message)

            # Get topic
            topic = self.config.get_topic(self._get_hostname())

            # Publish
            result = self.client.publish(topic, payload, qos=self.config.qos)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(
                    f"Published status to {topic}: {today_log.total_active_time}s"
                )
                return True
            else:
                logger.error(
                    f"Failed to publish to MQTT broker, return code: {result.rc}"
                )
                return False

        except Exception as e:
            logger.error(f"Error publishing status: {e}", exc_info=True)
            return False

    def _run_loop(self) -> None:
        """Background loop that publishes status at configured intervals."""
        logger.info(
            f"Starting MQTT publisher loop (interval: {self.config.update_interval}s)"
        )

        while self._running:
            try:
                self.publish_status()
            except Exception as e:
                logger.error(f"Error in MQTT publish loop: {e}", exc_info=True)

            # Sleep for the configured interval
            for _ in range(self.config.update_interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("MQTT publisher loop stopped")

    def start(self) -> bool:
        """Start the MQTT publisher daemon.

        Connects to the broker and starts a background thread that publishes
        status updates at the configured interval.

        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            logger.warning("MQTT client is already running")
            return True

        if not self.connect():
            logger.error("Failed to connect to MQTT broker")
            return False

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("MQTT publisher daemon started")
        return True

    def stop(self) -> None:
        """Stop the MQTT publisher daemon."""
        if not self._running:
            return

        logger.info("Stopping MQTT publisher daemon")
        self._running = False

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

        self.disconnect()
        logger.info("MQTT publisher daemon stopped")

    def is_running(self) -> bool:
        """Check if the MQTT publisher is running.

        Returns:
            True if running, False otherwise
        """
        return self._running
