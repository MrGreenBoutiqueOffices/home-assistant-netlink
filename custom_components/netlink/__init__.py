"""The NetLink integration."""

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

from .const import CONF_DEVICE_ID, DOMAIN, PLATFORMS
from .coordinator import NetlinkDataUpdateCoordinator
from .entity import _get_suggested_area

_LOGGER = logging.getLogger(__name__)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options or config entry updates."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry to current version."""
    _LOGGER.debug(
        "Migrating NetLink config entry from version %s.%s",
        entry.version,
        entry.minor_version,
    )

    if entry.version == 1 and entry.minor_version < 2:
        # Remove the orphaned desk sub-device created by older versions.
        # Desk entities now live on the main controller device instead of a
        # separate sub-device, so the old device entry is no longer needed.
        device_registry = dr.async_get(hass)
        desk_identifier = f"netlink-{entry.data[CONF_DEVICE_ID]}-desk"
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, desk_identifier)}
        )
        if device is not None:
            device_registry.async_remove_device(device.id)
            _LOGGER.debug("Removed orphaned desk sub-device %s", desk_identifier)

        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NetLink from a config entry."""
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
        entry,
    )

    try:
        # Setup WebSocket connection and fetch initial data
        await coordinator.async_setup()
    except NetlinkAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
            translation_placeholders={
                "name": entry.title,
                "host": entry.data[CONF_HOST],
            },
        ) from err
    except (NetlinkConnectionError, NetlinkError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={
                "name": entry.title,
                "host": entry.data[CONF_HOST],
            },
        ) from err

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    # Register the main NetLink controller device
    device_registry = dr.async_get(hass)
    device_info = coordinator.device_info
    if device_info is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={
                "name": entry.title,
                "host": entry.data[CONF_HOST],
            },
        )
    device_name = device_info.device_name

    connections = (
        {(dr.CONNECTION_NETWORK_MAC, device_info.mac_address)}
        if device_info.mac_address
        else set()
    )

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"netlink-{entry.data[CONF_DEVICE_ID]}")},
        name=device_name,
        manufacturer="NetOS",
        model=device_info.model,
        sw_version=device_info.version,
        configuration_url=f"http://{entry.data[CONF_HOST]}",
        connections=connections,
        suggested_area=_get_suggested_area(device_name),
    )

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

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
