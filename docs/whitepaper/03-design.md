# Design

Screen Guardian treats screenshots as one channel inside a broader desktop perception system.

## Main Design Objects

| Object | Meaning |
| --- | --- |
| Target | Display, region, window, webpage, nested scroll area, file, or future semantic node. |
| Route | Desktop pixels, application/window capture, browser capture, nested-scroll capture, watch, or envelope. |
| Guard | Decision logic that saves, waits, warns, or defers a capture. |
| Receipt | Machine-readable result used by the AI as the next decision input. |
| Budget | Runtime, capture count, context, storage, API, and privacy bounds. |
| Envelope | Prepared local request for a model, decision, monitor, capture chain, or future adapter. |

## Capture Semantics

Screen Guardian distinguishes evidence capture from informational capture.

Evidence capture records the current observable state. A blank, loading, error, or crash state can be valid evidence.

Informational capture is meant to understand a completed interface. It should warn, wait, or return a decision state when the UI is unrendered, unstable, occluded, stale, or ambiguous.

## Guard Vocabulary

Current guard behavior includes:

- direct fast capture by default
- optional delay
- render-complete retry
- visual stability wait
- error-signal wait
- suspected-unrendered warning
- decision menu before saving questionable frames
- quiet window capture with visible-bbox fallback risk reporting

The default guard set should remain small. Additional checks can be enabled, disabled, or combined without becoming hard moral blockers.

## Runtime Boundaries

High-level AI-first tools must not widen privileges:

- no bypass of feature flags
- no bypass of runtime limits
- no automatic upload
- no automatic model call
- no hidden subagent call
- no hidden background scheduler
- no raw local execution unless persistent and per-call gates are both satisfied

## Reference And Runtime Split

The future reference source should be flat, annotated, and easy to audit.

The optimized runtime can stay compact and efficient, but it must remain traceable to the reference intent and whitepaper claims.
