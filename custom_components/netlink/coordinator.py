"""DataUpdateCoordinator for NetLink."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from contextlib import suppress
from datetime import datetime
from enum import Enum, auto
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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, RECONCILIATION_INTERVAL, WEBSOCKET_DISCONNECT_GRACE

_LOGGER = logging.getLogger(__name__)


class _ConnectivityState(Enum):
    """Authoritative connectivity state for coordinator data."""

    INITIALIZING = auto()
    READY = auto()
    DISCONNECTED = auto()
    RECOVERING = auto()
    SHUTTING_DOWN = auto()


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
            update_interval=None,
        )
        self.client = client
        self.device_id = device_id
        self.device_info: DeviceInfo | None = None
        self.display_info: dict[str, DisplaySummary] = {}
        self.known_bus_ids: set[str] = set()
        self._new_display_callbacks: list[Callable[[str], None]] = []
        self._access_codes_available_callbacks: list[Callable[[], None]] = []
        self._connectivity_state = _ConnectivityState.INITIALIZING
        self._cancel_disconnect_grace: CALLBACK_TYPE | None = None
        self._cancel_reconciliation: CALLBACK_TYPE | None = None
        self._reconnect_lock = asyncio.Lock()

    def _cancel_disconnect_timer(self) -> None:
        """Cancel a pending disconnect grace timer."""
        if self._cancel_disconnect_grace is None:
            return
        self._cancel_disconnect_grace()
        self._cancel_disconnect_grace = None

    async def _async_disconnect_grace_elapsed(self, _: datetime) -> None:
        """Mark coordinator data unavailable after a sustained disconnect."""
        self._cancel_disconnect_grace = None
        if self._connectivity_state is not _ConnectivityState.DISCONNECTED:
            return

        self.async_set_update_error(UpdateFailed("WebSocket connection lost"))

    def _push_updates_allowed(self) -> bool:
        """Return whether push events may update authoritative live state."""
        return self._connectivity_state is _ConnectivityState.READY

    async def _async_reconcile(self, _: datetime) -> None:
        """Refresh REST state periodically without replacing push updates."""
        if (
            self._connectivity_state
            in {
                _ConnectivityState.INITIALIZING,
                _ConnectivityState.SHUTTING_DOWN,
            }
            or self._cancel_disconnect_grace is not None
        ):
            return
        await self.async_refresh()

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
        if self._connectivity_state is not _ConnectivityState.INITIALIZING:
            for callback in self._new_display_callbacks:
                callback(bus_id)

    def _track_bus_ids(self, displays: list[DisplaySummary]) -> None:
        """Remember all buses returned by the stable display inventory."""
        for display in displays:
            self._track_bus_id(str(display.bus))

    def _patch_data(self, key: str, value: Any) -> None:
        """Update a single key in coordinator data and notify listeners."""
        if not self._push_updates_allowed():
            return
        self.async_set_updated_data({**(self.data or {}), key: value})

    async def _fetch_display_status(
        self, display: DisplaySummary
    ) -> tuple[str, Display]:
        """Fetch authoritative status for a display."""
        return str(display.bus), await self.client.get_display_status(display.bus)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch an authoritative state snapshot via REST API."""
        try:
            device_info, desk_status, displays, browser_state = await asyncio.gather(
                self.client.get_device_info(),
                self.client.get_desk_status(),
                self.client.get_displays(),
                self.client.get_browser_status(),
            )
            display_results = await asyncio.gather(
                *[self._fetch_display_status(d) for d in displays]
            )
            display_states = dict(display_results)

            coordinator_data: dict[str, Any] = {
                "desk": desk_status,
                "displays": display_states,
                "browser": browser_state,
            }
            with suppress(NetlinkNotFoundError):
                access_codes = await self.client.get_access_codes()
                coordinator_data["access_codes"] = access_codes

        except NetlinkAuthenticationError as err:
            self._mark_refresh_failed()
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={
                    "name": self.config_entry.title,
                    "host": self.config_entry.data[CONF_HOST],
                },
            ) from err
        except (NetlinkError, NetlinkDataError) as err:
            self._mark_refresh_failed()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={
                    "name": self.config_entry.title,
                    "host": self.config_entry.data[CONF_HOST],
                },
            ) from err
        else:
            if not self.client.connected:
                self._mark_refresh_failed()
                raise UpdateFailed("WebSocket is disconnected")
            self.device_info = device_info
            self.display_info = {str(d.bus): d for d in displays}
            self._track_bus_ids(displays)
            self._connectivity_state = _ConnectivityState.READY
            return coordinator_data

    def _mark_refresh_failed(self) -> None:
        """Block push updates until a later authoritative refresh succeeds."""
        if self._connectivity_state in {
            _ConnectivityState.INITIALIZING,
            _ConnectivityState.SHUTTING_DOWN,
        }:
            return
        self._connectivity_state = (
            _ConnectivityState.RECOVERING
            if self.client.connected
            else _ConnectivityState.DISCONNECTED
        )

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
            if self._connectivity_state in {
                _ConnectivityState.INITIALIZING,
                _ConnectivityState.SHUTTING_DOWN,
            }:
                return

            self._cancel_disconnect_timer()
            async with self._reconnect_lock:
                if self._connectivity_state is _ConnectivityState.READY:
                    return
                self._connectivity_state = _ConnectivityState.RECOVERING
                await self.async_refresh()

        @self.client.on("disconnect")
        async def on_disconnect(_: dict[str, Any]) -> None:
            """Handle WebSocket disconnect events."""
            if self._connectivity_state is _ConnectivityState.SHUTTING_DOWN:
                return

            self._connectivity_state = _ConnectivityState.DISCONNECTED
            if self._cancel_disconnect_grace is not None:
                return
            self._cancel_disconnect_grace = async_call_later(
                self.hass,
                WEBSOCKET_DISCONNECT_GRACE,
                self._async_disconnect_grace_elapsed,
            )

        @self.client.on(EVENT_DEVICE_INFO)
        async def on_device_info(data: dict[str, Any]) -> None:
            """Handle device info updates."""
            if not self._push_updates_allowed():
                return
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
            if not self._push_updates_allowed():
                return
            try:
                desk = Desk.from_dict(data)
            except NetlinkDataError as exc:
                _LOGGER.warning("Skipping incomplete desk state: %s", exc)
                return
            self._patch_data("desk", desk)

        @self.client.on(EVENT_DISPLAY_STATE)
        async def on_display_state(data: dict[str, Any]) -> None:
            """Handle display state updates."""
            if not self._push_updates_allowed():
                return
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
            if not self._push_updates_allowed():
                return
            try:
                browser = BrowserState.from_dict(data)
            except NetlinkDataError as exc:
                _LOGGER.warning("Skipping incomplete browser state: %s", exc)
                return
            self._patch_data("browser", browser)

        @self.client.on(EVENT_ACCESS_CODES_STATE)
        async def on_access_codes_state(data: dict[str, Any]) -> None:
            """Handle push updates for access codes."""
            if not self._push_updates_allowed():
                return
            try:
                access_codes = AccessCodes.from_dict(data)
            except NetlinkDataError as exc:
                _LOGGER.warning("Skipping incomplete access code state: %s", exc)
                return
            had_access_codes = "access_codes" in (self.data or {})
            self._patch_data("access_codes", access_codes)
            if not had_access_codes:
                for callback in self._access_codes_available_callbacks:
                    callback()

        @self.client.on(EVENT_DISPLAYS_LIST)
        async def on_displays_list(data: list[dict[str, Any]]) -> None:
            """Handle display list updates."""
            if not self._push_updates_allowed():
                return
            displays = [DisplaySummary.from_dict(item) for item in data]
            self.display_info = {str(display.bus): display for display in displays}
            self._track_bus_ids(displays)

        try:
            await self.client.connect()
        except Exception:
            await self.client.disconnect()
            raise

        await self.async_config_entry_first_refresh()
        self._cancel_reconciliation = async_track_time_interval(
            self.hass,
            self._async_reconcile,
            RECONCILIATION_INTERVAL,
        )
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
        if self._connectivity_state is _ConnectivityState.SHUTTING_DOWN:
            return
        self._connectivity_state = _ConnectivityState.SHUTTING_DOWN
        self._cancel_disconnect_timer()
        if self._cancel_reconciliation is not None:
            self._cancel_reconciliation()
            self._cancel_reconciliation = None
        await super().async_shutdown()
        await self.client.disconnect()
