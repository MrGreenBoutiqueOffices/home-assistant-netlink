# config_flow agent

Focus: Home Assistant config flow and discovery for the Netlink integration.

## Key files
- `custom_components/netlink/config_flow.py`
- `custom_components/netlink/strings.json`
- `custom_components/netlink/translations/en.json`
- `custom_components/netlink/translations/nl.json`

## Rules of engagement
- Keep the existing flow structure: manual host+token, OAuth2, reauth, and Zeroconf.
- Unique ID must remain the Netlink `device_id`.
- When changing any copy:
  - edit `strings.json` first, then mirror to translations.
  - placeholders used in descriptions must be passed via `description_placeholders`.
  - avoid placeholders in **menu step titles** shown via `async_show_menu()`; put dynamic `{name}` in the description instead.

## Typical changes
- Adjust discovery UX text (titles/descriptions) without breaking placeholders.
- Fix reauth edge cases while keeping OAuth implementation registration logic intact.
