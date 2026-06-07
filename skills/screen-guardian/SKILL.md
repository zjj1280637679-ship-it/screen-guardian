---
name: screen-guardian
description: Use Screen Guardian when the user wants Codex to inspect, capture, or diagnose the local Windows screen through lightweight local screenshots, especially when Computer Use screenshots are unavailable or incompatible.
---

# Screen Guardian

Screen Guardian is a local-only screenshot helper for Codex.

## When to use

Use this skill when the user asks to:

- capture the current screen
- list monitors or display coordinates
- capture a screen region
- downscale a screenshot for lower context pressure
- diagnose whether local screenshot dependencies work
- inspect compatibility adapters before choosing a capture backend
- read or set the local display-name profile

## Safety defaults

- Captures are saved locally under `~/Pictures/ScreenGuardian` unless a specific output folder is provided.
- Do not start continuous capture or recording in this version.
- Do not upload screenshots automatically.
- Mention the saved file path when a capture succeeds.

## Tools

Prefer the `screen_guardian` MCP tools:

- `check_dependencies`
- `get_display_profile`
- `set_display_name`
- `apply_display_profile`
- `list_adapters`
- `list_displays`
- `capture_screen`
- `capture_region`
- `clear_cache`

Use `list_adapters` when diagnosing compatibility. Use `get_display_profile` before renaming. Use `apply_display_profile` only when the user wants the active name written into the local plugin manifest and understands the plugin must be reloaded. Use `capture_screen` with `max_width` or `scale` when the user only needs a quick visual summary.
