# Scenario: Desktop Situation Index

## User Situation

The user gives an ambiguous request such as "look at this," "check my browser," or "report what is open," and the AI should not guess the capture route too early.

## External Conditions

- Multiple displays, windows, tabs, regions, or nested scroll areas may exist.
- The lowest-cost useful observation may be metadata rather than pixels.
- A quiet route, visible desktop route, webpage route, or guided chain may have different side effects.

## Desired Effect

The AI first builds a compact index of possible targets and routes, then expands only the evidence needed for the task.

## Recommended Route

Use `guardian_check`, `guardian_survey_windows`, and `list_capture_routes` before expensive capture:

```json
{
  "capture_mode": "status_only",
  "limit": 20
}
```

Then select a target by HWND, display, region, URL, selector, or a future target id.

## Guard And Budget

- Prefer metadata-only status before screenshots.
- Report route side effects such as focus changes, visible-pixel fallback, browser automation, or long-image storage.
- Use hold-file when the target may be relevant but not yet worth context.

## Failure Branches

- Ambiguous title: require HWND or exact title.
- Webpage versus desktop confusion: ask for or infer a webpage route only when feature flags and dependencies permit it.
- Too many targets: page or truncate with counts.

## Acceptance Checks

- The index includes enough target metadata for the AI to avoid fragile prose-only target references.
- The route choice states whether it is desktop, application/window, webpage, nested-scroll, watch, or envelope-only.
- The receipt exposes side effects and risks before the AI spends high-cost context.

## Related Claims

- desktop situation index
- low-hamming-distance invocation
- route selection
- budget and auto-downgrade
