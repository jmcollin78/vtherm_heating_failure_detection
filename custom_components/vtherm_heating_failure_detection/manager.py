"""Heating and cooling failure detection feature manager."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.template import Template
from vtherm_api.const import EventType
from vtherm_api.log_collector import get_vtherm_logger, write_event_log

from .const import (
    CONF_ACTIVATION_TEMPLATE,
    CONF_COOLING_PERCENT_THRESHOLD,
    CONF_DELAY_MINUTES,
    CONF_ENABLED,
    CONF_HEATING_PERCENT_THRESHOLD,
    CONF_TEMPERATURE_DELTA,
    DOMAIN,
    FAILURE_TYPE_COOLING,
    FAILURE_TYPE_HEATING,
    MANAGER_ATTRIBUTES_KEY,
    MANAGER_NAME,
    SIGNAL_MANAGER_UPDATED,
)
from .models import effective_config

_LOGGER = get_vtherm_logger(__name__)


class HeatingFailureManager:
    """Detect insufficient temperature response to heating or cooling output."""

    def __init__(self, thermostat: Any, hass: HomeAssistant) -> None:
        self._thermostat = thermostat
        self._hass = hass
        self._configured = False
        self._heating_threshold = 0.8
        self._cooling_threshold = 0.0
        self._delay_minutes = 30
        self._temperature_delta = 0.0
        self._template: Template | None = None
        self._heating_state = STATE_UNAVAILABLE
        self._cooling_state = STATE_UNAVAILABLE
        self._baseline_temperature: float | None = None
        self._high_power_started: datetime | None = None
        self._zero_power_started: datetime | None = None
        self._listeners: list[CALLBACK_TYPE] = []

    @property
    def name(self) -> str:
        """Return the stable manager name used by the TPI handler."""
        return MANAGER_NAME

    @property
    def hass(self) -> HomeAssistant:
        """Return Home Assistant."""
        return self._hass

    @property
    def is_configured(self) -> bool:
        """Return whether detection has effective settings."""
        return self._configured

    @property
    def is_detected(self) -> bool:
        """Return whether either failure is active."""
        return self.is_failure_detected

    @property
    def is_failure_detected(self) -> bool:
        """Return whether a heating or cooling failure is active."""
        return self._heating_state == STATE_ON or self._cooling_state == STATE_ON

    @property
    def is_heating_failure_detected(self) -> bool:
        """Return whether a heating failure is active."""
        return self._heating_state == STATE_ON

    @property
    def is_cooling_failure_detected(self) -> bool:
        """Return whether a cooling failure is active."""
        return self._cooling_state == STATE_ON

    def post_init(self, entry_infos: dict[str, Any]) -> None:
        """Load the effective plugin configuration for this thermostat."""
        del entry_infos
        entries = self._hass.data.get(DOMAIN, {}).get("entries", {})
        config = effective_config(entries, self._thermostat.unique_id)
        if config is None or not config[CONF_ENABLED]:
            self._configured = False
            self._heating_state = STATE_UNAVAILABLE
            self._cooling_state = STATE_UNAVAILABLE
            self._hass.data.get(DOMAIN, {}).get("managers", {}).pop(
                self._thermostat.unique_id, None
            )
            return
        self._configured = True
        self._heating_threshold = float(config[CONF_HEATING_PERCENT_THRESHOLD])
        self._cooling_threshold = float(config[CONF_COOLING_PERCENT_THRESHOLD])
        self._delay_minutes = int(config[CONF_DELAY_MINUTES])
        self._temperature_delta = float(config[CONF_TEMPERATURE_DELTA])
        template = config.get(CONF_ACTIVATION_TEMPLATE)
        self._template = Template(template, self._hass) if template else None
        self._heating_state = STATE_UNKNOWN
        self._cooling_state = STATE_UNKNOWN
        self._hass.data.setdefault(DOMAIN, {}).setdefault("managers", {})[
            self._thermostat.unique_id
        ] = self

    async def start_listening(self, force: bool = False) -> None:
        """Implement the generic manager lifecycle; no listeners are required."""
        del force

    def stop_listening(self) -> None:
        """Release registered callbacks."""
        while self._listeners:
            self._listeners.pop()()
        managers = self._hass.data.get(DOMAIN, {}).get("managers", {})
        if managers.get(self._thermostat.unique_id) is self:
            managers.pop(self._thermostat.unique_id, None)

    def add_listener(self, func: CALLBACK_TYPE) -> None:
        """Register a callback released on stop."""
        self._listeners.append(func)

    def restore_state(self, old_state: Any) -> None:
        """Detection state is deliberately recomputed after restart."""
        del old_state

    async def refresh_state(self) -> bool:
        """Run one detection cycle and return the active failure state."""
        if not self._configured or not getattr(self._thermostat, "has_prop", False):
            return False
        if str(self._thermostat.requested_hvac_mode).lower() == "off":
            self._reset(STATE_OFF)
            return False
        if not self._is_template_enabled():
            now_temperature = self._thermostat.current_temperature or 0.0
            on_percent = self._thermostat.on_percent or 0.0
            if self._heating_state == STATE_ON:
                self._set_state(
                    FAILURE_TYPE_HEATING,
                    STATE_OFF,
                    on_percent,
                    0.0,
                    now_temperature,
                )
            if self._cooling_state == STATE_ON:
                self._set_state(
                    FAILURE_TYPE_COOLING,
                    STATE_OFF,
                    on_percent,
                    0.0,
                    now_temperature,
                )
            self._reset(STATE_OFF)
            self._publish_update()
            return False

        now = self._thermostat.now
        temperature = self._thermostat.current_temperature
        on_percent = self._thermostat.on_percent
        if temperature is None or on_percent is None:
            return False

        if str(self._thermostat.vtherm_hvac_mode).lower() == "heat":
            self._check_heating(now, temperature, on_percent)
            self._check_cooling(now, temperature, on_percent)
        if self._heating_state == STATE_UNKNOWN:
            self._heating_state = STATE_OFF
        if self._cooling_state == STATE_UNKNOWN:
            self._cooling_state = STATE_OFF
        self._publish_update()
        return self.is_failure_detected

    def _check_heating(self, now: datetime, temperature: float, on_percent: float) -> None:
        if on_percent < self._heating_threshold:
            if self._high_power_started is not None and self._heating_state == STATE_ON:
                self._set_state(FAILURE_TYPE_HEATING, STATE_OFF, on_percent, 0.0, temperature)
            self._high_power_started = None
            return
        if self._high_power_started is None:
            self._high_power_started, self._baseline_temperature = now, temperature
            return
        if now - self._high_power_started < timedelta(minutes=self._delay_minutes):
            return
        difference = temperature - (self._baseline_temperature or temperature)
        if difference < self._temperature_delta:
            self._set_state(FAILURE_TYPE_HEATING, STATE_ON, on_percent, difference, temperature)
        else:
            self._set_state(FAILURE_TYPE_HEATING, STATE_OFF, on_percent, difference, temperature)
            self._high_power_started, self._baseline_temperature = now, temperature

    def _check_cooling(self, now: datetime, temperature: float, on_percent: float) -> None:
        if on_percent > self._cooling_threshold:
            if self._zero_power_started is not None and self._cooling_state == STATE_ON:
                self._set_state(FAILURE_TYPE_COOLING, STATE_OFF, on_percent, 0.0, temperature)
            self._zero_power_started = None
            return
        if self._zero_power_started is None:
            self._zero_power_started, self._baseline_temperature = now, temperature
            return
        if now - self._zero_power_started < timedelta(minutes=self._delay_minutes):
            return
        difference = temperature - (self._baseline_temperature or temperature)
        if difference > self._temperature_delta:
            self._set_state(FAILURE_TYPE_COOLING, STATE_ON, on_percent, difference, temperature)
        else:
            self._set_state(FAILURE_TYPE_COOLING, STATE_OFF, on_percent, difference, temperature)
            self._zero_power_started, self._baseline_temperature = now, temperature

    def _set_state(self, failure_type: str, state: str, on_percent: float, difference: float, temperature: float) -> None:
        attribute = "_heating_state" if failure_type == FAILURE_TYPE_HEATING else "_cooling_state"
        old_state = getattr(self, attribute)
        if old_state == state:
            return
        setattr(self, attribute, state)
        event = f"{failure_type}_failure_{'start' if state == STATE_ON else 'end'}"
        self._send_event(event, failure_type, on_percent, difference, temperature)

    def _send_event(self, event: str, failure_type: str, on_percent: float, difference: float, temperature: float) -> None:
        diagnosis = self._diagnose(failure_type) if event.endswith("start") else self._empty_diagnosis()
        write_event_log(_LOGGER, self._thermostat, f"{failure_type.title()} failure {event.rsplit('_', 1)[-1]}: on_percent={on_percent * 100:.0f}%")
        self._thermostat.send_event(EventType.HEATING_FAILURE_EVENT, {
            "type": event, "failure_type": failure_type, "on_percent": on_percent,
            "temperature_difference": difference, "current_temp": temperature,
            "target_temp": self._thermostat.target_temperature,
            "threshold": self._heating_threshold if failure_type == FAILURE_TYPE_HEATING else self._cooling_threshold,
            "detection_delay_min": self._delay_minutes,
            "is_enabled_by_template": self._is_template_enabled(), **diagnosis,
        })

    def _empty_diagnosis(self) -> dict[str, Any]:
        return {"root_cause": "not_identified", "root_cause_entity_id": None, "root_cause_details": []}

    def _diagnose(self, failure_type: str) -> dict[str, Any]:
        diagnosis = self._empty_diagnosis()
        mismatches = []
        for valve in self._thermostat.valve_diagnostics:
            if valve.should_be_active == valve.is_active:
                continue
            kind = "valve_stuck_closed" if valve.should_be_active else "valve_stuck_open"
            mismatches.append({"entity_id": valve.entity_id, "type": kind, "requested": "open" if valve.should_be_active else "closed", "actual": "closed" if valve.should_be_active else "open"})
        if mismatches:
            preferred = "valve_stuck_closed" if failure_type == FAILURE_TYPE_HEATING else "valve_stuck_open"
            selected = next((item for item in mismatches if item["type"] == preferred), mismatches[0])
            diagnosis.update(root_cause=selected["type"], root_cause_entity_id=selected["entity_id"], root_cause_details=mismatches)
        return diagnosis

    def _is_template_enabled(self) -> bool:
        if self._template is None:
            return True
        try:
            return self._template.async_render().strip().lower() in {"true", "1", "yes", "on"}
        except Exception:  # noqa: BLE001
            _LOGGER.warning("%s - activation template failed; detection remains enabled", self._thermostat)
            return True

    def _reset(self, state: str) -> None:
        self._high_power_started = self._zero_power_started = None
        self._baseline_temperature = None
        self._heating_state = self._cooling_state = state

    def _tracking_info(self, start_time: datetime | None) -> dict[str, Any]:
        """Return the historical diagnostic tracking attributes."""
        if start_time is None:
            return {
                "is_tracking": False,
                "initial_temperature": None,
                "current_temperature": None,
                "remaining_time_min": None,
                "elapsed_time_min": None,
            }

        elapsed_minutes = (self._thermostat.now - start_time).total_seconds() / 60
        return {
            "is_tracking": True,
            "initial_temperature": self._baseline_temperature,
            "current_temperature": self._thermostat.current_temperature,
            "remaining_time_min": round(max(0, self._delay_minutes - elapsed_minutes), 1),
            "elapsed_time_min": round(elapsed_minutes, 1),
        }

    def _publish_update(self) -> None:
        self._thermostat.update_custom_attributes()
        self._thermostat.async_write_ha_state()
        async_dispatcher_send(self._hass, SIGNAL_MANAGER_UPDATED, self._thermostat.unique_id)

    def add_custom_attributes(self, attributes: dict[str, Any]) -> None:
        """Add the historical public attribute structure to the climate entity."""
        attributes["is_heating_failure_detection_configured"] = self._configured
        if self._configured:
            diagnosis = self._empty_diagnosis()
            if self._heating_state == STATE_ON:
                diagnosis = self._diagnose(FAILURE_TYPE_HEATING)
            elif self._cooling_state == STATE_ON:
                diagnosis = self._diagnose(FAILURE_TYPE_COOLING)
            attributes[MANAGER_ATTRIBUTES_KEY] = {
                "heating_failure_state": self._heating_state,
                "cooling_failure_state": self._cooling_state,
                "heating_failure_threshold": self._heating_threshold,
                "cooling_failure_threshold": self._cooling_threshold,
                "detection_delay_min": self._delay_minutes,
                "temperature_change_tolerance": self._temperature_delta,
                "failure_detection_enable_template": (
                    self._template.template if self._template is not None else None
                ),
                "is_detection_enabled_by_template": self._is_template_enabled(),
                "heating_tracking": self._tracking_info(self._high_power_started),
                "cooling_tracking": self._tracking_info(self._zero_power_started),
                "root_cause": diagnosis["root_cause"],
                "root_cause_entity_id": diagnosis["root_cause_entity_id"],
            }