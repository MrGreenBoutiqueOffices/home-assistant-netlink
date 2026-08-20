"""Constants for the NetLink integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "netlink"

# Config entry data keys
CONF_DEVICE_ID = "device_id"
CONF_AUTH_IMPLEMENTATION = "auth_implementation"

# Connectivity lifecycle
WEBSOCKET_DISCONNECT_GRACE = timedelta(seconds=15)
RECONCILIATION_INTERVAL = timedelta(minutes=15)

# Platforms
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.BUTTON,
]
