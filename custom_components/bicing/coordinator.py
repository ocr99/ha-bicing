"""Data update coordinator for Bicing."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, STALE_DATA_TTL_HOURS, UPDATE_INTERVAL
from .lib.bike_stations_api import (
    BicingApiError,
    BicingAuthError,
    BicingRateLimitError,
    BicingServerError,
    BikeStationApi,
    StationInfo,
    StationStatus,
)

_LOGGER = logging.getLogger(__name__)
_STALE_DATA_TTL = timedelta(hours=STALE_DATA_TTL_HOURS)


class BicingStationCoordinator(DataUpdateCoordinator[dict[str, StationStatus]]):
    """Coordinate all Bicing station updates."""

    station_info: dict[str, StationInfo]

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: BikeStationApi,
        station_ids: list[str],
    ) -> None:
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL),
        )
        self.entry = entry
        self.api = api
        self.station_ids = [str(station_id) for station_id in station_ids]
        self.station_info = {}
        self._last_success_time: datetime | None = None
        self._logged_unavailable = False

    async def _async_setup(self) -> None:
        """Load station metadata once during coordinator setup."""
        stations = await self.api.get_bike_stations()
        self.station_info = {station.id: station for station in stations}

        missing_station_ids = [
            station_id
            for station_id in self.station_ids
            if station_id not in self.station_info
        ]
        if missing_station_ids:
            _LOGGER.warning(
                "Les estacions configurades ja no apareixen al dataset del Bicing: %s",
                ", ".join(missing_station_ids),
            )

    def _cached_data_if_fresh(self, exc: Exception) -> dict[str, StationStatus] | None:
        """Return last known data while failures are within the stale TTL."""
        if self.data is None or self._last_success_time is None:
            return None

        age = datetime.now(timezone.utc) - self._last_success_time
        if age >= _STALE_DATA_TTL:
            return None

        _LOGGER.debug(
            "Error temporal obtenint dades del Bicing (%s). Es conserva l'últim estat "
            "conegut durant %s més.",
            exc,
            _STALE_DATA_TTL - age,
        )
        return self.data

    async def _async_update_data(self) -> dict[str, StationStatus]:
        """Fetch station status."""
        try:
            status = await self.api.get_stations_status(self.station_ids)
        except BicingAuthError as exc:
            raise ConfigEntryAuthFailed(
                "El token del Bicing ha estat rebutjat per l'API."
            ) from exc
        except BicingRateLimitError as exc:
            cached = self._cached_data_if_fresh(exc)
            if cached is not None:
                return cached
            self._log_unavailable()
            raise UpdateFailed(
                "L'API del Bicing ha limitat temporalment les peticions.",
                retry_after=exc.retry_after,
            ) from exc
        except (
            BicingServerError,
            aiohttp.ClientError,
            BicingApiError,
            TimeoutError,
        ) as exc:
            cached = self._cached_data_if_fresh(exc)
            if cached is not None:
                return cached
            self._log_unavailable()
            raise UpdateFailed(
                "No s'han pogut obtenir les dades del Bicing."
            ) from exc

        self._last_success_time = datetime.now(timezone.utc)
        self._log_recovered()
        return status

    def _log_unavailable(self) -> None:
        """Log the transition to an unavailable API once."""
        if self._logged_unavailable:
            return
        _LOGGER.warning("L'API del Bicing no està disponible; les entitats queden no disponibles.")
        self._logged_unavailable = True

    def _log_recovered(self) -> None:
        """Log recovery once after an outage."""
        if not self._logged_unavailable:
            return
        _LOGGER.info("L'API del Bicing torna a estar disponible.")
        self._logged_unavailable = False
