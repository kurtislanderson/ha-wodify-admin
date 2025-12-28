"""Binary sensor for tracking ongoing Wodify classes."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AFTER_BLOCK_MINUTES,
    CONF_BEFORE_CLASS_MINUTES,
    DEFAULT_AFTER_BLOCK_MINUTES,
    DEFAULT_BEFORE_CLASS_MINUTES,
    DOMAIN,
)
from .coordinator import WodifyDataUpdateCoordinator, detect_class_blocks
from .models import WodifyClass


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Wodify binary sensors."""
    runtime = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: WodifyDataUpdateCoordinator = runtime["coordinator"]

    async_add_entities(
        [
            WodifyClassOngoingBinarySensor(coordinator, config_entry),
            WodifyClassStartingSoonBinarySensor(coordinator, config_entry),
            WodifyBlockJustEndedBinarySensor(coordinator, config_entry),
        ]
    )


class WodifyClassOngoingBinarySensor(
    CoordinatorEntity[WodifyDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether a class is currently ongoing."""

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_name = "Class Ongoing"

    def __init__(self, coordinator: WodifyDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
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
            "model": "Gym Schedule",
        }


class WodifyClassStartingSoonBinarySensor(
    CoordinatorEntity[WodifyDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor that turns ON when a class starts within the configured minutes.

    Use this sensor to trigger pre-class automations (e.g., turn on TVs, lights).
    Turns ON when: now is within `before_class_minutes` of the next class start time.
    """

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_name = "Pre-Class Trigger"

    def __init__(self, coordinator: WodifyDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        unique_source = config_entry.unique_id or config_entry.entry_id
        self._attr_unique_id = f"{unique_source}_class_starting_soon"

    @property
    def _before_minutes(self) -> int:
        return self._config_entry.options.get(
            CONF_BEFORE_CLASS_MINUTES, DEFAULT_BEFORE_CLASS_MINUTES
        )

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
    def is_on(self) -> bool | None:
        if not self.available:
            return None
        next_class = self._next_class()
        if not next_class:
            return False
        now = dt_util.now()
        time_until_start = (next_class.start_time - now).total_seconds() / 60
        return 0 < time_until_start <= self._before_minutes

    @staticmethod
    def _format_time(value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%S")

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return attributes for the pre-class trigger sensor.

        Attributes:
            trigger_window_minutes: Configured minutes before class to trigger (5-60)
            next_class: Name of the upcoming class
            coach: Coach name for the upcoming class
            location: Location of the upcoming class
            minutes_until_class: Minutes until the class starts
            class_start_time: ISO formatted start time of the upcoming class
        """
        attributes: dict[str, object] = {
            "trigger_window_minutes": self._before_minutes,
        }
        next_class = self._next_class()
        if next_class is None:
            return attributes

        now = dt_util.now()
        minutes_until = int((next_class.start_time - now).total_seconds() // 60)

        attributes.update(
            {
                "next_class": next_class.name,
                "coach": next_class.coach_name,
                "location": next_class.location_name,
                "minutes_until_class": max(0, minutes_until),
                "class_start_time": self._format_time(next_class.start_time),
            }
        )
        return attributes

    @property
    def icon(self) -> str:
        return "mdi:television" if self.is_on else "mdi:television-off"

    @property
    def device_info(self) -> dict[str, object]:
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "Wodify",
            "manufacturer": "Wodify",
            "model": "Gym Schedule",
        }


class WodifyBlockJustEndedBinarySensor(
    CoordinatorEntity[WodifyDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor that turns ON after a class block ends within the configured minutes.

    Use this sensor to trigger post-block automations (e.g., turn off TVs, lights).
    Turns ON when: now is within `after_block_minutes` of the last class block end time.
    A "block" is a group of back-to-back classes with gaps < 30 minutes between them.
    """

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_name = "Post-Block Trigger"

    def __init__(self, coordinator: WodifyDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        unique_source = config_entry.unique_id or config_entry.entry_id
        self._attr_unique_id = f"{unique_source}_block_just_ended"

    @property
    def _after_minutes(self) -> int:
        return self._config_entry.options.get(CONF_AFTER_BLOCK_MINUTES, DEFAULT_AFTER_BLOCK_MINUTES)

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        return bool(data is not None and self.coordinator.last_update_success)

    def _last_ended_block(self) -> list[WodifyClass] | None:
        """Find the most recently ended block."""
        if not self.coordinator.data:
            return None
        now = dt_util.now()
        blocks = detect_class_blocks(self.coordinator.data)

        # Find blocks that ended recently (within after_minutes)
        for block in reversed(blocks):
            if not block:
                continue
            last_class = block[-1]
            block_end = last_class.end_time
            # Block ended and we're within the after_minutes window
            if block_end <= now <= block_end + timedelta(minutes=self._after_minutes):
                return block
        return None

    @property
    def is_on(self) -> bool | None:
        if not self.available:
            return None
        return self._last_ended_block() is not None

    @staticmethod
    def _format_time(value: datetime) -> str:
        return value.strftime("%Y-%m-%dT%H:%M:%S")

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return attributes for the post-block trigger sensor.

        Attributes:
            trigger_window_minutes: Configured minutes after block to trigger (5-60)
            last_class: Name of the last class in the block
            coach: Coach name for the last class
            location: Location of the block
            block_class_count: Number of classes in the block
            block_duration_minutes: Total duration of the block in minutes
            minutes_since_block_end: Minutes since the block ended
            block_end_time: ISO formatted end time of the block
        """
        attributes: dict[str, object] = {
            "trigger_window_minutes": self._after_minutes,
        }
        block = self._last_ended_block()
        if block is None:
            return attributes

        last_class = block[-1]
        first_class = block[0]
        now = dt_util.now()
        minutes_since_end = int((now - last_class.end_time).total_seconds() // 60)
        block_duration = int((last_class.end_time - first_class.start_time).total_seconds() // 60)

        attributes.update(
            {
                "last_class": last_class.name,
                "coach": last_class.coach_name,
                "location": last_class.location_name,
                "block_class_count": len(block),
                "block_duration_minutes": block_duration,
                "minutes_since_block_end": max(0, minutes_since_end),
                "block_end_time": self._format_time(last_class.end_time),
            }
        )
        return attributes

    @property
    def icon(self) -> str:
        return "mdi:television-off" if self.is_on else "mdi:television"

    @property
    def device_info(self) -> dict[str, object]:
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "Wodify",
            "manufacturer": "Wodify",
            "model": "Gym Schedule",
        }
