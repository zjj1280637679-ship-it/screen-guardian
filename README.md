# Screen Guardian

Screen Guardian is a lightweight local screenshot plugin for Codex on Windows.

It is meant to provide an independent visual input path when Computer Use screenshot capture is unavailable or incompatible.

Version `0.1.0` focuses on the smallest useful surface: local screenshots, monitor listing, region capture, downscaling, and cache cleanup.

## Current tools

- Check screenshot dependencies
- List connected displays
- Capture a full display or virtual desktop
- Capture a rectangular region
- Save PNG or JPG
- Optionally downscale captures
- Clear Screen Guardian's local cache files

Captures are saved locally by default:

```text
~/Pictures/ScreenGuardian
```

## Dependencies

The first version uses Python with:

- `mss`
- `Pillow`

Install them with:

```powershell
python -m pip install --user -r scripts/requirements.txt
```

The MCP server itself uses Node.js and has no npm dependencies.

## Local test

You can smoke-test the MCP server with newline-delimited JSON-RPC:

```powershell
@'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"check_dependencies","arguments":{}}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"list_displays","arguments":{}}}
'@ | node .\mcp\server.cjs
```

## Privacy model

This first version intentionally avoids continuous capture, recording, OCR, cloud upload, and screen history. It only saves requested screenshots to a local folder.

## Upgrade path

The next version can add:

- bounded continuous screenshots
- frame-change detection
- short FFmpeg recordings
- image and video summarization helpers
- stricter privacy filters by app, window, or region
