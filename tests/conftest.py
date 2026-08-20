"""Shared fixtures for the NetLink integration test suite."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import patch

import pytest
from pynetlink import (
    AccessCode,
    AccessCodes,
    BrowserState,
    Desk,
    DeskState,
    DeviceInfo,
    Display,
    DisplayState,
    DisplaySummary,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

from custom_components.netlink.const import CONF_DEVICE_ID, DOMAIN

DEVICE_ID = "device-id"
HOST = "netlink.local"
TOKEN = "secret-token"


class FakeNetlinkClient:
    """Fake the external pynetlink boundary while preserving its event contract."""

    def __init__(self) -> None:
        """Initialize a complete, healthy NetLink snapshot."""
        self.connected = False
        self.handlers = {}
        self.connect_error: Exception | None = None
        self.rest_error: Exception | None = None
        self.display_error: Exception | None = None
        self.access_codes_error: Exception | None = None
        self.command_error: Exception | None = None
        self.commands: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.device_info = DeviceInfo(
            device_id=DEVICE_ID,
            device_name="Meeting room",
            version="1.0.0",
            api_version="1",
            model="NetLink",
        )
        self.desk = Desk(
            capabilities={"supports": {"height": True}},
            inventory={},
            state=DeskState(
                height=75,
                mode="idle",
                moving=False,
                beep="on",
            ),
        )
        self.display_summary = DisplaySummary(
            id=0,
            bus=1,
            model="Test display",
            type="display",
            connected=True,
        )
        self.display_summaries = [self.display_summary]
        self.display = Display(
            bus=1,
            model="Test display",
            type="display",
            supports={
                "brightness": True,
                "power": True,
                "source": True,
                "volume": True,
            },
            state=DisplayState(
                power="on",
                source="HDMI1",
                brightness=40,
                volume=20,
            ),
            connected=True,
            source_options=["HDMI1", "USBC"],
        )
        self.browser = BrowserState(url="https://example.com")
        self.access_codes = AccessCodes(
            web_login=AccessCode(
                code="123456",
                valid_from="2026-08-20T08:00:00Z",
                valid_until="2026-08-20T18:00:00Z",
                timezone="Europe/Amsterdam",
            ),
            signing_maintenance=AccessCode(
                code="654321",
                valid_from="2026-08-20T08:00:00Z",
                valid_until="2026-08-20T18:00:00Z",
                timezone="Europe/Amsterdam",
            ),
        )

    def on(self, event: str):
        """Register a pynetlink event callback."""

        def register(handler):
            self.handlers[event] = handler
            return handler

        return register

    async def emit(self, event: str, data: Any | None = None) -> None:
        """Emit an external client event."""
        if event == "connect":
            self.connected = True
        elif event == "disconnect":
            self.connected = False
        await self.handlers[event]({} if data is None else data)

    async def connect(self) -> None:
        """Connect the fake WebSocket."""
        if self.connect_error is not None:
            raise self.connect_error
        self.connected = True

    async def disconnect(self) -> None:
        """Disconnect the fake WebSocket."""
        self.connected = False

    def _raise_rest_error(self) -> None:
        """Raise the configured snapshot error, if any."""
        if self.rest_error is not None:
            raise self.rest_error

    async def get_device_info(self) -> DeviceInfo:
        """Return device information."""
        self._raise_rest_error()
        return self.device_info

    async def get_desk_status(self) -> Desk:
        """Return desk state."""
        self._raise_rest_error()
        return self.desk

    async def get_displays(self) -> list[DisplaySummary]:
        """Return the display inventory."""
        self._raise_rest_error()
        return self.display_summaries

    async def get_display_status(self, _: int | str) -> Display:
        """Return display state."""
        if self.display_error is not None:
            raise self.display_error
        return self.display

    async def get_browser_status(self) -> BrowserState:
        """Return browser state."""
        self._raise_rest_error()
        return self.browser

    async def get_access_codes(self) -> AccessCodes:
        """Return access codes."""
        self._raise_rest_error()
        if self.access_codes_error is not None:
            raise self.access_codes_error
        return self.access_codes

    async def _record_command(self, name: str, *args: Any, **kwargs: Any) -> None:
        """Record an entity command or raise the configured command error."""
        if self.command_error is not None:
            raise self.command_error
        self.commands.append((name, args, kwargs))

    async def stop_desk(self) -> None:
        await self._record_command("stop_desk")

    async def reset_desk(self) -> None:
        await self._record_command("reset_desk")

    async def calibrate_desk(self) -> None:
        await self._record_command("calibrate_desk")

    async def refresh_browser(self) -> None:
        await self._record_command("refresh_browser")

    async def reboot_device(self) -> None:
        await self._record_command("reboot_device")

    async def set_desk_height(self, value: float) -> None:
        await self._record_command("set_desk_height", value)

    async def set_display_brightness(self, bus_id: str, value: int) -> None:
        await self._record_command("set_display_brightness", bus_id, value)

    async def set_display_volume(self, bus_id: str, value: int) -> None:
        await self._record_command("set_display_volume", bus_id, value)

    async def set_display_source(self, bus_id: str, option: str) -> None:
        await self._record_command("set_display_source", bus_id, option)

    async def set_desk_beep(self, *, state: str) -> None:
        await self._record_command("set_desk_beep", state=state)

    async def set_display_power(self, bus_id: str, state: str) -> None:
        await self._record_command("set_display_power", bus_id, state)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable loading custom integrations in every test."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a complete NetLink config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Meeting room",
        data={
            CONF_DEVICE_ID: DEVICE_ID,
            CONF_HOST: HOST,
            CONF_TOKEN: TOKEN,
        },
        unique_id=DEVICE_ID,
        version=1,
        minor_version=2,
    )


@pytest.fixture
def netlink_client() -> Generator[FakeNetlinkClient]:
    """Patch construction at the external pynetlink boundary."""
    client = FakeNetlinkClient()
    with patch("custom_components.netlink.NetlinkClient", return_value=client):
        yield client


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> AsyncGenerator[MockConfigEntry]:
    """Set up the complete integration through Home Assistant."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    yield mock_config_entry
