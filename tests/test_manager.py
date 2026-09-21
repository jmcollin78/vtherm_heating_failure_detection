"""Unit tests for the heating failure detection algorithm."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from homeassistant.const import STATE_OFF, STATE_ON

from custom_components.vtherm_heating_failure_detection.const import (
    CONF_DELAY_MINUTES,
    CONF_HEATING_PERCENT_THRESHOLD,
    CONF_TEMPERATURE_DELTA,
    DOMAIN,
)
from custom_components.vtherm_heating_failure_detection.manager import HeatingFailureManager


class FakeHass:
    """Minimal Home Assistant runtime required by the manager."""

    def __init__(self) -> None:
        self.data = {DOMAIN: {"entries": {"global": {CONF_HEATING_PERCENT_THRESHOLD: 0.8, CONF_DELAY_MINUTES: 30, CONF_TEMPERATURE_DELTA: 0.1}}}}

    def verify_event_loop_thread(self, method: str) -> None:
        """Match the dispatcher guard provided by Home Assistant."""
        del method


class FakeThermostat:
    """Public VTherm runtime surface used by the manager."""

    unique_id = "living-room"
    target_temperature = 20.0
    has_prop = True
    requested_hvac_mode = "heat"
    vtherm_hvac_mode = "heat"
    valve_diagnostics = ()

    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0)
        self.current_temperature = 19.0
        self.on_percent = 0.9
        self.events = []

    def send_event(self, event_type, payload) -> None:
        self.events.append((event_type, payload))

    def update_custom_attributes(self) -> None:
        pass

    def async_write_ha_state(self) -> None:
        pass


def test_detects_and_clears_heating_failure() -> None:
    """High output with insufficient rise starts then clears the failure."""
    asyncio.run(_detects_and_clears_heating_failure())


async def _detects_and_clears_heating_failure() -> None:
    """Run the asynchronous manager flow without pytest-asyncio fixtures."""
    hass = FakeHass()
    thermostat = FakeThermostat()
    manager = HeatingFailureManager(thermostat, hass)
    manager.post_init({})

    assert await manager.refresh_state() is False
    thermostat.now += timedelta(minutes=30)
    thermostat.current_temperature = 19.05

    assert await manager.refresh_state() is True
    assert manager.is_heating_failure_detected
    assert thermostat.events[-1][1]["type"] == "heating_failure_start"
    assert thermostat.events[-1][1]["failure_type"] == "heating"

    thermostat.now += timedelta(minutes=1)
    thermostat.on_percent = 0.5
    assert await manager.refresh_state() is False
    assert manager._heating_state == STATE_OFF
    assert thermostat.events[-1][1]["type"] == "heating_failure_end"


def test_disabled_hvac_resets_detection() -> None:
    """Turning HVAC off clears tracking and leaves no active failure."""
    asyncio.run(_disabled_hvac_resets_detection())


async def _disabled_hvac_resets_detection() -> None:
    """Run the asynchronous manager flow without pytest-asyncio fixtures."""
    hass = FakeHass()
    thermostat = FakeThermostat()
    manager = HeatingFailureManager(thermostat, hass)
    manager.post_init({})
    thermostat.requested_hvac_mode = "off"

    assert await manager.refresh_state() is False
    assert manager._heating_state == STATE_OFF
    assert manager._cooling_state == STATE_OFF