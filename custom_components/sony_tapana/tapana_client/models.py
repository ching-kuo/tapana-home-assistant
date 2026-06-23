"""Data models for the Sony LGTG-200 cloud API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LightState:
    """Current state of the LGTG-200 light."""

    is_on: bool | None = None
    brightness_pct: int | None = None    # 0-100
    color_temp_pct: int | None = None    # 0-100 (0=warm, 100=cool)
    nightlight_on: bool | None = None
    mode: str | None = None

    @property
    def brightness_ha(self) -> int | None:
        """Brightness scaled to Home Assistant range 0-255."""
        if self.brightness_pct is None:
            return None
        return round(self.brightness_pct * 255 / 100)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Color temperature in kelvin (2700=warm, 6500=cool)."""
        if self.color_temp_pct is None:
            return None
        # pct 0 = warm (2700K), pct 100 = cool (6500K)
        return round(2700 + self.color_temp_pct * (6500 - 2700) / 100)


@dataclass
class SensorData:
    """Environmental sensor readings from the LGTG-200."""

    temperature: float | None = None       # Celsius
    humidity: float | None = None          # %
    illuminance: float | None = None       # lumen 0-100 (ambient)
    presence: bool | None = None           # motion detected
    connected: bool | None = None          # device online


@dataclass
class NodeData:
    """Raw node data item from the API."""

    composite_id: str
    node_data_type_id: int
    value: str
    time: str | None = None
    label: str | None = None
    persistent: bool = False
    alert_level: str | None = None


@dataclass
class Node:
    """Device representation from the cloud API."""

    id: str
    uuid: str
    name: str
    version: str | None = None
    subversion: str | None = None
    edge_id: str | None = None
    user_group_id: str | None = None
    area_label: str | None = None
    is_firmware_updating: bool = False
    node_data_list: list[NodeData] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> Node:
        """Build a Node from raw API response dict."""
        raw_data = data.get("nodeDataList") or []
        node_data = [
            NodeData(
                composite_id=d.get("compositeId", ""),
                node_data_type_id=int(d.get("nodeDataTypeId", 0)),
                value=str(d.get("value", "")),
                time=d.get("time"),
                label=d.get("label"),
                persistent=bool(d.get("persistent", False)),
                alert_level=d.get("alertLevel"),
            )
            for d in raw_data
            if d
        ]
        return cls(
            id=str(data.get("id", "")),
            uuid=str(data.get("uuid", "")),
            name=str(data.get("name", "")),
            version=data.get("version"),
            subversion=data.get("subversion"),
            edge_id=str(data.get("edgeId")) if data.get("edgeId") else None,
            user_group_id=str(data.get("userGroupId")) if data.get("userGroupId") else None,
            area_label=data.get("areaLabel"),
            is_firmware_updating=bool(data.get("isFirmwareUpdating", False)),
            node_data_list=node_data,
        )


@dataclass
class ActionResult:
    """Result of a postActions mutation."""

    notification_id: str | None
    node_action_type: str | None
    timestamp: str | None
    error_code: int | None
    recipe_id: str | None = None

    @property
    def success(self) -> bool:
        """True when the command was accepted (errorCode is null)."""
        return self.error_code is None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> ActionResult:
        """Build ActionResult from raw API response."""
        return cls(
            notification_id=data.get("notificationId"),
            node_action_type=data.get("nodeActionType"),
            timestamp=data.get("timestamp"),
            error_code=data.get("errorCode"),
            recipe_id=data.get("recipeId"),
        )
