# Copilot instructions (home-assistant-netlink)

## Project overview
- Home Assistant custom integration: `custom_components/netlink/` (domain: `netlink`). See `manifest.json` (iot_class `local_push`, zeroconf `_netlink._tcp.local.`, requirement `pynetlink==1.0.2`).
- Architecture is **push-based**: initial REST fetch + WebSocket event updates (no polling). Core logic lives in `coordinator.py`.

## Runtime data flow (important)
- Entry setup: `custom_components/netlink/__init__.py` creates `NetlinkClient` + `NetlinkDataUpdateCoordinator` and stores it on `entry.runtime_data`.
- Coordinator:
  - `_async_update_data()` fetches initial state via REST (`get_device_info`, `get_desk_status`, `get_displays`, `get_display_status`).
  - `async_setup()` connects WebSocket and registers event handlers that call `async_set_updated_data(...)`.
- Entities are **CoordinatorEntities**; do not add your own polling. Use `coordinator.data["desk"]` and `coordinator.data["displays"][bus_id]` patterns.

## Entity conventions
- Base classes live in `custom_components/netlink/entity.py`:
  - `NetlinkMainEntity`, `NetlinkDeskEntity`, `NetlinkDisplayEntity` define device registry grouping + `suggested_area`.
- Platforms are split by HA platform file: `sensor.py`, `binary_sensor.py`, `number.py`, `switch.py`, `select.py`, `button.py` (see `PLATFORMS` in `const.py`).

## Config flow + discovery
- Config flow is in `custom_components/netlink/config_flow.py`:
  - Supports manual host + token, OAuth2 (`config_entry_oauth2_flow`), reauth, and Zeroconf discovery.
  - Unique ID is the Netlink `device_id`.
- Translation placeholders:
  - Put placeholders used in descriptions into `description_placeholders={...}`.
  - Avoid `{name}` placeholders in **menu step titles** shown via `async_show_menu()`; prefer a static title and show `{name}` in the description.

## Translations
- Source strings: `custom_components/netlink/strings.json`.
- Keep `custom_components/netlink/translations/*.json` aligned with `strings.json` keys/placeholders.

## Dev workflow (repo-specific)
- Python: `>=3.13` (see `pyproject.toml`). Dependency management uses **uv**.
- Lint/format (matches CI):
  - `uv sync --frozen --dev`
  - `uv run ruff check .`
  - `uv run ruff format --check .`
- Pre-commit hooks are uv-based (see `.pre-commit-config.yaml`): `pre-commit run -a`.
- CI validations: Hassfest (`.github/workflows/hassfest.yaml`), HACS (`.github/workflows/hacs.yaml`).

## Local Home Assistant setup
- For manual testing, symlink the integration into your HA config (see README): `custom_components/netlink` → `<config>/custom_components/netlink`, then restart HA.
- There are currently no repository tests under `tests/`.
