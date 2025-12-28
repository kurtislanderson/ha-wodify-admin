"""Test sensor entities."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.wodify.const import DOMAIN
from custom_components.wodify.models import WodifyClass
from custom_components.wodify.sensor import WodifyNextClassSensor, async_setup_entry


@pytest.fixture
def coordinator_with_data(hass, mock_coordinator):  # noqa: ARG001
    """Coordinator with test data."""
    mock_coordinator.data = [
        WodifyClass(
            id="123",
            name="CrossFit",
            start_time=datetime(2024, 1, 1, 17, 30, tzinfo=UTC),
            end_time=datetime(2024, 1, 1, 18, 30, tzinfo=UTC),
            coach_name="Coach Mike",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=15,
        ),
        WodifyClass(
            id="456",
            name="Olympic Lifting",
            start_time=datetime(2024, 1, 2, 9, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 2, 10, 0, tzinfo=UTC),
            coach_name="Coach Sarah",
            location_name="Downtown",
            program_name="Olympic Lifting",
            max_attendees=12,
            current_attendees=12,
        ),
    ]
    return mock_coordinator


class TestNextClassSensor:
    """Test next class sensor."""

    async def test_sensor_properties(
        self,
        hass,  # noqa: ARG002
        coordinator_with_data,
        mock_config_entry,  # noqa: ARG002
    ):
        """Test sensor properties."""
        sensor = WodifyNextClassSensor(coordinator_with_data, mock_config_entry)

        assert sensor.unique_id == "test_api_key_next_class"
        assert sensor.name == "Next Class"
        assert sensor.icon == "mdi:weight-lifter"
        assert sensor.should_poll is False
        assert sensor.available is True

    async def test_sensor_state(self, hass, coordinator_with_data, mock_config_entry):  # noqa: ARG002
        """Test sensor state."""
        sensor = WodifyNextClassSensor(coordinator_with_data, mock_config_entry)

        # Mock current time before class
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
            # Get expected time string using the same timezone conversion as the sensor
            start_local = dt_util.as_local(datetime(2024, 1, 1, 17, 30, tzinfo=UTC))
            expected_time = start_local.strftime("%I:%M %p").lstrip("0")
            assert sensor.native_value == f"CrossFit at {expected_time} with Coach Mike"

    async def test_sensor_state_different_formats(
        self,
        hass,  # noqa: ARG002
        coordinator_with_data,
        mock_config_entry,  # noqa: ARG002
    ):
        """Test sensor state with different time formats."""
        sensor = WodifyNextClassSensor(coordinator_with_data, mock_config_entry)

        # Morning class
        coordinator_with_data.data[0] = WodifyClass(
            id="789",
            name="Morning CrossFit",
            start_time=datetime(2024, 1, 1, 6, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 1, 7, 0, tzinfo=UTC),
            coach_name="Coach Tim",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=10,
        )

        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 5, 0, tzinfo=UTC)
            # Get expected time string using the same timezone conversion as the sensor
            start_local = dt_util.as_local(datetime(2024, 1, 1, 6, 0, tzinfo=UTC))
            expected_time = start_local.strftime("%I:%M %p").lstrip("0")
            assert sensor.native_value == f"Morning CrossFit at {expected_time} with Coach Tim"

    async def test_sensor_attributes(
        self,
        hass,  # noqa: ARG002
        coordinator_with_data,
        mock_config_entry,  # noqa: ARG002
    ):
        """Test sensor attributes."""
        sensor = WodifyNextClassSensor(coordinator_with_data, mock_config_entry)

        # Mock current time to be before the test classes
        with patch("custom_components.wodify.sensor.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
            attrs = sensor.extra_state_attributes

        assert attrs["class_id"] == "123"
        assert attrs["class_name"] == "CrossFit"
        assert attrs["coach"] == "Coach Mike"
        assert attrs["location"] == "Downtown"
        assert attrs["program"] == "CrossFit"
        assert attrs["start_time"] == "2024-01-01T17:30:00"
        assert attrs["end_time"] == "2024-01-01T18:30:00"
        assert attrs["duration_minutes"] == 60
        assert attrs["capacity"] == "15/20"
        assert attrs["is_full"] is False

    async def test_sensor_attributes_full_class(
        self,
        hass,  # noqa: ARG002
        coordinator_with_data,
        mock_config_entry,  # noqa: ARG002
    ):
        """Test sensor attributes when class is full."""
        sensor = WodifyNextClassSensor(coordinator_with_data, mock_config_entry)

        # Use the second class which is full
        coordinator_with_data.data = [coordinator_with_data.data[1]]

        # Mock current time to be before the test class (Jan 2 class)
        with patch("custom_components.wodify.sensor.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 2, 6, 0, tzinfo=UTC)
            attrs = sensor.extra_state_attributes

        assert attrs["capacity"] == "12/12"
        assert attrs["is_full"] is True

    async def test_sensor_no_classes(self, hass, mock_coordinator, mock_config_entry):  # noqa: ARG002
        """Test sensor with no upcoming classes."""
        mock_coordinator.data = []
        sensor = WodifyNextClassSensor(mock_coordinator, mock_config_entry)

        assert sensor.native_value == "No upcoming classes"
        assert sensor.extra_state_attributes == {}

    async def test_sensor_skips_past_classes(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,  # noqa: ARG002
    ):
        """Test sensor skips classes that have already started."""
        mock_coordinator.data = [
            WodifyClass(
                id="1",
                name="Past Class",
                start_time=datetime(2024, 1, 1, 10, 0, tzinfo=UTC),
                end_time=datetime(2024, 1, 1, 11, 0, tzinfo=UTC),
                coach_name="Coach A",
                location_name="Gym",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=10,
            ),
            WodifyClass(
                id="2",
                name="Future Class",
                start_time=datetime(2024, 1, 1, 18, 0, tzinfo=UTC),
                end_time=datetime(2024, 1, 1, 19, 0, tzinfo=UTC),
                coach_name="Coach B",
                location_name="Gym",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=10,
            ),
        ]

        sensor = WodifyNextClassSensor(mock_coordinator, mock_config_entry)

        # Mock current time between classes
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
            assert "Future Class" in sensor.native_value
            assert sensor.extra_state_attributes["class_id"] == "2"

    async def test_sensor_unavailable_on_coordinator_error(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,  # noqa: ARG002
    ):
        """Test sensor is unavailable when coordinator has no data."""
        mock_coordinator.data = None
        mock_coordinator.last_update_success = False

        sensor = WodifyNextClassSensor(mock_coordinator, mock_config_entry)

        assert sensor.available is False
        assert sensor.native_value is None

    async def test_sensor_device_info(self, hass, mock_coordinator, mock_config_entry):  # noqa: ARG002
        """Test sensor device info."""
        sensor = WodifyNextClassSensor(mock_coordinator, mock_config_entry)

        device_info = sensor.device_info
        assert device_info["identifiers"] == {(DOMAIN, mock_config_entry.entry_id)}
        assert device_info["name"] == "Wodify"
        assert device_info["manufacturer"] == "Wodify"
        assert device_info["model"] == "Gym Schedule"

    async def test_sensor_entity_registry_settings(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,  # noqa: ARG002
    ):
        """Test sensor entity registry settings."""
        sensor = WodifyNextClassSensor(mock_coordinator, mock_config_entry)

        # Regular sensor should be enabled by default
        assert (
            not hasattr(sensor, "entity_registry_enabled_default")
            or sensor.entity_registry_enabled_default is True
        )

    async def test_debug_sensor_disabled_by_default(
        self, hass, mock_coordinator, mock_config_entry
    ):
        """Test debug sensors are disabled by default for recorder efficiency."""
        # This would be implemented when we create debug sensors
        # For now, we'll just verify the pattern is understood

    async def test_sensor_setup(self, hass, mock_config_entry, mock_coordinator):
        """Test sensor setup through async_setup_entry."""
        # Set up runtime data using hass.data pattern (not runtime_data)
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
        assert len(entities) == 3  # Next Class + Current Class + API Status
        assert isinstance(entities[0], WodifyNextClassSensor)

    async def test_sensor_state_updates_on_coordinator_update(
        self,
        hass,  # noqa: ARG002
        coordinator_with_data,
        mock_config_entry,  # noqa: ARG002
    ):
        """Test sensor updates when coordinator data changes."""
        sensor = WodifyNextClassSensor(coordinator_with_data, mock_config_entry)

        # Update coordinator data (simulates what coordinator does on refresh)
        coordinator_with_data.data = [
            WodifyClass(
                id="999",
                name="New Class",
                start_time=datetime(2024, 1, 1, 20, 0, tzinfo=UTC),
                end_time=datetime(2024, 1, 1, 21, 0, tzinfo=UTC),
                coach_name="Coach New",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=5,
            )
        ]

        # Mock current time to be before the test class
        with patch("custom_components.wodify.sensor.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
            # State should reflect new data (sensor reads from coordinator.data directly)
            assert "New Class" in sensor.native_value
            assert sensor.extra_state_attributes["coach"] == "Coach New"
