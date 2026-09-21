"""Config flow for the heating failure detection plugin."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import *


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
    defaults = {CONF_ENABLED: DEFAULT_ENABLED, CONF_HEATING_PERCENT_THRESHOLD: DEFAULT_HEATING_PERCENT_THRESHOLD, CONF_COOLING_PERCENT_THRESHOLD: DEFAULT_COOLING_PERCENT_THRESHOLD, CONF_TEMPERATURE_DELTA: DEFAULT_TEMPERATURE_DELTA, CONF_DELAY_MINUTES: DEFAULT_DELAY_MINUTES}
    if data:
        defaults.update(data)
    return defaults


class HeatingFailureConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure global defaults and per-thermostat overrides."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if not self._async_current_entries():
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Heating failure defaults", data=_defaults())
        return await self.async_step_thermostat(user_input)

    async def async_step_thermostat(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            entity_id = user_input.pop("target_entity")
            registry_entry = er.async_get(self.hass).async_get(entity_id)
            if registry_entry is None:
                return self.async_show_form(step_id="thermostat", data_schema=self._target_schema(), errors={"target_entity": "invalid_entity"})
            target = registry_entry.unique_id
            await self.async_set_unique_id(f"{DOMAIN}-{target}")
            self._abort_if_unique_id_configured()
            user_input[CONF_VTHERM_UNIQUE_ID] = target
            state = self.hass.states.get(entity_id)
            return self.async_create_entry(title=state.name if state else entity_id, data=user_input)
        return self.async_show_form(step_id="thermostat", data_schema=self._target_schema())

    def _target_schema(self) -> vol.Schema:
        schema = {vol.Required("target_entity"): selector.EntitySelector(selector.EntitySelectorConfig(domain=CLIMATE_DOMAIN))}
        schema.update(_options_schema(_defaults()).schema)
        return vol.Schema(schema)

    @staticmethod
    def async_get_options_flow(config_entry):
        return HeatingFailureOptionsFlow(config_entry)


class HeatingFailureOptionsFlow(OptionsFlow):
    """Edit an existing plugin entry."""

    def __init__(self, config_entry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=_options_schema(_defaults(self._config_entry.options or self._config_entry.data)))