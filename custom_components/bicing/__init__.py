"""Bicing integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

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
    except (BicingAuthError, BicingRateLimitError, BicingApiError, aiohttp.ClientError, TimeoutError) as exc:
        # These exceptions can only reach here if the API/coordinator changes
        # its error mapping in the future. A failed first refresh should cause
        # Home Assistant to retry config entry setup automatically.
        from homeassistant.exceptions import ConfigEntryNotReady

        _LOGGER.debug("No s'ha pogut inicialitzar Bicing: %s", exc)
        raise ConfigEntryNotReady("No s'ha pogut connectar amb l'API del Bicing.") from exc

    entry.runtime_data = BicingRuntimeData(api=api, coordinator=coordinator)

    # The previous release used the station name as unique_id. Migrate those
    # registry entries in place once metadata is available, so users do not
    # get duplicate entities after upgrading.
    _migrate_entity_unique_ids(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _migrate_entity_registry_names(hass, entry, coordinator)
    return True


def _migrate_entity_registry_names(
    hass: HomeAssistant,
    entry: BicingConfigEntry,
    coordinator: BicingStationCoordinator,
) -> None:
    """Restore translated metric names for existing entities.

    Older releases stored the station name as the entity name. Existing
    registry entries keep that value, so simply adding translation keys does
    not fix already-created entities. This migration only clears the legacy
    station-name override and sets the expected translation key for our stable
    metric unique IDs. User-customized names are preserved.
    """
    registry = er.async_get(hass)
    metrics = (
        "total_bikes",
        "ebikes",
        "mechanical_bikes",
        "available_docks",
    )
    expected_metrics = {
        f"{station_id}_{metric}": (station_id, metric)
        for station_id in coordinator.station_info
        for metric in metrics
    }

    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        metric_info = expected_metrics.get(entity_entry.unique_id)
        if metric_info is None or entity_entry.domain != "sensor":
            continue

        station_id, metric = metric_info
        station_info = coordinator.station_info.get(station_id)
        changes: dict[str, object] = {}

        if entity_entry.translation_key != metric:
            changes["translation_key"] = metric

        # Only clear the legacy name when it is still exactly the station
        # name. A user-defined custom name must never be overwritten.
        if station_info and entity_entry.name == station_info.name:
            changes["name"] = None

        if changes:
            registry.async_update_entity(entity_entry.entity_id, **changes)


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
            _LOGGER.error("No s'ha pogut migrar l'entrada de Bicing: falta configuració.")
            return False

        hass.config_entries.async_update_entry(
            entry,
            data={TOKEN: token},
            options={CONF_STATION_IDS: list(map(str, station_ids))},
            version=3,
        )

    return True
