"""Diagnostics support for Bicing.

Permet descarregar un informe de diagnòstic des de la fitxa de la
integració a Home Assistant (Configuració > Dispositius i serveis > Bicing
> ... > Descarregar diagnòstics). El token de l'API es redacta sempre
abans d'incloure'l a l'informe, per evitar que s'acabi compartint per
error (p. ex. en adjuntar-lo a un issue de GitHub).
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import TOKEN

TO_REDACT = {TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), TO_REDACT),
    }
