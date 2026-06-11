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
import site
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
CURRENT_PYTHON_USERBASE = getattr(site, "USER_BASE", "") or ""


REQUIRED_TOOLS = [
    "guardian_check",
    "guardian_perceive",
    "guardian_survey_windows",
    "guardian_prepare_workflow",
    "guardian_list_commands",
    "guardian_run_command",
    "guardian_prepare_exec",
    "guardian_run_exec",
    "list_capture_routes",
    "prepare_capture_chain",
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
    "prepare_webpage_capture",
    "capture_webpage",
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
    "capture_chains",
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
    "webpage_capture",
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
    "capture routes and chains": ["capture routes", "prepare_capture_chain", "nested_scroll"],
    "positive freedom": ["positive freedom", "expand user agency"],
    "negative freedom": ["negative freedom", "forced upgrades", "forced background services"],
    "compatibility fallback": ["fallback", "compatibility", "older windows", "constrained systems"],
    "local control": ["local-only", "saved locally", "do not upload", "local cache"],
    "optional dependencies": ["optional", "inactive features", "feature flags"],
    "context economy": ["context", "downscale", "preprocess"],
    "no hidden scheduler": ["does not silently start", "does not start a background", "no-background-service"],
    "arbitrary decisions": ["arbitrary-complexity", "decision policies", "function_route"],
    "tool layering": ["core tools", "local control tools", "experimental envelope tools"],
    "whitepaper thesis": ["whitepaper", "desktop situation index", "machine-readable receipts"],
    "low-hamming invocation": ["low-hamming-distance", "target_id", "snapshot_id"],
    "perception subscription": ["perception subscriptions", "basic", "agentic interpretation"],
}


SCENARIO_COVERAGE = {
    "ai quick look facade": ["quick look", "guardian_perceive", "quick_look"],
    "hold file context": ["hold file", "hold_file", "file_marked_only"],
    "render timing capture": ["delay_seconds", "wait_for_nonblank", "render_retry_count", "render_guard"],
    "stackable capture modes": ["capture_modes", "wait_render", "wait_buffer", "wait_error"],
    "capture guard checks": ["guard_checks", "minimized_window", "offscreen_window", "tiny_capture", "stale_frame", "occlusion_risk"],
    "full webpage capture": ["full-page", "capture_webpage", "prepare_webpage_capture", "playwright"],
    "registered command runtime": ["guardian_list_commands", "guardian_run_command", "command_id"],
    "break-glass execution": ["guardian_prepare_exec", "guardian_run_exec", "raw_local_exec"],
    "older system capture": ["older windows", "native screen capture", "computer use"],
    "window/program capture": ["program window", "window", "process name"],
    "multi-window survey": ["guardian_survey_windows", "capture_mode", "hold_file"],
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
        ROOT / "docs" / "CAPTURE_GUARDS.md",
        ROOT / "docs" / "COMPATIBILITY.md",
        ROOT / "docs" / "EVALUATION.md",
        ROOT / "docs" / "MODELS.md",
        ROOT / "docs" / "RELATED_PROJECTS.md",
        ROOT / "docs" / "WEBPAGE_CAPTURE.md",
        ROOT / "docs" / "WHITEPAPER.md",
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
        "guardian_perceive defaults fast and supports stackable modes": ["apply_guardian_capture_modes", "default_fast", "wait_buffer", "wait_error"],
        "guardian_survey_windows has bounded status and capture modes": ["action_guardian_survey_windows", "window_survey_window_count_max", "window_survey_capture_count_max", "capture_mode"],
        "guardian_prepare_workflow writes envelopes only": ["action_guardian_prepare_workflow", "action_prepare_model_request", "action_prepare_decision_request", "action_prepare_monitor_tick", "action_prepare_capture_chain"],
        "capture routes distinguish desktop application webpage": ["CAPTURE_ROUTE_CATALOG", '"desktop"', '"application"', '"webpage"', '"nested_scroll"'],
        "quiet window capture is default strategy": ["quiet_capture_preferred", "no_foreground_activation", "quiet_preferred_default", "visible-screen bbox fallback"],
        "default MCP surface is core-sized": ["CORE_TOOL_NAMES", "SCREEN_GUARDIAN_TOOL_SURFACE", "visibleTools"],
        "CLI supports stdin JSON": ["--stdin", "sys.stdin.read", "Invalid JSON request"],
        "window matching returns candidates": ["WindowMatchError", "candidate_windows", "approximate_matches"],
        "stress uses isolated config": ["screen-guardian-stress", '"APPDATA"', "SCREEN_GUARDIAN_TOOL_SURFACE"],
        "capture chain is prepare only": ["action_prepare_capture_chain", "capture_chain_request", "does not execute screenshots, browser navigation, scripts, APIs, subagents, or background schedulers"],
        "nested scroll container capture is optional": ["scroll_container", "frame_selector", "capture_scroll_container"],
        "render timing has bounded delay and retry": ["capture_settle_delay_ms_max", "capture_render_retry_count_max", "capture_render_retry_interval_ms_max"],
        "render guard returns decision actions before saving suspected blank output": ["render_guard_warning_payload", "suspected_unrendered", "available_actions", "force_capture_now", "capture_later", "auto_detect_render_then_capture"],
        "guard decision is not mistaken for saved file": ['"saved": False', '"result_state": "decision_required"', "ok=true", "saved=false"],
        "capture guard checks document fallback exceptions": ["DEFAULT_GUARD_CHECKS = [\"unrendered\"]", "CAPTURE_GUARD_CHECKS", "bbox_identity_mismatch"],
        "direct hwnd client guard detects browser blank content": ["window_client_low_information", "window_client_content_status", "pillow-imagegrab-bbox-after-low-info-window-client"],
        "bbox fallback identity guard": ["bbox_identity_probe", "bbox_identity_mismatch", "allow_unverified_bbox_fallback"],
        "guardian facade forwards fallback controls": ["guardian_base_context", '"quiet_preferred"', '"render_guard_confirmed"', '"allow_unverified_bbox_fallback"'],
        "mcp child timeout bounds hung scripts": ["childTimeoutMs", "SCREEN_GUARDIAN_MCP_CHILD_TIMEOUT_MS", "Screen Guardian runtime timed out"],
        "mcp runtime reports active root and blocks mixed state writes": ["active_script_root", "mixed_runtime", "MIXED_ROOT_BLOCKED_ACTIONS", "runtime_file_sha256"],
        "mcp child output is bounded and framed": ["SCREEN_GUARDIAN_MCP_STDOUT_BYTES_MAX", "SCREEN_GUARDIAN_MCP_STDERR_BYTES_MAX", "parseRuntimeJson", "killProcessTree"],
        "cache runtime source fallback is explicit": ["runningFromPluginCache", "SCREEN_GUARDIAN_ALLOW_SOURCE_FALLBACK", "SCREEN_GUARDIAN_PLUGIN_ROOT"],
        "windows smoke verifies real watch change": ["launch_changing_window", "guardian_perceive_watch_change_real_event", "watch_change did not produce a real change event"],
        "read_text is text optimization not OCR": ["text_handling", "text_optimized_image", "ocr_available"],
        "webpage route reports inactive optional adapter": ["inactive_optional_adapter", "webpage_capture", "activation_hint"],
        "display indexes expose coordinate space": ["coordinate_space", "virtual_desktop", "physical_display"],
        "render-aware command defaults to wait guard": ['"id": "perceive.window.after_render"', '"render_guard": "wait"'],
        "webpage capture stays optional": ["action_prepare_webpage_capture", "action_capture_webpage", "webpage_capture", "optional-web-requirements.txt"],
        "webpage full-page command is registered": ['"id": "perceive.webpage.full_page"', '"maps_to": "capture_webpage"'],
        "window capture retries blank frames by default": ["default_wait_for_nonblank=True", "image_blank_metrics", "render_retry_options"],
        "registered commands map through a registry": ["CAPABILITY_COMMANDS", "action_guardian_list_commands", "action_guardian_run_command"],
        "run_command rejects arbitrary code strings": ["guardian_run_command only runs registry entries", "command_id is required"],
        "break-glass exec is gated": ['require_feature("raw_local_exec"', "user_confirmed=true is required", "append_exec_audit"],
    }
    validator_source = read_text(Path(__file__))
    combined_source = (server + "\n" + py_source + "\n" + validator_source).lower()
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
        tmp_path = Path(tmp)
        appdata_dir = tmp_path / "appdata"
        output_dir = tmp_path / "out"
        appdata_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        stress_env = os.environ.copy()
        stress_env.update(
            {
                "APPDATA": str(appdata_dir),
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUSERBASE": os.environ.get("PYTHONUSERBASE") or CURRENT_PYTHON_USERBASE,
                "SCREEN_GUARDIAN_PYTHON": sys.executable,
                "SCREEN_GUARDIAN_TOOL_SURFACE": "full",
            }
        )
        messages.extend(
            [
                tool_request(request_id, "list_capture_routes", {"include_examples": True}),
                tool_request(
                    request_id + 1,
                    "prepare_capture_chain",
                    {
                        "objective": "Prepare a quiet nested-scroll table capture chain for contract validation.",
                        "route": "nested_scroll",
                        "trigger": {"type": "selector_visible", "selector": ".table-scroll"},
                        "steps": [
                            {
                                "tool": "capture_webpage",
                                "args": {"mode": "scroll_container", "selector": ".table-scroll"},
                            },
                            {"tool": "prepare_model_request", "args": {"prompt": "Summarize the table compactly."}},
                        ],
                        "output_dir": str(output_dir),
                        "source_label": "capture-chain-direct",
                    },
                ),
                tool_request(
                    request_id + 2,
                    "guardian_prepare_workflow",
                    {
                        "workflow_type": "capture_chain",
                        "objective": "Prepare a delayed application-window screenshot chain for contract validation.",
                        "route": "application",
                        "trigger": {"type": "delay", "seconds": 2},
                        "steps": [{"tool": "capture_window", "args": {"render_guard": "wait"}}],
                        "settings": {"quiet": True},
                        "output_dir": str(output_dir),
                        "source_label": "capture-chain-facade",
                    },
                ),
            ]
        )
        request_id += 3

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
                            "output_dir": str(output_dir),
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
                            "output_dir": str(output_dir),
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
                            "source_path": str(output_dir / f"{base_id}.png"),
                            "objective": "Prepare a compact local narration request for contract validation.",
                            "settings": {"quality": "stress"},
                            "project_id": "screen-guardian-stress",
                            "workflow_id": "ai-first",
                            "output_dir": str(output_dir),
                        },
                    ),
                    tool_request(
                        request_id + 5,
                        "guardian_prepare_exec",
                        {
                            "language": "python",
                            "code": "print('screen-guardian stress prepared exec')",
                            "reason": "Contract validation prepare-only envelope.",
                            "output_dir": str(output_dir),
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
        timeout_seconds = max(120, loops * 8)
        try:
            completed = subprocess.run(
                ["node", str(SERVER_PATH)],
                input=payload,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(ROOT),
                env=stress_env,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            checks.check(
                False,
                "stress MCP server exits cleanly",
                f"timeout after {timeout_seconds}s; isolated APPDATA was {appdata_dir}; stdout_tail={(exc.stdout or '')[-500:]} stderr_tail={(exc.stderr or '')[-500:]}",
            )
            return checks

        checks.check(completed.returncode == 0, "stress MCP server exits cleanly", completed.stderr[-1000:])
        responses = []
        parse_failures = []
        for line in completed.stdout.splitlines():
            if not line.strip():
                continue
            try:
                responses.append(json.loads(line))
            except Exception as exc:
                parse_failures.append(f"{exc}: {line[:300]}")
        checks.check(not parse_failures, "stress responses are valid JSON", parse_failures[0] if parse_failures else "")
        checks.check(len(responses) == len(messages), "stress response count matches request count")
        if len(responses) < len(messages):
            return checks
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

        generated_files = list(output_dir.glob("*.json"))
        expected_files = loops * 4 + 2
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
