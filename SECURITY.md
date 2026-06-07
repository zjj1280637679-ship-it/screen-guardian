# Security Notes

Screen Guardian is designed as a local-only visual helper for Codex.

## Current boundaries

- Screenshots are saved locally only.
- The plugin does not upload screenshots.
- The plugin does not run continuous capture in version 0.1.0.
- The plugin does not keep a long-term screen history.
- Capture output defaults to `~/Pictures/ScreenGuardian`.

## Recommended use

- Capture only the screen or region needed for the current task.
- Use `max_width`, `max_height`, or `scale` to reduce image size before analysis.
- Clear the local cache after sensitive debugging sessions.

## Planned safeguards

Future versions should add explicit duration limits for continuous capture, app/window filters, bounded storage, and stronger redaction options before adding recording or screen-history features.
