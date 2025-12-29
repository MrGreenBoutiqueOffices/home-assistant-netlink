"""DataUpdateCoordinator for Netlink."""

from __future__ import annotations

from typing import Any

from pynetlink import (
    Desk,
    DeviceInfo,
    Display,
    DisplaySummary,
    NetlinkClient,
    NetlinkDataError,
    NetlinkError,
    EVENT_DESK_STATE,
    EVENT_DEVICE_INFO,
    EVENT_DISPLAY_STATE,
    EVENT_DISPLAYS_LIST,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

import logging

_LOGGER = logging.getLogger(__name__)


class NetlinkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Netlink data via WebSocket."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NetlinkClient,
        device_id: str,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Netlink {device_id}",
            update_interval=None,  # WebSocket push only, no polling!
        )
        self.client = client
        self.device_id = device_id
        self.device_info: DeviceInfo | None = None
        self.display_info: dict[str, DisplaySummary] = {}
        self._initial_refresh_done = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch initial data via REST API.

        This is called once during setup to get initial state.
        After that, WebSocket events keep state updated.
        """
        try:
            device_info = await self.client.get_device_info()
            self.device_info = device_info

            # Fetch initial desk status
            desk_status = await self.client.get_desk_status()

            # Fetch display list and states
            displays = await self.client.get_displays()
            self.display_info = {str(display.bus): display for display in displays}
            display_states: dict[str, Display] = {}
            for display in displays:
                try:
                    state = await self.client.get_display_status(display.bus)
                    display_states[str(display.bus)] = state
                except NetlinkError as err:
                    _LOGGER.warning(
                        "Failed to get display %s status: %s", display.bus, err
                    )

            return {
                "desk": desk_status,
                "displays": display_states,
            }
        except (NetlinkError, NetlinkDataError) as err:
            raise UpdateFailed(err) from err

    async def async_setup(self) -> None:
        """Setup WebSocket listeners and fetch initial data."""

        # Register WebSocket event handlers
        @self.client.on("connect")
        async def on_connect(_: dict[str, Any]) -> None:
            """Handle WebSocket reconnect events."""
            if self._initial_refresh_done:
                await self.async_refresh()

        @self.client.on("disconnect")
        async def on_disconnect(_: dict[str, Any]) -> None:
            """Handle WebSocket disconnect events."""
            self.last_update_success = False
            self.async_update_listeners()

        @self.client.on(EVENT_DEVICE_INFO)
        async def on_device_info(data: dict[str, Any]) -> None:
            """Handle device info updates."""
            self.device_info = DeviceInfo.from_dict(data)

        @self.client.on(EVENT_DESK_STATE)
        async def on_desk_state(data: dict[str, Any]) -> None:
            """Handle desk state updates."""
            try:
                desk = Desk.from_dict(data)
            except NetlinkDataError as exc:
                _LOGGER.warning("Skipping incomplete desk state: %s", exc)
                return

            current = self.data or {}
            self.async_set_updated_data(
                {
                    **current,
                    "desk": desk,
                    "displays": current.get("displays", {}),
                }
            )

        @self.client.on(EVENT_DISPLAY_STATE)
        async def on_display_state(data: dict[str, Any]) -> None:
            """Handle display state updates."""
            bus_id = str(data["bus"])
            try:
                display = Display.from_dict(data)
            except NetlinkDataError as exc:
                _LOGGER.warning("Skipping incomplete display %s state: %s", bus_id, exc)
                return

            current = self.data or {}
            displays = dict(current.get("displays", {}))
            displays[bus_id] = display

            self.async_set_updated_data(
                {
                    **current,
                    "desk": current.get("desk", {}),
                    "displays": displays,
                }
            )

        @self.client.on(EVENT_DISPLAYS_LIST)
        async def on_displays_list(data: list[dict[str, Any]]) -> None:
            """Handle display list updates."""
            displays = [DisplaySummary.from_dict(item) for item in data]
            self.display_info = {str(display.bus): display for display in displays}

        # Connect WebSocket
        await self.client.connect()

        # Fetch initial data
        await self.async_config_entry_first_refresh()
        self._initial_refresh_done = True

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect WebSocket."""
        await self.client.disconnect()
