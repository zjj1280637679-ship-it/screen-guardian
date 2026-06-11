# Scenario: Beginner User First Run

## User Situation

A non-expert user wants the AI to see the screen, but does not know which adapter, display index, window handle, cache path, or feature flag matters.

## External Conditions

- The system may have missing Python dependencies.
- MCP tool exposure may be stale or delayed.
- The user may only know that "screenshot does not work."

## Desired Effect

The AI gives a short diagnosis and one safe next step instead of exposing the whole expert tool surface.

## Recommended Route

Start with `guardian_check`:

```json
{
  "detail": "short"
}
```

Then use `guardian_perceive` only if readiness is acceptable.

## Guard And Budget

- Keep output short.
- Do not enable advanced tools unless needed.
- Prefer core capture and local diagnostics.
- Avoid raw local execution.

## Failure Branches

- Python path mismatch: report active root, candidate failures, and preferred runtime variable.
- Dependencies missing: report install hints.
- Tool not exposed: suggest plugin reload or MCP surface diagnosis.

## Acceptance Checks

- The first response does not require the user to understand all 40-plus tools.
- The next action is a single concrete command or tool call.
- The AI preserves causal uncertainty when evidence is incomplete.

## Related Claims

- AI-first facade
- compatibility fallback
- bounded diagnosis
- causal downgrade
