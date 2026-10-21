"""Service registration for the Wodify integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import ApiError
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
from .models import WodifyRuntimeData

_SERVICE_REFRESH = "refresh_now"
_SERVICE_SET_FILTER = "set_filter"
_SERVICE_SET_EVENT_TIMING = "set_event_timing"
_SERVICE_SEND_EMAIL = "send_email"
_SERVICE_FLAG = "services_registered"


def _get_runtime(hass: HomeAssistant, entry_id: str) -> WodifyRuntimeData:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )
    runtime: WodifyRuntimeData = entry.runtime_data
    return runtime


async def _async_handle_refresh(hass: HomeAssistant, call: ServiceCall) -> None:
    entry_id = call.data.get("entry_id")
    if not entry_id:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_id_required")
    runtime = _get_runtime(hass, entry_id)
    await runtime.coordinator.async_request_refresh()


async def _async_handle_set_filter(hass: HomeAssistant, call: ServiceCall) -> None:
    entry_id = call.data.get("entry_id")
    if not entry_id:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_id_required")

    locations = call.data.get(CONF_LOCATIONS)
    programs = call.data.get(CONF_PROGRAMS)
    if not locations:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_locations")
    if not programs:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_programs")

    runtime = _get_runtime(hass, entry_id)
    await runtime.coordinator.async_set_filters(list(locations), list(programs))

    config_entry = hass.config_entries.async_get_entry(entry_id)
    if config_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )

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
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_id_required")

    before_minutes = int(call.data.get(CONF_BEFORE_CLASS_MINUTES, DEFAULT_BEFORE_CLASS_MINUTES))
    after_minutes = int(call.data.get(CONF_AFTER_BLOCK_MINUTES, DEFAULT_AFTER_BLOCK_MINUTES))

    if not (MIN_EVENT_MINUTES <= before_minutes <= MAX_EVENT_MINUTES):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_before_minutes",
            translation_placeholders={"min": str(MIN_EVENT_MINUTES), "max": str(MAX_EVENT_MINUTES)},
        )
    if not (MIN_EVENT_MINUTES <= after_minutes <= MAX_EVENT_MINUTES):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_after_minutes",
            translation_placeholders={"min": str(MIN_EVENT_MINUTES), "max": str(MAX_EVENT_MINUTES)},
        )

    runtime = _get_runtime(hass, entry_id)
    runtime.event_manager.update_timing(before_minutes, after_minutes)

    config_entry = hass.config_entries.async_get_entry(entry_id)
    if config_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )

    new_options = dict(config_entry.options)
    new_options.setdefault(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    new_options[CONF_BEFORE_CLASS_MINUTES] = before_minutes
    new_options[CONF_AFTER_BLOCK_MINUTES] = after_minutes

    hass.config_entries.async_update_entry(
        config_entry,
        options=new_options,
    )


SEND_EMAIL_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("to_email"): cv.string,
        vol.Required("subject"): cv.string,
        vol.Required("body"): cv.string,
        vol.Optional("from_email"): cv.string,
        vol.Optional("cc"): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional("bcc"): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def _async_handle_send_email(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, int | None] | None:
    runtime = _get_runtime(hass, call.data["entry_id"])
    try:
        result = await runtime.api.send_email(
            call.data["to_email"],
            call.data["subject"],
            call.data["body"],
            from_email=call.data.get("from_email"),
            cc=call.data.get("cc"),
            bcc=call.data.get("bcc"),
        )
    except ApiError as err:  # ApiAuthError is a subclass
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="send_email_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    if call.return_response:
        return {"email_service_email_id": result.get("email_service_email_id")}
    return None


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

    async def handle_send_email(call: ServiceCall) -> dict[str, int | None] | None:
        return await _async_handle_send_email(hass, call)

    hass.services.async_register(
        DOMAIN,
        _SERVICE_SEND_EMAIL,
        handle_send_email,
        schema=SEND_EMAIL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
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

    hass.services.async_remove(DOMAIN, _SERVICE_SEND_EMAIL)
    hass.services.async_remove(DOMAIN, _SERVICE_REFRESH)
    hass.services.async_remove(DOMAIN, _SERVICE_SET_FILTER)
    hass.services.async_remove(DOMAIN, _SERVICE_SET_EVENT_TIMING)
    domain_data[_SERVICE_FLAG] = False


__all__ = ["async_setup_services", "async_unload_services"]
