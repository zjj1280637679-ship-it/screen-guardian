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
- OCR routes
- image narration routes
- video narration routes
- audio capture
- audio analysis
- audio transcription routes
- video audio extraction
- external API handoff
- Codex subagent handoff

Implemented modules can be used directly. Interface modules can be registered and prepared without forcing their heavy dependencies into the capture core.

## Feature Flags

`set_feature_flags` can enable, disable, or reset optional modules. `get_runtime_settings` returns the active flags and the feature catalog.

Inactive modules should behave like this:

- no polling loop unless `bounded_watch` is active and `watch_screen` is called
- no mirror copy unless `multi_storage_routes` is active
- no metadata sidecar unless `workflow_metadata` is active
- no heuristic image analysis unless requested and `image_analysis` is active
- no preprocessing unless `image_preprocess` is active
- no model request file unless `model_request_envelopes` is active
- no audio device probe or recording unless `audio_capture` is active
- no WAV analysis unless `audio_analysis` is active
- no FFmpeg extraction unless `video_audio_extract` is active
- no OCR, external API, video narration, or subagent handoff unless a future adapter explicitly handles it

## Route Interfaces

Image narration can be handled by:

- a user-provided API route
- a prepared local request file
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

## Runtime Bounds

Bounds such as watch duration, maximum captures, burst frames, scale, and JPEG quality are runtime policy. They can be changed or removed with `set_runtime_limits` where the underlying encoder or capture backend permits it.

## Design Rule

The project should expand what the user's AI can do while avoiding forced upgrades, forced background services, one-path lock-in, and hidden performance cost from inactive features.
