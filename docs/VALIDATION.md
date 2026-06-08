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

Default stress size is 25 loops. The maximum accepted value is 200 loops so a typo cannot create an unbounded local run. Override it with:

```powershell
python scripts/validate_contracts.py --stress --stress-loops 100
```

The stress test writes temporary envelope files under the system temp directory and removes them automatically. It briefly writes and removes temporary `sg-stress-*` decision policies and monitor profiles to exercise the real MCP persistence path. It does not start background monitoring, capture the screen, record audio, call external APIs, or invoke subagents.

## Windows Smoke Test

Run:

```powershell
python scripts/windows_smoke_test.py
```

or:

```powershell
npm run smoke:windows
```

The smoke test uses the MCP server, so it exercises Python runtime discovery instead of importing the capture script directly. It checks:

- explicit `SCREEN_GUARDIAN_PYTHON`
- fallback from a broken Python candidate to a working candidate
- `check_dependencies`
- `list_displays`
- `list_windows`
- a tiny `capture_region` when the screen adapter is available

This is a behavior smoke test for a local Windows machine. It may skip the tiny capture when optional screenshot dependencies are missing, but Python discovery and the MCP tool path must still work.

## Interpretation

A passing validation means the current public design is internally consistent and the lightweight MCP contract can survive repeated interface calls. It does not prove that every future adapter is implemented; interface-only modules are intentionally validated as declarative contracts until an adapter is added. Use the Windows smoke test for local behavior coverage.

The validation script intentionally mixes structural checks with documentation coverage checks. Structural checks are strict; documentation checks use curated terms and should be updated when the project adds new docs, localized wording, or new capability families.
