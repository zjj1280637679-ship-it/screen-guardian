# Workflow Interface

Screen Guardian `0.1.8` keeps the workflow layer flexible without turning the plugin into a background service.

## Local Cache

Use `get_runtime_settings` to inspect the active cache path and `set_cache_path` to set or clear a persistent local cache folder. Per-call `output_dir` still overrides the configured path.

Use `set_storage_routes` to add persistent mirror folders. Per-call `output_dirs` can store one capture in multiple places:

- first path: primary save path when `output_dir` is not set
- later paths: mirror paths
- `mirror_dirs`: extra per-call mirrors

Each mirror can receive a copied image and metadata sidecar.

## Project And Workflow Markers

Capture tools accept:

- `project_id`
- `workflow_id`
- `tags`
- `note`
- `context_policy`
- `marked_file_only`
- `output_dirs`
- `mirror_dirs`

When metadata is enabled, Screen Guardian writes a `.meta.json` sidecar next to the image. This lets agents leave marked files on disk, inspect their type, and decide later whether to load the image, downscale it, preprocess it, or wait for OCR/model narration.

## Runtime Limits

Upper and lower bounds are treated as runtime policy. `set_runtime_limits` can update, reset, or remove configurable limits.

Current default limits:

- `watch_duration_seconds_max`: `30`
- `watch_interval_seconds_min`: `0.1`
- `watch_interval_seconds_max`: `5`
- `watch_max_captures_max`: `50`
- `watch_burst_frames_max`: `10`
- `capture_scale_min`: `0.01`
- `capture_scale_max`: `1`
- `jpeg_quality_min`: `1`
- `jpeg_quality_max`: `95`

Use `null`, `none`, or `unbounded` to remove a configurable bound where the underlying capture or encoder still makes sense.

## Image Context Strategy

`analyze_image` estimates whether a local image is likely text, UI, photo, or mixed content. `preprocess_image` and capture-time `preprocess` can apply:

- `none`
- `auto`
- `text`
- `ui`
- `photo`

The `text` preset sharpens and increases contrast for text-heavy screenshots. It does not perform OCR yet; OCR is intentionally left as an optional adapter so older systems do not need a heavy dependency chain.

## Extension Routes

Use `set_extension_route` to register future routes for:

- `judgment`
- `ocr`
- `vision_summary`
- `video_summary`
- `transcription`
- `custom`

Routes can store provider names, model names, endpoints, command descriptors, and settings such as:

- `temperature`
- `quality`
- `max_tokens`
- `detail`
- `language`

Ultra-light mode does not execute arbitrary model commands. Instead, `prepare_model_request` writes a local request envelope with the input file, prompt, follow-up questions, and merged settings. A later adapter, model bridge, or subagent can read that request and write a response.

## Bounded Change Capture

`watch_screen` samples a display, region, or matching visible window for a short duration, saves frames when visual change crosses a threshold, and can save a small burst of consecutive frames after each detected change.

Default ultra-light limits:

- `duration_seconds` up to 30 seconds
- `max_captures` up to 50
- `burst_frames` up to 10

These defaults catch short UI changes while preserving the no-background-service default. They are configurable through `set_runtime_limits` because limits are policy, not permanent product walls.
