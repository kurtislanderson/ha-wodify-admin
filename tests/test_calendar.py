"""Test calendar entity."""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from custom_components.wodify.calendar import WodifyCalendar, async_setup_entry
from custom_components.wodify.const import DOMAIN
from custom_components.wodify.models import WodifyClass


@pytest.fixture
def calendar_test_data():
    """Create test data for calendar."""
    return [
        WodifyClass(
            id="1",
            name="Morning CrossFit",
            start_time=datetime(2024, 1, 1, 6, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 7, 0, tzinfo=timezone.utc),
            coach_name="Coach Mike",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=15,
        ),
        WodifyClass(
            id="2",
            name="Noon Yoga",
            start_time=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc),
            coach_name="Coach Sarah",
            location_name="Uptown",
            program_name="Yoga",
            max_attendees=15,
            current_attendees=10,
        ),
        WodifyClass(
            id="3",
            name="Evening CrossFit",
            start_time=datetime(2024, 1, 1, 18, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 19, 0, tzinfo=timezone.utc),
            coach_name="Coach John",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=20,
        ),
        WodifyClass(
            id="4",
            name="Next Week Class",
            start_time=datetime(2024, 1, 8, 10, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 8, 11, 0, tzinfo=timezone.utc),
            coach_name="Coach Amy",
            location_name="Downtown",
            program_name="Olympic Lifting",
            max_attendees=12,
            current_attendees=5,
        ),
    ]


class TestCalendar:
    """Test Wodify calendar."""

    async def test_calendar_properties(self, hass, mock_coordinator, mock_config_entry):
        """Test calendar properties."""
        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        assert calendar.unique_id == "test_api_key_calendar"
        assert calendar.name == "Classes"
        assert calendar.should_poll is False
        assert calendar.available is True

    async def test_calendar_event_during_class(
        self, hass, mock_coordinator, mock_config_entry, calendar_test_data
    ):
        """Test calendar event property during a class."""
        mock_coordinator.data = calendar_test_data
        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        # Mock current time during noon yoga
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 30, tzinfo=timezone.utc)
            event = calendar.event

            assert event is not None
            assert event.summary == "Noon Yoga - Coach Sarah"
            assert event.description == "Yoga at Uptown\nAttendees: 10/15"
            assert event.location == "Uptown"
            assert event.start == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
            assert event.end == datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc)

    async def test_calendar_event_no_current_class(
        self, hass, mock_coordinator, mock_config_entry, calendar_test_data
    ):
        """Test calendar event property when no class is ongoing."""
        mock_coordinator.data = calendar_test_data
        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        # Mock current time between classes
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
            event = calendar.event
            assert event is None

    async def test_calendar_get_events(
        self, hass, mock_coordinator, mock_config_entry, calendar_test_data
    ):
        """Test getting calendar events within date range."""
        mock_coordinator.data = calendar_test_data
        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        events = await calendar.async_get_events(
            hass,
            datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 7, 23, 59, tzinfo=timezone.utc),
        )

        # Should only include events within the week (not next week)
        assert len(events) == 3

        # Verify first event
        assert events[0].summary == "Morning CrossFit - Coach Mike"
        assert events[0].start == datetime(2024, 1, 1, 6, 0, tzinfo=timezone.utc)
        assert events[0].location == "Downtown"

        # Verify event descriptions include capacity
        assert "Attendees: 15/20" in events[0].description
        assert "Attendees: 10/15" in events[1].description
        assert "Attendees: 20/20 (FULL)" in events[2].description

    async def test_calendar_filters_by_date_range(
        self, hass, mock_coordinator, mock_config_entry, calendar_test_data
    ):
        """Test calendar properly filters events by date range."""
        mock_coordinator.data = calendar_test_data
        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        # Request only January 1st events
        events = await calendar.async_get_events(
            hass,
            datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 23, 59, tzinfo=timezone.utc),
        )

        assert len(events) == 3  # Only Jan 1 events
        assert all(
            event.start.date() == datetime(2024, 1, 1, tzinfo=timezone.utc).date()
            for event in events
        )

    async def test_calendar_returns_empty_task_list(
        self, hass, mock_coordinator, mock_config_entry
    ):
        """Test calendar returns empty task list to hide todo UI."""
        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        tasks = await calendar.async_get_tasks(hass)
        assert tasks == []

    async def test_calendar_event_description_formats(
        self, hass, mock_coordinator, mock_config_entry
    ):
        """Test different event description formats."""
        # Test with a full class
        full_class = WodifyClass(
            id="1",
            name="Popular Class",
            start_time=datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 1, 18, 0, tzinfo=timezone.utc),
            coach_name="Coach Mike",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=20,
        )

        mock_coordinator.data = [full_class]
        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        events = await calendar.async_get_events(
            hass,
            datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc),
        )

        assert len(events) == 1
        assert "Attendees: 20/20 (FULL)" in events[0].description

    async def test_calendar_no_events(self, hass, mock_coordinator, mock_config_entry):
        """Test calendar with no events."""
        mock_coordinator.data = []
        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        events = await calendar.async_get_events(
            hass,
            datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 7, 23, 59, tzinfo=timezone.utc),
        )

        assert events == []

    async def test_calendar_unavailable_on_coordinator_error(
        self, hass, mock_coordinator, mock_config_entry
    ):
        """Test calendar is unavailable when coordinator has no data."""
        mock_coordinator.data = None
        mock_coordinator.last_update_success = False

        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        assert calendar.available is False
        assert calendar.event is None

    async def test_calendar_device_info(
        self, hass, mock_coordinator, mock_config_entry
    ):
        """Test calendar device info."""
        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        device_info = calendar.device_info
        assert device_info["identifiers"] == {(DOMAIN, mock_config_entry.entry_id)}
        assert device_info["name"] == "Wodify"

    async def test_calendar_setup(self, hass, mock_config_entry, mock_coordinator):
        """Test calendar setup through async_setup_entry."""
        # Set up hass.data with the coordinator
        hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
            }
        }

        async_add_entities = Mock()

        await async_setup_entry(hass, mock_config_entry, async_add_entities)

        # Verify entities were added
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], WodifyCalendar)

    async def test_calendar_handles_timezone_aware_dates(
        self, hass, mock_coordinator, mock_config_entry
    ):
        """Test calendar handles timezone-aware dates properly."""
        # Create timezone-aware test data
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/New_York")
        mock_coordinator.data = [
            WodifyClass(
                id="1",
                name="Timezone Test",
                start_time=datetime(2024, 1, 1, 17, 0, tzinfo=tz),
                end_time=datetime(2024, 1, 1, 18, 0, tzinfo=tz),
                coach_name="Coach Mike",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=10,
            )
        ]

        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        # Request with naive datetimes
        events = await calendar.async_get_events(
            hass,
            datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc),
        )

        assert len(events) == 1
        # Event times should preserve timezone info
        assert events[0].start.tzinfo is not None

    async def test_calendar_event_uid_consistency(
        self, hass, mock_coordinator, mock_config_entry, calendar_test_data
    ):
        """Test calendar events have consistent UIDs."""
        mock_coordinator.data = calendar_test_data
        calendar = WodifyCalendar(mock_coordinator, mock_config_entry)

        events1 = await calendar.async_get_events(
            hass,
            datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 7, 23, 59, tzinfo=timezone.utc),
        )

        events2 = await calendar.async_get_events(
            hass,
            datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 7, 23, 59, tzinfo=timezone.utc),
        )

        # UIDs should be consistent between calls
        for e1, e2 in zip(events1, events2, strict=False):
            assert e1.uid == e2.uid
            assert e1.uid == f"wodify_class_{e1.start.strftime('%Y%m%d%H%M')}"
