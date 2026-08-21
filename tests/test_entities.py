"""Behavior tests for NetLink entities."""

from __future__ import annotations

import json

from pynetlink import (
    EVENT_AUTHORIZATION_STATE,
    NetlinkCommandError,
    NetlinkConnectionError,
    NetlinkUnauthorizedError,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.netlink.const import DOMAIN
from custom_components.netlink.sensor import (
    _access_code_valid_until,
    _access_code_value,
)

from .conftest import (
    DEVICE_ID,
    FakeNetlinkClient,
    authorization_payload,
    authorization_state,
)


def test_missing_access_code_values_are_none() -> None:
    """Absent optional access codes do not expose entity values."""
    data = object()
    assert _access_code_value(data, "web_login") is None
    assert _access_code_valid_until(data, "web_login") is None


async def test_display_error_sensor_summarizes_structured_diagnostics(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Structured display errors use a short state and diagnostic attributes."""
    netlink_client.display.state.error = json.dumps(
        {
            "attempt": 2,
            "bus": "1",
            "detail": "ddcutil exited with returncode=1 and no error text",
            "elapsed_ms": 4058,
            "exception_type": "DdcutilExitError",
            "max_attempts": 2,
            "model": "dell_u3821dw",
            "operation": "read_power",
            "profile": "dell_u3821dw",
            "reason": "general_io_failure",
            "retry_outcome": "exhausted",
            "stage": "ddc_read",
        }
    )
    coordinator = setup_integration.runtime_data
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity_id = _entity_id(hass, "sensor", f"{DEVICE_ID}_display_1_error")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "general_io_failure"
    assert state.attributes["operation"] == "read_power"
    assert state.attributes["detail"] == (
        "ddcutil exited with returncode=1 and no error text"
    )
    assert state.attributes["attempt"] == 2
    assert state.attributes["max_attempts"] == 2
    assert "{" not in state.state


async def test_display_error_sensor_preserves_legacy_detail(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Unstructured legacy errors remain available without becoming the state."""
    netlink_client.display.state.error = "No DDC/CI response from monitor"
    coordinator = setup_integration.runtime_data
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity_id = _entity_id(hass, "sensor", f"{DEVICE_ID}_display_1_error")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "other"
    assert state.attributes["detail"] == "No DDC/CI response from monitor"


def _entity_id(hass: HomeAssistant, platform: str, unique_id: str) -> str:
    """Resolve an entity through the Home Assistant entity registry."""
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def _call_entity_service(
    hass: HomeAssistant,
    domain: str,
    service: str,
    entity_id: str,
    **data: object,
) -> None:
    """Call an entity service through Home Assistant."""
    await hass.services.async_call(
        domain,
        service,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )


async def test_entity_commands_reach_client_boundary(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Entity services translate user commands to pynetlink calls."""
    for unique_id in ("desk_stop", "desk_reset", "browser_refresh", "device_reboot"):
        await _call_entity_service(
            hass,
            "button",
            "press",
            _entity_id(hass, "button", f"{DEVICE_ID}_{unique_id}"),
        )

    await _call_entity_service(
        hass,
        "number",
        "set_value",
        _entity_id(hass, "number", f"{DEVICE_ID}_desk_desk_target_height"),
        value=90,
    )
    await _call_entity_service(
        hass,
        "number",
        "set_value",
        _entity_id(hass, "number", f"{DEVICE_ID}_display_1_brightness"),
        value=55,
    )
    await _call_entity_service(
        hass,
        "number",
        "set_value",
        _entity_id(hass, "number", f"{DEVICE_ID}_display_1_volume"),
        value=30,
    )
    await _call_entity_service(
        hass,
        "select",
        "select_option",
        _entity_id(hass, "select", f"{DEVICE_ID}_display_1_source"),
        option="USBC",
    )

    desk_switch = _entity_id(hass, "switch", f"{DEVICE_ID}_desk_beep")
    display_switch = _entity_id(hass, "switch", f"{DEVICE_ID}_display_1_power")
    for entity_id in (desk_switch, display_switch):
        await _call_entity_service(hass, "switch", "turn_off", entity_id)
        await _call_entity_service(hass, "switch", "turn_on", entity_id)

    assert netlink_client.commands == [
        ("stop_desk", (), {}),
        ("reset_desk", (), {}),
        ("refresh_browser", (), {}),
        ("reboot_device", (), {}),
        ("set_desk_height", (90.0,), {}),
        ("set_display_brightness", ("1", 55), {}),
        ("set_display_volume", ("1", 30), {}),
        ("set_display_source", ("1", "USBC"), {}),
        ("set_desk_beep", (), {"state": "off"}),
        ("set_desk_beep", (), {"state": "on"}),
        ("set_display_power", ("1", "off"), {}),
        ("set_display_power", ("1", "on"), {}),
    ]


@pytest.mark.parametrize(
    ("domain", "service", "unique_id", "data"),
    [
        ("button", "press", "desk_stop", {}),
        ("button", "press", "browser_refresh", {}),
        ("button", "press", "device_reboot", {}),
        ("number", "set_value", "desk_desk_target_height", {"value": 80}),
        ("number", "set_value", "display_1_brightness", {"value": 50}),
        ("select", "select_option", "display_1_source", {"option": "USBC"}),
        ("switch", "turn_on", "desk_beep", {}),
        ("switch", "turn_off", "desk_beep", {}),
        ("switch", "turn_on", "display_1_power", {}),
        ("switch", "turn_off", "display_1_power", {}),
    ],
)
async def test_entity_command_errors_are_user_visible(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
    domain: str,
    service: str,
    unique_id: str,
    data: dict[str, object],
) -> None:
    """Command failures surface as Home Assistant service errors."""
    netlink_client.command_error = NetlinkCommandError("failed", "test")

    with pytest.raises(HomeAssistantError):
        await _call_entity_service(
            hass,
            domain,
            service,
            _entity_id(hass, domain, f"{DEVICE_ID}_{unique_id}"),
            **data,
        )


@pytest.mark.parametrize(
    ("domain", "service", "unique_id", "data"),
    [
        ("number", "set_value", "desk_desk_target_height", {"value": 80}),
        ("number", "set_value", "display_1_volume", {"value": 50}),
        ("select", "select_option", "display_1_source", {"option": "USBC"}),
    ],
)
async def test_entity_connection_errors_are_user_visible(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
    domain: str,
    service: str,
    unique_id: str,
    data: dict[str, object],
) -> None:
    """Connection failures surface as unavailable service errors."""
    netlink_client.command_error = NetlinkConnectionError("offline")

    with pytest.raises(HomeAssistantError):
        await _call_entity_service(
            hass,
            domain,
            service,
            _entity_id(hass, domain, f"{DEVICE_ID}_{unique_id}"),
            **data,
        )


async def test_unsupported_display_command_is_ignored(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A display rejecting an optional command does not raise a service error."""
    netlink_client.command_error = NetlinkCommandError("unsupported_command", "test")

    await _call_entity_service(
        hass,
        "number",
        "set_value",
        _entity_id(hass, "number", f"{DEVICE_ID}_display_1_brightness"),
        value=50,
    )

    assert "rejected brightness change (unsupported)" in caplog.text


async def test_typed_authorization_denial_is_recorded(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """A server denial is user-visible and retained as a safe diagnostic category."""
    await netlink_client.emit(
        EVENT_AUTHORIZATION_STATE,
        authorization_payload(authorization_state("command.browser.refresh")),
    )
    netlink_client.command_error = NetlinkUnauthorizedError(
        "unauthorized",
        command="command.browser.refresh",
    )

    with pytest.raises(HomeAssistantError):
        await _call_entity_service(
            hass,
            "button",
            "press",
            _entity_id(hass, "button", f"{DEVICE_ID}_browser_refresh"),
        )

    assert (
        setup_integration.runtime_data.last_authorization_failure
        == "NetlinkUnauthorizedError"
    )
    assert netlink_client.commands == []
