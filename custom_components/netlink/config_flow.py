"""Config flow for Netlink integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
from pynetlink import (
    NetlinkAuthenticationError,
    NetlinkClient,
    NetlinkConnectionError,
    NetlinkError,
    NetlinkTimeoutError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_AUTH_IMPLEMENTATION, CONF_DEVICE_ID, CONF_MAC_ADDRESS, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _validate_connection(
    host: str, token: str, session: ClientSession
) -> dict[str, str]:
    """Validate the connection to a Netlink device.

    Returns a dict with device_id and device_name on success.
    Raises NetlinkAuthenticationError, NetlinkConnectionError, or NetlinkError on failure.
    """
    client = NetlinkClient(host=host, token=token, session=session)

    # Fetch device info to validate connection
    device_info = await client.get_device_info()

    return {
        "device_id": device_info.device_id,
        "device_name": device_info.device_name,
    }


class NetlinkConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for Netlink with OAuth2 support."""

    VERSION = 1
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._host: str | None = None
        self._device_name: str | None = None
        self._device_id: str | None = None
        self._mac_address: str | None = None

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"response_type": "code"}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup - ask for host first."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store host for later use
            self._host = user_input[CONF_HOST]
            # Now show auth method menu
            return await self.async_step_auth_method()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )

    async def async_step_auth_method(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask user to choose authentication method."""
        return self.async_show_menu(
            step_id="auth_method",
            menu_options=["oauth", "manual"],
        )

    async def async_step_oauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle OAuth authentication."""
        return await self.async_step_pick_implementation(user_input)

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual token entry."""
        errors: dict[str, str] = {}
        if not self._host:
            return self.async_abort(reason="missing_host")

        if user_input is not None:
            token = user_input[CONF_TOKEN]
            session = async_get_clientsession(self.hass)

            try:
                # Validate connection (host already set from async_step_user)
                info = await _validate_connection(self._host, token, session)

                # Check if already configured
                await self.async_set_unique_id(info["device_id"])
                self._abort_if_unique_id_configured()

                # Create entry
                _LOGGER.debug(
                    "Creating config entry for %s at %s",
                    info["device_name"],
                    self._host,
                )
                return self.async_create_entry(
                    title=info["device_name"],
                    data={
                        CONF_HOST: self._host,
                        CONF_TOKEN: token,
                        CONF_DEVICE_ID: info["device_id"],
                    },
                )
            except NetlinkAuthenticationError:
                _LOGGER.error("Authentication failed for %s", self._host)
                errors["base"] = "invalid_auth"
            except (NetlinkConnectionError, NetlinkTimeoutError):
                _LOGGER.error("Cannot connect to Netlink device at %s", self._host)
                errors["base"] = "cannot_connect"
            except NetlinkError:
                _LOGGER.exception("Unknown error connecting to %s", self._host)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
            description_placeholders={
                "host": self._host or "unknown",
            },
        )

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry after OAuth flow completes."""
        token = data["token"]["access_token"]

        _LOGGER.debug("Finishing OAuth configuration for %s", self._host)

        # Validate the token and get device info
        session = async_get_clientsession(self.hass)
        try:
            if not self._host:
                return self.async_abort(reason="missing_host")

            info = await _validate_connection(self._host, token, session)

            # Check if already configured
            if not self.unique_id:
                await self.async_set_unique_id(info["device_id"])
            self._abort_if_unique_id_configured()

            # Create entry
            entry_data = {
                CONF_HOST: self._host,
                CONF_TOKEN: token,
                CONF_DEVICE_ID: self._device_id or info["device_id"],
                CONF_AUTH_IMPLEMENTATION: data[CONF_AUTH_IMPLEMENTATION],
            }
            if self._mac_address:
                entry_data[CONF_MAC_ADDRESS] = self._mac_address

            _LOGGER.debug(
                "Creating config entry for %s at %s via OAuth",
                info["device_name"],
                self._host,
            )
            return self.async_create_entry(
                title=info["device_name"],
                data=entry_data,
            )
        except NetlinkAuthenticationError:
            _LOGGER.error("OAuth authentication failed for %s", self._host)
            return self.async_abort(reason="invalid_auth")
        except (NetlinkConnectionError, NetlinkTimeoutError):
            _LOGGER.error("Cannot connect to Netlink device at %s", self._host)
            return self.async_abort(reason="cannot_connect")
        except NetlinkError:
            _LOGGER.exception("Unknown error during OAuth flow for %s", self._host)
            return self.async_abort(reason="unknown")

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        host = discovery_info.host

        properties = discovery_info.properties or {}
        device_id = properties.get("device_id")
        device_name = properties.get("device_name")
        mac_address = discovery_info.mac_address

        _LOGGER.debug("Discovered Netlink device %s at %s", device_name, host)

        if not device_id or not device_name:
            return self.async_abort(reason="unknown")

        if device_id:
            await self.async_set_unique_id(device_id)
            updates = {CONF_HOST: host}
            if mac_address:
                updates[CONF_MAC_ADDRESS] = mac_address
            self._abort_if_unique_id_configured(updates=updates)

        # Store for OAuth flow
        self._host = host
        self._device_name = device_name
        self._device_id = device_id
        self._mac_address = mac_address

        self.context["device_id"] = device_id
        self.context["device_name"] = device_name
        self.context["host"] = host
        self.context["mac_address"] = mac_address
        self.context["title_placeholders"] = {"name": device_name}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery and choose authentication method."""
        return self.async_show_menu(
            step_id="discovery_confirm",
            menu_options=["oauth", "discovery_manual"],
            description_placeholders={
                "name": self._device_name or "Netlink",
                "host": self._host or "unknown",
            },
        )

    async def async_step_discovery_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual token entry after discovery."""
        errors: dict[str, str] = {}
        device_name = self._device_name or self.context.get("device_name", "Netlink")
        host = self._host or self.context.get("host")
        mac_address = self._mac_address or self.context.get("mac_address")

        if user_input is not None:
            token = user_input[CONF_TOKEN]
            session = async_get_clientsession(self.hass)

            try:
                # Validate connection with provided token
                info = await _validate_connection(host, token, session)

                if not self.unique_id:
                    await self.async_set_unique_id(info["device_id"])
                    self._abort_if_unique_id_configured()

                # Create entry
                data = {
                    CONF_HOST: host,
                    CONF_TOKEN: token,
                    CONF_DEVICE_ID: info["device_id"],
                }
                if mac_address:
                    data[CONF_MAC_ADDRESS] = mac_address

                _LOGGER.debug(
                    "Creating config entry for %s at %s after discovery",
                    info["device_name"],
                    host,
                )
                return self.async_create_entry(
                    title=info["device_name"],
                    data=data,
                )
            except NetlinkAuthenticationError:
                _LOGGER.error("Authentication failed for %s", host)
                errors["base"] = "invalid_auth"
            except (NetlinkConnectionError, NetlinkTimeoutError):
                _LOGGER.error("Cannot connect to Netlink device at %s", host)
                errors["base"] = "cannot_connect"
            except NetlinkError:
                _LOGGER.exception("Unknown error connecting to %s", host)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="discovery_manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "name": device_name,
                "host": host,
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauthentication flow."""
        _LOGGER.debug("Starting reauthentication for %s", entry_data.get(CONF_HOST))
        # Store entry for later use
        self.context["entry_data"] = entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication and ask for new token."""
        errors: dict[str, str] = {}
        entry_data = self.context.get("entry_data", {})
        host = entry_data.get(CONF_HOST, "")

        if user_input is not None:
            token = user_input[CONF_TOKEN]
            session = async_get_clientsession(self.hass)

            try:
                # Validate connection with new token
                await _validate_connection(host, token, session)

                # Update the config entry with new token
                entry = await self.async_set_unique_id(entry_data.get(CONF_DEVICE_ID))
                if entry:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, CONF_TOKEN: token},
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    _LOGGER.debug("Reauthentication successful for %s", host)
                    return self.async_abort(reason="reauth_successful")

            except NetlinkAuthenticationError:
                _LOGGER.error(
                    "Reauthentication failed for %s: invalid credentials", host
                )
                errors["base"] = "invalid_auth"
            except (NetlinkConnectionError, NetlinkTimeoutError):
                _LOGGER.error(
                    "Cannot connect to Netlink device at %s during reauth", host
                )
                errors["base"] = "cannot_connect"
            except NetlinkError:
                _LOGGER.exception("Unknown error during reauthentication for %s", host)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TOKEN): str,
                }
            ),
            errors=errors,
            description_placeholders={
                "host": host,
            },
        )

    async def async_step_pick_implementation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick OAuth implementation - creates device-specific implementation."""
        if not self._host:
            # Should not happen - host must be set before OAuth
            return self.async_abort(reason="missing_host")

        _LOGGER.debug("Starting OAuth flow for %s", self._host)

        # Create device-specific LocalOAuth2Implementation
        implementation = config_entry_oauth2_flow.LocalOAuth2Implementation(
            self.hass,
            self._device_id or self._host,
            client_id="home-assistant",
            client_secret="",  # Public client - no secret needed
            authorize_url=f"http://{self._host}/oauth/authorize",  # Frontend route
            token_url=f"http://{self._host}/api/oauth/token",  # API endpoint
        )

        # Register implementation for this flow
        config_entry_oauth2_flow.async_register_implementation(
            self.hass, DOMAIN, implementation
        )

        # Continue with standard OAuth flow
        return await super().async_step_pick_implementation(user_input)
