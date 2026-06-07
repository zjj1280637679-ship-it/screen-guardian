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

## Safety defaults

- Captures are saved locally under `~/Pictures/ScreenGuardian` unless a specific output folder is provided.
- Do not start continuous capture or recording in this version.
- Do not upload screenshots automatically.
- Mention the saved file path when a capture succeeds.

## Tools

Prefer the `screen_guardian` MCP tools:

- `check_dependencies`
- `list_displays`
- `capture_screen`
- `capture_region`
- `clear_cache`

Use `capture_screen` with `max_width` or `scale` when the user only needs a quick visual summary.
