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
- AI-first facade tools are wired and map to the intended status, perception, and envelope paths
- capability-runtime tools are wired, registered commands map through the command catalog, and break-glass execution is feature-flagged plus confirmation-gated
- every feature flag has a feature-catalog entry
- design principles are represented in docs and skill guidance
- tool layers are represented as core tools, local control tools, and experimental envelope tools
- concrete scenarios such as older Windows fallback, context control, text screenshots, web/program/error/model triggers, audio, video, storage, bounded watch, and decision routing are covered
- delayed capture, render-complete retry, and suspected-unrendered guard controls are covered as timing safeguards for slow or older systems
- safety boundaries are documented, including local-only defaults, no automatic uploads, no arbitrary decision-code execution, and no hidden scheduler
- anti-abuse and disclaimer language is present for unsupported bypass or unauthorized-use scenarios
- text files are valid UTF-8, README command examples stay ASCII-only, and common mojibake patterns are rejected

You can run the encoding guard directly:

```powershell
npm run check:encoding
```

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

The stress test also calls `guardian_check` and `guardian_prepare_workflow` so the AI-first facade is covered without performing real capture.

It also calls `guardian_list_commands`, `guardian_run_command`, and `guardian_prepare_exec`. Stress does not run raw local code.

## Runtime Evaluation

Run:

```powershell
npm run evaluate
```

This is a product-health evaluation for the AI-first runtime surface. It checks that the AI-first tools and capability-runtime tools are present, that registered commands are discoverable, that the readiness command runs, that workflow and break-glass envelopes are local-only, and that raw local execution remains disabled by default and confirmation-gated after persistent enablement.

The evaluator uses a temporary `APPDATA` directory and temporary output directory. It does not capture the screen, record audio, call external APIs, invoke subagents, or start background monitors unless you explicitly add the optional capture flag:

```powershell
python scripts/evaluate_runtime.py --include-capture
```

For a machine-readable report:

```powershell
python scripts/evaluate_runtime.py --output .tmp/evaluation-report.json
```

See `docs/EVALUATION.md` for measurement scope and interpretation.

## Windows Smoke Test

Run:

```powershell
python scripts/windows_smoke_test.py
```

or:

```powershell
npm run smoke:windows
```

If npm prints `npm warn Unknown env config "python"`, the smoke result is still valid when the command exits successfully. That warning comes from npm's own config handling. Prefer `SCREEN_GUARDIAN_PYTHON` rather than npm's `python` config when pinning Screen Guardian's runtime.

The smoke test uses the MCP server, so it exercises Python runtime discovery instead of importing the capture script directly. It checks:

- explicit `SCREEN_GUARDIAN_PYTHON`
- fallback from a broken Python candidate to a working candidate
- explicit `SCREEN_GUARDIAN_CAPTURE_SCRIPT`
- `check_dependencies`
- `list_displays`
- `list_windows`
- a tiny `capture_region` when the screen adapter is available
- break-glass raw execution stays disabled by default, requires per-call confirmation after enablement, and can run a harmless Python snippet in an isolated config

This is a behavior smoke test for a local Windows machine. It may skip the tiny capture when optional screenshot dependencies are missing, but Python discovery and the MCP tool path must still work.

If `bin/screen-guardian-helper.exe` exists, smoke runs through that helper first. Otherwise it exercises the Python/script fallback path.

## Interpretation

A passing validation means the current public design is internally consistent and the lightweight MCP contract can survive repeated interface calls. It does not prove that every future adapter is implemented; interface-only modules are intentionally validated as declarative contracts until an adapter is added. Use the Windows smoke test for local behavior coverage.

The validation script intentionally mixes structural checks with documentation coverage checks. Structural checks are strict; documentation checks use curated terms and should be updated when the project adds new docs, localized wording, or new capability families.
