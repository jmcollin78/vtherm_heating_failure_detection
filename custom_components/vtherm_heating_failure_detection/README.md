# VTherm Heating Failure Detection

Home Assistant plugin that detects insufficient temperature response while a
Versatile Thermostat using proportional control is heating.

Install the integration, then use its configuration flow to migrate the legacy
settings explicitly:

1. the first entry creates the plugin defaults and pre-fills them from the
	Versatile Thermostat central configuration when it is available;
2. each thermostat-specific entry pre-fills its values from the selected
	VTherm, including its legacy central-configuration choice.

Review and confirm each form. Plugin values take precedence over legacy values;
missing plugin values continue to fall back to persisted core settings during
the transition release.

> [!WARNING]
> The historical binary sensor belongs to the `versatile_thermostat` integration,
> while the new sensor belongs to this plugin. Home Assistant does not support a
> safe cross-integration entity-registry migration, so its `unique_id` and
> resulting `entity_id` can change. Update dashboards and automations to use the
> new sensor after migration.

The plugin keeps the historical event
`versatile_thermostat_heating_failure_event` and climate attributes.