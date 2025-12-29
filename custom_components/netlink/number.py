"""Number platform for Netlink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import logging

from pynetlink.exceptions import NetlinkCommandError

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetlinkDataUpdateCoordinator
from .entity import NetlinkDeskEntity, NetlinkDisplayEntity

_LOGGER = logging.getLogger(__name__)

def _display_supports(
    coordinator: NetlinkDataUpdateCoordinator, bus_id: str, capability: str
) -> bool | None:
    """Check if display supports a capability."""
    for source in (
        coordinator.data["displays"].get(bus_id),
        coordinator.display_info.get(bus_id),
    ):
        if source is not None:
            supports = getattr(source, "supports", None)
            if isinstance(supports, dict) and capability in supports:
                return bool(supports[capability])
    return None


@dataclass(kw_only=True)
class NetlinkNumberEntityDescription(NumberEntityDescription):
    """Number entity description with value resolver."""

    value_fn: Callable[[object], int | float]


DESK_NUMBERS: list[NetlinkNumberEntityDescription] = [
    NetlinkNumberEntityDescription(
        key="desk_target_height",
        translation_key="desk_target_height",
        native_min_value=62,
        native_max_value=127,
        native_step=1,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        value_fn=lambda data: data.state.height,
    ),
]


DISPLAY_NUMBERS: list[NetlinkNumberEntityDescription] = [
    NetlinkNumberEntityDescription(
        key="brightness",
        translation_key="display_brightness",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.state.brightness,
    ),
    NetlinkNumberEntityDescription(
        key="volume",
        translation_key="display_volume",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.state.volume,
    ),
]


class NetlinkDeskNumber(NetlinkDeskEntity, NumberEntity):
    """Desk number entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: NetlinkNumberEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_desk_{description.key}"

    @property
    def native_value(self) -> int | float | None:
        data = self.coordinator.data["desk"]
        return self.entity_description.value_fn(data)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.set_desk_height(value)


class NetlinkDisplayNumber(NetlinkDisplayEntity, NumberEntity):
    """Display number entity."""

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        bus_id: str,
        description: NetlinkNumberEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry, bus_id)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_display_{bus_id}_{description.key}"

    @property
    def native_value(self) -> int | float | None:
        data = self.coordinator.data["displays"][self.bus_id]
        return self.entity_description.value_fn(data)

    def _supports(self, capability: str) -> bool | None:
        return _display_supports(self.coordinator, self.bus_id, capability)

    async def async_set_native_value(self, value: float) -> None:
        if self.entity_description.key == "brightness":
            if self._supports("brightness") is False:
                _LOGGER.debug("Display %s does not support brightness", self.bus_id)
                return
            try:
                await self.coordinator.client.set_display_brightness(
                    self.bus_id, int(value)
                )
            except NetlinkCommandError as err:
                if str(err) == "unsupported_command":
                    _LOGGER.warning(
                        "Display %s rejected brightness change (unsupported)",
                        self.bus_id,
                    )
                    return
                raise
        elif self.entity_description.key == "volume":
            if self._supports("volume") is False:
                _LOGGER.debug("Display %s does not support volume", self.bus_id)
                return
            try:
                await self.coordinator.client.set_display_volume(
                    self.bus_id, int(value)
                )
            except NetlinkCommandError as err:
                if str(err) == "unsupported_command":
                    _LOGGER.warning(
                        "Display %s rejected volume change (unsupported)", self.bus_id
                    )
                    return
                raise
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netlink number entities."""
    coordinator: NetlinkDataUpdateCoordinator = entry.runtime_data

    entities: list[NumberEntity] = [
        NetlinkDeskNumber(coordinator, entry, description)
        for description in DESK_NUMBERS
    ]

    display_bus_ids = set(coordinator.display_info.keys()) | set(
        coordinator.data["displays"].keys()
    )
    for bus_id in sorted(display_bus_ids):
        for description in DISPLAY_NUMBERS:
            supported = _display_supports(coordinator, bus_id, description.key)
            if supported is False:
                continue
            entities.append(
                NetlinkDisplayNumber(coordinator, entry, bus_id, description)
            )

    async_add_entities(entities)
