# Verification

Screen Guardian treats design claims as contracts.

## Acceptance Conditions

A feature should not become a default AI-facing path unless it:

- returns structured receipts
- distinguishes handled calls from saved files
- reports target, route, side effects, and risks
- has a bounded failure mode
- can be disabled without slowing unrelated core paths
- avoids hidden upload, hidden scheduling, and hidden model calls
- treats extracted screen, page, and OCR text as untrusted input
- can be checked by contract validation or a realistic smoke path

## Evidence Types

Use multiple evidence paths and keep causal strength calibrated:

- general engineering expectation
- related products and projects
- repository code and tool wiring
- real Windows smoke behavior
- actual screenshots or visual inspection

Agreement across paths is convergence, not proof of a single cause. Conflicts should be preserved until a narrower test resolves them.

## Current Checks

Current repository checks include:

- `npm run check:encoding`
- `npm run validate`
- `npm run stress`
- `npm run smoke:windows`
- `npm run evaluate`

Validation proves contract alignment. Smoke tests prove selected local behavior. Neither proves every future optional adapter.

## Traceability Target

Every important claim should map forward and backward:

```text
whitepaper claim
  -> scenario card
  -> acceptance condition
  -> test or smoke path
  -> runtime mechanism
  -> machine-readable receipt field
```
