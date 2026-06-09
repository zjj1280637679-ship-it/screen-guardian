# Workflow Interface

Screen Guardian `0.1.14` keeps the workflow layer flexible without turning the plugin into a background service.

For AI agents, start with the AI-first facade tools: `guardian_check`, `guardian_perceive`, and `guardian_prepare_workflow`. They reduce tool-choice overhead by mapping common intents to the existing core, local-control, and envelope tools without expanding permissions or starting hidden work.

For reusable capability workflows, use `guardian_list_commands` and `guardian_run_command`. For emergency user-directed code execution, use `guardian_prepare_exec` and `guardian_run_exec`; raw execution is a disabled-by-default break-glass path, not ordinary automation.

## How To Read The Layers

The workflow surface is split so first-time users do not need to understand every future route before taking one screenshot.

| Layer | Use it for | What it does not do |
| --- | --- | --- |
| Core tools | Dependency checks, display/window listing, screenshots, window capture, short foreground change capture, and cache cleanup | No background service, no model call, no hidden upload |
| Local control tools | Feature flags, runtime limits, cache paths, mirror routes, metadata sidecars, image analysis/preprocessing, display naming, and optional audio diagnostics | No automatic scheduler or external API handoff |
| Experimental envelope tools | Model request envelopes, extension routes, decision policies, and monitor profiles | No arbitrary code execution, API call, subagent invocation, recording, or monitoring unless another explicit caller consumes the envelope |
| Capability runtime tools | Registered command catalog, command runner, and break-glass execution envelopes | No arbitrary code through `guardian_run_command`; raw execution requires `raw_local_exec` and per-call confirmation |
| Optional browser tools | Full-page, viewport, or element webpage capture through Playwright when enabled | No browser launch, page navigation, or long screenshot unless `webpage_capture` is enabled and `capture_webpage` is called |

When onboarding a new user, start with `check_dependencies`, `list_displays`, and one capture tool. Add local control options only when the user needs storage, compression, preprocessing, metadata, or audio diagnostics. Use experimental envelope tools only when the user is designing a workflow that another bridge, scheduler, adapter, or subagent will consume.

## Feature Flags

Use `set_feature_flags` to enable, disable, or reset optional capability modules. `get_runtime_settings` returns the current flags and a catalog explaining what inactive features avoid doing.

The important performance rule is simple: inactive features should not drag active features. A normal capture can save an image without running image analysis, preprocessing, mirror copies, decision-policy preparation, monitor-profile lookup, audio probing, recording, FFmpeg extraction, OCR, API calls, video narration, or subagent handoff.

Persistent feature flags are also the safety boundary. Per-call `feature_flags` can temporarily disable a feature for one request, but they cannot enable a feature that persistent settings have disabled. High-risk paths such as audio capture, video audio extraction, OCR routes, external API handoff, and subagent handoff must be enabled persistently through `set_feature_flags`.

`raw_local_exec` is the break-glass local execution flag. It defaults to disabled and must be enabled persistently before `guardian_run_exec` can run Python, PowerShell, or Node code. The execution call must still include `user_confirmed=true`.

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

When metadata is enabled through `workflow_metadata`, Screen Guardian writes a `.meta.json` sidecar next to the image. This lets agents leave marked files on disk, inspect their type, and decide later whether to load the image, downscale it, preprocess it, or wait for OCR/model narration.

## Runtime Limits

Upper and lower bounds are treated as runtime policy. `set_runtime_limits` can update, reset, or remove configurable limits.

Per-call `runtime_limits` can only tighten persistent bounds. For example, a call may reduce `watch_duration_seconds_max` or increase `watch_interval_seconds_min`, but it may not remove a bound or raise a maximum above the configured value.

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
- `capture_settle_delay_ms_max`: `5000`
- `capture_render_retry_count_max`: `8`
- `capture_render_retry_interval_ms_max`: `2000`
- `audio_duration_seconds_max`: `120`
- `audio_sample_rate_max`: `48000`
- `audio_channels_max`: `2`
- `audio_extract_duration_seconds_max`: `null`

Use `null`, `none`, or `unbounded` to remove a configurable bound where the underlying capture or encoder still makes sense.

## Image Context Strategy

`analyze_image` estimates whether a local image is likely text, UI, photo, or mixed content. Normal capture saves do not run this analysis unless `analyze: true` is passed or `preprocess: auto` needs it.

`preprocess_image` and capture-time `preprocess` can apply:

- `none`
- `auto`
- `text`
- `ui`
- `photo`

The `text` preset sharpens and increases contrast for text-heavy screenshots. It does not perform OCR yet; OCR is intentionally left as an optional adapter so older systems do not need a heavy dependency chain.

## Advisory Context Signals

Screen Guardian should not use regex, focus state, window titles, process names, URL fragments, or simple keyword matches as hard moral blockers. Those signals are too low-context and have legitimate counterexamples.

When a workflow detects a potentially sensitive or ambiguous context, it should prefer reversible responses: add metadata, suggest `context_policy="hold_file"`, keep processing local, ask for explicit user confirmation before model sharing, or explain that a bypass-oriented use case is outside project support.

Hard rejection belongs to objective mechanics such as inactive feature flags, runtime limits, configured storage ownership, missing dependencies, or the rule that envelope tools do not execute APIs, subagents, commands, or schedulers by themselves.

## Experimental Envelope Layer: Extension Routes

Use `set_extension_route` to register future routes for:

- `judgment`
- `ocr`
- `vision_summary`
- `video_summary`
- `audio_summary`
- `sound_diagnostics`
- `transcription`
- `custom`

Routes can store provider names, model names, endpoints, command descriptors, and settings such as:

- `temperature`
- `quality`
- `max_tokens`
- `detail`
- `language`

Routes can also store `handoff_mode`:

- `prepared_file`
- `external_api`
- `codex_subagent`
- `local_command`

Image narration can use a user-provided API or a future Codex subagent handoff. Video narration has fewer practical providers, so Screen Guardian keeps a prior interface for video files, image sequences, and keyframes without selecting or installing a provider by default.

Ultra-light mode does not execute arbitrary model commands. Instead, `prepare_model_request` writes a local request envelope with the input file, prompt, follow-up questions, route prior, and merged settings. A later adapter, model bridge, or subagent can read that request and write a response.

The optional Volcengine Ark runner is one such bridge. It is a standalone script, not automatic MCP behavior, and it only makes a real external request when the user runs it with an API key in the environment.

## Experimental Envelope Layer: Decision Policies

Use `set_decision_policy` when the best next action should be chosen by configurable logic instead of a fixed threshold.

Decision policies can describe:

- what objective to optimize, such as "capture only when the UI meaningfully changes"
- what candidates are available, such as screenshot, window capture, audio clip, model request, or no-op
- what constraints apply, such as context budget, privacy rules, storage limits, or allowed programs
- what route owns the logic, such as a rule table, scoring function, prepared file, external API, Codex subagent, local command bridge, or caller-owned function

Use `prepare_decision_request` to write a local JSON envelope for one decision. The envelope includes the observation, candidates, constraints, route prior, policy metadata, and merged settings. This lets a later function become arbitrarily complex without making Screen Guardian execute arbitrary code in the ultra-light core.

`set_decision_policy` only stores configuration. It does not execute a function route, local command, API call, or subagent. Execution requires a separate explicit caller or adapter.

Example decision roles:

- `capture_decision`
- `preprocess_decision`
- `storage_decision`
- `model_route_decision`
- `monitor_decision`

## Experimental Envelope Layer: Monitor Profiles And Feature Triggers

Use `set_monitor_profile` to describe periodic or feature-triggered project monitoring.

Targets can describe:

- a webpage URL, DOM hash, title, or visual viewport
- a program window by title, HWND, or process name
- a display or screen region
- an audio device or system-loopback source
- a video file or extracted audio track
- a custom project/workflow source

Triggers can describe:

- `periodic`: run every configured interval
- `visual_change`: screenshot when a display, region, or window changes
- `web_change`: screenshot or request narration when a webpage changes
- `window_change`: screenshot when a program changes state
- `error_text`: capture when logs, OCR, DOM text, or a parser sees an error
- `model_feature`: capture when a program or agent model recognizes a configured feature
- `audio_energy`: record/analyze when sound energy appears
- `audio_silence`: capture diagnostics when expected sound is silent
- `audio_clipping`: capture diagnostics when audio peaks suggest clipping
- `custom`: leave room for project-specific detectors

Actions can describe:

- `capture_screen`
- `capture_region`
- `capture_window`
- `watch_screen`
- `record_audio`
- `analyze_audio`
- `extract_audio_track`
- `prepare_model_request`
- `prepare_decision_request`

Use `prepare_monitor_tick` to write one local tick envelope. A scheduler, caller, future adapter, or subagent can read the profile, current observations, detected features, and candidate actions, then choose what to do. Screen Guardian does not silently install a background scheduler.

`set_monitor_profile` only stores configuration. It does not start polling, screenshots, recording, API calls, subagent work, or a background service.

## Audio Capture And Extraction

Audio follows the same optional interface as screenshots and video:

- `list_audio_devices` can probe optional recording devices only when `audio_capture` is active.
- `record_audio` can save short WAV clips from a microphone or best-effort Windows WASAPI loopback.
- `analyze_audio` can inspect 16-bit PCM WAV files for duration, RMS, peak, likely silence, and clipping.
- `extract_audio_track` can extract a WAV track from a video through optional FFmpeg when `video_audio_extract` is active.

Useful cases include checking whether a program actually emitted sound, distinguishing silent output from a broken external speaker path, recording a user explanation, listening to lecture/video audio through a future transcription route, and testing program sound effects.

Optional recording dependencies live in `scripts/optional-audio-requirements.txt`. Video audio extraction requires FFmpeg on `PATH`.

## Bounded Change Capture

`watch_screen` samples a display, region, or matching visible window for a short duration, saves frames when visual change crosses a threshold, and can save a small burst of consecutive frames after each detected change.

Default ultra-light limits:

- `duration_seconds` up to 30 seconds
- `max_captures` up to 50
- `burst_frames` up to 10

These defaults catch short UI changes while preserving the no-background-service default. They are configurable through `set_runtime_limits` because limits are policy, not permanent product walls.

## Render Timing And Delayed Capture

Capture tools accept `delay_seconds` or `settle_delay_ms` when the user wants a screenshot a few seconds later, such as after opening a slow program or waiting for a popup.

Window capture defaults to `wait_for_nonblank=true`. If the first frame is clearly blank, black, or white with very low visual information, Screen Guardian retries briefly before saving. Use `render_retry_count` and `render_retry_interval_ms` to tune that behavior within runtime limits.

Use `render_guard` when the capture should not quietly save a likely unrendered frame:

- `render_guard="save"` keeps the old behavior and saves even if the final frame still looks blank.
- `render_guard="warn"` defers saving and returns decision actions: force capture now, capture later, or auto-detect render completion before capture. Set `render_guard_confirmed=true` when the blank frame is expected.
- `render_guard="wait"` forces render-aware retry and only saves when the final frame no longer looks blank; if the retry window expires, it returns the same decision actions instead of saving.
- `render_guard="fail"` blocks suspected-unrendered saves for stricter automation.

The registered command `perceive.window.after_render` uses `render_guard="wait"` by default. This is the preferred route when a slow program, installer, browser tab, or popup may exist before the contents finish drawing.

`guard_checks` controls which quality checks run. The default is `["unrendered"]`. Optional checks such as `minimized_window`, `offscreen_window`, `tiny_capture`, `stale_frame`, and `occlusion_risk` must be enabled explicitly, or by passing `["all"]`. See `docs/CAPTURE_GUARDS.md` for the decision payload and examples.

For screen or region capture, `wait_for_nonblank` is opt-in because a whole desktop or document page can legitimately be mostly white. Use `watch_screen` or `guardian_perceive` with `task="watch_change"` for screen changes, popup transitions, and other event-like moments.

## Full Webpage Long Screenshots

Desktop screenshot tools can only capture currently visible pixels. Use `prepare_webpage_capture` or `capture_webpage` when the user needs the full scrollable webpage instead of the current browser viewport.

`prepare_webpage_capture` writes a local request envelope only. `capture_webpage` is an optional Playwright route that supports `mode="full_page"`, `mode="viewport"`, and `mode="element"`. The feature flag `webpage_capture` defaults to inactive so the ultra-light screen path does not import browser automation dependencies or navigate pages.

See `docs/WEBPAGE_CAPTURE.md` for installation, examples, tall-page decision behavior, and related browser APIs.
