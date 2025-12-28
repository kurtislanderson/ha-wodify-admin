"""Data models for the Wodify integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self
from zoneinfo import ZoneInfo

DEFAULT_COACH_NAME = "Not Available"
DEFAULT_LOCATION_NAME = "Unknown"
DEFAULT_PROGRAM_NAME = "Unknown"

# Wodify API returns times in the gym's local timezone
# Default to US Eastern since most Wodify gyms are in the US
DEFAULT_TIMEZONE = ZoneInfo("America/New_York")


def _ensure_timezone(dt: datetime, tz: ZoneInfo | None = None) -> datetime:
    """Ensure a datetime is timezone aware.

    The Wodify API returns times in the gym's local timezone without
    timezone info. We need to attach the correct timezone.
    """
    if dt.tzinfo is None:
        # API returns local gym time, not UTC
        return dt.replace(tzinfo=tz or DEFAULT_TIMEZONE)
    return dt


def _parse_datetime(value: str, tz: ZoneInfo | None = None) -> datetime:
    """Parse the datetime string returned by the Wodify API.

    IMPORTANT: The Wodify API returns times in the gym's local timezone,
    even when using a "Z" suffix. The "Z" is misleading - the times are
    NOT actually UTC. We treat all times as gym local time.
    """
    if not value:
        raise ValueError("Datetime value is required")

    # Strip the misleading "Z" suffix - Wodify sends local times, not UTC
    cleaned = value.replace("Z", "")

    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as err:
        raise ValueError(f"Invalid datetime value: {value}") from err

    # Attach the gym's local timezone
    return _ensure_timezone(parsed, tz)


@dataclass(slots=True)
class WodifyClass:
    """Representation of a class returned by the Wodify API."""

    id: str
    name: str
    start_time: datetime
    end_time: datetime
    coach_name: str = DEFAULT_COACH_NAME
    location_name: str = DEFAULT_LOCATION_NAME
    program_name: str = DEFAULT_PROGRAM_NAME
    max_attendees: int = 0
    current_attendees: int = 0
    is_cancelled: bool = False
    # Attendee breakdown fields (prefixed to avoid confusion with is_cancelled)
    attendees_reserved: int = 0
    attendees_signed_in: int = 0
    attendees_drop_in: int = 0
    attendees_waitlisted: int = 0
    available_slots: int = 0
    attendees_cancelled: int = 0
    attendees_no_show: int = 0
    percent_filled: int = 0
    count_towards_attendance_limits: bool = True

    def __post_init__(self) -> None:
        """Validate the incoming data."""
        if self.max_attendees < 0:
            raise ValueError("max_attendees must be non-negative")
        if self.current_attendees < 0:
            raise ValueError("current_attendees must be non-negative")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must be timezone-aware")

    @property
    def is_full(self) -> bool:
        """Return True if the class is at or above capacity."""
        return self.max_attendees > 0 and self.current_attendees >= self.max_attendees

    @property
    def duration_minutes(self) -> int:
        """Return the class duration in minutes."""
        return int((self.end_time - self.start_time).total_seconds() // 60)

    @classmethod
    def from_api_response(cls, data: Mapping[str, Any]) -> Self:
        """Create a WodifyClass instance from a raw API response."""
        try:
            identifier = str(data["id"])
            name = str(data["name"])
            start_time = _parse_datetime(str(data["start_date_time"]))
            end_time = _parse_datetime(str(data["end_date_time"]))
        except KeyError as err:
            raise ValueError(f"Missing required field: {err.args[0]}") from err

        # Extract coach name(s) from coaches array if available (from GET /classes/{id})
        # or fall back to coach_name field (if present) or default
        coaches = data.get("coaches", [])
        if coaches and isinstance(coaches, list) and len(coaches) > 0:
            # Join all coach names with " & " for multiple coaches
            coach_names = [c.get("coach") for c in coaches if c.get("coach")]
            coach_name = " & ".join(coach_names) if coach_names else DEFAULT_COACH_NAME
        else:
            coach_name = data.get("coach_name") or DEFAULT_COACH_NAME

        location_name = data.get("location") or DEFAULT_LOCATION_NAME
        program_name = data.get("program_name") or DEFAULT_PROGRAM_NAME

        max_attendees = int(data.get("class_limit") or 0)

        # Parse attendee breakdown fields
        attendees_reserved = int(data.get("reserved") or 0)
        attendees_signed_in = int(data.get("signed_in") or 0)
        attendees_drop_in = int(data.get("drop_in") or 0)
        attendees_waitlisted = int(data.get("waitlisted") or 0)
        available_slots = int(data.get("available") or 0)
        attendees_cancelled = int(data.get("cancelled") or 0)
        attendees_no_show = int(data.get("no_show") or 0)
        percent_filled = int(data.get("percent_filled") or 0)
        count_towards_attendance_limits = bool(data.get("count_towards_attendance_limits", True))

        # Calculate current attendees (reserved + signed_in for backwards compat)
        current_attendees = attendees_reserved
        for extra_key in ("signed_in", "checked_in", "attending"):
            extra_value = data.get(extra_key)
            if extra_value:
                current_attendees += int(extra_value)

        cancelled_flag = bool(data.get("is_cancelled", False))
        status_value = str(data.get("status", "")).strip().lower()
        if status_value == "cancelled":
            cancelled_flag = True

        return cls(
            id=identifier,
            name=name,
            start_time=start_time,
            end_time=end_time,
            coach_name=coach_name,
            location_name=location_name,
            program_name=program_name,
            max_attendees=max_attendees,
            current_attendees=current_attendees,
            is_cancelled=cancelled_flag,
            attendees_reserved=attendees_reserved,
            attendees_signed_in=attendees_signed_in,
            attendees_drop_in=attendees_drop_in,
            attendees_waitlisted=attendees_waitlisted,
            available_slots=available_slots,
            attendees_cancelled=attendees_cancelled,
            attendees_no_show=attendees_no_show,
            percent_filled=percent_filled,
            count_towards_attendance_limits=count_towards_attendance_limits,
        )


__all__ = ["WodifyClass"]
