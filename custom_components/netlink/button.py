"""Button platform for NetLink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pynetlink import NetlinkCommandError, NetlinkConnectionError, NetlinkTimeoutError

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import NetlinkDataUpdateCoordinator
from .entity import NetlinkControllerEntity


@dataclass(kw_only=True)
class NetlinkButtonEntityDescription(ButtonEntityDescription):
    """Button entity description with press function."""

    command: str
    press_fn: Callable


DESK_BUTTONS: list[NetlinkButtonEntityDescription] = [
    NetlinkButtonEntityDescription(
        key="desk_stop",
        translation_key="desk_stop",
        command="command.desk.stop",
        press_fn=lambda client: client.stop_desk(),
    ),
    NetlinkButtonEntityDescription(
        key="desk_reset",
        translation_key="desk_reset",
        command="command.desk.reset",
        press_fn=lambda client: client.reset_desk(),
    ),
    NetlinkButtonEntityDescription(
        key="desk_calibrate",
        translation_key="desk_calibrate",
        command="command.desk.calibrate",
        entity_registry_enabled_default=False,
        press_fn=lambda client: client.calibrate_desk(),
    ),
]


BROWSER_BUTTONS: list[NetlinkButtonEntityDescription] = [
    NetlinkButtonEntityDescription(
        key="browser_refresh",
        translation_key="browser_refresh",
        command="command.browser.refresh",
        press_fn=lambda client: client.refresh_browser(),
    ),
]


SYSTEM_BUTTONS: list[NetlinkButtonEntityDescription] = [
    NetlinkButtonEntityDescription(
        key="device_reboot",
        translation_key="device_reboot",
        command="command.system.reboot",
        device_class=ButtonDeviceClass.RESTART,
        press_fn=lambda client: client.reboot_device(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NetLink button entities."""
    coordinator: NetlinkDataUpdateCoordinator = entry.runtime_data

    entities: list[ButtonEntity] = [
        NetlinkDeskButton(coordinator, entry, description)
        for description in DESK_BUTTONS
    ]
    entities.extend(
        NetlinkBrowserButton(coordinator, entry, description)
        for description in BROWSER_BUTTONS
    )
    entities.extend(
        NetlinkSystemButton(coordinator, entry, description)
        for description in SYSTEM_BUTTONS
    )

    async_add_entities(entities)


class NetlinkDeskButton(NetlinkControllerEntity, ButtonEntity):
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
        self.command = description.command
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    async def async_press(self) -> None:
        try:
            await self.entity_description.press_fn(self.coordinator.client)
        except (
            NetlinkCommandError,
            NetlinkConnectionError,
            NetlinkTimeoutError,
        ) as err:
            raise self._command_error(err) from err


class NetlinkBrowserButton(NetlinkControllerEntity, ButtonEntity):
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
        self.command = description.command
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    async def async_press(self) -> None:
        try:
            await self.entity_description.press_fn(self.coordinator.client)
        except (
            NetlinkCommandError,
            NetlinkConnectionError,
            NetlinkTimeoutError,
        ) as err:
            raise self._command_error(err) from err


class NetlinkSystemButton(NetlinkControllerEntity, ButtonEntity):
    """Main controller system button entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        description: NetlinkButtonEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry)
        self.entity_description = description
        self.command = description.command
        self._attr_unique_id = f"{self.device_id}_{description.key}"

    async def async_press(self) -> None:
        try:
            await self.entity_description.press_fn(self.coordinator.client)
        except (
            NetlinkCommandError,
            NetlinkConnectionError,
            NetlinkTimeoutError,
        ) as err:
            raise self._command_error(err) from err
