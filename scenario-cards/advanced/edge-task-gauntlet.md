# Edge Task Gauntlet

## User Situation

The user wants to stress Screen Guardian with hard desktop perception tasks before relying on it for real AI work. The focus is not happy-path screenshots; it is whether the plugin honestly separates background graphics acquisition, visible desktop pixels, webpage capture, and decision states.

## External Conditions

- Multiple overlapping windows are open.
- At least one target window is partially or fully occluded.
- At least one target is minimized or offscreen.
- Browser pages may be GPU-rendered or unavailable to direct HWND capture.
- Optional webpage capture may be disabled.

## Recommended Route

Start with `guardian_capture_targets` so the AI receives a target index before any screenshot is taken.

Then choose:

- `capture_window` with `background_mode="strict"` for occlusion-resistant HWND capture.
- `capture_window` with `background_mode="visible_fallback"` only when visible desktop pixels are acceptable.
- `capture_webpage` when an explicit URL is available and page content matters more than browser chrome.
- `guardian_survey_windows` with `capture_mode="hold_file"` for bounded multi-window evidence.

## Guard Strategy

- Use `guard_checks=["unrendered","window_client_low_information","background_capture_unavailable"]` for strict background capture.
- Use `guard_checks=["unrendered","occlusion_risk","bbox_identity_mismatch"]` for visible fallback paths.
- Treat `ok=true, saved=false` as a handled decision state.
- Never treat a visible bbox fallback as proof of background capture.

## Context Budget

Use `context_budget="low"` or `hold_file` for surveys. Use `max_width` for individual verification captures.

## Risks And Fallback Paths

- Some GPU/protected/minimized windows may not expose reliable direct HWND pixels.
- A visible bbox fallback can save the wrong application if another window overlaps.
- Browser window capture is not the same as full-page webpage capture.
- Optional webpage capture can be inactive by feature flag.

Fallbacks:

- Retry strict capture with render wait.
- Switch to webpage capture with an explicit URL.
- Ask the user to accept visible fallback before using `background_mode="visible_fallback"`.
- Return a decision instead of saving a misleading file.

## Acceptance Checks

- `guardian_capture_targets` returns `capture_performed=false`.
- Strict capture metadata has `foreground_activation_performed=false`.
- Strict capture metadata has `visible_screen_fallback_used=false`.
- Visible fallback paths expose `occlusion_risk` or `bbox_identity_mismatch` when applicable.
- Ambiguous title/process matches return candidates and require HWND/exact targeting.
- Runtime limits cannot be loosened per call.
- Invalid inputs return structured errors without crashing the MCP server.

## Related Whitepaper Claims

- Desktop situation index
- Quiet window capture
- Render guard decision
- Screen content is untrusted
- Hold-file context
