"""Set up VTherm heating failure detection."""

from __future__ import annotations

import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant

from .const import CONF_VTHERM_UNIQUE_ID, DOMAIN, PLATFORMS
from .factory import HeatingFailureManagerFactory, register_factory, unregister_factory

VT_DOMAIN = "versatile_thermostat"


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register the factory as soon as Home Assistant loads the integration."""
    del config
    register_factory(hass, HeatingFailureManagerFactory(hass))
    return True


async def _reload_thermostats(
    hass: HomeAssistant,
    source_entry: ConfigEntry | None = None,
) -> None:
    """Reload only thermostats affected by a global or targeted entry."""
    target = None if source_entry is None else (source_entry.options or source_entry.data).get(CONF_VTHERM_UNIQUE_ID)
    target_overrides = {
        (entry.options or entry.data).get(CONF_VTHERM_UNIQUE_ID)
        for entry in hass.config_entries.async_entries(DOMAIN)
        if (entry.options or entry.data).get(CONF_VTHERM_UNIQUE_ID)
    }
    tasks = []
    for thermostat_entry in hass.config_entries.async_entries(VT_DOMAIN):
        if target is not None:
            if thermostat_entry.unique_id != target:
                continue
        elif source_entry is not None and thermostat_entry.unique_id in target_overrides:
            continue
        tasks.append(hass.config_entries.async_reload(thermostat_entry.entry_id))
    if tasks:
        await asyncio.gather(*tasks)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one global or thermostat-specific configuration entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data.setdefault("entries", {})
    domain_data["entries"][entry.entry_id] = dict(entry.options or entry.data)
    register_factory(hass, HeatingFailureManagerFactory(hass))
    entry.async_on_unload(entry.add_update_listener(_async_update_options))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if hass.state == CoreState.running:
        await _reload_thermostats(hass, entry)
    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload thermostats after plugin options change."""
    await _reload_thermostats(hass, entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a configuration entry and remove the factory when unused."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        return False

    domain_data = hass.data[DOMAIN]
    domain_data["entries"].pop(entry.entry_id, None)
    if not domain_data["entries"]:
        unregister_factory(hass)
        hass.data.pop(DOMAIN, None)
    await _reload_thermostats(hass, entry)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an updated configuration entry."""
    await hass.config_entries.async_reload(entry.entry_id)