# Traceability

Traceability keeps the knowledge layout from drifting away from the runtime.

It connects:

```text
whitepaper claim
  -> scenario card
  -> acceptance condition
  -> runtime mechanism
  -> receipt fields and failure states
  -> validation or smoke evidence
```

## Files

- [whitepaper-scenario-map.yml](whitepaper-scenario-map.yml) is the first machine-readable map.

The map is intentionally still lightweight, but each claim should include more than file paths when the information is known: acceptance conditions, side effects, feature flags, failure states, and receipt fields.

## Rules

- Do not treat prose as proof of runtime behavior.
- Do not treat one successful screenshot as proof that all capture routes work.
- Keep causal strength calibrated: possible cause, contributing cause, necessary condition, sufficient condition, and unique cause are different claims.
- Preserve conflicts until a narrower test resolves them.
- Map high-risk routes to explicit feature flags, runtime limits, and receipt fields.

## Desired Future Checks

Future validation can check that:

- every scenario card links to at least one whitepaper chapter
- every scenario card has acceptance checks
- every high-risk runtime action has a scenario or safety rationale
- every receipt verdict appears in documentation
- every optional capability has an inactive-default statement
