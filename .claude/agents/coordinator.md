# coordinator agent

Focus: `NetlinkDataUpdateCoordinator` and runtime state flow.

## Key files
- `custom_components/netlink/coordinator.py`
- `custom_components/netlink/__init__.py`

## Architecture constraints
- **Push-based** integration:
  - `_async_update_data()` is for the initial REST snapshot during setup.
  - WebSocket events update state via `async_set_updated_data(...)`.
- `update_interval` must remain `None` (no polling).

## Data model expectations
- `coordinator.data` is a dict with:
  - `"desk"`: desk state object
  - `"displays"`: dict mapping `bus_id` (string) -> display state object
- Be careful to merge existing state when handling events; do not drop keys.
