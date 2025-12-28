"""Performance tests."""

import asyncio
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.wodify.models import WodifyClass


@pytest.fixture
def large_dataset():
    """Create a large dataset for performance testing."""
    classes = []
    base_time = datetime.now(tz=UTC)

    # Generate 500 classes over 7 days (typical weekly schedule)
    for day in range(7):
        for hour in range(6, 21):  # 6 AM to 9 PM
            for slot in range(0, 60, 30):  # Every 30 minutes
                class_id = f"{day}_{hour}_{slot}"
                start_time = base_time + timedelta(days=day, hours=hour, minutes=slot)
                classes.append(
                    WodifyClass(
                        id=class_id,
                        name=f"Class {class_id}",
                        start_time=start_time,
                        end_time=start_time + timedelta(hours=1),
                        coach_name=f"Coach {hour % 5}",
                        location_name=f"Location {day % 3}",
                        program_name=f"Program {hour % 3}",
                        max_attendees=20,
                        current_attendees=(day * hour) % 20,
                    )
                )

    return classes


class TestPerformance:
    """Test performance requirements."""

    async def test_update_performance(self, hass, mock_config_entry, large_dataset):  # noqa: ARG002
        """Test coordinator update performance with large dataset."""
        from custom_components.wodify.api import WodifyAPI
        from custom_components.wodify.coordinator import WodifyDataUpdateCoordinator

        # Mock API to return large dataset
        mock_api = Mock(spec=WodifyAPI)
        mock_api.search_classes = AsyncMock(return_value=large_dataset)

        coordinator = WodifyDataUpdateCoordinator(
            hass,
            mock_api,
            ["Location 1", "Location 2"],
            ["Program 1", "Program 2"],
            5,
        )

        # Measure update time
        start_time = time.time()
        result = await coordinator._async_update_data()
        end_time = time.time()

        update_duration = end_time - start_time

        # Should complete within 5 seconds (requirement)
        assert update_duration < 5.0, f"Update took {update_duration:.2f}s, expected < 5s"

        # Verify data was processed (returned, not coordinator.data)
        assert len(result) > 0
        assert all(not cls.is_cancelled for cls in result)

    async def test_memory_usage(self, hass, mock_config_entry, large_dataset):  # noqa: ARG002
        """Test memory usage stays reasonable with large dataset."""
        import sys

        from custom_components.wodify.api import WodifyAPI
        from custom_components.wodify.coordinator import WodifyDataUpdateCoordinator

        def get_slot_values(obj):
            """Get values from __slots__ instead of __dict__."""
            if hasattr(obj, "__slots__"):
                return [getattr(obj, slot, None) for slot in obj.__slots__]
            return []

        # Get initial memory baseline
        initial_size = 0
        for obj in large_dataset:
            initial_size += sys.getsizeof(obj)
            initial_size += sum(sys.getsizeof(v) for v in get_slot_values(obj) if v is not None)

        # Set up coordinator with large dataset
        mock_api = Mock(spec=WodifyAPI)
        mock_api.search_classes = AsyncMock(return_value=large_dataset)

        coordinator = WodifyDataUpdateCoordinator(
            hass,
            mock_api,
            ["Location 1", "Location 2", "Location 3"],
            ["Program 1", "Program 2", "Program 3"],
            5,
        )

        result = await coordinator._async_update_data()

        # Estimate memory usage (use result, not coordinator.data)
        coordinator_size = sys.getsizeof(result)
        for cls in result:
            coordinator_size += sys.getsizeof(cls)
            coordinator_size += sum(sys.getsizeof(v) for v in get_slot_values(cls) if v is not None)

        # Convert to MB
        memory_mb = coordinator_size / 1024 / 1024

        # Should use less than 50MB for large dataset (requirement)
        assert memory_mb < 50, f"Memory usage {memory_mb:.2f}MB, expected < 50MB"

    async def test_event_scheduling_performance(self, hass, mock_coordinator, large_dataset):
        """Test event scheduling performance with many classes."""
        from custom_components.wodify.events import WodifyEventManager

        mock_coordinator.data = large_dataset
        event_manager = WodifyEventManager(hass, mock_coordinator, 15, 15)

        # Measure scheduling time
        start_time = time.time()
        event_manager.schedule_events()
        end_time = time.time()

        scheduling_duration = end_time - start_time

        # Should complete quickly even with many classes
        assert scheduling_duration < 1.0, f"Scheduling took {scheduling_duration:.2f}s"

        # Verify events were scheduled (only for future classes)
        assert len(event_manager._upcoming_events) > 0
        assert len(event_manager._block_end_events) > 0

    async def test_entity_update_performance(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        large_dataset,  # noqa: ARG002
    ):
        """Test entity state update performance."""
        from custom_components.wodify.sensor import WodifyNextClassSensor

        mock_coordinator.data = large_dataset
        sensor = WodifyNextClassSensor(mock_coordinator, Mock(unique_id="test"))

        # Measure state calculation time
        iterations = 100
        start_time = time.time()

        for _ in range(iterations):
            _ = sensor.native_value
            _ = sensor.extra_state_attributes

        end_time = time.time()

        avg_time = (end_time - start_time) / iterations

        # State updates should be fast
        assert avg_time < 0.01, f"Average state update took {avg_time * 1000:.2f}ms"

    async def test_concurrent_update_performance(self, hass, mock_config_entry):  # noqa: ARG002
        """Test performance with concurrent operations."""
        from custom_components.wodify.api import WodifyAPI
        from custom_components.wodify.coordinator import WodifyDataUpdateCoordinator

        # Create multiple coordinators
        coordinators = []
        for i in range(5):
            mock_api = Mock(spec=WodifyAPI)
            mock_api.search_classes = AsyncMock(
                return_value=[
                    WodifyClass(
                        id=f"class_{i}_{j}",
                        name=f"Class {i}-{j}",
                        start_time=datetime.now(tz=UTC) + timedelta(hours=j),
                        end_time=datetime.now(tz=UTC) + timedelta(hours=j + 1),
                        coach_name=f"Coach {i}",
                        location_name=f"Location {i}",
                        program_name="CrossFit",
                        max_attendees=20,
                        current_attendees=10,
                    )
                    for j in range(20)
                ]
            )

            coordinator = WodifyDataUpdateCoordinator(
                hass,
                mock_api,
                [f"Location {i}"],
                ["CrossFit"],
                5,
            )
            coordinators.append(coordinator)

        # Run concurrent updates
        start_time = time.time()
        await asyncio.gather(*[coordinator._async_update_data() for coordinator in coordinators])
        end_time = time.time()

        total_duration = end_time - start_time

        # Concurrent updates should complete efficiently
        assert total_duration < 3.0, f"Concurrent updates took {total_duration:.2f}s"

    async def test_api_debouncer_performance(self, hass):
        """Test API rate limiter delays concurrent requests appropriately."""
        from custom_components.wodify.api import WodifyAPI

        # Create mock session
        session = Mock()

        api = WodifyAPI("test_key", session, hass)

        # Time how long it takes to make multiple serial rate limit calls
        # With debouncing, this should take at least debounce_time * (call_count - 1)
        call_count = 3
        start_time = time.time()

        for _ in range(call_count):
            try:  # noqa: SIM105
                await api._apply_rate_limit()
            except Exception:
                pass  # We just want to test the rate limiter timing

        end_time = time.time()
        duration = end_time - start_time

        # Rate limiter should enforce minimum delay between calls
        # With 60 calls/min rate limit, delay is ~1 second per call
        # For 3 calls, we should see ~2 seconds of delay
        min_expected_delay = api._DEFAULT_DEBOUNCE * (call_count - 1)
        assert duration >= min_expected_delay * 0.9, (
            f"Expected at least {min_expected_delay}s delay, got {duration}s"
        )

    async def test_state_history_performance(self, hass, mock_coordinator):  # noqa: ARG002
        """Test performance with state calculation across many data changes."""
        from custom_components.wodify.sensor import WodifyNextClassSensor

        # Create mock config entry with entry_id
        mock_entry = Mock()
        mock_entry.unique_id = "test"
        mock_entry.entry_id = "test_entry_id"

        # Simulate many state calculations
        sensor = WodifyNextClassSensor(mock_coordinator, mock_entry)

        state_calculations = 0
        start_time = time.time()

        for i in range(100):
            mock_coordinator.data = [
                WodifyClass(
                    id=f"class_{i}",
                    name=f"Class {i}",
                    start_time=datetime.now(tz=UTC) + timedelta(hours=i),
                    end_time=datetime.now(tz=UTC) + timedelta(hours=i + 1),
                    coach_name="Coach",
                    location_name="Gym",
                    program_name="CrossFit",
                    max_attendees=20,
                    current_attendees=i % 20,
                )
            ]

            # Calculate state and attributes (without triggering HA state update)
            _ = sensor.native_value
            _ = sensor.extra_state_attributes
            state_calculations += 1

        end_time = time.time()
        duration = end_time - start_time

        # State calculations should be efficient
        avg_time = duration / state_calculations
        assert avg_time < 0.01, f"Average state calculation took {avg_time * 1000:.2f}ms"

    async def test_calendar_query_performance(self, hass, mock_coordinator, large_dataset):
        """Test calendar entity query performance."""
        from custom_components.wodify.calendar import WodifyCalendar

        mock_coordinator.data = large_dataset
        calendar = WodifyCalendar(mock_coordinator, Mock(unique_id="test"))

        # Query different date ranges
        queries = [
            (
                datetime.now(tz=UTC),
                datetime.now(tz=UTC) + timedelta(days=1),
            ),  # 1 day
            (
                datetime.now(tz=UTC),
                datetime.now(tz=UTC) + timedelta(days=3),
            ),  # 3 days
            (
                datetime.now(tz=UTC),
                datetime.now(tz=UTC) + timedelta(days=7),
            ),  # 7 days
        ]

        for start_date, end_date in queries:
            start_time = time.time()
            events = await calendar.async_get_events(hass, start_date, end_date)
            end_time = time.time()

            query_duration = end_time - start_time

            # Calendar queries should be fast
            assert query_duration < 0.1, (
                f"Query took {query_duration:.2f}s for {len(events)} events"
            )
