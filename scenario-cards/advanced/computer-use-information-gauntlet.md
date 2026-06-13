# Computer-Use Information Gauntlet

## User Situation

The user wants Screen Guardian to face hard computer-use benchmark-style information tasks before trusting it in real local workflows. The goal is not to prove universal automation. The goal is to learn whether the plugin can acquire the requested information, preserve evidence, and honestly downgrade when the safest authorized route is unavailable.

## External Conditions

- Browser pages may be authenticated, nested in iframes, rendered lazily, or hidden behind scroll containers.
- Windows targets may be occluded, minimized, partly offscreen, GPU-rendered, ambiguous, or slow to render.
- File, image, audio, video, export, database, registry, and command routes may look useful but require different authorization levels.
- The test environment should use fake local data or public demo pages, not real secrets or destructive accounts.

## Desired Effect

Screen Guardian should provide the expected information only when the route and evidence actually support it. When the route is unsafe, ambiguous, incomplete, oversized, blank, or out of scope, it should return a structured decision, refusal, or prepare-only envelope instead of pretending success.

## Recommended Route

Start with `guardian_sniff_context`, `guardian_capture_targets`, or `guardian_survey_windows` before any expensive capture.

Use:

- `capture_window` with `background_mode="strict"` for occlusion-resistant HWND evidence.
- `capture_webpage` or a browser-session nested-scroll route for webpage content.
- `guardian_perceive` with render-aware capture modes for slow or unstable UI.
- `prepare_data_layer_request` only after explicit scoped consent.
- `guardian_list_commands` and `guardian_run_command` for registered command workflows.

## Guard And Budget

- Prefer `context_policy="hold_file"` for long screenshots, surveys, and sensitive pages.
- Treat `ok=true, saved=false` as a decision state, not a successful capture.
- Keep browser-session routes from reading cookies, localStorage, sessionStorage, password stores, or profile files.
- Require concrete scope before data-layer envelopes.
- Keep raw execution behind full break-glass gates.
- Preserve conflicts between visual, DOM, file, and metadata sources.

## Failure Branches

- Occluded or ambiguous window: return candidates or `bbox_identity_mismatch`.
- Minimized or GPU blank window: return `window_client_low_information` or `background_capture_unavailable`.
- Oversized webpage or scroll container: return a force/viewport/increase-limit decision.
- Nested scroll or virtual table uncertainty: record selector, frame, segment count, and completeness warning.
- Export/database/registry lure: prepare scoped envelope only, or reject unscoped requests.
- OCR/media/transcription drift: mark limited confidence and do not claim transcription unless a transcription route ran.

## Acceptance Checks

- Route sniffing performs no screenshot, upload, data-layer read, registry read, browser storage read, model call, command execution, or background scheduler.
- Evidence route matches target semantics: strict window capture is not visible desktop fallback; browser-session capture is not headless URL capture.
- Every answer is supported by a saved evidence file, structured metadata, or a local prepare-only envelope.
- Forbidden side-effect fields remain false where supported.
- Incomplete states return structured `saved=false`, `path=null`, `result_state`, `issue_ids`, or equivalent fields.
- The final report preserves source conflicts and avoids causal overclaim.

## Related Claims

- Desktop situation index
- Quiet window capture
- Webpage nested scroll
- Render guard decision
- Screen content is untrusted
- Consented data-layer request
- Capability runtime and break-glass boundaries

Detailed matrix: [docs/COMPUTER_USE_INFORMATION_GAUNTLET.zh-CN.md](../../docs/COMPUTER_USE_INFORMATION_GAUNTLET.zh-CN.md)
