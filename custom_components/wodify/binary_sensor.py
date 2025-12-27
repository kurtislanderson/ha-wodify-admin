"""Binary sensor platform for Wodify."""
import logging
from datetime import datetime

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_BLOCK_END, ATTR_BLOCK_START, ATTR_CLASSES_IN_BLOCK, DOMAIN
from .coordinator import WodifyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wodify binary sensor based on a config entry."""
    coordinator: WodifyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    async_add_entities([WodifyClassBlockBinarySensor(coordinator, entry)])


class WodifyClassBlockBinarySensor(
    CoordinatorEntity[WodifyDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor for indicating if currently in a class block."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self, coordinator: WodifyDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_in_class_block"
        self._attr_name = "In Class Block"

    @property
    def is_on(self) -> bool:
        """Return true if currently in a class block."""
        return self.coordinator.data.get("in_class_block", False)

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        attrs = {}
        
        block_info = self.coordinator.data.get("current_block_info")
        if block_info:
            attrs[ATTR_BLOCK_START] = block_info.get("start")
            attrs[ATTR_BLOCK_END] = block_info.get("end")
            
            classes = block_info.get("classes", [])
            attrs[ATTR_CLASSES_IN_BLOCK] = len(classes)
            
            # Add details of all classes in the block
            for i, cls in enumerate(classes, 1):
                attrs[f"class_{i}_name"] = cls.get("name")
                attrs[f"class_{i}_time"] = cls.get("start_time")
                attrs[f"class_{i}_instructor"] = cls.get("instructor")
        
        return attrs
