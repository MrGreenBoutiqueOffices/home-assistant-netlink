"""Tests for NetLink diagnostics."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from custom_components.netlink.diagnostics import async_get_config_entry_diagnostics

from .conftest import TOKEN


async def test_diagnostics_include_state_and_redact_secrets(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Diagnostics expose useful last-known state without credentials."""
    diagnostics = await async_get_config_entry_diagnostics(hass, setup_integration)

    assert diagnostics["device_info"]["device_id"] == "device-id"
    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["coordinator"]["data"]["desk"]["state"]["height"] == 75
    assert diagnostics["coordinator"]["data"]["displays"]["1"]["state"] == {
        "power": "on",
        "brightness": 40,
        "volume": 20,
        "source": "HDMI1",
        "error": None,
    }
    assert (
        diagnostics["coordinator"]["data"]["access_codes"]["web_login"]["code"]
        == "**REDACTED**"
    )
    assert diagnostics["config_entry"]["data"][CONF_TOKEN] == "**REDACTED**"
    assert TOKEN not in str(diagnostics)
    assert diagnostics["client"] == {"connected": True, "host": "netlink.local"}


async def test_diagnostics_support_partial_runtime_state(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Diagnostics remain useful while runtime state is incomplete."""
    coordinator = setup_integration.runtime_data
    desk = coordinator.data["desk"]
    client = coordinator.client

    coordinator.device_info = None
    coordinator.data = {}
    del client.connected
    diagnostics = await async_get_config_entry_diagnostics(hass, setup_integration)
    assert diagnostics["device_info"] is None
    assert diagnostics["coordinator"]["data"] == {}
    assert diagnostics["client"]["connected"] is None

    coordinator.data = {"desk": desk}
    diagnostics = await async_get_config_entry_diagnostics(hass, setup_integration)
    assert set(diagnostics["coordinator"]["data"]) == {"desk"}
    assert diagnostics["coordinator"]["data"]["desk"]["state"]["height"] == 75

    coordinator.data = {"displays": {}}
    diagnostics = await async_get_config_entry_diagnostics(hass, setup_integration)
    assert diagnostics["coordinator"]["data"] == {"displays": {}}
