"""DataUpdateCoordinator for Wodify."""
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WodifyApiClient
from .const import CLASS_BLOCK_THRESHOLD, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class WodifyDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Wodify data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: WodifyApiClient,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Wodify",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            classes = await self.client.async_get_classes()
            
            # Sort classes by start time
            sorted_classes = sorted(
                classes,
                key=lambda x: datetime.fromisoformat(x["start_time"])
            )
            
            # Find current and upcoming classes
            now = datetime.now()
            upcoming_classes = []
            current_class = None
            
            for cls in sorted_classes:
                start_time = datetime.fromisoformat(cls["start_time"])
                end_time = datetime.fromisoformat(cls["end_time"])
                
                if start_time <= now <= end_time:
                    current_class = cls
                elif start_time > now:
                    upcoming_classes.append(cls)
            
            # Detect class blocks (classes within 30 minutes of each other)
            class_blocks = []
            if current_class or upcoming_classes:
                current_block = []
                
                # Start with current class if exists
                if current_class:
                    current_block.append(current_class)
                    last_end_time = datetime.fromisoformat(current_class["end_time"])
                elif upcoming_classes:
                    current_block.append(upcoming_classes[0])
                    last_end_time = datetime.fromisoformat(upcoming_classes[0]["end_time"])
                    upcoming_classes = upcoming_classes[1:]
                
                # Check for back-to-back classes
                for cls in upcoming_classes:
                    start_time = datetime.fromisoformat(cls["start_time"])
                    time_diff = (start_time - last_end_time).total_seconds()
                    
                    if time_diff <= CLASS_BLOCK_THRESHOLD:
                        current_block.append(cls)
                        last_end_time = datetime.fromisoformat(cls["end_time"])
                    else:
                        if current_block:
                            class_blocks.append(current_block)
                        current_block = [cls]
                        last_end_time = datetime.fromisoformat(cls["end_time"])
                
                if current_block:
                    class_blocks.append(current_block)
            
            # Determine if currently in a class block
            in_class_block = False
            current_block_info = None
            
            if class_blocks:
                first_block = class_blocks[0]
                block_start = datetime.fromisoformat(first_block[0]["start_time"])
                block_end = datetime.fromisoformat(first_block[-1]["end_time"])
                
                if block_start <= now <= block_end:
                    in_class_block = True
                    current_block_info = {
                        "start": block_start.isoformat(),
                        "end": block_end.isoformat(),
                        "classes": first_block,
                    }
            
            # Find next class
            next_class = None
            if upcoming_classes:
                next_class = upcoming_classes[0]
            elif class_blocks and not in_class_block:
                next_class = class_blocks[0][0]
            
            return {
                "classes": sorted_classes,
                "upcoming_classes": upcoming_classes,
                "current_class": current_class,
                "class_blocks": class_blocks,
                "in_class_block": in_class_block,
                "current_block_info": current_block_info,
                "next_class": next_class,
                "last_update": now.isoformat(),
            }
            
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
