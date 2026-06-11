# Scenario: High-Intensity User Workflow

## User Situation

An advanced user wants the AI to observe multiple programs, hold evidence files, prepare model or decision envelopes, and avoid slowing the main AI with unnecessary images.

## External Conditions

- Many targets may change quickly.
- Some routes are optional or inactive.
- The user may have external model/API quota, but does not want hidden calls.
- Capture, narration, and decision logic can consume CPU, storage, context, and API budget.

## Desired Effect

The AI builds a bounded workflow that uses cheap status signals first and expands only selected evidence.

## Recommended Route

Use:

- `guardian_survey_windows` for status
- `list_capture_routes` for route choice
- `guardian_perceive` for selected captures
- `guardian_prepare_workflow` for local envelopes
- `prepare_capture_chain` for guided, conditional plans

## Guard And Budget

- Keep high-cost routes optional.
- Prefer hold-file paths before model narration.
- Use runtime limits and feature flags.
- Treat monitor profiles as declarative until a scheduler explicitly consumes them.

## Failure Branches

- Budget near exhaustion: downgrade to status-only or hold-file.
- Ambiguous targets: require stable ids such as HWND or exact selectors.
- Optional adapter missing: prepare the envelope but do not fake execution.

## Acceptance Checks

- No hidden upload, subagent call, API call, local command, or background scheduler occurs.
- The workflow can be resumed from saved local envelopes and metadata.
- Each high-cost step has a receipt or prepared request file.

## Related Claims

- perception subscriptions
- budget and auto-downgrade
- workflow envelopes
- optional heavy capability paths
