"""Binary sensor exposing an active heating or cooling failure."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_VTHERM_UNIQUE_ID, DOMAIN, SIGNAL_MANAGER_UPDATED


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    """Create one sensor for a thermostat-specific configuration entry."""
    config = entry.options or entry.data
    unique_id = config.get(CONF_VTHERM_UNIQUE_ID)
    if unique_id:
        async_add_entities([HeatingFailureBinarySensor(hass, unique_id)])


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