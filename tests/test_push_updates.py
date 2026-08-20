"""Tests for NetLink WebSocket push updates."""

from __future__ import annotations

import logging
from unittest.mock import patch

from pynetlink import (
    AccessCodes,
    BrowserState,
    EVENT_ACCESS_CODES_STATE,
    EVENT_BROWSER_STATE,
    EVENT_DESK_STATE,
    EVENT_DEVICE_INFO,
    EVENT_DISPLAY_STATE,
    EVENT_DISPLAYS_LIST,
    Desk,
    DeviceInfo,
    Display,
    DisplayState,
    DisplaySummary,
    NetlinkDataError,
    NetlinkNotFoundError,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.netlink.const import DOMAIN

from .conftest import DEVICE_ID, FakeNetlinkClient


@pytest.mark.parametrize(
    ("event", "model", "payload", "warning"),
    [
        (
            EVENT_DESK_STATE,
            Desk,
            {},
            "Skipping incomplete desk state",
        ),
        (
            EVENT_DISPLAY_STATE,
            Display,
            {"bus": 1},
            "Skipping incomplete display 1 state",
        ),
        (
            EVENT_BROWSER_STATE,
            BrowserState,
            {},
            "Skipping incomplete browser state",
        ),
        (
            EVENT_ACCESS_CODES_STATE,
            AccessCodes,
            {},
            "Skipping incomplete access code state",
        ),
    ],
)
async def test_incomplete_push_state_is_ignored(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
    caplog: pytest.LogCaptureFixture,
    event: str,
    model: type,
    payload: dict,
    warning: str,
) -> None:
    """An incomplete push event leaves the last known state available."""
    caplog.set_level(logging.WARNING, logger="custom_components.netlink.coordinator")

    with patch.object(
        model, "from_dict", side_effect=NetlinkDataError("incomplete state")
    ):
        await netlink_client.emit(event, payload)
    await hass.async_block_till_done()

    assert warning in caplog.text
    registry = er.async_get(hass)
    height_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_desk_height"
    )
    assert float(hass.states.get(height_id).state) == 75


async def test_push_events_update_home_assistant_state(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Valid WebSocket events update entities and device metadata."""
    await netlink_client.emit(
        EVENT_DEVICE_INFO,
        DeviceInfo(
            device_id=DEVICE_ID,
            device_name="Meeting room",
            version="2.0.0",
            api_version="1",
            model="NetLink Pro",
        ).to_dict(),
    )
    await netlink_client.emit(
        EVENT_DESK_STATE,
        {
            "capabilities": {"supports": {"height": True}},
            "inventory": {},
            "state": {
                "height": 84,
                "mode": "idle",
                "moving": False,
                "beep": "on",
            },
        },
    )
    display = Display(
        bus=1,
        model="Test display",
        type="display",
        supports=netlink_client.display.supports,
        state=DisplayState(power="on", source="USBC", brightness=65, volume=35),
        connected=True,
        source_options=["HDMI1", "USBC"],
    )
    await netlink_client.emit(EVENT_DISPLAY_STATE, display.to_dict())
    await netlink_client.emit(
        EVENT_BROWSER_STATE, BrowserState(url="https://example.org").to_dict()
    )
    await netlink_client.emit(
        EVENT_ACCESS_CODES_STATE, netlink_client.access_codes.to_dict()
    )
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    height_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_desk_height"
    )
    brightness_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_display_1_brightness"
    )
    browser_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_browser_url"
    )
    assert float(hass.states.get(height_id).state) == 84
    assert float(hass.states.get(brightness_id).state) == 65
    assert hass.states.get(browser_id).state == "https://example.org"

    controller = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, f"netlink-{DEVICE_ID}")}
    )
    assert controller is not None
    assert controller.model == "NetLink Pro"
    assert controller.sw_version == "2.0.0"


async def test_new_display_inventory_adds_entities(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """A new display in push inventory creates its supported entities."""
    new_display = DisplaySummary(
        id=1,
        bus=2,
        model="Second display",
        type="display",
        connected=True,
    )
    await netlink_client.emit(
        EVENT_DISPLAYS_LIST,
        [netlink_client.display_summary.to_dict(), new_display.to_dict()],
    )
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{DEVICE_ID}_display_2_connected"
    )
    assert registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_display_2_brightness"
    )
    assert registry.async_get_entity_id(
        "number", DOMAIN, f"{DEVICE_ID}_display_2_brightness"
    )
    assert registry.async_get_entity_id(
        "select", DOMAIN, f"{DEVICE_ID}_display_2_source"
    )
    assert registry.async_get_entity_id(
        "switch", DOMAIN, f"{DEVICE_ID}_display_2_power"
    )


async def test_access_code_push_adds_entities_when_endpoint_becomes_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Access-code entities appear when a previously absent endpoint starts pushing."""
    netlink_client.access_codes_error = NetlinkNotFoundError("not found")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_id = f"{DEVICE_ID}_web_login_access_code"
    assert registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None

    netlink_client.access_codes_error = None
    await netlink_client.emit(
        EVENT_ACCESS_CODES_STATE, netlink_client.access_codes.to_dict()
    )
    await hass.async_block_till_done()

    assert registry.async_get_entity_id("sensor", DOMAIN, unique_id) is not None
