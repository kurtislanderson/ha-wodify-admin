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

        # Link back to the coordinator so cancellation detection can notify us
        coordinator.event_manager = self

        _ensure_async_call_later(hass)

    def schedule_events(self) -> None:
        """Schedule events for all upcoming classes."""

        self._cancel_all_events()

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

    def _cancel_all_events(self) -> None:
        for handle in list(self._upcoming_events.values()):
            handle.cancel()
        for handle in list(self._block_end_events.values()):
            handle.cancel()
        self._upcoming_events.clear()
        self._block_end_events.clear()

    def cancel_all_events(self) -> None:
        """Cancel all scheduled events (public interface)."""
        self._cancel_all_events()


__all__ = ["WodifyEventManager"]
