# Compatibility Adapter Design

Screen Guardian is built around a dependency-compromise principle: prefer the best available local capability, but keep a useful fallback when the ideal path is unavailable.

## Origin Scenario

The motivating scenario was an older Windows system where a native Computer Use screenshot path was constrained by OS-level capture API support. In that situation, the AI could still use some text-oriented desktop signals, but screenshot-based workflows failed because there was no graceful fallback.

Screen Guardian should avoid that shape of failure. A user should not have to upgrade the operating system, replace the machine, or install a heavy service just to recover basic visual access for their AI.

## Adapter Contract

Future capture backends should fit this shape:

```text
CaptureAdapter
  id
  label
  priority
  dependencies
  capabilities
  probe()
  list_displays()
  list_windows()
  capture_screen(request)
  capture_region(request)
  capture_window(request)
  analyze_image(request)
  preprocess_image(request)
  list_audio_devices(request)
  record_audio(request)
  analyze_audio(request)
  extract_audio_track(request)
```

All adapters should return normalized result fields:

```text
ok
adapter
path
metadata_path
display
capture_box
analysis
original_size
saved_size
privacy
```

## Current Adapter

| Adapter | Role | Dependencies | Status |
| --- | --- | --- | --- |
| `python-mss` | Lightweight screenshot fallback | `mss`, `Pillow` | Implemented |
| `pillow-window` | Best-effort visible window capture | `Pillow`, Windows `user32` | Implemented |

## Workflow And Context Strategy

The current ultra-light model can write metadata sidecars for project IDs, workflow IDs, tags, notes, preprocessing choices, and source details. This is the first version of the workflow interface: files can be marked and held locally before an agent decides whether to spend context on the full image.

Image analysis and preprocessing are local Pillow-based heuristics. They can recommend whether a capture looks more like text, UI, photo, or mixed content, then apply presets such as text sharpening or UI sharpening. OCR and model-based image/video narration remain optional future adapters, not required dependencies.

Runtime limits, storage routes, and model/program routes are intentionally configurable. The default ultra-light limits protect ordinary use, but users can change or remove configurable bounds, save captures to multiple local folders, and register adapter routes for judgment, OCR, image narration, video narration, transcription, or custom workflows.

The route registry does not execute arbitrary commands in the ultra-light model. It records provider/model/settings metadata and can produce local request envelopes for another adapter, subagent, or model bridge to handle.

Feature flags are the performance boundary. Disabled modules should not import optional dependencies, start loops, copy mirrors, run image heuristics, call APIs, or trigger subagents. This lets one plugin expose many possible paths without making every path part of the hot capture path.

Image narration routes can point to a user-provided API or a future Codex subagent handoff. Video narration routes are kept as prior interfaces because practical video-capable models are relatively few; Screen Guardian records provider, model, input expectations, and settings without forcing a provider choice.

Audio capture and extraction use the same approach. Microphone recording, system-loopback recording, WAV analysis, and video audio extraction are optional modules. They can help diagnose whether a program emitted sound, whether a speaker/output path is silent, or whether a video should be summarized through its audio track.

## Planned Adapters

| Adapter | Role | Why optional |
| --- | --- | --- |
| `ffmpeg-gdigrab` | Short screen recording and video fallback | Useful but heavier than screenshots |
| `ffmpeg-audio-extract` | Extract audio tracks from videos | Useful for lecture/video understanding but requires FFmpeg |
| `sounddevice` | Microphone and best-effort Windows loopback recording | Useful for sound diagnostics but requires optional PortAudio/sounddevice dependencies |
| `screen-capture-lite` | High-frequency capture and frame-diff callbacks | Better performance, native build cost |
| `native-wgc` | Modern Windows Graphics Capture path | Fast on supported systems, fragile on unsupported ones |
| `ocr-adapter` | Convert text-heavy screenshots into text | Valuable but should not be mandatory |
| `vision-summary-adapter` | Convert image files into compact descriptions | Useful for context pressure, but model/provider choice should stay modular |
| `video-summary-adapter` | Convert videos, keyframes, or image sequences into compact descriptions | Useful but provider choices are few and should stay explicit |
| `audio-transcription-adapter` | Convert recordings or extracted audio into text or summaries | Useful for lectures, explanations, diagnostics, and program sound-effect tests |
| `route-bridge` | Execute prepared judgment/OCR/narration requests | Keeps model choice, temperature, quality, and follow-up behavior outside the capture core |
| `external-backend` | User-provided local capture service | Lets advanced users bring their own backend |

## Fallback Strategy

1. Probe adapters with `list_adapters`.
2. Use `adapter="auto"` for ordinary calls.
3. Prefer the lightest working backend.
4. Keep tool inputs stable across backend changes.
5. Return structured dependency hints when no backend is available.
6. Keep bounded watch capture short and explicit.
7. Gate optional work through feature flags.
8. Add heavier features, such as recording, OCR, or model narration, as optional adapters rather than mandatory dependencies.

This keeps positive freedom high by expanding what personal AI can do, while preserving negative freedom by avoiding forced upgrades, forced background services, and one-path lock-in.
