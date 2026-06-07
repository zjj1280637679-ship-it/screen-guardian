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
- configure the local cache path
- list or capture a specific program window
- run a short bounded change-triggered watch
- tag captures with project/workflow metadata
- analyze or preprocess a local image before deciding how much context to spend
- change or remove runtime limits when the user explicitly wants different bounds
- save captures to multiple local routes
- register model/program routes or prepare narration/transcription request files
- enable or disable optional feature modules so inactive features do not slow active capture

## Safety defaults

- Captures are saved locally under `~/Pictures/ScreenGuardian` unless a specific output folder is provided.
- Only start bounded watch capture when the user asks for it; keep duration and capture-count limits small.
- Do not upload screenshots automatically.
- Mention the saved file path when a capture succeeds.
- Use `marked_file_only` or `context_policy="hold_file"` when the user wants files tagged for later analysis instead of immediately read into context.
- Treat registered extension routes as configuration only unless a future adapter explicitly handles execution.
- Ordinary captures should avoid image analysis unless the user asks for it, passes `analyze: true`, or uses `preprocess: auto`.

## Tools

Prefer the `screen_guardian` MCP tools:

- `check_dependencies`
- `get_runtime_settings`
- `set_cache_path`
- `set_storage_routes`
- `set_runtime_limits`
- `set_feature_flags`
- `list_extension_routes`
- `set_extension_route`
- `prepare_model_request`
- `get_display_profile`
- `set_display_name`
- `apply_display_profile`
- `list_adapters`
- `list_displays`
- `list_windows`
- `capture_screen`
- `capture_region`
- `capture_window`
- `watch_screen`
- `analyze_image`
- `preprocess_image`
- `clear_cache`

Use `list_adapters` when diagnosing compatibility. Use `get_display_profile` before renaming. Use `apply_display_profile` only when the user wants the active name written into the local plugin manifest and understands the plugin must be reloaded. Use `capture_screen` with `max_width` or `scale` for fast visual capture; add `analyze: true` only when image classification is useful. Use `watch_screen` only as a short foreground task, not as a background monitor.
