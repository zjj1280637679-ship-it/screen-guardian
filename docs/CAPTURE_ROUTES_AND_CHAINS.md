# Capture Routes And Chains

Screen Guardian now separates capture intent into routes. This keeps the main AI from treating every screenshot as the same action.

## Route Map

| Route | Best for | Quiet capture | Primary tools |
| --- | --- | --- | --- |
| `desktop` | Visible desktop pixels, multi-display fallback, old-system capture | No. It sees what is visible on the desktop. | `capture_screen`, `capture_region`, `watch_screen` |
| `application` | A specific Windows program, HWND, process, title, or bounded multi-window survey | Quiet-preferred by default. `background_mode="strict"` uses direct HWND graphics without visible-screen bbox fallback; best-effort mode can still return guarded fallback decisions. | `guardian_capture_targets`, `list_windows`, `capture_window`, `guardian_survey_windows` |
| `webpage` | Browser-rendered viewport, element, or full scrollable webpage | Yes, when optional `webpage_capture` is enabled. Default status is inactive. | `prepare_webpage_capture`, `capture_webpage` |
| `nested_scroll` | Admin tables, scrollable panels, and embedded iframes inside a page | Yes, through a headless browser route when `webpage_capture=true`. Default status is inactive. | `capture_webpage` with `mode="scroll_container"` |
| `sandbox` | Background real-machine UI experiments, popup-heavy validation, and hidden desktop app instances | Yes, by isolation through an explicit hidden-desktop caller. | `prepare_sandbox_session`, then `screen_organ.sandbox_launch`, `screen_organ.sandbox_list`, `screen_organ.capture_screen`, optional `capture_window`, cleanup, and `write_sandbox_ledger` |
| `mixed` or `auto` | A caller wants a route plan before choosing exact tools | Depends on selected steps. | `prepare_capture_chain` |

Use `guardian_capture_targets` when the AI needs concrete capturable targets before taking any screenshot. Use `list_capture_routes` when the AI is unsure which route family to choose.

## Desktop Versus Application Versus Webpage

Desktop capture is a pixel fallback. It is the right first route when compatibility is the problem and the user needs the currently visible screen. It is also the route for short visible change capture.

Application capture is a window route. It should start with `guardian_capture_targets` or `list_windows` when the target is ambiguous, then use `capture_window` with `hwnd` or exact match. It is quiet-preferred by default: Screen Guardian does not activate, focus, raise, or make the target topmost. For occlusion-resistant capture, use `background_mode="strict"` so the adapter attempts direct HWND graphics and disables visible-screen bbox fallback. If direct HWND graphics are unavailable or too low-information, the result returns `background_capture_unavailable` and no misleading fallback image is saved.

Best-effort window capture can still fall back to visible-screen bbox pixels for compatibility. If that happens, the plugin samples the topmost window identity inside the bbox before saving. If the sampled visible window does not match the requested HWND, it returns a decision warning even if the caller already set `render_guard_confirmed=true`.

For "report all program windows" tasks, use `guardian_survey_windows` instead of repeatedly calling `list_windows` and `capture_window`. It returns a structured status table first, then optionally saves a bounded set of local window captures using `capture_mode="hold_file"` or `capture_mode="return_paths"`. The AI can then inspect only the saved paths that matter.

Use `quiet_preferred=false` only when the user accepts visible-screen fallback behavior, such as bringing a target forward or capturing a known visible region. Quiet preference is a strategy default, not a guarantee that every application can be captured while hidden, minimized, protected, or GPU-rendered.

For one-shot application captures, `guardian_perceive` can stack pre-capture modes such as `delay`, `wait_render`, `wait_buffer`, and `wait_error`. These are bounded foreground conditions for one capture call, not a hidden background monitor.

Webpage capture is a browser-rendered route. It does not need the page to be in the desktop foreground. It navigates an explicit URL with an optional Playwright/Chromium adapter, then captures the viewport, full page, element, or nested scroll container. `list_capture_routes` reports `webpage.active=false` and `nested_scroll.active=false` until the persistent `webpage_capture` feature flag is enabled and optional Playwright dependencies are installed.

## Sandbox Route

The `sandbox` route is for real-machine validation that should not disturb the
user's foreground desktop. It is a hidden-desktop route, not a normal visible
desktop screenshot. The intended caller launches a target program in a hidden
desktop sandbox, lists the sandbox windows, captures bounded evidence from the
target HWND, and writes a compact ledger.

Screen Guardian does not launch sandbox programs by itself. It prepares the
session, context markers, hold-file capture settings, lifecycle contract, and
ledger template. A separate explicit caller, such as
`screen_organ.sandbox_launch` and `screen_organ.sandbox_list`, owns the hidden
desktop lifecycle.

Use `prepare_sandbox_session` when a real run is expected. It writes a
`sandbox_session_request` and a `screen-guardian-sandbox-ledger/v1` template.
The required phases are:

- `launch`: call the external hidden-desktop launcher with the prepared program,
  cwd, and args.
- `list`: collect sandbox HWND/title/rect records.
- `capture`: save bounded sandbox captures, preferably through
  `screen_organ.capture_screen` with `context="sandbox"` and
  `source="composite"`.
- `stop`: close or stop owned sandbox resources through an explicit external
  cleanup method.
- `ledger`: write pid/window/capture/cleanup/verdict fields before returning a
  compact summary to the main channel.

When `sandbox_list` returns a hidden-desktop HWND, pass that whole window record
to `capture_window` as `window_record` and set `desktop_context="sandbox"`.
This lets Screen Guardian treat the external sandbox caller as the window truth
source instead of rejecting the HWND because it is absent from the main desktop
enumerator. Sandbox context disables visible-screen bbox fallback; if direct
HWND capture cannot produce a trustworthy frame, record that as a blocked or
failed sandbox capture instead of capturing foreground desktop pixels.

Use `write_sandbox_ledger` after cleanup. It validates and writes a
`screen-guardian-sandbox-ledger/v1` record. A `pass` verdict must include
successful launch, at least one capture record, `stop_attempted=true`,
`stop_ok=true`, and no leftover owned processes.

If no cleanup adapter is available, the prepared session records
`external_caller_stop_required`; the caller still has to mark `stop_attempted`,
`stop_ok`, and any `leftover_processes` in the ledger.

Use this route when many real-machine checks would otherwise create popups,
focus stealing, or front-channel noise. Keep captures bounded and prefer
`context_policy="hold_file"` so the main AI channel receives paths and summary
metadata rather than every frame.

## Nested Scroll Containers

Some management pages do not put all data in the document scroll. They render a table or embedded app inside a scrollable `div` or `iframe`. A normal desktop screenshot only sees the current viewport, and a normal full-page screenshot may still miss rows hidden inside the inner scroll container.

Use:

```json
{
  "url": "https://example.com/admin",
  "mode": "scroll_container",
  "selector": ".table-scroll",
  "frame_selector": "iframe[name='embedded-app']",
  "context_policy": "hold_file",
  "marked_file_only": true
}
```

`frame_selector` is optional. When present, Screen Guardian enters that iframe before resolving `selector`.

The plugin scrolls the container vertically, captures bounded segments, stitches them into one image, and restores the original scroll position. Segment count and delay are controlled by `webpage_capture_scroll_segments_max` and `webpage_capture_segment_delay_ms_max`.

If the panel is too tall or needs too many segments, Screen Guardian returns a decision menu instead of silently creating an enormous file.

## Capture Chains

`prepare_capture_chain` writes a local plan for guided capture. It is useful when a screenshot is not a standalone action:

- wait a few seconds, then capture a slow-rendering window
- watch for a visible program change, then capture and preprocess text
- wait until a webpage selector appears, then capture a nested scroll table
- detect an error feature, then prepare a model request
- route a capture result to a decision policy or future subagent
- run a hidden desktop sandbox experiment and record only bounded evidence

Example:

```json
{
  "objective": "When the quota table appears, capture the full nested table and prepare a compact summary request.",
  "route": "nested_scroll",
  "trigger": {"type": "selector_visible", "selector": ".quota-table-scroll"},
  "steps": [
    {
      "tool": "capture_webpage",
      "args": {
        "url": "https://example.com/console",
        "mode": "scroll_container",
        "selector": ".quota-table-scroll",
        "context_policy": "hold_file",
        "marked_file_only": true
      }
    },
    {
      "tool": "prepare_model_request",
      "args": {"prompt": "Summarize the quota table for a user in plain language."}
    }
  ]
}
```

This is prepare-only. It does not execute screenshots, browser navigation, scripts, APIs, subagents, or background schedulers from the envelope. A caller can later consume the plan and run explicit tools under the same feature flags and runtime limits.

For `route="sandbox"`, this also means Screen Guardian does not launch or keep
the hidden desktop alive. Prefer `prepare_sandbox_session` for executable
session plans. If a generic capture chain is used instead, the caller must still
return a ledger with sandbox pid/window ids, capture paths, cleanup result, and
a short summary.

## Boundary

These routes are for authorized perception, accessibility, debugging, visibility auditing, and personal AI assistance. They are not designed or supported for bypassing authentication, paywalls, CAPTCHA, DRM, access controls, platform rules, privacy expectations, or unauthorized data access.
