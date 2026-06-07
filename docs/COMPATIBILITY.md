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
  capture_screen(request)
  capture_region(request)
```

All adapters should return normalized result fields:

```text
ok
adapter
path
display
capture_box
original_size
saved_size
privacy
```

## Current Adapter

| Adapter | Role | Dependencies | Status |
| --- | --- | --- | --- |
| `python-mss` | Lightweight screenshot fallback | `mss`, `Pillow` | Implemented |

## Planned Adapters

| Adapter | Role | Why optional |
| --- | --- | --- |
| `ffmpeg-gdigrab` | Short screen recording and video fallback | Useful but heavier than screenshots |
| `screen-capture-lite` | High-frequency capture and frame-diff callbacks | Better performance, native build cost |
| `native-wgc` | Modern Windows Graphics Capture path | Fast on supported systems, fragile on unsupported ones |
| `external-backend` | User-provided local capture service | Lets advanced users bring their own backend |

## Fallback Strategy

1. Probe adapters with `list_adapters`.
2. Use `adapter="auto"` for ordinary calls.
3. Prefer the lightest working backend.
4. Keep tool inputs stable across backend changes.
5. Return structured dependency hints when no backend is available.
6. Add heavier features, such as recording or continuous capture, as optional adapters rather than mandatory dependencies.

This keeps positive freedom high by expanding what personal AI can do, while preserving negative freedom by avoiding forced upgrades, forced background services, and one-path lock-in.
