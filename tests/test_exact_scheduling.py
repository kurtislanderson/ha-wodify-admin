"""Regression test: binary sensors must flip at the exact scheduled time.

Before the HassJobType fix, the scheduled callbacks were classified as
HassJobType.Executor and ran in a worker thread, where async_write_ha_state()
raises. The sensor then only changed state on the next coordinator poll, so
"15 minutes before class" was really "10-15 minutes before class", depending on
where the poll landed.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.wodify.const import CONF_API_KEY, DOMAIN
from custom_components.wodify.models import WodifyClass

# Poll interval far larger than the pre-class window, so any state change we
# observe can only have come from the exact-time schedule, never from a poll.
POLL_MINUTES = 60
BEFORE_MINUTES = 15


@pytest.fixture
def entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Wodify",
        unique_id="exact_sched",
        data={
            CONF_API_KEY: "key",
            "locations": ["CrossFit inner loop"],
            "programs": ["DAILY WOD"],
        },
        options={
            "update_interval": POLL_MINUTES,
            "before_class_minutes": BEFORE_MINUTES,
            "after_block_minutes": 15,
        },
    )


async def test_class_starting_soon_flips_at_exactly_15_minutes(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Sensor turns ON at T-15:00, not at the next coordinator poll."""
    start = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
    # Setup at T-40: outside the window, and 40 < POLL_MINUTES so no poll can
    # fire before the class starts.
    freezer.move_to(start - timedelta(minutes=40))

    wodify_class = WodifyClass(
        id="1",
        name="Noon WOD",
        start_time=start,
        end_time=start + timedelta(hours=1),
        coach_name="Coach",
        location_name="CrossFit inner loop",
        program_name="DAILY WOD",
        max_attendees=20,
        current_attendees=5,
        is_cancelled=False,
    )

    with patch("custom_components.wodify.WodifyAPI") as mock_api:
        mock_api.return_value.search_classes = AsyncMock(return_value=[wodify_class])
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert hass.states.get("binary_sensor.class_starting_soon").state == "off"

        # T-15:01 — still outside the window.
        freezer.move_to(start - timedelta(minutes=15, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.class_starting_soon").state == "off"

        # T-15:00 exactly — the scheduled write must land here.
        freezer.move_to(start - timedelta(minutes=15))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.class_starting_soon").state == "on", (
            "sensor did not flip at T-15:00 — exact-time scheduling is broken, "
            "state is only tracking the coordinator poll"
        )

        # T+0 — class started, window closes on schedule too.
        freezer.move_to(start)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.class_starting_soon").state == "off"

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
