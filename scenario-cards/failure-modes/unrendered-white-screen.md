# Scenario: Unrendered Or White-Screen Capture

## User Situation

The user asks the AI to capture a program or page, but the target exists before its content has finished rendering.

## External Conditions

- Older systems may show white or incomplete frames during startup or page transitions.
- A blank frame can be valid evidence if the task is to document the blank state.
- A blank frame is misleading if the task is to read or verify completed content.

## Desired Effect

The plugin should distinguish evidence capture from informational capture and return a decision menu when needed.

## Recommended Route

Use `guardian_perceive` with stackable timing modes when the default fast path is not enough:

```json
{
  "task": "debug_ui",
  "target": {"type": "window", "hwnd": 123456},
  "capture_modes": ["wait_render", "wait_buffer"],
  "render_guard": "warn"
}
```

## Guard And Budget

- Default guard checks only enable unrendered detection.
- Additional checks should be optional and composable.
- The decision menu can offer force now, capture later, or auto-detect render completion.

## Failure Branches

- User needs raw evidence: save with risk metadata.
- User needs completed UI: wait within runtime limits.
- Timeout: return `not_ready` or `decision_required` with next actions.

## Acceptance Checks

- Suspected unrendered output does not silently save as a normal success.
- The receipt exposes `result_state`, `saved`, risks, and available actions.
- Runtime limits bound delay and retry behavior.
- Evidence capture can save a blank or error state when the receipt marks it as evidence with risk metadata.
- Informational capture returns wait, decision, timeout, or not-ready states instead of presenting blank content as complete UI.

## Related Claims

- render guard
- evidence capture
- informational capture
- bounded failure
