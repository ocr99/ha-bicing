# Bicing entity ID normalization

This update keeps the translated entity names while making the entity IDs stable and language-independent.

Example:

- `sensor.c_independencia_379_available_bikes`
- `sensor.c_independencia_379_available_electric_bikes`
- `sensor.c_independencia_379_available_mechanical_bikes`
- `sensor.c_independencia_379_available_docks`

The integration migrates existing Bicing entities in the entity registry after the platform has registered them, so existing dashboards and automations can use the new deterministic IDs without deleting and recreating the integration.

If a target entity ID is already occupied, the integration leaves the existing ID untouched and logs a warning instead of overwriting it.
