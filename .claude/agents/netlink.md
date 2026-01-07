# netlink (Home Assistant integration agent)

You are helping maintain the Home Assistant custom integration in `custom_components/netlink/`.

## Key constraints
- **Push only**: initial REST fetch + WebSocket updates. Do not introduce polling.
- Entities are `CoordinatorEntity`s backed by `NetlinkDataUpdateCoordinator`.

## Where state comes from
- `custom_components/netlink/__init__.py`: creates `NetlinkClient` + coordinator; stores coordinator on `entry.runtime_data`.
- `custom_components/netlink/coordinator.py`:
  - `_async_update_data()` does initial REST fetch.
  - `async_setup()` connects WebSocket and updates via `async_set_updated_data(...)`.

## Conventions
- Use base entity classes in `custom_components/netlink/entity.py` for device grouping (`NetlinkMainEntity`, `NetlinkDeskEntity`, `NetlinkDisplayEntity`).
- Platforms are split by HA platform file; see `custom_components/netlink/const.py` (`PLATFORMS`).

## Config flow + translations
- Flow: `custom_components/netlink/config_flow.py` (manual token, OAuth2, reauth, zeroconf).
- Strings source: `custom_components/netlink/strings.json`.
- Keep `custom_components/netlink/translations/*.json` aligned.
- Placeholder rule: avoid placeholders in `async_show_menu()` titles; use descriptions with `description_placeholders`.

## Dev commands
- `uv sync --frozen --dev`
- `uv run ruff check .`
- `uv run ruff format --check .`
