"""Home Assistant light platform for the Sony LGTG Tapana integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .tapana_client.exceptions import CommandError, InvalidParamsError

from .const import DOMAIN, KEY_LIGHT_STATE
from .coordinator import TapanaCoordinator

_LOGGER = logging.getLogger(__name__)

# LGTG-200 color temperature range:
#   pct 0   -> warm (2700 K)
#   pct 100 -> cool (6500 K)
MIN_KELVIN = 2700   # warmest
MAX_KELVIN = 6500   # coolest


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sony Tapana light entity."""
    coordinator: TapanaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SonyTapanaLight(coordinator, entry)])


class SonyTapanaLight(CoordinatorEntity[TapanaCoordinator], LightEntity):
    """Representation of the Sony LGTG main light."""

    _attr_has_entity_name = True
    _attr_name = None  # use device name as entity name
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = MIN_KELVIN
    _attr_max_color_temp_kelvin = MAX_KELVIN

    def __init__(
        self,
        coordinator: TapanaCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_light"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.data.get("node_id", entry.entry_id)))},
            name=entry.title,
            manufacturer="Sony",
            model="LGTG Multifunctional Light",
        )

    @property
    def _light_state(self):
        return self.coordinator.data.get(KEY_LIGHT_STATE)

    @property
    def is_on(self) -> bool | None:
        state = self._light_state
        if state is None:
            return None
        return state.is_on

    @property
    def brightness(self) -> int | None:
        state = self._light_state
        if state is None or state.brightness_pct is None:
            return None
        return state.brightness_ha

    @property
    def color_temp_kelvin(self) -> int | None:
        state = self._light_state
        if state is None or state.color_temp_pct is None:
            return None
        return state.color_temp_kelvin

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, optionally setting brightness and color temp."""
        client = self.coordinator.client

        # Turn on first if needed
        if not self.is_on:
            await self.hass.async_add_executor_job(client.turn_on)

        # Apply brightness if provided
        if ATTR_BRIGHTNESS in kwargs:
            ha_brightness = kwargs[ATTR_BRIGHTNESS]
            pct = round(ha_brightness * 100 / 255)
            await self.hass.async_add_executor_job(
                client.set_brightness, max(0, min(100, pct))
            )

        # Apply color temperature if provided
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            # Convert kelvin -> pct (warmer = lower kelvin = lower pct)
            pct = round(
                (kelvin - MIN_KELVIN) * 100 / (MAX_KELVIN - MIN_KELVIN)
            )
            try:
                await self.hass.async_add_executor_job(
                    client.set_color_temperature, max(0, min(100, pct))
                )
            except (CommandError, InvalidParamsError):
                _LOGGER.warning("Failed to set color temperature to %d K", kelvin)

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.hass.async_add_executor_job(self.coordinator.client.turn_off)
        await self.coordinator.async_request_refresh()
