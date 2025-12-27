"""Sensor platform for Wodify."""
import logging
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CLASS_DURATION,
    ATTR_CLASS_INSTRUCTOR,
    ATTR_CLASS_LOCATION,
    ATTR_CLASS_NAME,
    ATTR_CLASS_TIME,
    DOMAIN,
)
from .coordinator import WodifyDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Wodify sensor based on a config entry."""
    coordinator: WodifyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    async_add_entities([WodifyNextClassSensor(coordinator, entry)])


class WodifyNextClassSensor(
    CoordinatorEntity[WodifyDataUpdateCoordinator], SensorEntity
):
    """Sensor for next upcoming class."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:dumbbell"

    def __init__(
        self, coordinator: WodifyDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_next_class"
        self._attr_name = "Next Class"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        next_class = self.coordinator.data.get("next_class")
        if next_class:
            return next_class.get("name", "Unknown")
        return "No upcoming classes"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        attrs = {}
        
        next_class = self.coordinator.data.get("next_class")
        if next_class:
            attrs[ATTR_CLASS_NAME] = next_class.get("name")
            attrs[ATTR_CLASS_TIME] = next_class.get("start_time")
            attrs[ATTR_CLASS_INSTRUCTOR] = next_class.get("instructor")
            attrs[ATTR_CLASS_LOCATION] = next_class.get("location")
            attrs[ATTR_CLASS_DURATION] = next_class.get("duration")
            
            # Calculate time until class
            try:
                start_time = datetime.fromisoformat(next_class.get("start_time"))
                time_until = start_time - datetime.now()
                attrs["time_until_minutes"] = int(time_until.total_seconds() / 60)
                attrs["time_until_formatted"] = str(time_until).split(".")[0]
            except (ValueError, TypeError):
                pass
        
        # Add count of upcoming classes
        upcoming = self.coordinator.data.get("upcoming_classes", [])
        attrs["upcoming_classes_count"] = len(upcoming)
        
        return attrs
