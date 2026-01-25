"""MQTT configuration management for workpulse."""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MQTTConfig:
    """MQTT broker configuration."""

    broker_ip: str
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    topic_prefix: str = "workpulse"
    update_interval: int = 60
    qos: int = 0

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        if not self.broker_ip:
            raise ValueError("broker_ip is required")
        if self.port < 1 or self.port > 65535:
            raise ValueError("port must be between 1 and 65535")
        if self.update_interval < 1:
            raise ValueError("update_interval must be at least 1 second")
        if self.qos not in (0, 1, 2):
            raise ValueError("qos must be 0, 1, or 2")

    def get_topic(self, hostname: str) -> str:
        """Get the full MQTT topic for a given hostname.

        Args:
            hostname: Hostname to include in the topic

        Returns:
            Full topic string: {topic_prefix}/{hostname}/status
        """
        return f"{self.topic_prefix}/{hostname}/status"


def create_default_config(config_path: Optional[Path] = None) -> Path:
    """Create a default MQTT configuration file template.

    Args:
        config_path: Path to configuration file. If None, uses default location
                     (~/.workpulse/mqtt_config.json)

    Returns:
        Path to the created configuration file

    Raises:
        OSError: If the file cannot be created
    """
    if config_path is None:
        home = Path.home()
        config_dir = home / ".workpulse"
        config_dir.mkdir(mode=0o700, exist_ok=True)
        config_path = config_dir / "mqtt_config.json"

    # Don't overwrite existing config
    if config_path.exists():
        return config_path

    # Create default config template
    default_config = {
        "broker_ip": "localhost",
        "port": 1883,
        "username": None,
        "password": None,
        "topic_prefix": "workpulse",
        "update_interval": 60,
        "qos": 0,
    }

    try:
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=2)
        config_path.chmod(0o600)  # Read/write for owner only
        logger.info(f"Created default MQTT configuration file: {config_path}")
        return config_path
    except OSError as e:
        raise OSError(f"Failed to create MQTT configuration file: {e}") from e


def load_config(config_path: Optional[Path] = None) -> MQTTConfig:
    """Load MQTT configuration from JSON file.

    Args:
        config_path: Path to configuration file. If None, uses default location
                     (~/.workpulse/mqtt_config.json)

    Returns:
        MQTTConfig object with loaded configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid or missing required fields
    """
    if config_path is None:
        home = Path.home()
        config_dir = home / ".workpulse"
        config_path = config_dir / "mqtt_config.json"

    if not config_path.exists():
        raise FileNotFoundError(
            f"MQTT configuration file not found: {config_path}\n"
            f"Please create the file with at least 'broker_ip' field."
        )

    try:
        with open(config_path, "r") as f:
            config_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file: {e}") from e

    if "broker_ip" not in config_data:
        raise ValueError("Configuration file must contain 'broker_ip' field")

    try:
        return MQTTConfig(**config_data)
    except TypeError as e:
        raise ValueError(f"Invalid configuration field: {e}") from e
