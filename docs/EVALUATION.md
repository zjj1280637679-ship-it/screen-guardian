# Evaluation

Screen Guardian now has three complementary test layers:

| Layer | Command | Purpose |
| --- | --- | --- |
| Contract validation | `npm run validate` | Check docs, tool schemas, Python actions, feature flags, and safety wording stay aligned |
| Stress testing | `npm run stress` | Repeated MCP calls for decision, monitor, workflow, and command envelopes |
| Runtime evaluation | `npm run evaluate` | Measure the AI-first surface, command catalog, safety gates, and local envelope behavior |

Runtime evaluation is not a replacement for validation. It is a lightweight product-health check for the question: "Does this plugin reduce the main AI's burden while keeping powerful paths explicit and bounded?"

## What The Evaluator Measures

`scripts/evaluate_runtime.py` runs the MCP server through newline-delimited JSON-RPC and records:

- whether the AI-first tools are present
- whether the capability-runtime tools are present
- how many registered commands are available and active
- whether `guardian_check` gives a clear local status and next step
- whether `guardian_run_command` can run the registered readiness command
- whether `guardian_prepare_workflow` writes a local model-request envelope
- whether `guardian_prepare_exec` writes a break-glass envelope without executing code
- whether `guardian_run_exec` stays disabled by default
- whether `guardian_run_exec` still requires `user_confirmed=true` after persistent enablement
- whether a confirmed harmless Python snippet can run inside an isolated config
- per-call latency in milliseconds
- local artifact counts

The evaluator uses a temporary `APPDATA` directory and a temporary output directory. This keeps feature-flag changes and audit files isolated from the user's normal Screen Guardian configuration. On Windows it preserves `PYTHONUSERBASE` so `pip install --user` dependencies such as `mss` and Pillow remain discoverable while the Screen Guardian config stays isolated.

## Default Run

Run:

```powershell
npm run evaluate
```

The default run does not:

- capture the screen
- record audio
- invoke FFmpeg
- call external APIs
- call subagents
- start background monitors
- use the user's existing Screen Guardian config

It does test the confirmed raw-exec path, but only after enabling `raw_local_exec` in the temporary config and only with a harmless Python `print` snippet.

## Optional Tiny Capture

To include one small real perception call:

```powershell
python scripts/evaluate_runtime.py --include-capture
```

This calls `guardian_perceive` with a tiny region, `task="read_text"`, and `context_budget="hold_file"`. Use this only when a local screen capture is acceptable for the current test run.

## JSON Report

To save a machine-readable report:

```powershell
python scripts/evaluate_runtime.py --output .tmp/evaluation-report.json
```

The JSON report includes pass/fail checks, latency metrics, tool counts, command counts, artifact counts, and whether optional capture was enabled.

## Reading Results

A passing runtime evaluation means:

- the default AI-first entrypoints are callable
- the registered-command path is available
- envelope workflows are local-only
- raw local execution is still gated by persistent enablement and per-call confirmation
- the plugin can produce a compact measurement report without external services

It does not prove every optional adapter is installed or that every future visual model route works. External model, video narration, and high-volume visual tests should use separate experiment scripts so their quota, privacy, and failure modes are visible.
