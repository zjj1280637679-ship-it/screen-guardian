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
- survey many program windows and optionally save bounded hold-file captures for selective review
- run a short bounded change-triggered watch
- tag captures with project/workflow metadata
- analyze or preprocess a local image before deciding how much context to spend
- change or remove runtime limits when the user explicitly wants different bounds
- save captures to multiple local routes
- register model/program routes or prepare narration/transcription request files
- register arbitrary-complexity decision policies or prepare decision request files
- register project monitor profiles or prepare one monitor tick for a caller/scheduler/subagent
- enable or disable optional feature modules so inactive features do not slow active capture
- check optional audio capture support, record short WAV clips, analyze WAV files, or extract video audio tracks
- choose between desktop, application/window, webpage, nested scroll-container, and mixed capture routes
- prepare guided capture chains for delayed, conditional, quiet, or multi-step screenshot workflows

## Safety defaults

- Captures are saved locally under `~/Pictures/ScreenGuardian` unless a specific output folder is provided.
- Only start bounded watch capture when the user asks for it; keep duration and capture-count limits small.
- Do not upload screenshots automatically.
- Mention the saved file path when a capture succeeds.
- Use `marked_file_only` or `context_policy="hold_file"` when the user wants files tagged for later analysis instead of immediately read into context.
- Treat registered extension routes as configuration only unless a future adapter explicitly handles execution.
- Treat decision policies as configuration/envelope preparation only. Do not execute function routes, APIs, local commands, or subagents unless a future adapter or caller explicitly handles execution.
- Treat monitor profiles as declarative project/workflow plans. Setting a monitor profile does not start monitoring; do not start background monitoring unless the user clearly asks for an explicit scheduler or bounded foreground watch.
- Ordinary captures should avoid image analysis unless the user asks for it, passes `analyze: true`, or uses `preprocess: auto`.
- Do not record audio unless the user asks for it. Prefer listing audio adapter/device status first.

## AI-First Default

Prefer the AI-first facade tools before the expert tool surface:

- Use `guardian_check` when plugin health, runtime, adapters, cache path, or active capability flags are uncertain.
- Use `guardian_perceive` for ordinary visual tasks: quick look, text-heavy screenshot, UI debugging, window capture, short bounded change watch, or hold-file context control.
- Use `guardian_survey_windows` when the user asks for all program-window status or wants a bounded batch of quiet window captures. Start with `capture_mode="status_only"`; use `capture_mode="hold_file"` when screenshots should be saved for later selective review.
- `guardian_perceive` defaults to fast direct capture. Use stackable `capture_modes` only when a non-default strategy is needed: `delay`, `wait_render`, `wait_buffer`, and `wait_error`.
- Use `delay_seconds` for delayed screenshots, `capture_modes=["wait_render"]` for slow-rendering windows, `capture_modes=["wait_buffer"]` for buffering or visual stability, `capture_modes=["wait_error"]` for explicit error-window signals, `render_guard="warn"` when suspected-unrendered frames should return decision actions before saving, and `task="watch_change"` for screen transitions or popups.
- Prefer quiet window capture by default. Do not activate, focus, raise, or make a target window topmost unless the user asks for that visible fallback path. If `capture_window` returns an occlusion, bbox identity, or bbox-fallback decision warning, ask the user or choose a documented action instead of silently saving. Use `allow_unverified_bbox_fallback=true` only as a last resort when the user accepts that visible pixels may belong to another window.
- Use `guardian_prepare_workflow` when preparing a local model, decision, or monitor envelope without executing that route.
- Use `guardian_list_commands` and `guardian_run_command` when the main AI should choose from reusable capability commands instead of composing low-level tools.
- Use `list_capture_routes` when the task could be desktop visible pixels, an application window, a browser-rendered webpage, an inner scrollable table, or a mixed capture plan.
- Use `prepare_capture_chain` when the user wants a trigger, delay, condition, preprocessing step, model request, or subagent/caller handoff around capture. This prepares a local envelope only.
- Treat `guardian_prepare_exec` and `guardian_run_exec` as break-glass local execution tools. Do not use `guardian_run_exec` unless the user explicitly asks for local code execution; it requires persistent `raw_local_exec=true` and per-call `user_confirmed=true`.
- Use low-level tools directly only when the user asks for exact adapter control, storage routing, runtime limits, feature flags, audio diagnostics, route registration, or monitor/decision registration.

## Tool Layers

Prefer the `screen_guardian` MCP tools. Start with the AI-first facade layer for ordinary help, then add core, local control, or experimental envelopes only when the user asks for those workflows.

The default MCP surface is core-sized. Advanced workflow, media, policy, monitor, and lab execution tools are hidden unless the MCP server starts with `SCREEN_GUARDIAN_TOOL_SURFACE=advanced` or `SCREEN_GUARDIAN_TOOL_SURFACE=full`.

AI-first tools:

- `guardian_check`
- `guardian_perceive`
- `guardian_survey_windows`
- `guardian_prepare_workflow`
- `guardian_list_commands`
- `guardian_run_command`
- `guardian_prepare_exec`
- `guardian_run_exec`
- `list_capture_routes`

Core tools:

- `check_dependencies`
- `list_adapters`
- `list_displays`
- `list_windows`
- `guardian_survey_windows`
- `list_capture_routes`
- `capture_screen`
- `capture_region`
- `capture_window`
- `watch_screen`
- `clear_cache`

Local control tools:

- `get_runtime_settings`
- `set_cache_path`
- `set_storage_routes`
- `set_runtime_limits`
- `set_feature_flags`
- `get_display_profile`
- `set_display_name`
- `apply_display_profile`
- `list_audio_devices`
- `record_audio`
- `analyze_audio`
- `extract_audio_track`
- `analyze_image`
- `preprocess_image`

Experimental envelope tools:

- `list_extension_routes`
- `set_extension_route`
- `prepare_model_request`
- `list_decision_policies`
- `set_decision_policy`
- `prepare_decision_request`
- `list_monitor_profiles`
- `set_monitor_profile`
- `prepare_monitor_tick`
- `prepare_capture_chain`

Use `list_adapters` when diagnosing compatibility. Use `get_display_profile` before renaming. Use `apply_display_profile` only when the user wants the active name written into the local plugin manifest and understands the plugin must be reloaded. Use `capture_screen` with `max_width` or `scale` for fast visual capture; add `analyze: true` only when image classification is useful. Treat `task="read_text"` as text-oriented image preprocessing, not OCR text extraction. Use desktop capture for visible pixels, application capture for HWND/process/title targets, webpage capture for browser-rendered full-page/viewport/element capture only when `webpage_capture=true`, and `mode="scroll_container"` for inner tables, panels, or iframes. Application/window capture is quiet-preferred by default and should not raise the target; set `quiet_preferred=false` only when visible-screen fallback is accepted, and still prefer HWND/exact title when bbox identity cannot be verified. Use `capture_modes` in `guardian_perceive` for stacked timing strategy while keeping omitted modes as fast direct capture. Use `guardian_survey_windows` for multi-window status reports and bounded batch evidence; keep `capture_mode="status_only"` unless the user asks for screenshots. Use `set_decision_policy` when the user wants best-action logic that can become more complex than weights or increments. Use `set_monitor_profile` and `prepare_monitor_tick` for project monitoring contracts such as webpage changes, program/window changes, model-detected features, error triggers, and audio/video events. Use `prepare_capture_chain` for guided plans; it does not execute screenshots, browser navigation, scripts, APIs, subagents, or background schedulers. Use `watch_screen` only as a short foreground task, not as a background monitor.
