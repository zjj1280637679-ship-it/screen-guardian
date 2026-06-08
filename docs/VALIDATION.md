# Validation And Stress Testing

Screen Guardian treats its design principles as contracts, not only prose. The repository includes a lightweight validation script that checks whether the public documentation, MCP tool surface, Python actions, feature flags, and safety boundaries still line up.

## Static Contract Validation

Run:

```powershell
python scripts/validate_contracts.py
```

This verifies:

- manifest, package, MCP server, and local MCP config consistency
- every expected MCP tool is declared
- every MCP tool has a `callTool` mapping
- every mapped Python action exists
- every feature flag has a feature-catalog entry
- design principles are represented in docs and skill guidance
- concrete scenarios such as older Windows fallback, context control, text screenshots, web/program/error/model triggers, audio, video, storage, bounded watch, and decision routing are covered
- safety boundaries are documented, including local-only defaults, no automatic uploads, no arbitrary decision-code execution, and no hidden scheduler

## Stress Test

Run:

```powershell
python scripts/validate_contracts.py --stress
```

The stress test sends repeated newline-delimited JSON-RPC calls through the MCP server. It registers temporary decision policies and monitor profiles, prepares decision and monitor envelopes, lists the temporary profiles, and removes them again.

Default stress size is 25 loops. Override it with:

```powershell
python scripts/validate_contracts.py --stress --stress-loops 100
```

The stress test writes temporary envelope files under the system temp directory and removes them automatically. It does not start background monitoring, capture the screen, record audio, call external APIs, or invoke subagents.

## Interpretation

A passing validation means the current public design is internally consistent and the lightweight MCP contract can survive repeated interface calls. It does not prove that every future adapter is implemented; interface-only modules are intentionally validated as declarative contracts until an adapter is added.
