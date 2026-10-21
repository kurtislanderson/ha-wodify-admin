"""Wodify Home Assistant integration entry points."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WodifyAPI
from .const import (
    CONF_AFTER_BLOCK_MINUTES,
    CONF_API_KEY,
    CONF_BEFORE_CLASS_MINUTES,
    CONF_BLOCK_GAP_MINUTES,
    CONF_EXCLUDE_PRIVATE_TRAINING,
    CONF_LOCATIONS,
    CONF_PROGRAMS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_AFTER_BLOCK_MINUTES,
    DEFAULT_BEFORE_CLASS_MINUTES,
    DEFAULT_BLOCK_GAP_MINUTES,
    DEFAULT_EXCLUDE_PRIVATE_TRAINING,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import WodifyDataUpdateCoordinator
from .events import WodifyEventManager
from .models import WodifyConfigEntry, WodifyRuntimeData
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Initial set-up of the integration."""

    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: WodifyConfigEntry) -> bool:
    """Set up Wodify from a config entry."""

    # Get configuration from entry (locations/programs can be in data or options)
    api_key = entry.data[CONF_API_KEY]
    locations = entry.options.get(CONF_LOCATIONS, entry.data.get(CONF_LOCATIONS, []))
    programs = entry.options.get(CONF_PROGRAMS, entry.data.get(CONF_PROGRAMS, []))
    update_interval = entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    before_minutes = entry.options.get(CONF_BEFORE_CLASS_MINUTES, DEFAULT_BEFORE_CLASS_MINUTES)
    after_minutes = entry.options.get(CONF_AFTER_BLOCK_MINUTES, DEFAULT_AFTER_BLOCK_MINUTES)
    block_gap_minutes = entry.options.get(
        CONF_BLOCK_GAP_MINUTES, DEFAULT_BLOCK_GAP_MINUTES
    )
    exclude_private = entry.options.get(
        CONF_EXCLUDE_PRIVATE_TRAINING, DEFAULT_EXCLUDE_PRIVATE_TRAINING
    )

    # Create API client
    session = async_get_clientsession(hass)
    api = WodifyAPI(api_key=api_key, session=session, hass=hass)

    # Create coordinator
    coordinator = WodifyDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        api=api,
        locations=locations,
        programs=programs,
        update_interval=update_interval,
        exclude_private_training=exclude_private,
        block_gap_minutes=block_gap_minutes,
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

    # Listen for option updates (registered before the first refresh so a failed
    # setup still reloads on option changes)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Schedule events based on initial data
    event_manager.schedule_events()

    # Add listener to reschedule events when coordinator updates
    def _schedule_events_on_update() -> None:
        event_manager.schedule_events()

    entry.async_on_unload(coordinator.async_add_listener(_schedule_events_on_update))

    # Store runtime data
    entry.runtime_data = WodifyRuntimeData(
        coordinator=coordinator, api=api, event_manager=event_manager
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WodifyConfigEntry) -> bool:
    """Unload a config entry."""

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up event manager
        entry.runtime_data.event_manager.cancel_all_events()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: WodifyConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
