# Unopened App Page

## User Situation

The user wants the AI to inspect an application page that is not currently opened, expanded, or visible, such as an accelerator/VPN client window that is running in the background but its useful page is minimized, offscreen, hidden in tray, or not rendered.

## External Conditions

- The process may be running while the page UI is minimized or offscreen.
- The visible window title may be localized, for example Chinese application names.
- Direct HWND capture can fail before pixels are returned.
- Visible-screen fallback can capture the wrong window when the target is minimized or covered.
- The AI must not click connect/disconnect, close the app, or bring the VPN UI forward unless the user explicitly asks.

## Recommended Route

Start with `guardian_capture_targets` or `guardian_sniff_context`.

Prefer stable selectors in this order:

1. `hwnd` from a target index.
2. `process_name` when the app title is localized or unstable.
3. `exact_title` or `title_contains` when the caller can send UTF-8 or JSON escaped Unicode reliably.

For Windows PowerShell CLI tests, use JSON escaped Unicode such as `"\u53d8\u8272\u9f99"` if direct non-ASCII stdin is not reliable. MCP calls from the server use UTF-8 JSON and do not need this CLI workaround.

## Guard Strategy

- Recommended target-index capture args should include `minimized_window`, `offscreen_window`, and `tiny_capture` in addition to render/background checks.
- If the target is minimized or offscreen, return a pre-capture decision before any grab attempt.
- If direct HWND capture fails in strict mode, return `background_capture_unavailable` with `saved=false`.
- Only use visible-screen fallback after the user accepts visible desktop pixels.
- Keep `foreground_activation_performed=false` unless the user explicitly asks to bring the app forward.

## Context Budget

Use status-only target indexing first. Save screenshots only after the target is expanded or after the user accepts a visible fallback route.

## Risks And Fallback Paths

- Localized title filters can fail in CLI tests if stdin encoding is lossy.
- A minimized window often reports coordinates around `-32000`.
- A WebView or custom-drawn window can expose no direct HWND pixels.
- Visible bbox fallback can capture another topmost window.

Fallbacks:

- Retry with `process_name`.
- Retry with JSON escaped Unicode title filters.
- Ask the user to open or restore the page.
- Use a semantic/browser/API route when the app exposes a safer authorized route.

## Acceptance Checks

- Target indexing reports whether the app window is minimized or offscreen.
- Strict capture of a minimized/offscreen app returns `ok=true`, `saved=false`, and `result_state="decision_required"`.
- Direct HWND failure returns `background_capture_unavailable`, not a raw `screen grab failed` error.
- No click, close, connect/disconnect, or foreground activation is performed.
- Visible fallback is clearly labeled as visible pixels and is not treated as strict background capture.

## Related Whitepaper Claims

- Desktop situation index
- Quiet window capture
- Render guard decision
- Screen content is untrusted
- Review decomposition
