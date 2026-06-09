# Anti-Abuse And Disclaimer

Screen Guardian is built for authorized perception, accessibility, visibility auditing, debugging, and personal AI assistance. It helps users understand pages, screens, documents, and local workflows they are allowed to access.

Screen Guardian is not designed or supported for bypassing authentication, paywalls, CAPTCHA, DRM, access controls, rate limits, platform rules, privacy expectations, or other authorization boundaries. It is also not designed or supported for deceptive automation, bulk privacy-invasive collection, hidden data extraction, or unauthorized access to third-party systems.

Open source code can be modified, forked, or recombined by others. The maintainers cannot claim to prevent every misuse of modified code. Misuse, modified forks, or downstream combinations do not represent the project's purpose, maintainer position, or support scope.

Users are responsible for confirming that their use complies with applicable law, site terms, platform policies, data authorization requirements, and organizational rules. When a page, document, account console, or media file is sensitive, users should prefer local-only processing, minimal capture scope, and explicit review before sharing outputs with any model or third party.

This project is provided as-is. It is not legal, security, compliance, medical, financial, or other professional advice. Reports about misuse risk, privacy issues, permission boundaries, or security defects are welcome.

## Policy Posture

Screen Guardian should avoid regex-based or focus-state-based moral judgment. High-context situations cannot be reliably classified by window title, process name, URL fragment, focus state, or simple text patterns alone.

Hard runtime boundaries should be reserved for objective engineering constraints: disabled feature flags, runtime limits, configured cache ownership, explicit local-only behavior, missing dependencies, and actions that would require a separate caller such as API execution, subagent invocation, local command execution, or background scheduling.

Break-glass local execution is an explicit exception path, not an ordinary workflow. `guardian_run_exec` can run local code only after persistent `raw_local_exec` enablement and per-call user confirmation. Modified downstream uses or attempts to turn raw execution into hidden automation are outside the project's intended support posture.

For high-context or potentially sensitive situations, the preferred behavior is advisory rather than coercive:

- mark the capture or envelope with context metadata
- recommend `hold_file` or local-only processing
- ask for explicit user confirmation before sharing with a model or third party
- explain that a use case is outside the project's purpose or support scope
- avoid adding docs, examples, or maintenance support for bypass or unauthorized use

The project stance should not become a fragile denylist that blocks legitimate user workflows. It should make the default behavior responsible while preserving user control.
