"""Home Assistant binary sensor platform for the Sony LGTG Tapana integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .tapana_client.models import SensorData

from .const import CONF_NODE_ID, DOMAIN, KEY_SENSOR_DATA
from .coordinator import TapanaCoordinator


@dataclass(frozen=True, kw_only=True)
class TapanaBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor description extended with a value extractor."""

    value_fn: Callable[[SensorData], bool | None]


BINARY_SENSORS: tuple[TapanaBinarySensorDescription, ...] = (
    TapanaBinarySensorDescription(
        key="presence",
        name="Presence",
        device_class=BinarySensorDeviceClass.MOTION,
        value_fn=lambda s: s.presence,
    ),
    TapanaBinarySensorDescription(
        key="connected",
        name="Connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda s: s.connected,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sony Tapana binary sensor entities."""
    coordinator: TapanaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SonyTapanaBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSORS
    )


class SonyTapanaBinarySensor(CoordinatorEntity[TapanaCoordinator], BinarySensorEntity):
    """A binary sensor entity for the Sony LGTG device."""

    entity_description: TapanaBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TapanaCoordinator,
        entry: ConfigEntry,
        description: TapanaBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.data.get(CONF_NODE_ID, entry.entry_id)))},
            name=entry.title,
            manufacturer="Sony",
            model="LGTG Multifunctional Light",
        )

    @property
    def is_on(self) -> bool | None:
        sensor_data: SensorData | None = self.coordinator.data.get(KEY_SENSOR_DATA)
        if sensor_data is None:
            return None
        return self.entity_description.value_fn(sensor_data)
