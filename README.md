# Screen Guardian

![Screen Guardian icon](assets/composer-icon.png)

Screen Guardian is a lightweight local screenshot plugin for Codex on Windows.

It is meant to provide compatibility-first capability infrastructure for personal AI.

Version `0.1.11` adds arbitrary-complexity decision policies and periodic or feature-triggered monitor profiles. A caller can describe webpage changes, program/window changes, error text, model-detected features, audio events, or video/audio workflow events, then prepare a local decision or monitor envelope without forcing a background service.

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

Screen Guardian is useful when a personal AI needs local sensory access, but the user's system, dependencies, context budget, or privacy expectations make one perfect capture path unrealistic. Its concrete uses fall into five practical groups.

### Restore visual access on constrained systems

- Older Windows builds where native screen capture APIs are unavailable or partially unsupported.
- Machines that cannot be upgraded just to satisfy one AI tool's capture backend.
- Users who want AI visual access without accepting a heavy always-on screen recording service.

### Control context, storage, and preprocessing

- Agents that need lower-resolution screenshots to understand a UI while keeping context and storage small.
- Text-heavy screenshots that should be sharpened, downscaled, tagged, or held as files before entering AI context.
- Users who want limits, storage paths, model settings, or workflow stages to be configurable instead of hard-coded.

### Observe projects when timing matters

- Short workflow observation where a program or region should be captured immediately when it changes.
- Project monitoring where a webpage, program window, region, audio stream, video file, or custom target should trigger capture when a configured feature appears.
- Error-aware workflows where a program, parser, or model can mark an error feature and request a screenshot, audio clip, model request, or follow-up decision.

### Extend into audio, video, and model narration

- Audio debugging: checking whether sound is actually being emitted, whether an external speaker path is likely silent, or whether a program sound effect was produced.
- Recording short explanations, lecture/video audio, or test-program sound effects for later transcription or narration.
- Extracting an audio track from a video before sending it to an audio or transcription route.
- Future OCR, video, or continuous-capture workflows that need bounded, optional dependencies instead of mandatory heavy installs.

### Keep the system adaptable

- Developers who want to swap capture backends without rewriting the whole MCP tool surface.
- Users who want one plugin where optional features can stay inactive without slowing the active capture path.
- Advanced routing where a decision can be a simple table, scoring function, external API, Codex subagent, local command bridge, or prepared request file.

Together, these use cases define Screen Guardian as compatibility infrastructure rather than a heavy recorder. It helps the AI capture what matters, mark why it matters, route it to the right workflow, and keep heavier OCR, audio, video, model, or scheduler paths optional.

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

Inactive features should avoid optional work: no polling loop, no extra mirror copy, no heuristic image analysis, no preprocessing, no audio-device probe, no recording, no FFmpeg extraction, no OCR bridge, no external API request, and no subagent handoff unless the user enables or explicitly calls that path.

Decision policies and monitor profiles are configuration and envelope interfaces. They can express complex logic, but Screen Guardian does not execute arbitrary decision code or install a background scheduler by default.

See [docs/MODELS.md](docs/MODELS.md) for the activation model in more detail.

## Current tools

Stable core tools:

- Check screenshot dependencies
- Read or set runtime settings, optional capability flags, persistent cache path, mirror storage routes, and configurable limits
- List optional audio devices when audio capture is enabled
- Record short microphone or best-effort system-loopback WAV clips
- Analyze WAV files for duration, RMS, peak, likely silence, and clipping
- Extract WAV audio tracks from videos through optional FFmpeg
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

Experimental workflow tools:

- Register judgment/OCR/narration/transcription routes for future adapters
- Prepare model request files with prompt, questions, temperature, quality, and other settings
- Optionally run real Volcengine Ark image, video, or audio experiments from local files or prepared request envelopes
- Register decision policies for capture, preprocessing, storage, model routing, or monitor actions
- Prepare decision request envelopes for arbitrary-complexity policies, APIs, subagents, local commands, or caller-owned functions
- Register periodic or feature-triggered monitor profiles for webpages, programs, windows, displays, regions, video, audio, errors, and model-detected features
- Prepare monitor tick envelopes for one scheduler/caller cycle

Experimental workflow entries are inert envelopes unless an explicit caller or standalone bridge consumes them.

Captures are saved locally by default:

```text
~/Pictures/ScreenGuardian
```

See [docs/WORKFLOWS.md](docs/WORKFLOWS.md) for cache, feature flags, project/workflow markers, runtime limits, multi-route saves, model request envelopes, decision policies, monitor profiles, preprocessing, and bounded watch details.

## Volcengine Ark experiments

`scripts/volcengine_ark_runner.py` is an optional external API bridge for real Ark experiments. It can consume a Screen Guardian model-request envelope or a direct image, video, or audio file. It only calls Ark when you run it and provide an API key through an environment variable.

```powershell
$env:ARK_API_KEY = "your-ark-api-key"
$env:ARK_MODEL = "your-model-id"

python .\scripts\volcengine_ark_runner.py `
  --dry-run `
  --path "C:\path\to\capture.jpg" `
  --media-kind image `
  --detail low `
  --thinking disabled `
  --max-tokens 300 `
  --prompt "请用中文简洁描述这个截图中对排查问题最重要的信息。"
```

Real runs write redacted request artifacts, responses, summaries, and a JSONL usage ledger under `~/Pictures/ScreenGuardian/ArkRuns` by default.

See [docs/VOLCENGINE_EXPERIMENTS.md](docs/VOLCENGINE_EXPERIMENTS.md) for the quota-aware workflow.

## Dependencies

The first version uses Python with:

- `mss`
- `Pillow`

Install them with:

```powershell
python -m pip install --user -r scripts/requirements.txt
```

The MCP server itself uses Node.js and has no npm dependencies.

For predictable MCP runtime discovery, set `SCREEN_GUARDIAN_PYTHON` to the Python executable you want Screen Guardian to use:

```powershell
$env:SCREEN_GUARDIAN_PYTHON = "C:\Path\To\python.exe"
```

This is preferred over npm's legacy `python` config. If `npm run ...` prints `npm warn Unknown env config "python"`, the warning is from npm configuration and does not mean Screen Guardian failed when the script exits successfully.

Optional audio recording uses:

```powershell
python -m pip install --user -r scripts/optional-audio-requirements.txt
```

Video audio extraction requires FFmpeg on `PATH`.

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

## Validation

Run static contract validation:

```powershell
python scripts/validate_contracts.py
```

Run the bounded MCP stress test:

```powershell
python scripts/validate_contracts.py --stress
```

See [docs/VALIDATION.md](docs/VALIDATION.md) for what these checks prove and what they intentionally leave to future adapters.

Run the Windows smoke test on a local Windows machine:

```powershell
npm run smoke:windows
```

## Privacy model

This version still avoids background services, recording, bundled OCR, cloud upload, and screen history. It can run bounded change-triggered capture, but only as an explicit foreground request. Monitor profiles describe periodic or feature-triggered work for a caller, scheduler, future adapter, or subagent; they do not silently start a monitor or scheduler. Bounds are configurable because the project treats limits as policy, not permanent product walls.

## Upgrade path

The next version can add:

- short FFmpeg recordings
- OCR adapters for text screenshots
- more provider-specific image and video summarization helpers
- stricter privacy filters by app, window, or region
- scheduler adapters that consume monitor tick envelopes with explicit user approval
