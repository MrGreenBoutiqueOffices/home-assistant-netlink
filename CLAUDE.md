
# Claude notes (home-assistant-netlink)

You are working on a Home Assistant custom integration under `custom_components/netlink/`.

## Do
- Preserve the **push-based** architecture: coordinator does one REST refresh, then WebSocket events update state (no polling).
- Keep entities as `CoordinatorEntity`s reading from `NetlinkDataUpdateCoordinator`.
- Keep translations consistent:
	- edit `custom_components/netlink/strings.json` first
	- mirror changes into `custom_components/netlink/translations/*.json`.
- Prefer minimal, surgical changes; match existing Home Assistant patterns.

## Avoid
- Adding polling intervals or per-entity REST calls.
- Using placeholders in titles for `async_show_menu()` steps; put dynamic text in the description instead.

## Commands (CI parity)
- `uv sync --frozen --dev`
- `uv run ruff check .`
- `uv run ruff format --check .`

See `.github/copilot-instructions.md` and `AGENTS.md` for deeper repo context.
