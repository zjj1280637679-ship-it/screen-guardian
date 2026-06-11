# Whitepaper Chapter Map

This directory is the AI-first chapter map for the Screen Guardian whitepaper.

The canonical long-form paper remains in [../WHITEPAPER.md](../WHITEPAPER.md). This chapter map makes the paper easier to quote, test, and connect to scenario cards, reference source, optimized runtime code, and traceability files.

## Chapter Tree

| Chapter | File | Purpose |
| --- | --- | --- |
| Philosophy | [01-philosophy.md](01-philosophy.md) | Why compatibility-first local perception exists. |
| Usage | [02-usage.md](02-usage.md) | How AI agents and users enter the tool surface. |
| Design | [03-design.md](03-design.md) | How routes, guards, receipts, budgets, and envelopes fit together. |
| Verification | [04-verification.md](04-verification.md) | How claims become acceptance conditions and tests. |
| Safety | [05-safety.md](05-safety.md) | How local-only defaults, anti-abuse stance, and side-effect reporting bound the system. |
| Review Method | [06-review-method.md](06-review-method.md) | How topic separation, goal-misalignment checks, and minimum validation actions keep reviews small. |

The full posture is also documented in [../ANTI_ABUSE.md](../ANTI_ABUSE.md), [../../SECURITY.md](../../SECURITY.md), and the safety model section of [../WHITEPAPER.md](../WHITEPAPER.md).

## Relationship To The Repository

Screen Guardian keeps two compatible structures:

- Standard GitHub engineering layout for installation, testing, review, and release.
- AI-first knowledge layout for reasoning, scenario coverage, reference implementation, optimized runtime mapping, and traceability.

The knowledge layout is not a replacement for the runtime. It is a second entrance for agents and maintainers who need to understand why a tool exists before choosing how to call it.

## Traceability

Every important whitepaper claim should eventually connect to:

- one or more scenario cards under `scenario-cards/`
- one or more acceptance checks under `docs/VALIDATION.md`, smoke tests, or future test files
- one or more runtime mechanisms under `mcp/` or `scripts/`
- one receipt field or decision state that an AI can use without guessing
