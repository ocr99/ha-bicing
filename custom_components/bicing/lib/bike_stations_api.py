"""Client per a l'API de dades obertes del Bicing (Ajuntament de Barcelona)."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any
from collections.abc import Mapping

import aiohttp

from .. import const

_LOGGER = logging.getLogger(__name__)


class BicingAuthError(Exception):
    """El token ha estat rebutjat explícitament per l'API (HTTP 401/403)."""


class BicingRateLimitError(Exception):
    """L'API ha limitat temporalment el nombre de peticions."""

    def __init__(self, retry_after: float | None = None) -> None:
        """Initialize the exception."""
        super().__init__("L'API del Bicing ha limitat temporalment les peticions.")
        self.retry_after = retry_after


class BicingApiError(Exception):
    """L'API ha respost amb un format inesperat o un error no relacionat amb l'autenticació."""


class BicingServerError(BicingApiError):
    """L'API ha respost amb un error temporal del servidor."""

    def __init__(self, status: int, retry_after: float | None = None) -> None:
        """Initialize the server error."""
        super().__init__(f"L'API ha retornat un error HTTP {status}.")
        self.status = status
        self.retry_after = retry_after


@dataclass(frozen=True, slots=True)
class StationInfo:
    """Static information about a Bicing station."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class StationStatus:
    """Current status information about a Bicing station."""

    id: str
    bikes_available: int
    ebikes_available: int
    docks_available: int


class BikeStationApi:
    """Client for the public Bicing API."""

    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        """Initialize the API client."""
        self._session = session
        self._token = token

    @staticmethod
    def _get_retry_after(headers: Mapping[str, str], default: float | None = None) -> float | None:
        """Parse and sanitize the Retry-After header."""
        raw_value = headers.get("Retry-After")
        if raw_value is None:
            return default

        try:
            retry_after = float(raw_value)
        except (TypeError, ValueError):
            return default

        return min(max(retry_after, 0.0), const.MAX_RETRY_AFTER_SECONDS)

    async def _get_json(
        self,
        url: str,
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> dict[str, Any]:
        """Fetch a JSON document from the API."""
        headers = {"Authorization": self._token}
        kwargs: dict[str, Any] = {"headers": headers}
        if timeout is not None:
            kwargs["timeout"] = timeout

        async with self._session.get(url, **kwargs) as response:
            if response.status in (401, 403):
                raise BicingAuthError(
                    f"El token ha estat rebutjat per l'API (HTTP {response.status})."
                )

            if response.status == 429:
                raise BicingRateLimitError(
                    self._get_retry_after(response.headers, default=60)
                )

            if response.status >= 500:
                raise BicingServerError(
                    response.status,
                    self._get_retry_after(response.headers, default=30),
                )

            if response.status >= 400:
                raise BicingApiError(
                    f"L'API ha retornat un error HTTP {response.status}."
                )

            content_type = response.headers.get("Content-Type", "")
            content_type = content_type.lower().split(";", 1)[0].strip()
            if content_type != "application/json":
                raise BicingApiError(
                    "L'API ha retornat un contingut amb un Content-Type inesperat."
                )

            try:
                data = await response.json()
            except (aiohttp.ContentTypeError, ValueError) as exc:
                raise BicingApiError("No s'ha pogut interpretar la resposta JSON.") from exc

            if not isinstance(data, dict):
                raise BicingApiError("La resposta de l'API no és un objecte JSON.")

            return data

    async def get_bike_stations(self) -> list[StationInfo]:
        """Return the station metadata."""
        data = await self._get_json(const.STATION_INFO_ENDPOINT)

        try:
            raw_stations = data["data"]["stations"]
        except (KeyError, TypeError) as exc:
            raise BicingApiError(
                "Format inesperat a la resposta d'informació d'estacions."
            ) from exc

        if not isinstance(raw_stations, list):
            raise BicingApiError("La llista d'estacions no té el format esperat.")

        stations: list[StationInfo] = []
        for station_data in raw_stations:
            if not isinstance(station_data, dict):
                _LOGGER.warning("Dades d'estació inesperades: %s", station_data)
                continue

            try:
                station_id = str(station_data["station_id"])
                name = str(station_data["name"])
            except (KeyError, TypeError):
                _LOGGER.warning("Estació amb dades incompletes ignorada: %s", station_data)
                continue

            stations.append(StationInfo(id=station_id, name=name))

        return stations

    async def get_stations_status(self, station_ids: list[str]) -> dict[str, StationStatus]:
        """Return the current status for the configured stations."""
        station_ids_str = {str(station_id) for station_id in station_ids}
        timeout = aiohttp.ClientTimeout(total=const.REQUEST_TIMEOUT_SECONDS)

        for attempt in range(const.RETRY_ATTEMPTS):
            try:
                data = await self._get_json(const.STATION_STATUS_ENDPOINT, timeout=timeout)
            except (
                aiohttp.ServerConnectionError,
                aiohttp.ServerTimeoutError,
                asyncio.TimeoutError,
            ) as exc:
                if attempt == const.RETRY_ATTEMPTS - 1:
                    raise
                backoff = 2**attempt
                _LOGGER.debug(
                    "Error temporal obtenint l'estat del Bicing (%s). "
                    "Reintentant en %ss...",
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                continue
            except BicingServerError as exc:
                if attempt == const.RETRY_ATTEMPTS - 1:
                    raise
                backoff = exc.retry_after if exc.retry_after is not None else 2**attempt
                _LOGGER.debug(
                    "Error %s de l'API del Bicing. Reintentant en %ss...",
                    exc.status,
                    backoff,
                )
                await asyncio.sleep(backoff)
                continue

            try:
                raw_stations = data["data"]["stations"]
            except (KeyError, TypeError) as exc:
                raise BicingApiError(
                    "Format inesperat a la resposta d'estat de les estacions."
                ) from exc

            if not isinstance(raw_stations, list):
                raise BicingApiError("La llista d'estats no té el format esperat.")

            station_status: dict[str, StationStatus] = {}
            for station in raw_stations:
                if not isinstance(station, dict):
                    continue

                try:
                    station_id = str(station["station_id"])
                    if station_id not in station_ids_str:
                        continue

                    bikes_by_type = station["num_bikes_available_types"]
                    station_status[station_id] = StationStatus(
                        id=station_id,
                        bikes_available=int(bikes_by_type["mechanical"]),
                        ebikes_available=int(bikes_by_type["ebike"]),
                        docks_available=int(station["num_docks_available"]),
                    )
                except (KeyError, TypeError, ValueError):
                    _LOGGER.warning("Estació amb dades incompletes ignorada: %s", station)

            return station_status

        raise BicingApiError("No s'ha pogut obtenir l'estat de les estacions.")
