# Safety

Screen Guardian is for authorized perception, accessibility, visibility auditing, debugging, and personal AI assistance.

## Safety Shape

The project does not pretend open-source code can technically prevent every misuse. Instead, it makes the intended use, unsupported use, default behavior, and side effects explicit.

## Defaults

Default behavior should stay conservative:

- save locally
- do not upload automatically
- do not call external APIs automatically
- do not call subagents automatically
- do not start hidden background monitors
- keep heavy media, OCR, webpage, model, and lab execution paths optional
- require explicit feature flags and confirmations for high-risk routes

## Anti-Abuse Position

The project is not designed or supported for bypassing authentication, paywalls, CAPTCHA, DRM, access controls, platform rules, privacy expectations, or other authorization boundaries.

This is a project stance and responsibility boundary, not a claim that forks or local modifications can be impossible.

## Screen Content Is Untrusted

Screen pixels, OCR text, webpage text, terminal output, UI labels, and model narrations are untrusted input. A receipt should help the AI reason about target, method, risk, side effect, and confidence before acting on observed content.

## Safety Acceptance

A new route should disclose:

- what it can observe
- where it stores output
- whether it changes focus or page state
- whether it calls a model, API, subagent, scheduler, or local command
- how it is bounded by feature flags and runtime limits
- how a user can disable or avoid it
