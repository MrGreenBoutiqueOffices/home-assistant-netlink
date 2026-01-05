# Netlink Home Assistant Integration

[![hacs_badge][hacs-badge]][hacs]
[![GitHub Release][release-shield]][releases]
[![Project Maintenance][maintenance-shield]][maintenance]
[![License][license-shield]][license]

Native Home Assistant integration for Netlink smart desk and monitor control systems.

## About

Netlink is the operating software for smart standing desks, developed by [NetOS](https://net-os.com/). The system powers smart desks in commercial office environments, most notably at [Mr.Green Offices](https://mrgreenoffices.nl/) locations throughout the Netherlands.

This native Home Assistant integration provides **real-time control** over Netlink-powered desks. Unlike traditional polling-based integrations, it uses WebSocket push updates for instant state synchronization, making it ideal for responsive automations and dashboards.

## Features

- 🔌 **WebSocket real-time updates** - Instant state changes via push notifications
- 🔍 **Automatic discovery** - Devices found via mDNS/Zeroconf
- 🔐 **OAuth 2.0 support** - Secure authentication with local OAuth server (recommended)
- 🪑 **Desk control** - Height adjustment, calibration, and status monitoring
- 🖥️ **Display control** - Power, brightness, volume, and input source
- 🌐 **Browser control** - Refresh capabilities
- 📊 **Rich entities** - Binary sensors, sensors, numbers, switches, selects, and buttons
- 🏠 **Native HA integration** - Config flow, device registry, and proper entity organization
- 🔑 **Reauthentication flow** - OAuth or manual re-authentication when needed
- 🔍 **Diagnostics support** - Download diagnostic data for troubleshooting
- 🎨 **Icons** - Entity icons defined via `icons.json`

## Requirements

- Home Assistant >= 2025.12.0
- Netlink device with REST API, WebSocket, and OAuth 2.0 support
- Authentication via OAuth 2.0 (recommended) or bearer token

## Installation

<details>
<summary><b>📦 Installation Methods</b> (click to expand)</summary>

### HACS (Custom Repository)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots (⋮) in the top right → "Custom repositories"
4. Add repository URL: `https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink`
5. Category: "Integration"
6. Click "Add"
7. Install "Netlink" from the integrations list
8. Restart Home Assistant

### Manual Installation

1. Download the [latest release](https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink/releases)
2. Extract and copy `custom_components/netlink` to your HA config directory
3. Restart Home Assistant

</details>

## Configuration

The integration supports both **automatic discovery** (mDNS/Zeroconf) and **manual setup**.

<details>
<summary><b>⚙️ Setup Instructions</b> (click to expand)</summary>

### Automatic Discovery (Recommended)

If your Netlink device is discovered via mDNS/Zeroconf, it will appear automatically:

1. Go to **Settings** → **Devices & Services**
2. Find the discovered Netlink device in the list
3. Click **"Configure"**
4. Choose authentication method:
   - **OAuth 2.0** (Recommended): Click **"OAuth 2.0"** and follow the browser redirect to authorize
   - **Manual Token**: Click **"Manual token entry"** and enter your bearer token
5. Click **"Submit"**

The device will be added immediately.

### Manual Setup

If automatic discovery doesn't work:

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for **"Netlink"**
4. Enter the **host** (IP address or hostname)
5. Choose authentication method:
   - **OAuth 2.0** (Recommended): Click **"OAuth 2.0"** and follow the browser redirect to authorize
   - **Manual Token**: Click **"Manual token entry"** and enter your bearer token
6. Click **"Submit"**

The device will be added immediately.

</details>

## Entities

<details>
<summary><b>📊 Entity Overview</b> (click to expand)</summary>

### Devices Created

Each Netlink device creates multiple HA devices:

- **Main device**: `{device_name}` (Browser entities)
- **Desk device**: `{device_name} (Desk)` (Desk entities)
- **Display device(s)**: `{device_name} (Display {bus_id})` (Per display)

### 🪑 Desk Entities

| Entity Type | Entity | Description |
|------------|--------|-------------|
| **Binary Sensor** | `binary_sensor.desk_moving` | Movement status |
| **Sensor** | `sensor.desk_height` | Current height (cm) |
| **Sensor** | `sensor.desk_mode` | Operation mode |
| **Sensor** | `sensor.desk_error` | Error messages |
| **Number** | `number.desk_target_height` | Set height (62-127 cm) |
| **Switch** | `switch.desk_beep` | Beep on/off |
| **Button** | `button.desk_stop` | Stop movement |
| **Button** | `button.desk_reset` | Reset desk |
| **Button** | `button.desk_calibrate` | Calibrate (disabled by default) |

### 🖥️ Display Entities (per display)

| Entity Type | Entity | Description |
|------------|--------|-------------|
| **Sensor** | `sensor.display_{bus_id}_brightness` | Current brightness (%) |
| **Sensor** | `sensor.display_{bus_id}_volume` | Current volume (%) |
| **Sensor** | `sensor.display_{bus_id}_power` | Power state |
| **Sensor** | `sensor.display_{bus_id}_source` | Current input source |
| **Sensor** | `sensor.display_{bus_id}_error` | Error messages |
| **Switch** | `switch.display_{bus_id}_power` | Power on/off |
| **Number** | `number.display_{bus_id}_brightness` | Set brightness (0-100%) |
| **Number** | `number.display_{bus_id}_volume` | Set volume (0-100%) |
| **Select** | `select.display_{bus_id}_source` | Input source selection |

> **Note**: Display control entities are only created if the display supports them (brightness, volume, source).

### 🌐 Browser Entities

| Entity Type | Entity | Description |
|------------|--------|-------------|
| **Button** | `button.browser_refresh` | Refresh browser |

</details>

## Migration from MQTT

<details>
<summary><b>🔄 Migrating from MQTT</b> (click to expand)</summary>

This integration is fully compatible with the MQTT-based setup:

- ✅ **Device IDs** are identical for smooth migration
- ✅ **Entity naming** follows the same pattern
- ✅ **Both can coexist** - Run MQTT and native side-by-side

### Migration Steps

1. Install the native integration (keep MQTT running)
2. Verify all entities work correctly
3. Disable MQTT discovery for Netlink (optional)
4. Update automations to use native entities
5. Remove MQTT configuration when ready

</details>

## Troubleshooting

<details>
<summary><b>🔧 Common Issues</b> (click to expand)</summary>

### Device not discovered
- Ensure mDNS/Zeroconf is enabled on your network
- Try **manual setup** instead
- Check firewall rules (port 80 for REST/WebSocket)

### Authentication errors
- **OAuth 2.0** (Recommended):
  - Ensure the device OAuth server is running
  - Check that you can access `http://<device-ip>/oauth/authorize` in your browser
  - **Token validity**: Long-lived tokens with 100 year expiry (effectively permanent for local devices)
  - **No refresh needed**: Tokens remain valid for the device lifetime
  - **Re-authentication**: Only needed if device `REST_BEARER_TOKEN` changes or device is reset
  - If authentication expires, Home Assistant triggers automatic reauth flow - choose OAuth or manual token entry
- **Manual Token**:
  - Verify bearer token matches device configuration
  - Check `REST_BEARER_TOKEN` environment variable
  - Tokens do not expire (static configuration)
  - Navigate to **Settings** → **Devices & Services** → **Netlink** → **Configure** to update token manually

### Connection errors
- Confirm device is reachable: `ping <device_ip>`
- Review HA logs: **Settings** → **System** → **Logs**
- Check WebSocket connection in logs

### Entities unavailable
- WebSocket connection may be down
- Integration auto-reconnects (exponential backoff: 1s → 60s)
- Entities show "unavailable" during disconnection

### Display controls not appearing
- Display must support the feature (brightness/volume/source)
- Entities are created dynamically based on capabilities
- Check device logs for display detection

### Getting diagnostic information
- Navigate to **Settings** → **Devices & Services** → **Netlink**
- Click on your Netlink device
- Click **Download diagnostics** (three dots menu)
- Share the downloaded JSON file when reporting issues
- Diagnostics include: device info, coordinator state, connection status, entity states
- Sensitive data (tokens) is automatically redacted

</details>

## Development

Built on top of [`pynetlink`](https://github.com/MrGreenBoutiqueOffices/python-netlink) - the production-ready Python client library.

### Local Development

```bash
# Clone repository
git clone https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink.git
cd home-assistant-netlink

# Link to HA config directory
ln -s $(pwd)/custom_components/netlink ~/.homeassistant/custom_components/

# Restart Home Assistant
```

### Contributing

We welcome contributions! Please read the [contribution guidelines](CONTRIBUTING.md) before submitting PRs.

## Authors & contributors

The original setup of this repository is created by [Klaas Schoute](https://github.com/klaasnicolaas) for [NetOS](https://net-os.com/) and [Mr.Green Boutique Offices](https://mrgreenoffices.nl/).

Thanks to everyone who already contributed! ❤️

<a href="https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=MrGreenBoutiqueOffices/home-assistant-netlink" />
</a>

For a full list of all authors and contributors, check [the contributor's page][contributors].

## License

This project is licensed under the LGPL-3.0-or-later License - see the [LICENSE](LICENSE) file for details.

## Credits

Built with ❤️ using the [`pynetlink`](https://pypi.org/project/pynetlink/) library.

<!-- Links -->
[contributors]: https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink/graphs/contributors

<!-- Badge Links -->
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs]: https://github.com/hacs/integration
[release-shield]: https://img.shields.io/github/release/MrGreenBoutiqueOffices/home-assistant-netlink.svg
[releases]: https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink/releases
[maintenance-shield]: https://img.shields.io/maintenance/yes/2025.svg
[maintenance]: https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink
[license-shield]: https://img.shields.io/github/license/MrGreenBoutiqueOffices/home-assistant-netlink.svg
[license]: LICENSE
