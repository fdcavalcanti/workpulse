"""Home Assistant integration utilities for workpulse."""

import socket
from typing import Optional


class YAMLGenerator:
    def __init__(self, hostname: Optional[str] = None):
        if not hostname:
            self.hostname = socket.gethostname()
        else:
            self.hostname = hostname
        self.name = "WorkPulse Daily Time"
        self.identifier = f"workpulse_{self.hostname}"

    def generate_template_yaml(self) -> str:
        """Generates YAML configuration for a template sensor that formats the daily time
        reported by the MQTT sensor into a human-readable format (hours and minutes).
        The output can be copied and pasted directly into Home Assistant's configuration.yaml.

        Returns:
            YAML configuration string for the template sensor
        """
        sensor = f"sensor.{self.identifier}_{self.name.lower().replace(' ', '_')}"
        yaml_template = f"""template:
  - sensor:
      - name: "WorkPulse Daily Time Formatted ({self.hostname})"
        icon: mdi:clock-outline
        state: >
            {{% set total_seconds = states('{sensor}') | int %}}
            {{% set hours = (total_seconds // 3600) %}}
            {{% set minutes = ((total_seconds % 3600) // 60) %}}
            {{% if hours > 0 %}}
              {{{{ hours }}}}h {{% if minutes > 0 %}}{{{{ minutes }}}}m{{% endif %}}
            {{% else %}}
              {{{{ minutes }}}}m
            {{% endif %}}
    """
        return yaml_template

    def generate_mqtt_yaml(self) -> str:
        """Generate Home Assistant YAML configuration for WorkPulse.

        Generates complete YAML configuration with hostname automatically filled in.
        The output can be copied and pasted directly into Home Assistant's configuration.yaml.

        Args:
            hostname: Hostname to use in the configuration. If None, automatically detects.

        Returns:
            Complete YAML configuration string ready for Home Assistant
        """

        # Escape braces for Home Assistant template syntax
        # In f-strings: {{ becomes {, so {{{{ becomes {{
        yaml_config = f"""mqtt:
  sensor:
    - name: "{self.name}"
      unit_of_measurement: "s"
      device_class: duration
      state_class: total_increasing
      unique_id: "workpulse_{self.hostname}_daily_time"
      state_topic: "workpulse/{self.hostname}/status"
      value_template: "{{{{ value_json.total_time | int }}}}"
      icon: "mdi:clock-outline"
      device:
          identifiers:
          - "{self.identifier}"
          name: "WorkPulse - {self.hostname}"
          manufacturer: "WorkPulse"
          model: "WorkPulse"
    """

        return yaml_config
