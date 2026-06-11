# Reference Source

This directory is the planned home for highly annotated, flat, human- and AI-readable reference source.

It does not replace the current runtime files:

- `mcp/server.cjs`
- `scripts/screen_guardian_capture.py`

Those files remain the production runtime today.

## Purpose

Reference source should act like executable whitepaper material:

- explain why each route exists
- keep state machines explicit
- keep guard decisions visible
- annotate side effects and budget boundaries
- avoid deep call chains when flat reading is more useful
- map concepts back to whitepaper chapters and scenario cards

## Authority Model

Current authority:

```text
runtime code + validation tests + docs
```

Target authority:

```text
whitepaper claim
  -> scenario card
  -> annotated reference source
  -> optimized runtime
  -> validation or smoke evidence
```

The reference source should become a readable specification, not a competing fork of the runtime. Until there is a compiler or equivalence checker, runtime code remains the executable source of truth.

## First Extraction Targets

Good candidates for future flat reference modules:

- AI-first facade routing
- capture route selection
- render guard state machine
- window identity and fallback decisions
- machine-readable receipt construction
- runtime limit and feature-flag policy
- capture-chain envelope preparation
