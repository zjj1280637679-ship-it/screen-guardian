# Usage

Screen Guardian should feel intuitive to the AI caller. The agent should describe intent first, then let the plugin map that intent to safer lower-level tools.

## Default Entry

Recommended first calls:

- `guardian_check` when runtime state is uncertain
- `guardian_perceive` for quick look, text-heavy screenshot, UI debugging, window capture, short watch, or hold-file mode
- `guardian_survey_windows` for many-window status reports
- `list_capture_routes` when desktop, application, webpage, nested-scroll, or guided-chain routes may differ

Low-level tools remain available for expert control. They are not removed; they become the specialist layer.

## Ordinary Perception Flow

```text
guardian_check
  -> choose route and target
  -> guardian_perceive or low-level capture
  -> render and identity guard
  -> receipt
  -> optional selective image review or workflow envelope
```

## Context Economy

The AI should not ingest every image by default.

Use:

- low context budget for quick visual orientation
- normal budget for ordinary UI debugging
- high budget only when visual detail matters
- hold-file mode when a screenshot should be saved and tagged but not immediately read into context

## User-Facing Meaning

The user asks normal questions:

- "Look at my screen."
- "Check that window."
- "Wait until it finishes rendering, then capture."
- "Keep the image as a file."
- "Report all open program windows."

The plugin should translate these into structured target, route, guard, budget, and receipt choices.
