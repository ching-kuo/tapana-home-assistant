"""Home Assistant light platform for the Sony LGTG Tapana integration."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import replace
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

from .tapana_client.const import NATIVE_MAX, NATIVE_MIN
from .tapana_client.exceptions import CommandError, InvalidParamsError

from .const import DOMAIN, KEY_LIGHT_STATE
from .coordinator import TapanaCoordinator

_LOGGER = logging.getLogger(__name__)

# LGTG-200 color temperature range (device native scale is 1-255):
#   native 1   -> warm (2700 K)
#   native 255 -> cool (6500 K)
MIN_KELVIN = 2700   # warmest
MAX_KELVIN = 6500   # coolest

# Delay before re-pulling the lagging cloud shadow after a command; see
# _apply_local_state for the mechanism.
# ponytail: fixed delay tuned by observation; make configurable if it drifts
RECONCILE_DELAY_S = 10
# Brightness and color temperature share the device's native 1-255 scale
# (NATIVE_MIN/NATIVE_MAX imported from the client const).

# Serialize cloud commands so optimistic updates follow device command order.
PARALLEL_UPDATES = 1


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
        self._optimistic_changes: dict[str, Any] | None = None
        self._reconcile_enabled = True
        self._reconcile_task: asyncio.Task[None] | None = None
        self._attr_unique_id = f"{entry.entry_id}_light"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.data.get("node_id", entry.entry_id)))},
            name=entry.title,
            manufacturer="Sony",
            model="LGTG Multifunctional Light",
        )

    @property
    def _light_state(self):
        state = self.coordinator.data.get(KEY_LIGHT_STATE)
        if state is None or self._optimistic_changes is None:
            return state
        return replace(state, **self._optimistic_changes)

    @property
    def is_on(self) -> bool | None:
        state = self._light_state
        if state is None:
            return None
        return state.is_on

    @property
    def brightness(self) -> int | None:
        state = self._light_state
        if state is None:
            return None
        # Device brightness is already on HA's 0-255 scale.
        return state.brightness

    @property
    def color_temp_kelvin(self) -> int | None:
        state = self._light_state
        if state is None:
            return None
        return state.color_temp_kelvin

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on, optionally setting brightness and color temp."""
        await self._async_cancel_reconcile()

        client = self.coordinator.client
        prev = self._light_state
        was_off = not self.is_on

        # Track what actually reached the device so a mid-sequence command
        # failure still records the partial result before re-raising.
        is_on: bool | None = None
        sent_brightness: int | None = None
        sent_ct: int | None = None
        try:
            if was_off:
                await self.hass.async_add_executor_job(client.turn_on)
                is_on = True

            # powerControl "true" resets the device to a low built-in default,
            # so when the caller gives no explicit values, restore the pre-off
            # brightness and color temperature from the last known state.
            brightness = kwargs.get(ATTR_BRIGHTNESS)
            if brightness is None and was_off and prev is not None:
                brightness = prev.brightness
            if brightness is not None:
                # HA's 0-255 scale matches the device's native scale 1:1; the
                # device rejects 0, so clamp to 1-255.
                brightness = max(NATIVE_MIN, min(NATIVE_MAX, brightness))
                await self.hass.async_add_executor_job(
                    client.set_brightness, brightness
                )
                sent_brightness = brightness

            native_ct = None
            kelvin = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
            if kelvin is not None:
                # Convert kelvin -> native 1-255 (warmer = lower native).
                frac = (kelvin - MIN_KELVIN) / (MAX_KELVIN - MIN_KELVIN)
                native_ct = round(NATIVE_MIN + frac * (NATIVE_MAX - NATIVE_MIN))
                native_ct = max(NATIVE_MIN, min(NATIVE_MAX, native_ct))
            elif was_off and prev is not None:
                native_ct = prev.color_temp_native
            if native_ct is not None:
                try:
                    await self.hass.async_add_executor_job(
                        client.set_color_temperature, native_ct
                    )
                    sent_ct = native_ct
                except (CommandError, InvalidParamsError):
                    _LOGGER.warning(
                        "Failed to set color temperature to native %d", native_ct
                    )
        finally:
            if is_on is not None or sent_brightness is not None or sent_ct is not None:
                self._apply_local_state(
                    is_on=is_on,
                    brightness=sent_brightness,
                    color_temp_native=sent_ct,
                )
            self._schedule_reconcile()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_cancel_reconcile()

        turned_off = False
        try:
            await self.hass.async_add_executor_job(self.coordinator.client.turn_off)
            turned_off = True
        finally:
            if turned_off:
                self._apply_local_state(is_on=False)
            self._schedule_reconcile()

    def _apply_local_state(
        self,
        is_on: bool | None = None,
        brightness: int | None = None,
        color_temp_native: int | None = None,
    ) -> None:
        """Reflect successful command parts in HA immediately.

        The cloud shadow lags device commands, so refreshing right away reads
        stale data. Instead, push the new state through the coordinator
        (async_set_updated_data also resets the poll timer, so the regular
        30 s poll cannot revert this with stale data mid-window).
        """
        state = self._light_state
        if state is not None:
            changes = dict(self._optimistic_changes or {})
            if is_on is not None:
                changes["is_on"] = is_on
            if brightness is not None:
                changes["brightness"] = brightness
            if color_temp_native is not None:
                changes["color_temp_native"] = color_temp_native
            self._optimistic_changes = changes
            self.coordinator.async_set_updated_data(
                {**self.coordinator.data, KEY_LIGHT_STATE: replace(state, **changes)}
            )

    def _schedule_reconcile(self) -> None:
        """Re-pull the lagging cloud shadow after the settle window."""
        if not self._reconcile_enabled:
            return
        if self._reconcile_task is not None:
            self._reconcile_task.cancel()
        self._reconcile_task = self.hass.async_create_task(
            self._async_delayed_reconcile()
        )

    async def _async_delayed_reconcile(self) -> None:
        """Pull the cloud shadow to confirm the optimistic state."""
        this_task = asyncio.current_task()
        optimistic_changes = self._optimistic_changes
        try:
            await asyncio.sleep(RECONCILE_DELAY_S)
            await self.coordinator.async_refresh()
            if self._optimistic_changes is optimistic_changes:
                self._optimistic_changes = None
                self.async_write_ha_state()
        finally:
            if self._reconcile_task is this_task:
                self._reconcile_task = None

    async def _async_cancel_reconcile(self) -> None:
        """Cancel and drain a pending or in-flight reconcile."""
        task = self._reconcile_task
        if task is None:
            return
        self._reconcile_task = None
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending reconcile task."""
        self._reconcile_enabled = False
        await self._async_cancel_reconcile()
