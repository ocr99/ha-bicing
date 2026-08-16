"""Estat del Bicing."""
from __future__ import annotations

import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import TOKEN
from .lib.bike_stations_api import BicingApiError, BicingAuthError, BikeStationApi

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Sessió HTTP compartida de HA: evita obrir una connexió TLS nova a
    # cada crida i reutilitza el connection pool de la instància.
    session = async_get_clientsession(hass)
    token = entry.options.get(TOKEN, entry.data[TOKEN])

    try:
        await BikeStationApi.get_bike_stations(session, token)
    except BicingAuthError as exc:
        _LOGGER.error("El token del Bicing sembla invàlid o ha caducat.")
        raise ConfigEntryAuthFailed("Token invàlid o caducat.") from exc
    except aiohttp.ContentTypeError as exc:
        # Heurística: si l'API no respon JSON, sol ser un token no vàlid.
        _LOGGER.error(
            "Error connectant-se amb l'API del Bicing. El token podria ser invàlid (Content-Type inesperat)."
        )
        raise ConfigEntryAuthFailed(
            "Error connectant-se amb l'API del Bicing. El token podria ser invàlid."
        ) from exc
    except (BicingApiError, aiohttp.ClientError, TimeoutError) as exc:
        # Error temporal de xarxa/servidor: HA reintentarà automàticament.
        _LOGGER.error("Error connectant-se amb l'API del Bicing: %s", exc)
        raise ConfigEntryNotReady("No s'ha pogut connectar amb l'API del Bicing.") from exc

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def _async_update_options(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, **config_entry.options}
    )
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entries to the current version."""
    if config_entry.version == 1:
        data = {**config_entry.data}
        hass.config_entries.async_update_entry(config_entry, data=data, version=2)

    return True
