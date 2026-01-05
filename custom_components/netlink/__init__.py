"""The Netlink integration."""

from __future__ import annotations

import logging

from pynetlink import (
    NetlinkAuthenticationError,
    NetlinkClient,
    NetlinkConnectionError,
    NetlinkError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_ID, CONF_MAC_ADDRESS, DOMAIN, PLATFORMS
from .coordinator import NetlinkDataUpdateCoordinator
from .entity import _get_suggested_area

_LOGGER = logging.getLogger(__name__)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options or config entry updates."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Netlink from a config entry."""
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    session = async_get_clientsession(hass)

    # Create client
    client = NetlinkClient(
        host=entry.data[CONF_HOST],
        token=entry.data[CONF_TOKEN],
        session=session,
    )

    # Create coordinator
    coordinator = NetlinkDataUpdateCoordinator(
        hass,
        client,
        entry.data[CONF_DEVICE_ID],
    )

    try:
        # Setup WebSocket connection and fetch initial data
        await coordinator.async_setup()
    except NetlinkAuthenticationError as err:
        raise ConfigEntryAuthFailed(err) from err
    except NetlinkConnectionError as err:
        raise ConfigEntryNotReady(err) from err
    except NetlinkError as err:
        raise ConfigEntryNotReady(err) from err

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    # Register the main Netlink controller device
    device_registry = dr.async_get(hass)
    mac_address = entry.data.get(CONF_MAC_ADDRESS)
    device_info = coordinator.device_info
    if device_info is None:
        raise ConfigEntryNotReady("Device info not available after setup")
    device_name = device_info.device_name

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"netlink-{entry.data[CONF_DEVICE_ID]}")},
        name=device_name,
        manufacturer="NetOS",
        model=device_info.model,
        sw_version=device_info.version,
        configuration_url=f"http://{entry.data[CONF_HOST]}",
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)}
        if mac_address
        else set(),
        suggested_area=_get_suggested_area(device_name),
    )

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Disconnect WebSocket and cleanup
        coordinator: NetlinkDataUpdateCoordinator = entry.runtime_data
        await coordinator.async_shutdown()

    return unload_ok
