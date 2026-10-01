# Changelog

## 0.1.15 - 2026-10-01

- Require Pillow 11.2.1 or newer for the Windows `ImageGrab.grab(window=HWND)` API.
- Check HWND API support before reporting the window adapter as available. Health receipts now include window readiness, the Pillow version, upgrade guidance, and whether a real capture was tested.
- Record client-area coordinates for direct HWND images and outer-window coordinates only for visible bbox fallback. Client-area quality checks no longer crop the window-frame offset twice.
- Return and persist `coordinate_mapping` for saved window images, including the desktop origin and per-axis scale after resizing. Missing client geometry is reported as unavailable instead of substituting the outer-window origin.
- Add regression coverage for older Pillow, non-Windows readiness, direct capture, visible fallback, missing geometry, and resized output metadata.

These changes preserve local-only output and quiet capture defaults. This plugin supplies an independent screenshot route; it does not patch the native Computer Use capture service.
