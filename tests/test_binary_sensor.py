"""Test binary sensor entities."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.wodify.binary_sensor import (
    WodifyClassOngoingBinarySensor,
    async_setup_entry,
)
from custom_components.wodify.const import DOMAIN
from custom_components.wodify.models import WodifyClass


@pytest.fixture
def ongoing_class_data():
    """Create test data with ongoing class."""
    return [
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
        )
    ]


class TestClassOngoingBinarySensor:
    """Test class ongoing binary sensor."""

    async def test_sensor_properties(self, hass, mock_coordinator, mock_config_entry):  # noqa: ARG002
        """Test sensor properties."""
        sensor = WodifyClassOngoingBinarySensor(mock_coordinator, mock_config_entry)

        assert sensor.unique_id == "test_api_key_class_ongoing"
        assert sensor.name == "Class Ongoing"
        assert sensor.device_class == BinarySensorDeviceClass.RUNNING
        assert sensor.should_poll is False
        assert sensor.available is True

    async def test_sensor_on_during_class(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
        ongoing_class_data,  # noqa: ARG002
    ):
        """Test sensor is on during class."""
        mock_coordinator.data = ongoing_class_data
        sensor = WodifyClassOngoingBinarySensor(mock_coordinator, mock_config_entry)

        # Mock current time during class
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 17, 45, tzinfo=UTC)
            assert sensor.is_on is True

            attrs = sensor.extra_state_attributes
            assert attrs["current_class"] == "CrossFit"
            assert attrs["coach"] == "Coach Mike"
            assert attrs["location"] == "Downtown"
            assert attrs["minutes_remaining"] == 45
            assert attrs["start_time"] == "2024-01-01T17:30:00"
            assert attrs["end_time"] == "2024-01-01T18:30:00"

    async def test_sensor_off_before_class(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
        ongoing_class_data,  # noqa: ARG002
    ):
        """Test sensor is off before class starts."""
        mock_coordinator.data = ongoing_class_data
        sensor = WodifyClassOngoingBinarySensor(mock_coordinator, mock_config_entry)

        # Mock current time before class
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
            assert sensor.is_on is False
            assert sensor.extra_state_attributes == {}

    async def test_sensor_off_after_class(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
        ongoing_class_data,  # noqa: ARG002
    ):
        """Test sensor is off after class ends."""
        mock_coordinator.data = ongoing_class_data
        sensor = WodifyClassOngoingBinarySensor(mock_coordinator, mock_config_entry)

        # Mock current time after class
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 19, 0, tzinfo=UTC)
            assert sensor.is_on is False
            assert sensor.extra_state_attributes == {}

    async def test_sensor_minutes_remaining_calculation(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
        ongoing_class_data,  # noqa: ARG002
    ):
        """Test minutes remaining calculation during class."""
        mock_coordinator.data = ongoing_class_data
        sensor = WodifyClassOngoingBinarySensor(mock_coordinator, mock_config_entry)

        # Test at different times during class
        test_times = [
            (datetime(2024, 1, 1, 17, 30, tzinfo=UTC), 60),  # Start of class
            (datetime(2024, 1, 1, 17, 45, tzinfo=UTC), 45),  # 15 min in
            (datetime(2024, 1, 1, 18, 0, tzinfo=UTC), 30),  # 30 min in
            (datetime(2024, 1, 1, 18, 15, tzinfo=UTC), 15),  # 45 min in
            (datetime(2024, 1, 1, 18, 29, tzinfo=UTC), 1),  # 1 min left
        ]

        for current_time, expected_remaining in test_times:
            with patch("homeassistant.util.dt.now") as mock_now:
                mock_now.return_value = current_time
                assert sensor.is_on is True
                assert sensor.extra_state_attributes["minutes_remaining"] == expected_remaining

    async def test_sensor_multiple_overlapping_classes(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,  # noqa: ARG002
    ):
        """Test sensor with multiple overlapping classes (picks first ongoing)."""
        mock_coordinator.data = [
            WodifyClass(
                id="1",
                name="CrossFit",
                start_time=datetime(2024, 1, 1, 17, 0, tzinfo=UTC),
                end_time=datetime(2024, 1, 1, 18, 0, tzinfo=UTC),
                coach_name="Coach A",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=15,
            ),
            WodifyClass(
                id="2",
                name="Yoga",
                start_time=datetime(2024, 1, 1, 17, 30, tzinfo=UTC),
                end_time=datetime(2024, 1, 1, 18, 30, tzinfo=UTC),
                coach_name="Coach B",
                location_name="Uptown",
                program_name="Yoga",
                max_attendees=15,
                current_attendees=10,
            ),
        ]
        sensor = WodifyClassOngoingBinarySensor(mock_coordinator, mock_config_entry)

        # Mock current time when both classes are ongoing
        with patch("homeassistant.util.dt.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 17, 35, tzinfo=UTC)
            assert sensor.is_on is True
            # Should show the first ongoing class
            assert sensor.extra_state_attributes["current_class"] == "CrossFit"
            assert sensor.extra_state_attributes["coach"] == "Coach A"

    async def test_sensor_no_classes(self, hass, mock_coordinator, mock_config_entry):  # noqa: ARG002
        """Test sensor with no classes scheduled."""
        mock_coordinator.data = []
        sensor = WodifyClassOngoingBinarySensor(mock_coordinator, mock_config_entry)

        assert sensor.is_on is False
        assert sensor.extra_state_attributes == {}

    async def test_sensor_unavailable_on_coordinator_error(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,  # noqa: ARG002
    ):
        """Test sensor is unavailable when coordinator has no data."""
        mock_coordinator.data = None
        mock_coordinator.last_update_success = False

        sensor = WodifyClassOngoingBinarySensor(mock_coordinator, mock_config_entry)

        assert sensor.available is False
        assert sensor.is_on is None

    async def test_sensor_device_info(self, hass, mock_coordinator, mock_config_entry):  # noqa: ARG002
        """Test sensor device info."""
        sensor = WodifyClassOngoingBinarySensor(mock_coordinator, mock_config_entry)

        device_info = sensor.device_info
        assert device_info["identifiers"] == {(DOMAIN, mock_config_entry.entry_id)}
        assert device_info["name"] == "Wodify"

    async def test_binary_sensor_setup(self, hass, mock_config_entry, mock_coordinator):
        """Test binary sensor setup through async_setup_entry."""
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
        # 3 binary sensors: ongoing, starting_soon, block_ended
        assert len(entities) == 3
        assert isinstance(entities[0], WodifyClassOngoingBinarySensor)

    async def test_sensor_icon_changes(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
        ongoing_class_data,  # noqa: ARG002
    ):
        """Test sensor icon changes based on state."""
        mock_coordinator.data = ongoing_class_data
        sensor = WodifyClassOngoingBinarySensor(mock_coordinator, mock_config_entry)

        # During class - icon is mdi:timer when class is ongoing
        with patch("custom_components.wodify.binary_sensor.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 17, 45, tzinfo=UTC)
            assert sensor.icon == "mdi:timer"

        # Outside class - icon is mdi:timer-off when no class ongoing
        with patch("custom_components.wodify.binary_sensor.dt_util.now") as mock_now:
            mock_now.return_value = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
            assert sensor.icon == "mdi:timer-off"

    async def test_sensor_state_updates_on_coordinator_update(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,  # noqa: ARG002
    ):
        """Test sensor updates when coordinator data changes."""
        sensor = WodifyClassOngoingBinarySensor(mock_coordinator, mock_config_entry)

        # Initially no classes
        mock_coordinator.data = []
        assert sensor.is_on is False

        # Add an ongoing class (class started 10 mins ago, ends in 50 mins)
        now = datetime.now(tz=UTC)
        mock_coordinator.data = [
            WodifyClass(
                id="999",
                name="New Class",
                start_time=now - timedelta(minutes=10),
                end_time=now + timedelta(minutes=50),
                coach_name="Coach New",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=5,
            )
        ]

        # Should now be on (sensor reads from coordinator.data directly)
        assert sensor.is_on is True
        assert sensor.extra_state_attributes["current_class"] == "New Class"
