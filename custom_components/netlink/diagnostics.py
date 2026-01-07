"""Diagnostics support for Netlink."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import NetlinkDataUpdateCoordinator

TO_REDACT = {CONF_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: NetlinkDataUpdateCoordinator = entry.runtime_data

    # Serialize device info
    device_info_dict = None
    if coordinator.device_info:
        device_info_dict = {
            "device_id": coordinator.device_info.device_id,
            "device_name": coordinator.device_info.device_name,
            "model": coordinator.device_info.model,
            "version": coordinator.device_info.version,
            "api_version": coordinator.device_info.api_version,
            "mac_address": coordinator.device_info.mac_address,
        }

    # Serialize coordinator data
    coordinator_data_dict = {}
    if coordinator.data:
        # Desk data
        if "desk" in coordinator.data:
            desk = coordinator.data["desk"]
            coordinator_data_dict["desk"] = {
                "capabilities": desk.capabilities,
                "inventory": desk.inventory,
                "state": {
                    "height": desk.state.height,
                    "target": desk.state.target,
                    "moving": desk.state.moving,
                    "mode": desk.state.mode,
                    "beep": desk.state.beep,
                    "error": desk.state.error,
                },
            }

        # Display data (Display objects with full state)
        if "displays" in coordinator.data:
            displays_dict = {}
            for bus_id, display in coordinator.data["displays"].items():
                displays_dict[bus_id] = {
                    "bus": display.bus,
                    "model": display.model,
                    "type": display.type,
                    "serial_number": display.serial_number,
                    "state": {
                        "power": display.state.power,
                        "brightness": display.state.brightness,
                        "volume": display.state.volume,
                        "source": display.state.source,
                        "error": display.state.error,
                    },
                }
            coordinator_data_dict["displays"] = displays_dict

    # WebSocket connection state
    client_state = {
        "connected": coordinator.client.connected
        if hasattr(coordinator.client, "connected")
        else None,
        "host": entry.data.get("host"),
    }

    return {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "device_info": device_info_dict,
        "coordinator": {
            "name": coordinator.name,
            "last_update_success": coordinator.last_update_success,
            "data": coordinator_data_dict,
        },
        "client": client_state,
    }
