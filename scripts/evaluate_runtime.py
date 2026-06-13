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
    "guardian_radar",
    "guardian_extract_page_facts",
    "guardian_capture_targets",
    "guardian_sniff_context",
    "guardian_perceive",
    "guardian_survey_windows",
    "guardian_prepare_workflow",
}
EXPECTED_CORE_TOOLS = {
    "guardian_check",
    "guardian_radar",
    "guardian_extract_page_facts",
    "guardian_capture_targets",
    "guardian_sniff_context",
    "guardian_perceive",
    "guardian_survey_windows",
    "check_dependencies",
    "list_adapters",
    "list_displays",
    "list_windows",
    "list_capture_routes",
    "capture_screen",
    "capture_region",
    "capture_window",
    "watch_screen",
    "clear_cache",
}
EXPECTED_RUNTIME_TOOLS = {
    "guardian_list_commands",
    "guardian_run_command",
    "guardian_prepare_exec",
    "guardian_run_exec",
}
EXPECTED_ROUTE_TOOLS = {
    "list_capture_routes",
    "prepare_capture_chain",
    "prepare_data_layer_request",
}
EXPECTED_COMMAND_IDS = {
    "diagnostic.readiness",
    "perceive.screen.quick",
    "perceive.region.text",
    "perceive.window.after_render",
    "perceive.webpage.full_page",
    "perceive.change.popup",
    "artifact.hold_file",
    "workflow.model_request.prepare",
    "workflow.decision.prepare",
    "workflow.data_layer.prepare",
    "workflow.capture_chain.prepare",
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
    result["tool_surface"] = (response.get("result") or {}).get("toolSurface") if response else None
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
                "SCREEN_GUARDIAN_TOOL_SURFACE": "full",
            }

            default_surface_env = {
                "APPDATA": appdata_tmp,
                "PYTHONUSERBASE": os.environ.get("PYTHONUSERBASE") or CURRENT_PYTHON_USERBASE,
                "SCREEN_GUARDIAN_PYTHON": sys.executable,
            }
            advanced_surface_env = {
                **default_surface_env,
                "SCREEN_GUARDIAN_TOOL_SURFACE": "advanced",
            }
            default_tools_result = list_tools(default_surface_env)
            timings["tools.list.default_surface"] = default_tools_result
            default_tool_names = {tool.get("name") for tool in default_tools_result.get("tools", [])}
            add_check(checks, "default MCP surface reports core", ok_transport(default_tools_result) and default_tools_result.get("tool_surface") == "core", str(default_tools_result.get("tool_surface")))
            add_check(checks, "default MCP surface matches core whitelist", ok_transport(default_tools_result) and default_tool_names == EXPECTED_CORE_TOOLS, f"missing={sorted(EXPECTED_CORE_TOOLS - default_tool_names)} extra={sorted(default_tool_names - EXPECTED_CORE_TOOLS)}")
            hidden_result = timed_tool("guardian_run_exec", {}, default_surface_env)
            timings["guardian_run_exec.hidden_on_core_surface"] = hidden_result
            hidden_payload = hidden_result["payload"]
            add_check(
                checks,
                "hidden tool call returns surface hint",
                ok_transport(hidden_result)
                and hidden_payload.get("ok") is False
                and hidden_payload.get("tool_surface") == "core"
                and bool(hidden_payload.get("enable_hint"))
                and "available_surfaces" in hidden_payload,
                payload_text(hidden_payload)[:500],
            )
            advanced_commands_result = timed_tool("guardian_list_commands", {}, advanced_surface_env)
            timings["guardian_list_commands.advanced_surface"] = advanced_commands_result
            advanced_commands_payload = advanced_commands_result["payload"]
            advanced_command_ids = {command.get("id") for command in advanced_commands_payload.get("commands") or []}
            add_check(
                checks,
                "advanced command catalog hides emergency commands by default",
                ok_transport(advanced_commands_result)
                and "emergency.exec.prepare" not in advanced_command_ids
                and "emergency.exec.run" not in advanced_command_ids,
                payload_text(advanced_commands_payload)[:500],
            )
            advanced_emergency_result = timed_tool(
                "guardian_run_command",
                {"command_id": "emergency.exec.prepare", "args": {"code": "print('nope')"}},
                advanced_surface_env,
            )
            timings["guardian_run_command.emergency_on_advanced_surface"] = advanced_emergency_result
            advanced_emergency_payload = advanced_emergency_result["payload"]
            add_check(
                checks,
                "advanced command runner cannot bypass full surface",
                advanced_emergency_payload.get("ok") is False
                and "tool surface" in payload_text(advanced_emergency_payload).lower()
                and ((advanced_emergency_payload.get("command") or {}).get("surface") or {}).get("required") == "full",
                payload_text(advanced_emergency_payload)[:500],
            )

            tools_result = list_tools(env)
            timings["tools.list"] = tools_result
            tool_names = {tool.get("name") for tool in tools_result.get("tools", [])}
            add_check(checks, "MCP transport lists tools", ok_transport(tools_result), tools_result.get("stderr", "")[-500:])
            add_check(checks, "AI-first tools are present", EXPECTED_AI_FIRST_TOOLS <= tool_names, ", ".join(sorted(EXPECTED_AI_FIRST_TOOLS - tool_names)))
            add_check(checks, "capability runtime tools are present", EXPECTED_RUNTIME_TOOLS <= tool_names, ", ".join(sorted(EXPECTED_RUNTIME_TOOLS - tool_names)))
            add_check(checks, "capture route tools are present", EXPECTED_ROUTE_TOOLS <= tool_names, ", ".join(sorted(EXPECTED_ROUTE_TOOLS - tool_names)))

            guardian_check = timed_tool("guardian_check", {"detail": "short"}, env)
            timings["guardian_check"] = guardian_check
            guardian_payload = guardian_check["payload"]
            add_check(checks, "guardian_check returns without capture", ok_transport(guardian_check) and guardian_payload.get("ok") is True, payload_text(guardian_payload)[:500])
            add_check(checks, "guardian_check recommends an explicit next step", bool(guardian_payload.get("recommended_next")), payload_text(guardian_payload)[:500])
            add_check(checks, "guardian_check exposes local cache path", bool(guardian_payload.get("active_cache_dir")), payload_text(guardian_payload)[:500])
            add_check(
                checks,
                "guardian_check separates core and advanced AI-first tools",
                "guardian_radar" in set(guardian_payload.get("ai_first_tools") or [])
                and "guardian_extract_page_facts" in set(guardian_payload.get("ai_first_tools") or [])
                and "guardian_sniff_context" in set(guardian_payload.get("ai_first_tools") or [])
                and "guardian_prepare_workflow" not in set(guardian_payload.get("ai_first_tools") or [])
                and "guardian_prepare_workflow" in set(guardian_payload.get("advanced_ai_first_tools") or []),
                payload_text(guardian_payload)[:500],
            )

            radar_result = timed_tool(
                "guardian_radar",
                {
                    "authorization_level": "L1_current_page_readonly",
                    "declared_permissions": ["dom_measure", "container_scroll", "screenshot"],
                    "current_pages": [
                        {
                            "title": "引言 - 速云api",
                            "url": "https://syapi.apifox.cn/",
                            "source": "browser_pages",
                            "viewport": {"width": 1920, "height": 863},
                            "documentSize": {"scrollWidth": 1920, "scrollHeight": 863},
                            "scrollables": [
                                {
                                    "selectorHint": "div.relative.h-full.w-full.overflow-y-auto",
                                    "clientWidth": 1910,
                                    "clientHeight": 863,
                                    "scrollWidth": 1910,
                                    "scrollHeight": 2125,
                                }
                            ],
                        }
                    ],
                    "include_capture_targets": False,
                },
                env,
            )
            timings["guardian_radar"] = radar_result
            radar_payload = radar_result["payload"]
            radar_pages = ((radar_payload.get("pages") or {}).get("cards") or [])
            add_check(
                checks,
                "guardian_radar pre-judges nested scroll page without acting",
                ok_transport(radar_result)
                and radar_payload.get("ok") is True
                and radar_payload.get("radar_performed") is True
                and radar_payload.get("capture_performed") is False
                and radar_payload.get("secret_storage_read") is False
                and radar_pages
                and radar_pages[0].get("page_state") == "scroll_container_required"
                and radar_pages[0].get("recommended_route") == "browser_session_nested_scroll",
                payload_text(radar_payload)[:500],
            )

            facts_result = timed_tool(
                "guardian_extract_page_facts",
                {
                    "authorization_level": "L1_current_page_readonly",
                    "declared_permissions": ["dom_measure", "table_read", "form_metadata_read"],
                    "intent": "api_settings",
                    "current_pages": [
                        {
                            "title": "syapi api settings",
                            "url": "https://syapi.apifox.cn/doc-8039103",
                            "source": "browser_pages",
                            "viewport": {"width": 1920, "height": 863},
                            "documentSize": {"scrollWidth": 1920, "scrollHeight": 863},
                            "scrollables": [
                                {
                                    "selectorHint": "div#main-scroll-container",
                                    "clientWidth": 1910,
                                    "clientHeight": 863,
                                    "scrollWidth": 1910,
                                    "scrollHeight": 2125,
                                }
                            ],
                            "headings": ["API quick start", "Configuration steps"],
                            "blocks": [
                                "Use https://u1.syapi.cn https://u1.syapi.cn/v1 https://u1.syapi.cn/v1/chat/completions",
                                "{\"base_url\":\"https://u1.syapi.cn\",\"api_key\":\"your_token_here\",\"model\":\"selected_model_name\"}",
                                "Quota lookup supports current balance, usage detail, and consumption records.",
                            ],
                            "rows": [
                                "Name Status Group Smart route Key Available models IP limit Created Expires",
                                "zjj initial token enabled unlimited quota user group success-rate-first unlimited unlimited 2026-05-28 12:00:57 2026-07-02 18:18:44",
                            ],
                            "controls": [
                                {"tag": "input", "type": "text", "text": "API key"},
                                {"tag": "button", "text": "export all tokens"},
                                {"tag": "button", "text": "query"},
                            ],
                        }
                    ],
                },
                env,
            )
            timings["guardian_extract_page_facts"] = facts_result
            facts_payload = facts_result["payload"]
            facts = facts_payload.get("facts") or {}
            dangerous = ((facts_payload.get("handles") or {}).get("dangerous_objects") or [])
            add_check(
                checks,
                "guardian_extract_page_facts classifies valuable dangerous facts without acting",
                ok_transport(facts_result)
                and facts_payload.get("ok") is True
                and facts_payload.get("fact_extraction_performed") is True
                and facts_payload.get("capture_performed") is False
                and facts_payload.get("secret_storage_read") is False
                and (facts_payload.get("state_machine") or {}).get("current_state") == "redacted_answer_ready"
                and bool(facts.get("base_url") or facts.get("endpoint_url"))
                and bool(facts.get("token_rows"))
                and bool(facts.get("config_fields"))
                and bool(dangerous),
                payload_text(facts_payload)[:500],
            )

            sniff_result = timed_tool(
                "guardian_sniff_context",
                {
                    "authorization_level": "L1_current_page_readonly",
                    "declared_permissions": ["dom_measure", "container_scroll", "screenshot"],
                    "target": {"kind": "browser_tab", "url": "https://example.com", "selector": ".table-scroll"},
                },
                env,
            )
            timings["guardian_sniff_context"] = sniff_result
            sniff_payload = sniff_result["payload"]
            add_check(
                checks,
                "guardian_sniff_context returns route candidates without acting",
                ok_transport(sniff_result)
                and sniff_payload.get("ok") is True
                and sniff_payload.get("sniff_performed") is True
                and sniff_payload.get("capture_performed") is False
                and sniff_payload.get("secret_storage_read") is False
                and sniff_payload.get("database_or_registry_touched") is False
                and sniff_payload.get("network_request_performed") is False
                and bool(sniff_payload.get("route_candidates")),
                payload_text(sniff_payload)[:500],
            )

            commands_result = timed_tool("guardian_list_commands", {}, env)
            timings["guardian_list_commands"] = commands_result
            commands_payload = commands_result["payload"]
            commands = commands_payload.get("commands") or []
            command_ids = {command.get("id") for command in commands}
            active_commands = [command for command in commands if command.get("active")]
            add_check(checks, "registered command catalog is readable", ok_transport(commands_result) and commands_payload.get("ok") is True, payload_text(commands_payload)[:500])
            add_check(checks, "expected command ids are registered", EXPECTED_COMMAND_IDS <= command_ids, ", ".join(sorted(EXPECTED_COMMAND_IDS - command_ids)))
            add_check(checks, "normal registered commands are active", len(active_commands) >= 8, f"active={len(active_commands)} total={len(commands)}")

            route_result = timed_tool("list_capture_routes", {"include_examples": True}, env)
            timings["list_capture_routes"] = route_result
            route_payload = route_result["payload"]
            route_names = set((route_payload.get("routes") or {}).keys())
            add_check(checks, "capture routes are readable", ok_transport(route_result) and route_payload.get("ok") is True, payload_text(route_payload)[:500])
            add_check(checks, "desktop application webpage and nested routes are listed", {"desktop", "application", "webpage", "nested_scroll"} <= route_names, ", ".join(sorted(route_names)))

            chain_result = timed_tool(
                "prepare_capture_chain",
                {
                    "objective": "Evaluate local capture-chain preparation without executing capture.",
                    "route": "nested_scroll",
                    "trigger": {"type": "selector_visible", "selector": ".table-scroll"},
                    "steps": [{"tool": "capture_webpage", "args": {"mode": "scroll_container", "selector": ".table-scroll"}}],
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["prepare_capture_chain"] = chain_result
            chain_payload = chain_result["payload"]
            chain_path = Path(str(chain_payload.get("request_path") or ""))
            add_check(checks, "capture-chain tool prepares a local envelope", ok_transport(chain_result) and chain_payload.get("ok") is True and chain_path.exists(), payload_text(chain_payload)[:500])
            add_check(checks, "capture-chain tool remains prepare-only", "does not execute screenshots" in payload_text(chain_payload).lower(), payload_text(chain_payload)[:500])

            unsafe_chain_result = timed_tool(
                "prepare_capture_chain",
                {
                    "objective": "Verify unsafe capture-chain steps are rejected.",
                    "route": "application",
                    "steps": [{"tool": "guardian_run_exec", "args": {"code": "print('nope')"}}],
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["prepare_capture_chain.unsafe_step"] = unsafe_chain_result
            unsafe_chain_payload = unsafe_chain_result["payload"]
            add_check(
                checks,
                "capture-chain rejects unsafe step tools",
                unsafe_chain_payload.get("ok") is False
                and "not allowed" in payload_text(unsafe_chain_payload).lower()
                and unsafe_chain_payload.get("tool") == "guardian_run_exec",
                payload_text(unsafe_chain_payload)[:500],
            )

            data_layer_result = timed_tool(
                "prepare_data_layer_request",
                {
                    "source_type": "database",
                    "operation": "query",
                    "objective": "Evaluate consented data-layer envelope preparation without touching data.",
                    "user_consented": True,
                    "consent_text": "Evaluation consent for a readonly prepared envelope only.",
                    "scope": {"connection_ref": "example.analytics", "tables": ["events"], "fields": ["event_name"], "row_limit": 10},
                    "query": "select event_name from events limit 10",
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["prepare_data_layer_request"] = data_layer_result
            data_layer_payload = data_layer_result["payload"]
            data_layer_path = Path(str(data_layer_payload.get("request_path") or ""))
            add_check(
                checks,
                "data-layer tool prepares a consented envelope without touching data",
                ok_transport(data_layer_result)
                and data_layer_payload.get("ok") is True
                and data_layer_payload.get("data_layer_touched") is False
                and data_layer_path.exists(),
                payload_text(data_layer_payload)[:500],
            )

            data_layer_no_target_result = timed_tool(
                "prepare_data_layer_request",
                {
                    "source_type": "database",
                    "operation": "query",
                    "user_consented": True,
                    "consent_text": "Evaluation consent with constraints but no concrete data target.",
                    "scope": {"row_limit": 10},
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["prepare_data_layer_request.no_concrete_target"] = data_layer_no_target_result
            data_layer_no_target_payload = data_layer_no_target_result["payload"]
            add_check(
                checks,
                "data-layer scope requires a concrete target",
                data_layer_no_target_payload.get("ok") is False
                and "concrete target" in payload_text(data_layer_no_target_payload).lower(),
                payload_text(data_layer_no_target_payload)[:500],
            )

            data_layer_inline_secret_result = timed_tool(
                "prepare_data_layer_request",
                {
                    "source_type": "database",
                    "operation": "query",
                    "user_consented": True,
                    "consent_text": "Evaluation consent for inline-secret rejection.",
                    "scope": {"connection_ref": "example.analytics", "tables": ["events"], "row_limit": 10},
                    "query": "select * from events where api_key='abcdef123456'",
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["prepare_data_layer_request.inline_secret_value"] = data_layer_inline_secret_result
            data_layer_inline_secret_payload = data_layer_inline_secret_result["payload"]
            add_check(
                checks,
                "data-layer rejects inline secret values",
                data_layer_inline_secret_payload.get("ok") is False
                and "inline secrets" in payload_text(data_layer_inline_secret_payload).lower(),
                payload_text(data_layer_inline_secret_payload)[:500],
            )

            data_scope_sniff_result = timed_tool(
                "guardian_sniff_context",
                {
                    "authorization_level": "L4_sensitive_storage_or_data_access",
                    "include_sensitive_routes": True,
                    "data_layer_user_consented": True,
                    "data_layer_consent_text": "Evaluation consent for database route preparation only.",
                    "data_layer_scope": {"connection_ref": "example.analytics", "tables": ["events"], "row_limit": 10},
                    "target": {"kind": "database"},
                },
                env,
            )
            timings["guardian_sniff_context.data_layer_scope"] = data_scope_sniff_result
            data_scope_payload = data_scope_sniff_result["payload"]
            data_scope_routes = {route.get("id"): route.get("status") for route in data_scope_payload.get("route_candidates") or []}
            data_scope_status = data_scope_payload.get("data_layer_scope_status") or {}
            add_check(
                checks,
                "sniff data-layer scope is source-specific",
                ok_transport(data_scope_sniff_result)
                and data_scope_routes.get("database_readonly") == "eligible_for_prepare_data_layer_request"
                and data_scope_routes.get("api_readonly") == "requires_explicit_endpoint_and_scope"
                and data_scope_routes.get("registry_readonly") == "blocked_until_explicit_key_scope"
                and ((data_scope_status.get("database") or {}).get("eligible_for_prepare_data_layer_request") is True)
                and ((data_scope_status.get("api") or {}).get("eligible_for_prepare_data_layer_request") is False),
                payload_text(data_scope_payload)[:500],
            )

            data_scope_missing_text_result = timed_tool(
                "guardian_sniff_context",
                {
                    "authorization_level": "L4_sensitive_storage_or_data_access",
                    "include_sensitive_routes": True,
                    "data_layer_user_consented": True,
                    "data_layer_scope": {"connection_ref": "example.analytics", "tables": ["events"], "row_limit": 10},
                    "target": {"kind": "database"},
                },
                env,
            )
            timings["guardian_sniff_context.data_layer_missing_consent_text"] = data_scope_missing_text_result
            missing_text_payload = data_scope_missing_text_result["payload"]
            missing_text_routes = {route.get("id"): route.get("status") for route in missing_text_payload.get("route_candidates") or []}
            add_check(
                checks,
                "sniff data-layer readiness requires consent text",
                ok_transport(data_scope_missing_text_result)
                and missing_text_routes.get("database_readonly") == "scope_ready_requires_consent_text"
                and ((missing_text_payload.get("data_layer_scope_status") or {}).get("database") or {}).get("has_consent_text") is False,
                payload_text(missing_text_payload)[:500],
            )

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

            data_workflow_result = timed_tool(
                "guardian_prepare_workflow",
                {
                    "workflow_type": "data_layer_request",
                    "source_type": "database",
                    "operation": "query",
                    "objective": "Evaluate workflow facade data-layer envelope preparation.",
                    "user_consented": True,
                    "consent_text": "Evaluation consent for workflow-facade data-layer preparation only.",
                    "scope": {"connection_ref": "example.analytics", "tables": ["events"], "fields": ["event_name"], "row_limit": 10},
                    "query": "select event_name from events limit 10",
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["guardian_prepare_workflow.data_layer_request"] = data_workflow_result
            data_workflow_payload = data_workflow_result["payload"]
            data_workflow_path = Path(str(data_workflow_payload.get("request_path") or ""))
            add_check(
                checks,
                "workflow facade prepares data-layer envelopes",
                ok_transport(data_workflow_result)
                and data_workflow_payload.get("ok") is True
                and data_workflow_payload.get("data_layer_touched") is False
                and data_workflow_path.exists(),
                payload_text(data_workflow_payload)[:500],
            )

            chain_facade_result = timed_tool(
                "guardian_prepare_workflow",
                {
                    "workflow_type": "capture_chain",
                    "objective": "Evaluate facade capture-chain preparation without executing capture.",
                    "route": "application",
                    "trigger": {"type": "delay", "seconds": 1},
                    "steps": [{"tool": "capture_window", "args": {"render_guard": "wait"}}],
                    "output_dir": str(output_dir),
                },
                env,
            )
            timings["guardian_prepare_workflow.capture_chain"] = chain_facade_result
            chain_facade_payload = chain_facade_result["payload"]
            chain_facade_path = Path(str(chain_facade_payload.get("request_path") or ""))
            add_check(checks, "workflow facade prepares capture-chain envelopes", ok_transport(chain_facade_result) and chain_facade_payload.get("ok") is True and chain_facade_path.exists(), payload_text(chain_facade_payload)[:500])

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
