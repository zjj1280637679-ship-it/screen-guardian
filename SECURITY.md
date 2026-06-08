# Security Notes

Screen Guardian is designed as local-first capability infrastructure for Codex. It can capture screens, windows, short bounded change sequences, and optional audio/video artifacts, but heavy or sensitive paths stay off until explicitly configured or called.

## Data Types

| Data type | Tool path | Default state | Saved location |
| --- | --- | --- | --- |
| Screenshots | `capture_screen`, `capture_region`, `capture_window` | Enabled | `~/Pictures/ScreenGuardian` or configured routes |
| Bounded visual watch frames | `watch_screen` | Enabled, bounded by runtime limits | Same local capture paths |
| Metadata sidecars | capture/audio/model envelope tools | Enabled | Next to the saved file |
| Audio recordings | `record_audio` | Disabled by feature flag | Same local media paths |
| Video audio extraction | `extract_audio_track` | Disabled by feature flag and requires FFmpeg | Same local media paths |
| Model request envelopes | `prepare_model_request` | Enabled as local files only | Same local cache path |
| Decision and monitor envelopes | `prepare_decision_request`, `prepare_monitor_tick` | Enabled as local files only | Same local cache path |
| External API experiments | `scripts/volcengine_ark_runner.py` | Not part of MCP default execution | `~/Pictures/ScreenGuardian/ArkRuns` |

## Trigger Boundaries

- The plugin does not start a background scheduler.
- Monitor profiles are declarative. They do not poll, capture, record, call APIs, or invoke subagents until an explicit caller consumes them.
- Decision policies are declarative. They do not execute arbitrary functions, local commands, APIs, or subagents in the ultra-light core.
- Bounded watch only runs when `watch_screen` is explicitly called and is capped by runtime limits.
- Audio capture and FFmpeg extraction require persistent feature-flag enablement.
- External API use is handled by a separate runner script that must be run intentionally with an environment-provided API key.

## Configuration Boundaries

- Persistent feature flags are the hard enablement boundary.
- Per-call `feature_flags` can only disable a feature for that call. They cannot enable a feature disabled in persistent settings.
- Persistent runtime limits are the hard ceiling/floor boundary.
- Per-call `runtime_limits` can only tighten a bound. They cannot loosen or remove configured limits.
- `clear_cache` only accepts the default cache path or paths configured with `set_cache_path` or `set_storage_routes`.
- Cache deletion is limited to Screen Guardian-named files and skips metadata files that do not identify this plugin as owner.

## Storage And Deletion

Capture output defaults to:

```text
~/Pictures/ScreenGuardian
```

Use `set_cache_path` and `set_storage_routes` to choose persistent local storage. Use `clear_cache` for default or configured routes. For sensitive sessions, prefer a dedicated temporary cache route and clear it after the session.

## What Screen Guardian Does Not Do By Default

- It does not upload screenshots.
- It does not stream the screen.
- It does not keep a long-term screen history.
- It does not execute registered local commands.
- It does not call registered external APIs from MCP tools.
- It does not invoke Codex subagents from MCP tools.
- It does not silently enable audio, video extraction, OCR, or model narration routes.

## Recommended Use

- Capture only the screen, window, or region needed for the task.
- Prefer `max_width`, `max_height`, `scale`, and `context_policy="hold_file"` for context control.
- Use `preprocess="text"` for text-heavy screenshots before any OCR/model route.
- Use low-fps video experiments first, then raise fps only when motion detail is necessary.
- Keep API keys in environment variables, not files.
- Do not commit local captures, responses, ledgers, or account-console screenshots.
