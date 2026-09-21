# VTherm Heating Failure Detection

Home Assistant plugin that detects insufficient temperature response while a
Versatile Thermostat using proportional control is heating.

Install the integration, create its global configuration entry, then optionally
create thermostat-specific overrides. Existing core configuration remains active
during the transition release; do not enable both configurations for the same
thermostat.

The plugin keeps the historical event
`versatile_thermostat_heating_failure_event` and climate attributes.