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

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MrGreenBoutiqueOffices&repository=home-assistant-netlink&category=integration)

The recommended way to install this integration is via **HACS**. If you prefer, you can also install it manually.

### Option 1 — HACS (Recommended)

1. Click the button above (or open **HACS** in Home Assistant)
2. Go to **HACS** → **Integrations**
3. Add this repository as a custom repository:
  - Open the menu (⋮) → **Custom repositories**
  - Repository: `https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink`
  - Category: **Integration**
4. Search for **Netlink** and install it
5. Restart Home Assistant

### Option 2 — Manual

1. Download the [latest release](https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink/releases)
2. Copy `custom_components/netlink` into your Home Assistant config directory:
  - `<config>/custom_components/netlink`
3. Restart Home Assistant

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

See [docs/faq.md](docs/faq.md) for common issues and troubleshooting steps.

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
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[maintenance]: https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink
[license-shield]: https://img.shields.io/github/license/MrGreenBoutiqueOffices/home-assistant-netlink.svg
[license]: LICENSE
