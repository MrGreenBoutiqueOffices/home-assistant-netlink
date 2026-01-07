"""Constants for the Netlink integration."""

from homeassistant.const import Platform

DOMAIN = "netlink"

# Config entry data keys
CONF_DEVICE_ID = "device_id"
CONF_AUTH_IMPLEMENTATION = "auth_implementation"

# Platforms
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.BUTTON,
]
