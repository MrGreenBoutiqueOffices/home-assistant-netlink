# diagnostics agent

Focus: troubleshooting + diagnostics export.

## Key files
- `custom_components/netlink/diagnostics.py`
- `custom_components/netlink/__init__.py` (what runtime data is available)

## Goals
- Ensure diagnostics do not include secrets (tokens), and only include necessary device/state info.
- Keep diagnostics output stable and HA-friendly.

## Notes
- Client behavior comes from `pynetlink==1.0.2` (see `custom_components/netlink/manifest.json`).
