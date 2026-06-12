# AI-First Interface

Screen Guardian exposes many low-level tools because compatibility work needs escape hatches. That is useful for experts, but it can make an AI agent spend too much context deciding between similar capture, preprocessing, storage, and envelope paths.

The AI-first interface adds a small set of intent tools that should be tried before the expert tool surface:

| Intent | Start with |
| --- | --- |
| Check whether the plugin can run | `guardian_check` |
| See what can be captured before taking a screenshot | `guardian_capture_targets` |
| Look at the screen, text, UI, a window, or a short change | `guardian_perceive` |
| Survey many program windows without flooding context | `guardian_survey_windows` |
| Prepare a model, decision, or monitor envelope | `guardian_prepare_workflow` |
| Choose desktop/application/webpage capture routes | `list_capture_routes` |
| Prepare conditional capture chains | `prepare_capture_chain` |

These tools are wrappers. They do not remove or replace the existing tools, and they do not expand permission, runtime, feature-flag, upload, model-call, subagent, or background-monitor behavior.

## Intuitive Scenarios

| Scenario | AI-first call | What it maps to |
| --- | --- | --- |
| Choose a capture target before screenshot | `guardian_capture_targets` | A local target index for displays, application windows, and explicit webpage URLs; no capture is performed |
| Quick look | `guardian_perceive` with `task="quick_look"` | A normal local screen or region capture |
| Read text screenshot | `guardian_perceive` with `task="read_text"` | Capture plus `preprocess="text"` and local image analysis; this is text-friendly image handling, not bundled OCR |
| Debug UI | `guardian_perceive` with `task="debug_ui"` | Capture plus UI sharpening and local image analysis |
| Capture a program window | `guardian_perceive` with `task="capture_window"` | Existing `capture_window` behavior and ambiguity rules |
| Report all program windows | `guardian_survey_windows` with `capture_mode="status_only"` | Window title/process/bounds/status report with optional visibility sampling, no screenshot write |
| Save selected window evidence | `guardian_survey_windows` with `capture_mode="hold_file"` | Bounded quiet window captures saved as marked local files for later selective review |
| Short change watch | `guardian_perceive` with `task="watch_change"` | Existing bounded `watch_screen` behavior and runtime limits |
| Hold file out of context | `guardian_perceive` with `task="hold_file"` or `context_budget="hold_file"` | Local save with `context_policy="hold_file"` and `marked_file_only=true` |
| Fast capture | Omit `capture_modes` or pass `capture_modes=["fast"]` | Direct screenshot with no extra strategy wait |
| Delayed capture | `capture_modes=["delay"]` plus optional `delay_seconds` | Wait before capture, bounded by runtime limits |
| Render-complete capture | `capture_modes=["wait_render"]` | Retry clearly blank frames before saving |
| Buffer/stability capture | `capture_modes=["wait_buffer"]` | Wait until consecutive local samples look visually stable before the final screenshot |
| Error-signal capture | `capture_modes=["wait_error"]` plus an error title/process signal | Wait for an explicit error-window signal, then capture the original target or matching error window |
| Suspected-unrendered protection | Window capture with `render_guard="wait"` or `render_guard="warn"` | Auto-wait for a nonblank frame or return decision actions: force now, capture later, or auto-wait |
| Choose a quiet webpage route | `list_capture_routes` | Compare desktop, application, webpage, `nested_scroll`, and mixed routes before capturing |
| Prepare a guided screenshot sequence | `prepare_capture_chain` | Write a local capture-chain envelope for delay, selector-visible, error-text, change, model-feature, or custom triggers |

Window capture is quiet-preferred by default. The plugin does not activate or raise the target window. If a window capture needs visible-screen bbox fallback, it probes whether sampled visible pixels appear to belong to the requested HWND. If another topmost window appears to cover the bbox, saving is deferred so the caller can retry with HWND/exact title, bring the window forward, or explicitly set `allow_unverified_bbox_fallback=true` as a last resort.

When occlusion-resistant background acquisition matters, call `guardian_capture_targets` first and then use the returned `capture_target.primary` arguments. They default to `background_mode="strict"`, which attempts direct HWND graphics without visible-screen bbox fallback. If direct HWND pixels are blank, protected, or GPU-only, the capture returns `background_capture_unavailable` as a decision state rather than saving visible desktop pixels. Switch to a `capture_webpage` URL route for browser pages when possible, or explicitly choose `background_mode="visible_fallback"` when visible-screen behavior is acceptable.

`guardian_survey_windows` is the batch version of that strategy. It does not start a monitor, upload images, or call a model. It first returns a window-status report. If captures are requested, `window_survey_window_count_max` and `window_survey_capture_count_max` limit how many windows can be reported or saved in one call, and per-call limits can only tighten those bounds.

`capture_modes` are stackable. For example, `["delay","wait_render","wait_buffer"]` waits a fixed delay, retries blank render frames, then waits for visual stability before saving. `wait_error` is intentionally narrow in the ultra-light core: it detects explicit window-title/process signals such as an error dialog. OCR, DOM, log, or model-detected errors should use future semantic routes or `prepare_capture_chain`/monitor envelopes.

`read_text` keeps its name for compatibility with existing callers. In the current ultra-light core it returns a sharpened text-oriented image and `text_handling.ocr_available=false`; actual OCR remains a future route or external model handoff.

## Context Budget Defaults

| Budget | Behavior |
| --- | --- |
| `low` | Save at up to 960 px wide for fast visual triage |
| `normal` | Save at up to 1440 px wide |
| `high` | Do not add an extra facade downscale |
| `hold_file` | Save and mark the file without asking the AI to ingest it immediately |

For `guardian_survey_windows`, `low` defaults to smaller 640 px-wide saved captures and `normal` defaults to 960 px-wide saved captures, because batch evidence is meant for selective review rather than immediate full-resolution reading.

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
