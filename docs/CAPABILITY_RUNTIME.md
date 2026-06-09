# AI Capability Runtime

Screen Guardian is evolving into a local-first AI capability runtime. Its normal job is not to make the main AI invent shell commands. Its job is to expose reusable, auditable, intent-shaped commands that reduce main-AI cognitive load and speed up useful outcomes.

The runtime has two paths:

| Path | Default | Use |
| --- | --- | --- |
| Registered commands | Enabled | Reusable commands such as readiness checks, quick perception, rendered window capture, hold-file capture, and workflow-envelope preparation |
| Break-glass local execution | Disabled | Explicit user-directed emergency Python, PowerShell, or Node execution |

## Registered Commands

Use `guardian_list_commands` to inspect the command catalog. Use `guardian_run_command` to run one registered command by `command_id`.

`guardian_run_command` does not accept arbitrary shell, Python, PowerShell, or Node code. It only maps registered command ids to existing Screen Guardian actions.

Example:

```json
{
  "command_id": "perceive.window.after_render",
  "args": {
    "target": {"title_contains": "Chrome"},
    "delay_seconds": 1,
    "context_budget": "hold_file"
  }
}
```

Initial command ids include:

| Command | Purpose |
| --- | --- |
| `diagnostic.readiness` | Summarize runtime, adapters, cache path, and active capabilities |
| `perceive.screen.quick` | Save a quick local screen capture |
| `perceive.region.text` | Capture and sharpen a text-heavy region |
| `perceive.window.after_render` | Capture a program window after render-ready retry |
| `perceive.change.popup` | Watch briefly for visible changes or popups |
| `artifact.hold_file` | Save and mark a file without immediate context ingestion |
| `workflow.model_request.prepare` | Prepare a local model-request envelope |
| `workflow.decision.prepare` | Prepare a local decision-request envelope |
| `emergency.exec.prepare` | Prepare a break-glass execution envelope without running code |
| `emergency.exec.run` | Run break-glass local code when explicitly enabled and confirmed |

## Break-Glass Execution

`guardian_prepare_exec` writes a local execution envelope. It does not execute code.

`guardian_run_exec` can execute Python, PowerShell, or Node code, but only when all of these are true:

- persistent feature flag `raw_local_exec` is enabled through `set_feature_flags`
- the specific call passes `user_confirmed=true`
- the execution has a bounded timeout
- stdout and stderr are truncated by runtime limits
- an audit JSONL record is written locally
- execution is foreground-only, with no background service or automatic retry

This is intentionally an escape hatch. It is useful for emergency repair, local diagnostics, or one-off user-directed automation. It is not the normal AI workflow path.

## Boundary

The runtime does not pretend that code execution is impossible. It makes execution explicit, visible, bounded, and auditable.

The normal path should stay registered-command first. The break-glass path should be used only when the user clearly asks for local code execution and accepts the responsibility for that run.
