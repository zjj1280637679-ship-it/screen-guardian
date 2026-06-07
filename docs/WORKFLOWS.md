# Workflow Interface

Screen Guardian `0.1.7` adds a small workflow layer without turning the plugin into a background service.

## Local Cache

Use `get_runtime_settings` to inspect the active cache path and `set_cache_path` to set or clear a persistent local cache folder. Per-call `output_dir` still overrides the configured path.

## Project And Workflow Markers

Capture tools accept:

- `project_id`
- `workflow_id`
- `tags`
- `note`
- `context_policy`
- `marked_file_only`

When metadata is enabled, Screen Guardian writes a `.meta.json` sidecar next to the image. This lets agents leave marked files on disk, inspect their type, and decide later whether to load the image, downscale it, preprocess it, or wait for OCR/model narration.

## Image Context Strategy

`analyze_image` estimates whether a local image is likely text, UI, photo, or mixed content. `preprocess_image` and capture-time `preprocess` can apply:

- `none`
- `auto`
- `text`
- `ui`
- `photo`

The `text` preset sharpens and increases contrast for text-heavy screenshots. It does not perform OCR yet; OCR is intentionally left as an optional adapter so older systems do not need a heavy dependency chain.

## Bounded Change Capture

`watch_screen` samples a display, region, or matching visible window for a short duration, saves frames when visual change crosses a threshold, and can save a small burst of consecutive frames after each detected change.

Current ultra-light limits:

- `duration_seconds` up to 30 seconds
- `max_captures` up to 50
- `burst_frames` up to 10

This catches short UI changes while preserving the no-background-service default.
