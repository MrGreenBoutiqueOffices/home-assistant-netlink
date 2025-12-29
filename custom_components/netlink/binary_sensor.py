"""Binary sensor platform for Netlink."""

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
from .entity import NetlinkDeskEntity


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


class NetlinkDeskBinarySensor(NetlinkDeskEntity, BinarySensorEntity):
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netlink binary sensor entities."""
    coordinator: NetlinkDataUpdateCoordinator = entry.runtime_data

    entities: list[BinarySensorEntity] = [
        NetlinkDeskBinarySensor(coordinator, entry, description)
        for description in DESK_BINARY_SENSORS
    ]

    async_add_entities(entities)
