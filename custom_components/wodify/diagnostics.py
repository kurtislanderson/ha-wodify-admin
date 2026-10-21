"""Diagnostics support for the Wodify integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY
from .models import WodifyConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: WodifyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    last_update = coordinator.last_successful_update
    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "coordinator": {
            "api_connected": coordinator.api_connected,
            "last_error": coordinator.last_error,
            "last_successful_update": last_update.isoformat() if last_update else None,
            "class_count": len(coordinator.data or []),
        },
    }
