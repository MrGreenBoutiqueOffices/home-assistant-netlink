"""Tests for the NetLink config flow."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock, patch

from pynetlink import (
    NetlinkAuthenticationError,
    NetlinkConnectionError,
    NetlinkError,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.helpers import config_entry_oauth2_flow

from custom_components.netlink.config_flow import (
    NetlinkConfigFlow,
    _validate_connection,
)
from custom_components.netlink.const import CONF_DEVICE_ID, DOMAIN

from .conftest import DEVICE_ID, HOST, TOKEN, FakeNetlinkClient


DEVICE_INFO = {
    "device_id": DEVICE_ID,
    "device_name": "Meeting room",
    "mac_address": "00:11:22:33:44:55",
}


async def _start_manual_flow(hass: HomeAssistant) -> dict:
    """Start a user flow and select manual authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: HOST}
    )
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] is FlowResultType.FORM
    return result


async def test_validate_connection_uses_client_device_info() -> None:
    """Connection validation returns stable config-entry identity data."""
    client = AsyncMock()
    client.get_device_info.return_value.device_id = DEVICE_ID
    client.get_device_info.return_value.device_name = "Meeting room"
    client.get_device_info.return_value.mac_address = "00:11:22:33:44:55"

    with patch(
        "custom_components.netlink.config_flow.NetlinkClient", return_value=client
    ) as client_class:
        result = await _validate_connection(HOST, TOKEN, AsyncMock())

    assert result == DEVICE_INFO
    client_class.assert_called_once()


async def test_manual_flow_creates_entry(
    hass: HomeAssistant, netlink_client: FakeNetlinkClient
) -> None:
    """Manual authentication creates a config entry after validation."""
    result = await _start_manual_flow(hass)

    with patch(
        "custom_components.netlink.config_flow._validate_connection",
        AsyncMock(return_value=DEVICE_INFO),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: TOKEN}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Meeting room"
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_TOKEN: TOKEN,
        CONF_DEVICE_ID: DEVICE_ID,
    }


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (NetlinkAuthenticationError("invalid"), "invalid_auth"),
        (NetlinkConnectionError("offline"), "cannot_connect"),
        (NetlinkError("broken"), "unknown"),
    ],
)
async def test_manual_flow_reports_connection_errors(
    hass: HomeAssistant, error: Exception, expected_error: str
) -> None:
    """Manual authentication maps client failures to form errors."""
    result = await _start_manual_flow(hass)

    with patch(
        "custom_components.netlink.config_flow._validate_connection",
        AsyncMock(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: TOKEN}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


def _discovery_info(properties: dict) -> ZeroconfServiceInfo:
    """Build NetLink Zeroconf discovery data."""
    address = ip_address("192.0.2.10")
    return ZeroconfServiceInfo(
        ip_address=address,
        ip_addresses=[address],
        port=80,
        hostname="netlink.local.",
        type="_netlink._tcp.local.",
        name="Meeting room._netlink._tcp.local.",
        properties=properties,
    )


async def test_zeroconf_discovery_manual_flow(
    hass: HomeAssistant, netlink_client: FakeNetlinkClient
) -> None:
    """A discovered device can be configured with a manual token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery_info({"device_id": DEVICE_ID, "device_name": "Meeting room"}),
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discovery_manual"}
    )
    with patch(
        "custom_components.netlink.config_flow._validate_connection",
        AsyncMock(return_value=DEVICE_INFO),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: TOKEN}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == DEVICE_ID


async def test_zeroconf_rejects_incomplete_discovery(hass: HomeAssistant) -> None:
    """Discovery without stable identity data is rejected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery_info({}),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (NetlinkAuthenticationError("invalid"), "invalid_auth"),
        (NetlinkConnectionError("offline"), "cannot_connect"),
        (NetlinkError("broken"), "unknown"),
    ],
)
async def test_discovery_manual_reports_connection_errors(
    hass: HomeAssistant, error: Exception, expected_error: str
) -> None:
    """Discovery authentication maps client failures to form errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=_discovery_info({"device_id": DEVICE_ID, "device_name": "Meeting room"}),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discovery_manual"}
    )

    with patch(
        "custom_components.netlink.config_flow._validate_connection",
        AsyncMock(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: TOKEN}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_reauth_manual_updates_existing_entry(hass: HomeAssistant) -> None:
    """Manual reauthentication replaces the token and reloads the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Meeting room",
        data={CONF_HOST: HOST, CONF_TOKEN: TOKEN, CONF_DEVICE_ID: DEVICE_ID},
        unique_id=DEVICE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=dict(entry.data),
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reauth_confirm"}
    )

    with (
        patch(
            "custom_components.netlink.config_flow._validate_connection",
            AsyncMock(return_value=DEVICE_INFO),
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock()) as reload_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "new-token"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == "new-token"
    reload_entry.assert_awaited_once_with(entry.entry_id)


def test_oauth_flow_metadata() -> None:
    """OAuth flow exposes the expected authorization metadata."""
    flow = NetlinkConfigFlow()
    assert flow.logger.name == "custom_components.netlink.config_flow"
    assert flow.extra_authorize_data == {"response_type": "code"}


def _oauth_flow(hass: HomeAssistant, source: str = SOURCE_USER) -> NetlinkConfigFlow:
    """Build an initialized OAuth callback handler."""
    flow = NetlinkConfigFlow()
    flow.hass = hass
    flow.context = {"source": source}
    flow._host = HOST
    return flow


def test_register_oauth_implementation(hass: HomeAssistant) -> None:
    """OAuth endpoints are registered against the selected NetLink host."""
    flow = _oauth_flow(hass)
    with patch(
        "custom_components.netlink.config_flow.config_entry_oauth2_flow.async_register_implementation"
    ) as register:
        flow._register_oauth_implementation(DEVICE_ID)

    implementation = register.call_args.args[2]
    assert implementation.domain == DEVICE_ID
    assert implementation.authorize_url == f"http://{HOST}/oauth/authorize"
    assert implementation.token_url == f"http://{HOST}/api/oauth/token"


async def test_oauth_callback_creates_entry(hass: HomeAssistant) -> None:
    """A successful OAuth callback creates a device-bound config entry."""
    flow = _oauth_flow(hass)
    with (
        patch(
            "custom_components.netlink.config_flow._validate_connection",
            AsyncMock(return_value=DEVICE_INFO),
        ),
        patch.object(flow, "_register_oauth_implementation") as register,
    ):
        result = await flow.async_oauth_create_entry(
            {"token": {"access_token": TOKEN}, "implementation": HOST}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: HOST,
        CONF_TOKEN: TOKEN,
        CONF_DEVICE_ID: DEVICE_ID,
        "auth_implementation": DEVICE_ID,
    }
    register.assert_called_once_with(DEVICE_ID)


async def test_oauth_callback_requires_host(hass: HomeAssistant) -> None:
    """OAuth cannot complete without its originating device host."""
    flow = _oauth_flow(hass)
    flow._host = None
    result = await flow.async_oauth_create_entry({"token": {"access_token": TOKEN}})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "missing_host"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (NetlinkAuthenticationError("invalid"), "invalid_auth"),
        (NetlinkConnectionError("offline"), "cannot_connect"),
        (NetlinkError("broken"), "unknown"),
    ],
)
async def test_oauth_callback_reports_connection_errors(
    hass: HomeAssistant, error: Exception, reason: str
) -> None:
    """OAuth callback failures abort with stable user-facing reasons."""
    flow = _oauth_flow(hass)
    with patch(
        "custom_components.netlink.config_flow._validate_connection",
        AsyncMock(side_effect=error),
    ):
        result = await flow.async_oauth_create_entry({"token": {"access_token": TOKEN}})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_oauth_reauth_updates_existing_entry(hass: HomeAssistant) -> None:
    """OAuth reauthentication updates the existing entry and reloads it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Meeting room",
        data={CONF_HOST: HOST, CONF_TOKEN: TOKEN, CONF_DEVICE_ID: DEVICE_ID},
        unique_id=DEVICE_ID,
    )
    entry.add_to_hass(hass)
    flow = _oauth_flow(hass, SOURCE_REAUTH)
    flow.context["entry_id"] = entry.entry_id
    flow._netlink_reauth_entry_id = entry.entry_id
    flow._netlink_reauth_entry_data = dict(entry.data)

    with (
        patch(
            "custom_components.netlink.config_flow._validate_connection",
            AsyncMock(return_value=DEVICE_INFO),
        ),
        patch.object(flow, "_register_oauth_implementation"),
        patch.object(hass.config_entries, "async_reload", AsyncMock()) as reload_entry,
    ):
        result = await flow.async_oauth_create_entry(
            {"token": {"access_token": "new-token"}}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_TOKEN] == "new-token"
    reload_entry.assert_awaited_once_with(entry.entry_id)


@pytest.mark.parametrize(
    ("error", "expected_error"),
    [
        (NetlinkAuthenticationError("invalid"), "invalid_auth"),
        (NetlinkConnectionError("offline"), "cannot_connect"),
        (NetlinkError("broken"), "unknown"),
    ],
)
async def test_reauth_confirm_reports_connection_errors(
    hass: HomeAssistant, error: Exception, expected_error: str
) -> None:
    """Manual reauthentication keeps the form open after client failures."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Meeting room",
        data={CONF_HOST: HOST, CONF_TOKEN: TOKEN, CONF_DEVICE_ID: DEVICE_ID},
        unique_id=DEVICE_ID,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=dict(entry.data),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reauth_confirm"}
    )

    with patch(
        "custom_components.netlink.config_flow._validate_connection",
        AsyncMock(side_effect=error),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TOKEN: "new-token"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_steps_without_required_host_abort(hass: HomeAssistant) -> None:
    """Authentication steps fail closed when no host was established."""
    flow = _oauth_flow(hass)
    flow._host = None
    manual = await flow.async_step_manual({CONF_TOKEN: TOKEN})
    discovery = await flow.async_step_discovery_manual({CONF_TOKEN: TOKEN})
    oauth = await flow.async_step_pick_implementation()

    assert {manual["reason"], discovery["reason"], oauth["reason"]} == {"missing_host"}


async def test_authentication_step_delegates(hass: HomeAssistant) -> None:
    """OAuth menu steps delegate to the shared implementation picker."""
    flow = _oauth_flow(hass)
    expected = flow.async_abort(reason="delegated")
    with patch.object(
        flow,
        "async_step_pick_implementation",
        AsyncMock(return_value=expected),
    ) as pick:
        assert await flow.async_step_oauth() == expected
        assert await flow.async_step_reauth_oauth() == expected
    assert pick.await_count == 2


async def test_reconfigure_step_delegates_to_user(hass: HomeAssistant) -> None:
    """Reconfiguration restarts at host selection."""
    flow = _oauth_flow(hass)
    expected = flow.async_abort(reason="delegated")
    with patch.object(
        flow, "async_step_user", AsyncMock(return_value=expected)
    ) as user_step:
        assert await flow.async_step_reconfigure({}) == expected
    user_step.assert_awaited_once_with()


async def test_pick_oauth_implementation_registers_device_host(
    hass: HomeAssistant,
) -> None:
    """OAuth selection registers and selects the device-specific implementation."""
    flow = _oauth_flow(hass)
    expected = flow.async_abort(reason="delegated")
    with (
        patch.object(flow, "_register_oauth_implementation") as register,
        patch.object(
            config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
            "async_step_pick_implementation",
            AsyncMock(return_value=expected),
        ) as parent_step,
    ):
        result = await flow.async_step_pick_implementation()

    assert result == expected
    register.assert_called_once_with(HOST)
    parent_step.assert_awaited_once_with({"implementation": HOST})
