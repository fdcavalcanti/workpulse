"""Home Assistant integration utilities for worktracker."""

import socket
from typing import Optional


def generate_yaml_config(hostname: Optional[str] = None) -> str:
    """Generate Home Assistant YAML configuration for WorkTracker.

    Generates complete YAML configuration with hostname automatically filled in.
    The output can be copied and pasted directly into Home Assistant's configuration.yaml.

    Args:
        hostname: Hostname to use in the configuration. If None, automatically detects.

    Returns:
        Complete YAML configuration string ready for Home Assistant
    """
    if hostname is None:
        hostname = socket.gethostname()

    # Escape braces for Home Assistant template syntax
    # In f-strings: {{ becomes {, so {{{{ becomes {{
    yaml_config = f"""mqtt:
  sensor:
    # Daily Total Active Time (formatted as hours:minutes)
    - name: "WorkTracker Daily Time"
      unique_id: "worktracker_{hostname}_daily_time"
      state_topic: "worktracker/{hostname}/status"
      value_template: >
        {{% set total_seconds = value_json.total_time | int %}}
        {{% set hours = (total_seconds / 3600) | int %}}
        {{% set minutes = ((total_seconds % 3600) / 60) | int %}}
        {{% if hours > 0 %}}{{{{ hours }}}}h {{% if minutes > 0 %}}{{{{ minutes }}}}m{{% endif %}}{{% else %}}{{{{ minutes }}}}m{{% endif %}}
      icon: "mdi:clock-outline"
      device:
        identifiers:
          - "worktracker_{hostname}"
        name: "WorkTracker - {hostname}"
        manufacturer: "WorkTracker"
        model: "WorkTracker"
"""

    return yaml_config
