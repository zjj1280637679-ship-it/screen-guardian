# Screen Guardian

![Screen Guardian icon](assets/composer-icon.png)

Screen Guardian is a lightweight local screenshot plugin for Codex on Windows.

It is meant to provide compatibility-first capability infrastructure for personal AI.

Version `0.1.3` reframes the project purpose around freedom-preserving AI capability while keeping the smallest useful surface: local screenshots, monitor listing, region capture, downscaling, and cache cleanup.

## Purpose

Screen Guardian is not only a screenshot helper. Its broader goal is to help users reach positive freedom with AI: more practical capability, more ways for their AI to perceive local work, and more room to build personal workflows.

At the same time, it should not reduce negative freedom. Users should not have to upgrade Windows, replace their environment, accept heavy background services, or install a long chain of dependencies just to give their AI basic visual access.

The project is guided by four principles:

- Expand user agency by giving personal AI more useful local capabilities.
- Preserve user control through local-only defaults and explicit capture actions.
- Prefer compatibility paths that work on older or constrained systems.
- Keep dependencies light, optional, and explainable.

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
