"""Client per a l'API de dades obertes del Bicing (Ajuntament de Barcelona)."""
from __future__ import annotations

from dataclasses import dataclass
import asyncio
import logging

import aiohttp  # type: ignore

from .. import const

_LOGGER = logging.getLogger(__name__)


class BicingAuthError(Exception):
    """El token ha estat rebutjat explícitament per l'API (HTTP 401/403)."""


class BicingApiError(Exception):
    """L'API ha respost amb un format inesperat o un error no relacionat amb l'autenticació."""


@dataclass
class StationInfo:
    id: int
    name: str


@dataclass
class StationStatus:
    id: str
    bikes_available: int
    ebikes_available: int
    docks_available: int


class BikeStationApi:
    """Wrapper per consultar els datasets d'informació i estat d'estacions.

    Totes les crides reben una `aiohttp.ClientSession` ja existent (la sessió
    compartida de Home Assistant) en lloc de crear-ne una de nova a cada
    petició, tal com recomana la guia de qualitat d'integracions de HA.
    """

    @staticmethod
    def _is_json_content_type(content_type: str | None) -> bool:
        if not content_type:
            return False
        return content_type.lower().split(";", 1)[0].strip() == "application/json"

    @staticmethod
    async def _get_json(
        session: aiohttp.ClientSession,
        token: str,
        url: str,
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> dict:
        headers = {"Authorization": token}
        kwargs: dict = {"headers": headers}
        if timeout is not None:
            kwargs["timeout"] = timeout

        async with session.get(url, **kwargs) as response:
            if response.status in (401, 403):
                raise BicingAuthError(
                    f"El token ha estat rebutjat per l'API (HTTP {response.status})."
                )
            if response.status >= 400:
                raise BicingApiError(
                    f"L'API ha retornat un error HTTP {response.status}."
                )

            content_type = response.headers.get("Content-Type")
            if not BikeStationApi._is_json_content_type(content_type):
                # L'API de dades obertes acostuma a respondre amb HTML/text
                # quan el token no és vàlid, en lloc d'un 401/403 net. Es
                # tracta com un possible problema d'autenticació aigües
                # amunt (vegeu sensor.py / config_flow.py).
                _LOGGER.error(
                    "El servidor ha retornat un contingut inesperat. Status=%s, Content-Type=%s",
                    response.status,
                    content_type,
                )
                raise aiohttp.ContentTypeError(
                    request_info=response.request_info,
                    history=response.history,
                    message=f"La resposta no és un JSON: {content_type}",
                )

            try:
                return await response.json()
            except (aiohttp.ContentTypeError, ValueError) as exc:
                raise BicingApiError("No s'ha pogut interpretar la resposta JSON.") from exc

    @staticmethod
    async def get_bike_stations(
        session: aiohttp.ClientSession, token: str
    ) -> list[StationInfo]:
        data = await BikeStationApi._get_json(session, token, const.STATION_INFO_ENDPOINT)

        try:
            raw_stations = data["data"]["stations"]
        except (KeyError, TypeError) as exc:
            raise BicingApiError(
                "Format inesperat a la resposta d'informació d'estacions."
            ) from exc

        stations: list[StationInfo] = []
        for station_data in raw_stations:
            try:
                stations.append(
                    StationInfo(id=station_data["station_id"], name=station_data["name"])
                )
            except (KeyError, TypeError):
                _LOGGER.warning("Estació amb dades incompletes ignorada: %s", station_data)

        return stations

    @staticmethod
    async def get_station_name(
        session: aiohttp.ClientSession, token: str, station_id
    ) -> str:
        data = await BikeStationApi._get_json(session, token, const.STATION_INFO_ENDPOINT)

        try:
            raw_stations = data["data"]["stations"]
        except (KeyError, TypeError) as exc:
            raise BicingApiError(
                "Format inesperat a la resposta d'informació d'estacions."
            ) from exc

        for station in raw_stations:
            if str(station.get("station_id")) == str(station_id):
                return station.get("name") or f"Estació {station_id}"

        return f"Estació {station_id}"

    @staticmethod
    async def get_stations_status(
        session: aiohttp.ClientSession, token: str, station_ids
    ) -> list[StationStatus]:
        station_ids_str = set(map(str, station_ids))
        timeout = aiohttp.ClientTimeout(total=const.REQUEST_TIMEOUT_SECONDS)

        last_exc: Exception | None = None

        for attempt in range(const.RETRY_ATTEMPTS):
            try:
                data = await BikeStationApi._get_json(
                    session, token, const.STATION_STATUS_ENDPOINT, timeout=timeout
                )
            except (
                aiohttp.ServerConnectionError,
                aiohttp.ServerTimeoutError,
                asyncio.TimeoutError,
            ) as exc:
                last_exc = exc
                if attempt == const.RETRY_ATTEMPTS - 1:
                    raise
                backoff = 2 ** attempt
                _LOGGER.warning(
                    "Error temporal obtenint l'estat de les estacions (%s). "
                    "Reintentant en %ss...",
                    exc,
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

            station_status_list: list[StationStatus] = []
            for station in raw_stations:
                try:
                    if str(station["station_id"]) not in station_ids_str:
                        continue
                    station_status_list.append(
                        StationStatus(
                            id=station["station_id"],
                            bikes_available=station["num_bikes_available_types"]["mechanical"],
                            ebikes_available=station["num_bikes_available_types"]["ebike"],
                            docks_available=station["num_docks_available"],
                        )
                    )
                except (KeyError, TypeError):
                    _LOGGER.warning("Estació amb dades incompletes ignorada: %s", station)

            return station_status_list

        # No s'hauria d'arribar mai aquí (o bé es retorna, o bé es fa `raise`).
        if last_exc is not None:
            raise last_exc
        raise BicingApiError("No s'ha pogut obtenir l'estat de les estacions.")
