# Screen Guardian Whitepaper

## AI-First Desktop Perception

Screen Guardian is not just a screenshot helper. It is compatibility-first perception infrastructure for personal AI agents on Windows.

The central claim is simple: an AI should understand the local desktop situation before it spends context, changes focus, calls a model, or saves a screenshot.

Traditional screenshot tools assume a human already knows what to capture, why to capture it, when the target is ready, and whether the result is trustworthy. Screen Guardian assumes the opposite. An AI agent often does not know which windows, regions, pages, dialogs, terminals, browser tabs, or render states exist. It also does not know whether a capture is current, occluded, blank, stale, minimized, or relevant to the user's task.

Screen Guardian therefore treats screenshots as one observation channel inside a broader desktop perception layer.

## Roles

Screen Guardian has two users:

| Role | Meaning |
| --- | --- |
| Upstream user | The human who owns the computer, grants authority, and asks the AI for help. |
| Primary runtime user | The AI agent that calls tools, reads receipts, chooses routes, and manages context cost. |

The interface is optimized for the primary runtime user. Human-readable text still matters, but every important result should be machine-readable: target, method, verdict, saved path, risk, side effect, confidence, and recommended next action.

## Problem

AI desktop work fails when perception is treated as one raw `screenshot()` call.

Common failure modes:

- The AI does not know which screen, window, region, or page is relevant.
- A tool reports success while the saved pixels are blank, stale, occluded, or not the requested target.
- The AI repeatedly sends large screenshots or OCR output into context because it lacks a cheaper index.
- The AI uses long natural-language target descriptions that drift across turns.
- A foreground capture changes focus when a quiet route would have been enough.
- A quiet capture silently falls back to visible desktop pixels and may capture an overlapping window.
- A slow or older system produces a white or incomplete frame before the UI finishes rendering.
- Heavy features such as OCR, audio, video, model narration, or subagent handoff impose cost even when inactive.

The design goal is to move these decisions out of guesswork and into structured, bounded, local contracts.

## Core Thesis

Screen Guardian should give the AI a lightweight desktop situation index first, then let it expand only the evidence it needs.

In short:

```text
index first -> choose target -> choose observation channel -> apply guard policy -> return receipt
```

This is different from:

```text
capture first -> inspect image -> guess whether it was useful
```

The index lowers cognitive load. Target ids lower ambiguity. Guard policies lower misleading success. Receipts give the AI a reliable next-step input.

## Desktop Situation Index

A desktop situation index is a low-cost directory of observable local targets. It is not a screenshot, full OCR dump, full DOM snapshot, full UIA tree, terminal transcript, or model narration.

It should answer questions such as:

- Which displays exist?
- Which windows are visible, minimized, offscreen, or probably occluded?
- Which application or process owns a target?
- Which observation routes are available for a target?
- Which route is quiet, foreground, visible-pixel, webpage, or future semantic analysis?
- Which targets changed since the last turn?
- Which target looks risky, stale, ambiguous, or not ready?

Current Screen Guardian implements the beginning of this model through `guardian_check`, `list_displays`, `list_windows`, `guardian_survey_windows`, and `list_capture_routes`.

Future versions can extend the index with browser page state, tab identity, region catalogs, code panels, terminal tails, DOM hints, UIA summaries, or model-generated descriptions. Those routes should remain optional and cost-aware.

## Interface Topology

The AI should not treat the desktop as a flat list of pixels. It should reason over an interface topology:

```text
desktop
  display
    application
      top-level window
        page or tab
          panel, iframe, dialog, or nested scroll area
            region
              control, text, code, chart, input, or table cell
```

Each node can have a stable target id within a snapshot:

```json
{
  "snapshot_id": "desk_118",
  "target_id": "w03.p02.r01",
  "kind": "region",
  "title": "terminal panel",
  "parent": "w03.p02"
}
```

The current implementation exposes HWNDs, display ids, regions, window title/process metadata, and route descriptors. The target-id layer is a design direction for future richer index snapshots.

## Perception Depth

Not every task needs a screenshot. Screen Guardian should support increasing perception depth:

| Depth | Name | Description | Typical cost |
| --- | --- | --- | --- |
| S0 | `title_only` | Title, process, handle, rect, display, foreground/minimized/offscreen hints. | Very low |
| S1 | `structure` | Window tree, page or panel structure, major controls, route availability. | Low to medium |
| S2 | `text_preview` | Small text hints, error titles, button labels, terminal tail, page title, file name. | Medium |
| S3 | `semantic_analysis` | Local code/log/DOM/UIA analysis, summarized state, task relevance. | Medium to high |
| S4 | `pixel_analysis` | Screenshot, OCR, vision model, image narration, video frame or subagent interpretation. | High |

The default should be S0 plus selected S1/S2 hints. S3/S4 should be requested, subscribed to, or triggered by an explicit workflow because they spend more context, CPU, API quota, or privacy budget.

## Observation Channels

An observation channel is a way to inspect a target. It is not always a screenshot.

| Channel | Purpose | Side effect | Status |
| --- | --- | --- | --- |
| `title_read` | Read title/process/window metadata. | None | Current |
| `window_survey` | Report many windows without flooding context. | None unless captures requested | Current |
| `quiet_capture` | Capture a window without raising it. | Best effort; may have stale/GPU limitations | Current |
| `foreground_capture` | Capture after making a target visible or foreground. | Focus/visibility change | Partial, explicit strategy |
| `desktop_region` | Capture visible desktop pixels. | Captures what is visible, including occluders | Current |
| `render_guard` | Decide whether a capture is blank, stale, risky, or deferred. | None | Current |
| `watch_change` | Bounded foreground watch for visible changes. | Short active polling | Current |
| `full_surface` | Full page or nested scroll capture. | Browser adapter and possible scroll side effects | Optional |
| `uia_text` | Read UI text without image context. | Depends on UIA route | Future or external |
| `ocr` | Convert text-heavy image to text. | OCR cost and accuracy risk | Future route |
| `code_context` | Read code/log context directly. | File/tool access | Future route |
| `subagent_describe` | Ask another agent/model to summarize an image or media file. | Token/API/subagent cost | Envelope only |

Each channel should declare cost, side effect, risk, whether it is active, and whether it satisfies the current objective.

## Capture Semantics

Screen Guardian distinguishes two capture meanings.

### Evidence Capture

Evidence capture records the current raw UI state. A white screen, loading state, crash, error dialog, or half-rendered view can be valid evidence.

Success condition:

```text
the current observable state was captured and the receipt says how trustworthy it is
```

Use evidence capture for:

- documenting an error
- proving a blank page occurred
- recording a crash or loading state
- debugging the actual current UI
- keeping a local file for later analysis

### Informational Capture

Informational capture is meant to understand a completed UI. It should not silently succeed when the target is still loading, unstable, occluded, stale, or erroring.

Success condition:

```text
the target is sufficiently rendered, stable, and relevant for the intended interpretation
```

Use informational capture for:

- reading a final page
- checking a UI layout
- analyzing a chart
- verifying a rendered result
- comparing a finished design state

This distinction is why `render_guard`, `wait_render`, `wait_buffer`, `wait_error`, `capture_deferred`, `saved`, and `result_state` are part of the result contract.

## Guard Policies

A guard policy defines when a capture should be saved, deferred, or marked risky.

Recommended vocabulary:

| Guard | Meaning |
| --- | --- |
| `none` | Capture immediately. |
| `evidence` | Save the raw current state, even if blank or erroring, but report risks. |
| `stable` | Wait until sampled frames stop changing. |
| `render_ready` | Retry clearly blank or low-information frames. |
| `dom_ready` | Wait for a browser/page readiness signal. |
| `network_idle` | Wait for network quiet in a browser route. |
| `no_error` | Require no visible or parsed error signal. |
| `subagent_ok` | Let a model/subagent confirm readiness before saving. |
| `informational` | Require stable, rendered, relevant output for interpretation. |

Current Screen Guardian supports the implemented local subset through `render_guard`, `wait_for_nonblank`, `capture_modes`, `guard_checks`, and bounded watch behavior. Browser and semantic guards are future or optional route responsibilities.

## Low-Hamming-Distance Invocation

AI calls should avoid long natural-language target descriptions when a structured index exists.

Minimal pattern:

```json
{
  "target_id": "w03.p02",
  "capture_mode": "quiet",
  "guard_policy": "stable"
}
```

Expanded pattern:

```json
{
  "snapshot_id": "desk_118",
  "target_id": "w03.p02",
  "mode": "foreground",
  "guard": "informational",
  "timeout_ms": 8000,
  "fallback": "raw_evidence"
}
```

The current API still accepts HWNDs, titles, process names, display ids, and boxes. The design direction is to make richer target ids and snapshot ids available through future index snapshots so AI agents can avoid repeating fragile prose.

## Machine-Readable Receipts

Every observation should produce a receipt. A receipt is not just a log; it is the AI's next decision input.

Recommended shape:

```json
{
  "ok": true,
  "saved": true,
  "result_state": "saved",
  "verdict": "ok",
  "target_id": "w03.p02",
  "mode": "quiet",
  "guard": "render_ready",
  "evidence_ref": "cap_781",
  "path": "C:/Users/.../screen-guardian-window.png",
  "state": {
    "render_state": "stable",
    "occluded": false,
    "error_visible": false
  },
  "risks": [],
  "side_effects": [],
  "confidence": "high",
  "next_actions": []
}
```

Important verdicts:

- `ok`
- `usable_with_caution`
- `decision_required`
- `not_ready`
- `error_visible`
- `occluded_risk`
- `stale_frame_risk`
- `window_client_low_information`
- `bbox_identity_mismatch`
- `target_drift`
- `permission_required`
- `budget_exceeded`
- `failed`

Screen Guardian already applies this principle to capture results by separating `ok` from `saved`. A guard decision can return `ok=true` and `saved=false`; that means the tool handled the request and returned a decision menu, not that a file was created.

## Perception Subscriptions

Longer workflows should not repeatedly ask for expensive observations every turn. They should subscribe to targets and receive bounded summaries only when useful.

Subscription levels:

| Level | Description | Cost |
| --- | --- | --- |
| Basic | Title, process, bounds, minimized/offscreen/occlusion hints, route availability, small status hints. | Low |
| Local Analysis | Local CPU work such as code/log/DOM/UIA summaries, parser output, or structural change detection. | Medium |
| Agentic Interpretation | Vision, language, video, audio, subagent, or external API interpretation. | High |

Triggers:

- `on_turn`
- `on_change`
- `on_stable`
- `on_error`
- `on_focus`
- `on_render_ready`
- `on_network_idle`
- `on_interval`
- `on_task_relevant`

Current Screen Guardian implements declarative monitor profiles and `prepare_monitor_tick` envelopes. It does not silently start a background scheduler. Future schedulers or callers can consume those profiles under explicit runtime limits and feature flags.

## Budget And Auto-Downgrade

Perception needs budgets because desktop monitoring can spend CPU, storage, context, API quota, and privacy budget.

Budget dimensions:

- CPU time
- captures per task
- captures per hour
- OCR calls
- model or API calls
- subagent runs
- tokens or context bytes
- local storage
- maximum active subscriptions
- maximum high-cost routes

When a budget is close to exhaustion, Screen Guardian should prefer:

- downgrade high-cost subscriptions to Basic
- increase debounce or polling intervals
- push only error or change summaries
- hold files locally instead of loading them into context
- ask the AI or upstream user to confirm a higher-cost route

The current implementation exposes runtime limits, feature flags, hold-file policies, and inert envelopes as the foundation for this model.

## Safety Model

Screen Guardian is for authorized perception, accessibility, visibility auditing, debugging, and personal AI assistance.

Safety principles:

1. The upstream human user is the final authority.
2. The AI is the runtime caller, not the owner of the machine.
3. Screen, OCR, DOM, UIA, code, and webpage text are untrusted external content.
4. High-side-effect routes must declare side effects.
5. External API, model, and subagent routes must be explicit.
6. Sensitive targets need privacy gates.
7. Observation behavior should be auditable.

Sensitive content can include password managers, banking, payments, private chat, email, medical or financial information, `.env` files, SSH keys, company intranets, and private documents. The project cannot guarantee perfect content classification, so it uses explicit anti-abuse posture, local-only defaults, feature gates, and side-effect reporting rather than pretending regexes can solve high-context authorization questions.

## Current Implementation Map

| Whitepaper concept | Current Screen Guardian mechanism |
| --- | --- |
| Readiness check | `guardian_check`, `check_dependencies`, `list_adapters` |
| Desktop index | `list_displays`, `list_windows`, `guardian_survey_windows` |
| Route selection | `list_capture_routes` |
| Ordinary perception | `guardian_perceive` |
| Evidence file held out of context | `context_policy="hold_file"`, `marked_file_only=true` |
| Quiet window route | `capture_window`, `quiet_preferred` |
| Slow render protection | `render_guard`, `wait_for_nonblank`, `capture_modes=["wait_render"]` |
| Stability wait | `capture_modes=["wait_buffer"]` |
| Error signal wait | `capture_modes=["wait_error"]` |
| Bounded change observation | `watch_screen`, `guardian_perceive task="watch_change"` |
| Webpage/full surface route | Optional `webpage_capture`, `capture_webpage` |
| Guided chains | `prepare_capture_chain` |
| Subscription plans | `set_monitor_profile`, `prepare_monitor_tick` |
| Model or subagent handoff | Prepared envelopes, not automatic execution |
| Budget control | Runtime limits, feature flags, inactive-feature rules |
| Safety boundary | Local-only defaults, anti-abuse docs, no hidden scheduler/upload |

## Acceptance Conditions

A Screen Guardian feature should satisfy these conditions before it becomes part of the default AI-facing workflow:

- It returns structured receipts, not only prose.
- It distinguishes handled calls from saved files.
- It reports target, method, side effects, and risks.
- It can be disabled without slowing unrelated core capture paths.
- It avoids hidden upload, hidden scheduling, and hidden model calls.
- It treats extracted screen/page text as untrusted input.
- It provides a bounded failure mode and a next action.
- It keeps high-cost interpretation optional.
- It can be validated through contract tests and at least one realistic smoke path.

## Final Definition

Screen Guardian is an AI-facing desktop perception layer. It helps a personal AI discover what can be observed, choose the lowest-cost channel, capture only when needed, verify whether the result is trustworthy, and keep high-cost perception routes optional, auditable, and under user control.

