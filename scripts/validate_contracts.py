#!/usr/bin/env python3
"""Validate Screen Guardian design, tool, and stress-test contracts.

This script is intentionally dependency-free. It checks repository text,
MCP wiring, Python action wiring, feature-flag boundaries, and optionally
runs a bounded MCP stress test for decision and monitor envelopes.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "mcp" / "server.cjs"
PYTHON_PATH = ROOT / "scripts" / "screen_guardian_capture.py"
MANIFEST_PATH = ROOT / ".codex-plugin" / "plugin.json"
PACKAGE_PATH = ROOT / "package.json"
MCP_PATH = ROOT / ".mcp.json"
TEXT_ENCODING_PATH = ROOT / "scripts" / "check_text_encoding.py"
MAX_STRESS_LOOPS = 200


REQUIRED_TOOLS = [
    "guardian_check",
    "guardian_perceive",
    "guardian_prepare_workflow",
    "guardian_list_commands",
    "guardian_run_command",
    "guardian_prepare_exec",
    "guardian_run_exec",
    "check_dependencies",
    "get_runtime_settings",
    "set_cache_path",
    "set_storage_routes",
    "set_runtime_limits",
    "set_feature_flags",
    "list_extension_routes",
    "set_extension_route",
    "prepare_model_request",
    "list_decision_policies",
    "set_decision_policy",
    "prepare_decision_request",
    "list_monitor_profiles",
    "set_monitor_profile",
    "prepare_monitor_tick",
    "get_display_profile",
    "set_display_name",
    "apply_display_profile",
    "list_adapters",
    "list_audio_devices",
    "record_audio",
    "analyze_audio",
    "extract_audio_track",
    "list_displays",
    "list_windows",
    "capture_screen",
    "capture_region",
    "capture_window",
    "watch_screen",
    "analyze_image",
    "preprocess_image",
    "clear_cache",
]


REQUIRED_FEATURE_FLAGS = [
    "screen_capture",
    "window_capture",
    "bounded_watch",
    "workflow_metadata",
    "multi_storage_routes",
    "image_analysis",
    "image_preprocess",
    "extension_routes",
    "model_request_envelopes",
    "ocr_routes",
    "image_narration_routes",
    "video_narration_routes",
    "audio_capture",
    "audio_analysis",
    "audio_transcription_routes",
    "video_audio_extract",
    "decision_policies",
    "monitor_profiles",
    "external_api_handoff",
    "codex_subagent_handoff",
    "raw_local_exec",
]


DESIGN_COVERAGE = {
    "ai-first interface": ["ai-first", "guardian_check", "guardian_perceive"],
    "anti-abuse stance": ["anti-abuse", "not designed or supported for bypassing"],
    "advisory context signals": ["advisory", "regex", "hard moral blockers"],
    "capability runtime": ["capability runtime", "registered commands", "break-glass"],
    "related project research": ["related products", "private vision company", "borrowed design patterns"],
    "runtime evaluation": ["runtime evaluation", "npm run evaluate", "confirmation-gated"],
    "positive freedom": ["positive freedom", "expand user agency"],
    "negative freedom": ["negative freedom", "forced upgrades", "forced background services"],
    "compatibility fallback": ["fallback", "compatibility", "older windows", "constrained systems"],
    "local control": ["local-only", "saved locally", "do not upload", "local cache"],
    "optional dependencies": ["optional", "inactive features", "feature flags"],
    "context economy": ["context", "downscale", "preprocess"],
    "no hidden scheduler": ["does not silently start", "does not start a background", "no-background-service"],
    "arbitrary decisions": ["arbitrary-complexity", "decision policies", "function_route"],
    "tool layering": ["core tools", "local control tools", "experimental envelope tools"],
}


SCENARIO_COVERAGE = {
    "ai quick look facade": ["quick look", "guardian_perceive", "quick_look"],
    "hold file context": ["hold file", "hold_file", "file_marked_only"],
    "render timing capture": ["delay_seconds", "wait_for_nonblank", "render_retry_count"],
    "registered command runtime": ["guardian_list_commands", "guardian_run_command", "command_id"],
    "break-glass execution": ["guardian_prepare_exec", "guardian_run_exec", "raw_local_exec"],
    "older system capture": ["older windows", "native screen capture", "computer use"],
    "window/program capture": ["program window", "window", "process name"],
    "region/display capture": ["region", "display"],
    "text screenshot handling": ["text-heavy", "sharpen", "ocr"],
    "storage/cache routing": ["cache", "storage", "mirror"],
    "project workflow metadata": ["project_id", "workflow_id", "workflow"],
    "web change trigger": ["webpage", "web_change"],
    "program/window change trigger": ["window_change", "program changes"],
    "error trigger": ["error_text", "error-aware", "error"],
    "model feature trigger": ["model_feature", "model-detected"],
    "audio diagnostics": ["audio", "silence", "clipping"],
    "video/audio extraction": ["video", "extract_audio_track", "ffmpeg"],
    "decision routing": ["decision", "scoring function", "codex subagent"],
    "bounded watch": ["bounded watch", "watch_screen", "change-triggered"],
}


class CheckSet:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []

    def check(self, condition: bool, label: str, detail: str = "") -> None:
        if condition:
            self.passed.append(label)
            return
        self.failed.append(f"{label}{': ' + detail if detail else ''}")

    def extend(self, other: "CheckSet") -> None:
        self.passed.extend(other.passed)
        self.failed.extend(other.failed)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(read_text(path))


def all_project_text() -> str:
    parts = [
        ROOT / "README.md",
        ROOT / "SECURITY.md",
        ROOT / "docs" / "AI_FIRST_INTERFACE.md",
        ROOT / "docs" / "ANTI_ABUSE.md",
        ROOT / "docs" / "CAPABILITY_RUNTIME.md",
        ROOT / "docs" / "COMPATIBILITY.md",
        ROOT / "docs" / "EVALUATION.md",
        ROOT / "docs" / "MODELS.md",
        ROOT / "docs" / "RELATED_PROJECTS.md",
        ROOT / "docs" / "WORKFLOWS.md",
        ROOT / "docs" / "NAMING.md",
        ROOT / "skills" / "screen-guardian" / "SKILL.md",
    ]
    return "\n".join(read_text(path) for path in parts if path.exists()).lower()


def python_dict_keys(name: str, source: str) -> set[str]:
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            return set()
        keys: set[str] = set()
        for key in node.value.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.add(key.value)
        return keys
    return set()


def server_tools(source: str) -> set[str]:
    tools_block = re.search(r"const tools = \[(.*?)\n\];", source, re.S)
    if not tools_block:
        return set()
    return set(re.findall(r'name:\s*"([^"]+)"', tools_block.group(1)))


def server_call_mappings(source: str) -> dict[str, str]:
    pairs = re.findall(
        r'if \(name === "([^"]+)"\)\s*\{\s*return runPython\("([^"]+)"',
        source,
        re.S,
    )
    return dict(pairs)


def python_actions(source: str) -> set[str]:
    actions_block = re.search(r"ACTIONS\s*=\s*\{(.*?)\n\}", source, re.S)
    if not actions_block:
        return set()
    return set(re.findall(r'"([^"]+)"\s*:', actions_block.group(1)))


def check_static_contracts() -> CheckSet:
    checks = CheckSet()
    server = read_text(SERVER_PATH)
    py_source = read_text(PYTHON_PATH)
    manifest = read_json(MANIFEST_PATH)
    package = read_json(PACKAGE_PATH)
    mcp = read_json(MCP_PATH)
    text = all_project_text()

    manifest_version = manifest["version"].split("+", 1)[0]
    server_version = re.search(r'SERVER_VERSION = "([^"]+)"', server)
    checks.check(bool(server_version), "server exposes SERVER_VERSION")
    checks.check(package["version"] == manifest_version, "package version matches manifest base")
    checks.check(
        bool(server_version) and server_version.group(1) == package["version"],
        "server version matches package version",
    )
    mcp_server = mcp.get("mcpServers", {}).get("screen_guardian")
    checks.check(bool(mcp_server), "MCP config exposes screen_guardian server")
    if mcp_server:
        checks.check(mcp_server.get("command") == "node", "MCP config uses node command")
        args = mcp_server.get("args") or []
        entry = ROOT / args[0] if args else None
        checks.check(bool(entry and entry.exists()), "MCP config entrypoint exists", str(entry) if entry else "")

    tools = server_tools(server)
    mappings = server_call_mappings(server)
    actions = python_actions(py_source)
    required = set(REQUIRED_TOOLS)
    checks.check(required <= tools, "MCP tool list covers required tools", ", ".join(sorted(required - tools)))
    checks.check(tools <= set(mappings), "each MCP tool has callTool mapping", ", ".join(sorted(tools - set(mappings))))
    checks.check(
        set(mappings.values()) <= actions,
        "each callTool Python action exists",
        ", ".join(sorted(set(mappings.values()) - actions)),
    )

    flags = python_dict_keys("DEFAULT_FEATURE_FLAGS", py_source)
    catalog = python_dict_keys("FEATURE_CATALOG", py_source)
    required_flags = set(REQUIRED_FEATURE_FLAGS)
    checks.check(required_flags <= flags, "feature flags cover required modules", ", ".join(sorted(required_flags - flags)))
    checks.check(flags <= catalog, "feature catalog documents every flag", ", ".join(sorted(flags - catalog)))

    for label, terms in DESIGN_COVERAGE.items():
        checks.check(any(term in text for term in terms), f"design coverage: {label}")
    for label, terms in SCENARIO_COVERAGE.items():
        checks.check(any(term in text for term in terms), f"scenario coverage: {label}")

    boundary_terms = {
        "does not execute arbitrary": ["does not execute arbitrary"],
        "does not silently start": ["does not silently start", "do not silently start"],
        "do not upload screenshots automatically": ["do not upload screenshots automatically"],
        "inactive features should": ["inactive features should"],
    }
    for label, terms in boundary_terms.items():
        checks.check(any(term in text for term in terms), f"safety boundary documented: {label}")

    guardian_terms = {
        "guardian_check reports status without capture": ["action_guardian_check", "no screenshot", "recommended_next"],
        "guardian_perceive read_text maps to text preprocess": ['task == "read_text"', '"preprocess"] = "text"', '"analyze"] = True'],
        "guardian_perceive hold_file marks local file only": ['task == "hold_file"', '"context_policy"] = "hold_file"', '"marked_file_only"] = True'],
        "guardian_perceive watch_change uses bounded watch": ['task == "watch_change"', "action_watch_screen"],
        "guardian_prepare_workflow writes envelopes only": ["action_guardian_prepare_workflow", "action_prepare_model_request", "action_prepare_decision_request", "action_prepare_monitor_tick"],
        "render timing has bounded delay and retry": ["capture_settle_delay_ms_max", "capture_render_retry_count_max", "capture_render_retry_interval_ms_max"],
        "window capture retries blank frames by default": ["default_wait_for_nonblank=True", "image_blank_metrics", "render_retry_options"],
        "registered commands map through a registry": ["CAPABILITY_COMMANDS", "action_guardian_list_commands", "action_guardian_run_command"],
        "run_command rejects arbitrary code strings": ["guardian_run_command only runs registry entries", "command_id is required"],
        "break-glass exec is gated": ['require_feature("raw_local_exec"', "user_confirmed=true is required", "append_exec_audit"],
    }
    combined_source = (server + "\n" + py_source).lower()
    for label, terms in guardian_terms.items():
        checks.check(all(term.lower() in combined_source for term in terms), f"ai-first contract: {label}")

    if TEXT_ENCODING_PATH.exists():
        completed = subprocess.run(
            [sys.executable, str(TEXT_ENCODING_PATH)],
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
        detail = "\n".join(part for part in (completed.stdout.strip(), completed.stderr.strip()) if part)
        checks.check(completed.returncode == 0, "text encoding guard passes", detail[-1000:])
    else:
        checks.check(False, "text encoding guard passes", str(TEXT_ENCODING_PATH))

    return checks


def mcp_request(request_id: int, method: str, params: dict | None = None) -> dict:
    request: dict = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    return request


def tool_request(request_id: int, name: str, arguments: dict | None = None) -> dict:
    return mcp_request(
        request_id,
        "tools/call",
        {"name": name, "arguments": arguments or {}},
    )


def parse_tool_payload(response: dict) -> dict:
    if "error" in response:
        return {"ok": False, "error": response["error"]}
    result = response.get("result") or {}
    content = result.get("content") or []
    if not content:
        return {"ok": True}
    text = content[0].get("text", "{}")
    return json.loads(text)


def run_mcp_stress(loops: int) -> CheckSet:
    checks = CheckSet()
    messages: list[dict] = [
        mcp_request(1, "initialize", {"protocolVersion": "2024-11-05"}),
        mcp_request(2, "tools/list"),
        tool_request(3, "guardian_check", {"detail": "short"}),
        tool_request(4, "guardian_list_commands", {"category": "diagnostic"}),
        tool_request(5, "guardian_run_command", {"command_id": "diagnostic.readiness"}),
    ]
    request_id = 6
    stress_ids = [f"sg-stress-{i}" for i in range(loops)]

    with tempfile.TemporaryDirectory(prefix="screen-guardian-stress-") as tmp:
        for i, base_id in enumerate(stress_ids):
            policy_id = f"{base_id}-policy"
            profile_id = f"{base_id}-profile"
            messages.extend(
                [
                    tool_request(
                        request_id,
                        "set_decision_policy",
                        {
                            "id": policy_id,
                            "role": "monitor_decision",
                            "mode": "function_route",
                            "objective": "Choose the lowest-cost useful capture or narration action.",
                            "candidates": [
                                {"action": "capture_screen", "cost": 2},
                                {"action": "capture_window", "cost": 1},
                                {"action": "prepare_model_request", "cost": 3},
                                {"action": "noop", "cost": 0},
                            ],
                            "constraints": [
                                {"kind": "context_budget", "max_images": 2},
                                {"kind": "privacy", "local_only": True},
                            ],
                            "settings": {"temperature": 0.1, "quality": "stress"},
                        },
                    ),
                    tool_request(
                        request_id + 1,
                        "prepare_decision_request",
                        {
                            "policy_id": policy_id,
                            "output_dir": tmp,
                            "observation": {
                                "iteration": i,
                                "web_change": i % 2 == 0,
                                "error_text": "stress error" if i % 5 == 0 else "",
                            },
                            "candidates": [
                                {"action": "capture_window"},
                                {"action": "prepare_model_request"},
                                {"action": "noop"},
                            ],
                        },
                    ),
                    tool_request(
                        request_id + 2,
                        "set_monitor_profile",
                        {
                            "id": profile_id,
                            "project_id": "screen-guardian-stress",
                            "workflow_id": "contract-validation",
                            "media": ["screen", "webpage", "audio"],
                            "schedule": {"mode": "periodic", "interval_seconds": 15},
                            "targets": [
                                {"type": "webpage", "change_signal": "dom_hash"},
                                {"type": "program", "process_name": "example.exe"},
                                {"type": "audio_device", "source": "system_loopback"},
                            ],
                            "triggers": [
                                {"type": "web_change"},
                                {"type": "window_change"},
                                {"type": "error_text"},
                                {"type": "model_feature"},
                                {"type": "audio_silence"},
                            ],
                            "actions": [
                                {"name": "capture_screen"},
                                {"name": "capture_window"},
                                {"name": "record_audio"},
                                {"name": "prepare_model_request"},
                            ],
                            "decision_policy_id": policy_id,
                        },
                    ),
                    tool_request(
                        request_id + 3,
                        "prepare_monitor_tick",
                        {
                            "profile_id": profile_id,
                            "output_dir": tmp,
                            "observations": {
                                "iteration": i,
                                "dom_hash_changed": i % 2 == 0,
                                "window_changed": i % 3 == 0,
                                "audio_rms": 0.0,
                            },
                            "detected_features": [
                                {"type": "model_feature", "name": "stress_feature", "confidence": 0.5},
                                {"type": "audio_silence", "confidence": 0.9},
                            ],
                        },
                    ),
                    tool_request(
                        request_id + 4,
                        "guardian_prepare_workflow",
                        {
                            "workflow_type": "model_request",
                            "source_path": str(Path(tmp) / f"{base_id}.png"),
                            "objective": "Prepare a compact local narration request for contract validation.",
                            "settings": {"quality": "stress"},
                            "project_id": "screen-guardian-stress",
                            "workflow_id": "ai-first",
                            "output_dir": tmp,
                        },
                    ),
                    tool_request(
                        request_id + 5,
                        "guardian_prepare_exec",
                        {
                            "language": "python",
                            "code": "print('screen-guardian stress prepared exec')",
                            "reason": "Contract validation prepare-only envelope.",
                            "output_dir": tmp,
                        },
                    ),
                    tool_request(request_id + 6, "list_monitor_profiles", {"project_id": "screen-guardian-stress"}),
                    tool_request(request_id + 7, "set_monitor_profile", {"id": profile_id, "remove": True}),
                    tool_request(request_id + 8, "set_decision_policy", {"id": policy_id, "remove": True}),
                ]
            )
            request_id += 9

        messages.extend(
            [
                tool_request(request_id, "list_decision_policies", {"role": "monitor_decision"}),
                tool_request(request_id + 1, "list_monitor_profiles", {"project_id": "screen-guardian-stress"}),
            ]
        )

        payload = "\n".join(json.dumps(message, separators=(",", ":")) for message in messages) + "\n"
        completed = subprocess.run(
            ["node", str(SERVER_PATH)],
            input=payload,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(ROOT),
            timeout=max(30, loops * 2),
            check=False,
        )

        checks.check(completed.returncode == 0, "stress MCP server exits cleanly", completed.stderr[-1000:])
        responses = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
        checks.check(len(responses) == len(messages), "stress response count matches request count")
        package_version = read_json(PACKAGE_PATH)["version"]
        initialized_version = ((responses[0].get("result") or {}).get("serverInfo") or {}).get("version")
        checks.check(initialized_version == package_version, "runtime initialize version matches package version")
        listed_tools = {tool.get("name") for tool in (responses[1].get("result") or {}).get("tools", [])}
        checks.check(set(REQUIRED_TOOLS) <= listed_tools, "runtime tools/list covers required tools")

        failed_payloads: list[str] = []
        for response in responses:
            if response.get("id") in (1, 2):
                continue
            payload_data = parse_tool_payload(response)
            if not payload_data.get("ok", False):
                failed_payloads.append(f"id={response.get('id')} {payload_data}")

        checks.check(not failed_payloads, "stress tool calls all return ok", failed_payloads[:3][0] if failed_payloads else "")

        generated_files = list(Path(tmp).glob("*.json"))
        expected_files = loops * 4
        checks.check(len(generated_files) == expected_files, "stress generated expected envelope count", str(len(generated_files)))

        last_decisions = parse_tool_payload(responses[-2])
        last_profiles = parse_tool_payload(responses[-1])
        leaked_policy = any(item.get("id", "").startswith("sg-stress-") for item in last_decisions.get("policies", []))
        leaked_profile = any(item.get("id", "").startswith("sg-stress-") for item in last_profiles.get("profiles", []))
        checks.check(not leaked_policy, "stress decision policies cleaned up")
        checks.check(not leaked_profile, "stress monitor profiles cleaned up")

    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Screen Guardian contracts.")
    parser.add_argument("--stress", action="store_true", help="Run bounded MCP stress calls.")
    parser.add_argument("--stress-loops", type=int, default=int(os.environ.get("SCREEN_GUARDIAN_STRESS_LOOPS", "25")))
    args = parser.parse_args()

    if args.stress_loops > MAX_STRESS_LOOPS:
        print(f"FAIL stress loops must be <= {MAX_STRESS_LOOPS}")
        return 1

    checks = check_static_contracts()
    if args.stress:
        checks.extend(run_mcp_stress(max(1, args.stress_loops)))

    for label in checks.passed:
        print(f"PASS {label}")
    for label in checks.failed:
        print(f"FAIL {label}")

    print(f"\nSummary: {len(checks.passed)} passed, {len(checks.failed)} failed")
    return 1 if checks.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
