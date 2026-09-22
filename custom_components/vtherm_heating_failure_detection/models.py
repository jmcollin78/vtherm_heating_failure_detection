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

# Kept as literals so that the plugin never imports private core constants.
LEGACY_ENABLED = "use_heating_failure_detection_feature"
LEGACY_CONFIG_KEYS = {
    CONF_HEATING_PERCENT_THRESHOLD: "heating_failure_threshold",
    CONF_COOLING_PERCENT_THRESHOLD: "cooling_failure_threshold",
    CONF_DELAY_MINUTES: "heating_failure_detection_delay",
    CONF_TEMPERATURE_DELTA: "temperature_change_tolerance",
    CONF_ACTIVATION_TEMPLATE: "failure_detection_enable_template",
}
CONFIG_KEYS = (
    CONF_ENABLED,
    CONF_HEATING_PERCENT_THRESHOLD,
    CONF_COOLING_PERCENT_THRESHOLD,
    CONF_TEMPERATURE_DELTA,
    CONF_DELAY_MINUTES,
    CONF_ACTIVATION_TEMPLATE,
)


def default_config() -> dict[str, Any]:
    """Return the historical defaults for a configured detector."""
    return {
        CONF_ENABLED: DEFAULT_ENABLED,
        CONF_HEATING_PERCENT_THRESHOLD: DEFAULT_HEATING_PERCENT_THRESHOLD,
        CONF_COOLING_PERCENT_THRESHOLD: DEFAULT_COOLING_PERCENT_THRESHOLD,
        CONF_TEMPERATURE_DELTA: DEFAULT_TEMPERATURE_DELTA,
        CONF_DELAY_MINUTES: DEFAULT_DELAY_MINUTES,
    }


def _plugin_configs(
    entries: dict[str, dict[str, Any]], vtherm_unique_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the global and targeted plugin values, excluding entry metadata."""
    global_config: dict[str, Any] = {}
    targeted_config: dict[str, Any] = {}
    for entry in entries.values():
        values = {key: value for key, value in entry.items() if key in CONFIG_KEYS}
        target = entry.get(CONF_VTHERM_UNIQUE_ID)
        if target == vtherm_unique_id:
            targeted_config.update(values)
        elif not target:
            global_config.update(values)
    return global_config, targeted_config


def legacy_config(entry_infos: dict[str, Any]) -> dict[str, Any]:
    """Map the public, persisted legacy core values to plugin names."""
    if not entry_infos.get(LEGACY_ENABLED, False):
        return {}

    config = {CONF_ENABLED: True}
    for plugin_key, legacy_key in LEGACY_CONFIG_KEYS.items():
        if legacy_key in entry_infos:
            config[plugin_key] = entry_infos[legacy_key]
    return config


def effective_config(
    entries: dict[str, dict[str, Any]],
    vtherm_unique_id: str,
    legacy_entry_infos: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Resolve plugin overrides first, then persisted legacy core values."""
    global_config, targeted_config = _plugin_configs(entries, vtherm_unique_id)
    resolved_legacy_config = legacy_config(legacy_entry_infos or {})

    if not global_config and not targeted_config and not resolved_legacy_config:
        return None

    config = default_config()
    config.update(resolved_legacy_config)
    config.update(global_config)
    config.update(targeted_config)
    return config


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return config suitable for state attributes without the template object."""
    return {key: value for key, value in config.items() if key != CONF_ACTIVATION_TEMPLATE}