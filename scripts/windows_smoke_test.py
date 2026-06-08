import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "mcp" / "server.cjs"


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


class SmokeFailure(Exception):
    pass


def rpc_request(request_id, method, params=None):
    request = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    return request


def tool_request(request_id, name, arguments=None):
    return rpc_request(
        request_id,
        "tools/call",
        {"name": name, "arguments": arguments or {}},
    )


def run_server(requests, env_updates=None):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if env_updates:
        env.update(env_updates)
    payload = "\n".join(json.dumps(request, ensure_ascii=False) for request in requests) + "\n"
    completed = subprocess.run(
        ["node", str(SERVER)],
        input=payload,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )
    responses = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if line:
            responses.append(json.loads(line))
    return completed, responses


def parse_tool_payload(response):
    result = response.get("result") or {}
    content = result.get("content") or []
    if not content:
        return {}
    text = content[0].get("text") or "{}"
    return json.loads(text)


def call_tool(name, arguments=None, env_updates=None):
    requests = [
        rpc_request(1, "initialize", {"protocolVersion": "2024-11-05"}),
        tool_request(2, name, arguments or {}),
    ]
    completed, responses = run_server(requests, env_updates=env_updates)
    if completed.returncode != 0:
        raise SmokeFailure(f"MCP server exited {completed.returncode}: {completed.stderr[-2000:]}")
    if len(responses) != 2:
        raise SmokeFailure(f"Expected 2 MCP responses, got {len(responses)}: {completed.stdout[-2000:]}")
    if responses[-1].get("error"):
        raise SmokeFailure(f"MCP tool error for {name}: {responses[-1]['error']}")
    return parse_tool_payload(responses[-1])


def require_ok(label, payload):
    if not payload.get("ok"):
        raise SmokeFailure(f"{label} returned not ok: {json.dumps(payload, ensure_ascii=False)[:2000]}")


def main():
    if os.name != "nt":
        print(json.dumps({"ok": True, "skipped": True, "reason": "Windows smoke test only runs on Windows."}, ensure_ascii=False, indent=2))
        return 0
    if shutil.which("node") is None:
        raise SmokeFailure("node is not on PATH")

    checks = []
    explicit_env = {"SCREEN_GUARDIAN_PYTHON": sys.executable}
    dependency_payload = call_tool("check_dependencies", env_updates=explicit_env)
    require_ok("explicit SCREEN_GUARDIAN_PYTHON check_dependencies", dependency_payload)
    checks.append({"name": "explicit_python_runtime", "ok": True, "python_runtime": dependency_payload.get("python_runtime")})

    missing_python = str(Path(tempfile.gettempdir()) / "screen-guardian-missing-python.exe")
    fallback_payload = call_tool(
        "check_dependencies",
        env_updates={"SCREEN_GUARDIAN_PYTHON": missing_python, "PYTHON": sys.executable},
    )
    require_ok("fallback Python discovery check_dependencies", fallback_payload)
    runtime = fallback_payload.get("python_runtime") or {}
    failed_candidates = runtime.get("skipped_or_failed_candidates") or []
    if not failed_candidates:
        raise SmokeFailure("fallback Python discovery did not report the skipped broken candidate")
    checks.append({"name": "python_fallback_reports_candidates", "ok": True, "failed_candidates": failed_candidates})

    displays_payload = call_tool("list_displays", env_updates=explicit_env)
    require_ok("list_displays", displays_payload)
    if not displays_payload.get("displays"):
        raise SmokeFailure("list_displays returned no displays")
    checks.append({"name": "list_displays", "ok": True, "display_count": len(displays_payload.get("displays", []))})

    windows_payload = call_tool("list_windows", {"limit": 10}, env_updates=explicit_env)
    require_ok("list_windows", windows_payload)
    checks.append({"name": "list_windows", "ok": True, "window_count": windows_payload.get("count")})

    with tempfile.TemporaryDirectory(prefix="screen-guardian-smoke-appdata-") as appdata:
        isolated_env = {"SCREEN_GUARDIAN_PYTHON": sys.executable, "APPDATA": appdata}
        limits_payload = call_tool(
            "set_runtime_limits",
            {"limits": {"watch_duration_seconds_max": 1}},
            env_updates=isolated_env,
        )
        require_ok("set_runtime_limits isolated", limits_payload)
        watch_payload = call_tool(
            "watch_screen",
            {"duration_seconds": 2, "runtime_limits": {"watch_duration_seconds_max": 5}},
            env_updates=isolated_env,
        )
        if watch_payload.get("ok") or "no more than 1" not in str(watch_payload.get("error", "")):
            raise SmokeFailure(f"per-call runtime_limits loosened a persistent max: {watch_payload}")
        checks.append({"name": "per_call_runtime_limits_cannot_loosen", "ok": True})

        flags_payload = call_tool(
            "set_feature_flags",
            {"flags": {"audio_capture": False}},
            env_updates=isolated_env,
        )
        require_ok("set_feature_flags isolated", flags_payload)
        audio_payload = call_tool(
            "record_audio",
            {"duration_seconds": 0.1, "feature_flags": {"audio_capture": True}},
            env_updates=isolated_env,
        )
        if audio_payload.get("ok") or "inactive" not in str(audio_payload.get("error", "")):
            raise SmokeFailure(f"per-call feature_flags enabled a disabled feature: {audio_payload}")
        checks.append({"name": "per_call_feature_flags_cannot_enable", "ok": True})

        with tempfile.TemporaryDirectory(prefix="screen-guardian-uncleared-") as not_configured:
            clear_payload = call_tool("clear_cache", {"output_dir": not_configured, "all": True}, env_updates=isolated_env)
            if clear_payload.get("ok") or "only accepts" not in str(clear_payload.get("error", "")):
                raise SmokeFailure(f"clear_cache accepted an unconfigured directory: {clear_payload}")
            checks.append({"name": "clear_cache_rejects_unconfigured_dir", "ok": True})

    adapters = dependency_payload.get("adapters") or []
    screen_adapter = next((item for item in adapters if item.get("role") == "screen_capture"), {})
    if screen_adapter.get("available"):
        with tempfile.TemporaryDirectory(prefix="screen-guardian-smoke-") as tmp:
            capture_payload = call_tool(
                "capture_region",
                {
                    "left": 0,
                    "top": 0,
                    "width": 1,
                    "height": 1,
                    "relative_to_display": True,
                    "source_label": "windows-smoke",
                    "output_dir": tmp,
                    "write_metadata": True,
                },
                env_updates=explicit_env,
            )
            require_ok("capture_region", capture_payload)
            path = Path(capture_payload.get("path", ""))
            if not path.exists():
                raise SmokeFailure(f"capture_region reported a missing file: {path}")
            checks.append({"name": "tiny_region_capture", "ok": True, "path": str(path)})
    else:
        checks.append({"name": "tiny_region_capture", "ok": True, "skipped": True, "reason": screen_adapter.get("import_error")})

    print(json.dumps({"ok": True, "checks": checks}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1)
