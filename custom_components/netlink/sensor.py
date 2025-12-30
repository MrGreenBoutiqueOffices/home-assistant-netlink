"""Sensor platform for Netlink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetlinkDataUpdateCoordinator
from .entity import NetlinkDeskEntity, NetlinkDisplayEntity


@dataclass(kw_only=True)
class NetlinkSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description with value resolver."""

    value_fn: Callable[[object], int | float | str | bool]


DESK_SENSORS: list[NetlinkSensorEntityDescription] = [
    NetlinkSensorEntityDescription(
        key="desk_height",
        translation_key="desk_height",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.state.height,
    ),
    NetlinkSensorEntityDescription(
        key="desk_mode",
        translation_key="desk_mode",
        value_fn=lambda data: data.state.mode,
    ),
    NetlinkSensorEntityDescription(
        key="desk_error",
        translation_key="desk_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.state.error,
    ),
]


DISPLAY_SENSORS: list[NetlinkSensorEntityDescription] = [
    NetlinkSensorEntityDescription(
        key="brightness",
        translation_key="display_brightness",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.state.brightness,
    ),
    NetlinkSensorEntityDescription(
        key="volume",
        translation_key="display_volume",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.state.volume,
    ),
    NetlinkSensorEntityDescription(
        key="power",
        translation_key="display_power",
        value_fn=lambda data: data.state.power,
    ),
    NetlinkSensorEntityDescription(
        key="source",
        translation_key="display_source",
        value_fn=lambda data: data.state.source,
    ),
    NetlinkSensorEntityDescription(
        key="error",
        translation_key="display_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.state.error,
    ),
]


class NetlinkDeskSensor(NetlinkDeskEntity, SensorEntity):
    """Desk sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: NetlinkSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    @property
    def native_value(self) -> int | float | str | bool | None:
        data = self.coordinator.data["desk"]
        return self.entity_description.value_fn(data)


class NetlinkDisplaySensor(NetlinkDisplayEntity, SensorEntity):
    """Display sensor."""

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        bus_id: str,
        description: NetlinkSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry, bus_id)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_display_{bus_id}_{description.key}"

    @property
    def native_value(self) -> int | float | str | bool | None:
        data = self.coordinator.data["displays"][self.bus_id]
        return self.entity_description.value_fn(data)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netlink sensor entities."""
    coordinator: NetlinkDataUpdateCoordinator = entry.runtime_data

    entities: list[SensorEntity] = [
        NetlinkDeskSensor(coordinator, entry, description)
        for description in DESK_SENSORS
    ]

    display_bus_ids = set(coordinator.display_info.keys()) | set(
        coordinator.data["displays"].keys()
    )
    for bus_id in sorted(display_bus_ids):
        for description in DISPLAY_SENSORS:
            entities.append(
                NetlinkDisplaySensor(coordinator, entry, bus_id, description)
            )

    async_add_entities(entities)
