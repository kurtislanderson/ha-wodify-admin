"""Global fixtures for tests."""

import threading
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:  # pragma: no cover - optional dependency in tests
    import pytest_homeassistant_custom_component.plugins as hac_plugins
except ModuleNotFoundError:  # pragma: no cover
    hac_plugins = SimpleNamespace(threading=threading)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wodify.api import WodifyAPI
from custom_components.wodify.const import CONF_API_KEY, DOMAIN
from custom_components.wodify.models import WodifyClass

# Enable custom integrations for all tests
pytest_plugins = "pytest_homeassistant_custom_component"

# Real API key for testing with Wodify API
REAL_API_KEY = "YfaqPxyQ6e1LIA6yTsMkg7hrdlLbOsaG7E0yUmDG"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):  # noqa: ARG001
    """Automatically enable custom integrations."""
    yield


@pytest.fixture(autouse=True)
def allow_asyncio_shutdown_thread(monkeypatch: pytest.MonkeyPatch):
    """Rename asyncio's safe shutdown thread so HA plugin accepts it."""

    original_enumerate = threading.enumerate

    def patched_enumerate() -> list[threading.Thread]:
        threads = original_enumerate()
        for thread in threads:
            if "_run_safe_shutdown_loop" in thread.name and not thread.name.startswith(
                "waitpid-"
            ):
                thread.name = f"waitpid-{thread.name}"
        return threads

    monkeypatch.setattr(threading, "enumerate", patched_enumerate)
    monkeypatch.setattr(hac_plugins.threading, "enumerate", patched_enumerate)
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry with real API key."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Wodify (CrossFit inner loop)",
        unique_id="test_api_key",
        data={
            CONF_API_KEY: REAL_API_KEY,
            "locations": ["CrossFit inner loop"],
            "programs": ["DAILY WOD"],
        },
        options={
            "update_interval": 5,
            "before_class_minutes": 15,
            "after_block_minutes": 15,
        },
    )


@pytest.fixture
async def api_client(hass):
    """Create API client fixture with real API key."""
    session = async_get_clientsession(hass)
    api = WodifyAPI(REAL_API_KEY, session, hass)
    yield api


@pytest.fixture
def mock_wodify_class() -> WodifyClass:
    """Return a mock Wodify class."""
    return WodifyClass(
        id="123",
        name="CrossFit",
        start_time=datetime(2024, 1, 1, 17, 30, tzinfo=UTC),
        end_time=datetime(2024, 1, 1, 18, 30, tzinfo=UTC),
        coach_name="Coach Mike",
        location_name="Downtown",
        program_name="CrossFit",
        max_attendees=20,
        current_attendees=15,
        is_cancelled=False,
    )


@pytest.fixture
def mock_wodify_api():
    """Return a mock Wodify API client."""
    with patch("custom_components.wodify.api.WodifyAPI") as mock:
        api_instance = Mock()
        mock.return_value = api_instance
        yield api_instance


@pytest.fixture
def mock_coordinator():
    """Return a mock coordinator."""
    coordinator = Mock()
    coordinator.data = []
    coordinator.last_update_success = True
    return coordinator


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Wodify integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
async def real_api_setup(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    """Set up real API in hass.data for testing."""
    session = async_get_clientsession(hass)
    api = WodifyAPI(REAL_API_KEY, session, hass)

    # Create a mock coordinator that has the real API
    coordinator = Mock()
    coordinator.api = api
    coordinator.data = []
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_set_filters = AsyncMock()

    event_manager = Mock()
    event_manager.update_timing = Mock()

    runtime_data = {
        "coordinator": coordinator,
        "event_manager": event_manager,
        "api": api,
    }

    hass.data[DOMAIN] = {mock_config_entry.entry_id: runtime_data}
    mock_config_entry.add_to_hass(hass)

    return mock_config_entry, coordinator, api
