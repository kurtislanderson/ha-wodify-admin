"""Button entities for the Wodify integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import WodifyDataUpdateCoordinator
from .models import WodifyConfigEntry, wodify_device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: WodifyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Wodify button entities."""
    coordinator = config_entry.runtime_data.coordinator

    async_add_entities([WodifyRefreshButton(coordinator, config_entry)])


class WodifyRefreshButton(ButtonEntity):
    """Button to refresh Wodify data."""

    _attr_icon = "mdi:refresh"
    _attr_has_entity_name = True
    _attr_translation_key = "refresh"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: WodifyDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._config_entry = config_entry
        unique_source = config_entry.unique_id or config_entry.entry_id
        self._attr_unique_id = f"{unique_source}_refresh"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._coordinator.async_request_refresh()

    @property
    def device_info(self) -> DeviceInfo:
        return wodify_device_info(self._config_entry)
