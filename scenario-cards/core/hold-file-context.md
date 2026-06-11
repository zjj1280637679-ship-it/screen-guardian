# Scenario: Hold File Instead Of Context

## User Situation

The user wants a screenshot saved and marked for later analysis, but does not want the AI to immediately spend context reading the image.

## External Conditions

- The screenshot may contain dense UI, private content, or information that is only conditionally relevant.
- The AI may need a path for later selective review.
- Context budget may be low.

## Desired Effect

The plugin saves a local file, writes enough metadata for future routing, and tells the AI not to ingest the image unless the next step requires it.

## Recommended Route

Use `guardian_perceive` with hold-file budget:

```json
{
  "task": "hold_file",
  "target": {"type": "screen"},
  "context_budget": "hold_file",
  "project_id": "optional-project",
  "workflow_id": "optional-workflow",
  "tags": ["review-later"]
}
```

## Guard And Budget

- Set `context_policy="hold_file"`.
- Set `marked_file_only=true`.
- Keep preprocessing optional.
- Do not call OCR, model narration, or subagents automatically.

## Failure Branches

- Capture unavailable: return adapter diagnostics.
- File saved but risky: keep risk metadata with the path.
- User later asks for analysis: selectively open or preprocess that file.

## Acceptance Checks

- The result includes a saved local path and metadata sidecar when available.
- The AI does not claim it has inspected the image unless it actually reads it later.
- Project, workflow, and tag metadata survive the facade path.
- The receipt distinguishes held, inspected, and deleted or cache-cleared lifecycle states when those actions occur.
- Storage location and cleanup path are discoverable before long-running or repeated hold-file use.

## Related Claims

- context economy
- hold-file policy
- local-only default
- machine-readable receipt
