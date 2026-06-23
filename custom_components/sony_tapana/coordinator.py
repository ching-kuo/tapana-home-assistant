"""DataUpdateCoordinator for the Sony Tapana integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .tapana_client import TapanaClient
from .tapana_client.client import _parse_light_state, _parse_sensor_data
from .tapana_client.exceptions import ApiError, AuthenticationError

from .const import KEY_LIGHT_STATE, KEY_SENSOR_DATA, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TapanaCoordinator(DataUpdateCoordinator):
    """Poll the Tapana cloud API and distribute data to platform entities."""

    def __init__(self, hass: HomeAssistant, client: TapanaClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Sony Tapana",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        """Fetch both light state and sensor data in one node query."""
        try:
            node = await self.hass.async_add_executor_job(self.client.get_node)
        except AuthenticationError as exc:
            raise UpdateFailed(f"Authentication error: {exc}") from exc
        except ApiError as exc:
            raise UpdateFailed(f"API error: {exc}") from exc

        return {
            KEY_LIGHT_STATE: _parse_light_state(node),
            KEY_SENSOR_DATA: _parse_sensor_data(node),
        }
