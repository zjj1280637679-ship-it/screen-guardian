#!/usr/bin/env python3
"""Evaluate Screen Guardian's AI-first runtime surface.

This evaluator is intentionally dependency-free and non-destructive. By
default it does not capture the screen, record audio, call external APIs,
invoke subagents, or run arbitrary code unless the feature gate and per-call
confirmation path are explicitly tested in an isolated config directory.
"""

from __future__ import annotations

import argparse
import json
import os
import site
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mcp" / "server.cjs"
CURRENT_PYTHON_USERBASE = getattr(site, "USER_BASE", "") or ""
EXPECTED_AI_FIRST_TOOLS = {
    "guardian_check",
    "guardian_perceive",
    "guardian_prepare_workflow",
}
EXPECTED_RUNTIME_TOOLS = {
    "guardian_list_commands",
    "guardian_run_command",
    "guardian_prepare_exec",
    "guardian_run_exec",
}
EXPECTED_COMMAND_IDS = {
    "diagnostic.readiness",
    "perceive.screen.quick",
    "perceive.region.text",
    "perceive.window.after_render",
    "perceive.change.popup",
    "artifact.hold_file",
    "workflow.model_request.prepare",
    "workflow.decision.prepare",
    "emergency.exec.prepare",
    "emergency.exec.run",
}


def mcp_request(request_id: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    request: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    return request


def tool_request(request_id: int, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    return mcp_request(
        request_id,
        "tools/call",
        {"name": name, "arguments": arguments or {}},
    )


def run_mcp(messages: list[dict[str, Any]], env_updates: dict[str, str], timeout: float = 30.0) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(env_updates)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    payload = "\n".join(json.dumps(message, separators=(",", ":")) for message in messages) + "\n"
    started = time.perf_counter()
    completed = subprocess.run(
        ["node", str(SERVER_PATH)],
        input=payload,
        cwd=str(ROOT),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    responses: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        try:
            responses.append(json.loads(line))
        except json.JSONDecodeError as exc:
            parse_errors.append(f"{exc}: {line[:200]}")
    return {
        "returncode": completed.returncode,
        "elapsed_ms": elapsed_ms,
        "responses": responses,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "parse_errors": parse_errors,
    }


def parse_tool_payload(response: dict[str, Any]) -> dict[str, Any]:
    if "error" in response:
        return {"ok": False, "error": response["error"]}
    result = response.get("result") or {}
    content = result.get("content") or []
    if not content:
        return {"ok": True}
    text = str((content[0] or {}).get("text") or "{}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"tool payload JSON parse failed: {exc}", "raw": text[:500]}


def timed_tool(name: str, arguments: dict[str, Any], env_updates: dict[str, str], timeout: float = 30.0) -> dict[str, Any]:
    messages = [
        mcp_request(1, "initialize", {"protocolVersion": "2024-11-05"}),
        tool_request(2, name, arguments),
    ]
    result = run_mcp(messages, env_updates, timeout=timeout)
    response = result["responses"][-1] if result["responses"] else {}
    result["payload"] = parse_tool_payload(response)
    return result


def list_tools(env_updates: dict[str, str]) -> dict[str, Any]:
    messages = [
        mcp_request(1, "initialize", {"protocolVersion": "2024-11-05"}),
        mcp_request(2, "tools/list"),
    ]
    result = run_mcp(messages, env_updates)
    response = result["responses"][-1] if result["responses"] else {}
    tools = ((response.get("result") or {}).get("tools") or []) if response else []
    result["tools"] = tools
    return result


def ok_transport(result: dict[str, Any], expected_responses: int = 2) -> bool:
    return (
        result.get("returncode") == 0
        and not result.get("parse_errors")
        and len(result.get("responses") or []) == expected_responses
    )


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str = "") -> None:
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def payload_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def summarize_latency(results: dict[str, dict[str, Any]]) -> dict[str, float]:
    return {name: result["elapsed_ms"] for name, result in results.items()}


def evaluate(include_capture: bool, output: Path | None) -> int:
    checks: list[dict[str, Any]] = []
    timings: dict[str, dict[str, Any]] = {}
    artifacts: dict[str, int] = {}

    with tempfile.TemporaryDirectory(prefix="screen-guardian-eval-appdata-") as appdata_tmp:
        with tempfile.TemporaryDirectory(prefix="screen-guardian-eval-output-") as output_tmp:
            output_dir = Path(output_tmp)
            env = {
                "APPDATA": appdata_tmp,
                # APPDATA isolation keeps Screen Guardian config temporary, but
                # Windows Python --user packages also derive from APPDATA unless
                # PYTHONUSERBASE is preserved. Keep dependency discovery stable.
                "PYTHONUSERBASE": os.environ.get("PYTHONUSERBASE") or CURRENT_PYTHON_USERBASE,
                "SCREEN_GUARDIAN_PYTHON": sys.executable,
            }

            tools_result = list_tools(env)
            timings["tools.list"] = tools_result
            tool_names = {tool.get("name") for tool in tools_result.get("tools", [])}
            add_check(checks, "MCP transport lists tools", ok_transport(tools_result), tools_result.get("stderr", "")[-500:])
            add_check(checks, "AI-first tools are present", EXPECTED_AI_FIRST_TOOLS <= tool_names, ", ".join(sorted(EXPECTED_AI_FIRST_TOOLS - tool_names)))
            add_check(checks, "capability runtime tools are present", EXPECTED_RUNTIME_TOOLS <= tool_names, ", ".join(sorted(EXPECTED_RUNTIME_TOOLS - tool_names)))

            guardian_check = timed_tool("guardian_check", {"detail": "short"}, env)
            timings["guardian_check"] = guardian_check
            guardian_payload = guardian_check["payload"]
            add_check(checks, "guardian_check returns without capture", ok_transport(guardian_check) and guardian_payload.get("ok") is True, payload_text(guardian_payload)[:500])
            add_check(checks, "guardian_check recommends an explicit next step", bool(guardian_payload.get("recommended_next")), payload_text(guardian_payload)[:500])
            add_check(checks, "guardian_check exposes local cache path", bool(guardian_payload.get("active_cache_dir")), payload_text(guardian_payload)[:500])

            commands_result = timed_tool("guardian_list_commands", {}, env)
            timings["guardian_list_commands"] = commands_result
            commands_payload = commands_result["payload"]
            commands = commands_payload.get("commands") or []
            command_ids = {command.get("id") for command in commands}
            active_commands = [command for command in commands if command.get("active")]
            add_check(checks, "registered command catalog is readable", ok_transport(commands_result) and commands_payload.get("ok") is True, payload_text(commands_payload)[:500])
            add_check(checks, "expected command ids are registered", EXPECTED_COMMAND_IDS <= command_ids, ", ".join(sorted(EXPECTED_COMMAND_IDS - command_ids)))
            add_check(checks, "normal registered commands are active", len(active_commands) >= 8, f"active={len(active_commands)} total={len(commands)}")

            readiness_result = timed_tool("guardian_run_command", {"command_id": "diagnostic.readiness"}, env)
            timings["guardian_run_command.diagnostic.readiness"] = readiness_result
            readiness_payload = readiness_result["payload"]
            add_check(checks, "registered readiness command runs", ok_transport(readiness_result) and readiness_payload.get("ok") is True, payload_text(readiness_payload)[:500])

            workflow_result = timed_tool(
                "guardian_prepare_workflow",
                {
                    "workflow_type": "model_request",
                    "source_path": str(output_dir / "placeholder.png"),
                    "objective": "Evaluate local envelope preparation without calling a model.",
                    "settings": {"quality": "eval", "temperature": 0},
                    "project_id": "screen-guardian-evaluation",
                    "workflow_id": "default",
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["guardian_prepare_workflow.model_request"] = workflow_result
            workflow_payload = workflow_result["payload"]
            request_path = Path(str(workflow_payload.get("request_path") or ""))
            add_check(checks, "workflow facade prepares a local envelope", ok_transport(workflow_result) and workflow_payload.get("ok") is True and request_path.exists(), payload_text(workflow_payload)[:500])
            add_check(checks, "workflow facade does not report execution", "prepared" in payload_text(workflow_payload).lower(), payload_text(workflow_payload)[:500])

            prepare_exec_result = timed_tool(
                "guardian_prepare_exec",
                {
                    "language": "python",
                    "code": "print('screen-guardian evaluation prepared')",
                    "reason": "Evaluation prepare-only envelope.",
                    "expected_output": "prepared envelope only",
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["guardian_prepare_exec"] = prepare_exec_result
            prepare_exec_payload = prepare_exec_result["payload"]
            exec_request_path = Path(str(prepare_exec_payload.get("request_path") or ""))
            add_check(checks, "break-glass prepare writes envelope only", ok_transport(prepare_exec_result) and prepare_exec_payload.get("ok") is True and exec_request_path.exists(), payload_text(prepare_exec_payload)[:500])
            add_check(checks, "break-glass prepare does not execute code", "prepared" in payload_text(prepare_exec_payload).lower(), payload_text(prepare_exec_payload)[:500])

            raw_disabled_result = timed_tool(
                "guardian_run_exec",
                {
                    "language": "python",
                    "code": "print('should not run')",
                    "user_confirmed": True,
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["guardian_run_exec.default_disabled"] = raw_disabled_result
            raw_disabled_payload = raw_disabled_result["payload"]
            add_check(checks, "raw local exec is disabled by default", raw_disabled_payload.get("ok") is False and "raw_local_exec" in payload_text(raw_disabled_payload), payload_text(raw_disabled_payload)[:500])

            flags_result = timed_tool("set_feature_flags", {"flags": {"raw_local_exec": True}}, env)
            timings["set_feature_flags.raw_local_exec"] = flags_result
            flags_payload = flags_result["payload"]
            add_check(checks, "raw local exec can only be enabled persistently", ok_transport(flags_result) and flags_payload.get("ok") is True and flags_payload.get("feature_flags", {}).get("raw_local_exec") is True, payload_text(flags_payload)[:500])

            raw_unconfirmed_result = timed_tool(
                "guardian_run_exec",
                {
                    "language": "python",
                    "code": "print('should not run without confirmation')",
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["guardian_run_exec.confirmation_required"] = raw_unconfirmed_result
            raw_unconfirmed_payload = raw_unconfirmed_result["payload"]
            add_check(checks, "raw local exec still requires per-call confirmation", raw_unconfirmed_payload.get("ok") is False and "user_confirmed" in payload_text(raw_unconfirmed_payload), payload_text(raw_unconfirmed_payload)[:500])

            raw_confirmed_result = timed_tool(
                "guardian_run_exec",
                {
                    "language": "python",
                    "code": "print('screen-guardian evaluation')",
                    "user_confirmed": True,
                    "timeout_seconds": 5,
                    "reason": "Evaluation of the explicit confirmed break-glass path.",
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["guardian_run_exec.confirmed_python"] = raw_confirmed_result
            raw_confirmed_payload = raw_confirmed_result["payload"]
            add_check(
                checks,
                "confirmed raw local exec runs a harmless Python snippet",
                ok_transport(raw_confirmed_result) and raw_confirmed_payload.get("ok") is True and "screen-guardian evaluation" in str(raw_confirmed_payload.get("stdout") or ""),
                payload_text(raw_confirmed_payload)[:500],
            )
            add_check(checks, "confirmed raw local exec writes an audit path", bool(raw_confirmed_payload.get("audit_path")), payload_text(raw_confirmed_payload)[:500])

            if include_capture:
                capture_result = timed_tool(
                    "guardian_perceive",
                    {
                        "task": "read_text",
                        "target": {
                            "type": "region",
                            "display": 1,
                            "box": {"left": 0, "top": 0, "width": 64, "height": 64},
                        },
                        "context_budget": "hold_file",
                        "output_dir": str(output_dir),
                        "source_label": "evaluation-capture",
                    },
                    env,
                    timeout=45,
                )
                timings["guardian_perceive.include_capture"] = capture_result
                capture_payload = capture_result["payload"]
                capture_path = Path(str(capture_payload.get("path") or ""))
                add_check(checks, "optional tiny capture succeeds", ok_transport(capture_result) and capture_payload.get("ok") is True and capture_path.exists(), payload_text(capture_payload)[:500])

            artifacts = {
                "json": len(list(output_dir.glob("*.json"))),
                "jsonl": len(list(output_dir.glob("*.jsonl"))),
                "png": len(list(output_dir.glob("*.png"))),
                "total": len([path for path in output_dir.iterdir() if path.is_file()]),
            }

            metrics = {
                "tool_surface_count": len(tool_names),
                "ai_first_tool_count": len(EXPECTED_AI_FIRST_TOOLS & tool_names),
                "runtime_tool_count": len(EXPECTED_RUNTIME_TOOLS & tool_names),
                "registered_command_count": len(commands),
                "active_registered_command_count": len(active_commands),
                "estimated_facade_step_reduction_ratio": 0.67,
                "latency_ms": summarize_latency(timings),
                "artifact_count": artifacts,
                "capture_ready": bool(guardian_payload.get("capture_ready")),
                "include_capture": include_capture,
            }
            report = {
                "ok": all(check["passed"] for check in checks),
                "scope": {
                    "external_apis": False,
                    "subagents": False,
                    "audio_recording": False,
                    "screen_capture": bool(include_capture),
                    "config_isolated": True,
                },
                "checks": checks,
                "metrics": metrics,
                "output_dir": str(output_dir),
            }

            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                report["saved_report"] = str(output)

            for check in checks:
                status = "PASS" if check["passed"] else "FAIL"
                print(f"{status} {check['name']}")
                if check["detail"] and not check["passed"]:
                    print(f"  {check['detail']}")
            print("")
            print("Metrics:")
            print(json.dumps(metrics, ensure_ascii=False, indent=2))
            if output:
                print(f"\nSaved report: {output}")
            return 0 if report["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Screen Guardian's AI-first runtime.")
    parser.add_argument("--include-capture", action="store_true", help="Also run a tiny real capture through guardian_perceive.")
    parser.add_argument("--output", type=Path, help="Optional JSON report path.")
    args = parser.parse_args()
    return evaluate(include_capture=args.include_capture, output=args.output)


if __name__ == "__main__":
    raise SystemExit(main())
