# entities agent

Focus: entity model + platform files for Netlink.

## Key files
- `custom_components/netlink/entity.py` (base entity classes + device grouping)
- `custom_components/netlink/const.py` (`PLATFORMS`)
- Platform modules: `sensor.py`, `binary_sensor.py`, `number.py`, `switch.py`, `select.py`, `button.py`

## Non-negotiables
- Do **not** add polling. Entities must remain `CoordinatorEntity`s backed by the coordinator.
- Read state from coordinator data:
  - desk: `coordinator.data["desk"]`
  - displays: `coordinator.data["displays"][bus_id]`

## Conventions
- Use `NetlinkMainEntity` / `NetlinkDeskEntity` / `NetlinkDisplayEntity` for correct device registry grouping.
- Keep display entities keyed by `bus_id` as a string.
