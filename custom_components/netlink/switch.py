"""Switch platform for Netlink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetlinkDataUpdateCoordinator
from .entity import NetlinkDeskEntity, NetlinkDisplayEntity


@dataclass(kw_only=True)
class NetlinkSwitchEntityDescription(SwitchEntityDescription):
    """Switch entity description with value resolver."""

    value_fn: Callable[[object], str | bool]


DESK_SWITCHES: list[NetlinkSwitchEntityDescription] = [
    NetlinkSwitchEntityDescription(
        key="beep",
        translation_key="desk_beep",
        value_fn=lambda data: data.state.beep,
    ),
]


DISPLAY_SWITCHES: list[NetlinkSwitchEntityDescription] = [
    NetlinkSwitchEntityDescription(
        key="power",
        translation_key="display_power",
        device_class=SwitchDeviceClass.OUTLET,
        value_fn=lambda data: data.state.power,
    ),
]


class NetlinkDeskSwitch(NetlinkDeskEntity, SwitchEntity):
    """Desk switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: NetlinkSwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_desk_{description.key}"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data["desk"]
        value = self.entity_description.value_fn(data)
        if isinstance(value, str):
            return value == "on"
        return bool(value)

    async def async_turn_on(self, **_: Any) -> None:
        await self.coordinator.client.set_desk_beep(state="on")

    async def async_turn_off(self, **_: Any) -> None:
        await self.coordinator.client.set_desk_beep(state="off")


class NetlinkDisplaySwitch(NetlinkDisplayEntity, SwitchEntity):
    """Display switch."""

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        bus_id: str,
        description: NetlinkSwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry, bus_id)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_display_{bus_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data["displays"][self.bus_id]
        value = self.entity_description.value_fn(data)
        if isinstance(value, str):
            return value == "on"
        return bool(value)

    async def async_turn_on(self, **_: Any) -> None:
        await self.coordinator.client.set_display_power(self.bus_id, "on")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_: Any) -> None:
        await self.coordinator.client.set_display_power(self.bus_id, "off")
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netlink switch entities."""
    coordinator: NetlinkDataUpdateCoordinator = entry.runtime_data

    entities: list[SwitchEntity] = [
        NetlinkDeskSwitch(coordinator, entry, description)
        for description in DESK_SWITCHES
    ]

    display_bus_ids = set(coordinator.display_info.keys()) | set(
        coordinator.data["displays"].keys()
    )
    for bus_id in sorted(display_bus_ids):
        for description in DISPLAY_SWITCHES:
            entities.append(
                NetlinkDisplaySwitch(coordinator, entry, bus_id, description)
            )

    async_add_entities(entities)
