"""Test event system."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from homeassistant.core import Event

from custom_components.wodify.const import (
    EVENT_CLASS_BLOCK_DONE,
    EVENT_CLASS_CANCELLED,
    EVENT_CLASS_STARTS_SOON,
)
from custom_components.wodify.events import WodifyEventManager
from custom_components.wodify.models import WodifyClass


@pytest.fixture
def sample_classes_for_events():
    """Create sample classes for event testing."""
    base_time = datetime.now(tz=UTC).replace(microsecond=0)
    return [
        WodifyClass(
            id="1",
            name="Morning CrossFit",
            start_time=base_time + timedelta(hours=1),
            end_time=base_time + timedelta(hours=2),
            coach_name="Coach Mike",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=15,
        ),
        WodifyClass(
            id="2",
            name="Back-to-Back CrossFit",
            start_time=base_time + timedelta(hours=2, minutes=5),
            end_time=base_time + timedelta(hours=3, minutes=5),
            coach_name="Coach Sarah",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=10,
        ),
        WodifyClass(
            id="3",
            name="Evening Yoga",
            start_time=base_time + timedelta(hours=6),
            end_time=base_time + timedelta(hours=7),
            coach_name="Coach Amy",
            location_name="Uptown",
            program_name="Yoga",
            max_attendees=15,
            current_attendees=12,
        ),
    ]


@pytest.fixture
def mock_coordinator_with_events(mock_coordinator, sample_classes_for_events):
    """Mock coordinator with event test data."""
    mock_coordinator.data = sample_classes_for_events
    return mock_coordinator


class TestEventManager:
    """Test event manager."""

    async def test_event_manager_initialization(
        self, hass, mock_coordinator_with_events
    ):
        """Test event manager initialization."""
        event_manager = WodifyEventManager(hass, mock_coordinator_with_events, 15, 15)

        assert event_manager.hass == hass
        assert event_manager.coordinator == mock_coordinator_with_events
        assert event_manager.before_class_minutes == 15
        assert event_manager.after_block_minutes == 15
        assert event_manager._upcoming_events == {}
        assert event_manager._block_end_events == {}

        # Verify coordinator linkage
        assert mock_coordinator_with_events.event_manager == event_manager

    async def test_event_scheduling(self, hass, mock_coordinator_with_events):
        """Test event scheduling."""
        event_manager = WodifyEventManager(hass, mock_coordinator_with_events, 15, 15)

        # Mock current time
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime.now(tz=UTC).replace(microsecond=0)
            event_manager.schedule_events()

            # Verify events are scheduled
            assert len(event_manager._upcoming_events) == 3  # One per class
            assert len(event_manager._block_end_events) == 2  # Two blocks

    async def test_class_starts_soon_event(self, hass, mock_coordinator_with_events):
        """Test class starts soon event firing."""
        events_fired = []

        def capture_event(event: Event) -> None:
            events_fired.append(event)

        hass.bus.async_listen(EVENT_CLASS_STARTS_SOON, capture_event)

        event_manager = WodifyEventManager(hass, mock_coordinator_with_events, 15, 15)

        # Simulate event firing
        test_class = mock_coordinator_with_events.data[0]
        await event_manager._fire_class_starts_soon(test_class)

        await hass.async_block_till_done()

        assert len(events_fired) == 1
        event_data = events_fired[0].data
        assert event_data["class_id"] == "1"
        assert event_data["class_name"] == "Morning CrossFit"
        assert event_data["coach"] == "Coach Mike"
        assert event_data["location"] == "Downtown"
        assert event_data["minutes_until_start"] == 15
        assert "start_time" in event_data

    async def test_block_done_event(self, hass, mock_coordinator_with_events):
        """Test block done event firing."""
        events_fired = []

        def capture_event(event: Event) -> None:
            events_fired.append(event)

        hass.bus.async_listen(EVENT_CLASS_BLOCK_DONE, capture_event)

        event_manager = WodifyEventManager(hass, mock_coordinator_with_events, 15, 15)

        # Create a block of classes
        block_classes = mock_coordinator_with_events.data[:2]
        await event_manager._fire_block_done(block_classes)

        await hass.async_block_till_done()

        assert len(events_fired) == 1
        event_data = events_fired[0].data
        assert event_data["last_class_id"] == "2"
        assert event_data["last_class_name"] == "Back-to-Back CrossFit"
        assert event_data["block_duration_minutes"] == 125  # 2 hours + 5 min gap
        assert event_data["block_class_count"] == 2
        assert event_data["minutes_after_end"] == 15

    async def test_update_timing(self, hass, mock_coordinator_with_events):
        """Test updating event timing cancels and reschedules."""
        event_manager = WodifyEventManager(hass, mock_coordinator_with_events, 15, 15)

        # Initial scheduling
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime.now(tz=UTC).replace(microsecond=0)
            event_manager.schedule_events()

        initial_upcoming = list(event_manager._upcoming_events.values())
        initial_blocks = list(event_manager._block_end_events.values())

        # Verify initial tasks are scheduled
        assert all(not task.cancelled() for task in initial_upcoming)
        assert all(not task.cancelled() for task in initial_blocks)

        # Update timing
        event_manager.update_timing(30, 30)

        # Verify timing updated
        assert event_manager.before_class_minutes == 30
        assert event_manager.after_block_minutes == 30

        # Verify old events were cancelled
        assert all(task.cancelled() for task in initial_upcoming)
        assert all(task.cancelled() for task in initial_blocks)

        # Verify new events were scheduled
        assert len(event_manager._upcoming_events) == 3
        assert len(event_manager._block_end_events) == 2
        new_upcoming = list(event_manager._upcoming_events.values())
        new_blocks = list(event_manager._block_end_events.values())
        assert all(not task.cancelled() for task in new_upcoming)
        assert all(not task.cancelled() for task in new_blocks)

    async def test_class_cancelled_event(self, hass):
        """Test class cancelled event firing."""
        events_fired = []

        def capture_event(event: Event) -> None:
            events_fired.append(event)

        hass.bus.async_listen(EVENT_CLASS_CANCELLED, capture_event)

        coordinator = Mock()
        event_manager = WodifyEventManager(hass, coordinator, 15, 15)

        # Create a cancelled class
        cancelled_class = WodifyClass(
            id="123",
            name="Cancelled CrossFit",
            start_time=datetime.now(tz=UTC) + timedelta(hours=1),
            end_time=datetime.now(tz=UTC) + timedelta(hours=2),
            coach_name="Coach Mike",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=0,
            is_cancelled=True,
        )

        await event_manager.handle_class_cancelled("123", cancelled_class)

        await hass.async_block_till_done()

        assert len(events_fired) == 1
        event_data = events_fired[0].data
        assert event_data["class_id"] == "123"
        assert event_data["class_name"] == "Cancelled CrossFit"
        assert event_data["coach"] == "Coach Mike"
        assert event_data["location"] == "Downtown"
        assert "original_start_time" in event_data
        assert "cancellation_time" in event_data

    async def test_handle_class_cancelled_removes_scheduled_event(
        self, hass, mock_coordinator_with_events
    ):
        """Test that cancelling a class removes its scheduled event."""
        event_manager = WodifyEventManager(hass, mock_coordinator_with_events, 15, 15)

        # Schedule events
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime.now(tz=UTC).replace(microsecond=0)
            event_manager.schedule_events()

        # Verify event is scheduled
        assert "1" in event_manager._upcoming_events
        scheduled_task = event_manager._upcoming_events["1"]
        assert not scheduled_task.cancelled()

        # Cancel the class
        cancelled_class = mock_coordinator_with_events.data[0]
        cancelled_class.is_cancelled = True

        await event_manager.handle_class_cancelled("1", cancelled_class)

        # Verify event was removed
        assert "1" not in event_manager._upcoming_events
        assert scheduled_task.cancelled()

    async def test_block_detection(self, hass, mock_coordinator_with_events):
        """Test back-to-back class block detection."""
        event_manager = WodifyEventManager(hass, mock_coordinator_with_events, 15, 15)

        # Mock current time
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime.now(tz=UTC).replace(microsecond=0)
            event_manager.schedule_events()

        # Should detect 2 blocks: classes 1&2 (5 min gap), class 3 alone
        assert len(event_manager._block_end_events) == 2

    async def test_no_events_scheduled_for_past_classes(self, hass, mock_coordinator):
        """Test that events are not scheduled for past classes."""
        past_class = WodifyClass(
            id="past",
            name="Past Class",
            start_time=datetime.now(tz=UTC) - timedelta(hours=2),
            end_time=datetime.now(tz=UTC) - timedelta(hours=1),
            coach_name="Coach",
            location_name="Gym",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=10,
        )

        mock_coordinator.data = [past_class]
        event_manager = WodifyEventManager(hass, mock_coordinator, 15, 15)

        event_manager.schedule_events()

        # No events should be scheduled for past classes
        assert len(event_manager._upcoming_events) == 0
        assert len(event_manager._block_end_events) == 0

    async def test_cancel_all_events(self, hass, mock_coordinator_with_events):
        """Test cancelling all scheduled events."""
        event_manager = WodifyEventManager(hass, mock_coordinator_with_events, 15, 15)

        # Schedule events
        event_manager.schedule_events()

        upcoming_tasks = list(event_manager._upcoming_events.values())
        block_tasks = list(event_manager._block_end_events.values())

        # Verify events are scheduled
        assert len(upcoming_tasks) > 0
        assert len(block_tasks) > 0
        assert all(not task.cancelled() for task in upcoming_tasks)
        assert all(not task.cancelled() for task in block_tasks)

        # Cancel all
        event_manager._cancel_all_events()

        # Verify all cancelled
        assert len(event_manager._upcoming_events) == 0
        assert len(event_manager._block_end_events) == 0
        assert all(task.cancelled() for task in upcoming_tasks)
        assert all(task.cancelled() for task in block_tasks)

    async def test_event_timing_edge_cases(self, hass, mock_coordinator):
        """Test event timing edge cases."""
        # Class starting in exactly 15 minutes
        edge_class = WodifyClass(
            id="edge",
            name="Edge Class",
            start_time=datetime.now(tz=UTC) + timedelta(minutes=15),
            end_time=datetime.now(tz=UTC) + timedelta(minutes=75),
            coach_name="Coach",
            location_name="Gym",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=10,
        )

        mock_coordinator.data = [edge_class]
        event_manager = WodifyEventManager(hass, mock_coordinator, 15, 15)

        # Mock async_call_later to track scheduling
        with patch.object(hass, "async_call_later") as mock_call_later:
            event_manager.schedule_events()

            # Should schedule immediately (0 delay)
            mock_call_later.assert_called()
            delay = mock_call_later.call_args[0][0]
            assert delay <= 1  # Should fire immediately or within 1 second

    async def test_event_manager_logging(
        self, hass, mock_coordinator_with_events, caplog
    ):
        """Test event manager logging."""
        event_manager = WodifyEventManager(hass, mock_coordinator_with_events, 15, 15)

        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime.now(tz=UTC).replace(microsecond=0)
            event_manager.schedule_events()

        # Should log scheduled events
        assert "Scheduled starts_soon for Morning CrossFit" in caplog.text
        assert "Scheduled block_done after Back-to-Back CrossFit" in caplog.text

        # Test cancellation logging
        await event_manager.handle_class_cancelled(
            "1", mock_coordinator_with_events.data[0]
        )
        assert "Cancelled pending starts_soon event for class 1" in caplog.text
        assert "Fired cancellation event for class 1" in caplog.text
