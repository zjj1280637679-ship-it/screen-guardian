# Webpage Capture

Screen and window capture can only see visible pixels. A full webpage screenshot is different: it asks a browser renderer to capture the scrollable document, including content below the visible viewport.

Screen Guardian treats this as an optional browser adapter, not part of the ultra-light screen core.

## Reference Projects And APIs

| Reference | Relevant capability | Design lesson |
| --- | --- | --- |
| [Playwright screenshots](https://playwright.dev/python/docs/screenshots) | `page.screenshot(full_page=True)` captures a full scrollable page, and locator screenshots capture elements | Use browser-native rendering when the goal is a long webpage image |
| [Puppeteer Page.screenshot](https://pptr.dev/api/puppeteer.page.screenshot) | Puppeteer exposes page screenshot options for browser-rendered pages | Full-page capture is a browser automation concern, not a desktop screenshot concern |
| [Chrome DevTools Protocol Page.captureScreenshot](https://chromedevtools.github.io/devtools-protocol/tot/Page/#method-captureScreenshot) | `captureBeyondViewport` can capture beyond the current viewport | CDP is the lower-level route behind many full-page screenshot tools |
| Playwright MCP | Full-page screenshot tool for agents | Agents should ask for webpage intent rather than compose low-level browser commands |

## Tools

`prepare_webpage_capture`

- Writes a local `webpage_capture_request` envelope.
- Does not launch a browser.
- Does not navigate to the URL.
- Useful when a future browser adapter, external API, or subagent should consume the request.

`capture_webpage`

- Uses the optional Playwright Chromium adapter.
- Requires persistent feature flag `webpage_capture=true`.
- Requires optional dependency installation:

```powershell
python -m pip install --user -r scripts/optional-web-requirements.txt
python -m playwright install chromium
```

## Modes

| Mode | Meaning |
| --- | --- |
| `full_page` | Capture the full scrollable document as a long image |
| `viewport` | Capture only the browser viewport |
| `element` | Capture one CSS selector with `selector` |
| `scroll_container` | Capture and stitch one inner scrollable container, with optional `frame_selector` for iframes |

## Examples

Prepare only:

```json
{
  "url": "https://example.com",
  "mode": "full_page",
  "context_policy": "hold_file"
}
```

Direct optional capture:

```json
{
  "url": "https://example.com",
  "mode": "full_page",
  "viewport_width": 1440,
  "viewport_height": 900,
  "wait_until": "load",
  "context_policy": "hold_file",
  "marked_file_only": true
}
```

Capture a table or panel:

```json
{
  "url": "https://example.com/report",
  "mode": "element",
  "selector": "main table",
  "context_policy": "hold_file"
}
```

Capture an inner scrollable table:

```json
{
  "url": "https://example.com/admin",
  "mode": "scroll_container",
  "selector": ".table-scroll",
  "context_policy": "hold_file",
  "marked_file_only": true
}
```

Capture an inner table inside an iframe:

```json
{
  "url": "https://example.com/console",
  "mode": "scroll_container",
  "frame_selector": "iframe[name='app']",
  "selector": ".quota-table-scroll",
  "max_segments": 40,
  "segment_delay_ms": 100,
  "context_policy": "hold_file"
}
```

## Tall Page Decision

Very tall pages can produce huge images. Screen Guardian checks `full_page_height_max` before saving. If the page is taller than the configured limit, it returns a decision menu:

- force full-page capture with `allow_oversize=true`
- capture the viewport only
- increase `full_page_height_max`

The default document-height limit is controlled by `webpage_capture_full_page_height_max` in runtime limits.

Nested scroll capture also checks `webpage_capture_scroll_segments_max` and `webpage_capture_segment_delay_ms_max`. If the container would require too many segments, Screen Guardian returns a decision menu: increase the segment limit, capture only the visible element, or use full-page capture instead.

## Boundary

Webpage capture should be used for authorized pages, documentation, accessibility, debugging, and personal AI understanding. It is not for bypassing login, paywalls, CAPTCHA, DRM, access controls, platform rules, privacy expectations, or unauthorized data access.

It also does not replace browser DOM or accessibility-tree extraction. A long image is useful for visual overview, but structured page data is often cheaper and more reliable for AI reasoning.
