"""Test options flow."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.wodify.const import (
    CONF_AFTER_BLOCK_MINUTES,
    CONF_BLOCK_GAP_MINUTES,
    CONF_BEFORE_CLASS_MINUTES,
    CONF_EXCLUDE_PRIVATE_TRAINING,
    CONF_LOCATIONS,
    CONF_PROGRAMS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BLOCK_GAP_MINUTES,
)
from custom_components.wodify.models import WodifyClass


@pytest.fixture
def mock_api_responses():
    """Mock API responses with realistic Wodify data."""
    with patch("custom_components.wodify.config_flow.WodifyAPI") as mock_api_class:
        api_instance = Mock()
        mock_api_class.return_value = api_instance

        # Mock programs response (from real Wodify API)
        api_instance.get_programs = AsyncMock(
            return_value=[
                {"id": "1", "name": "DAILY WOD"},
                {"id": "2", "name": "Olympic Lifting"},
                {"id": "3", "name": "Open Gym"},
            ]
        )

        # Mock classes response with WodifyClass objects
        api_instance.search_classes = AsyncMock(
            return_value=[
                WodifyClass(
                    id="101",
                    name="8:00 AM WOD",
                    start_time=datetime(2025, 1, 1, 8, 0, tzinfo=UTC),
                    end_time=datetime(2025, 1, 1, 9, 0, tzinfo=UTC),
                    coach_name="Coach Mike",
                    location_name="CrossFit inner loop",
                    program_name="DAILY WOD",
                    max_attendees=20,
                    current_attendees=10,
                ),
                WodifyClass(
                    id="102",
                    name="9:00 AM WOD",
                    start_time=datetime(2025, 1, 1, 9, 0, tzinfo=UTC),
                    end_time=datetime(2025, 1, 1, 10, 0, tzinfo=UTC),
                    coach_name="Coach Sarah",
                    location_name="CrossFit inner loop",
                    program_name="DAILY WOD",
                    max_attendees=20,
                    current_attendees=15,
                ),
            ]
        )

        yield api_instance


class TestOptionsFlow:
    """Test options flow."""

    async def test_options_flow(self, hass, mock_config_entry, mock_api_responses):  # noqa: ARG002
        """Test options flow."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

        # Verify form is shown with expected fields
        schema = result["data_schema"].schema
        assert CONF_UPDATE_INTERVAL in schema
        assert CONF_BEFORE_CLASS_MINUTES in schema
        assert CONF_AFTER_BLOCK_MINUTES in schema
        assert CONF_EXCLUDE_PRIVATE_TRAINING in schema
        assert CONF_LOCATIONS in schema
        assert CONF_PROGRAMS in schema

        # Submit with valid values
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_UPDATE_INTERVAL: 10,
                CONF_BEFORE_CLASS_MINUTES: 30,
                CONF_AFTER_BLOCK_MINUTES: 20,
                CONF_EXCLUDE_PRIVATE_TRAINING: True,
                CONF_LOCATIONS: ["CrossFit inner loop"],
                CONF_PROGRAMS: ["DAILY WOD"],
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_UPDATE_INTERVAL] == 10
        assert result["data"][CONF_BEFORE_CLASS_MINUTES] == 30
        assert result["data"][CONF_AFTER_BLOCK_MINUTES] == 20
        assert result["data"][CONF_EXCLUDE_PRIVATE_TRAINING] is True
        assert result["data"][CONF_LOCATIONS] == ["CrossFit inner loop"]
        assert result["data"][CONF_PROGRAMS] == ["DAILY WOD"]

    async def test_options_flow_validation(self, hass, mock_config_entry, mock_api_responses):  # noqa: ARG002
        """Test options flow validation - schema validates ranges."""
        from homeassistant.data_entry_flow import InvalidData

        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        # Test invalid update interval (schema validation)
        with pytest.raises(InvalidData, match="update_interval"):
            await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    CONF_UPDATE_INTERVAL: 0,  # Too low - schema catches this
                    CONF_BEFORE_CLASS_MINUTES: 15,
                    CONF_AFTER_BLOCK_MINUTES: 15,
                    CONF_EXCLUDE_PRIVATE_TRAINING: True,
                    CONF_LOCATIONS: ["CrossFit inner loop"],
                    CONF_PROGRAMS: ["DAILY WOD"],
                },
            )

        # Re-init flow for next test
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        # Test invalid before class minutes (schema validation)
        with pytest.raises(InvalidData, match="before_class_minutes"):
            await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    CONF_UPDATE_INTERVAL: 5,
                    CONF_BEFORE_CLASS_MINUTES: 3,  # Too low - schema catches this
                    CONF_AFTER_BLOCK_MINUTES: 15,
                    CONF_EXCLUDE_PRIVATE_TRAINING: True,
                    CONF_LOCATIONS: ["CrossFit inner loop"],
                    CONF_PROGRAMS: ["DAILY WOD"],
                },
            )

        # Re-init flow for next test
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        # Test invalid after block minutes (schema validation)
        with pytest.raises(InvalidData, match="after_block_minutes"):
            await hass.config_entries.options.async_configure(
                result["flow_id"],
                {
                    CONF_UPDATE_INTERVAL: 5,
                    CONF_BEFORE_CLASS_MINUTES: 15,
                    CONF_AFTER_BLOCK_MINUTES: 100,  # Too high - schema catches this
                    CONF_EXCLUDE_PRIVATE_TRAINING: True,
                    CONF_LOCATIONS: ["CrossFit inner loop"],
                    CONF_PROGRAMS: ["DAILY WOD"],
                },
            )

    async def test_options_flow_with_api_update(
        self,
        hass,
        mock_config_entry,
        mock_api_responses,  # noqa: ARG002
    ):
        """Test options flow updates available locations and programs from API."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        # Should show locations and programs from API
        schema = result["data_schema"].schema
        locations_field = schema[CONF_LOCATIONS]
        programs_field = schema[CONF_PROGRAMS]

        assert "CrossFit inner loop" in locations_field.options
        assert "DAILY WOD" in programs_field.options
        assert "Olympic Lifting" in programs_field.options
        assert "Open Gym" in programs_field.options

    async def test_options_flow_no_changes(self, hass, mock_config_entry, mock_api_responses):  # noqa: ARG002
        """Test options flow with no changes."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        # Submit with same values
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_UPDATE_INTERVAL: 5,
                CONF_BEFORE_CLASS_MINUTES: 15,
                CONF_AFTER_BLOCK_MINUTES: 15,
                CONF_EXCLUDE_PRIVATE_TRAINING: True,
                CONF_LOCATIONS: ["CrossFit inner loop"],
                CONF_PROGRAMS: ["DAILY WOD"],
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        # Options should remain the same. block_gap_minutes is absent from the
        # submitted input above, so it lands on its default rather than being
        # dropped - an entry saved before the option existed keeps working.
        assert result["data"] == {
            CONF_UPDATE_INTERVAL: 5,
            CONF_BEFORE_CLASS_MINUTES: 15,
            CONF_AFTER_BLOCK_MINUTES: 15,
            CONF_BLOCK_GAP_MINUTES: DEFAULT_BLOCK_GAP_MINUTES,
            CONF_EXCLUDE_PRIVATE_TRAINING: True,
            CONF_LOCATIONS: ["CrossFit inner loop"],
            CONF_PROGRAMS: ["DAILY WOD"],
        }

    async def test_options_flow_empty_selections(self, hass, mock_config_entry, mock_api_responses):  # noqa: ARG002
        """Test options flow with empty location/program selections."""
        mock_config_entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

        # Try with no locations
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_UPDATE_INTERVAL: 5,
                CONF_BEFORE_CLASS_MINUTES: 15,
                CONF_AFTER_BLOCK_MINUTES: 15,
                CONF_EXCLUDE_PRIVATE_TRAINING: True,
                CONF_LOCATIONS: [],
                CONF_PROGRAMS: ["DAILY WOD"],
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {CONF_LOCATIONS: "no_locations"}

        # Try with no programs
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_UPDATE_INTERVAL: 5,
                CONF_BEFORE_CLASS_MINUTES: 15,
                CONF_AFTER_BLOCK_MINUTES: 15,
                CONF_EXCLUDE_PRIVATE_TRAINING: True,
                CONF_LOCATIONS: ["CrossFit inner loop"],
                CONF_PROGRAMS: [],
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {CONF_PROGRAMS: "no_programs"}
