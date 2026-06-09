# AI-First Interface

Screen Guardian exposes many low-level tools because compatibility work needs escape hatches. That is useful for experts, but it can make an AI agent spend too much context deciding between similar capture, preprocessing, storage, and envelope paths.

The AI-first interface adds three intent tools that should be tried before the expert tool surface:

| Intent | Start with |
| --- | --- |
| Check whether the plugin can run | `guardian_check` |
| Look at the screen, text, UI, a window, or a short change | `guardian_perceive` |
| Prepare a model, decision, or monitor envelope | `guardian_prepare_workflow` |
| Choose desktop/application/webpage capture routes | `list_capture_routes` |
| Prepare conditional capture chains | `prepare_capture_chain` |

These tools are wrappers. They do not remove or replace the existing tools, and they do not expand permission, runtime, feature-flag, upload, model-call, subagent, or background-monitor behavior.

## Intuitive Scenarios

| Scenario | AI-first call | What it maps to |
| --- | --- | --- |
| Quick look | `guardian_perceive` with `task="quick_look"` | A normal local screen or region capture |
| Read text screenshot | `guardian_perceive` with `task="read_text"` | Capture plus `preprocess="text"` and local image analysis |
| Debug UI | `guardian_perceive` with `task="debug_ui"` | Capture plus UI sharpening and local image analysis |
| Capture a program window | `guardian_perceive` with `task="capture_window"` | Existing `capture_window` behavior and ambiguity rules |
| Short change watch | `guardian_perceive` with `task="watch_change"` | Existing bounded `watch_screen` behavior and runtime limits |
| Hold file out of context | `guardian_perceive` with `task="hold_file"` or `context_budget="hold_file"` | Local save with `context_policy="hold_file"` and `marked_file_only=true` |
| Delayed capture | Any capture intent with `delay_seconds` | Wait before capture, bounded by runtime limits |
| Render-complete capture | Window capture with `wait_for_nonblank=true` | Retry clearly blank frames before saving |
| Suspected-unrendered protection | Window capture with `render_guard="wait"` or `render_guard="warn"` | Auto-wait for a nonblank frame or return decision actions: force now, capture later, or auto-wait |
| Choose a quiet webpage route | `list_capture_routes` | Compare desktop, application, webpage, `nested_scroll`, and mixed routes before capturing |
| Prepare a guided screenshot sequence | `prepare_capture_chain` | Write a local capture-chain envelope for delay, selector-visible, error-text, change, model-feature, or custom triggers |

Window capture is quiet-preferred by default. The plugin does not activate or raise the target window. If a window capture needs visible-screen bbox fallback, it returns a decision warning before saving so the caller can retry quietly, allow visible fallback, or ask the user to bring the window forward.

## Context Budget Defaults

| Budget | Behavior |
| --- | --- |
| `low` | Save at up to 960 px wide for fast visual triage |
| `normal` | Save at up to 1440 px wide |
| `high` | Do not add an extra facade downscale |
| `hold_file` | Save and mark the file without asking the AI to ingest it immediately |

## Workflow Preparation

`guardian_prepare_workflow` chooses the matching local envelope tool:

| Workflow type | Existing tool |
| --- | --- |
| `model_request` | `prepare_model_request` |
| `decision_request` | `prepare_decision_request` |
| `monitor_tick` | `prepare_monitor_tick` |
| `capture_chain` | `prepare_capture_chain` |

It writes local request files only. It does not call an API, invoke a Codex subagent, run a local command, record media, or start a scheduler.

## Expert Tools Still Matter

Use the low-level tools directly when the user explicitly needs exact adapter control, storage routes, feature flags, runtime limits, audio diagnostics, route registration, decision-policy registration, or monitor-profile registration.
