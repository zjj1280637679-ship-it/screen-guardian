# Scenario: Quiet Program Window Capture

## User Situation

The user wants the AI to inspect a program window without bringing that window to the front.

## External Conditions

- Some windows can be captured quietly through HWND or adapter routes.
- Browser or GPU-heavy content may return a low-information client area.
- Visible-bbox fallback can capture the wrong pixels when windows overlap.

## Desired Effect

The AI captures or diagnoses the target window while preserving user focus when possible.

## Recommended Route

Use `list_windows` or `guardian_survey_windows` first, then capture by HWND or exact target when available.

```json
{
  "task": "capture_window",
  "target": {"type": "window", "hwnd": 123456},
  "context_budget": "normal"
}
```

## Guard And Budget

- Prefer quiet capture.
- Do not activate, raise, or make the target topmost unless the user accepts a visible fallback.
- Report `window_client_low_information`, `occlusion_risk`, and `bbox_identity_mismatch` instead of silently saving risky fallback pixels.

## Failure Branches

- Multiple matching titles: request HWND or exact title.
- Direct window capture looks blank: try guarded visible fallback only if identity can be verified.
- Visible fallback identity is ambiguous: return a decision state instead of pretending success.

## Acceptance Checks

- The receipt states whether a quiet route or fallback route was used.
- `ok=true` is not treated as a saved file unless `saved=true`.
- Risk fields survive through the AI-first facade.
- Focus, foreground activation, topmost changes, or page-state changes are either absent or explicitly reported as side effects.
- A visible fallback requires user acceptance or a receipt-level decision state when identity cannot be verified.

## Related Claims

- quiet capture by default
- evidence versus informational capture
- guard policy
- machine-readable receipt
