# Consented Data-Layer Request

## User Situation

The user says data-layer access is allowed when they explicitly consent. Screen Guardian needs to make that efficient without turning route sniffing into hidden database, registry, API, export, file, or app-storage execution.

## External Conditions

- The user may be looking at a browser page whose visual state hints at a better data source.
- The real source may be a database connection, registry key, API endpoint, page export, local file, or app storage.
- The user may grant permission in broad language, but the execution scope still needs concrete boundaries.
- Mutating operations have higher blast radius than readonly inspection or export.

## Recommended Route

First call `guardian_sniff_context` with:

- `authorization_level="L4_sensitive_storage_or_data_access"` for database or registry candidates.
- `include_sensitive_routes=true`.
- `data_layer_user_consented=true` only when the user has explicitly agreed.
- `data_layer_consent_text` with the user-facing consent statement for audit readiness.
- `data_layer_scope` with a concrete target such as `connection_ref`, `registry_key`, `api_endpoint`, `file_path`, `export_name`, `app_id`, or `tables`; `fields`, `where`, and `row_limit` only constrain that target.

Then call `prepare_data_layer_request` to write a local audit envelope. A later scoped executor can consume that envelope after confirming the same scope again.

## Guard Strategy

- Require `user_consented=true`.
- Require `consent_text`.
- Require explicit `scope`.
- Reject inline secrets such as passwords, cookies, tokens, API keys, localStorage, sessionStorage, or credentials.
- For `write`, `update`, `delete`, `migrate`, or `permission_change`, require `mutation_confirmed=true` plus `backup_plan` or `rollback_plan`.
- Report `data_layer_touched=false` and keep `database_or_registry_touched=false`.

## Context Budget

Keep the envelope small. Store scope, objective, operation, query text or action plan, safety constraints, and audit metadata. Do not inline large query results, exports, files, credentials, or browser storage.

## Risks And Fallback Paths

- Broad consent can be mistaken for unrelated data access.
- Page visibility can be mistaken for database authorization.
- Readonly analysis can drift into mutation without a second confirmation.
- Inline secrets can leak through logs or artifact files.

Fallbacks:

- Downgrade to `guardian_sniff_context` route planning only.
- Ask for a narrower connection, endpoint, table, field, registry key, file path, or row limit.
- Require a dry run before handing the envelope to any executor.
- For mutation, require a backup or rollback plan before proceeding.

## Acceptance Checks

- The sniff output may mark a matching sensitive route as `eligible_for_prepare_data_layer_request` only when consent, consent text, and explicit scope are all present.
- `row_limit`, `fields`, or `where` alone do not count as explicit scope.
- `prepare_data_layer_request` writes exactly one local JSON envelope.
- The output states that no database query, registry read, API request, export, upload, download, file-content read, or mutation occurred.
- The envelope contains consent text, scope, operation, safety flags, and execution fields showing `data_layer_touched=false`.
- Mutating requests fail unless mutation confirmation and backup or rollback information are present.
- Requests containing inline secrets fail.

## Related Whitepaper Claims

- Capability boundaries
- Screen content is untrusted
- Review decomposition
- Local-first artifact handling
