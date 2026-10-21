"""Test diagnostics."""

from unittest.mock import Mock

from custom_components.wodify.const import CONF_API_KEY
from custom_components.wodify.diagnostics import async_get_config_entry_diagnostics
from custom_components.wodify.models import WodifyRuntimeData


async def test_diagnostics_redacts_api_key(hass, mock_config_entry, mock_coordinator):
    """api_key must never appear in diagnostics output."""
    mock_config_entry.add_to_hass(hass)
    mock_coordinator.api_connected = True
    mock_coordinator.last_error = None
    mock_coordinator.last_successful_update = None
    mock_coordinator.data = []
    mock_config_entry.runtime_data = WodifyRuntimeData(
        coordinator=mock_coordinator, api=Mock(), event_manager=Mock()
    )

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert result["entry"]["data"][CONF_API_KEY] == "**REDACTED**"
    assert result["coordinator"]["api_connected"] is True
    assert result["coordinator"]["class_count"] == 0
