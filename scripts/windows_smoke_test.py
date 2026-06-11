import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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


def launch_changing_window():
    code = r"""
import tkinter as tk

root = tk.Tk()
root.title("Screen Guardian Watch Smoke")
root.geometry("260x160+60+60")
root.attributes("-topmost", True)
frame = tk.Frame(root, bg="#c40000")
frame.pack(fill="both", expand=True)
label = tk.Label(frame, text="watch-start", bg="#c40000", fg="#ffffff", font=("Arial", 22))
label.pack(fill="both", expand=True)

def change():
    frame.configure(bg="#00c800")
    label.configure(text="watch-changed", bg="#00c800", fg="#000000")

root.after(900, change)
root.after(6000, root.destroy)
root.mainloop()
"""
    return subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def wait_for_window(title_fragment, env_updates, timeout_seconds=5):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        payload = call_tool("list_windows", {"title_contains": title_fragment, "limit": 5}, env_updates=env_updates)
        if payload.get("ok") and payload.get("windows"):
            return payload["windows"][0]
        time.sleep(0.2)
    return None


def main():
    if os.name != "nt":
        print(json.dumps({"ok": True, "skipped": True, "reason": "Windows smoke test only runs on Windows."}, ensure_ascii=False, indent=2))
        return 0
    if shutil.which("node") is None:
        raise SmokeFailure("node is not on PATH")

    checks = []
    explicit_env = {"SCREEN_GUARDIAN_PYTHON": sys.executable, "SCREEN_GUARDIAN_TOOL_SURFACE": "full"}
    dependency_payload = call_tool("check_dependencies", env_updates=explicit_env)
    require_ok("explicit SCREEN_GUARDIAN_PYTHON check_dependencies", dependency_payload)
    runtime_info = dependency_payload.get("python_runtime") or {}
    if not runtime_info.get("active_script_root") or runtime_info.get("mixed_runtime") not in (False, None):
        raise SmokeFailure(f"runtime active root consistency was not reported cleanly: {runtime_info}")
    checks.append({"name": "explicit_python_runtime", "ok": True, "python_runtime": dependency_payload.get("python_runtime")})

    guardian_check_payload = call_tool("guardian_check", {"detail": "short"}, env_updates=explicit_env)
    require_ok("guardian_check", guardian_check_payload)
    if guardian_check_payload.get("recommended_next") not in ("guardian_perceive", "check_dependencies"):
        raise SmokeFailure(f"guardian_check returned an unexpected next step: {guardian_check_payload}")
    checks.append({"name": "guardian_check", "ok": True, "recommended_next": guardian_check_payload.get("recommended_next")})

    helper_path = ROOT / "bin" / "screen-guardian-helper.exe"
    if helper_path.exists():
        helper_payload = call_tool("check_dependencies", env_updates={"SCREEN_GUARDIAN_HELPER_EXE": str(helper_path)})
        require_ok("explicit SCREEN_GUARDIAN_HELPER_EXE check_dependencies", helper_payload)
        runtime = helper_payload.get("python_runtime") or {}
        if runtime.get("kind") != "helper":
            raise SmokeFailure(f"helper executable was not selected first: {runtime}")
        checks.append({"name": "explicit_helper_runtime", "ok": True, "python_runtime": runtime})

    script_env = {
        "SCREEN_GUARDIAN_CAPTURE_SCRIPT": str(ROOT / "scripts" / "screen_guardian_capture.py"),
        "SCREEN_GUARDIAN_PYTHON": sys.executable,
        "SCREEN_GUARDIAN_TOOL_SURFACE": "full",
    }
    script_payload = call_tool("check_dependencies", env_updates=script_env)
    require_ok("explicit SCREEN_GUARDIAN_CAPTURE_SCRIPT check_dependencies", script_payload)
    script_runtime = script_payload.get("python_runtime") or {}
    if script_runtime.get("script_source") != "SCREEN_GUARDIAN_CAPTURE_SCRIPT":
        raise SmokeFailure(f"explicit capture script was not selected first: {script_runtime}")
    checks.append({"name": "explicit_capture_script", "ok": True, "python_runtime": script_runtime})

    missing_python = str(Path(tempfile.gettempdir()) / "screen-guardian-missing-python.exe")
    fallback_payload = call_tool(
        "check_dependencies",
        env_updates={"SCREEN_GUARDIAN_PYTHON": missing_python, "PYTHON": sys.executable},
    )
    require_ok("fallback Python discovery check_dependencies", fallback_payload)
    runtime = fallback_payload.get("python_runtime") or {}
    failed_candidates = runtime.get("skipped_or_failed_candidates") or []
    if not any(item.get("source") == "SCREEN_GUARDIAN_PYTHON" for item in failed_candidates):
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

    survey_status_payload = call_tool("guardian_survey_windows", {"capture_mode": "status_only", "limit": 5}, env_updates=explicit_env)
    require_ok("guardian_survey_windows status_only", survey_status_payload)
    if int(survey_status_payload.get("windows_reported") or 0) > 5:
        raise SmokeFailure(f"guardian_survey_windows ignored limit: {survey_status_payload}")
    checks.append(
        {
            "name": "guardian_survey_windows_status_only",
            "ok": True,
            "windows_reported": survey_status_payload.get("windows_reported"),
        }
    )

    with tempfile.TemporaryDirectory(prefix="screen-guardian-smoke-appdata-") as appdata:
        isolated_env = {"SCREEN_GUARDIAN_PYTHON": sys.executable, "APPDATA": appdata, "SCREEN_GUARDIAN_TOOL_SURFACE": "full"}
        limits_payload = call_tool(
            "set_runtime_limits",
            {
                "limits": {
                    "watch_duration_seconds_max": 1,
                    "capture_settle_delay_ms_max": 1,
                    "capture_stable_wait_seconds_max": 0,
                    "window_survey_capture_count_max": 0,
                }
            },
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

        guardian_watch_payload = call_tool(
            "guardian_perceive",
            {
                "task": "watch_change",
                "duration_seconds": 2,
                "runtime_limits": {"watch_duration_seconds_max": 5},
            },
            env_updates=isolated_env,
        )
        if guardian_watch_payload.get("ok") or "no more than 1" not in str(guardian_watch_payload.get("error", "")):
            raise SmokeFailure(f"guardian_perceive loosened a persistent watch max: {guardian_watch_payload}")
        checks.append({"name": "guardian_perceive_watch_cannot_loosen_limits", "ok": True})

        guardian_delay_payload = call_tool(
            "guardian_perceive",
            {
                "task": "quick_look",
                "delay_seconds": 0.01,
                "runtime_limits": {"capture_settle_delay_ms_max": 1000},
            },
            env_updates=isolated_env,
        )
        if guardian_delay_payload.get("ok") or "no more than 1" not in str(guardian_delay_payload.get("error", "")):
            raise SmokeFailure(f"guardian_perceive loosened a persistent render delay max: {guardian_delay_payload}")
        checks.append({"name": "guardian_perceive_delay_cannot_loosen_limits", "ok": True})

        survey_limit_payload = call_tool(
            "guardian_survey_windows",
            {
                "capture_mode": "hold_file",
                "capture_limit": 1,
                "runtime_limits": {"window_survey_capture_count_max": 5},
            },
            env_updates=isolated_env,
        )
        if survey_limit_payload.get("ok") or "no more than 0" not in str(survey_limit_payload.get("error", "")):
            raise SmokeFailure(f"guardian_survey_windows loosened a persistent capture max: {survey_limit_payload}")
        checks.append({"name": "guardian_survey_windows_capture_limit_cannot_loosen", "ok": True})

        stable_limit_payload = call_tool(
            "guardian_perceive",
            {
                "capture_modes": ["wait_buffer"],
                "stable_wait_seconds": 0.1,
                "runtime_limits": {"capture_stable_wait_seconds_max": 5},
            },
            env_updates=isolated_env,
        )
        if stable_limit_payload.get("ok") or "no more than 0" not in str(stable_limit_payload.get("error", "")):
            raise SmokeFailure(f"guardian_perceive loosened a persistent stable wait max: {stable_limit_payload}")
        checks.append({"name": "guardian_perceive_stable_wait_cannot_loosen_limits", "ok": True})

        raw_disabled_payload = call_tool(
            "guardian_run_exec",
            {"language": "python", "code": "print('should not run')", "user_confirmed": True},
            env_updates=isolated_env,
        )
        if raw_disabled_payload.get("ok") or "raw_local_exec" not in str(raw_disabled_payload):
            raise SmokeFailure(f"guardian_run_exec ran while raw_local_exec was inactive: {raw_disabled_payload}")
        checks.append({"name": "guardian_run_exec_default_disabled", "ok": True})

        raw_flags_payload = call_tool(
            "set_feature_flags",
            {"flags": {"raw_local_exec": True}},
            env_updates=isolated_env,
        )
        require_ok("set_feature_flags raw_local_exec isolated", raw_flags_payload)

        raw_unconfirmed_payload = call_tool(
            "guardian_run_exec",
            {"language": "python", "code": "print('should not run')", "user_confirmed": False},
            env_updates=isolated_env,
        )
        if raw_unconfirmed_payload.get("ok") or "user_confirmed" not in str(raw_unconfirmed_payload.get("error", "")):
            raise SmokeFailure(f"guardian_run_exec ran without per-call confirmation: {raw_unconfirmed_payload}")
        checks.append({"name": "guardian_run_exec_requires_confirmation", "ok": True})

        with tempfile.TemporaryDirectory(prefix="screen-guardian-exec-smoke-") as exec_tmp:
            prepared_exec = call_tool(
                "guardian_prepare_exec",
                {
                    "language": "python",
                    "code": "print('screen-guardian raw exec smoke')",
                    "reason": "Windows smoke test.",
                    "output_dir": exec_tmp,
                },
                env_updates=isolated_env,
            )
            require_ok("guardian_prepare_exec", prepared_exec)
            exec_payload = call_tool(
                "guardian_run_exec",
                {"envelope_path": prepared_exec.get("request_path"), "user_confirmed": True, "output_dir": exec_tmp},
                env_updates=isolated_env,
            )
            require_ok("guardian_run_exec confirmed", exec_payload)
            if "screen-guardian raw exec smoke" not in exec_payload.get("stdout", ""):
                raise SmokeFailure(f"guardian_run_exec did not return expected stdout: {exec_payload}")
            checks.append({"name": "guardian_run_exec_confirmed_python", "ok": True})

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
    routes_payload = call_tool("list_capture_routes", {"include_examples": False}, env_updates=explicit_env)
    require_ok("list_capture_routes", routes_payload)
    routes = routes_payload.get("routes") or {}
    if (routes.get("webpage") or {}).get("active") is not False:
        raise SmokeFailure(f"webpage route did not report inactive default state: {routes_payload}")
    checks.append({"name": "webpage_route_reports_inactive_default", "ok": True})

    screen_adapter = next((item for item in adapters if item.get("role") == "screen_capture"), {})
    if screen_adapter.get("available"):
        with tempfile.TemporaryDirectory(prefix="screen-guardian-smoke-") as tmp:
            timeout_payload = call_tool(
                "capture_region",
                {
                    "left": 0,
                    "top": 0,
                    "width": 1,
                    "height": 1,
                    "relative_to_display": True,
                    "delay_seconds": 2,
                    "output_dir": tmp,
                },
                env_updates={**explicit_env, "SCREEN_GUARDIAN_MCP_CHILD_TIMEOUT_MS": "1000"},
            )
            if timeout_payload.get("ok") or "timed out" not in str(timeout_payload.get("error", "")).lower():
                raise SmokeFailure(f"MCP child timeout did not stop delayed capture: {timeout_payload}")
            checks.append({"name": "mcp_child_timeout_stops_delayed_capture", "ok": True})

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

            guard_decision_payload = call_tool(
                "capture_region",
                {
                    "left": 0,
                    "top": 0,
                    "width": 1,
                    "height": 1,
                    "relative_to_display": True,
                    "source_label": "windows-smoke-guard-decision",
                    "output_dir": tmp,
                    "render_guard": "warn",
                    "guard_checks": ["tiny_capture"],
                    "guard_tiny_min_pixels": 16,
                },
                env_updates=explicit_env,
            )
            require_ok("capture_region guard decision", guard_decision_payload)
            if guard_decision_payload.get("saved") is not False:
                raise SmokeFailure(f"guard decision did not report saved=false: {guard_decision_payload}")
            if guard_decision_payload.get("path") is not None:
                raise SmokeFailure(f"guard decision unexpectedly reported a saved path: {guard_decision_payload}")
            if guard_decision_payload.get("result_state") != "decision_required" or not guard_decision_payload.get("capture_deferred"):
                raise SmokeFailure(f"guard decision did not report deferred decision state: {guard_decision_payload}")
            checks.append({"name": "capture_guard_decision_not_saved", "ok": True})

            fast_payload = call_tool(
                "guardian_perceive",
                {
                    "task": "quick_look",
                    "target": {
                        "type": "region",
                        "box": {
                            "left": 0,
                            "top": 0,
                            "width": 1,
                            "height": 1,
                            "relative_to_display": True,
                        },
                    },
                    "source_label": "guardian-fast-smoke",
                    "output_dir": tmp,
                },
                env_updates=explicit_env,
            )
            require_ok("guardian_perceive fast default", fast_payload)
            fast_strategy = fast_payload.get("capture_strategy") or {}
            if fast_strategy.get("modes") != ["fast"] or fast_strategy.get("default_fast") is not True:
                raise SmokeFailure(f"guardian_perceive did not report fast default strategy: {fast_payload}")
            checks.append({"name": "guardian_perceive_fast_default", "ok": True, "path": fast_payload.get("path")})

            stable_payload = call_tool(
                "guardian_perceive",
                {
                    "task": "quick_look",
                    "capture_modes": ["wait_buffer"],
                    "stable_wait_seconds": 0.5,
                    "stable_interval_ms": 100,
                    "stable_required_samples": 1,
                    "target": {
                        "type": "region",
                        "box": {
                            "left": 0,
                            "top": 0,
                            "width": 1,
                            "height": 1,
                            "relative_to_display": True,
                        },
                    },
                    "source_label": "guardian-buffer-smoke",
                    "output_dir": tmp,
                },
                env_updates=explicit_env,
            )
            require_ok("guardian_perceive wait_buffer", stable_payload)
            stable_strategy = stable_payload.get("capture_strategy") or {}
            if stable_strategy.get("modes") != ["wait_buffer"] or not isinstance(stable_strategy.get("stable_wait"), dict):
                raise SmokeFailure(f"guardian_perceive did not record wait_buffer strategy: {stable_payload}")
            checks.append({"name": "guardian_perceive_wait_buffer", "ok": True, "path": stable_payload.get("path")})

            guardian_payload = call_tool(
                "guardian_perceive",
                {
                    "task": "read_text",
                    "target": {
                        "type": "region",
                        "box": {
                            "left": 0,
                            "top": 0,
                            "width": 1,
                            "height": 1,
                            "relative_to_display": True,
                        },
                    },
                    "context_budget": "hold_file",
                    "source_label": "guardian-smoke",
                    "output_dir": tmp,
                },
                env_updates=explicit_env,
            )
            require_ok("guardian_perceive read_text hold_file", guardian_payload)
            if guardian_payload.get("preprocess", {}).get("applied") != "text":
                raise SmokeFailure(f"guardian_perceive did not apply text preprocessing: {guardian_payload}")
            if guardian_payload.get("text_handling", {}).get("ocr_available") is not False:
                raise SmokeFailure(f"guardian_perceive read_text did not report OCR unavailable in ultra-light mode: {guardian_payload}")
            if guardian_payload.get("context_delivery") != "file_marked_only":
                raise SmokeFailure(f"guardian_perceive did not mark hold_file delivery: {guardian_payload}")
            checks.append({"name": "guardian_perceive_read_text_hold_file", "ok": True, "path": guardian_payload.get("path")})

            watch_process = None
            try:
                watch_process = launch_changing_window()
                window = wait_for_window("Screen Guardian Watch Smoke", explicit_env)
                if not window:
                    raise SmokeFailure("changing watch smoke window did not appear")
                watch_change_payload = call_tool(
                    "guardian_perceive",
                    {
                        "task": "watch_change",
                        "target": {"hwnd": int(window["hwnd"])},
                        "duration_seconds": 2.8,
                        "interval_seconds": 0.2,
                        "change_threshold": 10,
                        "max_captures": 3,
                        "source_label": "watch-change-smoke",
                        "output_dir": tmp,
                    },
                    env_updates=explicit_env,
                )
                require_ok("guardian_perceive watch_change real event", watch_change_payload)
                if int(watch_change_payload.get("events") or 0) < 1 or not watch_change_payload.get("captures"):
                    raise SmokeFailure(f"watch_change did not produce a real change event: {watch_change_payload}")
                missing = [item.get("path") for item in watch_change_payload.get("captures") or [] if not Path(str(item.get("path") or "")).exists()]
                if missing:
                    raise SmokeFailure(f"watch_change reported missing capture files: {missing}")
                checks.append(
                    {
                        "name": "guardian_perceive_watch_change_real_event",
                        "ok": True,
                        "events": watch_change_payload.get("events"),
                        "captures": len(watch_change_payload.get("captures") or []),
                    }
                )

                error_wait_payload = call_tool(
                    "guardian_perceive",
                    {
                        "task": "capture_window",
                        "capture_modes": ["wait_error"],
                        "error_title_contains": "Screen Guardian Watch Smoke",
                        "error_capture_target": "matching_window",
                        "error_wait_seconds": 2,
                        "render_guard": "save",
                        "output_dir": tmp,
                    },
                    env_updates=explicit_env,
                )
                require_ok("guardian_perceive wait_error", error_wait_payload)
                error_strategy = error_wait_payload.get("capture_strategy") or {}
                error_wait = error_strategy.get("error_wait") if isinstance(error_strategy.get("error_wait"), dict) else {}
                if error_wait.get("status") != "detected":
                    raise SmokeFailure(f"guardian_perceive did not detect explicit error-window signal: {error_wait_payload}")
                checks.append({"name": "guardian_perceive_wait_error", "ok": True, "path": error_wait_payload.get("path")})

                survey_capture_payload = call_tool(
                    "guardian_survey_windows",
                    {
                        "capture_mode": "hold_file",
                        "hwnd": int(window["hwnd"]),
                        "limit": 1,
                        "capture_limit": 1,
                        "context_budget": "hold_file",
                        "render_guard": "save",
                        "output_dir": tmp,
                    },
                    env_updates=explicit_env,
                )
                require_ok("guardian_survey_windows hold_file capture", survey_capture_payload)
                if int(survey_capture_payload.get("saved_count") or 0) < 1:
                    raise SmokeFailure(f"guardian_survey_windows did not save a hold-file capture: {survey_capture_payload}")
                survey_capture_path = Path(str((survey_capture_payload.get("captures") or [{}])[0].get("result", {}).get("path") or ""))
                if not survey_capture_path.exists():
                    raise SmokeFailure(f"guardian_survey_windows reported a missing file: {survey_capture_path}")
                checks.append(
                    {
                        "name": "guardian_survey_windows_hold_file_capture",
                        "ok": True,
                        "saved_count": survey_capture_payload.get("saved_count"),
                    }
                )
            finally:
                if watch_process and watch_process.poll() is None:
                    watch_process.terminate()
                    try:
                        watch_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        watch_process.kill()
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
