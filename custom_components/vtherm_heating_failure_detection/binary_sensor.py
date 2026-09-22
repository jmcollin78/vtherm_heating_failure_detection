"""Binary sensor exposing an active heating or cooling failure."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import entity_registry as er

from .const import CONF_VTHERM_UNIQUE_ID, DOMAIN, SIGNAL_MANAGER_UPDATED

VT_DOMAIN = "versatile_thermostat"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Create sensors for targeted entries or every VTherm using global defaults."""
    config = entry.options or entry.data
    target = config.get(CONF_VTHERM_UNIQUE_ID)
    if target:
        unique_ids = [target]
    else:
        targeted_ids = {
            (plugin_entry.options or plugin_entry.data).get(CONF_VTHERM_UNIQUE_ID)
            for plugin_entry in hass.config_entries.async_entries(DOMAIN)
        }
        unique_ids = [
            thermostat_entry.unique_id
            for thermostat_entry in hass.config_entries.async_entries(VT_DOMAIN)
            if thermostat_entry.unique_id
            and thermostat_entry.unique_id not in targeted_ids
        ]

    registry = er.async_get(hass)
    entities = []
    for unique_id in unique_ids:
        sensor_unique_id = f"{unique_id}_heating_failure_state"
        if registry.async_get_entity_id(BINARY_SENSOR_DOMAIN, DOMAIN, sensor_unique_id):
            continue
        entities.append(HeatingFailureBinarySensor(hass, unique_id))
    if entities:
        async_add_entities(entities)


class HeatingFailureBinarySensor(BinarySensorEntity):
    """Expose the aggregate state of a plugin heating-failure manager."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:radiator-off"

    def __init__(self, hass: HomeAssistant, thermostat_unique_id: str) -> None:
        self._hass = hass
        self._thermostat_unique_id = thermostat_unique_id
        self._attr_unique_id = f"{thermostat_unique_id}_heating_failure_state"
        self._attr_name = "Heating failure"

    @property
    def is_on(self) -> bool:
        manager = self._hass.data.get(DOMAIN, {}).get("managers", {}).get(self._thermostat_unique_id)
        return bool(manager and manager.is_failure_detected)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self._hass, SIGNAL_MANAGER_UPDATED, self._manager_updated))

    @callback
    def _manager_updated(self, thermostat_unique_id: str) -> None:
        if thermostat_unique_id == self._thermostat_unique_id:
            self.async_write_ha_state()