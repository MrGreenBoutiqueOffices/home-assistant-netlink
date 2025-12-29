# Netlink Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/MrGreenBoutiqueOffices/home-assistant-netlink.svg)](https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink/releases)
[![License](https://img.shields.io/github/license/MrGreenBoutiqueOffices/home-assistant-netlink.svg)](LICENSE)

Native Home Assistant integration for Netlink smart desk and monitor control systems.

## About

Netlink is the operating software for smart standing desks, developed by [NetOS](https://net-os.com/). The system powers smart desks in commercial office environments, most notably at [Mr.Green Offices](https://mrgreenoffices.nl/) locations throughout the Netherlands.

## Features

- 🔌 **WebSocket real-time updates** - Instant state changes via push notifications
- 🔍 **Automatic discovery** - Devices found via mDNS/Zeroconf
- 🪑 **Desk control** - Height adjustment, calibration, and status monitoring
- 🖥️ **Display control** - Power, brightness, volume, and input source
- 🌐 **Browser control** - Refresh capabilities
- 📊 **Rich entities** - Binary sensors, sensors, numbers, switches, selects, and buttons
- 🏠 **Native HA integration** - Config flow, device registry, and proper entity organization
- 🎨 **Icons** - Entity icons defined via `icons.json`

## Requirements

- Home Assistant >= 2025.12.0
- Netlink device with REST API and WebSocket support
- Bearer token for authentication

## Installation

### Manual Installation

1. Copy the `custom_components/netlink` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Netlink"
5. Follow the configuration steps

## Configuration

### Automatic Discovery

The integration will automatically discover Netlink devices on your network via mDNS:

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Select "Netlink" from the list
4. Select your device from the discovered devices
5. Enter the bearer token when prompted
6. Click "Submit"

### Manual Setup

If automatic discovery doesn't work:

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Select "Netlink"
4. Choose "Manual Setup"
5. Enter the device IP/hostname
6. Enter the bearer token
7. Click "Submit"

## Entities

The integration creates the following entities per Netlink device:

## Devices Created

When you add a Netlink device, the integration registers:

- **Main device**: `{device_name}`
  - Manufacturer: NetOS
  - Model: Device model
  - Contains browser control entities
- **Desk device**: `{device_name} (Desk)`
  - Manufacturer: NetOS
  - Model: Desk Controller
  - Contains desk entities
- **Display device(s)**: `{device_name} (Display {bus_id})` per display bus
  - Manufacturer: NetOS
  - Model: Detected display model (fallback: "Display")
  - Contains display entities (power, brightness, volume, source, error)

### Desk Entities

- **Binary Sensors**:
  - `binary_sensor.{device_name}_desk_moving` - Desk movement status

- **Sensors**:
  - `sensor.{device_name}_desk_height` - Current desk height (cm)
  - `sensor.{device_name}_desk_mode` - Operation mode
  - `sensor.{device_name}_desk_error` - Error messages (if any)

- **Controls**:
  - `number.{device_name}_desk_target_height` - Set target height (62-127 cm)
  - `switch.{device_name}_desk_beep` - Beep setting (on/off)

- **Buttons**:
  - `button.{device_name}_desk_stop` - Stop movement
  - `button.{device_name}_desk_reset` - Reset desk
  - `button.{device_name}_desk_calibrate` - Calibrate desk (disabled by default)

### Display Entities (per display)

- **Sensors**:
  - `sensor.{device_name}_display_{bus_id}_brightness` - Current brightness (%)
  - `sensor.{device_name}_display_{bus_id}_volume` - Current volume (%)
  - `sensor.{device_name}_display_{bus_id}_power` - Power state
  - `sensor.{device_name}_display_{bus_id}_source` - Current input source
  - `sensor.{device_name}_display_{bus_id}_error` - Error messages (if any)

- **Controls**:
  - `switch.{device_name}_display_{bus_id}_power` - Power on/off
  - `number.{device_name}_display_{bus_id}_brightness` - Set brightness (0-100%, if supported)
  - `number.{device_name}_display_{bus_id}_volume` - Set volume (0-100%, if supported)
  - `select.{device_name}_display_{bus_id}_source` - Input source selection (if supported)

  
### Browser Entities

- **Buttons**:
  - `button.{device_name}_browser_refresh` - Refresh browser

## Services Used

This integration does not register custom Home Assistant services. It uses the
standard entity services below:

- `number.set_value` for desk height, display brightness, and volume
- `switch.turn_on` / `switch.turn_off` for desk beep and display power
- `select.select_option` for display input source
- `button.press` for desk and browser actions

## Migration from MQTT

This integration is designed to be compatible with the MQTT-based setup:

- **Device IDs** are identical to MQTT setup for smooth migration
- **Entity naming** follows the same pattern
- **Both can coexist** - MQTT and native integration can run simultaneously

To migrate:

1. Install the native integration (keep MQTT running)
2. Verify all entities work correctly
3. Disable MQTT discovery for Netlink devices (optional)
4. Remove old MQTT automations/scripts if needed

## Troubleshooting

### Device not discovered

- Ensure mDNS/Zeroconf is working on your network
- Try manual setup instead
- Check firewall rules (port 80 for REST, WebSocket)

### Connection errors

- Verify the bearer token is correct
- Check device is reachable: `ping <device_ip>`
- Review Home Assistant logs: Settings → System → Logs

### Entities unavailable

- Check WebSocket connection status in logs
- Device will auto-reconnect with exponential backoff
- Entities show "unavailable" during connection loss

## Development

Built on top of [`pynetlink`](https://github.com/MrGreenBoutiqueOffices/python-netlink) - the production-ready Python client library for Netlink devices.

### Local Development

```bash
# Clone repository
git clone https://github.com/MrGreenBoutiqueOffices/home-assistant-netlink.git
cd home-assistant-netlink

# Link to HA config directory
ln -s $(pwd)/custom_components/netlink ~/.homeassistant/custom_components/

# Restart Home Assistant
```

## Contributing

This is an active open-source project. We are always open to people who want to
use the code or contribute to it.

We've set up a separate document for our
[contribution guidelines](CONTRIBUTING.md).

Thank you for being involved! :heart_eyes:

## License

This project is licensed under the LGPL-3.0-or-later License - see the [LICENSE](LICENSE) file for details.

## Credits

Developed by [Klaas Schoute](https://github.com/klaasnicolaas) for [Mr. Green Boutique Offices](https://mrgreenoffices.nl/).

Built with ❤️ using the [`pynetlink`](https://pypi.org/project/pynetlink/) library.
