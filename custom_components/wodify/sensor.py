"""Sensor entities for the Wodify integration."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import WodifyDataUpdateCoordinator
from .models import WodifyClass

_ICON = "mdi:weight-lifter"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Wodify sensors."""
    runtime = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: WodifyDataUpdateCoordinator = runtime["coordinator"]

    async_add_entities(
        [
            WodifyNextClassSensor(coordinator, config_entry),
            WodifyCurrentClassSensor(coordinator, config_entry),
            WodifyApiStatusSensor(coordinator, config_entry),
        ]
    )


class WodifyNextClassSensor(CoordinatorEntity[WodifyDataUpdateCoordinator], SensorEntity):
    """Sensor representing the next upcoming class."""

    _attr_icon = _ICON
    _attr_should_poll = False
    _attr_name = "Next Class"

    def __init__(self, coordinator: WodifyDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        unique_source = config_entry.unique_id or config_entry.entry_id
        self._attr_unique_id = f"{unique_source}_next_class"

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        return bool(data is not None and self.coordinator.last_update_success)

    def _next_class(self) -> WodifyClass | None:
        if not self.coordinator.data:
            return None
        now = dt_util.now()
        for wodify_class in sorted(self.coordinator.data, key=lambda cls: cls.start_time):
            if wodify_class.start_time > now and not wodify_class.is_cancelled:
                return wodify_class
        return None

    @property
    def native_value(self) -> str | None:
        if not self.available:
            return None

        next_class = self._next_class()
        if not next_class:
            return "No upcoming classes"

        start_local = dt_util.as_local(next_class.start_time)
        time_str = start_local.strftime("%I:%M %p").lstrip("0")
        return f"{next_class.name} at {time_str} with {next_class.coach_name}"

    @staticmethod
    def _format_time(value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%S")

    @property
    def extra_state_attributes(self) -> dict[str, str | int | bool]:
        attributes: dict[str, str | int | bool] = {}
        if not self.available:
            return attributes

        next_class = self._next_class()
        if not next_class:
            return attributes

        capacity = (
            f"{next_class.current_attendees}/{next_class.max_attendees}"
            if next_class.max_attendees
            else str(next_class.current_attendees)
        )

        attributes.update(
            {
                "class_id": next_class.id,
                "class_name": next_class.name,
                "coach": next_class.coach_name,
                "location": next_class.location_name,
                "program": next_class.program_name,
                "start_time": self._format_time(next_class.start_time),
                "end_time": self._format_time(next_class.end_time),
                "duration_minutes": next_class.duration_minutes,
                "capacity": capacity,
                "is_full": next_class.is_full,
            }
        )
        return attributes

    @property
    def device_info(self) -> dict[str, object]:
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "Wodify",
            "manufacturer": "Wodify",
            "model": "Gym Schedule",
        }


class WodifyCurrentClassSensor(CoordinatorEntity[WodifyDataUpdateCoordinator], SensorEntity):
    """Sensor showing the current ongoing class or 'No class'."""

    _attr_icon = _ICON
    _attr_should_poll = False
    _attr_name = "Current Class"

    def __init__(self, coordinator: WodifyDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        unique_source = config_entry.unique_id or config_entry.entry_id
        self._attr_unique_id = f"{unique_source}_current_class"

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
    def native_value(self) -> str:
        if not self.available:
            return "Unavailable"

        current_class = self._current_class()
        if not current_class:
            return "No active class"

        return f"{current_class.name} with {current_class.coach_name}"

    @staticmethod
    def _format_time(value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%S")

    @property
    def extra_state_attributes(self) -> dict[str, str | int | bool]:
        attributes: dict[str, str | int | bool] = {}
        if not self.available:
            return attributes

        current_class = self._current_class()
        if not current_class:
            return attributes

        now = dt_util.now()
        remaining = int((current_class.end_time - now).total_seconds() // 60)

        capacity = (
            f"{current_class.current_attendees}/{current_class.max_attendees}"
            if current_class.max_attendees
            else str(current_class.current_attendees)
        )

        attributes.update(
            {
                "class_id": current_class.id,
                "class_name": current_class.name,
                "coach": current_class.coach_name,
                "location": current_class.location_name,
                "program": current_class.program_name,
                "start_time": self._format_time(current_class.start_time),
                "end_time": self._format_time(current_class.end_time),
                "minutes_remaining": max(0, remaining),
                "duration_minutes": current_class.duration_minutes,
                "capacity": capacity,
                "is_full": current_class.is_full,
            }
        )
        return attributes

    @property
    def icon(self) -> str:
        """Return different icon based on whether a class is ongoing."""
        return "mdi:timer" if self._current_class() else "mdi:timer-off"

    @property
    def device_info(self) -> dict[str, object]:
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "Wodify",
            "manufacturer": "Wodify",
            "model": "Gym Schedule",
        }


class WodifyApiStatusSensor(CoordinatorEntity[WodifyDataUpdateCoordinator], SensorEntity):
    """Sensor showing Wodify API connection status."""

    _attr_should_poll = False
    _attr_name = "API Status"

    def __init__(self, coordinator: WodifyDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        unique_source = config_entry.unique_id or config_entry.entry_id
        self._attr_unique_id = f"{unique_source}_api_status"

    @property
    def available(self) -> bool:
        # This sensor is always available (it reports the API status)
        return True

    @property
    def native_value(self) -> str:
        if self.coordinator.api_connected:
            return "Connected"
        return "Disconnected"

    @property
    def icon(self) -> str:
        if self.coordinator.api_connected:
            return "mdi:cloud-check"
        return "mdi:cloud-off-outline"

    @property
    def extra_state_attributes(self) -> dict[str, str | int | bool | None]:
        attributes: dict[str, str | int | bool | None] = {
            "connected": self.coordinator.api_connected,
        }

        if self.coordinator.last_successful_update:
            attributes["last_successful_update"] = (
                self.coordinator.last_successful_update.isoformat()
            )

        if self.coordinator.last_error:
            attributes["last_error"] = self.coordinator.last_error

        if self.coordinator.cached_data:
            attributes["cached_classes"] = len(self.coordinator.cached_data)
            attributes["using_cache"] = not self.coordinator.api_connected

        return attributes

    @property
    def device_info(self) -> dict[str, object]:
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "Wodify",
            "manufacturer": "Wodify",
            "model": "Gym Schedule",
        }
