"""Home Assistant sensor platform for the Sony LGTG Tapana integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfIlluminance,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .tapana_client.models import SensorData

from .const import DOMAIN, KEY_SENSOR_DATA
from .coordinator import TapanaCoordinator


@dataclass(frozen=True, kw_only=True)
class TapanaSensorDescription(SensorEntityDescription):
    """Sensor description extended with a value extractor."""

    value_fn: Callable[[SensorData], float | bool | None]


SENSORS: tuple[TapanaSensorDescription, ...] = (
    TapanaSensorDescription(
        key="temperature",
        name="Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda s: s.temperature,
    ),
    TapanaSensorDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda s: s.humidity,
    ),
    TapanaSensorDescription(
        key="illuminance",
        name="Illuminance",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfIlluminance.LUX,
        value_fn=lambda s: s.illuminance,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sony Tapana sensor entities."""
    coordinator: TapanaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SonyTapanaSensor(coordinator, entry, description)
        for description in SENSORS
    )


class SonyTapanaSensor(CoordinatorEntity[TapanaCoordinator], SensorEntity):
    """A sensor entity for the Sony LGTG device."""

    entity_description: TapanaSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TapanaCoordinator,
        entry: ConfigEntry,
        description: TapanaSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(entry.data.get("node_id", entry.entry_id)))},
            name=entry.title,
            manufacturer="Sony",
            model="LGTG Multifunctional Light",
        )

    @property
    def native_value(self) -> float | bool | None:
        sensor_data: SensorData | None = self.coordinator.data.get(KEY_SENSOR_DATA)
        if sensor_data is None:
            return None
        return self.entity_description.value_fn(sensor_data)
