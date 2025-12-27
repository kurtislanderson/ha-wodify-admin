"""Binary sensor for tracking ongoing Wodify classes."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import WodifyDataUpdateCoordinator
from .models import WodifyClass


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Wodify binary sensors."""
    runtime = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: WodifyDataUpdateCoordinator = runtime["coordinator"]

    async_add_entities([WodifyClassOngoingBinarySensor(coordinator, config_entry)])


class WodifyClassOngoingBinarySensor(
    CoordinatorEntity[WodifyDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether a class is currently ongoing."""

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_name = "Class Ongoing"

    def __init__(
        self, coordinator: WodifyDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        unique_source = config_entry.unique_id or config_entry.entry_id
        self._attr_unique_id = f"{unique_source}_class_ongoing"

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        return bool(data is not None and self.coordinator.last_update_success)

    def _current_class(self) -> WodifyClass | None:
        if not self.coordinator.data:
            return None
        now = dt_util.now()
        for wodify_class in self.coordinator.data:
            if wodify_class.is_cancelled:
                continue
            if wodify_class.start_time <= now < wodify_class.end_time:
                return wodify_class
        return None

    @property
    def is_on(self) -> bool | None:
        if not self.available:
            return None
        return self._current_class() is not None

    @staticmethod
    def _format_time(value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%S")

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        attributes: dict[str, object] = {}
        current = self._current_class()
        if current is None:
            return attributes

        now = dt_util.now()
        remaining = int((current.end_time - now).total_seconds() // 60)

        attributes.update(
            {
                "current_class": current.name,
                "coach": current.coach_name,
                "location": current.location_name,
                "minutes_remaining": max(0, remaining),
                "start_time": self._format_time(current.start_time),
                "end_time": self._format_time(current.end_time),
            }
        )
        return attributes

    @property
    def icon(self) -> str:
        return "mdi:timer" if self.is_on else "mdi:timer-off"

    @property
    def device_info(self) -> dict[str, object]:
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "Wodify",
            "manufacturer": "Wodify",
        }
