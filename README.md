# Screen Guardian

![Screen Guardian icon](assets/composer-icon.png)

Screen Guardian is a lightweight local screenshot plugin for Codex on Windows.

It is meant to provide compatibility-first capability infrastructure for personal AI.

Version `0.1.9` replaces separate product-weight thinking with optional capability flags: inactive features do not run optional work, while image/API/subagent and video narration routes can be kept as lightweight interfaces.

## Purpose

Screen Guardian is not only a screenshot helper. Its broader goal is to help users reach positive freedom with AI: more practical capability, more ways for their AI to perceive local work, and more room to build personal workflows.

At the same time, it should not reduce negative freedom. Users should not have to upgrade Windows, replace their environment, accept heavy background services, or install a long chain of dependencies just to give their AI basic visual access.

The project is guided by four principles:

- Expand user agency by giving personal AI more useful local capabilities.
- Preserve user control through local-only defaults and explicit capture actions.
- Prefer compatibility paths that work on older or constrained systems.
- Keep dependencies light, optional, and explainable.

## Why this exists

The first real use case came from an older Windows system where a native Computer Use screenshot path was limited by OS-level capture API support. The AI could still read some accessibility text, but native screenshots failed, so the whole visual workflow became fragile.

Screen Guardian treats that as the design problem: AI capability should not depend on one perfect system path. When a native interface, OS version, driver, or dependency is unavailable, the user should get a fallback path instead of losing the feature entirely.

## Concrete use cases

- Older Windows builds where native screen capture APIs are unavailable or partially unsupported.
- Machines that cannot be upgraded just to satisfy one AI tool's capture backend.
- Users who want AI visual access without accepting a heavy always-on screen recording service.
- Agents that need lower-resolution screenshots to understand a UI while keeping context and storage small.
- Developers who want to swap capture backends without rewriting the whole MCP tool surface.
- Short workflow observation where a program or region should be captured immediately when it changes.
- Text-heavy screenshots that should be sharpened, downscaled, tagged, or held as files before entering AI context.
- Future OCR, video, or continuous-capture workflows that need bounded, optional dependencies instead of mandatory heavy installs.
- Users who want limits, storage paths, model settings, or workflow stages to be configurable instead of hard-coded.
- Users who want one plugin where optional features can stay inactive without slowing the active capture path.

## Compatibility adapter model

Screen Guardian now exposes a small adapter surface through `list_adapters`. The current adapter is `python-mss`, selected through `adapter="auto"` by default.

The contract is intentionally simple:

- Probe available adapters before assuming a capture path works.
- Keep MCP tool inputs stable even when the backend changes.
- Return normalized result fields such as `adapter`, `path`, `display`, `capture_box`, and `saved_size`.
- Prefer lightweight fallbacks first, and make heavier dependencies optional.
- Report missing dependencies with install hints instead of failing silently.

See [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) for the planned dependency-compromise interface.

## Naming profile

Screen Guardian can keep its display identity flexible:

- `get_display_profile` reports the active name, detected system language, and current Codex manifest name.
- `set_display_name` switches between `auto` mode and `manual` mode.
- `auto` mode chooses a localized name such as `Screen Guardian` or `屏幕守护者`.
- `manual` mode stores a local alias under the user's app data folder, not in the public repository.
- `apply_display_profile` writes the active name into the local plugin manifest when the user wants the Codex plugin card to use it.

Codex reads plugin card metadata from the manifest, so a manifest-applied rename requires a plugin reload or reinstall before the UI shows the new name.

See [docs/NAMING.md](docs/NAMING.md) for details.

## Capability activation

Screen Guardian no longer needs separate lightweight/practical/heavy plugin variants. It is one compatibility-first plugin with optional capability flags.

Inactive features should avoid optional work: no polling loop, no extra mirror copy, no heuristic image analysis, no preprocessing, no OCR bridge, no external API request, and no subagent handoff unless the user enables or explicitly calls that path.

See [docs/MODELS.md](docs/MODELS.md) for the activation model in more detail.

## Current tools

- Check screenshot dependencies
- Read or set runtime settings, optional capability flags, persistent cache path, mirror storage routes, and configurable limits
- Register judgment/OCR/narration/transcription routes for future adapters
- Prepare model request files with prompt, questions, temperature, quality, and other settings
- Read or set the local display-name profile
- List compatibility adapters
- List connected displays
- List visible program windows
- Capture a full display or virtual desktop
- Capture a rectangular region
- Capture a visible program window by HWND, title, or process name
- Briefly watch a display, region, or matching window and save frames when it changes
- Analyze an image and recommend a context/preprocessing mode
- Preprocess an image with `none`, `auto`, `text`, `ui`, or `photo` presets
- Mark captures with project/workflow/tags/notes in a local metadata sidecar
- Save PNG or JPG
- Optionally downscale captures
- Clear Screen Guardian's local cache files

Captures are saved locally by default:

```text
~/Pictures/ScreenGuardian
```

See [docs/WORKFLOWS.md](docs/WORKFLOWS.md) for cache, feature flags, project/workflow markers, runtime limits, multi-route saves, model request envelopes, preprocessing, and bounded watch details.

## Dependencies

The first version uses Python with:

- `mss`
- `Pillow`

Install them with:

```powershell
python -m pip install --user -r scripts/requirements.txt
```

The MCP server itself uses Node.js and has no npm dependencies.

## Local test

You can smoke-test the MCP server with newline-delimited JSON-RPC:

```powershell
@'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"check_dependencies","arguments":{}}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_displays","arguments":{}}}
{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"list_windows","arguments":{"limit":5}}}
'@ | node .\mcp\server.cjs
```

## Privacy model

This version still avoids background services, recording, bundled OCR, cloud upload, and screen history. It can run bounded change-triggered capture, but only as an explicit foreground request. Bounds are configurable because the project treats limits as policy, not permanent product walls.

## Upgrade path

The next version can add:

- short FFmpeg recordings
- OCR adapters for text screenshots
- image and video summarization helpers
- stricter privacy filters by app, window, or region
