"""Select platform for Netlink."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data["displays"][self.bus_id]
        return data.state.source

    @property
    def options(self) -> list[str]:
        data = self.coordinator.data["displays"][self.bus_id]
        source_options = data.source_options
        return [str(item) for item in source_options]

    async def async_select_option(self, option: str) -> None:
        await self.entity_description.select_fn(
            self.coordinator.client, self.bus_id, option
        )


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
