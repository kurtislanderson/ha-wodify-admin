"""Test configuration flow."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResultType

from custom_components.wodify.api import ApiAuthError, ApiError
from custom_components.wodify.const import (
    CONF_AFTER_BLOCK_MINUTES,
    CONF_BEFORE_CLASS_MINUTES,
    CONF_LOCATIONS,
    CONF_PROGRAMS,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
)


@pytest.fixture
def mock_wodify_api():
    """Mock Wodify API calls."""
    with patch("custom_components.wodify.config_flow.WodifyAPI") as mock:
        api_instance = Mock()
        mock.return_value = api_instance

        # Default successful responses
        api_instance.get_programs = AsyncMock(
            return_value=[
                {"id": "1", "name": "CrossFit"},
                {"id": "2", "name": "Yoga"},
                {"id": "3", "name": "Olympic Lifting"},
            ]
        )

        api_instance.search_classes = AsyncMock(
            return_value=[
                Mock(location_name="Downtown", program_name="CrossFit"),
                Mock(location_name="Uptown", program_name="CrossFit"),
                Mock(location_name="Downtown", program_name="Yoga"),
            ]
        )

        yield api_instance


class TestConfigFlow:
    """Test config flow."""

    async def test_form_api_key(self, hass):
        """Test API key form is shown."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

    async def test_form_invalid_auth(self, hass, mock_wodify_api):
        """Test invalid authentication."""
        mock_wodify_api.get_programs.side_effect = ApiAuthError("Invalid API key")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "invalid"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_form_cannot_connect(self, hass, mock_wodify_api):
        """Test connection error."""
        mock_wodify_api.get_programs.side_effect = ApiError("Connection failed")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "test_key"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_full_flow_success(self, hass, mock_wodify_api):
        """Test successful full configuration flow."""
        # Step 1: API Key
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "test_key"},
        )

        # Step 2: Locations
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "locations"
        assert "Downtown" in result["data_schema"].schema["locations"].options
        assert "Uptown" in result["data_schema"].schema["locations"].options

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LOCATIONS: ["Downtown"]},
        )

        # Step 3: Programs
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "programs"
        assert "CrossFit" in result["data_schema"].schema["programs"].options
        assert "Yoga" in result["data_schema"].schema["programs"].options

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PROGRAMS: ["CrossFit"]},
        )

        # Step 4: Options
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "options"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_UPDATE_INTERVAL: 5,
                CONF_BEFORE_CLASS_MINUTES: 15,
                CONF_AFTER_BLOCK_MINUTES: 15,
            },
        )

        # Should create entry
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Wodify (Downtown)"
        assert result["data"][CONF_API_KEY] == "test_key"
        assert result["data"][CONF_LOCATIONS] == ["Downtown"]
        assert result["data"][CONF_PROGRAMS] == ["CrossFit"]
        assert result["options"][CONF_UPDATE_INTERVAL] == 5
        assert result["options"][CONF_BEFORE_CLASS_MINUTES] == 15
        assert result["options"][CONF_AFTER_BLOCK_MINUTES] == 15

    async def test_flow_already_configured(self, hass, mock_config_entry):
        """Test flow when already configured."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "test_key"},
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"

    async def test_reauth_flow(self, hass, mock_config_entry, mock_wodify_api):
        """Test reauth flow."""
        mock_config_entry.add_to_hass(hass)

        # Start reauth flow - don't pass data= to see the form first
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth"

        # Submit new API key
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "new_api_key"},
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"

        # Verify entry was updated
        assert mock_config_entry.data[CONF_API_KEY] == "new_api_key"

    async def test_reauth_flow_invalid_auth(
        self, hass, mock_config_entry, mock_wodify_api
    ):
        """Test reauth flow with invalid credentials."""
        mock_config_entry.add_to_hass(hass)
        mock_wodify_api.get_programs.side_effect = ApiAuthError("Invalid API key")

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config_entry.entry_id,
            },
            data=mock_config_entry.data,
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "invalid_key"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_options_validation(self, hass, mock_wodify_api):
        """Test options validation in config flow - schema validates ranges."""
        from homeassistant.data_entry_flow import InvalidData

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Complete flow until options step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "test_key"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LOCATIONS: ["Downtown"]},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PROGRAMS: ["CrossFit"]},
        )

        # Test invalid update interval - schema catches this
        with pytest.raises(InvalidData, match="update_interval"):
            await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_UPDATE_INTERVAL: 100,  # Out of range - schema catches
                    CONF_BEFORE_CLASS_MINUTES: 15,
                    CONF_AFTER_BLOCK_MINUTES: 15,
                },
            )

    async def test_empty_locations_or_programs(self, hass, mock_wodify_api):
        """Test handling when no locations or programs selected."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "test_key"},
        )

        # Try to submit with no locations
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LOCATIONS: []},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"locations": "no_locations"}

    async def test_unique_location_extraction(self, hass, mock_wodify_api):
        """Test that locations are extracted uniquely from classes."""
        # Setup API to return duplicate locations
        mock_wodify_api.search_classes.return_value = [
            Mock(location_name="Downtown"),
            Mock(location_name="Downtown"),
            Mock(location_name="Uptown"),
            Mock(location_name="Downtown"),
        ]

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "test_key"},
        )

        # Check locations are unique and sorted
        locations = result["data_schema"].schema["locations"].options
        assert locations == {"Downtown", "Uptown"}  # Set ensures uniqueness
