"""Coordinators and helpers for the Wodify integration."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import ApiAuthError, ApiError, WodifyAPI
from .const import BLOCK_GAP_THRESHOLD, CACHE_MAX_AGE_HOURS, DOMAIN
from .models import DEFAULT_COACH_NAME, WodifyClass

_LOGGER = logging.getLogger(__name__)


def _coerce_datetime(value: Any) -> datetime:
    """Best effort conversion to a datetime object."""
    if isinstance(value, datetime):
        return value
    raise TypeError("Value must be a datetime")


def _get_value(item: Any, getter: Callable[[Any], Any], *fallbacks: str) -> Any:
    """Return attribute or dictionary value using provided fallbacks."""
    if isinstance(item, dict):
        for key in fallbacks:
            if key in item:
                return item[key]
        return None
    for key in fallbacks:
        if hasattr(item, key):
            return getattr(item, key)
    return getter(item)


def detect_class_blocks(
    classes: Iterable[Any], gap_threshold: int | None = None
) -> list[list[Any]]:
    """Group back-to-back classes into contiguous blocks.

    ``gap_threshold`` is the number of minutes between two classes that still
    counts as the same block. Pass the configured value from the config entry;
    it falls back to :data:`BLOCK_GAP_THRESHOLD` when omitted.

    The helper accepts either dictionaries (used by the light-weight coordinator
    tests) or :class:`WodifyClass` instances from the main coordinator.
    """

    try:
        threshold = BLOCK_GAP_THRESHOLD if gap_threshold is None else int(gap_threshold)
    except (TypeError, ValueError):
        # A malformed option must not break block detection entirely.
        threshold = BLOCK_GAP_THRESHOLD

    # Normalise and filter cancelled classes up-front
    active_items: list[Any] = []
    for entry in classes:
        is_cancelled = bool(_get_value(entry, lambda _: False, "is_cancelled", "cancelled"))
        if is_cancelled:
            continue
        start = _get_value(entry, lambda _: None, "start", "start_time")
        end = _get_value(entry, lambda _: None, "end", "end_time")
        if start is None or end is None:
            _LOGGER.debug("Skipping class without start/end: %s", entry)
            continue
        active_items.append(entry)

    if not active_items:
        return []

    active_items.sort(
        key=lambda item: _get_value(item, lambda _: datetime.min, "start", "start_time")
    )

    blocks: list[list[Any]] = []
    current_block: list[Any] = [active_items[0]]
    block_end = _coerce_datetime(
        _get_value(active_items[0], lambda _: datetime.min, "end", "end_time")
    )

    for current in active_items[1:]:
        current_start = _coerce_datetime(
            _get_value(current, lambda _: datetime.max, "start", "start_time")
        )
        current_end = _coerce_datetime(
            _get_value(current, lambda _: datetime.max, "end", "end_time")
        )

        gap_minutes = (current_start - block_end).total_seconds() / 60

        # Start a new block when the next class is separated from the current
        # block by more than the configured threshold, either because there is a
        # large gap or the classes overlap by a significant amount (e.g. classes
        # running in parallel in different locations).
        if gap_minutes > threshold or gap_minutes < -threshold:
            blocks.append(current_block)
            current_block = [current]
            block_end = current_end
            continue

        current_block.append(current)
        if current_end > block_end:
            block_end = current_end

    blocks.append(current_block)
    return blocks


class WodifyDataUpdateCoordinator(DataUpdateCoordinator[list[WodifyClass]]):
    """Coordinator that fetches classes through the API client."""

    # Maximum number of upcoming classes to enrich with coach info
    MAX_COACH_ENRICHMENT = 10

    def __init__(
        self,
        hass: HomeAssistant,
        api: WodifyAPI,
        locations: list[str],
        programs: list[str],
        update_interval: int,
        exclude_private_training: bool = True,
        block_gap_minutes: int = BLOCK_GAP_THRESHOLD,
    ) -> None:
        """Initialise the coordinator."""

        self.api = api
        self.locations = locations
        self.programs = programs
        self.exclude_private_training = exclude_private_training
        self.block_gap_minutes = int(block_gap_minutes)
        self.event_manager: Any | None = None
        self.last_data: dict[str, WodifyClass] = {}

        # Coach names resolved per class id (search endpoint omits coaches, so
        # we backfill from GET /classes/{id} and remember the result across
        # refreshes). Survives the search wipe and covers in-progress classes.
        self._coach_cache: dict[str, str] = {}

        # Cache for API status tracking
        self._cached_data: list[WodifyClass] = []
        self._api_connected: bool = True
        self._last_error: str | None = None
        self._last_successful_update: datetime | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=update_interval),
        )

    @property
    def api_connected(self) -> bool:
        """Return True if API is connected and responding."""
        return self._api_connected

    @property
    def last_error(self) -> str | None:
        """Return the last error message if API is disconnected."""
        return self._last_error

    @property
    def last_successful_update(self) -> datetime | None:
        """Return when data was last successfully fetched."""
        return self._last_successful_update

    @property
    def cached_data(self) -> list[WodifyClass]:
        """Return cached data (used when API is down)."""
        return self._cached_data

    async def _enrich_with_coaches(self, classes: list[WodifyClass]) -> list[WodifyClass]:
        """Backfill coach names that the /classes/search endpoint omits.

        Search never returns coaches, so every refresh wipes them back to
        DEFAULT_COACH_NAME. We resolve coaches via GET /classes/{id} and cache
        them per class id so the value survives refreshes (including after a
        class has already started). Today's classes are re-fetched every refresh
        because coaches can change same-day; future classes are fetched once
        (capped) to populate the next-day preview, then served from cache.
        """
        index_by_id = {c.id: i for i, c in enumerate(classes)}

        # 1. Restore previously-resolved coaches wiped by the search response.
        for cls in classes:
            if cls.coach_name == DEFAULT_COACH_NAME and cls.id in self._coach_cache:
                cls.coach_name = self._coach_cache[cls.id]

        # 2. Decide what to (re)fetch. The search window starts at midnight
        #    today, so every class is today or later.
        today = dt_util.now().date()
        today_classes = [
            c for c in classes if not c.is_cancelled and c.start_time.date() == today
        ]
        future_uncached = sorted(
            (
                c
                for c in classes
                if not c.is_cancelled
                and c.start_time.date() > today
                and c.id not in self._coach_cache
            ),
            key=lambda c: c.start_time,
        )
        to_enrich = today_classes + future_uncached[: self.MAX_COACH_ENRICHMENT]

        enriched_ids: set[str] = set()
        for cls in to_enrich:
            try:
                full_data = await self.api.get_class(cls.id)
            except Exception as err:  # noqa: BLE001 - never let one class break the refresh
                _LOGGER.debug("Failed to enrich class %s with coach: %s", cls.id, err)
                continue
            if not full_data or "coaches" not in full_data:
                continue
            # Parse only to extract the coach name; keep the search object (it
            # already carries fresh attendee data) and mutate coach_name in place.
            coach_name = WodifyClass.from_api_response(full_data).coach_name
            if coach_name != DEFAULT_COACH_NAME:
                self._coach_cache[cls.id] = coach_name
            else:
                # Coach removed in Wodify: drop any stale cached value.
                self._coach_cache.pop(cls.id, None)
            idx = index_by_id.get(cls.id)
            if idx is not None:
                classes[idx].coach_name = coach_name
                enriched_ids.add(cls.id)

        # Prune cache entries for classes that have rolled out of the window.
        live_ids = {c.id for c in classes}
        self._coach_cache = {
            cid: name for cid, name in self._coach_cache.items() if cid in live_ids
        }

        if enriched_ids:
            _LOGGER.debug("Enriched %d classes with coach info", len(enriched_ids))

        return classes

    async def _async_update_data(self) -> list[WodifyClass]:
        """Fetch classes from the Wodify API and detect cancellations."""

        # Start from midnight today to include all of today's classes
        start_date = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)

        try:
            classes = await self.api.search_classes(
                start_date=start_date,
                end_date=end_date,
                location_names=self.locations if self.locations else None,
                program_names=self.programs if self.programs else None,
            )
            # API call succeeded - update status
            self._api_connected = True
            self._last_error = None
            self._last_successful_update = dt_util.now()
        except ApiAuthError as err:
            self._api_connected = False
            self._last_error = "Authentication failed"
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except ApiError as err:
            self._api_connected = False
            self._last_error = str(err)
            # Return cached data if available and not too old
            if self._cached_data and self._last_successful_update:
                cache_age = dt_util.now() - self._last_successful_update
                max_age = timedelta(hours=CACHE_MAX_AGE_HOURS)
                if cache_age < max_age:
                    _LOGGER.warning(
                        "API error, using cached data (age: %s): %s",
                        cache_age,
                        err,
                    )
                    return self._cached_data
                _LOGGER.warning(
                    "API error and cached data too old (%s > %s hours): %s",
                    cache_age,
                    CACHE_MAX_AGE_HOURS,
                    err,
                )
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        # Sort classes chronologically for consistent behaviour
        classes.sort(key=lambda cls: cls.start_time)

        # Enrich upcoming classes with coach information
        classes = await self._enrich_with_coaches(classes)

        cancellations: list[WodifyClass] = []
        active_classes: list[WodifyClass] = []

        for cls in classes:
            previous = self.last_data.get(cls.id)
            if cls.is_cancelled:
                if previous and not previous.is_cancelled:
                    cancellations.append(cls)
                continue
            # Filter out private training classes if configured
            if self.exclude_private_training and "private training" in cls.name.lower():
                continue
            active_classes.append(cls)

        # Track the most recent state for cancellation detection on next refresh
        self.last_data = {cls.id: cls for cls in classes}

        if cancellations:
            for cancelled in cancellations:
                _LOGGER.info("Class %s (%s) was cancelled", cancelled.id, cancelled.name)
                if self.event_manager is not None:
                    await self.event_manager.handle_class_cancelled(cancelled.id, cancelled)

        # Cache successful data for use when API is down
        self._cached_data = active_classes

        return active_classes

    async def async_set_filters(self, locations: list[str], programs: list[str]) -> None:
        """Update location and program filters then refresh."""

        self.locations = locations
        self.programs = programs
        await self.async_request_refresh()
