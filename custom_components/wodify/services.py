"""Service registration for the Wodify integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import (
    CONF_AFTER_BLOCK_MINUTES,
    CONF_BEFORE_CLASS_MINUTES,
    CONF_LOCATIONS,
    CONF_PROGRAMS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_AFTER_BLOCK_MINUTES,
    DEFAULT_BEFORE_CLASS_MINUTES,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_EVENT_MINUTES,
    MIN_EVENT_MINUTES,
)

_SERVICE_REFRESH = "refresh_now"
_SERVICE_SET_FILTER = "set_filter"
_SERVICE_SET_EVENT_TIMING = "set_event_timing"
_SERVICE_FLAG = "services_registered"


def _get_runtime(hass: HomeAssistant, entry_id: str) -> Any:
    runtime = hass.data.get(DOMAIN, {}).get(entry_id)
    if runtime is None:
        raise ServiceValidationError("Config entry not found")
    return runtime


async def _async_handle_refresh(hass: HomeAssistant, call: ServiceCall) -> None:
    entry_id = call.data.get("entry_id")
    if not entry_id:
        raise ServiceValidationError("entry_id is required")
    runtime = _get_runtime(hass, entry_id)
    await runtime["coordinator"].async_request_refresh()


async def _async_handle_set_filter(hass: HomeAssistant, call: ServiceCall) -> None:
    entry_id = call.data.get("entry_id")
    if not entry_id:
        raise ServiceValidationError("entry_id is required")

    locations = call.data.get(CONF_LOCATIONS)
    programs = call.data.get(CONF_PROGRAMS)
    if not locations:
        raise ServiceValidationError("At least one location must be provided")
    if not programs:
        raise ServiceValidationError("At least one program must be provided")

    runtime = _get_runtime(hass, entry_id)
    await runtime["coordinator"].async_set_filters(list(locations), list(programs))

    config_entry = hass.config_entries.async_get_entry(entry_id)
    if config_entry is None:
        raise ServiceValidationError("Config entry not found")

    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            CONF_LOCATIONS: list(locations),
            CONF_PROGRAMS: list(programs),
        },
    )


async def _async_handle_set_event_timing(hass: HomeAssistant, call: ServiceCall) -> None:
    entry_id = call.data.get("entry_id")
    if not entry_id:
        raise ServiceValidationError("entry_id is required")

    before_minutes = int(call.data.get(CONF_BEFORE_CLASS_MINUTES, DEFAULT_BEFORE_CLASS_MINUTES))
    after_minutes = int(call.data.get(CONF_AFTER_BLOCK_MINUTES, DEFAULT_AFTER_BLOCK_MINUTES))

    if not (MIN_EVENT_MINUTES <= before_minutes <= MAX_EVENT_MINUTES):
        raise ServiceValidationError(
            f"before_class_minutes must be between {MIN_EVENT_MINUTES} and {MAX_EVENT_MINUTES}"
        )
    if not (MIN_EVENT_MINUTES <= after_minutes <= MAX_EVENT_MINUTES):
        raise ServiceValidationError(
            f"after_block_minutes must be between {MIN_EVENT_MINUTES} and {MAX_EVENT_MINUTES}"
        )

    runtime = _get_runtime(hass, entry_id)
    runtime["event_manager"].update_timing(before_minutes, after_minutes)

    config_entry = hass.config_entries.async_get_entry(entry_id)
    if config_entry is None:
        raise ServiceValidationError("Config entry not found")

    new_options = dict(config_entry.options)
    new_options.setdefault(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    new_options[CONF_BEFORE_CLASS_MINUTES] = before_minutes
    new_options[CONF_AFTER_BLOCK_MINUTES] = after_minutes

    hass.config_entries.async_update_entry(
        config_entry,
        options=new_options,
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Wodify services."""

    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(_SERVICE_FLAG):
        return

    # Use async handlers directly - HA supports async service handlers
    async def handle_refresh(call: ServiceCall) -> None:
        await _async_handle_refresh(hass, call)

    async def handle_set_filter(call: ServiceCall) -> None:
        await _async_handle_set_filter(hass, call)

    async def handle_set_event_timing(call: ServiceCall) -> None:
        await _async_handle_set_event_timing(hass, call)

    hass.services.async_register(
        DOMAIN,
        _SERVICE_REFRESH,
        handle_refresh,
    )
    hass.services.async_register(
        DOMAIN,
        _SERVICE_SET_FILTER,
        handle_set_filter,
    )
    hass.services.async_register(
        DOMAIN,
        _SERVICE_SET_EVENT_TIMING,
        handle_set_event_timing,
    )

    domain_data[_SERVICE_FLAG] = True


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove registered services if present."""

    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get(_SERVICE_FLAG):
        return

    hass.services.async_remove(DOMAIN, _SERVICE_REFRESH)
    hass.services.async_remove(DOMAIN, _SERVICE_SET_FILTER)
    hass.services.async_remove(DOMAIN, _SERVICE_SET_EVENT_TIMING)
    domain_data[_SERVICE_FLAG] = False


__all__ = ["async_setup_services", "async_unload_services"]
