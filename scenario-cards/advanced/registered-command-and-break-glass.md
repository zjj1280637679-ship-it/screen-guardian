# Registered Command And Break-Glass

## User Situation

The user wants Screen Guardian to offer reusable commands so the AI does not guess long tool chains, but raw local execution must remain an explicit break-glass path.

## External Conditions

- `guardian_list_commands` and `guardian_run_command` are advanced-surface tools.
- Normal registered commands can prepare envelopes, inspect readiness, or run bounded perception workflows.
- Emergency commands can prepare or run local code, so they require the `full` tool surface.
- `guardian_run_exec` still requires persistent `raw_local_exec=true` and per-call `user_confirmed=true`.

## Recommended Route

Use `guardian_list_commands` for normal reusable workflows. Use `guardian_run_command` only with a known `command_id` from that catalog.

For break-glass execution, switch intentionally to the `full` surface and use `guardian_prepare_exec` or `guardian_run_exec` directly. Do not rely on `guardian_run_command` as an indirect path.

## Guard Strategy

- Hide `emergency.*` commands from the default advanced command catalog.
- Mark emergency commands inactive unless `SCREEN_GUARDIAN_TOOL_SURFACE=full`.
- Keep raw execution disabled until `raw_local_exec=true`.
- Require `user_confirmed=true` on every raw execution call.
- Write an audit record for prepared and executed break-glass paths.

## Context Budget

Return compact command records by default. Include disabled or emergency commands only when the caller explicitly asks for that category or runs on the full surface.

## Risks And Fallback Paths

- A command catalog can become an accidental bypass if command entries ignore the tool surface.
- A prepared execution envelope can be mistaken for executed code.
- A feature flag can be mistaken for per-call user confirmation.

Fallbacks:

- Use direct low-level tools instead of adding a command entry.
- Prepare an envelope without running it.
- Reject command execution and return the required surface or feature flag.

## Acceptance Checks

- On the advanced surface, `guardian_list_commands` does not show `emergency.exec.prepare` or `emergency.exec.run` by default.
- On the advanced surface, `guardian_run_command` rejects `emergency.exec.prepare` and reports the required `full` surface.
- On the full surface, emergency commands are still gated by `raw_local_exec` and `user_confirmed=true`.
- `guardian_run_command` never accepts arbitrary code strings as a substitute for `command_id`.

## Related Whitepaper Claims

- Capability boundaries
- No hidden scheduler
- Screen content is untrusted
- Local-first artifact handling
