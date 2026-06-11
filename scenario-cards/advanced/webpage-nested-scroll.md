# Scenario: Webpage Or Nested Scroll Long Capture

## User Situation

The user wants the AI to capture a full webpage, long admin page, embedded table, iframe, or nested scroll container rather than only the visible desktop slice.

## External Conditions

- Desktop screenshots only capture visible pixels.
- Webpage capture may require browser automation dependencies.
- Some admin pages contain nested scroll regions that need a selector or route plan.
- This route can change page scroll state or require a browser context.

## Desired Effect

The AI chooses a webpage route instead of pretending a desktop screenshot is a complete page capture.

## Recommended Route

Use `list_capture_routes` first. If enabled, prepare or run the webpage route:

```json
{
  "url": "https://example.com",
  "mode": "scroll_container",
  "selector": ".table-scroll",
  "context_policy": "hold_file",
  "marked_file_only": true
}
```

## Guard And Budget

- Requires persistent `webpage_capture=true`.
- Prefer hold-file mode for long images.
- Use explicit URL, selector, frame selector, or route envelope.
- Do not treat webpage capture as a normal desktop screenshot parameter.

## Failure Branches

- Feature disabled: return activation hint and optional route description.
- Selector missing: return diagnostic information and avoid fake success.
- Page requires authentication or authorization: rely on the user's authorized browser/session context only.

## Acceptance Checks

- The route reports whether webpage capture is active or inactive.
- Long capture output is local and bounded.
- Nested scroll capture does not imply bypassing access controls or platform rules.

## Related Claims

- capture route selection
- optional dependencies
- anti-abuse stance
- hold-file context
