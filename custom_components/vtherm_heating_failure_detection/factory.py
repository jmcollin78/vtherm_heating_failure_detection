"""Feature manager factory registered with VThermAPI."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from vtherm_api import VThermAPI
from vtherm_api.interfaces import InterfaceFeatureManager, InterfaceThermostatRuntime

from .const import DOMAIN, MANAGER_NAME
from .manager import HeatingFailureManager
from .models import effective_config

DATA_FACTORY_REGISTERED = "factory_registered"


class HeatingFailureManagerFactory:
    """Create managers only for thermostats with effective plugin settings."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass

    @property
    def name(self) -> str:
        """Return the stable feature-manager identifier."""
        return MANAGER_NAME

    def supports(self, thermostat: InterfaceThermostatRuntime) -> bool:
        """Return whether settings exist for this thermostat."""
        entries = self._hass.data.get(DOMAIN, {}).get("entries", {})
        return effective_config(entries, thermostat.unique_id) is not None

    def create(self, thermostat: InterfaceThermostatRuntime) -> InterfaceFeatureManager:
        """Create a manager bound to a single runtime thermostat."""
        return HeatingFailureManager(thermostat, self._hass)


def register_factory(hass: HomeAssistant, factory: HeatingFailureManagerFactory) -> None:
    """Idempotently register the feature-manager factory."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(DATA_FACTORY_REGISTERED):
        return
    api = VThermAPI.get_vtherm_api(hass)
    if api is None:
        return
    if api.get_feature_manager(MANAGER_NAME) is None:
        api.register_feature_manager(factory)
    data[DATA_FACTORY_REGISTERED] = True


def unregister_factory(hass: HomeAssistant) -> None:
    """Remove this plugin factory from the shared registry."""
    api = VThermAPI.get_vtherm_api(hass)
    if api is not None:
        api.unregister_feature_manager(MANAGER_NAME)
    hass.data.setdefault(DOMAIN, {})[DATA_FACTORY_REGISTERED] = False