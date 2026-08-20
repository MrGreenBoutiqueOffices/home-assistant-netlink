# FAQ / Troubleshooting

This page collects the most common issues when installing and using the NetLink Home Assistant integration.

## Contents

- [Device not discovered](#device-not-discovered)
- [Authentication errors](#authentication-errors)
- [Authorization policy errors](#authorization-policy-errors)
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
- Prefer the dedicated Home Assistant service token configured on the NetLink device
- During migration, verify that the legacy `REST_BEARER_TOKEN` still matches the device configuration

**Notes**
- Tokens do not expire automatically (static configuration)
- Reauthenticate the existing entry to rotate a token without recreating entities or devices
- Never enter a signing maintenance code; Home Assistant is a machine integration

## Authorization policy errors

Newer devices advertise the commands and sensitive events allowed for the connected
identity. If a control entity is unavailable while the connection is healthy, download
diagnostics and inspect the non-sensitive authorization section.

- Missing expected commands normally mean the wrong service token or an incomplete server policy
- Home Assistant does not request a maintenance PIN and does not bypass an explicit WebSocket denial through REST
- Older devices without authorization discovery retain their existing behavior
- If access-code permission is missing, only the access-code entities become unavailable

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

1. Go to **Settings** → **Devices & Services** → **NetLink**
2. Click your NetLink device
3. Open the menu (⋮) and choose **Download diagnostics**

**What diagnostics include**
- Device information
- Coordinator state
- Connection status
- Entity states
- Authorization policy version, allowed/missing command identifiers, and failure category

**Privacy**
- Sensitive data (tokens) is automatically redacted
- Daily access code values are explicitly redacted from diagnostics exports
