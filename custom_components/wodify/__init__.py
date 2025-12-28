"""Wodify Home Assistant integration entry points."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WodifyAPI
from .const import (
    CONF_AFTER_BLOCK_MINUTES,
    CONF_API_KEY,
    CONF_BEFORE_CLASS_MINUTES,
    CONF_EXCLUDE_PRIVATE_TRAINING,
    CONF_LOCATIONS,
    CONF_PROGRAMS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_AFTER_BLOCK_MINUTES,
    DEFAULT_BEFORE_CLASS_MINUTES,
    DEFAULT_EXCLUDE_PRIVATE_TRAINING,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import WodifyDataUpdateCoordinator
from .events import WodifyEventManager
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Initial set-up of the integration."""

    await async_setup_services(hass)
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wodify from a config entry."""

    # Get configuration from entry (locations/programs can be in data or options)
    api_key = entry.data[CONF_API_KEY]
    locations = entry.options.get(CONF_LOCATIONS, entry.data.get(CONF_LOCATIONS, []))
    programs = entry.options.get(CONF_PROGRAMS, entry.data.get(CONF_PROGRAMS, []))
    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    before_minutes = entry.options.get(CONF_BEFORE_CLASS_MINUTES, DEFAULT_BEFORE_CLASS_MINUTES)
    after_minutes = entry.options.get(CONF_AFTER_BLOCK_MINUTES, DEFAULT_AFTER_BLOCK_MINUTES)
    exclude_private = entry.options.get(
        CONF_EXCLUDE_PRIVATE_TRAINING, DEFAULT_EXCLUDE_PRIVATE_TRAINING
    )

    # Create API client
    session = async_get_clientsession(hass)
    api = WodifyAPI(api_key=api_key, session=session, hass=hass)

    # Create coordinator
    coordinator = WodifyDataUpdateCoordinator(
        hass=hass,
        api=api,
        locations=locations,
        programs=programs,
        update_interval=update_interval,
        exclude_private_training=exclude_private,
    )

    # Create event manager
    event_manager = WodifyEventManager(
        hass=hass,
        coordinator=coordinator,
        before_class_minutes=before_minutes,
        after_block_minutes=after_minutes,
    )

    # Link event manager to coordinator for cancellation handling
    coordinator.event_manager = event_manager

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Schedule events based on initial data
    event_manager.schedule_events()

    # Add listener to reschedule events when coordinator updates
    def _schedule_events_on_update() -> None:
        event_manager.schedule_events()

    coordinator.async_add_listener(_schedule_events_on_update)

    # Store runtime data
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
        "event_manager": event_manager,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for option updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up event manager
        if "event_manager" in hass.data[DOMAIN][entry.entry_id]:
            event_manager = hass.data[DOMAIN][entry.entry_id]["event_manager"]
            event_manager.cancel_all_events()

        # Remove entry data
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
