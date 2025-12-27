"""Calendar entity for the Wodify integration."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
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
    """Set up the Wodify calendar entity."""
    runtime = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: WodifyDataUpdateCoordinator = runtime["coordinator"]

    async_add_entities([WodifyCalendar(coordinator, config_entry)])


class WodifyCalendar(CoordinatorEntity[WodifyDataUpdateCoordinator], CalendarEntity):
    """Calendar showing scheduled Wodify classes."""

    _attr_should_poll = False
    _attr_name = "Classes"

    def __init__(
        self, coordinator: WodifyDataUpdateCoordinator, config_entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        unique_source = config_entry.unique_id or config_entry.entry_id
        self._attr_unique_id = f"{unique_source}_calendar"

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        return bool(data is not None and self.coordinator.last_update_success)

    def _iter_classes(self) -> Iterable[WodifyClass]:
        return sorted(self.coordinator.data or [], key=lambda cls: cls.start_time)

    def _build_event(self, wodify_class: WodifyClass) -> CalendarEvent:
        attendees = f"{wodify_class.current_attendees}/{wodify_class.max_attendees}"
        if wodify_class.is_full:
            attendees += " (FULL)"

        description = (
            f"{wodify_class.program_name} at {wodify_class.location_name}\n"
            f"Attendees: {attendees}"
        )

        event = CalendarEvent(
            summary=f"{wodify_class.name} - {wodify_class.coach_name}",
            start=wodify_class.start_time,
            end=wodify_class.end_time,
            description=description,
            location=wodify_class.location_name,
        )
        event.uid = f"wodify_class_{wodify_class.start_time.strftime('%Y%m%d%H%M')}"
        return event

    @property
    def event(self) -> CalendarEvent | None:
        if not self.available:
            return None

        now = dt_util.now()
        for wodify_class in self._iter_classes():
            if wodify_class.start_time <= now <= wodify_class.end_time:
                return self._build_event(wodify_class)
        return None

    async def async_get_events(
        self,
        _hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        if not self.available:
            return events

        start = dt_util.as_utc(start_date)
        end = dt_util.as_utc(end_date)

        for wodify_class in self._iter_classes():
            if start <= wodify_class.start_time <= end:
                events.append(self._build_event(wodify_class))

        return events

    async def async_get_tasks(self, _hass: HomeAssistant) -> list:
        return []

    @property
    def device_info(self) -> dict[str, object]:
        return {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": "Wodify",
        }
