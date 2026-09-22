"""Binary sensor exposing an active heating or cooling failure."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_VTHERM_UNIQUE_ID, DOMAIN, SIGNAL_MANAGER_UPDATED

VT_DOMAIN = "versatile_thermostat"


def _async_vtherm_device_id(
    hass: HomeAssistant, thermostat_unique_id: str
) -> str | None:
    """Return the device registry ID of a VTherm from its stable unique ID."""
    registry = er.async_get(hass)
    climate_entity_id = registry.async_get_entity_id(
        CLIMATE_DOMAIN, VT_DOMAIN, thermostat_unique_id
    )
    if climate_entity_id is None:
        return None
    climate_entry = registry.async_get(climate_entity_id)
    return climate_entry.device_id if climate_entry is not None else None


def _async_vtherm_device_info(
    hass: HomeAssistant, thermostat_unique_id: str
) -> DeviceInfo | None:
    """Return DeviceInfo linking the plugin sensor to the VTherm device."""
    device_id = _async_vtherm_device_id(hass, thermostat_unique_id)
    device = dr.async_get(hass).async_get(device_id) if device_id else None
    return DeviceInfo(identifiers=device.identifiers) if device else None


def _async_take_legacy_entity_id(
    hass: HomeAssistant, thermostat_unique_id: str
) -> str | None:
    """Release an inactive legacy sensor ID so the plugin can retain it.

    Entity registry identity includes the integration platform, so Home Assistant
    cannot transfer a registry entry from the core domain to this plugin. When
    the legacy sensor has already been unloaded, remove only its stale registry
    entry and reuse its entity ID as the suggested ID of the plugin entity.
    """
    registry = er.async_get(hass)
    device_id = _async_vtherm_device_id(hass, thermostat_unique_id)
    if device_id is None:
        return None

    for candidate in registry.entities.values():
        if (
            candidate.domain == BINARY_SENSOR_DOMAIN
            and candidate.platform == VT_DOMAIN
            and candidate.device_id == device_id
            and candidate.unique_id.endswith("_heating_failure_state")
        ):
            if hass.states.get(candidate.entity_id) is not None:
                return None
            registry.async_remove(candidate.entity_id)
            return candidate.entity_id
    return None


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
        device_id = _async_vtherm_device_id(hass, unique_id)
        device_info = _async_vtherm_device_info(hass, unique_id)
        legacy_entity_id = _async_take_legacy_entity_id(hass, unique_id)
        existing_entity_id = registry.async_get_entity_id(
            BINARY_SENSOR_DOMAIN, DOMAIN, sensor_unique_id
        )
        if existing_entity_id:
            update_kwargs = {"config_entry_id": entry.entry_id}
            if legacy_entity_id and existing_entity_id != legacy_entity_id:
                update_kwargs["new_entity_id"] = legacy_entity_id
            if device_id is not None:
                update_kwargs["device_id"] = device_id
            registry.async_update_entity(existing_entity_id, **update_kwargs)
            continue
        entities.append(
            HeatingFailureBinarySensor(
                hass,
                unique_id,
                legacy_entity_id,
                device_info,
            )
        )
    if entities:
        async_add_entities(entities)


class HeatingFailureBinarySensor(BinarySensorEntity):
    """Expose the aggregate state of a plugin heating-failure manager."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:radiator-off"

    def __init__(
        self,
        hass: HomeAssistant,
        thermostat_unique_id: str,
        legacy_entity_id: str | None = None,
        device_info: DeviceInfo | None = None,
    ) -> None:
        self._hass = hass
        self._thermostat_unique_id = thermostat_unique_id
        self._attr_unique_id = f"{thermostat_unique_id}_heating_failure_state"
        self._attr_translation_key = "heating_failure_state"
        self._attr_has_entity_name = True
        self._attr_device_info = device_info
        self._legacy_object_id = (
            legacy_entity_id.removeprefix(f"{BINARY_SENSOR_DOMAIN}.")
            if legacy_entity_id is not None
            else None
        )

    @property
    def suggested_object_id(self) -> str | None:
        """Reuse the historical object ID when the legacy registry entry was stale."""
        return self._legacy_object_id or super().suggested_object_id

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