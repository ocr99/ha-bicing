"""Config flow for Bicing."""
from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_STATION_IDS, DOMAIN, TOKEN
from .lib.bike_stations_api import BicingApiError, BicingAuthError, BikeStationApi


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bicing."""

    VERSION = 3

    def __init__(self) -> None:
        self.token: str | None = None

    async def _fetch_stations(self, token: str):
        """Fetch station metadata using HA's shared HTTP session."""
        session = async_get_clientsession(self.hass)
        return await BikeStationApi(session, token).get_bike_stations()

    @staticmethod
    def _station_schema(stations, defaults: list[str] | None = None) -> vol.Schema:
        """Build the station selector schema."""
        options = [
            SelectOptionDict(label=f"{station.id} - {station.name}", value=station.id)
            for station in stations
        ]
        selector = SelectSelector(
            SelectSelectorConfig(
                options=options,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        if defaults is not None:
            return vol.Schema(
                {vol.Required(CONF_STATION_IDS, default=defaults): selector}
            )
        return vol.Schema({vol.Required(CONF_STATION_IDS): selector})

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Ask for the API token."""
        if user_input is not None:
            self.token = user_input[TOKEN]
            return await self.async_step_station()

        schema = vol.Schema(
            {
                vol.Required(TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_station(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Select stations to monitor."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Bicing",
                data={TOKEN: self.token},
                options={CONF_STATION_IDS: [str(value) for value in user_input[CONF_STATION_IDS]]},
            )

        try:
            stations = await self._fetch_stations(self.token or "")
        except BicingAuthError:
            return self.async_abort(reason="token_error")
        except (aiohttp.ClientError, TimeoutError, BicingApiError):
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="station",
            data_schema=self._station_schema(stations),
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> FlowResult:
        """Perform reauthentication after an API authentication error."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_mismatch()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Explain that reauthentication is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_token()

    async def async_step_token(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Validate and save a replacement token."""
        schema = vol.Schema(
            {
                vol.Required(TOKEN): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                )
            }
        )

        if user_input is None:
            return self.async_show_form(step_id="token", data_schema=schema)

        new_token = user_input[TOKEN]
        try:
            await self._fetch_stations(new_token)
        except BicingAuthError:
            return self.async_show_form(
                step_id="token",
                data_schema=schema,
                errors={"base": "invalid_auth"},
            )
        except (aiohttp.ClientError, TimeoutError, BicingApiError):
            return self.async_show_form(
                step_id="token",
                data_schema=schema,
                errors={"base": "cannot_connect"},
            )

        entry = self._get_reauth_entry()
        return self.async_update_reload_and_abort(
            entry,
            data_updates={TOKEN: new_token},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reconfigure the stations to monitor."""
        entry = self._get_reconfigure_entry()
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_mismatch()
        current_station_ids = list(entry.options.get(CONF_STATION_IDS, []))

        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                entry,
                options={
                    **entry.options,
                    CONF_STATION_IDS: [
                        str(value) for value in user_input[CONF_STATION_IDS]
                    ],
                },
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="data_updated")

        try:
            stations = await self._fetch_stations(entry.data[TOKEN])
        except BicingAuthError:
            return self.async_abort(reason="token_error")
        except (aiohttp.ClientError, TimeoutError, BicingApiError):
            return self.async_abort(reason="cannot_connect")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._station_schema(stations, current_station_ids),
        )
