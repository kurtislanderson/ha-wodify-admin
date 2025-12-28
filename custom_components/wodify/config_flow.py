"""Configuration and options flow for the Wodify integration."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ApiAuthError, ApiError, WodifyAPI
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
    MAX_UPDATE_INTERVAL,
    MIN_EVENT_MINUTES,
    MIN_UPDATE_INTERVAL,
)


def _extract_program_names(programs: Iterable[dict[str, Any]]) -> list[str]:
    return sorted({str(program.get("name")) for program in programs if program.get("name")})


def _extract_locations(classes: Iterable[Any]) -> list[str]:
    locations: set[str] = set()
    for item in classes:
        location = getattr(item, "location_name", None)
        if not location and isinstance(item, dict):
            location = item.get("location")
        if location:
            locations.add(str(location))
    return sorted(locations)


class WodifyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key: str | None = None
        self._program_options: list[str] = []
        self._location_options: list[str] = []
        self._selected_locations: list[str] = []
        self._selected_programs: list[str] = []

    async def _create_api(self, hass: HomeAssistant, api_key: str) -> WodifyAPI:
        session = async_get_clientsession(hass)
        return WodifyAPI(api_key, session, hass)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            if self._async_current_entries():
                return self.async_abort(reason="already_configured")

            api_key = user_input[CONF_API_KEY]
            api = await self._create_api(self.hass, api_key)

            try:
                programs = await api.get_programs()
                classes = await api.search_classes()
            except ApiAuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            else:
                self._api_key = api_key
                self._program_options = _extract_program_names(programs)
                self._location_options = _extract_locations(classes)
                return await self.async_step_locations()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    async def async_step_locations(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        options = set(self._location_options)

        if user_input is not None:
            locations = user_input[CONF_LOCATIONS]
            if not locations:
                errors[CONF_LOCATIONS] = "no_locations"
            else:
                self._selected_locations = list(locations)
                return await self.async_step_programs()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LOCATIONS, default=list(self._selected_locations)
                ): cv.multi_select(options if options else set())
            }
        )
        return self.async_show_form(
            step_id="locations",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_programs(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        options = set(self._program_options)

        if user_input is not None:
            programs = user_input[CONF_PROGRAMS]
            if not programs:
                errors[CONF_PROGRAMS] = "no_programs"
            else:
                self._selected_programs = list(programs)
                return await self.async_step_options()

        schema = vol.Schema(
            {
                vol.Required(CONF_PROGRAMS, default=list(self._selected_programs)): cv.multi_select(
                    options if options else set()
                )
            }
        )
        return self.async_show_form(
            step_id="programs",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            update_interval = user_input[CONF_UPDATE_INTERVAL]
            before_minutes = user_input[CONF_BEFORE_CLASS_MINUTES]
            after_minutes = user_input[CONF_AFTER_BLOCK_MINUTES]

            if not (MIN_UPDATE_INTERVAL <= update_interval <= MAX_UPDATE_INTERVAL):
                errors[CONF_UPDATE_INTERVAL] = "invalid_update_interval"
            if not (MIN_EVENT_MINUTES <= before_minutes <= MAX_EVENT_MINUTES):
                errors[CONF_BEFORE_CLASS_MINUTES] = "invalid_before_minutes"
            if not (MIN_EVENT_MINUTES <= after_minutes <= MAX_EVENT_MINUTES):
                errors[CONF_AFTER_BLOCK_MINUTES] = "invalid_after_minutes"

            if not errors:
                title_location = self._selected_locations[0]
                return self.async_create_entry(
                    title=f"Wodify ({title_location})",
                    data={
                        CONF_API_KEY: self._api_key,
                        CONF_LOCATIONS: self._selected_locations,
                        CONF_PROGRAMS: self._selected_programs,
                    },
                    options={
                        CONF_UPDATE_INTERVAL: update_interval,
                        CONF_BEFORE_CLASS_MINUTES: before_minutes,
                        CONF_AFTER_BLOCK_MINUTES: after_minutes,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL),
                ),
                vol.Required(
                    CONF_BEFORE_CLASS_MINUTES, default=DEFAULT_BEFORE_CLASS_MINUTES
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_EVENT_MINUTES, max=MAX_EVENT_MINUTES),
                ),
                vol.Required(
                    CONF_AFTER_BLOCK_MINUTES, default=DEFAULT_AFTER_BLOCK_MINUTES
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_EVENT_MINUTES, max=MAX_EVENT_MINUTES),
                ),
            }
        )
        return self.async_show_form(
            step_id="options",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        entry_id = self.context.get("entry_id")
        entry = self.hass.config_entries.async_get_entry(entry_id) if entry_id else None

        if user_input is not None and entry is not None:
            new_key = user_input[CONF_API_KEY]
            api = await self._create_api(self.hass, new_key)
            try:
                await api.get_programs()
            except ApiAuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_API_KEY: new_key},
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        return WodifyOptionsFlow(config_entry)


class WodifyOptionsFlow(config_entries.OptionsFlowWithConfigEntry):
    """Handle options for an existing config entry."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        super().__init__(config_entry)
        self._locations: list[str] = list(
            config_entry.options.get(CONF_LOCATIONS, config_entry.data.get(CONF_LOCATIONS, []))
        )
        self._programs: list[str] = list(
            config_entry.options.get(CONF_PROGRAMS, config_entry.data.get(CONF_PROGRAMS, []))
        )

    async def _load_dynamic_options(self, hass: HomeAssistant) -> None:
        runtime = hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        # Handle both dict and object access for api
        if isinstance(runtime, dict):
            api = runtime.get("api")
        else:
            api = getattr(runtime, "api", None)
        if api is None:
            session = async_get_clientsession(hass)
            api = WodifyAPI(self.config_entry.data[CONF_API_KEY], session, hass)

        try:
            programs = await api.get_programs()
            classes = await api.search_classes()
        except (ApiError, ApiAuthError):
            return

        extracted_programs = _extract_program_names(programs)
        extracted_locations = _extract_locations(classes)
        if extracted_programs:
            self._programs = extracted_programs
        if extracted_locations:
            self._locations = extracted_locations

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        await self._load_dynamic_options(self.hass)

        errors: dict[str, str] = {}
        current_options = self.config_entry.options or {}

        update_interval = current_options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        before_minutes = current_options.get(
            CONF_BEFORE_CLASS_MINUTES, DEFAULT_BEFORE_CLASS_MINUTES
        )
        after_minutes = current_options.get(CONF_AFTER_BLOCK_MINUTES, DEFAULT_AFTER_BLOCK_MINUTES)
        selected_locations = current_options.get(
            CONF_LOCATIONS, self.config_entry.data.get(CONF_LOCATIONS, [])
        )
        selected_programs = current_options.get(
            CONF_PROGRAMS, self.config_entry.data.get(CONF_PROGRAMS, [])
        )

        if user_input is not None:
            update_interval = user_input[CONF_UPDATE_INTERVAL]
            before_minutes = user_input[CONF_BEFORE_CLASS_MINUTES]
            after_minutes = user_input[CONF_AFTER_BLOCK_MINUTES]
            selected_locations = user_input[CONF_LOCATIONS]
            selected_programs = user_input[CONF_PROGRAMS]

            if not (MIN_UPDATE_INTERVAL <= update_interval <= MAX_UPDATE_INTERVAL):
                errors[CONF_UPDATE_INTERVAL] = "invalid_update_interval"
            if not (MIN_EVENT_MINUTES <= before_minutes <= MAX_EVENT_MINUTES):
                errors[CONF_BEFORE_CLASS_MINUTES] = "invalid_before_minutes"
            if not (MIN_EVENT_MINUTES <= after_minutes <= MAX_EVENT_MINUTES):
                errors[CONF_AFTER_BLOCK_MINUTES] = "invalid_after_minutes"
            if not selected_locations:
                errors[CONF_LOCATIONS] = "no_locations"
            if not selected_programs:
                errors[CONF_PROGRAMS] = "no_programs"

            if not errors:
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_UPDATE_INTERVAL: update_interval,
                        CONF_BEFORE_CLASS_MINUTES: before_minutes,
                        CONF_AFTER_BLOCK_MINUTES: after_minutes,
                        CONF_LOCATIONS: list(selected_locations),
                        CONF_PROGRAMS: list(selected_programs),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_UPDATE_INTERVAL, default=update_interval): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL),
                ),
                vol.Required(CONF_BEFORE_CLASS_MINUTES, default=before_minutes): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_EVENT_MINUTES, max=MAX_EVENT_MINUTES),
                ),
                vol.Required(CONF_AFTER_BLOCK_MINUTES, default=after_minutes): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_EVENT_MINUTES, max=MAX_EVENT_MINUTES),
                ),
                vol.Required(CONF_LOCATIONS, default=list(selected_locations)): cv.multi_select(
                    set(self._locations)
                ),
                vol.Required(CONF_PROGRAMS, default=list(selected_programs)): cv.multi_select(
                    set(self._programs)
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
