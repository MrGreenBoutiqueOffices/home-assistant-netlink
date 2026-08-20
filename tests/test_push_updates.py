"""Tests for NetLink WebSocket push updates."""

from __future__ import annotations

import logging
from unittest.mock import patch

from pynetlink import (
    AccessCodes,
    BrowserState,
    EVENT_ACCESS_CODES_STATE,
    EVENT_AUTHORIZATION_STATE,
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
    NetlinkAuthenticationError,
    NetlinkConnectionError,
    NetlinkDataError,
    NetlinkNotFoundError,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.netlink.const import DOMAIN
from custom_components.netlink.coordinator import EXPECTED_HOME_ASSISTANT_COMMANDS
from custom_components.netlink.sensor import (
    ACCESS_CODE_SENSORS,
    DESK_SENSORS,
    NetlinkAccessCodeSensor,
    NetlinkDeskSensor,
)

from .conftest import (
    DEVICE_ID,
    FakeNetlinkClient,
    authorization_payload,
    authorization_state,
)


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


async def test_authorization_state_updates_command_availability(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Advertised command policy updates entity availability without polling."""
    registry = er.async_get(hass)
    stop_id = registry.async_get_entity_id("button", DOMAIN, f"{DEVICE_ID}_desk_stop")
    refresh_id = registry.async_get_entity_id(
        "button", DOMAIN, f"{DEVICE_ID}_browser_refresh"
    )
    height_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_desk_height"
    )

    await netlink_client.emit(
        EVENT_AUTHORIZATION_STATE,
        authorization_payload(authorization_state("command.desk.stop")),
    )
    await hass.async_block_till_done()

    assert hass.states.get(stop_id).state != "unavailable"
    assert hass.states.get(refresh_id).state == "unavailable"
    assert hass.states.get(height_id).state != "unavailable"

    await netlink_client.emit(
        EVENT_AUTHORIZATION_STATE,
        authorization_payload(
            authorization_state("command.browser.refresh", "command.desk.stop")
        ),
    )
    await hass.async_block_till_done()
    assert hass.states.get(refresh_id).state != "unavailable"


async def test_dedicated_identity_keeps_expected_commands_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """The expected Home Assistant policy keeps every command entity available."""
    netlink_client.authorization_state = authorization_state(
        *EXPECTED_HOME_ASSISTANT_COMMANDS
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    for platform, unique_id in (
        ("button", "desk_reset"),
        ("button", "browser_refresh"),
        ("button", "device_reboot"),
        ("number", "display_1_brightness"),
        ("select", "display_1_source"),
        ("switch", "display_1_power"),
    ):
        entity_id = registry.async_get_entity_id(
            platform, DOMAIN, f"{DEVICE_ID}_{unique_id}"
        )
        assert hass.states.get(entity_id).state != "unavailable"


async def test_access_code_denial_degrades_only_sensitive_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """A denied access-code audience does not fail unrelated state setup."""
    netlink_client.authorization_state = authorization_state(
        *EXPECTED_HOME_ASSISTANT_COMMANDS,
        access_codes=False,
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert netlink_client.access_codes_calls == 0
    assert coordinator.access_codes_status == "unauthorized"
    assert "access_codes" not in coordinator.data

    access_code = NetlinkAccessCodeSensor(
        coordinator, mock_config_entry, ACCESS_CODE_SENSORS[0]
    )
    desk_sensor = NetlinkDeskSensor(coordinator, mock_config_entry, DESK_SENSORS[0])
    assert access_code.available is False
    assert desk_sensor.available is True

    registry = er.async_get(hass)
    assert registry.async_get_entity_id(
        "sensor", DOMAIN, f"{DEVICE_ID}_web_login_access_code"
    )

    await netlink_client.emit(
        EVENT_ACCESS_CODES_STATE, netlink_client.access_codes.to_dict()
    )
    assert "access_codes" not in coordinator.data


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (NetlinkAuthenticationError("denied"), "unauthorized"),
        (NetlinkConnectionError("forbidden"), "NetlinkConnectionError"),
    ],
)
async def test_access_code_rest_failure_does_not_break_other_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
    error: Exception,
    status: str,
) -> None:
    """A sensitive endpoint failure does not fail the complete REST snapshot."""
    netlink_client.access_codes_error = error
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.access_codes_status == status
    assert "desk" in coordinator.data
    assert "access_codes" not in coordinator.data


async def test_late_access_code_denial_adds_unavailable_sensitive_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """A late policy denial represents sensitive entities without exposing data."""
    netlink_client.access_codes_error = NetlinkNotFoundError("not found")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    unique_id = f"{DEVICE_ID}_web_login_access_code"
    assert registry.async_get_entity_id("sensor", DOMAIN, unique_id) is None

    await netlink_client.emit(
        EVENT_AUTHORIZATION_STATE,
        authorization_payload(authorization_state(access_codes=False)),
    )
    await hass.async_block_till_done()

    assert registry.async_get_entity_id("sensor", DOMAIN, unique_id) is not None
    assert mock_config_entry.runtime_data.access_codes_status == "unauthorized"


async def test_invalid_authorization_push_is_ignored(
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An incomplete policy event leaves legacy behavior intact."""
    await netlink_client.handlers[EVENT_AUTHORIZATION_STATE]({})

    assert "Skipping incomplete authorization state" in caplog.text
    assert setup_integration.runtime_data.authorization_state is None


async def test_reconnect_to_server_without_policy_restores_legacy_behavior(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """A reconnect clears stale policy when the new server advertises no state."""
    netlink_client.authorization_state = authorization_state("command.desk.stop")
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    assert coordinator.command_allowed("command.browser.refresh") is False

    await netlink_client.emit("disconnect")
    await netlink_client.emit("connect")
    await hass.async_block_till_done()

    assert coordinator.authorization_state is None
    assert coordinator.command_allowed("command.browser.refresh") is True


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
