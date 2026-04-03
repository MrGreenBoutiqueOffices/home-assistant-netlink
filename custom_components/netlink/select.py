"""Select platform for Netlink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pynetlink import NetlinkCommandError, NetlinkConnectionError, NetlinkTimeoutError

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NetlinkDataUpdateCoordinator
from .entity import NetlinkDisplayEntity


@dataclass(kw_only=True)
class NetlinkSelectEntityDescription(SelectEntityDescription):
    """Select entity description."""

    select_fn: Callable


DISPLAY_SELECTS: list[NetlinkSelectEntityDescription] = [
    NetlinkSelectEntityDescription(
        key="source",
        translation_key="display_source",
        select_fn=lambda client, bus_id, option: client.set_display_source(
            bus_id, option
        ),
    ),
]


class NetlinkDisplaySelect(NetlinkDisplayEntity, SelectEntity):
    """Display select."""

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        bus_id: str,
        description: NetlinkSelectEntityDescription,
    ) -> None:
        super().__init__(coordinator, entry, bus_id)
        self.entity_description = description
        self._attr_unique_id = f"{self.device_id}_display_{bus_id}_{description.key}"
        # Seed options from initial coordinator data so they remain available
        # even when the display temporarily disappears (e.g. after power-off).
        initial = coordinator.data.get("displays", {}).get(bus_id)
        self._attr_options = (
            [str(item) for item in initial.source_options] if initial else []
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update options when coordinator data arrives, preserve last known on absence."""
        data = self.coordinator.data.get("displays", {}).get(self.bus_id)
        if data is not None:
            self._attr_options = [str(item) for item in data.source_options]
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        return self.coordinator.data["displays"][self.bus_id].state.source

    async def async_select_option(self, option: str) -> None:
        try:
            await self.entity_description.select_fn(
                self.coordinator.client, self.bus_id, option
            )
        except NetlinkCommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"name": self.device_name},
            ) from err
        except (NetlinkConnectionError, NetlinkTimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_unavailable",
                translation_placeholders={"name": self.device_name},
            ) from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Netlink select entities."""
    coordinator: NetlinkDataUpdateCoordinator = entry.runtime_data

    entities: list[SelectEntity] = []
    display_bus_ids = set(coordinator.display_info.keys()) | set(
        coordinator.data["displays"].keys()
    )
    for bus_id in sorted(display_bus_ids):
        # Only create source select for displays with source support
        state = coordinator.data["displays"].get(bus_id)
        if state and getattr(state, "supports", {}).get("source"):
            for description in DISPLAY_SELECTS:
                entities.append(
                    NetlinkDisplaySelect(coordinator, entry, bus_id, description)
                )

    async_add_entities(entities)

    def _on_new_display(bus_id: str) -> None:
        state = coordinator.data["displays"].get(bus_id)
        if state and getattr(state, "supports", {}).get("source"):
            async_add_entities(
                [
                    NetlinkDisplaySelect(coordinator, entry, bus_id, description)
                    for description in DISPLAY_SELECTS
                ]
            )

    coordinator.async_add_new_display_callback(_on_new_display)
