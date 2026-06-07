# Naming Profile

Screen Guardian supports a local naming profile so the user can choose whether the project name follows the system language or uses a manual alias.

## Modes

| Mode | Behavior | Storage |
| --- | --- | --- |
| `auto` | Chooses a localized display name from the detected system language. | Local config stores the mode only. |
| `manual` | Uses a user-provided local display name and optional short description. | Local config stores the alias. |

The local config file is stored outside the repository:

```text
%APPDATA%/ScreenGuardian/config.json
```

## Supported Localized Names

| Locale | Display name |
| --- | --- |
| `en` | Screen Guardian |
| `zh`, `zh-cn` | 屏幕守护者 |
| `zh-tw` | 螢幕守護者 |
| `ja` | スクリーンガーディアン |
| `ko` | 스크린 가디언 |

Unsupported locales fall back to English.

## MCP Tools

- `get_display_profile` returns the detected system language, active name, local config path, and current plugin-manifest name.
- `set_display_name` switches between `auto` and `manual` mode.
- `apply_display_profile` writes the active name into `.codex-plugin/plugin.json`.

## Codex Manifest Boundary

Codex plugin cards read display metadata from `.codex-plugin/plugin.json`. This means:

- changing the local naming profile does not instantly rename the Codex plugin card
- `apply_display_profile` can update the local manifest
- Codex must reload or reinstall the plugin before the UI shows the manifest-applied name

This separation is intentional. It lets users keep personal aliases locally without pushing those aliases to the public repository.
