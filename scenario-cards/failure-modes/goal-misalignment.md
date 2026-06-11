# Scenario: Goal Misalignment During Review

## User Situation

The user asks for an important project review or redesign, and the AI or subagent starts solving a broader or different problem than the current blocking question.

## External Conditions

- The project has many valid concerns: runtime behavior, GitHub structure, safety, scenario coverage, validation, and future compiler-like source splitting.
- A broad review prompt can create long waits and unfocused output.
- Multiple evidence paths may converge without proving the same cause.

## Desired Effect

The main AI keeps the review moving by splitting work into narrow topics and preserving the distinction between goal, non-goal, evidence, and causal strength.

## Recommended Route

Use a short review task shape:

```text
Topic: one bounded question
Goal: the claim to verify
Non-goal: what not to solve now
Evidence: files or tests to inspect
Output: missing items only
Minimum validation action: one next check
```

## Guard And Budget

- Prefer multiple small tasks over one broad task.
- Do not wait indefinitely for a non-blocking review.
- Treat timed-out subagent work as missing evidence, not as a negative finding.

## Failure Branches

- Subagent drifts into implementation: narrow the prompt or close the task.
- Findings use strong causality without evidence: downgrade the claim.
- Suggestions conflict with project goals: mark target mismatch and keep the current scope.

## Acceptance Checks

- Each delegated task has one topic, one goal, and one non-goal.
- Findings name their evidence source and causal grade when relevant.
- The main agent can continue local work while subagents run.
- A timed-out review is split into smaller checks instead of blocking the whole task.

## Related Claims

- topic separation
- goal-misalignment check
- causal downgrade
- minimum validation action
