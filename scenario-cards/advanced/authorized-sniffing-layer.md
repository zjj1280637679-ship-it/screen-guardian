# Authorized Sniffing Layer

## User Situation

The user says the AI can work much more efficiently when explicitly authorized, and asks Screen Guardian to add that capability to the sniffing layer. The AI must decide whether to use visual capture, browser-session readonly DOM, nested-scroll capture, document-to-markdown conversion, page export, readonly API access, database reads, or registry reads.

## External Conditions

- The user may be looking at an authenticated browser page.
- The task may involve documents, images, cloud-console tables, export buttons, APIs, or local system state.
- The user may grant broad language such as "full rights", but the tool still needs scoped route boundaries.
- Efficient data routes can be sensitive even when they are readonly.

## Recommended Route

Start with `guardian_sniff_context`.

Use inputs such as:

- `authorization_level`
- `declared_permissions`
- `target.kind`
- `target.url`
- `target.selector`
- `file_paths`
- `include_sensitive_routes`

The sniffer returns ranked route candidates. It does not execute any route.

## Guard Strategy

- Report `capture_performed=false`.
- Report `secret_storage_read=false`.
- Report `database_or_registry_touched=false`.
- Report `network_request_performed=false`.
- Treat MarkItDown-style conversion as a file-conversion route, not a browser-session secret route.
- Mark export/API/database/registry routes as confirmation- or scope-required.
- Never infer database or registry permission from ordinary webpage visibility.

## Context Budget

Keep the sniff result structured and short. Save long documents, screenshots, and exports as hold-file artifacts only after a later authorized execution step.

## Risks And Fallback Paths

- Broad user language can be misread as permission for unrelated data sources.
- A browser-session route can be confused with headless URL capture.
- A document conversion route can be confused with credential or browser storage access.
- Database and registry reads can reveal unrelated sensitive data.

Fallbacks:

- Downgrade to `L0_visual_only`.
- Ask for explicit endpoint, key, selector, file path, or export confirmation.
- Use `guardian_capture_targets` when the concrete visual target is still unknown.
- Use `prepare_capture_chain` when a later multi-step execution plan is needed.

## Acceptance Checks

- The output contains ranked `route_candidates`.
- The output states that no screenshot, navigation, storage read, database query, registry read, upload, model call, or background monitor occurred.
- Sensitive routes require explicit scope and confirmation.
- File paths are classified by metadata/extension only.
- The recommended route labels do not misrepresent browser-session capture as headless URL capture, visible bbox capture as strict background capture, or document conversion as credential access.

## Related Whitepaper Claims

- Desktop situation index
- Webpage nested scroll
- Screen content is untrusted
- Review decomposition
- Capability boundaries
