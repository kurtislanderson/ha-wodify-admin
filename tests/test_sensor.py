"""Test sensor entities."""

from datetime import UTC, datetime
from unittest.mock import Mock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.wodify.const import DOMAIN
from custom_components.wodify.models import WodifyClass
from custom_components.wodify.sensor import (
    WodifyNextClassSensor,
    WodifySettingsSensor,
    WodifyTodaysClassesSensor,
    async_setup_entry,
)


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
        # Next Class + Current Class + API Status + Today's Classes + Settings
        assert len(entities) == 5
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


class TestTodaysClassesSensor:
    """Test today's classes sensor."""

    async def test_sensor_properties(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
    ):
        """Test sensor properties."""
        mock_coordinator.data = []
        sensor = WodifyTodaysClassesSensor(mock_coordinator, mock_config_entry)

        assert sensor.unique_id == "test_api_key_todays_classes"
        assert sensor.name == "Today's Classes"
        assert sensor.icon == "mdi:calendar-today"
        assert sensor.should_poll is False

    async def test_sensor_no_classes_today(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
    ):
        """Test sensor when no classes today."""
        mock_coordinator.data = []
        sensor = WodifyTodaysClassesSensor(mock_coordinator, mock_config_entry)

        with patch("custom_components.wodify.sensor.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
            assert sensor.native_value == "No classes today"
            assert sensor.extra_state_attributes["class_count"] == 0
            assert sensor.extra_state_attributes["classes"] == []

    async def test_sensor_one_class_today(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
    ):
        """Test sensor with one class today."""
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
        ]
        sensor = WodifyTodaysClassesSensor(mock_coordinator, mock_config_entry)

        with patch("custom_components.wodify.sensor.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
            assert sensor.native_value == "1 class today"
            attrs = sensor.extra_state_attributes
            assert attrs["class_count"] == 1
            assert len(attrs["classes"]) == 1
            assert attrs["classes"][0]["name"] == "CrossFit"
            assert attrs["classes"][0]["coach"] == "Coach Mike"

    async def test_sensor_multiple_classes_today(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
    ):
        """Test sensor with multiple classes today."""
        mock_coordinator.data = [
            WodifyClass(
                id="123",
                name="Morning CrossFit",
                start_time=datetime(2024, 1, 1, 6, 0, tzinfo=UTC),
                end_time=datetime(2024, 1, 1, 7, 0, tzinfo=UTC),
                coach_name="Coach Mike",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=15,
            ),
            WodifyClass(
                id="456",
                name="Noon CrossFit",
                start_time=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
                end_time=datetime(2024, 1, 1, 13, 0, tzinfo=UTC),
                coach_name="Coach Sarah",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=10,
            ),
            WodifyClass(
                id="789",
                name="Evening CrossFit",
                start_time=datetime(2024, 1, 1, 17, 30, tzinfo=UTC),
                end_time=datetime(2024, 1, 1, 18, 30, tzinfo=UTC),
                coach_name="Coach Tim",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=18,
            ),
        ]
        sensor = WodifyTodaysClassesSensor(mock_coordinator, mock_config_entry)

        with patch("custom_components.wodify.sensor.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 5, 0, tzinfo=UTC)
            assert sensor.native_value == "3 classes today"
            attrs = sensor.extra_state_attributes
            assert attrs["class_count"] == 3
            assert len(attrs["classes"]) == 3
            # Verify classes are sorted by start time
            assert attrs["classes"][0]["name"] == "Morning CrossFit"
            assert attrs["classes"][1]["name"] == "Noon CrossFit"
            assert attrs["classes"][2]["name"] == "Evening CrossFit"

    async def test_sensor_filters_other_days(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
    ):
        """Test sensor only shows today's classes."""
        mock_coordinator.data = [
            WodifyClass(
                id="123",
                name="Today CrossFit",
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
                name="Tomorrow CrossFit",
                start_time=datetime(2024, 1, 2, 17, 30, tzinfo=UTC),
                end_time=datetime(2024, 1, 2, 18, 30, tzinfo=UTC),
                coach_name="Coach Sarah",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=10,
            ),
        ]
        sensor = WodifyTodaysClassesSensor(mock_coordinator, mock_config_entry)

        with patch("custom_components.wodify.sensor.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
            assert sensor.native_value == "1 class today"
            attrs = sensor.extra_state_attributes
            assert attrs["class_count"] == 1
            assert attrs["classes"][0]["name"] == "Today CrossFit"

    async def test_sensor_filters_cancelled(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
    ):
        """Test sensor filters out cancelled classes."""
        mock_coordinator.data = [
            WodifyClass(
                id="123",
                name="Active CrossFit",
                start_time=datetime(2024, 1, 1, 17, 30, tzinfo=UTC),
                end_time=datetime(2024, 1, 1, 18, 30, tzinfo=UTC),
                coach_name="Coach Mike",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=15,
                is_cancelled=False,
            ),
            WodifyClass(
                id="456",
                name="Cancelled CrossFit",
                start_time=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
                end_time=datetime(2024, 1, 1, 13, 0, tzinfo=UTC),
                coach_name="Coach Sarah",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=0,
                is_cancelled=True,
            ),
        ]
        sensor = WodifyTodaysClassesSensor(mock_coordinator, mock_config_entry)

        with patch("custom_components.wodify.sensor.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)
            assert sensor.native_value == "1 class today"
            attrs = sensor.extra_state_attributes
            assert attrs["class_count"] == 1
            assert attrs["classes"][0]["name"] == "Active CrossFit"

    async def test_sensor_class_attributes(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
    ):
        """Test sensor class attributes contain all expected fields."""
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
        ]
        sensor = WodifyTodaysClassesSensor(mock_coordinator, mock_config_entry)

        with patch("custom_components.wodify.sensor.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
            attrs = sensor.extra_state_attributes
            class_data = attrs["classes"][0]

            assert class_data["id"] == "123"
            assert class_data["name"] == "CrossFit"
            assert class_data["coach"] == "Coach Mike"
            assert class_data["location"] == "Downtown"
            assert class_data["program"] == "CrossFit"
            assert class_data["start_time"] == "2024-01-01T17:30:00"
            assert class_data["end_time"] == "2024-01-01T18:30:00"
            assert "time" in class_data  # Formatted short time
            assert class_data["duration_minutes"] == 60
            assert class_data["capacity"] == "15/20"
            assert class_data["is_full"] is False

    async def test_sensor_unavailable_on_coordinator_error(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
    ):
        """Test sensor is unavailable when coordinator has no data."""
        mock_coordinator.data = None
        mock_coordinator.last_update_success = False

        sensor = WodifyTodaysClassesSensor(mock_coordinator, mock_config_entry)

        assert sensor.available is False
        assert sensor.native_value == "Unavailable"


class TestSettingsSensor:
    """Test settings sensor."""

    async def test_sensor_properties(
        self,
        hass,  # noqa: ARG002
        mock_config_entry,
    ):
        """Test sensor properties."""
        sensor = WodifySettingsSensor(mock_config_entry)

        assert sensor.unique_id == "test_api_key_settings"
        assert sensor.name == "Settings"
        assert sensor.icon == "mdi:cog"
        assert sensor.should_poll is False
        assert sensor.available is True

    async def test_sensor_state(
        self,
        hass,  # noqa: ARG002
        mock_config_entry,
    ):
        """Test sensor state shows update interval."""
        sensor = WodifySettingsSensor(mock_config_entry)

        # Default update interval is 5 minutes
        assert sensor.native_value == "Updates every 5 min"

    async def test_sensor_attributes(
        self,
        hass,  # noqa: ARG002
        mock_config_entry,
    ):
        """Test sensor attributes contain all settings."""
        sensor = WodifySettingsSensor(mock_config_entry)
        attrs = sensor.extra_state_attributes

        assert attrs["update_interval_minutes"] == 5
        assert attrs["before_class_minutes"] == 15
        assert attrs["after_block_minutes"] == 15
        assert attrs["locations"] == ["CrossFit inner loop"]
        assert attrs["programs"] == ["DAILY WOD"]
