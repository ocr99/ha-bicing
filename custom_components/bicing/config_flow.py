"""Config flow for Bicing."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

import voluptuous as vol  # type: ignore

from homeassistant import config_entries  # type: ignore
from homeassistant.data_entry_flow import FlowResult  # type: ignore
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.helpers.selector import (  # type: ignore
    SelectSelector,
    SelectSelectorConfig,
    SelectOptionDict,
    SelectSelectorMode,
    TextSelector,
)

from .const import CONF_STATION_IDS, DOMAIN, TOKEN
from .lib.bike_stations_api import BicingApiError, BicingAuthError, BikeStationApi

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self.token: str | None = None
        self.station_ids: list[str] = []
        self.config_entry: config_entries.ConfigEntry | None = None

    async def _fetch_stations(self, token: str):
        """Consulta l'API amb la sessió HTTP compartida de HA."""
        session = async_get_clientsession(self.hass)
        return await BikeStationApi.get_bike_stations(session, token)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self.token = user_input[TOKEN]
            return await self.async_step_station()

        schema = vol.Schema({vol.Required(TOKEN): TextSelector()})
        return self.async_show_form(step_id="user", data_schema=schema, last_step=False)

    async def async_step_station(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self.station_ids = list(user_input[CONF_STATION_IDS])

            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Bicing",
                data={TOKEN: self.token, CONF_STATION_IDS: self.station_ids},
            )

        try:
            stations = await self._fetch_stations(self.token)
        except (BicingAuthError, aiohttp.ContentTypeError):
            return self.async_abort(reason="token_error")
        except aiohttp.ServerConnectionError:
            return self.async_abort(reason="status_error")
        except (aiohttp.ClientError, TimeoutError):
            return self.async_abort(reason="client_error")
        except BicingApiError:
            return self.async_abort(reason="status_error")

        options = [
            SelectOptionDict(label=f"{s.id} - {s.name}", value=str(s.id)) for s in stations
        ]

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_IDS): SelectSelector(
                    SelectSelectorConfig(
                        options=options, multiple=True, mode=SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(step_id="station", data_schema=schema)

    async def async_step_token(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Demana (o revalida) el token, usat pel flux de reautenticació."""
        schema = vol.Schema({vol.Required(TOKEN): TextSelector()})

        if user_input is None:
            return self.async_show_form(step_id="token", data_schema=schema)

        assert self.config_entry is not None
        new_token = user_input[TOKEN]

        # Es valida el token abans de desar-lo, en comptes d'assumir que és
        # correcte i descobrir-ho al proper cicle d'actualització.
        try:
            await self._fetch_stations(new_token)
        except (BicingAuthError, aiohttp.ContentTypeError):
            return self.async_show_form(
                step_id="token", data_schema=schema, errors={"base": "invalid_auth"}
            )
        except aiohttp.ServerConnectionError:
            return self.async_show_form(
                step_id="token", data_schema=schema, errors={"base": "cannot_connect"}
            )
        except (aiohttp.ClientError, TimeoutError):
            return self.async_show_form(
                step_id="token", data_schema=schema, errors={"base": "cannot_connect"}
            )
        except BicingApiError:
            return self.async_show_form(
                step_id="token", data_schema=schema, errors={"base": "unknown"}
            )

        return self.async_update_reload_and_abort(
            self.config_entry,
            data={
                TOKEN: new_token,
                CONF_STATION_IDS: self.config_entry.data[CONF_STATION_IDS],
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self.config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_token()

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        self.config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        assert self.config_entry is not None

        estacions_actuals = self.config_entry.data[CONF_STATION_IDS]
        token_actual = self.config_entry.data[TOKEN]

        if user_input is not None:
            station_ids = list(user_input[CONF_STATION_IDS])
            self.station_ids = station_ids

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={TOKEN: token_actual, CONF_STATION_IDS: station_ids},
                options=self.config_entry.options,
            )

            # Neteja d'entitats antigues que hagin quedat "unavailable" en
            # desseleccionar estacions. S'usa l'accés modern al registre
            # d'entitats (`entity_registry.async_get(hass)`); l'antic
            # `hass.helpers.entity_registry.async_get()` està deprecat des
            # de fa temps i s'ha anat retirant de Home Assistant Core.
            entity_registry = er.async_get(self.hass)
            entity_entries = async_entries_for_config_entry(
                entity_registry, self.config_entry.entry_id
            )

            for entity_entry in entity_entries:
                state = self.hass.states.get(entity_entry.entity_id)
                if state is not None and state.state != STATE_UNAVAILABLE:
                    continue
                entity_registry.async_remove(entity_entry.entity_id)

            return self.async_abort(reason="data_updated")

        try:
            stations = await self._fetch_stations(token_actual)
        except (BicingAuthError, aiohttp.ContentTypeError):
            return self.async_abort(reason="token_error")
        except aiohttp.ServerConnectionError:
            return self.async_abort(reason="status_error")
        except (aiohttp.ClientError, TimeoutError):
            return self.async_abort(reason="client_error")
        except BicingApiError:
            return self.async_abort(reason="status_error")

        options = [
            SelectOptionDict(label=f"{s.id} - {s.name}", value=str(s.id)) for s in stations
        ]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_STATION_IDS, default=list(estacions_actuals)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=options, multiple=True, mode=SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )

        return self.async_show_form(step_id="reconfigure", data_schema=schema)
