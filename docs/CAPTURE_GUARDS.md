# Capture Guards

Capture guards are lightweight quality checks that run before a capture is saved. They are not permission blockers. They are decision helpers for cases where the screenshot may be incomplete, stale, tiny, hidden, or otherwise misleading.

The ordinary screenshot default guard is intentionally small:

```json
{
  "guard_checks": ["unrendered"]
}
```

Most other checks are opt-in. Window bbox fallback is the exception: `occlusion_risk` and `bbox_identity_mismatch` can be attached automatically because visible-screen fallback can save the wrong pixels when another window overlaps the target. This keeps ordinary screenshots fast while making fragile window fallback honest.

## Guard Checks

| Check | Default | Detects | Typical cause | Decision menu |
| --- | --- | --- | --- | --- |
| `unrendered` | On | Blank, solid, black, white, or very low-information final frame | Slow rendering, loading screen, GPU/protected overlay, blank fallback | Force capture now, capture later, auto-detect render then capture |
| `minimized_window` | Off | Target window is minimized | HWND/window capture cannot see useful pixels while minimized | Restore window then capture, force capture now |
| `offscreen_window` | Off | Window is partly or fully outside the virtual desktop | Multi-monitor movement, disconnected display, bad window coordinates | Move window visible then capture, reselect target |
| `tiny_capture` | Off | Capture box width or height is below `guard_tiny_min_pixels` | Bad region coordinates, wrong display, overly small UI target | Reselect region/window, force capture now |
| `stale_frame` | Off | Retry attempts return the same sampled frame | Frozen app, stale capture backend, no visible change during retry | Refresh or wait for change, force capture now |
| `occlusion_risk` | On for quiet-preferred window capture; otherwise off | Window capture used a bbox fallback that may include another window | GPU/protected window fallback, non-topmost window, overlap | Retry quiet capture, allow visible fallback, bring window forward, or capture visible screen/region |
| `bbox_identity_mismatch` | On for any window bbox fallback | Sampled visible pixels appear to belong to another topmost window | Overlapping UWP/ApplicationFrameHost windows, same-size windows, Store/Settings style fallback collision | Retry with HWND/exact title, bring target forward, or explicitly allow unverified bbox fallback |

## Decision Payload

When a guard triggers and `render_guard` is `warn` or `wait`, Screen Guardian defers saving and returns a decision menu:

```json
{
  "ok": true,
  "reason": "capture_guard_decision",
  "capture_deferred": true,
  "requires_decision": true,
  "issue_ids": ["unrendered"],
  "available_actions": {
    "force_capture_now": {"render_guard_confirmed": true},
    "capture_later": {"delay_seconds": 1, "render_guard": "warn"},
    "auto_detect_render_then_capture": {
      "wait_for_nonblank": true,
      "render_guard": "wait"
    }
  }
}
```

This is deliberately not a refusal. The caller can force the capture, wait a fixed delay, auto-wait until the frame appears rendered, or adjust the target.

## Modes

| Mode | Behavior |
| --- | --- |
| `render_guard="save"` | Save even when guard checks detect issues; include guard metadata in the result |
| `render_guard="warn"` | Do not save yet; return decision actions |
| `render_guard="wait"` | Retry until nonblank within runtime limits; if still incomplete, return decision actions |
| `render_guard="fail"` | Strict automation mode; return `ok=false` instead of decision actions |

## Examples

Default behavior, only unrendered detection:

```json
{
  "task": "capture_window",
  "render_guard": "warn"
}
```

Enable all guard checks for a fragile window capture:

```json
{
  "task": "capture_window",
  "render_guard": "warn",
  "guard_checks": ["all"]
}
```

Disable quiet preference only when visible-screen fallback is acceptable:

```json
{
  "task": "capture_window",
  "target": {"title_contains": "Chrome"},
  "quiet_preferred": false,
  "render_guard_confirmed": true
}
```

If the bbox identity probe sees another topmost window at the sampled points, `render_guard_confirmed=true` alone does not save the image. This prevents cases where a requested Store window silently saves a same-sized Settings window. The explicit last-resort override is:

```json
{
  "task": "capture_window",
  "quiet_preferred": false,
  "render_guard_confirmed": true,
  "allow_unverified_bbox_fallback": true
}
```

Disable guard checks entirely for a known blank target:

```json
{
  "task": "capture_window",
  "render_guard": "save",
  "guard_checks": ["none"]
}
```

Detect tiny-region mistakes:

```json
{
  "task": "quick_look",
  "target": {
    "type": "region",
    "box": {"left": 0, "top": 0, "width": 8, "height": 8}
  },
  "render_guard": "warn",
  "guard_checks": ["tiny_capture"],
  "guard_tiny_min_pixels": 16
}
```

## Boundary

Capture guards use local heuristics and metadata. They can catch common bad captures, but they are not proof that a screenshot is complete or authorized. They should return reversible decisions, not hard moral judgments.
