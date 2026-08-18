"""Bicing integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from .const import CONF_STATION_IDS, DOMAIN, TOKEN
from .coordinator import BicingStationCoordinator
from .lib.bike_stations_api import (
    BicingApiError,
    BicingAuthError,
    BicingRateLimitError,
    BikeStationApi,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass(slots=True)
class BicingRuntimeData:
    """Runtime data for a Bicing config entry."""

    api: BikeStationApi
    coordinator: BicingStationCoordinator


BicingConfigEntry = ConfigEntry[BicingRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: BicingConfigEntry) -> bool:
    """Set up a Bicing config entry."""
    station_ids = [str(station_id) for station_id in entry.options[CONF_STATION_IDS]]
    session = async_get_clientsession(hass)
    api = BikeStationApi(session, entry.data[TOKEN])
    coordinator = BicingStationCoordinator(hass, entry, api, station_ids)
    try:
        await coordinator.async_config_entry_first_refresh()
    except (
        BicingAuthError,
        BicingRateLimitError,
        BicingApiError,
        aiohttp.ClientError,
        TimeoutError,
    ) as exc:
        from homeassistant.exceptions import ConfigEntryNotReady

        _LOGGER.debug("No s'ha pogut inicialitzar Bicing: %s", exc)
        raise ConfigEntryNotReady(
            "No s'ha pogut connectar amb l'API del Bicing."
        ) from exc

    entry.runtime_data = BicingRuntimeData(api=api, coordinator=coordinator)

    # The previous release used the station name as unique_id. Migrate those
    # registry entries in place once metadata is available, so users do not
    # get duplicate entities after upgrading.
    _migrate_entity_unique_ids(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Existing entities keep the object_id that was generated when they were
    # first created. Normalize all Bicing sensor entity IDs to an English,
    # language-independent format after the entities have been registered.
    _migrate_entity_registry(hass, entry, coordinator)

    return True


def _migrate_entity_registry(
    hass: HomeAssistant,
    entry: BicingConfigEntry,
    coordinator: BicingStationCoordinator,
) -> None:
    """Normalize Bicing sensor names and entity IDs.

    Home Assistant generates an entity_id from the translated entity name and
    device name when an entity is first registered. That means the resulting
    entity_id can depend on the backend language and can also differ between
    installations. Bicing instead uses a stable English metric suffix:

        sensor.c_independencia_379_available_bikes
        sensor.c_independencia_379_available_electric_bikes
        sensor.c_independencia_379_available_mechanical_bikes
        sensor.c_independencia_379_available_docks

    The friendly entity name remains translated through strings.json.
    User-defined entity names are preserved; only the entity_id is normalized.
    """
    registry = er.async_get(hass)
    metric_names = {
        "total_bikes": "available_bikes",
        "ebikes": "available_electric_bikes",
        "mechanical_bikes": "available_mechanical_bikes",
        "available_docks": "available_docks",
    }

    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity_entry.domain != "sensor":
            continue

        # Se usa split (primer "_") y no rsplit (último "_"): el station_id
        # del Bicing es siempre numérico, pero las claves de métrica
        # ("mechanical_bikes", "available_docks") contienen guiones bajos,
        # así que cortar por el último "_" partía la clave por la mitad.
        parts = entity_entry.unique_id.split("_", 1)
        if len(parts) != 2:
            continue

        station_id, metric = parts
        if metric not in metric_names:
            continue

        station_info = coordinator.station_info.get(station_id)
        if station_info is None:
            continue

        station_slug = slugify(station_info.name)
        target_entity_id = f"sensor.{station_slug}_{metric_names[metric]}"

        current_entity_id = entity_entry.entity_id
        if current_entity_id != target_entity_id:
            existing = registry.async_get(target_entity_id)
            if existing is None:
                registry.async_update_entity(
                    current_entity_id,
                    new_entity_id=target_entity_id,
                )
                current_entity_id = target_entity_id
            else:
                _LOGGER.warning(
                    "No se puede renombrar %s a %s porque la entidad ya existe",
                    current_entity_id,
                    target_entity_id,
                )

        # Older releases stored the station name as an explicit entity name.
        # Remove only that legacy override; custom user names remain untouched.
        if entity_entry.name == station_info.name:
            registry.async_update_entity(current_entity_id, name=None)

        if entity_entry.translation_key != metric:
            registry.async_update_entity(
                current_entity_id,
                translation_key=metric,
            )


def _migrate_entity_unique_ids(
    hass: HomeAssistant,
    entry: BicingConfigEntry,
    coordinator: BicingStationCoordinator,
) -> None:
    """Migrate entity unique IDs from old station-name IDs when possible."""
    registry = er.async_get(hass)
    station_names = {
        info.name: info.id for info in coordinator.station_info.values()
    }
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity_entry.unique_id not in station_names:
            continue
        station_id = station_names[entity_entry.unique_id]
        new_unique_id = f"{station_id}_total_bikes"
        if registry.async_get_entity_id(entity_entry.domain, DOMAIN, new_unique_id):
            continue
        registry.async_update_entity(
            entity_entry.entity_id,
            new_unique_id=new_unique_id,
            translation_key="total_bikes",
        )


async def async_unload_entry(hass: HomeAssistant, entry: BicingConfigEntry) -> bool:
    """Unload a Bicing config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries to the current format."""
    if entry.version == 1:
        hass.config_entries.async_update_entry(entry, version=2)
    if entry.version <= 2:
        station_ids = entry.options.get(
            CONF_STATION_IDS,
            entry.data.get(CONF_STATION_IDS, []),
        )
        token = entry.data.get(TOKEN, entry.options.get(TOKEN))
        if not token or not station_ids:
            _LOGGER.error(
                "No s'ha pogut migrar l'entrada de Bicing: falta configuració."
            )
            return False
        hass.config_entries.async_update_entry(
            entry,
            data={TOKEN: token},
            options={CONF_STATION_IDS: list(map(str, station_ids))},
            version=3,
        )

    return True