"""Test services."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wodify.const import (
    CONF_AFTER_BLOCK_MINUTES,
    CONF_BEFORE_CLASS_MINUTES,
    CONF_LOCATIONS,
    CONF_PROGRAMS,
    DOMAIN,
)
from custom_components.wodify.models import WodifyRuntimeData


@pytest.fixture
def mock_integration_setup(hass, mock_config_entry, mock_coordinator):
    """Set up mock integration."""
    mock_event_manager = Mock()
    mock_event_manager.update_timing = Mock()

    mock_config_entry.runtime_data = WodifyRuntimeData(
        coordinator=mock_coordinator, api=Mock(), event_manager=mock_event_manager
    )

    # Add config entry to hass so services can find it
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    return mock_config_entry, mock_coordinator, mock_event_manager


class TestServices:
    """Test Wodify services."""

    async def test_refresh_service(self, hass, mock_integration_setup):
        """Test refresh service."""
        config_entry, coordinator, _ = mock_integration_setup
        coordinator.async_request_refresh = AsyncMock()

        # Register service
        from custom_components.wodify.services import async_setup_services

        await async_setup_services(hass)

        # Call service
        await hass.services.async_call(
            DOMAIN,
            "refresh_now",
            {"entry_id": config_entry.entry_id},
            blocking=True,
        )

        # Verify coordinator refresh was called
        coordinator.async_request_refresh.assert_called_once()

    async def test_refresh_service_invalid_entry(self, hass):
        """Test refresh service with invalid entry ID."""
        from custom_components.wodify.services import async_setup_services

        await async_setup_services(hass)

        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "refresh_now",
                {"entry_id": "invalid_id"},
                blocking=True,
            )
        assert exc_info.value.translation_key == "entry_not_found"

    async def test_set_filter_service(self, hass, mock_integration_setup):
        """Test set filter service."""
        config_entry, coordinator, _ = mock_integration_setup
        coordinator.async_set_filters = AsyncMock()

        from custom_components.wodify.services import async_setup_services

        await async_setup_services(hass)

        # Call service
        await hass.services.async_call(
            DOMAIN,
            "set_filter",
            {
                "entry_id": config_entry.entry_id,
                "locations": ["Downtown", "Uptown"],
                "programs": ["CrossFit", "Yoga"],
            },
            blocking=True,
        )

        # Verify filters were updated
        coordinator.async_set_filters.assert_called_once_with(
            ["Downtown", "Uptown"], ["CrossFit", "Yoga"]
        )

    async def test_set_filter_service_empty_lists(self, hass, mock_integration_setup):
        """Test set filter service with empty lists."""
        config_entry, coordinator, _ = mock_integration_setup
        coordinator.async_set_filters = AsyncMock()

        from custom_components.wodify.services import async_setup_services

        await async_setup_services(hass)

        # Should raise error for empty locations
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "set_filter",
                {
                    "entry_id": config_entry.entry_id,
                    "locations": [],
                    "programs": ["CrossFit"],
                },
                blocking=True,
            )
        assert exc_info.value.translation_key == "no_locations"

        # Should raise error for empty programs
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "set_filter",
                {
                    "entry_id": config_entry.entry_id,
                    "locations": ["Downtown"],
                    "programs": [],
                },
                blocking=True,
            )
        assert exc_info.value.translation_key == "no_programs"

    async def test_set_event_timing_service(self, hass, mock_integration_setup):
        """Test set event timing service."""
        config_entry, _, event_manager = mock_integration_setup

        from custom_components.wodify.services import async_setup_services

        await async_setup_services(hass)

        # Call service
        await hass.services.async_call(
            DOMAIN,
            "set_event_timing",
            {
                "entry_id": config_entry.entry_id,
                "before_class_minutes": 30,
                "after_block_minutes": 20,
            },
            blocking=True,
        )

        # Verify timing was updated
        event_manager.update_timing.assert_called_once_with(30, 20)

    async def test_set_event_timing_service_validation(self, hass, mock_integration_setup):
        """Test set event timing service validation."""
        config_entry, _, _ = mock_integration_setup

        from custom_components.wodify.services import async_setup_services

        await async_setup_services(hass)

        # Test invalid before_class_minutes (too low)
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "set_event_timing",
                {
                    "entry_id": config_entry.entry_id,
                    "before_class_minutes": 3,
                    "after_block_minutes": 15,
                },
                blocking=True,
            )
        assert exc_info.value.translation_key == "invalid_before_minutes"

        # Test invalid after_block_minutes (too high)
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "set_event_timing",
                {
                    "entry_id": config_entry.entry_id,
                    "before_class_minutes": 15,
                    "after_block_minutes": 100,
                },
                blocking=True,
            )
        assert exc_info.value.translation_key == "invalid_after_minutes"

    async def test_service_with_multiple_entries(self, hass):
        """Test service with multiple config entries."""
        from custom_components.wodify.services import async_setup_services

        await async_setup_services(hass)

        # Set up multiple entries
        entry1_id = "entry1"
        entry2_id = "entry2"

        coordinator1 = Mock()
        coordinator1.async_request_refresh = AsyncMock()
        coordinator2 = Mock()
        coordinator2.async_request_refresh = AsyncMock()

        for entry_id, coordinator in ((entry1_id, coordinator1), (entry2_id, coordinator2)):
            entry = MockConfigEntry(domain=DOMAIN, entry_id=entry_id)
            entry.runtime_data = WodifyRuntimeData(
                coordinator=coordinator, api=Mock(), event_manager=Mock()
            )
            entry.add_to_hass(hass)
            entry.mock_state(hass, ConfigEntryState.LOADED)

        # Call service for entry1
        await hass.services.async_call(
            DOMAIN,
            "refresh_now",
            {"entry_id": entry1_id},
            blocking=True,
        )

        # Only entry1's coordinator should be refreshed
        coordinator1.async_request_refresh.assert_called_once()
        coordinator2.async_request_refresh.assert_not_called()

    async def test_service_descriptions(self, hass):
        """Test service descriptions are registered."""
        from custom_components.wodify.services import async_setup_services

        await async_setup_services(hass)

        # Check services are registered
        assert hass.services.has_service(DOMAIN, "refresh_now")
        assert hass.services.has_service(DOMAIN, "set_filter")
        assert hass.services.has_service(DOMAIN, "set_event_timing")

    async def test_service_unload(self, hass):
        """Test service unloading."""
        from custom_components.wodify.services import (
            async_setup_services,
            async_unload_services,
        )

        # Set up services
        await async_setup_services(hass)
        assert hass.services.has_service(DOMAIN, "refresh_now")

        # Unload services
        await async_unload_services(hass)
        assert not hass.services.has_service(DOMAIN, "refresh_now")
        assert not hass.services.has_service(DOMAIN, "set_filter")
        assert not hass.services.has_service(DOMAIN, "set_event_timing")

    async def test_service_config_entry_update(self, hass, mock_integration_setup):
        """Test services update config entry data."""
        config_entry, coordinator, _ = mock_integration_setup
        coordinator.async_set_filters = AsyncMock()

        # Mock config entry update
        with patch.object(hass.config_entries, "async_update_entry") as mock_update:
            from custom_components.wodify.services import async_setup_services

            await async_setup_services(hass)

            # Call set_filter service
            await hass.services.async_call(
                DOMAIN,
                "set_filter",
                {
                    "entry_id": config_entry.entry_id,
                    "locations": ["New Location"],
                    "programs": ["New Program"],
                },
                blocking=True,
            )

            # Verify config entry was updated
            mock_update.assert_called_once()
            call_args = mock_update.call_args[0]
            assert call_args[0] == config_entry
            assert CONF_LOCATIONS in mock_update.call_args[1]["data"]
            assert mock_update.call_args[1]["data"][CONF_LOCATIONS] == ["New Location"]
            assert mock_update.call_args[1]["data"][CONF_PROGRAMS] == ["New Program"]

    async def test_service_options_update(self, hass, mock_integration_setup):
        """Test services update config entry options."""
        config_entry, _, _event_manager = mock_integration_setup

        # Mock config entry update
        with patch.object(hass.config_entries, "async_update_entry") as mock_update:
            from custom_components.wodify.services import async_setup_services

            await async_setup_services(hass)

            # Call set_event_timing service
            await hass.services.async_call(
                DOMAIN,
                "set_event_timing",
                {
                    "entry_id": config_entry.entry_id,
                    "before_class_minutes": 45,
                    "after_block_minutes": 30,
                },
                blocking=True,
            )

            # Verify config entry options were updated
            mock_update.assert_called_once()
            options = mock_update.call_args[1]["options"]
            assert options[CONF_BEFORE_CLASS_MINUTES] == 45
            assert options[CONF_AFTER_BLOCK_MINUTES] == 30


class TestSendEmailService:
    """Test wodify.send_email."""

    async def test_passes_fields_and_returns_response(self, hass, mock_integration_setup):
        """Fields reach the API and the email id is returned."""
        config_entry, _, _ = mock_integration_setup
        api = config_entry.runtime_data.api
        api.send_email = AsyncMock(return_value={"is_success": True, "email_service_email_id": 42})

        from custom_components.wodify.services import async_setup_services

        await async_setup_services(hass)
        result = await hass.services.async_call(
            DOMAIN,
            "send_email",
            {
                "entry_id": config_entry.entry_id,
                "to_email": "a@x.com",
                "subject": "S",
                "body": "B",
                "cc": "c@x.com",
            },
            blocking=True,
            return_response=True,
        )

        assert result == {"email_service_email_id": 42}
        api.send_email.assert_awaited_once_with(
            "a@x.com", "S", "B", from_email=None, cc=["c@x.com"], bcc=None
        )

    async def test_api_error_maps_to_ha_error(self, hass, mock_integration_setup):
        """ApiError becomes HomeAssistantError with send_email_failed key."""
        from custom_components.wodify.api import ApiError
        from custom_components.wodify.services import async_setup_services

        config_entry, _, _ = mock_integration_setup
        config_entry.runtime_data.api.send_email = AsyncMock(side_effect=ApiError("nope"))
        await async_setup_services(hass)

        with pytest.raises(HomeAssistantError) as exc:
            await hass.services.async_call(
                DOMAIN,
                "send_email",
                {
                    "entry_id": config_entry.entry_id,
                    "to_email": "a@x.com",
                    "subject": "S",
                    "body": "B",
                },
                blocking=True,
            )
        assert exc.value.translation_key == "send_email_failed"

    async def test_unknown_entry(self, hass):
        """Unknown entry_id raises ServiceValidationError."""
        from custom_components.wodify.services import async_setup_services

        await async_setup_services(hass)
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                "send_email",
                {"entry_id": "missing", "to_email": "a@x.com", "subject": "S", "body": "B"},
                blocking=True,
            )
