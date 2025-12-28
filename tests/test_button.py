"""Test button entities."""

from unittest.mock import AsyncMock, Mock

from custom_components.wodify.button import WodifyRefreshButton, async_setup_entry
from custom_components.wodify.const import DOMAIN


class TestRefreshButton:
    """Test refresh button."""

    async def test_button_properties(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
    ):
        """Test button properties."""
        button = WodifyRefreshButton(mock_coordinator, mock_config_entry)

        assert button.unique_id == "test_api_key_refresh"
        assert button.name == "Refresh"
        assert button.icon == "mdi:refresh"

    async def test_button_press(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
    ):
        """Test button press triggers coordinator refresh."""
        mock_coordinator.async_request_refresh = AsyncMock()
        button = WodifyRefreshButton(mock_coordinator, mock_config_entry)

        await button.async_press()

        mock_coordinator.async_request_refresh.assert_called_once()

    async def test_button_device_info(
        self,
        hass,  # noqa: ARG002
        mock_coordinator,
        mock_config_entry,
    ):
        """Test button device info."""
        button = WodifyRefreshButton(mock_coordinator, mock_config_entry)

        device_info = button.device_info
        assert device_info["identifiers"] == {(DOMAIN, mock_config_entry.entry_id)}
        assert device_info["name"] == "Wodify"
        assert device_info["manufacturer"] == "Wodify"
        assert device_info["model"] == "Gym Schedule"

    async def test_button_setup(self, hass, mock_config_entry, mock_coordinator):
        """Test button setup through async_setup_entry."""
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
        assert len(entities) == 1
        assert isinstance(entities[0], WodifyRefreshButton)
