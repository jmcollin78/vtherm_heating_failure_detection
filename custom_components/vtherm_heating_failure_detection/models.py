"""Configuration helpers for heating failure detection."""

from __future__ import annotations

from typing import Any

from .const import (
    CONF_ACTIVATION_TEMPLATE,
    CONF_COOLING_PERCENT_THRESHOLD,
    CONF_DELAY_MINUTES,
    CONF_ENABLED,
    CONF_HEATING_PERCENT_THRESHOLD,
    CONF_TEMPERATURE_DELTA,
    CONF_VTHERM_UNIQUE_ID,
    DEFAULT_COOLING_PERCENT_THRESHOLD,
    DEFAULT_DELAY_MINUTES,
    DEFAULT_ENABLED,
    DEFAULT_HEATING_PERCENT_THRESHOLD,
    DEFAULT_TEMPERATURE_DELTA,
)


def effective_config(entries: dict[str, dict[str, Any]], vtherm_unique_id: str) -> dict[str, Any] | None:
    """Merge the global entry and the optional entry for a thermostat."""
    global_config: dict[str, Any] = {}
    targeted_config: dict[str, Any] | None = None
    for config in entries.values():
        target = config.get(CONF_VTHERM_UNIQUE_ID)
        if target == vtherm_unique_id:
            targeted_config = config
        elif not target:
            global_config.update(config)

    if not global_config and targeted_config is None:
        return None

    config = {
        CONF_ENABLED: DEFAULT_ENABLED,
        CONF_HEATING_PERCENT_THRESHOLD: DEFAULT_HEATING_PERCENT_THRESHOLD,
        CONF_COOLING_PERCENT_THRESHOLD: DEFAULT_COOLING_PERCENT_THRESHOLD,
        CONF_TEMPERATURE_DELTA: DEFAULT_TEMPERATURE_DELTA,
        CONF_DELAY_MINUTES: DEFAULT_DELAY_MINUTES,
        **global_config,
    }
    if targeted_config:
        config.update(targeted_config)
    return config


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return config suitable for state attributes without the template object."""
    return {key: value for key, value in config.items() if key != CONF_ACTIVATION_TEMPLATE}