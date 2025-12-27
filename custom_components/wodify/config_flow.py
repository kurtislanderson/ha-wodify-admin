"""Config flow for Wodify integration."""
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WodifyApiClient
from .const import (
    CONF_AFTER_BLOCK_NOTIFICATION,
    CONF_BEFORE_CLASS_NOTIFICATION,
    CONF_GYM_URL,
    DEFAULT_AFTER_BLOCK_NOTIFICATION,
    DEFAULT_BEFORE_CLASS_NOTIFICATION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_GYM_URL): str,
        vol.Optional(
            CONF_BEFORE_CLASS_NOTIFICATION,
            default=DEFAULT_BEFORE_CLASS_NOTIFICATION,
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
        vol.Optional(
            CONF_AFTER_BLOCK_NOTIFICATION,
            default=DEFAULT_AFTER_BLOCK_NOTIFICATION,
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    client = WodifyApiClient(
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        data[CONF_GYM_URL],
        session,
    )

    if not await client.async_test_connection():
        raise ConnectionError("Cannot connect to Wodify")

    return {"title": f"Wodify - {data[CONF_USERNAME]}"}


class WodifyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Wodify."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
