# Local Target Range

The local target range is a deterministic browser test site for difficult Screen Guardian page-perception scenarios. It exists so real browser tests can run without real accounts, API calls, browser storage reads, databases, registries, or external network dependencies.

Run:

```powershell
npm run target-range
```

Then open:

```text
http://127.0.0.1:8765
```

For a quick server self-test:

```powershell
npm run target-range:check
```

## State Space

The target range is built around the state path used by `guardian_radar` and `guardian_extract_page_facts`:

```text
unknown_target
-> target_indexed
-> page_measured
-> radar_classified
-> region_segmented
-> value_danger_classified
-> facts_extracted
-> secret_fields_marked
-> redacted_answer_ready
```

The pages are intentionally awkward. A successful test should not only answer the page question; it should explain which state was reached and which states remain missing.

## Scenarios

| Scenario | URL | Purpose |
| --- | --- | --- |
| `nested-docs` | `/nested-docs` | SPA-like docs page where the body does not scroll but the main article lives in an inner scroll container. |
| `token-console` | `/token-console` | Token table mixed with key inputs, copy/export/delete buttons, and quota/group facts. |
| `delayed-render` | `/delayed-render` | Skeleton page that becomes answer-bearing only after a bounded delay. |
| `empty-doc` | `/empty-doc` | Document shell with navigation and title but no body content. |
| `virtual-table` | `/virtual-table` | Virtualized usage table where visible rows are only a sample of the logical table. |
| `iframe-scroll` | `/iframe-scroll` | Same-origin iframe with its own scroll root and endpoint facts inside the frame. |
| `overlay-obstruction` | `/overlay-obstruction` | Useful content behind a blocking modal with a risky confirm action. |
| `shadow-settings` | `/shadow-settings` | API settings inside an open Shadow DOM tree with a fake secret field. |

## Ground Truth

The server exposes a machine-readable manifest:

```text
/manifest.json
```

Each scenario also has a caller-supplied readonly observation fixture:

```text
/observation/<scenario-id>.json
```

These JSON fixtures are not a replacement for real Chrome/browser measurement. They provide stable ground truth for contract tests and for directly exercising `guardian_radar` or `guardian_extract_page_facts` without loading a browser.

## Safety

- Binds to `127.0.0.1` by default.
- Uses fake local-only secrets such as `sk-target-range-*`.
- Does not make outbound network requests.
- Does not require cookies, localStorage, sessionStorage, passwords, databases, registries, or real API tokens.
- Dangerous controls are inert HTML buttons unless a test intentionally clicks them.

## Recommended Manual Test

1. Start the server with `npm run target-range`.
2. Open `/manifest.json` and choose a scenario.
3. In Chrome, open the scenario URL.
4. Gather one readonly DOM observation: title, URL, viewport, document size, scrollables, headings, links, rows, controls, overlays, frames, and shadow roots when applicable.
5. Pass that observation to `guardian_radar`.
6. Pass the same observation or extracted snippets to `guardian_extract_page_facts`.
7. Check that the result distinguishes valuable objects, dangerous objects, and structured facts without reading browser storage or clicking risky controls.
