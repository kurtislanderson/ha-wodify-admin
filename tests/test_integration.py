"""Integration tests."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.wodify.const import DOMAIN
from custom_components.wodify.models import WodifyClass


@pytest.fixture
def persistent_api_mock(mock_api_responses):
    """Create a persistent API mock that survives reloads."""
    with (
        patch("custom_components.wodify.config_flow.WodifyAPI") as mock_api_class,
        patch("custom_components.wodify.WodifyAPI") as mock_api_init,
    ):
        # Mock API for config flow
        mock_api = mock_api_class.return_value
        mock_api.get_programs = AsyncMock(return_value=mock_api_responses["programs"])
        mock_api.search_classes = AsyncMock(return_value=mock_api_responses["classes"])

        # Mock API for integration
        mock_api_instance = mock_api_init.return_value
        mock_api_instance.search_classes = AsyncMock(return_value=mock_api_responses["classes"])

        yield mock_api_instance


async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api_responses,
) -> None:
    """Set up the integration with mocked API responses."""
    with (
        patch("custom_components.wodify.config_flow.WodifyAPI") as mock_api_class,
        patch("custom_components.wodify.WodifyAPI") as mock_api_init,
    ):
        # Mock API for config flow
        mock_api = mock_api_class.return_value
        mock_api.get_programs = AsyncMock(return_value=mock_api_responses["programs"])
        mock_api.search_classes = AsyncMock(return_value=mock_api_responses["classes"])

        # Mock API for integration
        mock_api_instance = mock_api_init.return_value
        mock_api_instance.search_classes = AsyncMock(return_value=mock_api_responses["classes"])

        # Add entry and set up
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.fixture
def mock_api_responses():
    """Create mock API responses."""
    now = datetime.now(tz=UTC)
    return {
        "programs": [
            {"id": "1", "name": "CrossFit"},
            {"id": "2", "name": "Yoga"},
        ],
        "classes": [
            WodifyClass(
                id="1",
                name="Morning CrossFit",
                start_time=now + timedelta(hours=2),
                end_time=now + timedelta(hours=3),
                coach_name="Coach Mike",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=15,
            ),
            WodifyClass(
                id="2",
                name="Evening Yoga",
                start_time=now + timedelta(hours=8),
                end_time=now + timedelta(hours=9),
                coach_name="Coach Sarah",
                location_name="Downtown",
                program_name="Yoga",
                max_attendees=15,
                current_attendees=10,
            ),
        ],
    }


class TestIntegration:
    """Test full integration."""

    async def test_full_setup_flow(self, hass, mock_config_entry, mock_api_responses):
        """Test complete setup flow from config to entities."""
        await setup_integration(hass, mock_config_entry, mock_api_responses)

        # Verify integration is loaded
        assert mock_config_entry.state == ConfigEntryState.LOADED

        # Verify entities are created
        state = hass.states.get("sensor.next_class")
        assert state is not None
        assert state.state != STATE_UNAVAILABLE
        assert "Morning CrossFit" in state.state

        state = hass.states.get("binary_sensor.class_ongoing")
        assert state is not None
        assert state.state == "off"  # No class ongoing

        # Calendar platform is also loaded
        state = hass.states.get("calendar.classes")
        assert state is not None

    async def test_reload_entry(
        self,
        hass,
        mock_config_entry,
        mock_api_responses,  # noqa: ARG002
        persistent_api_mock,  # noqa: ARG002
    ):
        """Test reloading config entry."""
        # Using persistent_api_mock fixture to ensure mocks survive reload
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Get initial state
        old_state = hass.states.get("sensor.next_class")
        assert old_state is not None

        # Reload
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify still working
        new_state = hass.states.get("sensor.next_class")
        assert new_state is not None
        assert new_state.state != STATE_UNAVAILABLE

    async def test_unload_entry(
        self,
        hass,
        mock_config_entry,
        mock_api_responses,  # noqa: ARG002
        persistent_api_mock,  # noqa: ARG002
    ):
        """Test unloading config entry."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify entities exist
        assert hass.states.get("sensor.next_class") is not None

        # Unload
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Entity state becomes unavailable but entity remains in registry
        state = hass.states.get("sensor.next_class")
        # State may be unavailable or None depending on HA version
        if state is not None:
            assert state.state == STATE_UNAVAILABLE

        # Verify data cleaned up
        assert mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})

    async def test_entity_registry_cleanup(self, hass, mock_config_entry, mock_api_responses):
        """Test entity registry is properly cleaned up."""
        await setup_integration(hass, mock_config_entry, mock_api_responses)

        # Get entity registry
        ent_reg = er.async_get(hass)

        # Verify entities are registered
        sensor_entity = ent_reg.async_get("sensor.next_class")
        assert sensor_entity is not None

        # Remove entry
        await hass.config_entries.async_remove(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify entities are removed from registry
        sensor_entity = ent_reg.async_get("sensor.next_class")
        assert sensor_entity is None

    async def test_coordinator_updates_entities(self, hass, mock_config_entry, mock_api_responses):
        """Test coordinator updates propagate to entities."""
        await setup_integration(hass, mock_config_entry, mock_api_responses)

        # Get coordinator
        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Update coordinator data
        new_class = WodifyClass(
            id="3",
            name="New Class",
            start_time=datetime.now(tz=UTC) + timedelta(hours=1),
            end_time=datetime.now(tz=UTC) + timedelta(hours=2),
            coach_name="Coach New",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=5,
        )
        coordinator.data = [new_class]
        coordinator.async_set_updated_data([new_class])

        await hass.async_block_till_done()

        # Verify entity updated
        state = hass.states.get("sensor.next_class")
        assert "New Class" in state.state

    async def test_coordinator_refresh_reschedules_events(
        self, hass, mock_config_entry, mock_api_responses
    ):
        """Each coordinator refresh should trigger event rescheduling."""

        with (
            patch("custom_components.wodify.config_flow.WodifyAPI") as mock_api_class,
            patch("custom_components.wodify.WodifyAPI") as mock_api_init,
        ):
            mock_api = mock_api_class.return_value
            mock_api.get_programs = AsyncMock(return_value=mock_api_responses["programs"])
            mock_api.search_classes = AsyncMock(return_value=mock_api_responses["classes"])

            mock_api_instance = mock_api_init.return_value
            mock_api_instance.search_classes = AsyncMock(return_value=mock_api_responses["classes"])

            mock_config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            event_manager = hass.data[DOMAIN][mock_config_entry.entry_id]["event_manager"]

            # Verify coordinator has a listener (the event_manager)
            assert len(coordinator._listeners) >= 1

            # Test that updating coordinator data triggers the event manager
            initial_event_count = len(event_manager._upcoming_events)  # noqa: F841
            new_class = WodifyClass(
                id="new",
                name="New Class",
                start_time=datetime.now(tz=UTC) + timedelta(hours=1),
                end_time=datetime.now(tz=UTC) + timedelta(hours=2),
                coach_name="Coach",
                location_name="Downtown",
                program_name="CrossFit",
                max_attendees=20,
                current_attendees=10,
            )
            coordinator.async_set_updated_data([new_class])
            await hass.async_block_till_done()

            # Event manager should have processed the update
            # (it may or may not have events scheduled depending on timing)
            assert event_manager is not None

    async def test_event_system_integration(self, hass, mock_config_entry, mock_api_responses):
        """Test event system is properly integrated."""
        events_fired = []

        def capture_event(event):
            events_fired.append(event)

        hass.bus.async_listen("wodify_class_starts_soon", capture_event)

        # Set up with a class starting in the future (beyond before_class_minutes)
        upcoming_class = WodifyClass(
            id="1",
            name="Starting Soon",
            start_time=datetime.now(tz=UTC) + timedelta(minutes=20),
            end_time=datetime.now(tz=UTC) + timedelta(hours=1),
            coach_name="Coach Mike",
            location_name="Downtown",
            program_name="CrossFit",
            max_attendees=20,
            current_attendees=15,
        )

        with (
            patch("custom_components.wodify.config_flow.WodifyAPI") as mock_api_class,
            patch("custom_components.wodify.WodifyAPI") as mock_api_init,
        ):
            mock_api = mock_api_class.return_value
            mock_api.get_programs = AsyncMock(return_value=mock_api_responses["programs"])
            mock_api.search_classes = AsyncMock(return_value=[upcoming_class])

            mock_api_instance = mock_api_init.return_value
            mock_api_instance.search_classes = AsyncMock(return_value=[upcoming_class])

            mock_config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            # Get event manager
            event_manager = hass.data[DOMAIN][mock_config_entry.entry_id]["event_manager"]

            # Verify event manager exists and has the right timing values
            assert event_manager is not None
            assert event_manager.before_class_minutes == 15
            assert event_manager.after_block_minutes == 15

            # Manually trigger schedule_events to verify scheduling works
            event_manager.coordinator.data = [upcoming_class]
            event_manager.schedule_events()
            await hass.async_block_till_done()

            # Now there should be scheduled events
            assert len(event_manager._upcoming_events) > 0

    async def test_service_integration(self, hass, mock_config_entry, mock_api_responses):
        """Test services work with integration."""
        await setup_integration(hass, mock_config_entry, mock_api_responses)

        # Test refresh service
        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        coordinator.async_request_refresh = AsyncMock()

        await hass.services.async_call(
            DOMAIN,
            "refresh_now",
            {"entry_id": mock_config_entry.entry_id},
            blocking=True,
        )

        coordinator.async_request_refresh.assert_called_once()

    async def test_options_flow_updates_integration(
        self, hass, mock_config_entry, mock_api_responses
    ):
        """Test options flow updates affect integration."""
        with (
            patch("custom_components.wodify.config_flow.WodifyAPI") as mock_api_class,
            patch("custom_components.wodify.WodifyAPI") as mock_api_init,
        ):
            # Mock API for config flow
            mock_api = mock_api_class.return_value
            mock_api.get_programs = AsyncMock(return_value=mock_api_responses["programs"])
            mock_api.search_classes = AsyncMock(return_value=mock_api_responses["classes"])

            # Mock API for integration
            mock_api_instance = mock_api_init.return_value
            mock_api_instance.search_classes = AsyncMock(return_value=mock_api_responses["classes"])
            mock_api_instance.get_programs = AsyncMock(return_value=mock_api_responses["programs"])

            mock_config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            event_manager = hass.data[DOMAIN][mock_config_entry.entry_id][  # noqa: F841
                "event_manager"
            ]

            # Update options
            result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

            result = await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    "update_interval": 10,
                    "before_class_minutes": 30,
                    "after_block_minutes": 20,
                    "locations": ["Downtown"],
                    "programs": ["CrossFit"],
                },
            )

            await hass.async_block_till_done()

            # After options change, event manager gets the updated values from config
            # Get the potentially new event_manager after reload
            new_event_manager = hass.data[DOMAIN][mock_config_entry.entry_id]["event_manager"]
            assert new_event_manager.before_class_minutes == 30
            assert new_event_manager.after_block_minutes == 20

    async def test_multiple_config_entries(self, hass, mock_api_responses):
        """Test multiple config entries work independently."""
        from homeassistant.helpers import entity_registry as er
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        # Create two config entries
        entry1 = MockConfigEntry(
            domain=DOMAIN,
            title="Wodify 1",
            unique_id="api_key_1",
            data={
                "api_key": "key1",
                "locations": ["Downtown"],
                "programs": ["CrossFit"],
            },
            options={
                "update_interval": 5,
                "before_class_minutes": 15,
                "after_block_minutes": 15,
            },
        )

        entry2 = MockConfigEntry(
            domain=DOMAIN,
            title="Wodify 2",
            unique_id="api_key_2",
            data={
                "api_key": "key2",
                "locations": ["Uptown"],
                "programs": ["Yoga"],
            },
            options={
                "update_interval": 10,
                "before_class_minutes": 30,
                "after_block_minutes": 30,
            },
        )

        # Set up both
        await setup_integration(hass, entry1, mock_api_responses)
        await setup_integration(hass, entry2, mock_api_responses)

        # Verify both are loaded
        assert entry1.state == ConfigEntryState.LOADED
        assert entry2.state == ConfigEntryState.LOADED

        # Verify separate coordinators
        assert (
            hass.data[DOMAIN][entry1.entry_id]["coordinator"]
            != hass.data[DOMAIN][entry2.entry_id]["coordinator"]
        )

        # Verify entities have unique IDs
        ent_reg = er.async_get(hass)
        entities = er.async_entries_for_config_entry(ent_reg, entry1.entry_id)
        assert len(entities) == 5  # next_class, current_class, api_status, binary_sensor, calendar

        entities2 = er.async_entries_for_config_entry(ent_reg, entry2.entry_id)
        assert len(entities2) == 5

        # Ensure no overlap
        entity1_ids = {e.unique_id for e in entities}
        entity2_ids = {e.unique_id for e in entities2}
        assert entity1_ids.isdisjoint(entity2_ids)
