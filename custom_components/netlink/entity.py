"""Entity helpers for the NetLink integration."""

from __future__ import annotations

import re

from pynetlink import (
    NetlinkAuthorizationError,
    NetlinkCommandError,
    NetlinkConnectionError,
    NetlinkTimeoutError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, DOMAIN
from .coordinator import NetlinkDataUpdateCoordinator


def _get_suggested_area(device_name: str | None) -> str | None:
    """Get suggested area from device name."""
    if not device_name:
        return None
    # Remove trailing " - 1", " -1", "- 1", "-1", " 1", etc.
    return re.sub(r"[\s-]*\d+$", "", device_name).strip()


class NetlinkBaseEntity(CoordinatorEntity[NetlinkDataUpdateCoordinator]):
    """Base entity for NetLink platforms."""

    command: str | None = None

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entry = entry
        self.device_id = entry.data[CONF_DEVICE_ID]
        self.device_name = self.coordinator.device_info.device_name
        self.device_identifier = f"netlink-{self.device_id}"
        self.suggested_area = _get_suggested_area(self.device_name)

    def _device_sw_version(self) -> str | None:
        """Return device software version if known."""
        return self.coordinator.device_info.version

    @property
    def available(self) -> bool:
        """Return availability based on connectivity and advertised policy."""
        return super().available and (
            self.command is None or self.coordinator.command_allowed(self.command)
        )

    def _command_error(self, err: Exception) -> HomeAssistantError:
        """Translate a client command error without exposing sensitive details."""
        if isinstance(err, NetlinkAuthorizationError):
            self.coordinator.record_authorization_failure(err)
            key = "command_not_authorized"
        elif isinstance(err, (NetlinkConnectionError, NetlinkTimeoutError)):
            key = "command_unavailable"
        elif isinstance(err, NetlinkCommandError):
            key = "command_failed"
        else:  # pragma: no cover - callers only pass the public client hierarchy
            raise err
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=key,
            translation_placeholders={"name": self.device_name},
        )


class NetlinkControllerEntity(NetlinkBaseEntity):
    """Entity attached to the main NetLink controller device."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry info for the main controller."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_identifier)},
            name=self.device_name,
            manufacturer="NetOS",
            model=self.coordinator.device_info.model,
            sw_version=self._device_sw_version(),
            suggested_area=self.suggested_area,
            configuration_url=f"http://{self.entry.data[CONF_HOST]}",
        )


class NetlinkDisplayEntity(NetlinkBaseEntity):
    """Entity attached to a specific display."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NetlinkDataUpdateCoordinator,
        entry: ConfigEntry,
        bus_id: int | str,
    ) -> None:
        """Initialize display entity."""
        super().__init__(coordinator, entry)
        self.bus_id = str(bus_id)

    def _display_model(self) -> str:
        """Return display model name if known."""
        display_info = self.coordinator.display_info
        display_states = self.coordinator.data["displays"]

        summary = display_info.get(self.bus_id)
        state = display_states.get(self.bus_id)
        return (
            getattr(summary, "model", None)
            or getattr(state, "model", None)
            or "Display"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry info for the display."""
        state = self.coordinator.data["displays"].get(self.bus_id)
        serial = getattr(state, "serial_number", None) if state else None
        model = self._display_model()

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.device_identifier}-display-{self.bus_id}")},
            name=f"{self.device_name} (Display {self.bus_id})",
            manufacturer="NetOS",
            model=model,
            sw_version=self._device_sw_version(),
            serial_number=serial,
            suggested_area=self.suggested_area,
            via_device=(DOMAIN, self.device_identifier),
            configuration_url=f"http://{self.entry.data[CONF_HOST]}",
        )
