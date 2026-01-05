# FAQ / Troubleshooting

This page collects the most common issues when installing and using the Netlink Home Assistant integration.

## Contents

- [Device not discovered](#device-not-discovered)
- [Authentication errors](#authentication-errors)
- [Connection errors](#connection-errors)
- [Entities show as unavailable](#entities-show-as-unavailable)
- [Display controls not appearing](#display-controls-not-appearing)
- [Getting diagnostic information](#getting-diagnostic-information)

## Device not discovered

**Symptoms**
- The integration does not show up under discovered devices
- Adding the integration manually is the only option

**What to check**
- Ensure mDNS/Zeroconf is enabled on your network
- Try the manual setup flow in Home Assistant
- Check firewall rules (port 80 for REST/WebSocket)

## Authentication errors

### OAuth 2.0 (recommended)

**What to check**
- Ensure the device OAuth server is running
- Verify you can open `http://<device-ip>/oauth/authorize` in your browser

**Token behavior**
- Tokens are long-lived (configured with a 100-year expiry for local devices)
- No refresh is needed for normal operation

**When re-authentication is needed**
- Only if the device `REST_BEARER_TOKEN` changes or the device is reset
- If Home Assistant detects auth failure, it will prompt a re-auth flow (choose OAuth or manual token entry)

### Manual token

**What to check**
- Verify the bearer token matches the device configuration
- Check the `REST_BEARER_TOKEN` environment variable on the Netlink device

**Notes**
- Tokens do not expire (static configuration)
- To update the token in Home Assistant: **Settings** → **Devices & Services** → **Netlink** → **Configure**

## Connection errors

**What to check**
- Confirm the device is reachable: `ping <device_ip>`
- Review Home Assistant logs: **Settings** → **System** → **Logs**
- Look for WebSocket connection errors and reconnect attempts

## Entities show as unavailable

**Why this happens**
- The WebSocket connection may be down temporarily

**What to expect**
- The integration auto-reconnects using exponential backoff (1s → 60s)
- Entities can show as `unavailable` while disconnected

## Display controls not appearing

**Why this happens**
- The display must support the specific feature (brightness/volume/source)

**What to check**
- Entities are created dynamically based on detected capabilities
- Check device logs for display detection and capability reporting

## Getting diagnostic information

Diagnostics are the fastest way to troubleshoot.

1. Go to **Settings** → **Devices & Services** → **Netlink**
2. Click your Netlink device
3. Open the menu (⋮) and choose **Download diagnostics**

**What diagnostics include**
- Device information
- Coordinator state
- Connection status
- Entity states

**Privacy**
- Sensitive data (tokens) is automatically redacted
