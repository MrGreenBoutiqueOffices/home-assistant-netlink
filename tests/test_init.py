"""Tests for NetLink config-entry lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from pynetlink import NetlinkAuthenticationError, NetlinkConnectionError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from custom_components.netlink import (
    _async_update_listener,
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.netlink.const import CONF_DEVICE_ID, DOMAIN

from .conftest import DEVICE_ID, HOST, TOKEN, FakeNetlinkClient


async def test_migrate_entry_removes_legacy_desk_device(
    hass: HomeAssistant,
) -> None:
    """Migration 1.2 removes the obsolete desk sub-device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Meeting room",
        data={CONF_HOST: HOST, CONF_TOKEN: TOKEN, CONF_DEVICE_ID: DEVICE_ID},
        unique_id=DEVICE_ID,
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    legacy = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"netlink-{DEVICE_ID}-desk")},
        name="Legacy desk",
    )

    assert await async_migrate_entry(hass, entry)
    assert entry.minor_version == 2
    assert registry.async_get(legacy.id) is None


@pytest.mark.parametrize(
    ("error", "expected_exception"),
    [
        (NetlinkAuthenticationError("invalid"), ConfigEntryAuthFailed),
        (NetlinkConnectionError("offline"), ConfigEntryNotReady),
    ],
)
async def test_setup_maps_client_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    expected_exception: type[Exception],
) -> None:
    """Setup maps raw client failures to config-entry lifecycle errors."""
    with patch(
        "custom_components.netlink.NetlinkDataUpdateCoordinator.async_setup",
        AsyncMock(side_effect=error),
    ):
        with pytest.raises(expected_exception):
            await async_setup_entry(hass, mock_config_entry)


async def test_setup_requires_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Setup fails closed if no device identity was fetched."""
    with patch(
        "custom_components.netlink.NetlinkDataUpdateCoordinator.async_setup",
        AsyncMock(),
    ):
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


async def test_update_listener_reloads_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Config-entry updates trigger a reload."""
    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as reload_entry:
        await _async_update_listener(hass, mock_config_entry)
    reload_entry.assert_awaited_once_with(mock_config_entry.entry_id)


async def test_unload_disconnects_client(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Successful unload removes platforms and disconnects pynetlink."""
    assert await async_unload_entry(hass, setup_integration)
    assert netlink_client.connected is False


async def test_failed_platform_unload_preserves_connection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A failed platform unload does not tear down runtime data."""
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=False),
    ):
        assert await async_unload_entry(hass, mock_config_entry) is False


async def test_coordinator_setup_disconnects_after_connect_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """A failed WebSocket connection is cleaned up before setup retries."""
    netlink_client.connect_error = NetlinkConnectionError("offline")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is False
    assert netlink_client.connected is False


async def test_coordinator_setup_maps_rest_authentication_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Authentication failures during the first snapshot start reauthentication."""
    netlink_client.rest_error = NetlinkAuthenticationError("invalid")
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id) is False


async def test_setup_removes_stale_display_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    netlink_client: FakeNetlinkClient,
) -> None:
    """Setup removes displays no longer present in authoritative inventory."""
    mock_config_entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    stale = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, f"netlink-{DEVICE_ID}-display-99")},
        name="Stale display",
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get(stale.id) is None
