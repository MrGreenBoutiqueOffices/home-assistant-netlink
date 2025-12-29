"""Button platform for Netlink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetlinkDataUpdateCoordinator
from .entity import NetlinkDeskEntity, NetlinkMainEntity


@dataclass(kw_only=True)
class NetlinkButtonEntityDescription(ButtonEntityDescription):
    """Button entity description with press function."""

    press_fn: Callable


DESK_BUTTONS: list[NetlinkButtonEntityDescription] = [
    NetlinkButtonEntityDescription(
        key="desk_stop",
        translation_key="desk_stop",
        press_fn=lambda client: client.stop_desk(),
    ),
    NetlinkButtonEntityDescription(
        key="desk_reset",
        translation_key="desk_reset",
        press_fn=lambda client: client.reset_desk(),
    ),
    NetlinkButtonEntityDescription(
        key="desk_calibrate",
        translation_key="desk_calibrate",
        entity_registry_enabled_default=False,
        press_fn=lambda client: client.calibrate_desk(),
    ),
]


MAIN_BUTTONS: list[NetlinkButtonEntityDescription] = [
    NetlinkButtonEntityDescription(
        key="browser_refresh",
        translation_key="browser_refresh",
        press_fn=lambda client: client.refresh_browser(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netlink button entities."""
    coordinator: NetlinkDataUpdateCoordinator = entry.runtime_data

    entities: list[ButtonEntity] = [
        NetlinkDeskButton(coordinator, entry, description)
        for description in DESK_BUTTONS
    ]
    entities.extend(
        NetlinkMainButton(coordinator, entry, description)
        for description in MAIN_BUTTONS
    )

    async_add_entities(entities)


class NetlinkDeskButton(NetlinkDeskEntity, ButtonEntity):
    """Desk button entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: NetlinkButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator.client)


class NetlinkMainButton(NetlinkMainEntity, ButtonEntity):
    """Main controller button entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: NetlinkButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator.client)
