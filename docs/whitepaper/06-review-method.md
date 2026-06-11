# Review Method

Screen Guardian uses narrow review topics instead of broad undifferentiated review tasks.

This reduces waiting time, avoids agent drift, and keeps causal claims calibrated.

## Topic Separation

Every review question should name one topic and one expected output.

Good topics:

- route-selection coverage
- render-guard acceptance checks
- traceability field completeness
- encoding path coverage
- quiet-window side effects
- untrusted screen-content handling

Poor topics:

- review the whole project
- check everything
- make the docs better
- analyze all safety issues

## Goal-Misalignment Check

Each topic should state the target goal and the non-goal.

Example:

```text
Topic: traceability field completeness
Goal: check whether each claim has acceptance conditions, side effects, feature flags, receipt fields, and failure states.
Non-goal: rewrite the whitepaper or judge runtime correctness.
Output: missing fields only.
```

Goal-misalignment checks prevent a reviewer from solving a different problem than the one blocking the next step.

## Evidence Separation

Keep evidence paths separate:

- common engineering expectation
- repository text
- runtime code
- validation output
- smoke behavior
- visual inspection

Agreement across paths is convergence. It is not automatically proof of a single cause.

## Causal Downgrade

When evidence is incomplete, use weaker claims:

- co-occurs with
- is related to
- may contribute to
- is a likely contributing cause
- is a necessary condition
- is a sufficient condition
- is the unique cause

Do not upgrade a weak claim just because multiple broad signals feel consistent.

## Minimum Validation Action

Every finding should end with the smallest next check or patch that would reduce uncertainty.

Examples:

- add one scenario card
- add one acceptance condition
- add one validation term
- run one encoding check
- run one smoke path
- inspect one receipt field

## Subagent Task Shape

Subagents should receive narrow prompts:

```text
Inspect only file X and file Y.
Do not edit files.
Answer whether condition Z is true.
If false, name the exact missing item.
Keep under 10 bullets.
```

If a subagent exceeds the waiting budget, the main agent should downgrade the result to unavailable, continue with local evidence, and optionally re-split the question into smaller tasks.
