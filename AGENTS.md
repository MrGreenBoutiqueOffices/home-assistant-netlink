
# Agent notes (home-assistant-netlink)

This repo is a Home Assistant custom integration: `custom_components/netlink/` (domain `netlink`).

## Architecture (what matters most)
- **Push-based state**: initial REST fetch + WebSocket events. Do **not** add polling.
- Core state management lives in `custom_components/netlink/coordinator.py` (`NetlinkDataUpdateCoordinator`).
- Entry setup is in `custom_components/netlink/__init__.py`:
	- creates `NetlinkClient` and the coordinator
	- stores coordinator on `entry.runtime_data`
	- forwards setup to platforms listed in `custom_components/netlink/const.py`.

## Entity patterns
- Entities are `CoordinatorEntity`s and must read from coordinator data:
	- desk: `coordinator.data["desk"]`
	- displays: `coordinator.data["displays"][bus_id]`
- Device grouping is handled by base classes in `custom_components/netlink/entity.py`:
	- `NetlinkMainEntity`, `NetlinkDeskEntity`, `NetlinkDisplayEntity`
	- `suggested_area` is derived from the device name.

## Config flow + translations (common footgun)
- Config flow is in `custom_components/netlink/config_flow.py` (manual host+token, OAuth2, reauth, Zeroconf).
- Translation source is `custom_components/netlink/strings.json`; shipped translations in `custom_components/netlink/translations/*.json`.
- When adding placeholders:
	- pass placeholders used in **descriptions** via `description_placeholders={...}`
	- avoid `{name}` (or other placeholders) in **menu step titles** rendered by `async_show_menu()`; use a static title and put the dynamic bits in the description.

## Dev workflow (what CI enforces)
- Python `>=3.13` (see `pyproject.toml`). Dependency manager: **uv**.
- Lint/format (matches CI):
	- `uv sync --frozen --dev`
	- `uv run ruff check .`
	- `uv run ruff format --check .`
- Pre-commit is uv-based (see `.pre-commit-config.yaml`): `pre-commit run -a`.
- CI validations to keep green:
	- Ruff (`.github/workflows/linting.yaml`)
	- Hassfest (`.github/workflows/hassfest.yaml`)
	- HACS (`.github/workflows/hacs.yaml`)

## Where to look first
- Protocol/client behavior: external dependency `pynetlink==1.0.2` (see `custom_components/netlink/manifest.json`).
- Diagnostics: `custom_components/netlink/diagnostics.py`.

If you need a shorter version, also see `.github/copilot-instructions.md`.
