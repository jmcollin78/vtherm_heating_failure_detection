"""Config flow for the heating failure detection plugin."""

from __future__ import annotations

from typing import Any, Self

import voluptuous as vol
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    CONF_ACTIVATION_TEMPLATE,
    CONF_COOLING_PERCENT_THRESHOLD,
    CONF_DELAY_MINUTES,
    CONF_ENABLED,
    CONF_HEATING_PERCENT_THRESHOLD,
    CONF_TEMPERATURE_DELTA,
    CONF_VTHERM_UNIQUE_ID,
    DOMAIN,
)
from .models import CONFIG_KEYS, default_config, legacy_config

VT_DOMAIN = "versatile_thermostat"
LEGACY_THERMOSTAT_TYPE = "thermostat_type"
LEGACY_CENTRAL_TYPE = "thermostat_central_config"
LEGACY_USE_CENTRAL = "use_heating_failure_detection_central_config"


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Optional(CONF_ENABLED, default=defaults[CONF_ENABLED]): selector.BooleanSelector(),
        vol.Optional(CONF_HEATING_PERCENT_THRESHOLD, default=defaults[CONF_HEATING_PERCENT_THRESHOLD]): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=1, step=0.01, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_COOLING_PERCENT_THRESHOLD, default=defaults[CONF_COOLING_PERCENT_THRESHOLD]): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=1, step=0.01, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_TEMPERATURE_DELTA, default=defaults[CONF_TEMPERATURE_DELTA]): selector.NumberSelector(selector.NumberSelectorConfig(min=0, max=5, step=0.01, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_DELAY_MINUTES, default=defaults[CONF_DELAY_MINUTES]): selector.NumberSelector(selector.NumberSelectorConfig(min=1, max=1440, step=1, mode=selector.NumberSelectorMode.BOX)),
        vol.Optional(CONF_ACTIVATION_TEMPLATE, default=defaults.get(CONF_ACTIVATION_TEMPLATE, "")): selector.TemplateSelector(),
    })


def _defaults(data: dict[str, Any] | None = None) -> dict[str, Any]:
    defaults = default_config()
    if data:
        defaults.update(data)
    return defaults


def _global_defaults(hass) -> dict[str, Any]:
    """Return global plugin values, with historical defaults for the form."""
    defaults = _defaults()
    for entry in hass.config_entries.async_entries(DOMAIN):
        config = entry.options or entry.data
        if not config.get(CONF_VTHERM_UNIQUE_ID):
            defaults.update({key: value for key, value in config.items() if key in CONFIG_KEYS})
    return defaults


def _target_overrides(user_input: dict[str, Any], global_defaults: dict[str, Any]) -> dict[str, Any]:
    """Keep only values explicitly different from the global plugin settings."""
    overrides: dict[str, Any] = {}
    for key in CONFIG_KEYS:
        value = user_input.get(key)
        default = global_defaults.get(key, "" if key == CONF_ACTIVATION_TEMPLATE else None)
        if value != default:
            overrides[key] = value
    return overrides


def _legacy_central_values(hass) -> dict[str, Any]:
    """Return configured heating-failure values from the legacy central entry."""
    for entry in hass.config_entries.async_entries(VT_DOMAIN):
        data = entry.options or entry.data
        if data.get(LEGACY_THERMOSTAT_TYPE) == LEGACY_CENTRAL_TYPE:
            return legacy_config(data)
    return {}


def _legacy_target_values(hass, entity_id: str) -> dict[str, Any]:
    """Resolve the legacy values selected by a VTherm configuration entry."""
    registry_entry = er.async_get(hass).async_get(entity_id)
    if registry_entry is None or registry_entry.config_entry_id is None:
        return {}

    core_entry = hass.config_entries.async_get_entry(registry_entry.config_entry_id)
    if core_entry is None or core_entry.domain != VT_DOMAIN:
        return {}

    data = core_entry.options or core_entry.data
    values = _legacy_central_values(hass) if data.get(LEGACY_USE_CENTRAL) else {}
    values.update(legacy_config(data))
    return values


class HeatingFailureConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure global defaults and per-thermostat overrides."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the selected VTherm kept between migration steps."""
        super().__init__()
        self._target_entity_id = ""
        self._target_unique_id = ""

    def is_matching(self, other_flow: Self) -> bool:
        """Return whether another flow targets the same configuration entry."""
        return other_flow.unique_id == self.unique_id

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if not self._async_current_entries():
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return await self.async_step_global(user_input)
        return await self.async_step_thermostat(user_input)

    async def async_step_global(self, user_input: dict[str, Any] | None = None):
        """Create global settings, prefilled from legacy central settings."""
        if user_input is not None:
            return self.async_create_entry(title="Heating failure defaults", data=user_input)
        defaults = _defaults(_legacy_central_values(self.hass))
        return self.async_show_form(
            step_id="global", data_schema=_options_schema(defaults)
        )

    async def async_step_thermostat(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            entity_id = user_input["target_entity"]
            registry_entry = er.async_get(self.hass).async_get(entity_id)
            if registry_entry is None:
                return self.async_show_form(step_id="thermostat", data_schema=self._target_schema(), errors={"target_entity": "invalid_entity"})
            self._target_entity_id = entity_id
            self._target_unique_id = registry_entry.unique_id
            await self.async_set_unique_id(f"{DOMAIN}-{self._target_unique_id}")
            self._abort_if_unique_id_configured()
            return await self.async_step_thermostat_options()
        return self.async_show_form(step_id="thermostat", data_schema=self._target_schema())

    async def async_step_thermostat_options(
        self, user_input: dict[str, Any] | None = None
    ):
        """Confirm the plugin overrides prefilled from the selected legacy VTherm."""
        if user_input is not None:
            user_input = _target_overrides(user_input, _global_defaults(self.hass))
            user_input[CONF_VTHERM_UNIQUE_ID] = self._target_unique_id
            state = self.hass.states.get(self._target_entity_id)
            return self.async_create_entry(
                title=state.name if state else self._target_entity_id,
                data=user_input,
            )

        defaults = _global_defaults(self.hass)
        defaults.update(_legacy_target_values(self.hass, self._target_entity_id))
        return self.async_show_form(
            step_id="thermostat_options", data_schema=_options_schema(defaults)
        )

    def _target_schema(self) -> vol.Schema:
        return vol.Schema({
            vol.Required("target_entity"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=CLIMATE_DOMAIN)
            )
        })

    @staticmethod
    def async_get_options_flow(config_entry):
        return HeatingFailureOptionsFlow(config_entry)


class HeatingFailureOptionsFlow(OptionsFlow):
    """Edit an existing plugin entry."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            current = self._config_entry.options or self._config_entry.data
            if current.get(CONF_VTHERM_UNIQUE_ID):
                user_input = _target_overrides(user_input, _global_defaults(self.hass))
            return self.async_create_entry(title="", data=user_input)
        current = self._config_entry.options or self._config_entry.data
        defaults = _global_defaults(self.hass)
        defaults.update({key: value for key, value in current.items() if key in CONFIG_KEYS})
        return self.async_show_form(step_id="init", data_schema=_options_schema(defaults))