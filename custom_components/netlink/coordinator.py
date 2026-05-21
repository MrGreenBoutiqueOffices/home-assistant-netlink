"""DataUpdateCoordinator for NetLink."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from contextlib import suppress
import logging
from typing import Any

from pynetlink import (
    EVENT_ACCESS_CODES_STATE,
    EVENT_BROWSER_STATE,
    EVENT_DESK_STATE,
    EVENT_DEVICE_INFO,
    EVENT_DISPLAY_STATE,
    EVENT_DISPLAYS_LIST,
    BrowserState,
    Desk,
    DeviceInfo,
    Display,
    DisplaySummary,
    AccessCodes,
    NetlinkAuthenticationError,
    NetlinkClient,
    NetlinkDataError,
    NetlinkError,
    NetlinkNotFoundError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class NetlinkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching NetLink data via WebSocket."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: NetlinkClient,
        device_id: str,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"NetLink {device_id}",
            update_interval=None,  # WebSocket push only, no polling!
        )
        self.client = client
        self.device_id = device_id
        self.device_info: DeviceInfo | None = None
        self.display_info: dict[str, DisplaySummary] = {}
        self.known_bus_ids: set[str] = set()
        self._new_display_callbacks: list[Callable[[str], None]] = []
        self._access_codes_available_callbacks: list[Callable[[], None]] = []
        self._initial_refresh_done = False

    def _iter_registry_display_buses(self) -> Iterator[tuple[str, dr.DeviceEntry]]:
        """Yield (bus_id, device) for all display devices in the HA device registry."""
        prefix = f"netlink-{self.device_id}-display-"
        device_reg = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(
            device_reg, self.config_entry.entry_id
        ):
            for domain, identifier in device.identifiers:
                if domain == DOMAIN and identifier.startswith(prefix):
                    yield identifier[len(prefix) :], device
                    break

    def _track_bus_id(self, bus_id: str) -> None:
        """Remember a bus as part of the controllable display inventory."""
        if bus_id in self.known_bus_ids:
            return
        self.known_bus_ids.add(bus_id)
        if self._initial_refresh_done:
            for callback in self._new_display_callbacks:
                callback(bus_id)

    def _track_bus_ids(self, displays: list[DisplaySummary]) -> None:
        """Remember all buses returned by the stable display inventory."""
        for display in displays:
            self._track_bus_id(str(display.bus))

    def _patch_data(self, key: str, value: Any) -> None:
        """Update a single key in coordinator data and notify listeners."""
        self.async_set_updated_data({**(self.data or {}), key: value})

    async def _fetch_display_status(
        self, display: DisplaySummary
    ) -> tuple[str, Display | None]:
        """Fetch status for a single display, returning (bus_key, state_or_None)."""
        bus_key = str(display.bus)
        try:
            return bus_key, await self.client.get_display_status(display.bus)
        except NetlinkError as err:
            _LOGGER.warning("Failed to get display %s status: %s", display.bus, err)
            fallback = (self.data or {}).get("displays", {}).get(bus_key)
            return bus_key, fallback

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch initial data via REST API.

        This is called once during setup to get initial state.
        After that, WebSocket events keep state updated.
        """
        try:
            device_info, desk_status, displays, browser_state = await asyncio.gather(
                self.client.get_device_info(),
                self.client.get_desk_status(),
                self.client.get_displays(),
                self.client.get_browser_status(),
            )
            self.device_info = device_info
            self.display_info = {str(d.bus): d for d in displays}
            self._track_bus_ids(displays)

            display_results = await asyncio.gather(
                *[self._fetch_display_status(d) for d in displays]
            )
            display_states: dict[str, Display] = {
                bus_key: state
                for bus_key, state in display_results
                if state is not None
            }

            coordinator_data: dict[str, Any] = {
                "desk": desk_status,
                "displays": display_states,
                "browser": browser_state,
            }
            with suppress(NetlinkNotFoundError):
                access_codes = await self.client.get_access_codes()
                coordinator_data["access_codes"] = access_codes

        except NetlinkAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={
                    "name": self.config_entry.title,
                    "host": self.config_entry.data[CONF_HOST],
                },
            ) from err
        except (NetlinkError, NetlinkDataError) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={
                    "name": self.config_entry.title,
                    "host": self.config_entry.data[CONF_HOST],
                },
            ) from err
        else:
            return coordinator_data

    def display_supports(self, bus_id: str, capability: str) -> bool | None:
        """Return whether a display supports a capability.

        Checks live state first, then the stable inventory summary.
        Returns None when no data is available yet.
        """
        for data in (
            self.data["displays"].get(bus_id) if self.data else None,
            self.display_info.get(bus_id),
        ):
            if data is not None:
                supports = getattr(data, "supports", None)
                if isinstance(supports, dict) and capability in supports:
                    return bool(supports[capability])
        return None

    def async_add_new_display_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback to be called when a new display is discovered."""
        self._new_display_callbacks.append(callback)

    def async_add_access_codes_available_callback(
        self, callback: Callable[[], None]
    ) -> None:
        """Register a callback for when access codes become available."""
        self._access_codes_available_callbacks.append(callback)

    async def async_setup(self) -> None:
        """Setup WebSocket listeners and fetch initial data."""

        @self.client.on("connect")
        async def on_connect(_: dict[str, Any]) -> None:
            """Handle WebSocket reconnect events."""
            if self._initial_refresh_done:
                await self.async_refresh()

        @self.client.on("disconnect")
        async def on_disconnect(_: dict[str, Any]) -> None:
            """Handle WebSocket disconnect events."""
            _LOGGER.debug("WebSocket disconnected for %s", self.name)

        @self.client.on(EVENT_DEVICE_INFO)
        async def on_device_info(data: dict[str, Any]) -> None:
            """Handle device info updates."""
            self.device_info = DeviceInfo.from_dict(data)
            device_reg = dr.async_get(self.hass)
            for device in dr.async_entries_for_config_entry(
                device_reg, self.config_entry.entry_id
            ):
                device_reg.async_update_device(
                    device.id,
                    sw_version=self.device_info.version,
                    model=self.device_info.model,
                )

            # Keep coordinator updated so entities get a refresh signal.
            if self.data is not None:
                self.async_set_updated_data(self.data)

        @self.client.on(EVENT_DESK_STATE)
        async def on_desk_state(data: dict[str, Any]) -> None:
            """Handle desk state updates."""
            try:
                desk = Desk.from_dict(data)
            except NetlinkDataError as exc:
                _LOGGER.warning("Skipping incomplete desk state: %s", exc)
                return
            self._patch_data("desk", desk)

        @self.client.on(EVENT_DISPLAY_STATE)
        async def on_display_state(data: dict[str, Any]) -> None:
            """Handle display state updates."""
            bus_id = str(data["bus"])
            try:
                display = Display.from_dict(data)
            except NetlinkDataError as exc:
                _LOGGER.warning("Skipping incomplete display %s state: %s", bus_id, exc)
                return
            displays = dict((self.data or {}).get("displays", {}))
            displays[bus_id] = display
            self._patch_data("displays", displays)
            self._track_bus_id(bus_id)

        @self.client.on(EVENT_BROWSER_STATE)
        async def on_browser_state(data: dict[str, Any]) -> None:
            """Handle browser state updates."""
            try:
                browser = BrowserState.from_dict(data)
            except NetlinkDataError as exc:
                _LOGGER.warning("Skipping incomplete browser state: %s", exc)
                return
            self._patch_data("browser", browser)

        @self.client.on(EVENT_ACCESS_CODES_STATE)
        async def on_access_codes_state(data: dict[str, Any]) -> None:
            """Handle push updates for access codes."""
            try:
                access_codes = AccessCodes.from_dict(data)
            except NetlinkDataError as exc:
                _LOGGER.warning("Skipping incomplete access code state: %s", exc)
                return
            had_access_codes = "access_codes" in (self.data or {})
            self._patch_data("access_codes", access_codes)
            if self._initial_refresh_done and not had_access_codes:
                for callback in self._access_codes_available_callbacks:
                    callback()

        @self.client.on(EVENT_DISPLAYS_LIST)
        async def on_displays_list(data: list[dict[str, Any]]) -> None:
            """Handle display list updates."""
            displays = [DisplaySummary.from_dict(item) for item in data]
            self.display_info = {str(display.bus): display for display in displays}
            self._track_bus_ids(displays)

        try:
            await self.client.connect()
        except Exception:
            await self.client.disconnect()
            raise

        await self.async_config_entry_first_refresh()
        self._initial_refresh_done = True
        self._async_cleanup_stale_devices()

    def _async_cleanup_stale_devices(self) -> None:
        """Remove display devices that are no longer in the webserver inventory."""
        device_reg = dr.async_get(self.hass)
        for bus_id, device in self._iter_registry_display_buses():
            if bus_id not in self.display_info:
                device_reg.async_update_device(
                    device.id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )
                _LOGGER.debug(
                    "Removed orphaned display device %s (bus %s)", device.id, bus_id
                )

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and disconnect WebSocket."""
        await self.client.disconnect()
