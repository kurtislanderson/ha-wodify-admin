"""Event management for the Wodify integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta

from homeassistant.core import HassJob, HomeAssistant
from homeassistant.helpers.event import async_call_later as hass_async_call_later
from homeassistant.util import dt as dt_util

from .const import (
    EVENT_CLASS_BLOCK_DONE,
    EVENT_CLASS_CANCELLED,
    EVENT_CLASS_STARTS_SOON,
)
from .coordinator import detect_class_blocks
from .models import WodifyClass

_LOGGER = logging.getLogger(__name__)


# Older Home Assistant versions exposed ``async_call_later`` as a helper
# function instead of a method on ``HomeAssistant``. The pytest fixture used in
# the tests mirrors that behaviour, which means recent HA builds no longer
# provide ``hass.async_call_later``. To keep the integration compatible (and to
# make the tests happy) we create a lightweight wrapper when the attribute is
# missing. The wrapper delegates to the helper module so we still get a
# ``HassJob`` backed handle that Home Assistant's shutdown checks understand.
class _CancelHandle:
    """Simple wrapper around the cancellation callback returned by HA."""

    __slots__ = ("_cancel", "_cancelled")

    def __init__(self, cancel: Callable[[], None]) -> None:
        self._cancel = cancel
        self._cancelled = False

    def cancel(self) -> None:
        if self._cancelled:
            return
        self._cancelled = True
        self._cancel()


def _ensure_async_call_later(hass: HomeAssistant) -> None:
    if hasattr(hass, "async_call_later"):
        return

    def _async_call_later(
        delay: float | timedelta,
        callback: Callable[..., None],
    ):
        job = HassJob(lambda when: callback(when), cancel_on_shutdown=True)
        cancel = hass_async_call_later(hass, delay, job)
        return _CancelHandle(cancel)

    hass.async_call_later = _async_call_later


class _ScheduledEvent:
    """Wrapper around Home Assistant's scheduling helpers."""

    def __init__(
        self,
        hass: HomeAssistant,
        delay: float,
        callback: Callable[[], asyncio.Future | asyncio.Task | None],
    ) -> None:
        self._hass = hass
        self._cancelled = False
        self._callback = callback
        # Ensure we always schedule through async_call_later for HA friendly timing
        self._handle = hass.async_call_later(max(delay, 0), self._run)

    def _run(self, *_: object) -> None:
        if self._cancelled:
            return
        result = self._callback()
        if isinstance(result, asyncio.Future):
            return
        if isinstance(result, asyncio.Task):
            return

    def cancel(self) -> None:
        if self._cancelled:
            return
        self._cancelled = True
        self._handle.cancel()

    def cancelled(self) -> bool:
        return self._cancelled


class WodifyEventManager:
    """Schedule Home Assistant events for upcoming classes."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator,
        before_class_minutes: int,
        after_block_minutes: int,
    ) -> None:
        self.hass = hass
        self.coordinator = coordinator
        self.before_class_minutes = before_class_minutes
        self.after_block_minutes = after_block_minutes
        self._upcoming_events: dict[str, _ScheduledEvent] = {}
        self._block_end_events: dict[str, _ScheduledEvent] = {}
        self._sensor_schedules: dict[str, _ScheduledEvent] = {}
        self._binary_sensors: list = []

        # Link back to the coordinator so cancellation detection can notify us
        coordinator.event_manager = self

        _ensure_async_call_later(hass)

    def register_binary_sensors(self, sensors: list) -> None:
        """Store references to binary sensors for time-based state updates."""
        self._binary_sensors = sensors
        # Schedule updates immediately if we have data
        if self.coordinator.data:
            self._schedule_sensor_updates()

    def schedule_events(self) -> None:
        """Schedule events for all upcoming classes."""

        self._cancel_all_events()
        self._schedule_sensor_updates()

        classes = sorted(self.coordinator.data or [], key=lambda cls: cls.start_time)
        if not classes:
            return

        now = dt_util.now()

        # Schedule block completion events first
        blocks = detect_class_blocks(classes)
        for block in blocks:
            if not block:
                continue
            last_class: WodifyClass = block[-1]

            block_end = last_class.end_time + timedelta(minutes=self.after_block_minutes)
            if block_end <= now:
                continue

            delay = max(0.0, (block_end - now).total_seconds())
            key = last_class.id

            def make_block_callback(
                block_classes: list[WodifyClass],
            ) -> Callable[[], None]:
                def _callback() -> None:
                    self.hass.async_create_task(self._fire_block_done(block_classes))

                return _callback

            self._block_end_events[key] = _ScheduledEvent(
                self.hass,
                delay,
                make_block_callback(block),
            )

            _LOGGER.debug(
                "Scheduled block_done after %s (delay %.1fs)",
                last_class.name,
                delay,
            )

        # Schedule per-class "starts soon" events after block scheduling so the
        # most imminent callback is the most recent one queued.
        for wodify_class in classes:
            if wodify_class.is_cancelled:
                continue
            if wodify_class.end_time <= now:
                continue

            event_time = wodify_class.start_time - timedelta(minutes=self.before_class_minutes)
            delay = max(0.0, (event_time - now).total_seconds())

            def make_callback(cls: WodifyClass) -> Callable[[], None]:
                def _callback() -> None:
                    self.hass.async_create_task(self._fire_class_starts_soon(cls))

                return _callback

            self._upcoming_events[wodify_class.id] = _ScheduledEvent(
                self.hass,
                delay,
                make_callback(wodify_class),
            )

            _LOGGER.debug(
                "Scheduled starts_soon for %s at %s (delay %.1fs)",
                wodify_class.name,
                event_time,
                delay,
            )

    async def _fire_class_starts_soon(self, wodify_class: WodifyClass) -> None:
        """Fire the starts soon event for a class."""

        self._upcoming_events.pop(wodify_class.id, None)

        event_data = {
            "class_id": wodify_class.id,
            "class_name": wodify_class.name,
            "coach": wodify_class.coach_name,
            "location": wodify_class.location_name,
            "program": wodify_class.program_name,
            "start_time": wodify_class.start_time.isoformat(),
            "minutes_until_start": self.before_class_minutes,
        }

        _LOGGER.info("Firing starts_soon event for %s", wodify_class.name)
        self.hass.bus.async_fire(EVENT_CLASS_STARTS_SOON, event_data)

    async def _fire_block_done(self, block: list[WodifyClass]) -> None:
        """Fire the block completion event."""

        if not block:
            return

        first_class = block[0]
        last_class = block[-1]
        self._block_end_events.pop(last_class.id, None)

        block_duration = int((last_class.end_time - first_class.start_time).total_seconds() // 60)

        event_data = {
            "block_class_count": len(block),
            "block_duration_minutes": block_duration,
            "last_class_id": last_class.id,
            "last_class_name": last_class.name,
            "location": last_class.location_name,
            "minutes_after_end": self.after_block_minutes,
        }

        _LOGGER.info("Firing block_done event after %s", last_class.name)
        self.hass.bus.async_fire(EVENT_CLASS_BLOCK_DONE, event_data)

    def update_timing(self, before_minutes: int, after_minutes: int) -> None:
        """Update notification timing and reschedule events."""

        self.before_class_minutes = before_minutes
        self.after_block_minutes = after_minutes
        self.schedule_events()

    async def handle_class_cancelled(self, class_id: str, cancelled_class: WodifyClass) -> None:
        """Handle cancellation notification from the coordinator."""

        scheduled = self._upcoming_events.pop(class_id, None)
        if scheduled:
            scheduled.cancel()
            _LOGGER.info("Cancelled pending starts_soon event for class %s", class_id)

        event_data = {
            "class_id": class_id,
            "class_name": cancelled_class.name,
            "coach": cancelled_class.coach_name,
            "location": cancelled_class.location_name,
            "original_start_time": cancelled_class.start_time.isoformat(),
            "cancellation_time": dt_util.now().isoformat(),
        }

        _LOGGER.info("Fired cancellation event for class %s", class_id)
        self.hass.bus.async_fire(EVENT_CLASS_CANCELLED, event_data)

    def _schedule_sensor_updates(self) -> None:
        """Schedule exact-time state updates for binary sensors."""
        if not self._binary_sensors:
            return

        # Cancel old sensor schedules
        for handle in list(self._sensor_schedules.values()):
            handle.cancel()
        self._sensor_schedules.clear()

        now = dt_util.now()
        classes = [c for c in (self.coordinator.data or []) if not c.is_cancelled]
        if not classes:
            return

        blocks = detect_class_blocks(classes)

        # Find sensors by type
        class_starting_sensor = None
        block_starting_sensor = None
        block_ended_sensor = None
        class_ongoing_sensor = None

        for sensor in self._binary_sensors:
            sensor_id = getattr(sensor, "_attr_unique_id", "")
            if "class_starting_soon" in sensor_id and "block" not in sensor_id:
                class_starting_sensor = sensor
            elif "block_starting_soon" in sensor_id:
                block_starting_sensor = sensor
            elif "block_just_ended" in sensor_id:
                block_ended_sensor = sensor
            elif "class_ongoing" in sensor_id:
                class_ongoing_sensor = sensor

        # Schedule Class Starting Soon sensor updates (before each class)
        if class_starting_sensor:
            for wodify_class in classes:
                if wodify_class.end_time <= now:
                    continue
                # Schedule ON at: start_time - before_minutes
                on_time = wodify_class.start_time - timedelta(minutes=self.before_class_minutes)
                if on_time > now:
                    delay = (on_time - now).total_seconds()
                    key = f"class_starting_on_{wodify_class.id}"
                    self._sensor_schedules[key] = _ScheduledEvent(
                        self.hass,
                        delay,
                        lambda s=class_starting_sensor: s.async_write_ha_state(),
                    )
                    _LOGGER.debug("Scheduled class_starting ON at %s (delay %.1fs)", on_time, delay)

                # Schedule OFF at: start_time (class has started)
                if wodify_class.start_time > now:
                    delay = (wodify_class.start_time - now).total_seconds()
                    key = f"class_starting_off_{wodify_class.id}"
                    self._sensor_schedules[key] = _ScheduledEvent(
                        self.hass,
                        delay,
                        lambda s=class_starting_sensor: s.async_write_ha_state(),
                    )
                    _LOGGER.debug(
                        "Scheduled class_starting OFF at %s (delay %.1fs)",
                        wodify_class.start_time,
                        delay,
                    )

        # Schedule Block Starting Soon sensor updates (before first class of each block)
        if block_starting_sensor:
            for block in blocks:
                if not block:
                    continue
                first_class = block[0]
                last_class = block[-1]

                # Skip if block already ended
                if last_class.end_time <= now:
                    continue

                # Schedule ON at: block_start - before_minutes
                on_time = first_class.start_time - timedelta(minutes=self.before_class_minutes)
                if on_time > now:
                    delay = (on_time - now).total_seconds()
                    key = f"block_starting_on_{first_class.id}"
                    self._sensor_schedules[key] = _ScheduledEvent(
                        self.hass,
                        delay,
                        lambda s=block_starting_sensor: s.async_write_ha_state(),
                    )
                    _LOGGER.debug("Scheduled block_starting ON at %s (delay %.1fs)", on_time, delay)

                # Schedule OFF at: block_start (first class has started)
                if first_class.start_time > now:
                    delay = (first_class.start_time - now).total_seconds()
                    key = f"block_starting_off_{first_class.id}"
                    self._sensor_schedules[key] = _ScheduledEvent(
                        self.hass,
                        delay,
                        lambda s=block_starting_sensor: s.async_write_ha_state(),
                    )
                    _LOGGER.debug(
                        "Scheduled block_starting OFF at %s (delay %.1fs)",
                        first_class.start_time,
                        delay,
                    )

        # Schedule Block Just Ended sensor updates (after last class of each block)
        if block_ended_sensor:
            for block in blocks:
                if not block:
                    continue
                last_class = block[-1]

                # Schedule ON at: block_end (last class ended)
                if last_class.end_time > now:
                    delay = (last_class.end_time - now).total_seconds()
                    key = f"block_ended_on_{last_class.id}"
                    self._sensor_schedules[key] = _ScheduledEvent(
                        self.hass,
                        delay,
                        lambda s=block_ended_sensor: s.async_write_ha_state(),
                    )
                    _LOGGER.debug(
                        "Scheduled block_ended ON at %s (delay %.1fs)", last_class.end_time, delay
                    )

                # Schedule OFF at: block_end + after_minutes
                off_time = last_class.end_time + timedelta(minutes=self.after_block_minutes)
                if off_time > now:
                    delay = (off_time - now).total_seconds()
                    key = f"block_ended_off_{last_class.id}"
                    self._sensor_schedules[key] = _ScheduledEvent(
                        self.hass,
                        delay,
                        lambda s=block_ended_sensor: s.async_write_ha_state(),
                    )
                    _LOGGER.debug("Scheduled block_ended OFF at %s (delay %.1fs)", off_time, delay)

        # Schedule Class Ongoing sensor updates (during each class)
        if class_ongoing_sensor:
            for wodify_class in classes:
                # Schedule ON at: start_time
                if wodify_class.start_time > now:
                    delay = (wodify_class.start_time - now).total_seconds()
                    key = f"class_ongoing_on_{wodify_class.id}"
                    self._sensor_schedules[key] = _ScheduledEvent(
                        self.hass,
                        delay,
                        lambda s=class_ongoing_sensor: s.async_write_ha_state(),
                    )
                    _LOGGER.debug(
                        "Scheduled class_ongoing ON at %s (delay %.1fs)",
                        wodify_class.start_time,
                        delay,
                    )

                # Schedule OFF at: end_time
                if wodify_class.end_time > now:
                    delay = (wodify_class.end_time - now).total_seconds()
                    key = f"class_ongoing_off_{wodify_class.id}"
                    self._sensor_schedules[key] = _ScheduledEvent(
                        self.hass,
                        delay,
                        lambda s=class_ongoing_sensor: s.async_write_ha_state(),
                    )
                    _LOGGER.debug(
                        "Scheduled class_ongoing OFF at %s (delay %.1fs)",
                        wodify_class.end_time,
                        delay,
                    )

    def _cancel_all_events(self) -> None:
        for handle in list(self._upcoming_events.values()):
            handle.cancel()
        for handle in list(self._block_end_events.values()):
            handle.cancel()
        for handle in list(self._sensor_schedules.values()):
            handle.cancel()
        self._upcoming_events.clear()
        self._block_end_events.clear()
        self._sensor_schedules.clear()

    def cancel_all_events(self) -> None:
        """Cancel all scheduled events (public interface)."""
        self._cancel_all_events()


__all__ = ["WodifyEventManager"]
