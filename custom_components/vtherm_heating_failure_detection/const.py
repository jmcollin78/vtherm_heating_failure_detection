"""Constants for the VTherm heating failure detection integration."""

from __future__ import annotations

DOMAIN = "vtherm_heating_failure_detection"
MANAGER_NAME = "heating_failure_detection"
MANAGER_ATTRIBUTES_KEY = "heating_failure_detection_manager"
SIGNAL_MANAGER_UPDATED = f"{DOMAIN}_manager_updated"

CONF_VTHERM_UNIQUE_ID = "vtherm_unique_id"
CONF_ENABLED = "enabled"
CONF_HEATING_PERCENT_THRESHOLD = "heating_percent_threshold"
CONF_COOLING_PERCENT_THRESHOLD = "cooling_percent_threshold"
CONF_TEMPERATURE_DELTA = "temperature_delta"
CONF_DELAY_MINUTES = "delay_minutes"
CONF_ACTIVATION_TEMPLATE = "activation_template"

DEFAULT_ENABLED = True
DEFAULT_HEATING_PERCENT_THRESHOLD = 0.9
DEFAULT_COOLING_PERCENT_THRESHOLD = 0.0
DEFAULT_TEMPERATURE_DELTA = 0.5
DEFAULT_DELAY_MINUTES = 15

EVENT_TYPE = "versatile_thermostat_heating_failure_event"
FAILURE_TYPE_HEATING = "heating"
FAILURE_TYPE_COOLING = "cooling"

PLATFORMS = ["binary_sensor"]