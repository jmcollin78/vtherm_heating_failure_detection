# VTherm Heating Failure Detection

[Lire cette documentation en français](README.md)

Home Assistant plugin for heating and cooling failure detection with [Versatile Thermostat](https://github.com/jmcollin/versatile_thermostat).

It monitors how temperature responds to commands from the thermostat's proportional algorithm. When an abnormal condition persists, it publishes a Versatile Thermostat-compatible event and exposes a binary sensor for automations.

## How It Works

The plugin creates a `heating_failure_detection` manager for every VTherm with an effective configuration.

- A **heating failure** is detected when requested power is at or above the heating threshold for the configured delay, without sufficient temperature increase.
- A **cooling failure** is detected when requested power is at or below the cooling threshold for the configured delay while the temperature continues to rise.
- Detection is inactive when the VTherm is off, has no proportional algorithm, or when the activation template evaluates to false.
- When Versatile Thermostat provides valve diagnostics, the event also reports a valve that may be stuck open or closed.

Power thresholds are fractions between `0` and `1`: `0.80` means `80%` and `1.0` means `100%`.

## Prerequisites

- Home Assistant with [Versatile Thermostat](https://github.com/jmcollin/versatile_thermostat) installed and configured.
- A VTherm using a proportional algorithm.
- `vtherm_api` version `0.4.0` or later.

The plugin depends on the `versatile_thermostat` integration and does not control equipment. It observes VTherm state and reports anomalies.

## Installation

### HACS

[![Open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jmcollin&repository=vtherm_heating_failure_detection&category=Integration)

1. In HACS, add this repository as a custom integration.
2. Install `VTherm Heating Failure Detection`.
3. Restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration** and add `VTherm Heating Failure Detection`.

### Manual Installation

1. Copy [custom_components/vtherm_heating_failure_detection](custom_components/vtherm_heating_failure_detection) to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add `VTherm Heating Failure Detection` from **Settings > Devices & services**.

## Configuration

The first entry is the **global** entry: it defines defaults for every VTherm. Add another integration entry and select a thermostat to create a **per-thermostat override**. Its values replace global settings for that VTherm only.

| Option | Description | Default |
| --- | --- | --- |
| Enable detection | Enables or disables the detection manager. | Enabled |
| Heating threshold | Minimum requested power at which insufficient temperature rise is considered. | `1.0` |
| Cooling threshold | Maximum requested power below which temperature rise may indicate an anomaly. | `0.0` |
| Minimum expected temperature change | Minimum temperature increase expected during the detection delay. | `0.0` |
| Detection delay | Duration in minutes for which the condition must persist. | `30` |
| Activation template | Home Assistant template that must return `true`, `1`, `yes`, or `on` to enable detection. | Empty, therefore enabled |

Example template to monitor only while someone is home:

```jinja
{{ is_state('person.alice', 'home') }}
```

If template evaluation fails, detection deliberately remains enabled so a failure is not hidden.

After an entry is created, changed, or removed, only affected VTherms are reloaded to apply the new settings.

## Entities, Attributes, and Events

For every per-thermostat configuration, the plugin creates a binary sensor whose unique ID preserves the historical VTherm identifier:

```text
<vtherm_unique_id>_heating_failure_state
```

The sensor is on when either a heating or cooling failure is detected. The VTherm climate entity keeps tracking attributes under `heating_failure_detection_manager`, including individual states, thresholds, delay, and template status.

At every failure start or end, the plugin emits this event:

```text
versatile_thermostat_heating_failure_event
```

Its payload includes `type`, `failure_type`, `on_percent`, `temperature_difference`, `current_temp`, `target_temp`, `threshold`, `detection_delay_min`, `is_enabled_by_template`, and the `root_cause` diagnostic fields.

Example automation that notifies only when a heating failure starts:

```yaml
alias: VTherm heating failure alert
triggers:
  - trigger: event
    event_type: versatile_thermostat_heating_failure_event
    event_data:
      type: heating_failure_start
      failure_type: heating
actions:
  - action: notify.mobile_app_my_phone
    data:
      message: >-
        Heating is not producing the expected temperature increase.
mode: single
```

## Limitations

Detection reports an abnormal thermal response; it cannot by itself confirm the cause of a failure. Check equipment, temperature sensors, target temperature, and heating delay before taking action.

## Development

The manager unit tests are in [tests/test_manager.py](tests/test_manager.py). From an environment with Home Assistant dependencies:

```bash
pytest -q tests/test_manager.py
```