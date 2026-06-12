# Browser Session Nested Scroll Longshot

## User Situation

The user has an already-authenticated browser tab open, such as a cloud-console billing, entitlement, permission, or resource-package page. The target data lives inside a nested scroll container or wide table rather than the document body. The AI needs one complete local long image without bringing the browser page to the foreground as a visible desktop screenshot.

## External Conditions

- The page may require the user's existing authenticated Chrome session.
- The relevant content may be inside an inner `div`, table viewport, virtualized list, or iframe.
- The container can scroll vertically, horizontally, or both.
- The local Screen Guardian helper must not inspect cookies, localStorage, passwords, or session files.

## Recommended Route

Use a browser-session connector or future CDP adapter, not the headless URL route, when the current authenticated tab is required.

Route outline:

1. Claim the already-open authorized browser tab.
2. Detect scrollable containers with bounded DOM reads.
3. Choose an explicit selector and record it in metadata.
4. Scroll the container through browser interaction or CDP, not by extracting session credentials.
5. Capture clipped segments locally.
6. Restore the original scroll position.
7. Stitch segments into a local long image.

## Guard Strategy

- Do not read cookies, localStorage, sessionStorage, browser passwords, or profile files.
- Do not submit forms, click destructive actions, or change filters unless the user explicitly asks.
- Label the result as `browser_session_nested_scroll`, not `headless_url_capture`.
- Record `selector`, `frame_selector`, `segments`, `scroll_axis`, `restored_scroll`, and `capture_performed=true` in metadata.
- If the page uses virtualization, return a decision warning unless segment evidence confirms that rows are complete.

## Context Budget

Use a local file path or hold-file policy by default. Do not paste long table contents into chat unless the user asks for extraction.

## Risks And Fallback Paths

- Virtualized tables may recycle DOM rows during scroll, so visual stitching can duplicate or skip rows.
- Sticky columns or headers can appear in multiple segments.
- Horizontal and vertical stitching need different overlap rules.
- Logged-in pages can contain sensitive account, billing, or entitlement data.

Fallbacks:

- Capture a scoped viewport only and ask for selector confirmation.
- Use structured export/download if the page provides an authorized export button and the user requests it.
- Use `capture_webpage` only when an explicit URL plus independent browser context is enough.
- Return a plan envelope if the current connector cannot safely scroll and restore the container.

## Acceptance Checks

- The target tab is selected from current open tabs by title/URL, not guessed.
- The detector returns container dimensions before screenshot.
- The capture does not inspect cookies or localStorage.
- The container scroll position is restored after capture.
- The final image covers the intended scroll extent.
- Metadata distinguishes browser-session capture from headless URL capture.
- The final response avoids dumping sensitive table contents unless requested.

## Related Whitepaper Claims

- Desktop situation index
- Webpage nested scroll
- Screen content is untrusted
- Hold-file context
- Review decomposition
