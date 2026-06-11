# Scenario: Batch Window Survey

## User Situation

The user asks the AI to report the status of all program windows and optionally inspect selected screenshots.

## External Conditions

- Many windows may be open.
- Capturing every window into context would waste tokens and may expose private content.
- Quiet window capture can be imperfect for GPU or browser windows.

## Desired Effect

The AI receives a compact desktop situation index first, then selectively opens or captures only the relevant targets.

## Recommended Route

Start status-only:

```json
{
  "capture_mode": "status_only",
  "limit": 20
}
```

Then request hold-file captures for selected windows only:

```json
{
  "capture_mode": "hold_file",
  "limit": 5,
  "include_visibility_probe": true
}
```

## Guard And Budget

- Use bounded capture count.
- Prefer hold-file mode for images.
- Keep private or ambiguous windows as metadata unless the user asks for capture.

## Failure Branches

- Too many windows: sort and page results.
- Ambiguous titles: require HWND.
- Risky fallback: return paths and risk fields for selective review.

## Acceptance Checks

- Status-only mode does not save screenshots.
- Hold-file mode returns local paths without forcing every image into AI context.
- The AI can choose a subset based on process, title, bounds, and risk fields.
- Large surveys report `total_count`, `returned_count`, and whether results were truncated or paged.
- Each listed window includes stable target metadata such as HWND when available, process, title, bounds, minimized/offscreen hints, and visibility or occlusion risk when probed.
- Privacy-sensitive or ambiguous windows can remain metadata-only until the user asks for capture.

## Related Claims

- desktop situation index
- perception depth
- budget and auto-downgrade
- selective context spending
