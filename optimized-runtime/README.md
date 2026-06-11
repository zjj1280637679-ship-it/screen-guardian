# Optimized Runtime

This directory documents the optimized runtime layer.

The current production runtime remains in the normal project locations:

- `mcp/server.cjs`
- `scripts/screen_guardian_capture.py`

The code is not moved here because MCP configuration, plugin packaging, local cache recovery, validation scripts, and existing documentation already depend on those paths.

## Purpose

The optimized runtime layer should be:

- fast enough for local AI tool calls
- compatibility-first on constrained Windows machines
- light on required dependencies
- strict about feature flags and runtime limits
- traceable back to whitepaper claims and scenario-card needs

## Relationship To Reference Source

The long-term goal is not to manually maintain two unrelated codebases.

Target relationship:

```text
annotated reference source
  -> generated or reviewed optimized runtime
  -> equivalence checks
  -> release package
```

Current relationship:

```text
whitepaper and scenario cards
  -> production runtime in mcp/ and scripts/
  -> validation and smoke checks
```

## Runtime Mapping Rules

Every optimized runtime path should keep a visible mapping to:

- scenario card or whitepaper claim
- feature flag or runtime limit when applicable
- side effects
- receipt fields
- failure states
- validation or smoke coverage

The mapping currently lives under `traceability/`.
