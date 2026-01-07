# translations agent

Focus: strings, placeholders, and translation alignment.

## Key files
- `custom_components/netlink/strings.json` (source)
- `custom_components/netlink/translations/en.json`
- `custom_components/netlink/translations/nl.json`

## Rules
- Treat `strings.json` as the source of truth.
- Keep translation keys and placeholders aligned across all translation files.
- Placeholders:
  - descriptions: must have matching `description_placeholders={...}` in code.
  - menu titles (`async_show_menu()`): avoid placeholders; some HA builds do not support passing `title_placeholders` there.

## When editing text
- Preserve `{host}`, `{name}`, and other placeholders exactly.
- Prefer minimal copy changes; avoid rewording unrelated strings.
