"""Binary sensor platform for NetLink."""

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetlinkDataUpdateCoordinator
from .entity import NetlinkControllerEntity, NetlinkDisplayEntity


@dataclass(kw_only=True)
class NetlinkBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor entity description with value resolver."""

    value_fn: Callable[[object], bool]


DESK_BINARY_SENSORS: list[NetlinkBinarySensorEntityDescription] = [
    NetlinkBinarySensorEntityDescription(
        key="desk_moving",
        translation_key="desk_moving",
        device_class=BinarySensorDeviceClass.MOVING,
        value_fn=lambda data: data.state.moving,
    ),
]

DISPLAY_BINARY_SENSORS: list[NetlinkBinarySensorEntityDescription] = [
    NetlinkBinarySensorEntityDescription(
        key="connected",
        translation_key="display_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: getattr(data, "connected", None) is not False,
    ),
]


class NetlinkDeskBinarySensor(NetlinkControllerEntity, BinarySensorEntity):
    """Desk binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: NetlinkBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data["desk"]
        return bool(self.entity_description.value_fn(data))


class NetlinkDisplayBinarySensor(NetlinkDisplayEntity, BinarySensorEntity):
    """Display binary sensor (e.g. connected status)."""

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        bus_id: str,
        description: NetlinkBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry, bus_id)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_display_{bus_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data["displays"].get(
            self.bus_id
        ) or self.coordinator.display_info.get(self.bus_id)
        if data is None:
            return None
        return bool(self.entity_description.value_fn(data))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NetLink binary sensor entities."""
    coordinator: NetlinkDataUpdateCoordinator = entry.runtime_data

    entities: list[BinarySensorEntity] = [
        NetlinkDeskBinarySensor(coordinator, entry, description)
        for description in DESK_BINARY_SENSORS
    ]

    for bus_id in sorted(coordinator.known_bus_ids):
        for description in DISPLAY_BINARY_SENSORS:
            entities.append(
                NetlinkDisplayBinarySensor(coordinator, entry, bus_id, description)
            )

    async_add_entities(entities)

    def _on_new_display(bus_id: str) -> None:
        async_add_entities(
            [
                NetlinkDisplayBinarySensor(coordinator, entry, bus_id, description)
                for description in DISPLAY_BINARY_SENSORS
            ]
        )

    coordinator.async_add_new_display_callback(_on_new_display)
