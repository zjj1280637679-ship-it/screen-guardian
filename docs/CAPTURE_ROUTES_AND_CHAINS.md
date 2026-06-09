# Capture Routes And Chains

Screen Guardian now separates capture intent into routes. This keeps the main AI from treating every screenshot as the same action.

## Route Map

| Route | Best for | Quiet capture | Primary tools |
| --- | --- | --- | --- |
| `desktop` | Visible desktop pixels, multi-display fallback, old-system capture | No. It sees what is visible on the desktop. | `capture_screen`, `capture_region`, `watch_screen` |
| `application` | A specific Windows program, HWND, process, title, or bounded multi-window survey | Quiet-preferred by default. It does not activate or raise the window, but minimized, protected, GPU-rendered, or occluded windows can still fail. | `list_windows`, `capture_window`, `guardian_survey_windows` |
| `webpage` | Browser-rendered viewport, element, or full scrollable webpage | Yes, when optional `webpage_capture` is enabled. Default status is inactive. | `prepare_webpage_capture`, `capture_webpage` |
| `nested_scroll` | Admin tables, scrollable panels, and embedded iframes inside a page | Yes, through a headless browser route when `webpage_capture=true`. Default status is inactive. | `capture_webpage` with `mode="scroll_container"` |
| `mixed` or `auto` | A caller wants a route plan before choosing exact tools | Depends on selected steps. | `prepare_capture_chain` |

Use `list_capture_routes` when the AI is unsure which route to choose.

## Desktop Versus Application Versus Webpage

Desktop capture is a pixel fallback. It is the right first route when compatibility is the problem and the user needs the currently visible screen. It is also the route for short visible change capture.

Application capture is a window route. It should start with `list_windows` when the target is ambiguous, then use `capture_window` with `hwnd` or exact match. It is quiet-preferred by default: Screen Guardian does not activate, focus, raise, or make the target topmost. If the HWND route has to fall back to a visible-screen bbox capture, the plugin samples the topmost window identity inside the bbox before saving. If the sampled visible window does not match the requested HWND, it returns a decision warning even if the caller already set `render_guard_confirmed=true`.

For "report all program windows" tasks, use `guardian_survey_windows` instead of repeatedly calling `list_windows` and `capture_window`. It returns a structured status table first, then optionally saves a bounded set of local window captures using `capture_mode="hold_file"` or `capture_mode="return_paths"`. The AI can then inspect only the saved paths that matter.

Use `quiet_preferred=false` only when the user accepts visible-screen fallback behavior, such as bringing a target forward or capturing a known visible region. Quiet preference is a strategy default, not a guarantee that every application can be captured while hidden, minimized, protected, or GPU-rendered.

Webpage capture is a browser-rendered route. It does not need the page to be in the desktop foreground. It navigates an explicit URL with an optional Playwright/Chromium adapter, then captures the viewport, full page, element, or nested scroll container. `list_capture_routes` reports `webpage.active=false` and `nested_scroll.active=false` until the persistent `webpage_capture` feature flag is enabled and optional Playwright dependencies are installed.

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

## Boundary

These routes are for authorized perception, accessibility, debugging, visibility auditing, and personal AI assistance. They are not designed or supported for bypassing authentication, paywalls, CAPTCHA, DRM, access controls, platform rules, privacy expectations, or unauthorized data access.
