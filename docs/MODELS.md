# Capability Activation Model

Screen Guardian is one plugin, not a family of separate lightweight/practical/heavy plugins.

The design goal is to keep capability broad while making each nonessential path optional. A feature that is inactive should avoid optional runtime cost for the features that remain active.

## Principle

Capability is split into small modules:

- screen capture
- window capture
- bounded watch
- workflow metadata
- multi-route storage
- image analysis
- image preprocessing
- extension route registry
- model request envelopes
- decision policies
- monitor profiles
- OCR routes
- image narration routes
- video narration routes
- audio capture
- audio analysis
- audio transcription routes
- video audio extraction
- external API handoff
- Codex subagent handoff
- raw local execution

Implemented modules can be used directly. Interface modules can be registered and prepared without forcing their heavy dependencies into the capture core.

The public tool surface is split into two layers:

- core capture and local diagnostics: stable paths that perform local capture, preprocessing, audio analysis, and cache management
- experimental workflow envelopes: declarative model routes, decision policies, monitor profiles, external API handoff descriptors, and subagent handoff descriptors

Experimental workflow envelopes are inert until an explicit caller or standalone bridge consumes them.

For first use, treat this as a progressive path:

1. Start with core tools: check dependencies, list displays/windows, and capture a screen, region, or window.
2. Add local control tools when the user needs cache routing, runtime limits, metadata, preprocessing, display naming, or audio diagnostics.
3. Add experimental envelope tools only when the user wants another caller, bridge, scheduler, future adapter, or subagent to consume prepared workflow data.

## Feature Flags

`set_feature_flags` can enable, disable, or reset optional modules. `get_runtime_settings` returns the active flags and the feature catalog.

Inactive modules should behave like this:

- no polling loop unless `bounded_watch` is active and `watch_screen` is called
- no mirror copy unless `multi_storage_routes` is active
- no metadata sidecar unless `workflow_metadata` is active
- no heuristic image analysis unless requested and `image_analysis` is active
- no preprocessing unless `image_preprocess` is active
- no model request file unless `model_request_envelopes` is active
- no decision envelope unless `decision_policies` is active and explicitly called
- no monitor profile lookup or monitor tick envelope unless `monitor_profiles` is active and explicitly called
- no audio device probe or recording unless `audio_capture` is active
- no WAV analysis unless `audio_analysis` is active
- no FFmpeg extraction unless `video_audio_extract` is active
- no OCR, external API, video narration, or subagent handoff unless a future adapter explicitly handles it
- no raw local execution unless `raw_local_exec` is persistently enabled and `guardian_run_exec` is called with `user_confirmed=true`

## Route Interfaces

Image narration can be handled by:

- a user-provided API route
- a prepared local request file
- the optional `scripts/volcengine_ark_runner.py` bridge when the user explicitly wants a real Ark API call
- a future Codex subagent handoff
- a future local command adapter

Video narration providers are fewer, so Screen Guardian keeps a prior interface for them:

- input can be a video file, keyframes, or an image sequence
- settings can include detail, quality, temperature, keyframe policy, language, and token budget
- execution remains outside the capture core until an adapter is added

Audio is mapped the same way as images and video:

- microphone or system-loopback recording is optional
- local WAV analysis can detect likely silence, clipping, and basic audio energy
- video files can expose audio by extracting a WAV track through optional FFmpeg
- transcription and audio-summary routes can use prepared files, user APIs, local commands, or future Codex subagent handoff

## Decision Policies

`set_decision_policy` stores how a caller should choose between capture, preprocessing, storage, model-route, and monitor actions.

The policy can stay simple:

- `manual`
- `rule_table`
- `scoring_function`

Or it can point to arbitrary-complexity logic owned outside the hot capture path:

- `function_route`
- `prepared_file`
- `external_api`
- `codex_subagent`
- `local_command`

`prepare_decision_request` writes the observation, candidates, constraints, objective, registered route prior, and merged settings into a local envelope. Screen Guardian prepares the decision input; the route, API, subagent, local command bridge, or caller performs the complex decision.

Registering a decision policy is configuration, not execution. It does not call an API, run a local command, invoke a subagent, or choose an action until an explicit caller or future adapter consumes the prepared request.

## Monitor Profiles

`set_monitor_profile` stores periodic or feature-triggered monitoring plans for a project or workflow. Profiles can describe targets such as webpages, program windows, processes, displays, regions, audio devices, video files, or custom sources.

Supported trigger descriptions include:

- `periodic`
- `visual_change`
- `web_change`
- `window_change`
- `error_text`
- `model_feature`
- `audio_energy`
- `audio_silence`
- `audio_clipping`
- `custom`

Actions can include screenshot capture, window capture, audio recording, video audio extraction, model request preparation, and decision request preparation. `prepare_monitor_tick` writes one local tick envelope for a caller, scheduler, future adapter, or subagent. It does not start a background scheduler by itself.

Registering a monitor profile is also configuration, not monitoring. It stores targets, triggers, and candidate actions so an explicit scheduler, caller, foreground watch, or future adapter can decide what to do.

## Capability Runtime And Break-Glass Execution

`guardian_list_commands` exposes reusable command entries for the main AI. `guardian_run_command` runs only those registered entries, so common workflows can be reused without the main AI inventing low-level tool chains or raw code.

`guardian_prepare_exec` can write a local break-glass execution envelope. `guardian_run_exec` is the only raw local execution path. It can run Python, PowerShell, or Node code, but it is disabled by default, bounded by runtime limits, logged locally, and requires explicit per-call confirmation.

## Runtime Bounds

Bounds such as watch duration, maximum captures, burst frames, scale, and JPEG quality are runtime policy. They can be changed or removed with `set_runtime_limits` where the underlying encoder or capture backend permits it.

## Design Rule

The project should expand what the user's AI can do while avoiding forced upgrades, forced background services, one-path lock-in, and hidden performance cost from inactive features.

## Real External Experiments

External API experiments stay outside the always-available capture core. The Volcengine Ark runner can execute a prepared request envelope or direct media file, but it is a script the user runs intentionally. It reads API keys only from environment variables, stores redacted request artifacts, and appends local usage records for later reconciliation.

This keeps the default plugin local-only while allowing real image, video, and audio model tests when the user chooses to spend quota.
