"""Test data update coordinator."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.wodify.api import ApiAuthError, ApiError
from custom_components.wodify.coordinator import WodifyDataUpdateCoordinator
from custom_components.wodify.models import WodifyClass


@pytest.fixture
def mock_api():
    """Mock API for coordinator tests."""
    return Mock()


@pytest.fixture
def sample_classes():
    """Sample class data for tests."""
    return [
        WodifyClass(
            id="1",
            name="CrossFit",
            start_time=datetime.now(tz=timezone.utc) + timedelta(hours=1),
            end_time=datetime.now(tz=timezone.utc) + timedelta(hours=2),
            coach_name="Coach A",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=10,
            is_cancelled=False,
        ),
        WodifyClass(
            id="2",
            name="Yoga",
            start_time=datetime.now(tz=timezone.utc) + timedelta(hours=3),
            end_time=datetime.now(tz=timezone.utc) + timedelta(hours=4),
            coach_name="Coach B",
            location_name="Uptown",
            program_name="Yoga",
            max_attendees=15,
            current_attendees=12,
            is_cancelled=False,
        ),
    ]


class TestCoordinator:
    """Test WodifyDataUpdateCoordinator."""

    async def test_coordinator_initialization(self, hass, mock_api):
        """Test coordinator initialization."""
        coordinator = WodifyDataUpdateCoordinator(
            hass,
            mock_api,
            ["Downtown"],
            ["CrossFit"],
            5,
        )

        assert coordinator.api == mock_api
        assert coordinator.locations == ["Downtown"]
        assert coordinator.programs == ["CrossFit"]
        assert coordinator.update_interval == timedelta(minutes=5)
        assert coordinator.name == "wodify"

    async def test_coordinator_update_success(self, hass, mock_api, sample_classes):
        """Test successful coordinator update."""
        mock_api.search_classes = AsyncMock(return_value=sample_classes)

        coordinator = WodifyDataUpdateCoordinator(
            hass,
            mock_api,
            ["Downtown", "Uptown"],
            ["CrossFit", "Yoga"],
            5,
        )

        await coordinator.async_refresh()

        assert coordinator.data is not None
        assert len(coordinator.data) == 2
        assert coordinator.last_update_success is True
        assert all(isinstance(cls, WodifyClass) for cls in coordinator.data)

        # Verify sorting by start time
        assert coordinator.data[0].id == "1"
        assert coordinator.data[1].id == "2"

    async def test_coordinator_update_interval(self, hass, mock_api):
        """Test update interval configuration."""
        # Test various intervals
        intervals = [1, 5, 10, 30, 60]

        for minutes in intervals:
            coordinator = WodifyDataUpdateCoordinator(hass, mock_api, [], [], minutes)
            assert coordinator.update_interval == timedelta(minutes=minutes)

    async def test_coordinator_auth_failure(self, hass, mock_api):
        """Test authentication failure handling."""
        mock_api.search_classes = AsyncMock(side_effect=ApiAuthError("Invalid key"))

        coordinator = WodifyDataUpdateCoordinator(hass, mock_api, [], [], 5)

        # async_refresh catches exceptions and sets last_update_success = False
        await coordinator.async_refresh()
        assert coordinator.last_update_success is False

    async def test_coordinator_update_failure(self, hass, mock_api):
        """Test update failure handling."""
        mock_api.search_classes = AsyncMock(side_effect=ApiError("Network error"))

        coordinator = WodifyDataUpdateCoordinator(hass, mock_api, [], [], 5)

        # async_refresh catches exceptions and sets last_update_success = False
        await coordinator.async_refresh()
        assert coordinator.last_update_success is False

    async def test_coordinator_filters_cancelled_classes(self, hass, mock_api):
        """Test coordinator filters out cancelled classes."""
        classes = [
            WodifyClass(
                id="1",
                name="Active Class",
                start_time=datetime.now(tz=timezone.utc) + timedelta(hours=1),
                end_time=datetime.now(tz=timezone.utc) + timedelta(hours=2),
                coach_name="Coach A",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=10,
                is_cancelled=False,
            ),
            WodifyClass(
                id="2",
                name="Cancelled Class",
                start_time=datetime.now(tz=timezone.utc) + timedelta(hours=2),
                end_time=datetime.now(tz=timezone.utc) + timedelta(hours=3),
                coach_name="Coach B",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=0,
                is_cancelled=True,
            ),
            WodifyClass(
                id="3",
                name="Another Active",
                start_time=datetime.now(tz=timezone.utc) + timedelta(hours=3),
                end_time=datetime.now(tz=timezone.utc) + timedelta(hours=4),
                coach_name="Coach C",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=15,
                is_cancelled=False,
            ),
        ]

        mock_api.search_classes = AsyncMock(return_value=classes)

        coordinator = WodifyDataUpdateCoordinator(
            hass, mock_api, ["Downtown"], ["CrossFit"], 5
        )

        await coordinator.async_refresh()

        # Should only include non-cancelled classes
        assert len(coordinator.data) == 2
        assert all(not cls.is_cancelled for cls in coordinator.data)
        assert coordinator.data[0].id == "1"
        assert coordinator.data[1].id == "3"

    async def test_coordinator_detects_newly_cancelled_classes(self, hass, mock_api):
        """Test coordinator detects when classes become cancelled."""
        # Initial data - all active
        initial_classes = [
            WodifyClass(
                id="1",
                name="Class 1",
                start_time=datetime.now(tz=timezone.utc) + timedelta(hours=1),
                end_time=datetime.now(tz=timezone.utc) + timedelta(hours=2),
                coach_name="Coach A",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=10,
                is_cancelled=False,
            ),
            WodifyClass(
                id="2",
                name="Class 2",
                start_time=datetime.now(tz=timezone.utc) + timedelta(hours=2),
                end_time=datetime.now(tz=timezone.utc) + timedelta(hours=3),
                coach_name="Coach B",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=15,
                is_cancelled=False,
            ),
        ]

        mock_api.search_classes = AsyncMock(return_value=initial_classes)

        coordinator = WodifyDataUpdateCoordinator(
            hass, mock_api, ["Downtown"], ["CrossFit"], 5
        )

        # Set up mock event manager
        coordinator.event_manager = Mock()
        coordinator.event_manager.handle_class_cancelled = AsyncMock()

        # First update
        await coordinator.async_refresh()
        assert len(coordinator.data) == 2

        # Update with one cancelled
        updated_classes = [
            initial_classes[0],  # Still active
            WodifyClass(
                id="2",
                name="Class 2",
                start_time=initial_classes[1].start_time,
                end_time=initial_classes[1].end_time,
                coach_name="Coach B",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=0,
                is_cancelled=True,  # Now cancelled
            ),
        ]

        mock_api.search_classes = AsyncMock(return_value=updated_classes)

        # Second update
        await coordinator.async_refresh()

        # Should detect the newly cancelled class
        assert len(coordinator.data) == 1  # Only active class remains
        assert coordinator.data[0].id == "1"

        # Should have notified event manager
        coordinator.event_manager.handle_class_cancelled.assert_called_once()
        call_args = coordinator.event_manager.handle_class_cancelled.call_args[0]
        assert call_args[0] == "2"  # class_id
        assert call_args[1].id == "2"  # cancelled_class

    async def test_coordinator_date_window(self, hass, mock_api):
        """Test coordinator queries appropriate date window."""
        mock_api.search_classes = AsyncMock(return_value=[])

        coordinator = WodifyDataUpdateCoordinator(
            hass, mock_api, ["Downtown"], ["CrossFit"], 5
        )

        with patch("custom_components.wodify.coordinator.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
            await coordinator.async_refresh()

        # Verify API was called with correct date range
        mock_api.search_classes.assert_called_once()
        call_args = mock_api.search_classes.call_args[1]

        # Should query from today to 7 days out
        assert (
            call_args["start_date"].date()
            == datetime(2024, 1, 1, tzinfo=timezone.utc).date()
        )
        assert (
            call_args["end_date"].date()
            == datetime(2024, 1, 8, tzinfo=timezone.utc).date()
        )

    async def test_coordinator_location_program_filters(self, hass, mock_api):
        """Test coordinator passes location and program filters to API."""
        mock_api.search_classes = AsyncMock(return_value=[])

        locations = ["Downtown", "Uptown", "Westside"]
        programs = ["CrossFit", "Yoga", "Olympic Lifting"]

        coordinator = WodifyDataUpdateCoordinator(
            hass, mock_api, locations, programs, 5
        )

        await coordinator.async_refresh()

        # Verify filters were passed to API
        mock_api.search_classes.assert_called_once()
        call_kwargs = mock_api.search_classes.call_args[1]
        assert call_kwargs["location_names"] == locations
        assert call_kwargs["program_names"] == programs

    async def test_coordinator_handles_empty_response(self, hass, mock_api):
        """Test coordinator handles empty class list gracefully."""
        mock_api.search_classes = AsyncMock(return_value=[])

        coordinator = WodifyDataUpdateCoordinator(
            hass, mock_api, ["Downtown"], ["CrossFit"], 5
        )

        await coordinator.async_refresh()

        assert coordinator.data == []
        assert coordinator.last_update_success is True

    async def test_coordinator_preserves_last_data_tracking(self, hass, mock_api):
        """Test coordinator properly tracks last data for cancellation detection."""
        classes = [
            WodifyClass(
                id="1",
                name="Class 1",
                start_time=datetime.now(tz=timezone.utc) + timedelta(hours=1),
                end_time=datetime.now(tz=timezone.utc) + timedelta(hours=2),
                coach_name="Coach A",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=10,
                is_cancelled=False,
            ),
        ]

        mock_api.search_classes = AsyncMock(return_value=classes)

        coordinator = WodifyDataUpdateCoordinator(
            hass, mock_api, ["Downtown"], ["CrossFit"], 5
        )

        # First update
        await coordinator.async_refresh()

        # Verify last_data is populated
        assert "1" in coordinator.last_data
        assert coordinator.last_data["1"].id == "1"

        # Second update with same data
        await coordinator.async_refresh()

        # last_data should still be populated
        assert "1" in coordinator.last_data

    async def test_coordinator_logs_cancellations(self, hass, mock_api, caplog):
        """Test coordinator logs class cancellations."""
        # Initial active class
        active_class = WodifyClass(
            id="1",
            name="Morning CrossFit",
            start_time=datetime.now(tz=timezone.utc) + timedelta(hours=1),
            end_time=datetime.now(tz=timezone.utc) + timedelta(hours=2),
            coach_name="Coach Mike",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=10,
            is_cancelled=False,
        )

        # Cancelled version
        cancelled_class = WodifyClass(
            id="1",
            name="Morning CrossFit",
            start_time=active_class.start_time,
            end_time=active_class.end_time,
            coach_name="Coach Mike",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=0,
            is_cancelled=True,
        )

        coordinator = WodifyDataUpdateCoordinator(
            hass, mock_api, ["Downtown"], ["CrossFit"], 5
        )
        coordinator.event_manager = Mock()

        # First update - active
        mock_api.search_classes = AsyncMock(return_value=[active_class])
        await coordinator.async_refresh()

        # Second update - cancelled
        mock_api.search_classes = AsyncMock(return_value=[cancelled_class])
        await coordinator.async_refresh()

        # Check log message
        assert "Class 1 (Morning CrossFit) was cancelled" in caplog.text
