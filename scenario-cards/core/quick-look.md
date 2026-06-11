# Scenario: Quick Look

## User Situation

The user wants the AI to see the current screen quickly without setting up a heavy workflow.

## External Conditions

- Local screen capture may be the only available visual fallback.
- The user may be on an older or constrained Windows system.
- The AI does not yet know which window or region matters.

## Desired Effect

The AI gets a low-cost visual orientation and a structured receipt.

## Recommended Route

Start with `guardian_check`, then use `guardian_perceive`:

```json
{
  "task": "quick_look",
  "target": {"type": "screen"},
  "context_budget": "low"
}
```

## Guard And Budget

- Use fast direct capture by default.
- Downscale for low context pressure.
- Do not run OCR, model narration, audio, video, webpage capture, or subagents.

## Failure Branches

- Adapter unavailable: return install hints and next diagnostic step.
- Capture saved but not useful: use region, window, or render guard next.
- User wants file only: repeat with `context_budget="hold_file"`.

## Acceptance Checks

- A local file is saved only when `saved=true` and `path` is present.
- Receipt includes adapter, display, capture box, saved size, and any risks.
- The AI can explain the next action without guessing from prose only.

## Related Claims

- AI-first default entry
- context economy
- local-only default
- machine-readable receipt
