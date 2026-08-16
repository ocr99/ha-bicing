"""Sensor platform for Bicing."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Mapping, Any

import aiohttp

from .const import (
    CONF_STATION_IDS,
    UPDATE_INTERVAL,
    STALE_DATA_TTL_HOURS,
    TOKEN,
)

from .lib.bike_stations_api import BicingApiError, BicingAuthError, BikeStationApi

from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
    UpdateFailed,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from homeassistant.components.sensor import SensorEntityDescription, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

_STALE_DATA_TTL = timedelta(hours=STALE_DATA_TTL_HOURS)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    stations = entry.options.get(CONF_STATION_IDS, entry.data[CONF_STATION_IDS])
    token = entry.options.get(TOKEN, entry.data[TOKEN])
    session = async_get_clientsession(hass)

    _LOGGER.info("Creating Bicing stations %s", stations)

    coordinator = BicingStationCoordinator(hass, session, stations, token)
    await coordinator.async_config_entry_first_refresh()

    entities = []
    for station in stations:
        try:
            name = await BikeStationApi.get_station_name(session, token, station)
        except BicingAuthError as exc:
            _LOGGER.error("El token del Bicing sembla invàlid o ha caducat.")
            raise ConfigEntryAuthFailed("Token invàlid o caducat.") from exc
        except aiohttp.ContentTypeError:
            _LOGGER.error(
                "Error connectant-se amb l'API del Bicing. El token podria ser invàlid (Content-Type inesperat)."
            )
            return
        except (BicingApiError, aiohttp.ClientError, TimeoutError) as exc:
            _LOGGER.error("Error connectant-se amb l'API del Bicing: %s", exc)
            return

        entities.append(BicingStationSensor(name, name, station, coordinator))

    async_add_entities(entities)


class BicingStationCoordinator(DataUpdateCoordinator):

    def __init__(self, hass: HomeAssistant, session: aiohttp.ClientSession, stations, token):
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="Bicing Station",
            update_interval=timedelta(minutes=UPDATE_INTERVAL),
        )
        self._session = session
        self._token = token
        self._stations = stations
        self._last_success_time: datetime | None = None

    def _cached_data_if_fresh(self, exc: Exception):
        """Return last known data while failures are within the stale TTL."""
        if self.data is None or self._last_success_time is None:
            return None

        age = datetime.now(timezone.utc) - self._last_success_time
        if age >= _STALE_DATA_TTL:
            return None

        _LOGGER.warning(
            "Error temporal obtenint dades del Bicing (%s). "
            "Es manté l'últim estat conegut (fa %s; límit %s).",
            exc,
            age,
            _STALE_DATA_TTL,
        )
        return self.data

    async def _async_update_data(self):
        try:
            status = await BikeStationApi.get_stations_status(
                self._session, self._token, self._stations
            )

        except BicingAuthError as exc:
            # Error d'autenticació confirmat (HTTP 401/403): cal disparar el
            # flux de reautenticació de seguida, no té sentit servir dades
            # en caché perquè el token no tornarà a funcionar tot sol.
            _LOGGER.error("El token del Bicing sembla invàlid o ha caducat.")
            raise ConfigEntryAuthFailed("Token invàlid o caducat.") from exc

        except (
            aiohttp.ContentTypeError,
            aiohttp.ClientError,
            BicingApiError,
            TimeoutError,
        ) as exc:
            cached = self._cached_data_if_fresh(exc)
            if cached is not None:
                return cached

            _LOGGER.error("Error connectant-se amb l'API del Bicing: %s", exc)

            if isinstance(exc, aiohttp.ContentTypeError):
                # Un Content-Type inesperat sol indicar un token caducat.
                # Un cop exhaurida la caché, es dispara reautenticació.
                raise ConfigEntryAuthFailed(
                    "Error connectant-se amb l'API del Bicing (Content-Type inesperat). "
                    "El token podria haver caducat."
                ) from exc

            raise UpdateFailed("Error temporal connectant-se amb l'API del Bicing.") from exc

        self._last_success_time = datetime.now(timezone.utc)
        _LOGGER.debug("Bulk update=%s", status)
        return status


class BicingStationSensor(CoordinatorEntity, SensorEntity):

    def __init__(self, name: str, unique_id: str, id: str, coordinator):
        super().__init__(coordinator=coordinator)
        self.id = id
        self._state = None
        self._attrs: dict[str, Any] = {}
        self._attr_name = name
        self._attr_unique_id = unique_id
        self.entity_description = SensorEntityDescription(
            key=name,
            icon="mdi:bicycle",
            state_class="measurement",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Prefer unknown over unavailable after prolonged API failures."""
        # Els errors transitoris reutilitzen la caché del coordinator
        # (last_update_success es manté True). Passat el TTL, es llança
        # UpdateFailed i l'estat passa a "unknown" tot i seguir disponible.
        return True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.last_update_success:
            self._state = None
            self._attrs = {}
            self.async_write_ha_state()
            return

        data = self.coordinator.data
        if data is None:
            _LOGGER.debug("No coordinator data available for station %s", self.id)
            return

        for d in data:
            if str(d.id) == str(self.id):
                self._state = d.bikes_available + d.ebikes_available
                self._attrs["Bicicletes elèctriques disponibles"] = d.ebikes_available
                self._attrs["Bicicletes mecàniques disponibles"] = d.bikes_available
                self._attrs["Ancoratges disponibles"] = d.docks_available
                break

        self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        return self._state

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return self._attrs
