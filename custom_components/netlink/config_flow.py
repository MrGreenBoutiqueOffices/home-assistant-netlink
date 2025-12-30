"""Config flow for Netlink integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from pynetlink import (
    NetlinkAuthenticationError,
    NetlinkConnectionError,
    NetlinkError,
    NetlinkTimeoutError,
    NetlinkClient,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import CONF_DEVICE_ID, CONF_MAC_ADDRESS, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_TOKEN): str,
    }
)


async def validate_connection(host: str, token: str, session) -> dict[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    client = NetlinkClient(host=host, token=token, session=session)

    try:
        # Test connection by fetching device info
        device_info = await client.get_device_info()

        return {
            "device_id": device_info.device_id,
            "device_name": device_info.device_name,
            "title": f"Netlink {device_info.device_name}",
        }
    finally:
        await client.disconnect()


class NetlinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Netlink."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        self.context["title_placeholders"] = {"name": "Netlink"}
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)

            try:
                # Validate connection
                info = await validate_connection(
                    user_input[CONF_HOST], user_input[CONF_TOKEN], session
                )

                # Check if already configured
                await self.async_set_unique_id(info["device_id"])
                self._abort_if_unique_id_configured()

                # Create entry
                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_TOKEN: user_input[CONF_TOKEN],
                        CONF_DEVICE_ID: info["device_id"],
                    },
                )
            except NetlinkAuthenticationError:
                errors["base"] = "invalid_auth"
            except (NetlinkConnectionError, NetlinkTimeoutError):
                errors["base"] = "cannot_connect"
            except NetlinkError:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by zeroconf discovery."""
        host = discovery_info.host

        properties = discovery_info.properties or {}
        device_id = str(properties["device_id"])
        device_name = str(properties["device_name"])
        mac_address = properties.get("mac_address")

        if device_id:
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()

        self.context["device_id"] = device_id
        self.context["device_name"] = device_name
        self.context["host"] = host
        self.context["mac_address"] = mac_address
        self.context["title_placeholders"] = {"name": device_name}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery and ask for token."""
        errors: dict[str, str] = {}
        device_name = self.context.get("device_name", "Netlink")
        host = self.context.get("host")
        mac_address = self.context.get("mac_address")

        if user_input is not None:
            token = user_input[CONF_TOKEN]
            session = async_get_clientsession(self.hass)

            try:
                # Validate connection with provided token
                info = await validate_connection(host, token, session)

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

                return self.async_create_entry(
                    title=info["title"],
                    data=data,
                )
            except NetlinkAuthenticationError:
                errors["base"] = "invalid_auth"
            except (NetlinkConnectionError, NetlinkTimeoutError):
                errors["base"] = "cannot_connect"
            except NetlinkError:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="discovery_confirm",
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
                await validate_connection(host, token, session)

                # Update the config entry with new token
                entry = await self.async_set_unique_id(entry_data.get(CONF_DEVICE_ID))
                if entry:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, CONF_TOKEN: token},
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

            except NetlinkAuthenticationError:
                errors["base"] = "invalid_auth"
            except (NetlinkConnectionError, NetlinkTimeoutError):
                errors["base"] = "cannot_connect"
            except NetlinkError:
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
