import ctypes
import ctypes.wintypes
import array
import copy
import difflib
import hashlib
import json
import locale
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import wave
from pathlib import Path


PLUGIN_NAME = "screen-guardian"
DEFAULT_CACHE_DIR = Path.home() / "Pictures" / "ScreenGuardian"
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
CONFIG_DIR = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "ScreenGuardian"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_LIMITS = {
    "watch_duration_seconds_max": 30,
    "watch_interval_seconds_min": 0.1,
    "watch_interval_seconds_max": 5,
    "watch_max_captures_max": 50,
    "watch_burst_frames_max": 10,
    "capture_scale_min": 0.01,
    "capture_scale_max": 1,
    "capture_settle_delay_ms_max": 5000,
    "capture_render_retry_count_max": 8,
    "capture_render_retry_interval_ms_max": 2000,
    "capture_stable_wait_seconds_max": 10,
    "capture_stable_interval_ms_min": 100,
    "capture_stable_interval_ms_max": 2000,
    "capture_error_wait_seconds_max": 30,
    "capture_error_poll_interval_ms_min": 100,
    "capture_error_poll_interval_ms_max": 5000,
    "window_survey_window_count_max": 100,
    "window_survey_capture_count_max": 12,
    "jpeg_quality_min": 1,
    "jpeg_quality_max": 95,
    "audio_duration_seconds_max": 120,
    "audio_sample_rate_max": 48000,
    "audio_channels_max": 2,
    "audio_extract_duration_seconds_max": None,
    "raw_exec_timeout_seconds_max": 30,
    "raw_exec_output_chars_max": 12000,
    "webpage_capture_timeout_ms_max": 30000,
    "webpage_capture_viewport_width_max": 3840,
    "webpage_capture_viewport_height_max": 2160,
    "webpage_capture_full_page_height_max": 50000,
    "webpage_capture_scroll_segments_max": 80,
    "webpage_capture_segment_delay_ms_max": 1000,
}

CAPTURE_GUARD_CHECKS = {
    "unrendered": "Detect blank, uniform, or very low-information frames that often mean rendering has not completed.",
    "window_client_low_information": "Detect direct HWND captures where the client/content area is blank or very low-information while the window frame is present.",
    "background_capture_unavailable": "Detect strict background window captures where direct HWND graphics are unavailable or too low-information and visible-screen bbox fallback is disabled.",
    "minimized_window": "Detect target windows that are minimized before capture.",
    "offscreen_window": "Detect target windows that are outside or partly outside the virtual desktop.",
    "tiny_capture": "Detect capture boxes that are probably too small to be intentional.",
    "stale_frame": "Detect retry attempts that returned the same frame repeatedly.",
    "occlusion_risk": "Detect best-effort bbox fallback window captures that may include occluding windows.",
    "bbox_identity_mismatch": "Detect visible-screen bbox fallback captures where the top visible window does not appear to be the requested target.",
}
DEFAULT_GUARD_CHECKS = ["unrendered"]

CAPTURE_ROUTE_CATALOG = {
    "desktop": {
        "title": "Desktop screen capture",
        "tools": ["capture_screen", "capture_region", "watch_screen"],
        "quiet": False,
        "best_for": ["visible desktop pixels", "multi-display diagnostics", "old-system screenshot fallback"],
        "limits": ["only sees visible pixels", "cannot capture hidden scroll content by itself"],
    },
    "application": {
        "title": "Application/window capture",
        "tools": ["guardian_capture_targets", "list_windows", "capture_window", "guardian_survey_windows"],
        "quiet": "default_best_effort",
        "best_for": ["specific Windows HWND/process/title", "non-topmost best-effort capture", "strict background HWND capture", "render-aware window capture", "bounded multi-window surveys"],
        "limits": ["strict background capture avoids visible-screen bbox fallback but may return a decision when the app does not expose drawable HWND pixels", "minimized, GPU-rendered, protected, or occluded windows may be blank, stale, or require a visible-screen fallback decision"],
    },
    "webpage": {
        "title": "Browser-rendered webpage capture",
        "tools": ["prepare_webpage_capture", "capture_webpage"],
        "quiet": True,
        "best_for": ["full scrollable webpage long screenshots", "browser viewport capture", "element capture"],
        "limits": ["optional Playwright/Chromium adapter", "requires explicit URL navigation"],
    },
    "nested_scroll": {
        "title": "Nested scroll container or iframe capture",
        "tools": ["capture_webpage"],
        "quiet": True,
        "best_for": ["tables inside admin pages", "embedded iframes", "scrollable panels within a page"],
        "limits": ["requires selector/frame_selector", "stitches multiple scroll segments"],
    },
    "chain": {
        "title": "Guided capture chain",
        "tools": ["prepare_capture_chain", "prepare_monitor_tick", "prepare_decision_request"],
        "quiet": "depends_on_route",
        "best_for": ["conditional screenshots", "AI-guided multi-step capture", "capture plus preprocess/model envelope"],
        "limits": ["prepare-only by default; no hidden scheduler"],
    },
}

DEFAULT_FEATURE_FLAGS = {
    "screen_capture": True,
    "window_capture": True,
    "bounded_watch": True,
    "workflow_metadata": True,
    "capture_chains": True,
    "multi_storage_routes": True,
    "image_analysis": True,
    "image_preprocess": True,
    "extension_routes": True,
    "model_request_envelopes": True,
    "ocr_routes": False,
    "image_narration_routes": False,
    "video_narration_routes": False,
    "audio_capture": False,
    "audio_analysis": True,
    "audio_transcription_routes": False,
    "video_audio_extract": False,
    "webpage_capture": False,
    "decision_policies": True,
    "monitor_profiles": True,
    "external_api_handoff": False,
    "codex_subagent_handoff": False,
    "raw_local_exec": False,
}

FEATURE_CATALOG = {
    "screen_capture": {
        "status": "implemented",
        "cost_when_inactive": "No screenshot adapter is imported unless a screen capture action runs.",
    },
    "window_capture": {
        "status": "implemented",
        "cost_when_inactive": "No window enumeration or Pillow window capture runs unless requested.",
    },
    "bounded_watch": {
        "status": "implemented",
        "cost_when_inactive": "No polling loop runs unless watch_screen is called.",
    },
    "workflow_metadata": {
        "status": "implemented",
        "cost_when_inactive": "No metadata sidecar is written.",
    },
    "capture_chains": {
        "status": "implemented",
        "cost_when_inactive": "No capture-chain envelope is written.",
    },
    "multi_storage_routes": {
        "status": "implemented",
        "cost_when_inactive": "No mirror copy is attempted.",
    },
    "image_analysis": {
        "status": "implemented",
        "cost_when_inactive": "Capture saving skips heuristic image analysis.",
    },
    "image_preprocess": {
        "status": "implemented",
        "cost_when_inactive": "No preprocessing preset is applied.",
    },
    "extension_routes": {
        "status": "implemented",
        "cost_when_inactive": "Route registry is not read or changed except by route tools.",
    },
    "model_request_envelopes": {
        "status": "implemented",
        "cost_when_inactive": "No request envelope is written.",
    },
    "ocr_routes": {
        "status": "interface",
        "cost_when_inactive": "No OCR adapter is invoked.",
    },
    "image_narration_routes": {
        "status": "interface",
        "cost_when_inactive": "No image narration model/API/subagent is invoked.",
    },
    "video_narration_routes": {
        "status": "interface",
        "cost_when_inactive": "No video model/API/subagent is invoked.",
    },
    "webpage_capture": {
        "status": "optional_adapter",
        "cost_when_inactive": "No browser runtime, Playwright import, navigation, DOM read, or webpage screenshot runs.",
    },
    "audio_capture": {
        "status": "interface",
        "cost_when_inactive": "No sounddevice import, device probe, microphone recording, or loopback capture runs.",
    },
    "audio_analysis": {
        "status": "implemented",
        "cost_when_inactive": "No audio waveform analysis runs.",
    },
    "audio_transcription_routes": {
        "status": "interface",
        "cost_when_inactive": "No audio transcription model/API/subagent is invoked.",
    },
    "video_audio_extract": {
        "status": "interface",
        "cost_when_inactive": "No FFmpeg probe or video audio extraction runs.",
    },
    "decision_policies": {
        "status": "interface",
        "cost_when_inactive": "No decision policy is loaded, evaluated, or prepared.",
    },
    "monitor_profiles": {
        "status": "interface",
        "cost_when_inactive": "No periodic target, trigger, detector, or action profile is loaded.",
    },
    "external_api_handoff": {
        "status": "interface",
        "cost_when_inactive": "No external API request is made.",
    },
    "codex_subagent_handoff": {
        "status": "interface",
        "cost_when_inactive": "No subagent handoff is started.",
    },
    "raw_local_exec": {
        "status": "break_glass",
        "cost_when_inactive": "No arbitrary local code execution is allowed.",
    },
}

ROLE_FEATURES = {
    "ocr": "ocr_routes",
    "vision_summary": "image_narration_routes",
    "video_summary": "video_narration_routes",
    "audio_summary": "audio_transcription_routes",
    "sound_diagnostics": "audio_analysis",
    "transcription": "audio_transcription_routes",
}

DEFAULT_CONFIG = {
    "mode": "auto",
    "manual_name": "",
    "manual_short_description": "",
    "cache_dir": "",
    "extra_output_dirs": [],
    "runtime_limits": DEFAULT_LIMITS,
    "feature_flags": DEFAULT_FEATURE_FLAGS,
    "extension_routes": [],
    "decision_policies": [],
    "monitor_profiles": [],
}


class WindowMatchError(ValueError):
    def __init__(self, message, payload):
        super().__init__(message)
        self.payload = payload


CAPABILITY_COMMANDS = [
    {
        "id": "diagnostic.readiness",
        "category": "diagnostic",
        "title": "Check Screen Guardian readiness",
        "intent_tags": ["health", "dependencies", "adapters"],
        "execution_mode": "direct",
        "maps_to": "guardian_check",
        "required_features": [],
        "default_args": {"detail": "short"},
        "side_effects": [],
        "context_strategy": "return_path",
        "safety_note": "No capture, upload, model call, subagent, command, or configuration change.",
    },
    {
        "id": "perceive.screen.quick",
        "category": "perceive",
        "title": "Quick local screen look",
        "intent_tags": ["screen", "quick_look", "low_context"],
        "execution_mode": "direct",
        "maps_to": "guardian_perceive",
        "required_features": ["screen_capture"],
        "default_args": {"task": "quick_look", "context_budget": "normal"},
        "side_effects": ["local_file_write"],
        "context_strategy": "return_path",
        "safety_note": "Local capture only; no model call or upload.",
    },
    {
        "id": "perceive.region.text",
        "category": "perceive",
        "title": "Capture and sharpen a text-heavy region",
        "intent_tags": ["region", "text", "preprocess"],
        "execution_mode": "direct",
        "maps_to": "guardian_perceive",
        "required_features": ["screen_capture", "image_analysis", "image_preprocess"],
        "default_args": {"task": "read_text", "target": {"type": "region"}, "context_budget": "normal"},
        "side_effects": ["local_file_write"],
        "context_strategy": "return_path",
        "safety_note": "Uses local image analysis and preprocessing only.",
    },
    {
        "id": "perceive.window.after_render",
        "category": "perceive",
        "title": "Capture a program window after rendering",
        "intent_tags": ["window", "debug_ui", "after_render"],
        "execution_mode": "direct",
        "maps_to": "guardian_perceive",
        "required_features": ["window_capture"],
        "default_args": {"task": "capture_window", "quiet_preferred": True, "wait_for_nonblank": True, "render_guard": "wait", "render_retry_count": 2, "context_budget": "normal"},
        "side_effects": ["local_file_write"],
        "context_strategy": "return_path",
        "safety_note": "Retries clearly blank frames within runtime limits and warns before saving suspected unrendered output.",
    },
    {
        "id": "perceive.windows.survey",
        "category": "perceive",
        "title": "Survey visible program windows",
        "intent_tags": ["windows", "survey", "batch", "hold_file"],
        "execution_mode": "direct",
        "maps_to": "guardian_survey_windows",
        "required_features": ["window_capture"],
        "default_args": {"capture_mode": "status_only", "include_visibility_probe": True, "context_budget": "hold_file"},
        "side_effects": ["optional_local_file_write"],
        "context_strategy": "hold_file",
        "safety_note": "Lists window status by default. Batch captures are bounded, local-only, and use hold-file delivery unless explicitly changed.",
    },
    {
        "id": "perceive.webpage.full_page",
        "category": "perceive",
        "title": "Capture a full scrollable webpage",
        "intent_tags": ["webpage", "full_page", "long_screenshot", "browser"],
        "execution_mode": "direct",
        "maps_to": "capture_webpage",
        "required_features": ["webpage_capture"],
        "default_args": {"mode": "full_page", "context_policy": "hold_file", "marked_file_only": True},
        "side_effects": ["browser_navigation", "local_file_write"],
        "context_strategy": "hold_file",
        "safety_note": "Optional Playwright route. It navigates only to the explicit URL and saves locally; no upload or model call.",
    },
    {
        "id": "perceive.change.popup",
        "category": "perceive",
        "title": "Watch briefly for a popup or visible change",
        "intent_tags": ["watch", "change", "popup"],
        "execution_mode": "direct",
        "maps_to": "guardian_perceive",
        "required_features": ["bounded_watch"],
        "default_args": {"task": "watch_change", "duration_seconds": 3, "interval_seconds": 0.5, "max_captures": 5},
        "side_effects": ["local_file_write"],
        "context_strategy": "return_path",
        "safety_note": "Short foreground bounded watch only; no background scheduler.",
    },
    {
        "id": "artifact.hold_file",
        "category": "artifact",
        "title": "Save and mark a capture without immediate context ingestion",
        "intent_tags": ["hold_file", "context_budget", "local_file"],
        "execution_mode": "direct",
        "maps_to": "guardian_perceive",
        "required_features": ["screen_capture"],
        "default_args": {"task": "hold_file", "context_budget": "hold_file"},
        "side_effects": ["local_file_write"],
        "context_strategy": "hold_file",
        "safety_note": "Stores a local marked file for later inspection.",
    },
    {
        "id": "workflow.model_request.prepare",
        "category": "workflow",
        "title": "Prepare a local model-request envelope",
        "intent_tags": ["model", "envelope", "prepare_only"],
        "execution_mode": "prepare_only",
        "maps_to": "guardian_prepare_workflow",
        "required_features": ["model_request_envelopes"],
        "default_args": {"workflow_type": "model_request"},
        "side_effects": ["local_envelope_write"],
        "context_strategy": "return_path",
        "safety_note": "Writes a local request envelope only; no API, model, or subagent execution.",
    },
    {
        "id": "workflow.decision.prepare",
        "category": "workflow",
        "title": "Prepare a local decision-request envelope",
        "intent_tags": ["decision", "envelope", "prepare_only"],
        "execution_mode": "prepare_only",
        "maps_to": "guardian_prepare_workflow",
        "required_features": ["decision_policies"],
        "default_args": {"workflow_type": "decision_request"},
        "side_effects": ["local_envelope_write"],
        "context_strategy": "return_path",
        "safety_note": "Writes decision inputs only; arbitrary complexity belongs to an explicit caller.",
    },
    {
        "id": "workflow.capture_chain.prepare",
        "category": "workflow",
        "title": "Prepare a guided capture chain",
        "intent_tags": ["capture_chain", "trigger", "combo", "prepare_only"],
        "execution_mode": "prepare_only",
        "maps_to": "prepare_capture_chain",
        "required_features": ["capture_chains"],
        "default_args": {"route": "auto", "trigger": {"type": "manual"}, "quiet": True},
        "side_effects": ["local_envelope_write"],
        "context_strategy": "return_path",
        "safety_note": "Writes a local chain plan only; no screenshot, browser navigation, scheduler, API, subagent, or script execution.",
    },
    {
        "id": "emergency.exec.prepare",
        "category": "emergency",
        "title": "Prepare a break-glass local execution envelope",
        "intent_tags": ["break_glass", "code", "prepare_only"],
        "execution_mode": "prepare_only",
        "maps_to": "guardian_prepare_exec",
        "required_features": [],
        "default_args": {"language": "python", "timeout_seconds": 30},
        "side_effects": ["local_envelope_write", "audit_log_write"],
        "context_strategy": "return_path",
        "safety_note": "Saves code for explicit user-directed execution later; does not execute it.",
    },
    {
        "id": "emergency.exec.run",
        "category": "emergency",
        "title": "Run break-glass local code",
        "intent_tags": ["break_glass", "code", "raw_exec"],
        "execution_mode": "break_glass",
        "maps_to": "guardian_run_exec",
        "required_features": ["raw_local_exec"],
        "default_args": {"language": "python", "timeout_seconds": 30},
        "side_effects": ["local_code_execution", "audit_log_write"],
        "context_strategy": "return_path",
        "safety_note": "Requires persistent raw_local_exec=true and user_confirmed=true for every call.",
    },
]

DISPLAY_PROFILES = {
    "en": {
        "display_name": "Screen Guardian",
        "short_description": "Ultra-light AI screen access without forced upgrades.",
    },
    "zh": {
        "display_name": "\u5c4f\u5e55\u5b88\u62a4\u8005",
        "short_description": "\u4e0d\u5f3a\u8feb\u5347\u7ea7\u7684\u8d85\u8f7b\u91cf AI \u5c4f\u5e55\u8bbf\u95ee\u3002",
    },
    "zh-cn": {
        "display_name": "\u5c4f\u5e55\u5b88\u62a4\u8005",
        "short_description": "\u4e0d\u5f3a\u8feb\u5347\u7ea7\u7684\u8d85\u8f7b\u91cf AI \u5c4f\u5e55\u8bbf\u95ee\u3002",
    },
    "zh-tw": {
        "display_name": "\u87a2\u5e55\u5b88\u8b77\u8005",
        "short_description": "\u4e0d\u5f37\u8feb\u5347\u7d1a\u7684\u8d85\u8f15\u91cf AI \u87a2\u5e55\u5b58\u53d6\u3002",
    },
    "ja": {
        "display_name": "\u30b9\u30af\u30ea\u30fc\u30f3\u30ac\u30fc\u30c7\u30a3\u30a2\u30f3",
        "short_description": "\u30a2\u30c3\u30d7\u30b0\u30ec\u30fc\u30c9\u3092\u5f37\u5236\u3057\u306a\u3044\u8efd\u91cf AI \u753b\u9762\u30a2\u30af\u30bb\u30b9\u3002",
    },
    "ko": {
        "display_name": "\uc2a4\ud06c\ub9b0 \uac00\ub514\uc5b8",
        "short_description": "\uac15\uc81c \uc5c5\uadf8\ub808\uc774\ub4dc \uc5c6\ub294 \ucd08\uacbd\ub7c9 AI \ud654\uba74 \uc811\uadfc.",
    },
}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def write_json(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.flush()


def error(message, **extra):
    result = {"ok": False, "error": message}
    result.update(extra)
    write_json(result)
    return 1


def deep_merge(default, data):
    result = copy.deepcopy(default)
    if not isinstance(data, dict):
        return result
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def read_json_file(path, default):
    try:
        if not path.exists():
            return copy.deepcopy(default)
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            return copy.deepcopy(default)
        return deep_merge(default, data)
    except Exception:
        return copy.deepcopy(default)


def write_json_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def load_config():
    config = read_json_file(CONFIG_PATH, DEFAULT_CONFIG)
    mode = str(config.get("mode", "auto")).lower()
    if mode not in ("auto", "manual"):
        config["mode"] = "auto"
    if not isinstance(config.get("extra_output_dirs"), list):
        config["extra_output_dirs"] = []
    if not isinstance(config.get("runtime_limits"), dict):
        config["runtime_limits"] = copy.deepcopy(DEFAULT_LIMITS)
    else:
        config["runtime_limits"] = deep_merge(DEFAULT_LIMITS, config["runtime_limits"])
    if not isinstance(config.get("feature_flags"), dict):
        config["feature_flags"] = copy.deepcopy(DEFAULT_FEATURE_FLAGS)
    else:
        config["feature_flags"] = deep_merge(DEFAULT_FEATURE_FLAGS, config["feature_flags"])
    if not isinstance(config.get("extension_routes"), list):
        config["extension_routes"] = []
    if not isinstance(config.get("decision_policies"), list):
        config["decision_policies"] = []
    if not isinstance(config.get("monitor_profiles"), list):
        config["monitor_profiles"] = []
    return config


def save_config(config):
    config["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_json_file(CONFIG_PATH, config)


def parse_unbounded_number(value):
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in ("", "none", "null", "unbounded", "off", "disabled"):
        return None
    number = float(value)
    if number.is_integer():
        return int(number)
    return number


def runtime_limits(args=None):
    config = load_config()
    limits = deep_merge(DEFAULT_LIMITS, config.get("runtime_limits") or {})
    args = args or {}
    for source_key in ("runtime_limits", "limit_overrides"):
        overrides = args.get(source_key)
        if not isinstance(overrides, dict):
            continue
        for key, value in overrides.items():
            if key not in DEFAULT_LIMITS:
                raise ValueError(f"Unknown per-call runtime limit: {key}")
            requested = parse_unbounded_number(value)
            current = limits.get(key)
            if requested is None:
                continue
            if key.endswith("_max"):
                if current is None or requested < current:
                    limits[key] = requested
            elif key.endswith("_min"):
                if current is None or requested > current:
                    limits[key] = requested
    return limits


def feature_flags(args=None):
    config = load_config()
    flags = deep_merge(DEFAULT_FEATURE_FLAGS, config.get("feature_flags") or {})
    args = args or {}
    if isinstance(args.get("feature_flags"), dict):
        for key, value in args["feature_flags"].items():
            if key not in DEFAULT_FEATURE_FLAGS:
                raise ValueError(f"Unknown per-call feature flag: {key}")
            if value is False:
                flags[key] = False
    return flags


def feature_enabled(name, args=None):
    return bool(feature_flags(args).get(name, False))


def require_feature(name, args=None):
    if not feature_enabled(name, args):
        raise RuntimeError(f"Feature '{name}' is inactive. Enable it with set_feature_flags before using this path.")


def skipped_analysis(reason):
    return {"available": False, "skipped": True, "reason": reason}


def check_min_max(value, min_value, max_value, label):
    if min_value is not None and value < float(min_value):
        raise ValueError(f"{label} must be at least {min_value}")
    if max_value is not None and value > float(max_value):
        raise ValueError(f"{label} must be no more than {max_value}")


def normalize_path_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value).split(",")
    paths = []
    for item in raw:
        text = str(item or "").strip()
        if text:
            paths.append(Path(text).expanduser())
    return paths


def serialize_paths(paths):
    return [str(path) for path in paths]


def dedupe_paths(paths):
    seen = set()
    result = []
    for path in paths:
        key = str(path.resolve() if path.exists() else path).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def path_key(path):
    return str(Path(path).expanduser().resolve()).lower()


def configured_cache_dirs():
    config = load_config()
    dirs = [DEFAULT_CACHE_DIR]
    config_cache_dir = str(config.get("cache_dir") or "").strip()
    if config_cache_dir:
        dirs.append(Path(config_cache_dir).expanduser())
    dirs.extend(normalize_path_list(config.get("extra_output_dirs")))
    return dedupe_paths(dirs)


def is_configured_cache_dir(path):
    target = path_key(path)
    return any(path_key(candidate) == target for candidate in configured_cache_dirs())


def normalize_locale_key(raw):
    if not raw:
        return ""
    value = str(raw).strip().lower().replace("_", "-")
    if not value:
        return ""
    if "chinese" in value:
        if "traditional" in value or "taiwan" in value or "hong kong" in value:
            return "zh-tw"
        return "zh-cn"
    if value.startswith("zh"):
        if "tw" in value or "hk" in value or "hant" in value:
            return "zh-tw"
        return "zh-cn"
    if value.startswith("ja") or "japanese" in value:
        return "ja"
    if value.startswith("ko") or "korean" in value:
        return "ko"
    if value.startswith("en") or "english" in value:
        return "en"
    return value.split(".")[0]


def detect_system_locale():
    candidates = []
    for key in ("LANGUAGE", "LC_ALL", "LC_CTYPE", "LANG"):
        value = os.environ.get(key)
        if value:
            candidates.append(value.split(":")[0])
    for getter in (lambda: locale.getlocale()[0], lambda: locale.getlocale(locale.LC_CTYPE)[0], lambda: locale.setlocale(locale.LC_CTYPE)):
        try:
            value = getter()
        except Exception:
            value = None
        if value:
            candidates.append(value)

    normalized = ""
    for candidate in candidates:
        normalized = normalize_locale_key(candidate)
        if normalized:
            break
    if not normalized:
        normalized = "en"
    return {"normalized": normalized, "raw_candidates": candidates}


def profile_for_locale(locale_key):
    if locale_key in DISPLAY_PROFILES:
        return DISPLAY_PROFILES[locale_key], locale_key
    language = locale_key.split("-")[0]
    if language in DISPLAY_PROFILES:
        return DISPLAY_PROFILES[language], language
    return DISPLAY_PROFILES["en"], "en"


def build_display_profile(config=None):
    config = config or load_config()
    system_locale = detect_system_locale()
    locale_profile, matched_locale = profile_for_locale(system_locale["normalized"])
    manual_name = str(config.get("manual_name") or "").strip()
    manual_short = str(config.get("manual_short_description") or "").strip()
    mode = str(config.get("mode", "auto")).lower()

    if mode == "manual" and manual_name:
        active = {
            "display_name": manual_name,
            "short_description": manual_short or locale_profile["short_description"],
            "source": "manual",
        }
    else:
        active = {
            "display_name": locale_profile["display_name"],
            "short_description": locale_profile["short_description"],
            "source": "system_locale",
            "matched_locale": matched_locale,
        }

    return {
        "mode": mode,
        "active": active,
        "system_locale": system_locale,
        "config_path": str(CONFIG_PATH),
        "supported_locales": sorted(DISPLAY_PROFILES.keys()),
    }


def manifest_display_profile():
    manifest = read_json_file(PLUGIN_MANIFEST_PATH, {})
    interface = manifest.get("interface") or {}
    return {
        "path": str(PLUGIN_MANIFEST_PATH),
        "display_name": interface.get("displayName", ""),
        "short_description": interface.get("shortDescription", ""),
        "note": "Codex plugin cards read this manifest after plugin reload or reinstall.",
    }


def import_capture_libs():
    try:
        import mss
        from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageGrab, ImageOps, ImageStat

        return {
            "mss": mss,
            "Image": Image,
            "ImageChops": ImageChops,
            "ImageEnhance": ImageEnhance,
            "ImageFilter": ImageFilter,
            "ImageGrab": ImageGrab,
            "ImageOps": ImageOps,
            "ImageStat": ImageStat,
        }, None
    except Exception as exc:
        return None, str(exc)


def mss_adapter_status():
    libs, import_error = import_capture_libs()
    status = {
        "id": "python-mss",
        "label": "Python MSS",
        "role": "screen_capture",
        "priority": 10,
        "available": import_error is None,
        "dependencies": ["mss", "Pillow"],
        "capabilities": [
            "list_displays",
            "capture_screen",
            "capture_region",
            "downscale",
            "preprocess",
            "metadata_sidecar",
            "png",
            "jpg",
        ],
        "compatibility_note": "Pure Python/ctypes path used as the current lightweight fallback for older or constrained Windows systems.",
    }
    if import_error:
        status["import_error"] = import_error
        status["install_hint"] = f"{sys.executable} -m pip install --user -r scripts/requirements.txt"
    else:
        status["versions"] = {
            "mss": getattr(libs["mss"], "__version__", "unknown"),
            "Pillow": getattr(libs["Image"], "__version__", "unknown"),
        }
    return status, libs


def window_adapter_status():
    libs, import_error = import_capture_libs()
    available = os.name == "nt" and import_error is None
    status = {
        "id": "pillow-window",
        "label": "Pillow Window Capture",
        "role": "window_capture",
        "priority": 20,
        "available": available,
        "dependencies": ["Pillow", "Windows user32"],
        "capabilities": ["guardian_capture_targets", "list_windows", "capture_window", "strict_background_mode", "non_topmost_best_effort", "no_foreground_activation", "quiet_preferred_default"],
        "compatibility_note": "Best-effort HWND capture. The adapter does not activate or raise the target window. Strict background mode disables visible-screen bbox fallback; some GPU, minimized, protected, or occluded windows may return blank, stale, or decision-only frames.",
    }
    if os.name != "nt":
        status["import_error"] = "Window capture is currently Windows-only."
    elif import_error:
        status["import_error"] = import_error
    return status, libs


def get_cache_dir(args=None):
    args = args or {}
    output_dirs = normalize_path_list(args.get("output_dirs"))
    if output_dirs and not (args.get("output_dir") or args.get("cache_dir")):
        return output_dirs[0]
    output_dir = args.get("output_dir") or args.get("cache_dir")
    if output_dir:
        return Path(output_dir).expanduser()
    config_cache_dir = str(load_config().get("cache_dir") or "").strip()
    if config_cache_dir:
        return Path(config_cache_dir).expanduser()
    return DEFAULT_CACHE_DIR


def ensure_cache_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def output_routes(args=None):
    args = args or {}
    primary = get_cache_dir(args)
    mirrors = []
    if not feature_enabled("multi_storage_routes", args):
        return primary, mirrors
    explicit_dirs = normalize_path_list(args.get("output_dirs"))
    if explicit_dirs:
        if args.get("output_dir") or args.get("cache_dir"):
            mirrors.extend(explicit_dirs)
        else:
            mirrors.extend(explicit_dirs[1:])
    mirrors.extend(normalize_path_list(args.get("mirror_dirs")))
    mirrors.extend(normalize_path_list(load_config().get("extra_output_dirs")))
    mirrors = [path for path in dedupe_paths(mirrors) if str(path).lower() != str(primary).lower()]
    return primary, mirrors


def safe_filename_part(value, fallback="capture"):
    text = str(value or "").strip().lower()
    kept = []
    for char in text:
        if char.isalnum() or char in ("-", "_"):
            kept.append(char)
        elif char in (" ", ".", "/", "\\", ":"):
            kept.append("-")
    result = "".join(kept).strip("-_")
    while "--" in result:
        result = result.replace("--", "-")
    return result[:80] or fallback


def normalized_tags(value):
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value).split(",")
    return [str(item).strip() for item in raw if str(item).strip()]


def normalized_format(value):
    fmt = str(value or "png").lower().strip(".")
    if fmt in ("jpg", "jpeg"):
        return "jpg"
    if fmt == "png":
        return "png"
    raise ValueError("format must be png or jpg")


def monitor_to_dict(index, monitor):
    index = int(index)
    return {
        "index": index,
        "display_index": index,
        "scope": "virtual_desktop" if index == 0 else "physical_display",
        "is_virtual": index == 0,
        "left": int(monitor["left"]),
        "top": int(monitor["top"]),
        "width": int(monitor["width"]),
        "height": int(monitor["height"]),
    }


def capture_box(sct, args):
    display_index = int(args.get("display_index", 1))
    if display_index < 0 or display_index >= len(sct.monitors):
        raise ValueError(f"display_index must be between 0 and {len(sct.monitors) - 1}")

    monitor = dict(sct.monitors[display_index])
    region = args.get("region")
    if not region:
        display = monitor_to_dict(display_index, monitor)
        display["coordinate_space"] = display["scope"]
        display["relative_to_display"] = False
        return monitor, display

    left = int(region.get("left", 0))
    top = int(region.get("top", 0))
    width = int(region.get("width", 0))
    height = int(region.get("height", 0))
    if width <= 0 or height <= 0:
        raise ValueError("region width and height must be positive")

    relative = bool(region.get("relative_to_display", True))
    if relative:
        left += int(monitor["left"])
        top += int(monitor["top"])

    box = {"left": left, "top": top, "width": width, "height": height}
    display = monitor_to_dict(display_index, monitor)
    display["coordinate_space"] = "physical_display_relative" if relative else "virtual_desktop_absolute"
    display["relative_to_display"] = relative
    return box, display


def resize_dimensions(width, height, args):
    limits = runtime_limits(args)
    scale = args.get("scale")
    max_width = args.get("max_width")
    max_height = args.get("max_height")

    new_width = int(width)
    new_height = int(height)

    if scale is not None:
        scale = float(scale)
        if scale <= 0:
            raise ValueError("scale must be greater than 0")
        check_min_max(scale, limits.get("capture_scale_min"), limits.get("capture_scale_max"), "scale")
        new_width = max(1, round(new_width * scale))
        new_height = max(1, round(new_height * scale))

    if max_width or max_height:
        max_width = int(max_width or new_width)
        max_height = int(max_height or new_height)
        if max_width <= 0 or max_height <= 0:
            raise ValueError("max_width and max_height must be positive")
        ratio = min(max_width / new_width, max_height / new_height, 1)
        new_width = max(1, round(new_width * ratio))
        new_height = max(1, round(new_height * ratio))

    return new_width, new_height


def resolve_capture_adapter(args):
    requested = str(args.get("adapter", "auto")).lower()
    if requested not in ("auto", "python-mss", "mss"):
        raise ValueError("adapter must be auto or python-mss")

    status, libs = mss_adapter_status()
    if not status["available"]:
        raise RuntimeError(
            "No capture adapter is available. Install the lightweight dependencies with: "
            + status.get("install_hint", "scripts/requirements.txt")
        )
    return status["id"], libs


def grab_screen_image(args):
    settle_delay = capture_settle_delay_seconds(args)
    if settle_delay:
        time.sleep(settle_delay)
    if capture_modes_include(args, "wait_buffer"):
        wait_for_stable_frames(args, lambda: grab_screen_once(args))
    wait_for_nonblank, retry_count, retry_interval = render_retry_options(args, default_wait_for_nonblank=False)
    attempts = []
    image = source = libs = None
    for attempt in range(retry_count + 1):
        image, source, libs = grab_screen_once(args)
        metrics = image_blank_metrics(image, libs)
        attempts.append({"attempt": attempt + 1, **metrics})
        if not wait_for_nonblank or not metrics["likely_blank"] or attempt >= retry_count:
            break
        time.sleep(retry_interval)
    source = with_render_timing(source, args, attempts, settle_delay, wait_for_nonblank)
    source = with_capture_strategy(source, args)
    return image, source, libs


def image_entropy(gray):
    histogram = gray.histogram()
    total = float(sum(histogram)) or 1.0
    entropy = 0.0
    for count in histogram:
        if count:
            p = count / total
            entropy -= p * math.log(p, 2)
    return entropy


def analyze_image_object(image, libs):
    ImageFilter = libs["ImageFilter"]
    ImageOps = libs["ImageOps"]
    ImageStat = libs["ImageStat"]
    width, height = image.size
    sample = image.convert("RGB")
    if max(sample.size) > 512:
        ratio = 512 / max(sample.size)
        sample = sample.resize((max(1, round(width * ratio)), max(1, round(height * ratio))))
    gray = ImageOps.grayscale(sample)
    gray_stat = ImageStat.Stat(gray)
    brightness = float(gray_stat.mean[0])
    contrast = float(gray_stat.stddev[0])
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_mean = float(ImageStat.Stat(edges).mean[0])
    entropy = image_entropy(gray)
    palette = sample.convert("P", palette=sample.palette.ADAPTIVE if sample.palette else 1, colors=64)
    colors = palette.getcolors(maxcolors=4096) or []
    color_count = len(colors)

    if contrast > 55 and edge_mean > 18 and color_count <= 40:
        likely = "text"
        recommended = "text"
        context_mode = "ocr_or_sharp_image"
    elif edge_mean > 14 and color_count <= 64:
        likely = "ui"
        recommended = "ui"
        context_mode = "sharp_image_or_summary"
    elif color_count > 48 and entropy > 5.0:
        likely = "photo"
        recommended = "photo"
        context_mode = "image_summary"
    else:
        likely = "mixed"
        recommended = "ui"
        context_mode = "keep_file_then_analyze"

    return {
        "width": width,
        "height": height,
        "likely_type": likely,
        "recommended_preprocess": recommended,
        "recommended_context_mode": context_mode,
        "metrics": {
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
            "edge_mean": round(edge_mean, 2),
            "entropy": round(entropy, 2),
            "color_count_approx": color_count,
        },
        "text_extraction": {
            "available": False,
            "note": "OCR is not bundled in the ultra-light model. Use a future OCR adapter or external transcription model.",
        },
    }


def apply_preprocess(image, mode, analysis, libs):
    ImageEnhance = libs["ImageEnhance"]
    ImageFilter = libs["ImageFilter"]
    ImageOps = libs["ImageOps"]
    requested = str(mode or "none").lower()
    if requested == "auto":
        requested = analysis.get("recommended_preprocess", "ui")
    if requested == "none":
        return image, "none"
    if requested == "text":
        processed = ImageOps.grayscale(image)
        processed = ImageOps.autocontrast(processed)
        processed = processed.filter(ImageFilter.SHARPEN)
        processed = ImageEnhance.Contrast(processed).enhance(1.25)
        return processed.convert("RGB"), "text"
    if requested == "ui":
        processed = ImageOps.autocontrast(image.convert("RGB"))
        processed = processed.filter(ImageFilter.UnsharpMask(radius=1.0, percent=90, threshold=4))
        return processed, "ui"
    if requested == "photo":
        processed = ImageEnhance.Color(image.convert("RGB")).enhance(1.03)
        processed = ImageEnhance.Contrast(processed).enhance(1.02)
        return processed, "photo"
    raise ValueError("preprocess must be none, auto, text, ui, or photo")


def capture_context(args):
    return {
        "project": str(args.get("project") or args.get("project_id") or "").strip(),
        "workflow": str(args.get("workflow") or args.get("workflow_id") or "").strip(),
        "tags": normalized_tags(args.get("tags")),
        "note": str(args.get("note") or "").strip(),
        "context_policy": str(args.get("context_policy") or "return_path").lower(),
        "marked_file_only": bool(args.get("marked_file_only", False)),
    }


def write_metadata_sidecar(path, metadata, args):
    if not feature_enabled("workflow_metadata", args):
        return ""
    if not bool(args.get("write_metadata", True)):
        return ""
    metadata_path = path.with_suffix(path.suffix + ".meta.json")
    write_json_file(metadata_path, metadata)
    return str(metadata_path)


def write_media_metadata_sidecar(path, metadata, args):
    if not feature_enabled("workflow_metadata", args):
        return ""
    if not bool(args.get("write_metadata", True)):
        return ""
    metadata_path = Path(path).with_suffix(Path(path).suffix + ".meta.json")
    write_json_file(metadata_path, metadata)
    return str(metadata_path)


def output_filename(args, fmt):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = int((time.time() % 1) * 1000)
    parts = [PLUGIN_NAME]
    context = capture_context(args)
    if context["project"]:
        parts.append(safe_filename_part(context["project"], "project"))
    if context["workflow"]:
        parts.append(safe_filename_part(context["workflow"], "workflow"))
    source_label = safe_filename_part(args.get("source_label") or args.get("title_contains") or args.get("process_name") or "", "")
    if source_label:
        parts.append(source_label)
    parts.extend([timestamp, f"{suffix:03d}"])
    return "-".join(parts) + "." + fmt


def mirror_media_file(output_path, metadata, args):
    _primary, mirror_dirs = output_routes(args)
    mirror_paths = []
    mirror_metadata_paths = []
    for mirror_dir in mirror_dirs:
        mirror_dir = ensure_cache_dir(mirror_dir)
        mirror_path = mirror_dir / Path(output_path).name
        shutil.copy2(output_path, mirror_path)
        mirror_paths.append(str(mirror_path))
        if feature_enabled("workflow_metadata", args) and bool(args.get("write_metadata", True)):
            mirror_metadata = copy.deepcopy(metadata)
            mirror_metadata["path"] = str(mirror_path)
            mirror_metadata.setdefault("storage", {})["primary_path"] = str(output_path)
            mirror_metadata["storage"]["is_mirror"] = True
            mirror_metadata_path = mirror_path.with_suffix(mirror_path.suffix + ".meta.json")
            write_json_file(mirror_metadata_path, mirror_metadata)
            mirror_metadata_paths.append(str(mirror_metadata_path))
    return mirror_paths, mirror_metadata_paths


def save_capture_image(image, source, libs, args):
    render_guard = render_guard_status(source, args)
    fmt = normalized_format(args.get("format", "png"))
    output_dir, mirror_dirs = output_routes(args)
    output_dir = ensure_cache_dir(output_dir)
    output_path = output_dir / output_filename(args, fmt)
    original_width, original_height = image.size
    requested_preprocess = str(args.get("preprocess", "none") or "none").lower()
    if requested_preprocess != "none":
        require_feature("image_preprocess", args)
    analysis_requested = bool(args.get("analyze", False))
    needs_analysis_before = analysis_requested or requested_preprocess == "auto"
    if needs_analysis_before:
        require_feature("image_analysis", args)
        analysis_before = analyze_image_object(image, libs)
    else:
        analysis_before = skipped_analysis("image analysis not requested")
    processed, applied_preprocess = apply_preprocess(image, requested_preprocess, analysis_before, libs)
    target_width, target_height = resize_dimensions(processed.size[0], processed.size[1], args)
    if (target_width, target_height) != processed.size:
        processed = processed.resize((target_width, target_height), libs["Image"].Resampling.LANCZOS)
    if analysis_requested:
        require_feature("image_analysis", args)
        analysis_after = analyze_image_object(processed, libs)
    else:
        analysis_after = skipped_analysis("image analysis not requested")

    limits = runtime_limits(args)
    quality = int(args.get("quality", 90))
    if fmt == "jpg":
        check_min_max(quality, limits.get("jpeg_quality_min"), limits.get("jpeg_quality_max"), "quality")
        processed.convert("RGB").save(output_path, "JPEG", quality=quality)
    else:
        processed.save(output_path, "PNG")

    mirror_paths = []
    for mirror_dir in mirror_dirs:
        mirror_dir = ensure_cache_dir(mirror_dir)
        mirror_path = mirror_dir / output_path.name
        shutil.copy2(output_path, mirror_path)
        mirror_paths.append(str(mirror_path))

    metadata = {
        "plugin": PLUGIN_NAME,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,
        "context": capture_context(args),
        "capture_strategy": copy.deepcopy(strategy_from_args(args)),
        "format": fmt,
        "path": str(output_path),
        "original_size": {"width": original_width, "height": original_height},
        "saved_size": {"width": processed.size[0], "height": processed.size[1]},
        "preprocess": {"requested": str(args.get("preprocess", "none")), "applied": applied_preprocess},
        "analysis": analysis_after,
        "analysis_before_preprocess": analysis_before,
        "text_handling": {
            "mode": "text_optimized_image" if applied_preprocess == "text" else "none",
            "ocr_available": bool((analysis_after.get("text_extraction") or {}).get("available", False)),
            "note": "Text mode sharpens and analyzes the screenshot, but the ultra-light core does not extract OCR text."
            if applied_preprocess == "text"
            else "",
        },
        "render_guard": render_guard,
        "storage": {
            "primary_path": str(output_path),
            "mirror_paths": mirror_paths,
        },
        "privacy": "Saved locally only.",
    }
    metadata_path = write_metadata_sidecar(output_path, metadata, args)
    mirror_metadata_paths = []
    if metadata_path:
        for mirror_path in mirror_paths:
            mirror_metadata = copy.deepcopy(metadata)
            mirror_metadata["path"] = mirror_path
            mirror_metadata["storage"]["primary_path"] = str(output_path)
            mirror_metadata["storage"]["is_mirror"] = True
            mirror_metadata_path = Path(mirror_path).with_suffix(Path(mirror_path).suffix + ".meta.json")
            write_json_file(mirror_metadata_path, mirror_metadata)
            mirror_metadata_paths.append(str(mirror_metadata_path))

    result = {
        "ok": True,
        "saved": True,
        "capture_deferred": False,
        "requires_decision": False,
        "result_state": "saved",
        "adapter": source.get("adapter"),
        "path": str(output_path),
        "metadata_path": metadata_path,
        "mirror_paths": mirror_paths,
        "mirror_metadata_paths": mirror_metadata_paths,
        "format": fmt,
        "source": source,
        "display": source.get("display"),
        "capture_box": source.get("capture_box"),
        "original_size": metadata["original_size"],
        "saved_size": metadata["saved_size"],
        "preprocess": metadata["preprocess"],
        "analysis": analysis_after,
        "text_handling": metadata["text_handling"],
        "render_guard": render_guard,
        "capture_strategy": metadata["capture_strategy"],
        "context": metadata["context"],
        "cursor_included": False,
        "privacy": "Saved locally only.",
    }
    if metadata["context"]["marked_file_only"]:
        result["context_delivery"] = "file_marked_only"
        result["note"] = "Capture was saved with metadata. Send the file or analysis explicitly when needed."
    return result


def window_rect(hwnd):
    rect = ctypes.wintypes.RECT()
    if not ctypes.windll.user32.GetWindowRect(int(hwnd), ctypes.byref(rect)):
        return None
    return {
        "left": int(rect.left),
        "top": int(rect.top),
        "right": int(rect.right),
        "bottom": int(rect.bottom),
        "width": int(rect.right - rect.left),
        "height": int(rect.bottom - rect.top),
    }


def window_client_rect(hwnd):
    if os.name != "nt":
        return None
    user32 = ctypes.windll.user32
    client = ctypes.wintypes.RECT()
    if not user32.GetClientRect(int(hwnd), ctypes.byref(client)):
        return None
    point = ctypes.wintypes.POINT(0, 0)
    if not user32.ClientToScreen(int(hwnd), ctypes.byref(point)):
        return None
    width = int(client.right - client.left)
    height = int(client.bottom - client.top)
    if width <= 0 or height <= 0:
        return None
    left = int(point.x)
    top = int(point.y)
    return {
        "left": left,
        "top": top,
        "right": left + width,
        "bottom": top + height,
        "width": width,
        "height": height,
    }


def window_text(hwnd):
    if os.name != "nt":
        return ""
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(int(hwnd))
    if length <= 0:
        return ""
    title_buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(int(hwnd), title_buffer, length + 1)
    return title_buffer.value.strip()


def process_name_for_pid(pid):
    if os.name != "nt":
        return ""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = ctypes.wintypes.DWORD(len(buffer))
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return Path(buffer.value).name
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)
    return ""


def window_info_for_hwnd(hwnd):
    if os.name != "nt":
        return None
    hwnd = int(hwnd)
    user32 = ctypes.windll.user32
    if not user32.IsWindow(hwnd):
        return None
    rect = window_rect(hwnd)
    if not rect or rect["width"] <= 0 or rect["height"] <= 0:
        return None
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {
        "hwnd": hwnd,
        "title": window_text(hwnd),
        "pid": int(pid.value),
        "process_name": process_name_for_pid(pid.value),
        "rect": rect,
        "client_rect": window_client_rect(hwnd) or {},
        "is_minimized": bool(user32.IsIconic(hwnd)),
        "is_visible": bool(user32.IsWindowVisible(hwnd)),
    }


def enum_windows(args=None):
    if os.name != "nt":
        return []
    args = args or {}
    user32 = ctypes.windll.user32
    windows = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def callback(hwnd, _lparam):
        info = window_info_for_hwnd(hwnd)
        if not info or not info.get("is_visible"):
            return True
        if not info.get("title"):
            return True
        windows.append(info)
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)

    title_filters = normalized_tags(args.get("title_contains_any"))
    title_contains = str(args.get("title_contains") or "").strip()
    if title_contains:
        title_filters.append(title_contains)
    title_filters = [item.lower() for item in title_filters if item]

    process_filters = normalized_tags(args.get("process_names"))
    process_name = str(args.get("process_name") or "").strip()
    if process_name:
        process_filters.append(process_name)
    process_filters = [item.lower() for item in process_filters if item]

    if title_filters:
        windows = [w for w in windows if any(item in w["title"].lower() for item in title_filters)]
    if process_filters:
        windows = [w for w in windows if any(item in w.get("process_name", "").lower() for item in process_filters)]
    return windows


def summarize_windows(windows, limit=10):
    return [
        {
            "hwnd": item.get("hwnd"),
            "title": item.get("title"),
            "process_name": item.get("process_name"),
            "pid": item.get("pid"),
            "rect": item.get("rect"),
            "is_minimized": item.get("is_minimized"),
        }
        for item in windows[:limit]
    ]


def window_match_terms(args):
    terms = []
    for key in ("exact_title", "title_contains", "process_name"):
        value = str(args.get(key) or "").strip()
        if value:
            terms.append(value)
    terms.extend(normalized_tags(args.get("title_contains_any")))
    terms.extend(normalized_tags(args.get("process_names")))
    return [term for term in terms if term]


def window_match_score(window, terms):
    if not terms:
        return 0.0
    title = str(window.get("title") or "").lower()
    process = str(window.get("process_name") or "").lower()
    haystacks = [title, process]
    best = 0.0
    for term in terms:
        needle = str(term or "").lower()
        if not needle:
            continue
        for haystack in haystacks:
            if needle in haystack:
                best = max(best, 1.0)
            best = max(best, difflib.SequenceMatcher(None, needle, haystack).ratio())
    return round(best, 4)


def window_match_payload(args, reason, windows=None):
    all_windows = windows if isinstance(windows, list) else enum_windows({})
    terms = window_match_terms(args)
    scored = []
    for window in all_windows:
        scored.append({**window, "match_score": window_match_score(window, terms)})
    scored.sort(key=lambda item: item.get("match_score", 0), reverse=True)
    approximate = [item for item in scored if item.get("match_score", 0) >= 0.25][:10]
    if not approximate:
        approximate = scored[:10]
    return {
        "reason": reason,
        "requested": {
            "hwnd": args.get("hwnd"),
            "exact_title": args.get("exact_title"),
            "title_contains": args.get("title_contains"),
            "title_contains_any": args.get("title_contains_any"),
            "process_name": args.get("process_name"),
            "process_names": args.get("process_names"),
        },
        "candidate_count": len(all_windows),
        "candidate_windows": summarize_windows(all_windows, 10),
        "approximate_matches": summarize_windows(approximate, 10),
        "recommended_next": "Call list_windows, then retry capture_window with a specific hwnd or exact_title.",
    }


def root_window(hwnd):
    if os.name != "nt" or not hwnd:
        return int(hwnd or 0)
    GA_ROOT = 2
    root = ctypes.windll.user32.GetAncestor(int(hwnd), GA_ROOT)
    return int(root or hwnd)


def root_window_from_point(x, y):
    if os.name != "nt":
        return 0
    point = ctypes.wintypes.POINT(int(x), int(y))
    hwnd = ctypes.windll.user32.WindowFromPoint(point)
    return root_window(hwnd)


def windows_equivalent(a, b):
    if not a or not b:
        return False
    return root_window(int(a)) == root_window(int(b))


def bbox_identity_probe(window):
    if os.name != "nt":
        return {"available": False, "reason": "not_windows"}
    rect = window.get("rect") if isinstance(window, dict) else {}
    hwnd = int(window.get("hwnd") or 0)
    if not hwnd or not isinstance(rect, dict):
        return {"available": False, "reason": "missing_window_or_rect"}
    left = int(rect.get("left", 0))
    top = int(rect.get("top", 0))
    width = int(rect.get("width") or (int(rect.get("right", left)) - left))
    height = int(rect.get("height") or (int(rect.get("bottom", top)) - top))
    if width <= 0 or height <= 0:
        return {"available": False, "reason": "invalid_rect", "rect": rect}
    points = [
        (left + width * 0.50, top + height * 0.50),
        (left + width * 0.25, top + height * 0.25),
        (left + width * 0.75, top + height * 0.25),
        (left + width * 0.25, top + height * 0.75),
        (left + width * 0.75, top + height * 0.75),
    ]
    target_root = root_window(hwnd)
    hits = []
    match_count = 0
    for x, y in points:
        top_hwnd = root_window_from_point(x, y)
        matched = windows_equivalent(hwnd, top_hwnd)
        if matched:
            match_count += 1
        top_info = window_info_for_hwnd(top_hwnd) or {"hwnd": int(top_hwnd or 0), "title": "", "pid": 0, "process_name": ""}
        hits.append(
            {
                "point": {"x": int(round(x)), "y": int(round(y))},
                "top_hwnd": int(top_hwnd or 0),
                "target_match": bool(matched),
                "top_window": {
                    "hwnd": top_info.get("hwnd"),
                    "title": top_info.get("title"),
                    "pid": top_info.get("pid"),
                    "process_name": top_info.get("process_name"),
                },
            }
        )
    sample_count = len(hits)
    match_ratio = match_count / float(sample_count or 1)
    return {
        "available": True,
        "target_hwnd": hwnd,
        "target_root_hwnd": target_root,
        "target_title": window.get("title"),
        "target_pid": window.get("pid"),
        "target_process_name": window.get("process_name"),
        "sample_count": sample_count,
        "target_match_count": match_count,
        "target_match_ratio": round(match_ratio, 3),
        "identity_verified": match_ratio >= 0.6,
        "samples": hits,
        "note": "Visible-screen bbox fallback can only be identity-checked against currently topmost windows at sampled points.",
    }


def find_window(args):
    hwnd = args.get("hwnd")
    if hwnd:
        info = window_info_for_hwnd(int(hwnd))
        if info:
            return info
    windows = enum_windows(args)
    exact_title = str(args.get("exact_title") or "").lower()
    if exact_title:
        windows = [w for w in windows if w["title"].lower() == exact_title]
    if not windows:
        raise WindowMatchError("No matching window found", window_match_payload(args, "no_matching_window"))
    if len(windows) > 1 and not bool(args.get("allow_first_match", False)):
        raise WindowMatchError(
            "Multiple matching windows found; pass hwnd from list_windows, use a more specific exact_title/process filter, "
            "or set allow_first_match=true.",
            window_match_payload(args, "ambiguous_window_match", windows),
        )
    return windows[0]


def image_looks_black(image, libs):
    stat = libs["ImageStat"].Stat(image.convert("RGB"))
    mean = sum(stat.mean) / 3.0
    contrast = sum(stat.stddev) / 3.0
    return mean < 1.0 and contrast < 0.5


def image_blank_metrics(image, libs):
    ImageFilter = libs["ImageFilter"]
    ImageOps = libs["ImageOps"]
    ImageStat = libs["ImageStat"]
    sample = image.convert("RGB")
    if max(sample.size) > 384:
        ratio = 384 / max(sample.size)
        sample = sample.resize((max(1, round(sample.size[0] * ratio)), max(1, round(sample.size[1] * ratio))))
    gray = ImageOps.grayscale(sample)
    gray_stat = ImageStat.Stat(gray)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edge_mean = float(ImageStat.Stat(edges).mean[0])
    brightness = float(gray_stat.mean[0])
    contrast = float(gray_stat.stddev[0])
    entropy = image_entropy(gray)
    uniform_dark = brightness <= 3.0 and contrast <= 1.0 and entropy <= 0.1
    uniform_light = brightness >= 252.0 and contrast <= 1.0 and entropy <= 0.1
    low_information = contrast <= 3.0 and edge_mean <= 1.2 and entropy <= 0.45
    bright_low_information = brightness >= 252.0 and contrast <= 6.0 and entropy <= 0.2
    likely_blank = uniform_dark or uniform_light or low_information or bright_low_information
    return {
        "likely_blank": bool(likely_blank),
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "edge_mean": round(edge_mean, 2),
        "entropy": round(entropy, 2),
        "sample_hash": hashlib.sha256(gray.tobytes()).hexdigest()[:16],
    }


def window_client_crop_box(image, window):
    rect = window.get("rect") if isinstance(window.get("rect"), dict) else {}
    client = window.get("client_rect") if isinstance(window.get("client_rect"), dict) else {}
    if not rect or not client:
        return None
    left = int(client.get("left", 0)) - int(rect.get("left", 0))
    top = int(client.get("top", 0)) - int(rect.get("top", 0))
    right = left + int(client.get("width", 0))
    bottom = top + int(client.get("height", 0))
    left = max(0, min(int(image.size[0]), left))
    top = max(0, min(int(image.size[1]), top))
    right = max(left, min(int(image.size[0]), right))
    bottom = max(top, min(int(image.size[1]), bottom))
    if right - left <= 32 or bottom - top <= 32:
        return None
    return (left, top, right, bottom)


def window_client_content_status(image, libs, window):
    box = window_client_crop_box(image, window)
    if not box:
        return {"available": False, "reason": "missing_or_too_small_client_rect", "client_rect": window.get("client_rect") or {}}
    client_image = image.crop(box)
    metrics = image_blank_metrics(client_image, libs)
    frame_metrics = image_blank_metrics(image, libs)
    client_area = (box[2] - box[0]) * (box[3] - box[1])
    image_area = max(1, int(image.size[0]) * int(image.size[1]))
    low_information = bool(metrics.get("likely_blank", False))
    return {
        "available": True,
        "client_crop_box": {"left": box[0], "top": box[1], "right": box[2], "bottom": box[3], "width": box[2] - box[0], "height": box[3] - box[1]},
        "client_area_ratio": round(client_area / float(image_area), 3),
        "client_metrics": metrics,
        "whole_window_metrics": frame_metrics,
        "client_low_information": low_information,
        "note": "Direct HWND captures can include a rendered frame while GPU/browser content remains blank. A low-information client area is treated as a capture-quality signal.",
    }


def rect_area(rect):
    if not isinstance(rect, dict):
        return 0
    width = int(rect.get("width") or (int(rect.get("right", 0)) - int(rect.get("left", 0))))
    height = int(rect.get("height") or (int(rect.get("bottom", 0)) - int(rect.get("top", 0))))
    return max(0, width) * max(0, height)


def virtual_screen_rect():
    if os.name != "nt":
        return {}
    user32 = ctypes.windll.user32
    left = int(user32.GetSystemMetrics(76))
    top = int(user32.GetSystemMetrics(77))
    width = int(user32.GetSystemMetrics(78))
    height = int(user32.GetSystemMetrics(79))
    return {"left": left, "top": top, "right": left + width, "bottom": top + height, "width": width, "height": height}


def rect_intersection_ratio(rect, bounds):
    if not isinstance(rect, dict) or not isinstance(bounds, dict):
        return 1.0
    area = rect_area(rect)
    if area <= 0:
        return 0.0
    left = max(int(rect.get("left", 0)), int(bounds.get("left", 0)))
    top = max(int(rect.get("top", 0)), int(bounds.get("top", 0)))
    right = min(int(rect.get("right", int(rect.get("left", 0)) + int(rect.get("width", 0)))), int(bounds.get("right", 0)))
    bottom = min(int(rect.get("bottom", int(rect.get("top", 0)) + int(rect.get("height", 0)))), int(bounds.get("bottom", 0)))
    visible = max(0, right - left) * max(0, bottom - top)
    return visible / float(area)


def capture_settle_delay_seconds(args):
    limits = runtime_limits(args)
    delay_ms = args.get("settle_delay_ms")
    if args.get("delay_seconds") is not None:
        delay_ms = float(args.get("delay_seconds")) * 1000.0
    delay_ms = float(delay_ms or 0)
    if delay_ms < 0:
        raise ValueError("delay_seconds and settle_delay_ms must be zero or greater")
    check_min_max(delay_ms, 0, limits.get("capture_settle_delay_ms_max"), "settle_delay_ms")
    return delay_ms / 1000.0


def normalize_render_guard(args, source_type="screen"):
    default_mode = "warn" if source_type == "window" else "save"
    mode = str(args.get("render_guard") or default_mode).strip().lower()
    aliases = {
        "": default_mode,
        "off": "save",
        "none": "save",
        "confirm": "warn",
        "require_confirmation": "warn",
        "auto": "wait",
    }
    mode = aliases.get(mode, mode)
    if mode not in ("save", "warn", "wait", "fail"):
        raise ValueError("render_guard must be save, warn, wait, or fail")
    return mode


def normalize_guard_checks(args):
    raw = args.get("guard_checks")
    if raw is None:
        return list(DEFAULT_GUARD_CHECKS)
    if isinstance(raw, str):
        items = [item.strip().lower() for item in raw.replace(",", " ").split() if item.strip()]
    elif isinstance(raw, list):
        items = [str(item).strip().lower() for item in raw if str(item).strip()]
    else:
        raise ValueError("guard_checks must be an array of strings, a comma-separated string, 'all', or 'none'")
    if not items:
        return []
    if any(item in ("none", "off", "disabled") for item in items):
        return []
    if any(item == "all" for item in items):
        return list(CAPTURE_GUARD_CHECKS.keys())
    unknown = [item for item in items if item not in CAPTURE_GUARD_CHECKS]
    if unknown:
        raise ValueError(f"Unknown guard_checks: {', '.join(unknown)}")
    normalized = []
    for item in items:
        if item not in normalized:
            normalized.append(item)
    return normalized


def quiet_capture_preferred(args, source_type="screen"):
    if "quiet_preferred" in args:
        return bool(args.get("quiet_preferred"))
    if "quiet" in args:
        return bool(args.get("quiet"))
    return source_type in ("window", "webpage")


def normalize_background_mode(args):
    mode = str(args.get("background_mode") or args.get("window_background_mode") or "best_effort").strip().lower()
    aliases = {
        "auto": "best_effort",
        "default": "best_effort",
        "quiet": "best_effort",
        "direct": "strict",
        "direct_only": "strict",
        "hwnd": "strict",
        "occlusion_safe": "strict",
        "occlusion_resistant": "strict",
        "no_bbox": "strict",
        "no_visible_fallback": "strict",
        "fallback": "visible_fallback",
        "bbox": "visible_fallback",
        "screen_bbox": "visible_fallback",
        "visible": "visible_fallback",
    }
    mode = aliases.get(mode, mode)
    if mode not in ("best_effort", "strict", "visible_fallback"):
        raise ValueError("background_mode must be best_effort, strict, or visible_fallback")
    return mode


def visible_window_fallback_allowed(args):
    mode = normalize_background_mode(args)
    if mode == "strict":
        return False
    return True


def render_retry_options(args, default_wait_for_nonblank=False):
    limits = runtime_limits(args)
    wait_value = args.get("wait_for_nonblank")
    wait_for_nonblank = bool(default_wait_for_nonblank if wait_value is None else wait_value)
    if str(args.get("render_guard") or "").strip().lower() in ("wait", "auto"):
        wait_for_nonblank = True
    retry_default = 2 if wait_for_nonblank else 0
    retry_count = int(args.get("render_retry_count", retry_default))
    retry_interval_ms = float(args.get("render_retry_interval_ms", 250))
    if retry_count < 0:
        raise ValueError("render_retry_count must be zero or greater")
    if retry_interval_ms < 0:
        raise ValueError("render_retry_interval_ms must be zero or greater")
    check_min_max(retry_count, 0, limits.get("capture_render_retry_count_max"), "render_retry_count")
    check_min_max(retry_interval_ms, 0, limits.get("capture_render_retry_interval_ms_max"), "render_retry_interval_ms")
    return wait_for_nonblank, retry_count, retry_interval_ms / 1000.0


def normalize_capture_modes(args):
    raw = args.get("capture_modes")
    if raw is None:
        raw = args.get("capture_strategy")
    if raw is None:
        return ["fast"]
    if isinstance(raw, str):
        items = [item.strip().lower() for item in raw.replace(",", " ").split() if item.strip()]
    elif isinstance(raw, list):
        items = [str(item).strip().lower() for item in raw if str(item).strip()]
    else:
        raise ValueError("capture_modes must be an array of strings or a comma-separated string")
    if not items:
        return ["fast"]
    aliases = {
        "direct": "fast",
        "quick": "fast",
        "quick_capture": "fast",
        "time_delay": "delay",
        "delayed": "delay",
        "render": "wait_render",
        "render_complete": "wait_render",
        "render_ready": "wait_render",
        "buffer": "wait_buffer",
        "buffer_stable": "wait_buffer",
        "stable": "wait_buffer",
        "wait_stable": "wait_buffer",
        "error": "wait_error",
        "error_text": "wait_error",
        "error_window": "wait_error",
    }
    allowed = {"fast", "delay", "wait_render", "wait_buffer", "wait_error"}
    normalized = []
    for item in items:
        item = aliases.get(item, item)
        if item not in allowed:
            raise ValueError("capture_modes must contain fast, delay, wait_render, wait_buffer, or wait_error")
        if item not in normalized:
            normalized.append(item)
    if len(normalized) > 1 and "fast" in normalized:
        normalized = [item for item in normalized if item != "fast"]
    return normalized or ["fast"]


def strategy_from_args(args):
    strategy = args.get("_capture_strategy")
    return strategy if isinstance(strategy, dict) else {}


def capture_modes_include(args, mode):
    return mode in normalize_capture_modes(args)


def stable_wait_options(args):
    limits = runtime_limits(args)
    timeout = float(args.get("stable_wait_seconds", args.get("buffer_wait_seconds", 2.0)))
    interval_ms = float(args.get("stable_interval_ms", args.get("buffer_interval_ms", 250)))
    threshold = float(args.get("stable_threshold", args.get("buffer_stable_threshold", 1.5)))
    required_samples = int(args.get("stable_required_samples", 2))
    if timeout < 0:
        raise ValueError("stable_wait_seconds must be zero or greater")
    if interval_ms <= 0:
        raise ValueError("stable_interval_ms must be greater than zero")
    if threshold < 0:
        raise ValueError("stable_threshold must be zero or greater")
    if required_samples < 1:
        raise ValueError("stable_required_samples must be at least 1")
    check_min_max(timeout, 0, limits.get("capture_stable_wait_seconds_max"), "stable_wait_seconds")
    check_min_max(interval_ms, limits.get("capture_stable_interval_ms_min"), limits.get("capture_stable_interval_ms_max"), "stable_interval_ms")
    return timeout, interval_ms / 1000.0, threshold, required_samples


def wait_for_stable_frames(args, grab_once):
    timeout, interval, threshold, required_samples = stable_wait_options(args)
    strategy = args.setdefault("_capture_strategy", {})
    if timeout <= 0:
        strategy["stable_wait"] = {"enabled": True, "skipped": True, "reason": "stable_wait_seconds is zero"}
        return
    deadline = time.time() + timeout
    previous = None
    stable_count = 0
    samples = []
    libs = None
    while time.time() <= deadline:
        image, _source, libs = grab_once()
        metrics = image_blank_metrics(image, libs)
        diff = None
        stable = False
        if previous is not None:
            diff = image_difference_score(image, previous, libs)
            stable = diff <= threshold
            stable_count = stable_count + 1 if stable else 0
        samples.append(
            {
                "sample": len(samples) + 1,
                "stable": bool(stable),
                "diff": None if diff is None else round(float(diff), 3),
                "likely_blank": bool(metrics.get("likely_blank", False)),
                "sample_hash": metrics.get("sample_hash"),
            }
        )
        previous = image
        if stable_count >= required_samples:
            break
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(interval, max(0.0, remaining)))
    strategy["stable_wait"] = {
        "enabled": True,
        "status": "stable" if stable_count >= required_samples else "timeout",
        "samples": samples,
        "threshold": threshold,
        "required_samples": required_samples,
        "timeout_seconds": timeout,
        "interval_seconds": round(interval, 3),
        "note": "wait_buffer waits until consecutive local captures look stable before the final screenshot.",
    }


def with_capture_strategy(source, args):
    strategy = strategy_from_args(args)
    if strategy:
        source["capture_strategy"] = copy.deepcopy(strategy)
    return source


def with_render_timing(source, args, attempts, settle_delay, wait_for_nonblank):
    guard_mode = normalize_render_guard(args, source.get("type", "screen"))
    final_attempt = attempts[-1] if attempts else {}
    source["render_timing"] = {
        "delay_seconds": round(settle_delay, 3),
        "wait_for_nonblank": bool(wait_for_nonblank),
        "render_guard": guard_mode,
        "attempts": attempts,
        "final_attempt": final_attempt,
        "final_likely_blank": bool(final_attempt.get("likely_blank", False)),
        "note": "Clearly blank frames can be retried before saving. Render guard can warn or fail before saving a suspected unrendered frame.",
    }
    return source


def render_guard_status(source, args):
    timing = source.get("render_timing") if isinstance(source.get("render_timing"), dict) else {}
    final_attempt = timing.get("final_attempt") if isinstance(timing.get("final_attempt"), dict) else {}
    source_type = str(source.get("type") or "screen")
    mode = normalize_render_guard(args, source_type)
    checks = normalize_guard_checks(args)
    if source_type == "window" and quiet_capture_preferred(args, source_type) and "occlusion_risk" not in checks:
        checks.append("occlusion_risk")
    capture_method = str(source.get("capture_method") or "")
    direct_content = source.get("direct_window_content") if isinstance(source.get("direct_window_content"), dict) else {}
    if source_type == "window" and direct_content.get("client_low_information") and "window_client_low_information" not in checks:
        checks.append("window_client_low_information")
    background_capture = source.get("background_capture") if isinstance(source.get("background_capture"), dict) else {}
    if source_type == "window" and background_capture.get("strict_unavailable") and "background_capture_unavailable" not in checks:
        checks.append("background_capture_unavailable")
    if source_type == "window" and "bbox" in capture_method and "bbox_identity_mismatch" not in checks:
        checks.append("bbox_identity_mismatch")
    issues = capture_guard_issues(source, args, checks)
    suspected_unrendered = any(issue.get("id") == "unrendered" for issue in issues)
    identity_mismatch = any(issue.get("id") == "bbox_identity_mismatch" for issue in issues)
    background_unavailable = any(issue.get("id") == "background_capture_unavailable" for issue in issues)
    allow_unverified_bbox = bool(args.get("allow_unverified_bbox_fallback", False))
    confirmed = bool(args.get("render_guard_confirmed", False))
    if not issues:
        status = "passed"
    elif identity_mismatch and not allow_unverified_bbox:
        status = "awaiting_bbox_identity_decision"
    elif background_unavailable and not confirmed:
        status = "awaiting_background_capture_decision"
    elif confirmed:
        status = "confirmed_save"
    elif mode == "save":
        status = "saved_with_suspected_unrendered_warning"
    elif mode == "wait":
        status = "awaiting_decision_after_wait"
    elif mode == "warn":
        status = "awaiting_decision"
    else:
        status = "blocked"
    return {
        "mode": mode,
        "status": status,
        "enabled_checks": checks,
        "available_checks": CAPTURE_GUARD_CHECKS,
        "issues": issues,
        "suspected_unrendered": suspected_unrendered,
        "bbox_identity_mismatch": identity_mismatch,
        "background_capture_unavailable": background_unavailable,
        "allow_unverified_bbox_fallback": allow_unverified_bbox,
        "confirmed": confirmed,
        "final_attempt": final_attempt,
        "wait_for_nonblank": bool(timing.get("wait_for_nonblank", False)),
        "attempt_count": len(timing.get("attempts") or []),
        "hint": "Set render_guard_confirmed=true or render_guard='save' if this blank frame is expected.",
        "quiet_preferred": quiet_capture_preferred(args, source_type),
    }


def capture_guard_issues(source, args, checks):
    timing = source.get("render_timing") if isinstance(source.get("render_timing"), dict) else {}
    final_attempt = timing.get("final_attempt") if isinstance(timing.get("final_attempt"), dict) else {}
    attempts = timing.get("attempts") if isinstance(timing.get("attempts"), list) else []
    capture_box = source.get("capture_box") if isinstance(source.get("capture_box"), dict) else {}
    window = source.get("window") if isinstance(source.get("window"), dict) else {}
    issues = []

    if "unrendered" in checks and bool(final_attempt.get("likely_blank", False)):
        brightness = float(final_attempt.get("brightness") or 0)
        if brightness <= 3:
            subtype = "black_or_protected_like"
        elif brightness >= 252:
            subtype = "white_or_loading_like"
        else:
            subtype = "low_information"
        issues.append(
            {
                "id": "unrendered",
                "subtype": subtype,
                "severity": "decision",
                "message": "Final capture attempt looks blank, uniform, or very low-information.",
                "evidence": final_attempt,
            }
        )

    if "window_client_low_information" in checks and source.get("type") == "window":
        direct_content = source.get("direct_window_content") if isinstance(source.get("direct_window_content"), dict) else {}
        if direct_content.get("client_low_information"):
            issues.append(
                {
                    "id": "window_client_low_information",
                    "severity": "decision",
                    "message": "Direct HWND capture reported a blank or very low-information client/content area while the window frame may still be present.",
                    "evidence": direct_content,
                }
            )

    if "background_capture_unavailable" in checks and source.get("type") == "window":
        background_capture = source.get("background_capture") if isinstance(source.get("background_capture"), dict) else {}
        if background_capture.get("strict_unavailable"):
            issues.append(
                {
                    "id": "background_capture_unavailable",
                    "severity": "decision",
                    "message": "Strict background capture did not produce reliable direct HWND graphics, and visible-screen bbox fallback is disabled.",
                    "evidence": {
                        "background_capture": background_capture,
                        "direct_window_content": source.get("direct_window_content"),
                        "capture_method": source.get("capture_method"),
                    },
                }
            )

    if "minimized_window" in checks and source.get("type") == "window" and bool(window.get("is_minimized", False)):
        issues.append(
            {
                "id": "minimized_window",
                "severity": "decision",
                "message": "The target window is minimized, so window capture may return blank, stale, or incomplete pixels.",
                "evidence": {"hwnd": window.get("hwnd"), "title": window.get("title"), "process_name": window.get("process_name")},
            }
        )

    if "offscreen_window" in checks and source.get("type") == "window":
        ratio = rect_intersection_ratio(window.get("rect") or capture_box, source.get("virtual_screen") or {})
        if ratio < 0.98:
            issues.append(
                {
                    "id": "offscreen_window",
                    "severity": "decision",
                    "message": "The target window appears partly or fully outside the virtual desktop.",
                    "evidence": {"visible_ratio": round(ratio, 3), "rect": window.get("rect") or capture_box, "virtual_screen": source.get("virtual_screen")},
                }
            )

    if "tiny_capture" in checks:
        width = int(capture_box.get("width") or 0)
        height = int(capture_box.get("height") or 0)
        min_pixels = int(args.get("guard_tiny_min_pixels") or 16)
        if width > 0 and height > 0 and (width < min_pixels or height < min_pixels):
            issues.append(
                {
                    "id": "tiny_capture",
                    "severity": "decision",
                    "message": "The capture box is very small and may be a bad coordinate or target selection.",
                    "evidence": {"capture_box": capture_box, "min_pixels": min_pixels},
                }
            )

    if "stale_frame" in checks and len(attempts) >= 2:
        hashes = [item.get("sample_hash") for item in attempts if item.get("sample_hash")]
        if len(hashes) >= 2 and len(set(hashes)) == 1:
            issues.append(
                {
                    "id": "stale_frame",
                    "severity": "decision",
                    "message": "Repeated retry attempts returned the same sampled frame.",
                    "evidence": {"attempt_count": len(hashes), "sample_hash": hashes[-1]},
                }
            )

    capture_method = str(source.get("capture_method") or "")
    if "occlusion_risk" in checks and source.get("type") == "window" and "bbox" in capture_method:
        issues.append(
            {
                "id": "occlusion_risk",
                "severity": "advisory",
                "message": "Window capture used a screen-bbox fallback, so another window may have occluded the target.",
                "evidence": {"capture_method": capture_method, "window": {"hwnd": window.get("hwnd"), "title": window.get("title")}},
            }
        )

    if "bbox_identity_mismatch" in checks and source.get("type") == "window" and "bbox" in capture_method:
        identity = source.get("visible_screen_identity") if isinstance(source.get("visible_screen_identity"), dict) else {}
        if identity.get("available") and not bool(identity.get("identity_verified", False)):
            issues.append(
                {
                    "id": "bbox_identity_mismatch",
                    "severity": "decision",
                    "message": "Visible-screen bbox fallback appears to be pointed at another topmost window, so saving could capture the wrong application.",
                    "evidence": identity,
                }
            )

    return issues


def render_guard_warning_payload(source, args):
    guard = render_guard_status(source, args)
    if not guard["issues"]:
        return None
    identity_mismatch_requires_decision = bool(guard.get("bbox_identity_mismatch")) and not bool(guard.get("allow_unverified_bbox_fallback"))
    background_unavailable_requires_decision = bool(guard.get("background_capture_unavailable")) and not bool(guard.get("confirmed"))
    if not identity_mismatch_requires_decision and not background_unavailable_requires_decision and (guard["confirmed"] or guard["mode"] == "save"):
        return None
    limits = runtime_limits(args)
    max_retry_count = int(limits.get("capture_render_retry_count_max") or 8)
    max_retry_interval_ms = int(limits.get("capture_render_retry_interval_ms_max") or 2000)
    current_retry_count = int(args.get("render_retry_count", 2))
    current_retry_interval_ms = int(args.get("render_retry_interval_ms", 250))
    is_strict_failure = guard["mode"] == "fail"
    issue_ids = [issue.get("id") for issue in guard["issues"]]
    payload = {
        "ok": not is_strict_failure,
        "saved": False,
        "path": None,
        "metadata_path": None,
        "result_state": "blocked" if is_strict_failure else "decision_required",
        "warning": "Capture guard detected possible incomplete output. Capture was deferred for a user/agent decision.",
        "message": "Choose whether to force a capture now, capture later, auto-wait until the frame appears rendered, or adjust the target before capture.",
        "reason": "capture_guard_decision",
        "issue_ids": issue_ids,
        "suspected_unrendered": guard["suspected_unrendered"],
        "capture_deferred": True,
        "requires_decision": not is_strict_failure,
        "requires_confirmation": not is_strict_failure,
        "render_guard": guard,
        "source": source,
        "available_actions": {
            "force_capture_now": {
                "render_guard_confirmed": True,
                "note": "Save the current blank-looking frame because the user/agent confirms it is expected or still useful.",
            },
            "capture_later": {
                "delay_seconds": 1,
                "render_guard": "warn",
                "note": "Wait a short fixed delay, then capture again and return the same decision warning if it still looks blank.",
            },
            "auto_detect_render_then_capture": {
                "wait_for_nonblank": True,
                "render_guard": "wait",
                "render_retry_count": min(max(current_retry_count, 2) + 2, max_retry_count),
                "render_retry_interval_ms": min(max(current_retry_interval_ms, 500), max_retry_interval_ms),
                "note": "Retry until the frame no longer looks blank within runtime limits, then save automatically.",
            },
        },
        "issue_specific_actions": {},
        "recommended_next": "Choose one of available_actions and call the same capture tool again with those arguments.",
        "privacy": "No screenshot was saved, uploaded, sent to a model, or retried in the background after this decision warning.",
    }
    if "minimized_window" in issue_ids:
        payload["issue_specific_actions"]["restore_window_then_capture"] = {
            "note": "Restore or bring the window visible, then retry with render_guard='wait'.",
            "render_guard": "wait",
        }
    if "offscreen_window" in issue_ids:
        payload["issue_specific_actions"]["move_window_visible_then_capture"] = {
            "note": "Move the target window fully onto a display, then retry capture.",
            "render_guard": "wait",
        }
    if "tiny_capture" in issue_ids:
        payload["issue_specific_actions"]["reselect_region_or_window"] = {
            "note": "Call list_displays/list_windows or choose a larger region before retrying.",
        }
    if "stale_frame" in issue_ids:
        payload["issue_specific_actions"]["refresh_or_wait_for_change"] = {
            "note": "Refresh the UI or use watch_change before retrying the capture.",
            "task": "watch_change",
        }
    if "occlusion_risk" in issue_ids:
        payload["issue_specific_actions"]["retry_quiet_window_capture"] = {
            "quiet_preferred": True,
            "render_guard": "wait",
            "guard_checks": ["unrendered", "occlusion_risk"],
            "note": "Retry the HWND/window route without accepting visible-screen bbox fallback output silently.",
        }
        payload["issue_specific_actions"]["retry_strict_background_capture"] = {
            "background_mode": "strict",
            "quiet_preferred": True,
            "render_guard": "wait",
            "guard_checks": ["unrendered", "window_client_low_information", "background_capture_unavailable"],
            "note": "Retry direct background HWND capture and do not save visible-screen bbox fallback pixels.",
        }
        payload["issue_specific_actions"]["allow_visible_bbox_fallback"] = {
            "background_mode": "visible_fallback",
            "quiet_preferred": False,
            "render_guard_confirmed": True,
            "note": "Accept the visible-screen fallback when the user understands the target may need to be visible or unobscured.",
        }
        payload["issue_specific_actions"]["bring_window_front_or_capture_screen"] = {
            "note": "Bring the target window forward or capture the visible screen/region instead of a fallback bbox.",
        }
    if "bbox_identity_mismatch" in issue_ids:
        payload["warning"] = "Visible-screen bbox fallback may be pointed at another topmost window. Capture was deferred to avoid saving the wrong application."
        payload["message"] = "Choose a safer retry path, bring the target forward, or explicitly allow an unverified visible-screen bbox capture."
        payload["available_actions"].pop("force_capture_now", None)
        payload["issue_specific_actions"].pop("allow_visible_bbox_fallback", None)
        payload["issue_specific_actions"]["retry_with_hwnd_or_exact_title"] = {
            "note": "Call list_windows, then retry with a specific hwnd or exact_title so the target identity is unambiguous.",
        }
        payload["issue_specific_actions"]["allow_unverified_bbox_fallback"] = {
            "background_mode": "visible_fallback",
            "quiet_preferred": False,
            "render_guard_confirmed": True,
            "allow_unverified_bbox_fallback": True,
            "note": "Last-resort visible-pixel capture. This may save another window if it is covering the target.",
        }
        payload["recommended_next"] = "Prefer retry_with_hwnd_or_exact_title or bring_window_front_or_capture_screen. Use allow_unverified_bbox_fallback only as a last resort."
    if "background_capture_unavailable" in issue_ids:
        payload["warning"] = "Strict background window capture did not produce reliable direct HWND graphics, so no visible-screen fallback was saved."
        payload["message"] = "Choose a strict retry with more render waiting, switch to a webpage/DOM route when the target is a browser page, or explicitly accept visible-screen fallback."
        payload["available_actions"].pop("force_capture_now", None)
        payload["issue_specific_actions"]["retry_strict_after_render_wait"] = {
            "background_mode": "strict",
            "quiet_preferred": True,
            "wait_for_nonblank": True,
            "render_guard": "wait",
            "render_retry_count": min(max(current_retry_count, 2) + 2, max_retry_count),
            "render_retry_interval_ms": min(max(current_retry_interval_ms, 500), max_retry_interval_ms),
            "guard_checks": ["unrendered", "window_client_low_information", "background_capture_unavailable"],
            "note": "Keep the capture occlusion-resistant and wait longer for direct HWND content before returning another decision.",
        }
        payload["issue_specific_actions"]["switch_to_webpage_route"] = {
            "tool": "capture_webpage",
            "background_mode": "strict",
            "note": "For browser content, use the webpage route with an explicit URL when possible instead of relying on window pixels.",
        }
        payload["issue_specific_actions"]["allow_visible_bbox_fallback"] = {
            "background_mode": "visible_fallback",
            "quiet_preferred": False,
            "render_guard": "warn",
            "note": "Explicitly switch to visible-screen bbox fallback. This is not occlusion-proof and should be treated as a visible screenshot route.",
        }
        payload["recommended_next"] = "Prefer retry_strict_after_render_wait or switch_to_webpage_route. Use allow_visible_bbox_fallback only when the user accepts visible desktop pixels."
    if is_strict_failure:
        payload["error"] = "Capture guard blocked suspected incomplete output because render_guard='fail'."
        payload["requires_confirmation"] = False
        payload["requires_decision"] = False
        payload["recommended_next"] = "Use render_guard='warn' or render_guard='wait' if the caller should receive decision options instead of a strict failure."
    return payload


def save_or_warn_capture(image, source, libs, args):
    warning = render_guard_warning_payload(source, args)
    if warning:
        return warning
    return save_capture_image(image, source, libs, args)


def normalized_webpage_url(args):
    url = str(args.get("url") or "").strip()
    if not url:
        raise ValueError("url is required")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https", "file"):
        raise ValueError("url must use http, https, or file")
    return url


def webpage_capture_options(args):
    limits = runtime_limits(args)
    mode = str(args.get("mode") or "full_page").strip().lower()
    aliases = {"full": "full_page", "long": "full_page", "long_image": "full_page", "current": "viewport", "node": "element"}
    mode = aliases.get(mode, mode)
    if mode not in ("full_page", "viewport", "element", "scroll_container"):
        raise ValueError("mode must be full_page, viewport, element, or scroll_container")
    width = int(args.get("viewport_width") or 1440)
    height = int(args.get("viewport_height") or 900)
    timeout_ms = int(args.get("timeout_ms") or 15000)
    full_page_height_max = int(args.get("full_page_height_max") or limits.get("webpage_capture_full_page_height_max") or 50000)
    check_min_max(width, 1, limits.get("webpage_capture_viewport_width_max"), "viewport_width")
    check_min_max(height, 1, limits.get("webpage_capture_viewport_height_max"), "viewport_height")
    check_min_max(timeout_ms, 100, limits.get("webpage_capture_timeout_ms_max"), "timeout_ms")
    check_min_max(full_page_height_max, 1, limits.get("webpage_capture_full_page_height_max"), "full_page_height_max")
    wait_until = str(args.get("wait_until") or "load").strip().lower()
    if wait_until not in ("commit", "domcontentloaded", "load", "networkidle"):
        raise ValueError("wait_until must be commit, domcontentloaded, load, or networkidle")
    device_scale_factor = float(args.get("device_scale_factor") or 1)
    if device_scale_factor <= 0:
        raise ValueError("device_scale_factor must be greater than 0")
    selector = str(args.get("selector") or "").strip()
    frame_selector = str(args.get("frame_selector") or "").strip()
    if mode in ("element", "scroll_container") and not selector:
        raise ValueError("selector is required when mode is element or scroll_container")
    scroll_axis = str(args.get("scroll_axis") or "vertical").strip().lower()
    if scroll_axis not in ("vertical",):
        raise ValueError("scroll_axis currently supports vertical only")
    max_segments = int(args.get("max_segments") or limits.get("webpage_capture_scroll_segments_max") or 80)
    segment_delay_ms = int(args.get("segment_delay_ms") or 100)
    check_min_max(max_segments, 1, limits.get("webpage_capture_scroll_segments_max"), "max_segments")
    check_min_max(segment_delay_ms, 0, limits.get("webpage_capture_segment_delay_ms_max"), "segment_delay_ms")
    fmt = normalized_format(args.get("format", "png"))
    quality = int(args.get("quality", 90))
    if fmt == "jpg":
        check_min_max(quality, limits.get("jpeg_quality_min"), limits.get("jpeg_quality_max"), "quality")
    settle_delay_ms = int(args.get("settle_delay_ms") or float(args.get("delay_seconds") or 0) * 1000)
    check_min_max(settle_delay_ms, 0, limits.get("capture_settle_delay_ms_max"), "settle_delay_ms")
    return {
        "mode": mode,
        "viewport_width": width,
        "viewport_height": height,
        "timeout_ms": timeout_ms,
        "full_page_height_max": full_page_height_max,
        "wait_until": wait_until,
        "device_scale_factor": device_scale_factor,
        "selector": selector,
        "frame_selector": frame_selector,
        "scroll_axis": scroll_axis,
        "max_segments": max_segments,
        "segment_delay_ms": segment_delay_ms,
        "format": fmt,
        "quality": quality,
        "settle_delay_ms": settle_delay_ms,
    }


def webpage_output_path(args, fmt):
    output_dir = ensure_cache_dir(output_routes(args)[0])
    merged = {"source_label": "webpage", **args}
    if args.get("mode"):
        merged["source_label"] = f"webpage-{safe_filename_part(args.get('mode'), 'capture')}"
    return output_dir / output_filename(merged, fmt)


def webpage_dimensions(page):
    return page.evaluate(
        """() => {
            const body = document.body || {};
            const html = document.documentElement || {};
            return {
              scrollWidth: Math.max(body.scrollWidth || 0, body.offsetWidth || 0, html.clientWidth || 0, html.scrollWidth || 0, html.offsetWidth || 0),
              scrollHeight: Math.max(body.scrollHeight || 0, body.offsetHeight || 0, html.clientHeight || 0, html.scrollHeight || 0, html.offsetHeight || 0),
              viewportWidth: window.innerWidth,
              viewportHeight: window.innerHeight,
              title: document.title || "",
              url: location.href
            };
        }"""
    )


def webpage_target_locator(page, options):
    if options.get("frame_selector"):
        return page.frame_locator(options["frame_selector"]).locator(options["selector"]).first
    return page.locator(options["selector"]).first


def scroll_container_info(locator):
    return locator.evaluate(
        """(el) => {
            const style = window.getComputedStyle(el);
            return {
              scrollTop: el.scrollTop,
              scrollLeft: el.scrollLeft,
              scrollHeight: el.scrollHeight,
              scrollWidth: el.scrollWidth,
              clientHeight: el.clientHeight,
              clientWidth: el.clientWidth,
              overflowY: style.overflowY,
              overflowX: style.overflowX
            };
        }"""
    )


def scroll_positions(total, viewport, max_segments):
    total = int(total or 0)
    viewport = max(1, int(viewport or 1))
    max_scroll = max(0, total - viewport)
    positions = list(range(0, max_scroll + 1, viewport))
    if not positions or positions[-1] != max_scroll:
        positions.append(max_scroll)
    seen = []
    for item in positions:
        if item not in seen:
            seen.append(item)
    if len(seen) > max_segments:
        return None
    return seen


def capture_scroll_container(page, options, output_path, args):
    libs, import_error = import_capture_libs()
    if import_error:
        raise RuntimeError("Pillow is required to stitch scroll-container screenshots.")
    Image = libs["Image"]
    locator = webpage_target_locator(page, options)
    locator.wait_for(state="visible", timeout=options["timeout_ms"])
    info = scroll_container_info(locator)
    total_height = int(info.get("scrollHeight") or 0)
    client_height = int(info.get("clientHeight") or 0)
    if total_height <= 0 or client_height <= 0:
        raise RuntimeError("scroll container has invalid dimensions")
    positions = scroll_positions(total_height, client_height, options["max_segments"])
    if positions is None:
        return {
            "deferred": True,
            "payload": {
                "ok": True,
                "capture_deferred": True,
                "reason": "scroll_container_too_many_segments",
                "message": "The nested scroll container requires more segments than the configured limit.",
                "container": info,
                "limit": {"max_segments": options["max_segments"]},
                "available_actions": {
                    "increase_max_segments": {"max_segments": math.ceil(total_height / max(1, client_height))},
                    "capture_visible_element": {"mode": "element"},
                    "capture_page_full_page": {"mode": "full_page"},
                },
            },
        }
    if total_height > options["full_page_height_max"] and not bool(args.get("allow_oversize", False)):
        return {
            "deferred": True,
            "payload": {
                "ok": True,
                "capture_deferred": True,
                "reason": "scroll_container_too_tall",
                "message": "The nested scroll container is taller than the configured limit.",
                "container": info,
                "limit": {"full_page_height_max": options["full_page_height_max"]},
                "available_actions": {
                    "force_scroll_container_capture": {"allow_oversize": True},
                    "capture_visible_element": {"mode": "element"},
                    "increase_limit": {"full_page_height_max": total_height},
                },
            },
        }
    original_scroll_top = int(info.get("scrollTop") or 0)
    segment_images = []
    with tempfile.TemporaryDirectory(prefix="screen-guardian-scroll-segments-") as tmp:
        for index, y in enumerate(positions):
            locator.evaluate("(el, y) => { el.scrollTop = y; }", y)
            if options["segment_delay_ms"] > 0:
                page.wait_for_timeout(options["segment_delay_ms"])
            segment_path = Path(tmp) / f"segment-{index:03d}.png"
            locator.screenshot(path=str(segment_path), timeout=options["timeout_ms"])
            segment_images.append((y, Image.open(segment_path).convert("RGB")))
        locator.evaluate("(el, y) => { el.scrollTop = y; }", original_scroll_top)
        first = segment_images[0][1]
        width_scale = first.size[0] / max(1, int(info.get("clientWidth") or first.size[0]))
        height_scale = first.size[1] / max(1, client_height)
        canvas_width = first.size[0]
        canvas_height = max(1, round(total_height * height_scale))
        stitched = Image.new("RGB", (canvas_width, canvas_height), "white")
        for y, image in segment_images:
            paste_y = round(y * height_scale)
            stitched.paste(image, (0, paste_y))
        if options["format"] == "jpg":
            stitched.save(output_path, "JPEG", quality=options["quality"])
        else:
            stitched.save(output_path, "PNG")
    return {
        "deferred": False,
        "container": info,
        "segments": len(segment_images),
        "positions": positions,
        "stitched_size": {"width": canvas_width, "height": canvas_height},
        "scale": {"width": round(width_scale, 4), "height": round(height_scale, 4)},
    }


def action_prepare_webpage_capture(args):
    try:
        url = normalized_webpage_url(args)
        options = webpage_capture_options(args)
    except Exception as exc:
        return error(str(exc))
    request = {
        "plugin": PLUGIN_NAME,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "webpage_capture_request",
        "url": url,
        "options": options,
        "context": capture_context(args),
        "execution": {
            "status": "prepared",
            "note": "This envelope does not navigate or capture. A Playwright/CDP/browser adapter can consume it later.",
        },
        "sources": [
            "Playwright supports fullPage screenshots.",
            "Chrome DevTools Protocol Page.captureScreenshot supports captureBeyondViewport.",
        ],
    }
    output_dir = ensure_cache_dir(get_cache_dir(args))
    filename = output_filename({"source_label": "webpage-capture-request", **args}, "json")
    request_path = output_dir / filename
    write_json_file(request_path, request)
    return write_json({"ok": True, "request_path": str(request_path), "request": request})


def action_capture_webpage(args):
    try:
        require_feature("webpage_capture", args)
    except Exception as exc:
        return error(str(exc), feature="webpage_capture")
    try:
        url = normalized_webpage_url(args)
        options = webpage_capture_options(args)
        status, libs = webpage_adapter_status(args)
        if not status.get("available"):
            return error("Webpage capture adapter is unavailable.", adapter=status, install_hint=status.get("install_hint"))
    except Exception as exc:
        return error(str(exc))

    sync_playwright = libs["sync_playwright"]
    output_path = webpage_output_path({**args, "mode": options["mode"]}, options["format"])
    browser = page = None
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": options["viewport_width"], "height": options["viewport_height"]},
                device_scale_factor=options["device_scale_factor"],
            )
            page.goto(url, wait_until=options["wait_until"], timeout=options["timeout_ms"])
            if options["settle_delay_ms"] > 0:
                page.wait_for_timeout(options["settle_delay_ms"])
            dims = webpage_dimensions(page)
            if options["mode"] == "full_page" and int(dims.get("scrollHeight") or 0) > options["full_page_height_max"] and not bool(args.get("allow_oversize", False)):
                browser.close()
                browser = None
                return write_json(
                    {
                        "ok": True,
                        "capture_deferred": True,
                        "reason": "webpage_too_tall",
                        "message": "The full webpage is taller than the configured limit. Choose whether to force capture, capture viewport, or raise the limit.",
                        "url": url,
                        "page": dims,
                        "limit": {"full_page_height_max": options["full_page_height_max"]},
                        "available_actions": {
                            "force_full_page_capture": {"allow_oversize": True},
                            "capture_viewport_only": {"mode": "viewport"},
                            "increase_limit": {"full_page_height_max": int(dims.get("scrollHeight") or options["full_page_height_max"])},
                        },
                    }
                )
            screenshot_args = {"path": str(output_path), "timeout": options["timeout_ms"]}
            if options["format"] == "jpg":
                screenshot_args["type"] = "jpeg"
                screenshot_args["quality"] = options["quality"]
            scroll_result = None
            if options["mode"] == "full_page":
                screenshot_args["full_page"] = True
                page.screenshot(**screenshot_args)
            elif options["mode"] == "scroll_container":
                scroll_result = capture_scroll_container(page, options, output_path, args)
                if scroll_result.get("deferred"):
                    browser.close()
                    browser = None
                    return write_json(scroll_result["payload"])
            elif options["mode"] == "element":
                locator = webpage_target_locator(page, options)
                locator.screenshot(**screenshot_args)
            else:
                page.screenshot(**screenshot_args)
            final_url = page.url
            title = page.title()
            browser.close()
            browser = None
    except Exception as exc:
        if browser:
            try:
                browser.close()
            except Exception:
                pass
        return error(
            "Webpage capture failed.",
            detail=str(exc),
            install_hint=f"If this is a browser install issue, run: {sys.executable} -m playwright install chromium",
        )

    metadata = {
        "plugin": PLUGIN_NAME,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "webpage_capture",
        "adapter": status["id"],
        "path": str(output_path),
        "source": {
            "type": "webpage",
            "url": url,
            "final_url": final_url,
            "title": title,
            "mode": options["mode"],
            "selector": options["selector"],
            "frame_selector": options["frame_selector"],
            "dimensions": dims,
            "scroll_container": scroll_result if scroll_result and not scroll_result.get("deferred") else None,
            "viewport": {"width": options["viewport_width"], "height": options["viewport_height"], "device_scale_factor": options["device_scale_factor"]},
        },
        "context": capture_context(args),
        "privacy": "Saved locally only. No upload, model call, or subagent handoff was performed.",
    }
    metadata_path = write_metadata_sidecar(output_path, metadata, args)
    result = {
        "ok": True,
        "saved": True,
        "capture_deferred": False,
        "requires_decision": False,
        "result_state": "saved",
        "adapter": status["id"],
        "path": str(output_path),
        "metadata_path": metadata_path,
        "source": metadata["source"],
        "context": metadata["context"],
        "privacy": metadata["privacy"],
    }
    if metadata["context"]["marked_file_only"]:
        result["context_delivery"] = "file_marked_only"
        result["note"] = "Webpage capture was saved with metadata. Send the file or analysis explicitly when needed."
    return write_json(result)


def grab_screen_once(args):
    adapter_id, libs = resolve_capture_adapter(args)
    with libs["mss"].MSS() as sct:
        box, display = capture_box(sct, args)
        shot = sct.grab(box)
        image = libs["Image"].frombytes("RGB", shot.size, shot.rgb)
    source = {
        "type": "screen",
        "adapter": adapter_id,
        "display": display,
        "display_index": display.get("display_index"),
        "coordinate_space": display.get("coordinate_space"),
        "capture_box": {
            "left": int(box["left"]),
            "top": int(box["top"]),
            "width": int(box["width"]),
            "height": int(box["height"]),
        },
    }
    return image, source, libs


def grab_window_once(args, status, libs, window):
    hwnd = int(window["hwnd"])
    background_mode = normalize_background_mode(args)
    fallback_allowed = visible_window_fallback_allowed(args)
    capture_method = "pillow-imagegrab-window"
    direct_content_status = {}
    direct_black = False
    direct_client_low_info = False
    direct_hwnd_error = ""
    try:
        image = libs["ImageGrab"].grab(window=hwnd)
        direct_content_status = window_client_content_status(image.convert("RGB"), libs, window)
        direct_black = image_looks_black(image, libs)
        direct_client_low_info = bool(direct_content_status.get("client_low_information", False))
        if fallback_allowed and (direct_black or direct_client_low_info):
            rect = window.get("rect") or {}
            if rect:
                capture_method = "pillow-imagegrab-bbox-after-black-window-frame" if direct_black else "pillow-imagegrab-bbox-after-low-info-window-client"
                image = libs["ImageGrab"].grab(
                    bbox=(rect["left"], rect["top"], rect["right"], rect["bottom"]),
                    all_screens=True,
                )
    except TypeError as exc:
        direct_hwnd_error = str(exc)
        rect = window.get("rect") or {}
        if not fallback_allowed:
            raise RuntimeError(
                "Strict background window capture is unavailable because this Pillow runtime does not support direct HWND capture; "
                "retry with background_mode='best_effort' or 'visible_fallback' only if visible-screen fallback is acceptable."
            )
        if not rect:
            raise
        capture_method = "pillow-imagegrab-bbox-fallback"
        image = libs["ImageGrab"].grab(
            bbox=(rect["left"], rect["top"], rect["right"], rect["bottom"]),
                all_screens=True,
            )
    visible_fallback_used = "bbox" in capture_method
    strict_background_unavailable = bool(
        background_mode == "strict"
        and not visible_fallback_used
        and (direct_black or direct_client_low_info or direct_hwnd_error)
    )
    source = {
        "type": "window",
        "adapter": status["id"],
        "capture_method": capture_method,
        "quiet_capture": {
            "preferred": quiet_capture_preferred(args, "window"),
            "foreground_activation_performed": False,
            "visible_screen_fallback": visible_fallback_used,
            "occlusion_risk_check_applicable": visible_fallback_used,
            "bbox_identity_check_applicable": visible_fallback_used,
            "direct_hwnd_guard_note": "occlusion_risk and bbox_identity_mismatch apply only after visible-screen bbox fallback; direct HWND capture uses client-content quality checks instead.",
        },
        "background_capture": {
            "mode": background_mode,
            "direct_hwnd_attempted": True,
            "direct_hwnd_error": direct_hwnd_error,
            "visible_screen_fallback_allowed": fallback_allowed,
            "visible_screen_fallback_used": visible_fallback_used,
            "foreground_activation_performed": False,
            "occlusion_resistant_current_frame": not visible_fallback_used,
            "strict_unavailable": strict_background_unavailable,
            "note": "Strict mode is a graphics/window acquisition attempt, not a visible desktop screenshot. It does not raise the target window and does not save a visible-screen bbox fallback.",
        },
        "window": window,
        "virtual_screen": virtual_screen_rect(),
        "capture_box": window.get("rect"),
        "direct_window_content": direct_content_status,
        "compatibility_note": "HWND capture is best-effort and does not activate or raise the target window. Strict background mode avoids visible-screen fallback but may return a decision when the app exposes only blank, stale, protected, or GPU-rendered client pixels.",
    }
    if visible_fallback_used:
        source["visible_screen_identity"] = bbox_identity_probe(window)
    return image.convert("RGB"), source, libs


def grab_window_image(args):
    status, libs = window_adapter_status()
    if not status["available"]:
        raise RuntimeError(status.get("import_error") or "Window capture adapter is unavailable")
    window = find_window(args)
    return grab_known_window_image(args, window, status, libs)


def window_pre_capture_guard_payload(args, window, status=None):
    checks = normalize_guard_checks(args)
    preflight_checks = {"minimized_window", "offscreen_window", "tiny_capture"}
    if not any(check in checks for check in preflight_checks):
        return None
    background_mode = normalize_background_mode(args)
    source = {
        "type": "window",
        "adapter": (status or {}).get("id") or "pillow-window",
        "capture_method": "preflight-window-state",
        "quiet_capture": {
            "preferred": quiet_capture_preferred(args, "window"),
            "foreground_activation_performed": False,
            "visible_screen_fallback": False,
            "occlusion_risk_check_applicable": False,
            "bbox_identity_check_applicable": False,
            "direct_hwnd_guard_note": "Pre-capture window-state guards run before any HWND or visible-screen grab is attempted.",
        },
        "background_capture": {
            "mode": background_mode,
            "direct_hwnd_attempted": False,
            "direct_hwnd_error": "",
            "visible_screen_fallback_allowed": background_mode != "strict",
            "visible_screen_fallback_used": False,
            "foreground_activation_performed": False,
            "occlusion_resistant_current_frame": background_mode == "strict",
            "strict_unavailable": False,
            "note": "Window-state guard returned a decision before capture, so no desktop pixels or direct HWND pixels were saved.",
        },
        "window": window,
        "virtual_screen": virtual_screen_rect(),
        "capture_box": window.get("rect"),
        "render_timing": {
            "delay_seconds": 0,
            "wait_for_nonblank": False,
            "render_guard": normalize_render_guard(args, "window"),
            "attempts": [],
            "final_attempt": {},
            "final_likely_blank": False,
            "note": "No render attempt was made because a pre-capture window-state guard requires a decision first.",
        },
        "compatibility_note": "Pre-capture guards prevent minimized, offscreen, or tiny window states from turning into low-level grab errors or misleading blank images.",
    }
    payload = render_guard_warning_payload(source, args)
    if payload:
        payload["reason"] = "window_pre_capture_guard_decision"
        payload["warning"] = "Window state suggests this capture may be incomplete or misleading. Capture was deferred before any grab was attempted."
        payload["message"] = "Restore or move the target window, choose a safer route, or explicitly confirm that this state should still be captured."
        payload["privacy"] = "No screenshot was saved, uploaded, sent to a model, or retried in the background after this pre-capture decision warning."
    return payload


def grab_known_window_image(args, window, status=None, libs=None):
    if status is None or libs is None:
        status, libs = window_adapter_status()
        if not status["available"]:
            raise RuntimeError(status.get("import_error") or "Window capture adapter is unavailable")
    settle_delay = capture_settle_delay_seconds(args)
    if settle_delay:
        time.sleep(settle_delay)
    if capture_modes_include(args, "wait_buffer"):
        wait_for_stable_frames(args, lambda: grab_window_once(args, status, libs, window))
    wait_for_nonblank, retry_count, retry_interval = render_retry_options(args, default_wait_for_nonblank=True)
    attempts = []
    image = source = None
    for attempt in range(retry_count + 1):
        image, source, libs = grab_window_once(args, status, libs, window)
        metrics = image_blank_metrics(image, libs)
        attempts.append({"attempt": attempt + 1, **metrics})
        if not wait_for_nonblank or not metrics["likely_blank"] or attempt >= retry_count:
            break
        time.sleep(retry_interval)
    source = with_render_timing(source, args, attempts, settle_delay, wait_for_nonblank)
    source = with_capture_strategy(source, args)
    return image, source, libs


def image_difference_score(a, b, libs):
    ImageChops = libs["ImageChops"]
    ImageStat = libs["ImageStat"]
    if a.size != b.size:
        b = b.resize(a.size)
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    stat = ImageStat.Stat(diff)
    return sum(stat.mean) / 3.0


def import_audio_libs():
    try:
        import sounddevice as sd

        return {"sounddevice": sd}, None
    except Exception as exc:
        return None, str(exc)


def audio_adapter_status(args=None):
    args = args or {}
    status = {
        "id": "sounddevice",
        "label": "SoundDevice optional audio capture",
        "role": "audio_capture",
        "available": False,
        "dependencies": ["sounddevice", "numpy", "PortAudio"],
        "capabilities": ["list_audio_devices", "record_microphone", "record_wasapi_loopback_best_effort"],
        "feature_active": feature_enabled("audio_capture", args),
        "compatibility_note": "Optional adapter. It is not imported until an audio tool probes or records.",
    }
    if not feature_enabled("audio_capture", args):
        status["import_skipped"] = True
        status["install_hint"] = "Enable audio_capture with set_feature_flags before probing or recording audio."
        return status, None
    libs, import_error = import_audio_libs()
    status["available"] = import_error is None
    if import_error:
        status["import_error"] = import_error
        status["install_hint"] = f"{sys.executable} -m pip install --user -r scripts/optional-audio-requirements.txt"
    else:
        status["version"] = getattr(libs["sounddevice"], "__version__", "unknown")
    return status, libs


def ffmpeg_status():
    executable = shutil.which("ffmpeg")
    return {
        "id": "ffmpeg",
        "label": "FFmpeg audio extraction",
        "role": "video_audio_extract",
        "available": bool(executable),
        "executable": executable or "",
        "capabilities": ["extract_audio_track", "pcm_wav"],
        "install_hint": "Install FFmpeg and make ffmpeg available on PATH." if not executable else "",
    }


def import_playwright_libs():
    try:
        from playwright.sync_api import sync_playwright

        return {"sync_playwright": sync_playwright}, None
    except Exception as exc:
        return None, str(exc)


def webpage_adapter_status(args=None):
    args = args or {}
    status = {
        "id": "playwright-chromium",
        "label": "Playwright Chromium webpage capture",
        "role": "webpage_capture",
        "available": False,
        "dependencies": ["playwright", "chromium browser"],
        "capabilities": [
            "full_page_screenshot",
            "viewport_screenshot",
            "element_screenshot",
            "scroll_container_stitching",
            "iframe_targeting",
            "render_wait",
        ],
        "feature_active": feature_enabled("webpage_capture", args),
        "compatibility_note": "Optional browser-rendered route for full scrollable webpages. It is separate from lightweight screen/window capture.",
    }
    if not feature_enabled("webpage_capture", args):
        status["import_skipped"] = True
        status["install_hint"] = "Enable webpage_capture with set_feature_flags before probing or capturing webpages."
        return status, None
    libs, import_error = import_playwright_libs()
    status["available"] = import_error is None
    if import_error:
        status["import_error"] = import_error
        status["install_hint"] = f"{sys.executable} -m pip install --user -r scripts/optional-web-requirements.txt && {sys.executable} -m playwright install chromium"
    else:
        status["install_hint"] = f"If Chromium is missing, run: {sys.executable} -m playwright install chromium"
    return status, libs


def audio_output_path(args, fmt="wav"):
    output_dir = ensure_cache_dir(output_routes(args)[0])
    merged = dict(args)
    merged.setdefault("source_label", args.get("source_label") or "audio")
    return output_dir / output_filename(merged, fmt)


def audio_context_payload(args):
    context = capture_context(args)
    return {
        "project": context["project"],
        "workflow": context["workflow"],
        "tags": context["tags"],
        "note": context["note"],
        "context_policy": context["context_policy"],
        "marked_file_only": context["marked_file_only"],
    }


def analyze_wav_file(path, args=None):
    args = args or {}
    require_feature("audio_analysis", args)
    threshold = float(args.get("silence_threshold", 0.01))
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.getnframes()
        duration = frames / float(sample_rate or 1)
        if sample_width != 2:
            return {
                "duration_seconds": round(duration, 3),
                "channels": channels,
                "sample_rate": sample_rate,
                "sample_width": sample_width,
                "analysis_limited": True,
                "note": "Only 16-bit PCM WAV amplitude metrics are currently supported.",
            }
        total_samples = 0
        sum_squares = 0.0
        peak = 0
        silent_samples = 0
        chunk_frames = 4096
        while True:
            data = wav.readframes(chunk_frames)
            if not data:
                break
            samples = array.array("h")
            samples.frombytes(data)
            if sys.byteorder != "little":
                samples.byteswap()
            for sample in samples:
                value = abs(int(sample))
                total_samples += 1
                sum_squares += value * value
                peak = max(peak, value)
                if value / 32768.0 <= threshold:
                    silent_samples += 1
        rms = math.sqrt(sum_squares / total_samples) if total_samples else 0.0
        rms_norm = rms / 32768.0
        peak_norm = peak / 32768.0
        silent_fraction = silent_samples / float(total_samples or 1)
    likely_silent = rms_norm < threshold and peak_norm < threshold * 3
    likely_clipping = peak_norm >= 0.98
    return {
        "duration_seconds": round(duration, 3),
        "channels": channels,
        "sample_rate": sample_rate,
        "sample_width": sample_width,
        "rms": round(rms_norm, 5),
        "peak": round(peak_norm, 5),
        "silent_fraction": round(silent_fraction, 4),
        "likely_silent": likely_silent,
        "likely_clipping": likely_clipping,
        "diagnostic_hint": "No meaningful audio detected." if likely_silent else "Audio energy detected.",
    }


def write_wav(path, frames_bytes, sample_rate, channels):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(int(channels))
        wav.setsampwidth(2)
        wav.setframerate(int(sample_rate))
        wav.writeframes(frames_bytes)


def args_with_region_from_flat(args):
    if args.get("region"):
        return dict(args)
    if all(key in args for key in ("left", "top", "width", "height")):
        forwarded = dict(args)
        forwarded["region"] = {
            "left": args.get("left", 0),
            "top": args.get("top", 0),
            "width": args.get("width", 0),
            "height": args.get("height", 0),
            "relative_to_display": args.get("relative_to_display", True),
        }
        return forwarded
    return dict(args)


def grab_watch_image(args):
    window_keys = ("hwnd", "exact_title", "title_contains", "title_contains_any", "process_name", "process_names")
    if any(args.get(key) for key in window_keys):
        return grab_window_image(args)
    return grab_screen_image(args)


def action_get_runtime_settings(args):
    config = load_config()
    primary, mirrors = output_routes({})
    return write_json(
        {
            "ok": True,
            "config_path": str(CONFIG_PATH),
            "default_cache_dir": str(DEFAULT_CACHE_DIR),
            "active_cache_dir": str(primary),
            "cache_dir_configured": str(config.get("cache_dir") or ""),
            "extra_output_dirs": serialize_paths(mirrors),
            "runtime_limits": config.get("runtime_limits", {}),
            "runtime_limit_units": {
                "watch_duration_seconds_max": "seconds",
                "watch_interval_seconds_min": "seconds",
                "watch_interval_seconds_max": "seconds",
                "watch_max_captures_max": "frames",
                "watch_burst_frames_max": "frames",
                "capture_scale_min": "multiplier",
                "capture_scale_max": "multiplier",
                "capture_settle_delay_ms_max": "milliseconds",
                "capture_render_retry_count_max": "attempts",
                "capture_render_retry_interval_ms_max": "milliseconds",
                "capture_stable_wait_seconds_max": "seconds",
                "capture_stable_interval_ms_min": "milliseconds",
                "capture_stable_interval_ms_max": "milliseconds",
                "capture_error_wait_seconds_max": "seconds",
                "capture_error_poll_interval_ms_min": "milliseconds",
                "capture_error_poll_interval_ms_max": "milliseconds",
                "window_survey_window_count_max": "windows",
                "window_survey_capture_count_max": "captures",
                "jpeg_quality_min": "encoder quality",
                "jpeg_quality_max": "encoder quality",
                "audio_duration_seconds_max": "seconds",
                "audio_sample_rate_max": "Hz",
                "audio_channels_max": "channels",
                "audio_extract_duration_seconds_max": "seconds",
                "raw_exec_timeout_seconds_max": "seconds",
                "raw_exec_output_chars_max": "characters",
                "webpage_capture_timeout_ms_max": "milliseconds",
                "webpage_capture_viewport_width_max": "CSS pixels",
                "webpage_capture_viewport_height_max": "CSS pixels",
                "webpage_capture_full_page_height_max": "CSS pixels",
                "webpage_capture_scroll_segments_max": "segments",
                "webpage_capture_segment_delay_ms_max": "milliseconds",
            },
            "feature_flags": config.get("feature_flags", {}),
            "feature_catalog": FEATURE_CATALOG,
            "extension_routes": config.get("extension_routes", []),
            "decision_policies": config.get("decision_policies", []),
            "monitor_profiles": config.get("monitor_profiles", []),
            "display_profile": build_display_profile(config),
        }
    )


def action_set_cache_path(args):
    cache_dir = str(args.get("cache_dir") or "").strip()
    config = load_config()
    if cache_dir:
        path = ensure_cache_dir(Path(cache_dir).expanduser())
        config["cache_dir"] = str(path)
    else:
        config["cache_dir"] = ""
    save_config(config)
    return write_json(
        {
            "ok": True,
            "config_path": str(CONFIG_PATH),
            "active_cache_dir": str(get_cache_dir({})),
            "cache_dir_configured": str(config.get("cache_dir") or ""),
        }
    )


def action_set_storage_routes(args):
    config = load_config()
    if "cache_dir" in args:
        cache_dir = str(args.get("cache_dir") or "").strip()
        if cache_dir:
            config["cache_dir"] = str(ensure_cache_dir(Path(cache_dir).expanduser()))
        else:
            config["cache_dir"] = ""
    if bool(args.get("clear_extra_output_dirs", False)):
        config["extra_output_dirs"] = []
    if "extra_output_dirs" in args:
        dirs = []
        for path in normalize_path_list(args.get("extra_output_dirs")):
            if bool(args.get("create_dirs", True)):
                path = ensure_cache_dir(path)
            dirs.append(str(path))
        config["extra_output_dirs"] = dirs
    save_config(config)
    primary, mirrors = output_routes({})
    return write_json(
        {
            "ok": True,
            "config_path": str(CONFIG_PATH),
            "active_cache_dir": str(primary),
            "extra_output_dirs": serialize_paths(mirrors),
        }
    )


def action_set_runtime_limits(args):
    config = load_config()
    if bool(args.get("reset", False)):
        config["runtime_limits"] = copy.deepcopy(DEFAULT_LIMITS)
    updates = args.get("limits") or {}
    if not isinstance(updates, dict):
        return error("limits must be an object")
    allowed = set(DEFAULT_LIMITS.keys())
    for key, value in updates.items():
        if key not in allowed:
            return error(f"Unknown runtime limit: {key}", allowed=sorted(allowed))
        try:
            config["runtime_limits"][key] = parse_unbounded_number(value)
        except Exception:
            return error(f"Invalid numeric value for {key}")
    save_config(config)
    return write_json(
        {
            "ok": True,
            "config_path": str(CONFIG_PATH),
            "runtime_limits": config["runtime_limits"],
            "note": "Persistent limits are the hard boundary. Per-call runtime_limits can only tighten these values; use null, 'none', or 'unbounded' here to remove a configurable persistent limit where the backend still permits it.",
        }
    )


def action_set_feature_flags(args):
    config = load_config()
    if bool(args.get("reset", False)):
        config["feature_flags"] = copy.deepcopy(DEFAULT_FEATURE_FLAGS)
    updates = args.get("flags") or {}
    if not isinstance(updates, dict):
        return error("flags must be an object")
    allowed = set(DEFAULT_FEATURE_FLAGS.keys())
    for key, value in updates.items():
        if key not in allowed:
            return error(f"Unknown feature flag: {key}", allowed=sorted(allowed))
        config["feature_flags"][key] = bool(value)
    save_config(config)
    return write_json(
        {
            "ok": True,
            "config_path": str(CONFIG_PATH),
            "feature_flags": config["feature_flags"],
            "feature_catalog": FEATURE_CATALOG,
            "note": "Inactive persistent features return at the tool boundary or skip optional work. Per-call feature_flags can only disable features for one call, not enable disabled features.",
        }
    )


def action_list_capture_routes(args):
    include_examples = bool(args.get("include_examples", True))
    routes = copy.deepcopy(CAPTURE_ROUTE_CATALOG)
    flags = feature_flags(args)
    routes["webpage"]["active"] = bool(flags.get("webpage_capture"))
    routes["webpage"]["status"] = "enabled" if routes["webpage"]["active"] else "inactive_optional_adapter"
    routes["webpage"]["activation_hint"] = "Enable feature flag webpage_capture and install scripts/optional-web-requirements.txt before direct capture_webpage use."
    routes["nested_scroll"]["active"] = bool(flags.get("webpage_capture"))
    routes["nested_scroll"]["status"] = "enabled" if routes["nested_scroll"]["active"] else "inactive_optional_adapter"
    routes["nested_scroll"]["activation_hint"] = routes["webpage"]["activation_hint"]
    if include_examples:
        routes["desktop"]["example"] = {"tool": "capture_region", "args": {"left": 0, "top": 0, "width": 800, "height": 600}}
        routes["application"]["example"] = {"tool": "capture_window", "args": {"title_contains": "Chrome", "render_guard": "wait"}}
        routes["webpage"]["example"] = {"tool": "capture_webpage", "args": {"url": "https://example.com", "mode": "full_page"}}
        routes["nested_scroll"]["example"] = {
            "tool": "capture_webpage",
            "args": {"url": "https://example.com/admin", "mode": "scroll_container", "selector": ".table-scroll"},
        }
        routes["chain"]["example"] = {
            "tool": "prepare_capture_chain",
            "args": {
                "objective": "Wait for an error panel, capture the target, preprocess text, then prepare a model request.",
                "route": "application",
                "trigger": {"type": "error_text", "contains": "error"},
                "steps": [{"tool": "capture_window"}, {"tool": "preprocess_image", "preset": "text"}, {"tool": "prepare_model_request"}],
            },
        }
    return write_json(
        {
            "ok": True,
            "routes": routes,
            "default_route_guidance": {
                "desktop": "Use for visible desktop pixels and old-system fallback.",
                "application": "Use for a specific Windows program/window without treating it as a browser page.",
                "webpage": "Use browser-rendered capture for full scrollable pages or DOM-targeted elements.",
                "nested_scroll": "Use browser-rendered scroll-container stitching for embedded tables, panels, and iframes.",
            },
            "quiet_capture": {
                "desktop": "not quiet; captures visible desktop pixels",
                "application": "quiet-preferred by default through HWND/window adapter; visible-screen bbox fallback returns a decision warning before saving",
                "webpage": "quiet through headless browser when webpage_capture is enabled",
            },
            "feature_flags": {
                "webpage_capture": bool(flags.get("webpage_capture")),
                "note": "Webpage and nested_scroll routes are listed for route planning, but direct browser-rendered capture is inactive until webpage_capture=true.",
            },
            "privacy": "Listing routes does not capture, navigate, record, upload, call a model, or start monitoring.",
        }
    )


def action_prepare_capture_chain(args):
    try:
        require_feature("capture_chains", args)
    except Exception as exc:
        return error(str(exc), feature="capture_chains")
    objective = str(args.get("objective") or "").strip()
    if not objective:
        return error("objective is required")
    route = str(args.get("route") or "auto").strip().lower()
    allowed_routes = ("auto", "desktop", "application", "webpage", "nested_scroll", "mixed")
    if route not in allowed_routes:
        return error("route must be auto, desktop, application, webpage, nested_scroll, or mixed")
    trigger = args.get("trigger") if isinstance(args.get("trigger"), dict) else {"type": "manual"}
    trigger_type = str(trigger.get("type") or "manual").strip().lower()
    allowed_triggers = (
        "manual",
        "delay",
        "schedule",
        "screen_change",
        "window_change",
        "selector_visible",
        "error_text",
        "model_feature",
        "audio_feature",
        "custom",
    )
    if trigger_type not in allowed_triggers:
        return error(f"trigger.type must be one of: {', '.join(allowed_triggers)}")
    steps = args.get("steps") if isinstance(args.get("steps"), list) else []
    if not steps:
        steps = [{"tool": "capture_webpage" if route in ("webpage", "nested_scroll") else "capture_window" if route == "application" else "capture_screen"}]
    normalized_steps = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            return error("each step must be an object", step_index=index)
        normalized_steps.append(
            {
                "index": index,
                "tool": str(step.get("tool") or step.get("action") or "").strip(),
                "args": step.get("args") if isinstance(step.get("args"), dict) else {},
                "condition": step.get("condition") if isinstance(step.get("condition"), dict) else {},
                "on_failure": str(step.get("on_failure") or "return_decision").strip(),
                "note": str(step.get("note") or "").strip(),
            }
        )
    chain = {
        "plugin": PLUGIN_NAME,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "capture_chain_request",
        "objective": objective,
        "route": route,
        "route_catalog": copy.deepcopy(CAPTURE_ROUTE_CATALOG),
        "quiet": bool(args.get("quiet", True)),
        "trigger": trigger,
        "steps": normalized_steps,
        "decision_policy_id": str(args.get("decision_policy_id") or "").strip(),
        "settings": args.get("settings") if isinstance(args.get("settings"), dict) else {},
        "context": capture_context(args),
        "execution": {
            "status": "prepared",
            "note": "This chain is a local plan only. Screen Guardian does not execute screenshots, browser navigation, scripts, APIs, subagents, or background schedulers from this envelope.",
        },
        "available_execution_paths": {
            "foreground_bounded_watch": "A caller may translate trigger=screen_change/window_change into watch_screen.",
            "browser_quiet_capture": "A caller may translate webpage/nested_scroll steps into capture_webpage when webpage_capture is enabled.",
            "decision_or_subagent": "A caller may pass this envelope to a decision policy, route, or subagent.",
        },
    }
    output_dir = ensure_cache_dir(get_cache_dir(args))
    filename = output_filename({"source_label": "capture-chain", **args}, "json")
    request_path = output_dir / filename
    write_json_file(request_path, chain)
    return write_json({"ok": True, "request_path": str(request_path), "chain": chain})


def normalized_route(args):
    route_id = safe_filename_part(args.get("id") or args.get("route_id") or "", "")
    if not route_id:
        raise ValueError("route id is required")
    role = str(args.get("role") or "vision_summary").strip().lower()
    allowed_roles = ("judgment", "ocr", "vision_summary", "video_summary", "audio_summary", "sound_diagnostics", "transcription", "custom")
    if role not in allowed_roles:
        raise ValueError("role must be judgment, ocr, vision_summary, video_summary, audio_summary, sound_diagnostics, transcription, or custom")
    settings = args.get("settings") or {}
    if not isinstance(settings, dict):
        raise ValueError("settings must be an object")
    handoff_mode = str(args.get("handoff_mode") or "prepared_file").strip().lower()
    allowed_handoff_modes = ("prepared_file", "external_api", "codex_subagent", "local_command")
    if handoff_mode not in allowed_handoff_modes:
        raise ValueError("handoff_mode must be prepared_file, external_api, codex_subagent, or local_command")
    activation_feature = ROLE_FEATURES.get(role, "extension_routes")
    return {
        "id": route_id,
        "role": role,
        "activation_feature": activation_feature,
        "active": feature_enabled(activation_feature),
        "enabled": bool(args.get("enabled", True)),
        "handoff_mode": handoff_mode,
        "provider": str(args.get("provider") or "").strip(),
        "model": str(args.get("model") or "").strip(),
        "endpoint": str(args.get("endpoint") or "").strip(),
        "api_key_env": str(args.get("api_key_env") or "").strip(),
        "command": str(args.get("command") or "").strip(),
        "capabilities": normalized_tags(args.get("capabilities")),
        "settings": settings,
        "notes": str(args.get("notes") or "").strip(),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def route_prior(role):
    priors = {
        "vision_summary": {
            "feature": "image_narration_routes",
            "input_types": ["image"],
            "handoff_modes": ["prepared_file", "external_api", "codex_subagent"],
            "settings": ["temperature", "quality", "max_tokens", "detail", "language"],
        },
        "video_summary": {
            "feature": "video_narration_routes",
            "input_types": ["video", "image_sequence", "keyframes"],
            "handoff_modes": ["prepared_file", "external_api", "codex_subagent"],
            "settings": ["temperature", "quality", "max_tokens", "detail", "fps", "keyframe_policy", "language"],
            "note": "Video narration providers are relatively few; this interface keeps provider/model choice outside the capture core.",
        },
        "ocr": {
            "feature": "ocr_routes",
            "input_types": ["image"],
            "handoff_modes": ["prepared_file", "external_api", "codex_subagent", "local_command"],
            "settings": ["language", "quality", "layout_mode"],
        },
        "transcription": {
            "feature": "audio_transcription_routes",
            "input_types": ["audio", "video"],
            "handoff_modes": ["prepared_file", "external_api", "codex_subagent"],
            "settings": ["language", "temperature", "timestamps"],
        },
        "audio_summary": {
            "feature": "audio_transcription_routes",
            "input_types": ["audio", "extracted_audio"],
            "handoff_modes": ["prepared_file", "external_api", "codex_subagent", "local_command"],
            "settings": ["temperature", "quality", "max_tokens", "language", "timestamps"],
            "note": "Audio summary routes can diagnose recordings, explain lectures, or describe program sound effects.",
        },
        "sound_diagnostics": {
            "feature": "audio_analysis",
            "input_types": ["audio"],
            "handoff_modes": ["prepared_file", "local_command"],
            "settings": ["silence_threshold", "rms_threshold", "clipping_threshold"],
            "note": "Local diagnostics can detect silence, clipping, and basic energy before a model is used.",
        },
    }
    return priors.get(role, {"feature": "extension_routes", "input_types": ["file"], "handoff_modes": ["prepared_file"]})


def route_with_current_activation(route, args=None):
    if not isinstance(route, dict):
        return route
    decorated = copy.deepcopy(route)
    activation_feature = decorated.get("activation_feature") or ROLE_FEATURES.get(decorated.get("role"), "extension_routes")
    decorated["activation_feature"] = activation_feature
    decorated["active"] = bool(decorated.get("enabled", True)) and feature_enabled(activation_feature, args)
    return decorated


def action_list_extension_routes(args):
    try:
        require_feature("extension_routes", args)
    except Exception as exc:
        return error(str(exc), feature="extension_routes")
    config = load_config()
    flags = feature_flags(args)
    role = str(args.get("role") or "").strip().lower()
    routes = config.get("extension_routes", [])
    if role:
        routes = [route for route in routes if str(route.get("role", "")).lower() == role]
    routes = [route_with_current_activation(route, args) for route in routes]
    return write_json(
        {
            "ok": True,
            "routes": routes,
            "contract": {
                "roles": ["judgment", "ocr", "vision_summary", "video_summary", "audio_summary", "sound_diagnostics", "transcription", "custom"],
                "settings_examples": ["temperature", "quality", "max_tokens", "detail", "language", "timestamps", "keyframe_policy"],
                "handoff_modes": ["prepared_file", "external_api", "codex_subagent", "local_command"],
                "feature_flags": flags,
                "execution": "Routes are registered only in the ultra-light model. External adapters can read prepared request files.",
            },
        }
    )


def action_set_extension_route(args):
    try:
        require_feature("extension_routes", args)
    except Exception as exc:
        return error(str(exc), feature="extension_routes")
    config = load_config()
    route_id = safe_filename_part(args.get("id") or args.get("route_id") or "", "")
    if bool(args.get("remove", False)):
        if not route_id:
            return error("route id is required when remove is true")
        config["extension_routes"] = [route for route in config.get("extension_routes", []) if route.get("id") != route_id]
        save_config(config)
        return write_json({"ok": True, "removed": route_id, "routes": config["extension_routes"]})
    try:
        route = normalized_route(args)
    except Exception as exc:
        return error(str(exc))
    routes = [item for item in config.get("extension_routes", []) if item.get("id") != route["id"]]
    routes.append(route)
    config["extension_routes"] = routes
    save_config(config)
    return write_json({"ok": True, "route": route, "routes": routes})


def route_by_id(config, route_id, args=None):
    for route in config.get("extension_routes", []):
        if route.get("id") == route_id:
            return route_with_current_activation(route, args)
    return None


def action_prepare_model_request(args):
    try:
        require_feature("model_request_envelopes", args)
    except Exception as exc:
        return error(str(exc), feature="model_request_envelopes")
    config = load_config()
    route_id = str(args.get("route_id") or "").strip()
    route = route_by_id(config, route_id, args) if route_id else None
    role = str(args.get("role") or (route or {}).get("role") or "vision_summary").strip().lower()
    settings = {}
    if route and isinstance(route.get("settings"), dict):
        settings.update(route["settings"])
    if isinstance(args.get("settings"), dict):
        settings.update(args["settings"])
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        prompt = "Describe this visual artifact compactly for an AI agent."
    request = {
        "plugin": PLUGIN_NAME,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "role": role,
        "route_id": route_id,
        "route": route,
        "input_path": str(Path(str(args.get("path") or "")).expanduser()) if args.get("path") else "",
        "prompt": prompt,
        "followup_of": str(args.get("followup_of") or "").strip(),
        "questions": normalized_tags(args.get("questions")),
        "settings": settings,
        "route_prior": route_prior(role),
        "feature_flags": feature_flags(args),
        "context": capture_context(args),
        "execution": {
            "status": "prepared",
            "note": "Ultra-light Screen Guardian writes a request envelope only. A model/subagent adapter can execute it and write a response.",
        },
    }
    output_dir = ensure_cache_dir(get_cache_dir(args))
    filename = output_filename({"source_label": f"model-request-{role}", **args}, "json")
    request_path = output_dir / filename
    write_json_file(request_path, request)
    return write_json({"ok": True, "request_path": str(request_path), "request": request})


def normalized_decision_policy(args):
    policy_id = safe_filename_part(args.get("id") or args.get("policy_id") or "", "")
    if not policy_id:
        raise ValueError("decision policy id is required")
    mode = str(args.get("mode") or "function_route").strip().lower()
    allowed_modes = ("manual", "rule_table", "scoring_function", "function_route", "prepared_file", "codex_subagent", "external_api", "local_command")
    if mode not in allowed_modes:
        raise ValueError("mode must be manual, rule_table, scoring_function, function_route, prepared_file, codex_subagent, external_api, or local_command")
    role = str(args.get("role") or "capture_decision").strip().lower()
    settings = args.get("settings") or {}
    if not isinstance(settings, dict):
        raise ValueError("settings must be an object")
    return {
        "id": policy_id,
        "role": role,
        "enabled": bool(args.get("enabled", True)),
        "mode": mode,
        "route_id": str(args.get("route_id") or "").strip(),
        "objective": str(args.get("objective") or "").strip(),
        "input_schema": args.get("input_schema") if isinstance(args.get("input_schema"), dict) else {},
        "output_schema": args.get("output_schema") if isinstance(args.get("output_schema"), dict) else {},
        "rules": args.get("rules") if isinstance(args.get("rules"), list) else [],
        "candidates": args.get("candidates") if isinstance(args.get("candidates"), list) else [],
        "constraints": args.get("constraints") if isinstance(args.get("constraints"), list) else [],
        "settings": settings,
        "notes": str(args.get("notes") or "").strip(),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def action_list_decision_policies(args):
    try:
        require_feature("decision_policies", args)
    except Exception as exc:
        return error(str(exc), feature="decision_policies")
    config = load_config()
    role = str(args.get("role") or "").strip().lower()
    policies = config.get("decision_policies", [])
    if role:
        policies = [policy for policy in policies if str(policy.get("role", "")).lower() == role]
    return write_json(
        {
            "ok": True,
            "policies": policies,
            "contract": {
                "modes": ["manual", "rule_table", "scoring_function", "function_route", "prepared_file", "codex_subagent", "external_api", "local_command"],
                "note": "Decision policies are not limited to simple increments. Arbitrary complexity can live behind a route, subagent, API, or local command adapter.",
            },
        }
    )


def action_set_decision_policy(args):
    try:
        require_feature("decision_policies", args)
    except Exception as exc:
        return error(str(exc), feature="decision_policies")
    config = load_config()
    policy_id = safe_filename_part(args.get("id") or args.get("policy_id") or "", "")
    if bool(args.get("remove", False)):
        if not policy_id:
            return error("decision policy id is required when remove is true")
        config["decision_policies"] = [policy for policy in config.get("decision_policies", []) if policy.get("id") != policy_id]
        save_config(config)
        return write_json({"ok": True, "removed": policy_id, "policies": config["decision_policies"]})
    try:
        policy = normalized_decision_policy(args)
    except Exception as exc:
        return error(str(exc))
    policies = [item for item in config.get("decision_policies", []) if item.get("id") != policy["id"]]
    policies.append(policy)
    config["decision_policies"] = policies
    save_config(config)
    return write_json({"ok": True, "policy": policy, "policies": policies})


def decision_policy_by_id(config, policy_id):
    for policy in config.get("decision_policies", []):
        if policy.get("id") == policy_id:
            return copy.deepcopy(policy)
    return None


def action_prepare_decision_request(args):
    try:
        require_feature("decision_policies", args)
    except Exception as exc:
        return error(str(exc), feature="decision_policies")
    config = load_config()
    policy_id = str(args.get("policy_id") or "").strip()
    policy = decision_policy_by_id(config, policy_id) if policy_id else None
    role = str(args.get("role") or (policy or {}).get("role") or "capture_decision").strip().lower()
    request = {
        "plugin": PLUGIN_NAME,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "decision_request",
        "policy_id": policy_id,
        "policy": policy,
        "role": role,
        "objective": args.get("objective") or (policy or {}).get("objective") or "",
        "observation": args.get("observation") if isinstance(args.get("observation"), dict) else {},
        "candidates": args.get("candidates") if isinstance(args.get("candidates"), list) else (policy or {}).get("candidates", []),
        "constraints": args.get("constraints") if isinstance(args.get("constraints"), list) else (policy or {}).get("constraints", []),
        "context": audio_context_payload(args),
        "settings": deep_merge((policy or {}).get("settings", {}), args.get("settings") if isinstance(args.get("settings"), dict) else {}),
        "expected_output": (policy or {}).get("output_schema", {}),
        "execution": {
            "status": "prepared",
            "note": "Screen Guardian prepares decision inputs. Arbitrary complexity belongs in the selected route, subagent, API, local command, or caller.",
        },
    }
    output_dir = ensure_cache_dir(get_cache_dir(args))
    filename = output_filename({"source_label": f"decision-request-{role}", **args}, "json")
    request_path = output_dir / filename
    write_json_file(request_path, request)
    return write_json({"ok": True, "request_path": str(request_path), "request": request})


def normalized_monitor_profile(args):
    profile_id = safe_filename_part(args.get("id") or args.get("profile_id") or "", "")
    if not profile_id:
        raise ValueError("monitor profile id is required")
    media = normalized_tags(args.get("media")) or ["screen"]
    targets = args.get("targets") if isinstance(args.get("targets"), list) else []
    triggers = args.get("triggers") if isinstance(args.get("triggers"), list) else []
    actions = args.get("actions") if isinstance(args.get("actions"), list) else []
    decision_policy_id = str(args.get("decision_policy_id") or "").strip()
    return {
        "id": profile_id,
        "enabled": bool(args.get("enabled", True)),
        "project_id": str(args.get("project_id") or "").strip(),
        "workflow_id": str(args.get("workflow_id") or "").strip(),
        "media": media,
        "schedule": args.get("schedule") if isinstance(args.get("schedule"), dict) else {"mode": "manual_tick", "interval_seconds": args.get("interval_seconds", 60)},
        "targets": targets,
        "triggers": triggers,
        "actions": actions,
        "decision_policy_id": decision_policy_id,
        "settings": args.get("settings") if isinstance(args.get("settings"), dict) else {},
        "notes": str(args.get("notes") or "").strip(),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def action_list_monitor_profiles(args):
    try:
        require_feature("monitor_profiles", args)
    except Exception as exc:
        return error(str(exc), feature="monitor_profiles")
    config = load_config()
    project_id = str(args.get("project_id") or "").strip()
    profiles = config.get("monitor_profiles", [])
    if project_id:
        profiles = [profile for profile in profiles if profile.get("project_id") == project_id]
    return write_json(
        {
            "ok": True,
            "profiles": profiles,
            "contract": {
                "target_examples": ["webpage", "window", "program", "display", "region", "audio_device", "video_file", "custom"],
                "trigger_examples": ["periodic", "visual_change", "web_change", "window_change", "error_text", "model_feature", "audio_energy", "audio_silence", "audio_clipping", "custom"],
                "action_examples": ["capture_screen", "capture_window", "record_audio", "extract_audio_track", "prepare_model_request", "prepare_decision_request"],
                "execution": "Profiles describe periodic or feature-triggered work. A scheduler, caller, or future adapter performs ticks.",
            },
        }
    )


def action_set_monitor_profile(args):
    try:
        require_feature("monitor_profiles", args)
    except Exception as exc:
        return error(str(exc), feature="monitor_profiles")
    config = load_config()
    profile_id = safe_filename_part(args.get("id") or args.get("profile_id") or "", "")
    if bool(args.get("remove", False)):
        if not profile_id:
            return error("monitor profile id is required when remove is true")
        config["monitor_profiles"] = [profile for profile in config.get("monitor_profiles", []) if profile.get("id") != profile_id]
        save_config(config)
        return write_json({"ok": True, "removed": profile_id, "profiles": config["monitor_profiles"]})
    try:
        profile = normalized_monitor_profile(args)
    except Exception as exc:
        return error(str(exc))
    profiles = [item for item in config.get("monitor_profiles", []) if item.get("id") != profile["id"]]
    profiles.append(profile)
    config["monitor_profiles"] = profiles
    save_config(config)
    return write_json({"ok": True, "profile": profile, "profiles": profiles})


def monitor_profile_by_id(config, profile_id):
    for profile in config.get("monitor_profiles", []):
        if profile.get("id") == profile_id:
            return copy.deepcopy(profile)
    return None


def action_prepare_monitor_tick(args):
    try:
        require_feature("monitor_profiles", args)
    except Exception as exc:
        return error(str(exc), feature="monitor_profiles")
    config = load_config()
    profile_id = str(args.get("profile_id") or "").strip()
    profile = monitor_profile_by_id(config, profile_id) if profile_id else None
    decision_policy = decision_policy_by_id(config, (profile or {}).get("decision_policy_id", ""))
    tick = {
        "plugin": PLUGIN_NAME,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "monitor_tick",
        "profile_id": profile_id,
        "profile": profile,
        "decision_policy": decision_policy,
        "observations": args.get("observations") if isinstance(args.get("observations"), dict) else {},
        "detected_features": args.get("detected_features") if isinstance(args.get("detected_features"), list) else [],
        "candidate_actions": args.get("candidate_actions") if isinstance(args.get("candidate_actions"), list) else (profile or {}).get("actions", []),
        "context": audio_context_payload(args),
        "execution": {
            "status": "prepared",
            "note": "This tick describes periodic or feature-triggered monitor work. Screen Guardian does not install a background scheduler by default.",
        },
    }
    output_dir = ensure_cache_dir(get_cache_dir(args))
    filename = output_filename({"source_label": "monitor-tick", **args}, "json")
    tick_path = output_dir / filename
    write_json_file(tick_path, tick)
    return write_json({"ok": True, "tick_path": str(tick_path), "tick": tick})


def action_get_display_profile(args):
    profile = build_display_profile()
    profile["ok"] = True
    profile["manifest"] = manifest_display_profile()
    return write_json(profile)


def action_set_display_name(args):
    mode = str(args.get("mode", "auto")).lower()
    if mode not in ("auto", "manual"):
        return error("mode must be auto or manual")

    display_name = str(args.get("display_name") or "").strip()
    short_description = str(args.get("short_description") or "").strip()
    if mode == "manual" and not display_name:
        return error("display_name is required when mode is manual")
    if len(display_name) > 64:
        return error("display_name must be 64 characters or fewer")
    if len(short_description) > 128:
        return error("short_description must be 128 characters or fewer")

    config = load_config()
    config["mode"] = mode
    if mode == "manual":
        config["manual_name"] = display_name
        config["manual_short_description"] = short_description
    elif bool(args.get("clear_manual", False)):
        config["manual_name"] = ""
        config["manual_short_description"] = ""
    save_config(config)

    profile = build_display_profile(config)
    profile["ok"] = True
    profile["manifest"] = manifest_display_profile()
    profile["reload_note"] = "Manual names are stored locally. Use apply_display_profile to write the active name into the Codex plugin manifest, then reload the plugin."
    return write_json(profile)


def action_apply_display_profile(args):
    profile = build_display_profile()
    active = profile["active"]
    display_name = str(args.get("display_name") or active["display_name"]).strip()
    short_description = str(args.get("short_description") or active["short_description"]).strip()
    if not display_name:
        return error("display_name cannot be empty")
    if len(display_name) > 64:
        return error("display_name must be 64 characters or fewer")
    if len(short_description) > 128:
        return error("short_description must be 128 characters or fewer")

    manifest = read_json_file(PLUGIN_MANIFEST_PATH, {})
    interface = manifest.setdefault("interface", {})
    interface["displayName"] = display_name
    interface["shortDescription"] = short_description
    write_json_file(PLUGIN_MANIFEST_PATH, manifest)

    return write_json(
        {
            "ok": True,
            "manifest": manifest_display_profile(),
            "reload_note": "Reload or reinstall the local plugin before expecting Codex to show the new manifest name.",
        }
    )


def key_capability_summary(flags):
    keys = [
        "screen_capture",
        "window_capture",
        "bounded_watch",
        "workflow_metadata",
        "image_analysis",
        "image_preprocess",
        "model_request_envelopes",
        "decision_policies",
        "monitor_profiles",
        "capture_chains",
        "webpage_capture",
        "audio_capture",
        "video_audio_extract",
        "external_api_handoff",
        "codex_subagent_handoff",
    ]
    return {key: bool(flags.get(key, False)) for key in keys}


def action_guardian_check(args):
    detail = str(args.get("detail") or "short").strip().lower()
    if detail not in ("short", "full"):
        return error("detail must be short or full")
    config = load_config()
    flags = feature_flags({})
    primary, mirrors = output_routes({})
    mss_status, libs = mss_adapter_status()
    window_status, _window_libs = window_adapter_status()
    audio_status, _audio_libs = audio_adapter_status({"probe": False})
    ffmpeg = ffmpeg_status()
    webpage_status, _web_libs = webpage_adapter_status({})
    adapters = [mss_status, window_status, audio_status, ffmpeg, webpage_status]
    best_adapter = next((item for item in adapters if item.get("role") == "screen_capture" and item.get("available")), None)
    if not best_adapter:
        best_adapter = next((item for item in adapters if item.get("available")), None)
    capture_ready = bool(flags.get("screen_capture") and mss_status.get("available"))
    recommended_next = "guardian_perceive" if capture_ready else "check_dependencies"
    payload = {
        "ok": True,
        "plugin": PLUGIN_NAME,
        "capture_ready": capture_ready,
        "best_adapter": best_adapter,
        "python": sys.executable,
        "active_cache_dir": str(primary),
        "extra_output_dirs": serialize_paths(mirrors),
        "key_capabilities": key_capability_summary(flags),
        "recommended_next": recommended_next,
        "ai_first_tools": ["guardian_check", "guardian_capture_targets", "guardian_perceive", "guardian_survey_windows", "guardian_prepare_workflow"],
        "privacy": "Local status check only; no screenshot, audio recording, upload, model call, or configuration change.",
    }
    if detail == "full":
        payload.update(
            {
                "config_path": str(CONFIG_PATH),
                "default_cache_dir": str(DEFAULT_CACHE_DIR),
                "runtime_limits": config.get("runtime_limits", {}),
                "feature_flags": config.get("feature_flags", {}),
                "feature_catalog": FEATURE_CATALOG,
                "adapters": adapters,
                "versions": {
                    "mss": getattr(libs["mss"], "__version__", "unknown") if libs else "",
                    "pillow": getattr(libs["Image"], "__version__", "unknown") if libs else "",
                },
            }
        )
    return write_json(payload)


def display_capture_targets(args):
    status, libs = mss_adapter_status()
    if not status.get("available"):
        return {
            "available": False,
            "adapter": status,
            "targets": [],
            "reason": status.get("import_error") or "screen_capture_adapter_unavailable",
        }
    with libs["mss"].MSS() as sct:
        monitors = [monitor_to_dict(i, monitor) for i, monitor in enumerate(sct.monitors)]
    targets = []
    for monitor in monitors:
        display_index = int(monitor.get("display_index") or 0)
        label = "Virtual desktop" if display_index == 0 else f"Display {display_index}"
        targets.append(
            {
                "id": f"display:{display_index}",
                "type": "display",
                "label": label,
                "tool": "capture_screen",
                "args": {"display_index": display_index},
                "display": monitor,
                "quiet_capture": False,
                "occlusion_resistant": False,
                "note": "Display capture reads visible desktop pixels and is affected by overlap, occlusion, and foreground state.",
            }
        )
    return {"available": True, "adapter": status.get("id"), "targets": targets}


def normalized_page_targets(args):
    raw_pages = []
    if args.get("url"):
        raw_pages.append({"url": args.get("url")})
    for url in args.get("urls") or []:
        raw_pages.append({"url": url})
    for page in args.get("pages") or []:
        if isinstance(page, dict):
            raw_pages.append(dict(page))
    pages = []
    seen = set()
    for index, page in enumerate(raw_pages, start=1):
        url = normalized_webpage_url({"url": page.get("url")})
        key = (url, str(page.get("selector") or ""), str(page.get("frame_selector") or ""), str(page.get("mode") or "full_page"))
        if key in seen:
            continue
        seen.add(key)
        mode = str(page.get("mode") or "full_page").strip().lower()
        if mode not in ("full_page", "viewport", "element", "scroll_container"):
            raise ValueError("page mode must be full_page, viewport, element, or scroll_container")
        capture_args = {"url": url, "mode": mode}
        for key_name in ("selector", "frame_selector"):
            if page.get(key_name):
                capture_args[key_name] = str(page.get(key_name))
        label = str(page.get("label") or urllib.parse.urlparse(url).netloc or f"page {index}").strip()
        pages.append(
            {
                "id": f"page:{index}",
                "type": "webpage",
                "label": label,
                "tool": "capture_webpage",
                "args": capture_args,
                "quiet_capture": True,
                "occlusion_resistant": True,
                "note": "Webpage capture uses an explicit URL and a browser-rendered route, not visible desktop pixels.",
            }
        )
    return pages


def window_capture_target_record(window, include_visibility_probe, background_mode):
    record = window_survey_status(window, include_visibility_probe)
    hwnd = int(window.get("hwnd"))
    strict_args = {
        "hwnd": hwnd,
        "background_mode": background_mode,
        "quiet_preferred": True,
        "wait_for_nonblank": True,
        "render_guard": "warn",
        "guard_checks": ["unrendered", "window_client_low_information", "background_capture_unavailable"],
    }
    fallback_args = {
        "hwnd": hwnd,
        "background_mode": "visible_fallback",
        "quiet_preferred": False,
        "render_guard": "warn",
        "guard_checks": ["unrendered", "occlusion_risk", "bbox_identity_mismatch"],
    }
    record["id"] = f"window:{hwnd}"
    record["type"] = "window"
    record["label"] = " - ".join(part for part in (record.get("process_name"), record.get("title")) if part)
    record["tool"] = "capture_window"
    record["args"] = strict_args
    record["capture_target"] = {
        "primary": {"tool": "capture_window", "args": strict_args},
        "visible_fallback": {"tool": "capture_window", "args": fallback_args},
        "selection_key": {"hwnd": hwnd, "exact_title": window.get("title"), "process_name": window.get("process_name")},
    }
    record["background_capture"] = {
        "preferred": True,
        "mode": background_mode,
        "foreground_activation_required": False,
        "visible_screen_fallback_allowed": background_mode != "strict",
        "occlusion_resistant_when_direct_hwnd_succeeds": True,
        "capability_confirmed": "unknown_until_capture",
        "note": "The target index does not capture pixels. Strict background capability is confirmed by the capture result metadata.",
    }
    return record


def action_guardian_capture_targets(args):
    try:
        return write_json(guardian_capture_targets_payload(args))
    except Exception as exc:
        return error(str(exc))


def guardian_capture_targets_payload(args):
    flags = feature_flags(args)
    include_displays = bool(args.get("include_displays", True))
    include_windows = bool(args.get("include_windows", True))
    include_pages = bool(args.get("include_pages", True))
    include_visibility_probe = bool(args.get("include_visibility_probe", True))
    background_mode = normalize_background_mode({"background_mode": args.get("background_mode") or "strict"})
    limit = int(args.get("limit", 50))
    if limit < 1:
        raise ValueError("limit must be at least 1")
    limit = min(limit, 200)

    display_payload = {"available": False, "targets": [], "reason": "not_requested"}
    if include_displays:
        if flags.get("screen_capture"):
            display_payload = display_capture_targets(args)
        else:
            display_payload = {"available": False, "targets": [], "reason": "screen_capture_feature_disabled"}

    window_targets = []
    windows_total = 0
    if include_windows:
        if flags.get("window_capture"):
            windows = filtered_survey_windows(args)
            windows_total = len(windows)
            window_targets = [window_capture_target_record(window, include_visibility_probe, background_mode) for window in windows[:limit]]
        else:
            window_targets = []

    page_targets = []
    page_error = ""
    if include_pages:
        try:
            page_targets = normalized_page_targets(args)
        except Exception as exc:
            page_error = str(exc)

    targets = []
    targets.extend(display_payload.get("targets") or [])
    targets.extend(window_targets)
    targets.extend(page_targets)
    return {
        "ok": True,
        "target_index_ready": True,
        "capture_performed": False,
        "targets_total": len(targets),
        "targets": targets,
        "displays": display_payload,
        "windows": {
            "available": bool(flags.get("window_capture")),
            "reported": len(window_targets),
            "total_matching": windows_total,
            "targets": window_targets,
        },
        "pages": {
            "available": bool(flags.get("webpage_capture")),
            "reported": len(page_targets),
            "targets": page_targets,
            "error": page_error,
            "current_browser_tab_enumeration": {
                "available": False,
                "reason": "The local helper does not inspect the user's browser session or tab list. Pass explicit URLs or use a browser/Chrome connector before calling capture_webpage.",
            },
        },
        "recommended_capture_policy": {
            "application_window": "Use capture_target.primary first. With the default background_mode='strict', it does not raise the window and does not save visible-screen bbox fallback pixels.",
            "browser_page": "Use capture_webpage with an explicit URL when page content matters more than the browser chrome.",
            "desktop": "Use display targets only when visible desktop pixels are desired.",
        },
        "privacy": "Target indexing only. No screenshot, audio recording, upload, model call, browser navigation, or background monitor was performed.",
    }


AUTHORIZATION_LEVELS = {
    "L0_visual_only": {
        "rank": 0,
        "label": "Default visual-only",
        "allowed_actions": ["target_index", "display_list", "window_list", "screenshot", "window_capture", "hold_file"],
        "forbidden_actions": ["dom_measure", "container_scroll", "form_submit", "export_download", "cookie_read", "localStorage_read", "sessionStorage_read", "database_read", "registry_read", "credential_read"],
    },
    "L1_current_page_readonly": {
        "rank": 1,
        "label": "Current page readonly",
        "allowed_actions": ["target_index", "dom_measure", "container_scroll", "screenshot", "window_capture", "browser_session_screenshot", "nested_scroll_longshot", "hold_file"],
        "forbidden_actions": ["form_submit", "export_download", "cookie_read", "localStorage_read", "sessionStorage_read", "database_read", "registry_read", "credential_read"],
    },
    "L2_page_interaction": {
        "rank": 2,
        "label": "Page interaction",
        "allowed_actions": ["target_index", "dom_measure", "container_scroll", "screenshot", "click_filter", "open_dropdown", "pagination", "export_download_after_confirmation", "file_convert", "hold_file"],
        "forbidden_actions": ["destructive_submit", "permission_change", "purchase", "cookie_read", "localStorage_read", "sessionStorage_read", "database_read", "registry_read", "credential_read"],
    },
    "L3_sensitive_action_confirmed": {
        "rank": 3,
        "label": "Sensitive action with confirmation",
        "allowed_actions": ["target_index", "dom_measure", "container_scroll", "screenshot", "export_download_after_confirmation", "api_readonly_after_confirmation", "file_convert", "hold_file"],
        "forbidden_actions": ["credential_read", "cookie_read", "localStorage_read", "sessionStorage_read", "raw_database_mutation", "raw_registry_mutation"],
    },
    "L4_sensitive_storage_or_data_access": {
        "rank": 4,
        "label": "Sensitive storage or data access",
        "allowed_actions": ["target_index", "dom_measure", "container_scroll", "screenshot", "export_download_after_confirmation", "api_readonly_after_confirmation", "database_readonly_after_confirmation", "registry_readonly_after_confirmation", "file_convert", "hold_file"],
        "forbidden_actions": ["cookie_read", "localStorage_read", "sessionStorage_read", "password_store_read", "credential_read", "credential_printing", "secret_exfiltration", "database_mutation_without_explicit_scope", "registry_mutation_without_explicit_scope"],
    },
}


def normalize_authorization_level(args):
    level = str(args.get("authorization_level") or "L0_visual_only").strip()
    aliases = {
        "l0": "L0_visual_only",
        "visual": "L0_visual_only",
        "visual_only": "L0_visual_only",
        "l1": "L1_current_page_readonly",
        "page_readonly": "L1_current_page_readonly",
        "readonly_page": "L1_current_page_readonly",
        "l2": "L2_page_interaction",
        "page_interaction": "L2_page_interaction",
        "l3": "L3_sensitive_action_confirmed",
        "confirmed_sensitive": "L3_sensitive_action_confirmed",
        "l4": "L4_sensitive_storage_or_data_access",
        "full": "L4_sensitive_storage_or_data_access",
        "full_rights": "L4_sensitive_storage_or_data_access",
    }
    level = aliases.get(level.lower(), level)
    if level not in AUTHORIZATION_LEVELS:
        raise ValueError("authorization_level must be L0_visual_only, L1_current_page_readonly, L2_page_interaction, L3_sensitive_action_confirmed, or L4_sensitive_storage_or_data_access")
    return level


def sniff_target_hints(args):
    target = args.get("target") if isinstance(args.get("target"), dict) else {}
    hints = []
    if target:
        hints.append(
            {
                "kind": str(target.get("kind") or "unknown"),
                "title": str(target.get("title") or ""),
                "url": str(target.get("url") or ""),
                "selector": str(target.get("selector") or ""),
                "frame_selector": str(target.get("frame_selector") or ""),
                "path": str(target.get("path") or ""),
            }
        )
    if args.get("url"):
        hints.append({"kind": "webpage", "url": str(args.get("url")), "title": "", "selector": "", "frame_selector": "", "path": ""})
    for url in args.get("urls") or []:
        hints.append({"kind": "webpage", "url": str(url), "title": "", "selector": "", "frame_selector": "", "path": ""})
    for path in args.get("file_paths") or []:
        hints.append({"kind": "file", "path": str(path), "title": "", "url": "", "selector": "", "frame_selector": ""})
    return hints


def is_potential_network_path(path_text):
    raw = str(path_text or "").strip()
    lowered = raw.lower()
    return raw.startswith("\\\\") or lowered.startswith("//") or lowered.startswith("file://")


def file_route_record(path_text, allow_network_metadata_probe=False):
    raw_path = str(path_text or "")
    path = Path(raw_path).expanduser()
    suffix = path.suffix.lower()
    markdown_like = suffix in {".md", ".markdown", ".txt", ".rst", ".csv", ".tsv", ".json", ".yaml", ".yml", ".xml", ".html", ".htm"}
    document_like = suffix in {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".odt", ".rtf", ".epub"}
    image_like = suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
    media_like = suffix in {".mp3", ".wav", ".m4a", ".mp4", ".mov", ".mkv", ".webm"}
    network_path = is_potential_network_path(raw_path)
    exists = None
    size_bytes = None
    metadata_checked = False
    metadata_probe_skipped = ""
    if network_path and not allow_network_metadata_probe:
        metadata_probe_skipped = "potential_network_path"
    else:
        metadata_checked = True
        exists = path.exists()
        size_bytes = path.stat().st_size if exists and path.is_file() else None
    record = {
        "path": str(path),
        "exists": bool(exists) if exists is not None else None,
        "suffix": suffix,
        "size_bytes": size_bytes,
        "metadata_checked": metadata_checked,
        "metadata_probe_skipped": metadata_probe_skipped,
        "potential_network_path": bool(network_path),
        "content_read": False,
        "recommended_routes": [],
    }
    if markdown_like:
        record["recommended_routes"].append({"route": "direct_text_or_structured_parse", "priority": 20, "requires_authorization": "file_path_access", "note": "Prefer structured/text parsing for already textual files."})
    if document_like or image_like:
        record["recommended_routes"].append({"route": "document_to_markdown", "adapter": "markitdown_style_optional", "priority": 30, "requires_authorization": "file_convert", "note": "A MarkItDown-style adapter can convert authorized local documents/images into markdown-like text, but the core sniffer only reports the route and does not read contents."})
    if media_like:
        record["recommended_routes"].append({"route": "media_audio_or_frame_analysis", "priority": 50, "requires_authorization": "media_analysis", "note": "Media routes should stay optional and bounded."})
    if not record["recommended_routes"]:
        record["recommended_routes"].append({"route": "unknown_file_hold_file", "priority": 90, "requires_authorization": "file_review", "note": "Unknown suffix. Keep as hold-file until a caller chooses a parser."})
    return record


def sniff_route_candidates(args, level, permissions):
    rank = AUTHORIZATION_LEVELS[level]["rank"]
    target = args.get("target") if isinstance(args.get("target"), dict) else {}
    target_kind = str(target.get("kind") or "unknown").strip().lower()
    has_url = bool(args.get("url") or args.get("urls") or target.get("url"))
    has_selector = bool(target.get("selector"))
    wants_export = "export_download" in permissions
    wants_api = "api_readonly" in permissions or target_kind == "api"
    wants_database = "database_readonly" in permissions or target_kind == "database"
    wants_registry = "registry_readonly" in permissions or target_kind == "registry"
    wants_sensitive_routes = bool(args.get("include_sensitive_routes") or rank >= 3 or wants_export or wants_api or wants_database or wants_registry)
    candidates = [
        {
            "id": "visual_target_index",
            "route": "guardian_capture_targets",
            "priority": 10,
            "authorization_required": "L0_visual_only",
            "status": "available",
            "side_effects": ["window_enumeration_optional"],
            "forbidden": ["cookie_read", "localStorage_read", "registry_read", "database_read"],
            "note": "Default first sniff. It gives the AI capture targets before any screenshot.",
        },
        {
            "id": "strict_window_background",
            "route": "capture_window",
            "priority": 20,
            "authorization_required": "L0_visual_only",
            "status": "available",
            "args": {"background_mode": "strict", "guard_checks": ["unrendered", "window_client_low_information", "background_capture_unavailable"]},
            "side_effects": ["local_file_write_when_executed"],
            "note": "Use for occlusion-resistant HWND graphics. It is not a DOM/data route.",
        },
    ]
    if rank >= 1 or "dom_measure" in permissions or target_kind in ("browser_tab", "webpage"):
        candidates.append(
            {
                "id": "browser_session_readonly",
                "route": "browser_connector_current_tab",
                "priority": 5 if target_kind == "browser_tab" else 25,
                "authorization_required": "L1_current_page_readonly",
                "status": "available_with_external_connector",
                "side_effects": ["bounded_dom_measure", "container_scroll_if_executed", "local_screenshot_if_executed"],
                "forbidden": ["cookie_read", "localStorage_read", "sessionStorage_read", "form_submit"],
                "note": "Best route for already-authenticated pages. Use current tab state without inspecting browser secrets.",
            }
        )
    if has_url:
        candidates.append(
            {
                "id": "headless_webpage_capture",
                "route": "capture_webpage",
                "priority": 35,
                "authorization_required": "L1_current_page_readonly",
                "status": "feature_flag_dependent",
                "side_effects": ["browser_navigation_when_executed", "local_file_write_when_executed"],
                "note": "Use for explicit URLs when login/session state is not required or a separate browser context is acceptable.",
            }
        )
    if has_selector:
        candidates.append(
            {
                "id": "nested_scroll_longshot",
                "route": "browser_session_nested_scroll" if target_kind == "browser_tab" else "capture_webpage_scroll_container",
                "priority": 8 if target_kind == "browser_tab" else 30,
                "authorization_required": "L1_current_page_readonly",
                "status": "planned",
                "side_effects": ["container_scroll_if_executed", "local_file_write_when_executed"],
                "note": "Use for inner tables, panels, and iframes. Metadata must record selector, segments, and restored scroll state.",
            }
        )
    if rank >= 2 or "file_convert" in permissions:
        candidates.append(
            {
                "id": "document_to_markdown",
                "route": "markitdown_style_optional_adapter",
                "priority": 18,
                "authorization_required": "L2_page_interaction_or_file_convert",
                "status": "optional_adapter_not_executed",
                "side_effects": ["local_file_read_when_executed", "local_markdown_output_when_executed"],
                "forbidden": ["credential_extraction", "hidden_upload"],
                "note": "For authorized documents, a MarkItDown-style adapter can be faster than screenshots. The sniffer only recommends the route.",
            }
        )
    if target_kind == "folder":
        candidates.append(
            {
                "id": "folder_manifest",
                "route": "folder_metadata_manifest",
                "priority": 55,
                "authorization_required": "explicit_folder_scope",
                "status": "blocked_until_explicit_folder_scope",
                "side_effects": ["folder_enumeration_when_executed"],
                "note": "Folder targets need an explicit path scope and are not enumerated by the sniffer.",
            }
        )
    if wants_sensitive_routes or rank >= 3:
        candidates.extend(
            [
                {
                    "id": "page_export",
                    "route": "authorized_export_download",
                    "priority": 12,
                    "authorization_required": "L3_sensitive_action_confirmed",
                    "status": "requires_action_confirmation" if rank >= 3 else "blocked_by_authorization_level",
                    "side_effects": ["download", "possible_sensitive_data_file"],
                    "note": "Efficient when the page provides an export button, but requires action-time confirmation.",
                },
                {
                    "id": "api_readonly",
                    "route": "api_readonly",
                    "priority": 14,
                    "authorization_required": "L3_sensitive_action_confirmed",
                    "status": "requires_explicit_endpoint_and_scope" if rank >= 3 else "blocked_by_authorization_level",
                    "side_effects": ["network_request_when_executed"],
                    "note": "Only use with explicit API endpoint, scope, and user confirmation.",
                },
            ]
        )
    if wants_sensitive_routes or rank >= 4:
        candidates.extend(
            [
                {
                    "id": "database_readonly",
                    "route": "database_readonly",
                    "priority": 16,
                    "authorization_required": "L4_sensitive_storage_or_data_access",
                    "status": "blocked_until_explicit_connection_scope" if rank >= 4 else "blocked_by_authorization_level",
                    "side_effects": ["database_query_when_executed"],
                    "note": "Must be explicit readonly scope. Never infer database access from page visibility alone.",
                },
                {
                    "id": "registry_readonly",
                    "route": "registry_readonly",
                    "priority": 60,
                    "authorization_required": "L4_sensitive_storage_or_data_access",
                    "status": "blocked_until_explicit_key_scope" if rank >= 4 else "blocked_by_authorization_level",
                    "side_effects": ["registry_read_when_executed"],
                    "note": "Registry reads are not a normal webpage/file perception route.",
                },
            ]
        )
    return sorted(candidates, key=lambda item: int(item.get("priority", 100)))


def action_guardian_sniff_context(args):
    try:
        level = normalize_authorization_level(args)
        profile = copy.deepcopy(AUTHORIZATION_LEVELS[level])
        permissions = {str(item).strip().lower() for item in normalized_tags(args.get("declared_permissions"))}
        file_routes = []
        allow_network_metadata_probe = bool(args.get("allow_network_file_metadata_probe", False))
        if bool(args.get("include_document_routes", True)):
            for path_text in args.get("file_paths") or []:
                file_routes.append(file_route_record(path_text, allow_network_metadata_probe))
            target = args.get("target") if isinstance(args.get("target"), dict) else {}
            if target.get("kind") == "file" and target.get("path"):
                file_routes.append(file_route_record(target.get("path"), allow_network_metadata_probe))

        capture_index = None
        if bool(args.get("include_capture_targets", False)):
            target = args.get("target") if isinstance(args.get("target"), dict) else {}
            capture_args = {**args, "include_pages": bool(args.get("url") or args.get("urls") or target.get("url")), "include_displays": True, "include_windows": True}
            if target.get("url") and not capture_args.get("url"):
                capture_args["url"] = target.get("url")
            capture_index = guardian_capture_targets_payload(capture_args)

        candidates = sniff_route_candidates(args, level, permissions)
        return write_json(
            {
                "ok": True,
                "sniff_performed": True,
                "capture_performed": False,
                "secret_storage_read": False,
                "database_or_registry_touched": False,
                "network_request_performed": False,
                "objective": str(args.get("objective") or ""),
                "authorization": {
                    "level": level,
                    "label": profile["label"],
                    "declared_permissions": sorted(permissions),
                    "recommendable_actions": profile["allowed_actions"],
                    "allowed_actions": profile["allowed_actions"],
                    "performed_actions": [],
                    "forbidden_actions": profile["forbidden_actions"],
                    "note": "Authorization is scoped by action and data type. allowed_actions are recommendable actions for later tools; guardian_sniff_context itself performs no route actions.",
                },
                "target_hints": sniff_target_hints(args),
                "route_candidates": candidates,
                "file_routes": file_routes,
                "capture_targets": capture_index,
                "recommended_order": [item["id"] for item in candidates[:5]],
                "sensitive_boundaries": {
                    "never_by_default": ["cookie_read", "localStorage_read", "sessionStorage_read", "password_store_read", "credential_printing", "secret_exfiltration"],
                    "requires_explicit_scope": ["api_readonly", "database_readonly", "registry_readonly", "export_download"],
                    "markitdown_style_route": "Allowed only for user-authorized local files or downloads; it is a converter route, not a credential or browser-session route.",
                    "file_metadata_probe": "Local path metadata may be checked for supplied file_paths. Potential network paths are skipped unless allow_network_file_metadata_probe=true.",
                },
                "metadata_contract": {
                    "authorization_level": level,
                    "recommendable_actions": profile["allowed_actions"],
                    "performed_actions": [],
                    "forbidden_actions": profile["forbidden_actions"],
                    "restored_state_required": True,
                    "route_must_not_be_mislabelled": ["browser_session_capture_as_headless_url_capture", "visible_bbox_as_strict_background_capture", "document_conversion_as_cookie_access"],
                },
                "privacy": "Route sniffing only. No screenshot, page navigation, browser storage read, database query, registry read, upload, model call, or background monitor was performed.",
            }
        )
    except Exception as exc:
        return error(str(exc))


def guardian_base_context(args, default_source_label):
    forwarded = {}
    for key in (
        "output_dir",
        "project_id",
        "workflow_id",
        "tags",
        "note",
        "delay_seconds",
        "settle_delay_ms",
        "wait_for_nonblank",
        "quiet_preferred",
        "background_mode",
        "window_background_mode",
        "render_guard",
        "render_guard_confirmed",
        "allow_unverified_bbox_fallback",
        "guard_checks",
        "guard_tiny_min_pixels",
        "render_retry_count",
        "render_retry_interval_ms",
        "stable_wait_seconds",
        "stable_interval_ms",
        "stable_threshold",
        "stable_required_samples",
        "buffer_wait_seconds",
        "buffer_interval_ms",
        "buffer_stable_threshold",
        "runtime_limits",
        "feature_flags",
    ):
        if key in args:
            forwarded[key] = args[key]
    forwarded["source_label"] = str(args.get("source_label") or default_source_label)
    return forwarded


def apply_guardian_budget(forwarded, context_budget):
    budget = str(context_budget or "normal").strip().lower()
    if budget not in ("low", "normal", "high", "hold_file"):
        raise ValueError("context_budget must be low, normal, high, or hold_file")
    if budget == "low":
        forwarded.setdefault("max_width", 960)
    elif budget in ("normal", "hold_file"):
        forwarded.setdefault("max_width", 1440)
    if budget == "hold_file":
        forwarded["context_policy"] = "hold_file"
        forwarded["marked_file_only"] = True
    return budget


def apply_guardian_target(forwarded, target):
    target = target if isinstance(target, dict) else {}
    target_type = str(target.get("type") or "screen").strip().lower()
    if target_type not in ("screen", "region", "window"):
        raise ValueError("target.type must be screen, region, or window")
    display_index = target.get("display_index", target.get("display"))
    if display_index is not None:
        forwarded["display_index"] = int(display_index)
    box = target.get("box") if isinstance(target.get("box"), dict) else None
    if box:
        for key in ("left", "top", "width", "height"):
            if key not in box:
                raise ValueError(f"target.box.{key} is required for a region target")
            forwarded[key] = int(box[key])
        forwarded["relative_to_display"] = bool(box.get("relative_to_display", True))
        target_type = "region" if target_type == "screen" else target_type
    for key in ("hwnd", "title_contains", "exact_title", "process_name", "allow_first_match"):
        if key in target:
            forwarded[key] = target[key]
    if any(forwarded.get(key) for key in ("hwnd", "title_contains", "exact_title", "process_name")) and target_type == "screen":
        target_type = "window"
    return target_type


def error_wait_options(args):
    limits = runtime_limits(args)
    timeout = float(args.get("error_wait_seconds", 10))
    interval_ms = float(args.get("error_poll_interval_ms", 500))
    if timeout < 0:
        raise ValueError("error_wait_seconds must be zero or greater")
    if interval_ms <= 0:
        raise ValueError("error_poll_interval_ms must be greater than zero")
    check_min_max(timeout, 0, limits.get("capture_error_wait_seconds_max"), "error_wait_seconds")
    check_min_max(interval_ms, limits.get("capture_error_poll_interval_ms_min"), limits.get("capture_error_poll_interval_ms_max"), "error_poll_interval_ms")
    return timeout, interval_ms / 1000.0


def error_signal_filters(args):
    filters = {}
    if args.get("error_title_contains"):
        filters["title_contains"] = str(args.get("error_title_contains"))
    if args.get("error_title_contains_any"):
        filters["title_contains_any"] = normalized_tags(args.get("error_title_contains_any"))
    if args.get("error_process_name"):
        filters["process_name"] = str(args.get("error_process_name"))
    if args.get("error_process_names"):
        filters["process_names"] = normalized_tags(args.get("error_process_names"))
    if not filters and args.get("error_text"):
        filters["title_contains"] = str(args.get("error_text"))
    return filters


def wait_for_error_signal(args, forwarded):
    filters = error_signal_filters(args)
    if not filters:
        raise ValueError("wait_error requires error_title_contains, error_title_contains_any, error_process_name, error_process_names, or error_text")
    timeout, interval = error_wait_options(args)
    deadline = time.time() + timeout
    samples = 0
    matched = []
    while True:
        samples += 1
        matched = enum_windows(filters)
        if matched or time.time() >= deadline:
            break
        time.sleep(min(interval, max(0.0, deadline - time.time())))
    strategy = forwarded.setdefault("_capture_strategy", {})
    strategy["error_wait"] = {
        "enabled": True,
        "filters": filters,
        "status": "detected" if matched else "timeout",
        "samples": samples,
        "timeout_seconds": timeout,
        "interval_seconds": round(interval, 3),
        "matched_windows": summarize_windows(matched, 5),
        "note": "wait_error currently detects explicit window-title/process signals; OCR, DOM, and log parsing belong to future semantic routes or caller-provided signals.",
    }
    if not matched:
        raise RuntimeError("No matching error signal was detected before timeout")
    capture_target = str(args.get("error_capture_target") or "original").strip().lower()
    if capture_target not in ("original", "matching_window"):
        raise ValueError("error_capture_target must be original or matching_window")
    if capture_target == "matching_window":
        forwarded["hwnd"] = int(matched[0].get("hwnd"))
        forwarded.pop("title_contains", None)
        forwarded.pop("exact_title", None)
        forwarded.pop("process_name", None)
        return "window"
    return None


def apply_guardian_capture_modes(forwarded, args):
    modes = normalize_capture_modes(args)
    forwarded["capture_modes"] = list(modes)
    strategy = forwarded.setdefault("_capture_strategy", {})
    strategy["modes"] = list(modes)
    strategy["default_fast"] = modes == ["fast"]
    strategy["note"] = "Default mode is fast direct capture. Optional modes add explicit delay, render-ready retry, buffer-stability wait, or error-signal wait."
    if "delay" in modes:
        forwarded.setdefault("delay_seconds", float(args.get("delay_seconds") or 1.0))
    if "wait_render" in modes:
        forwarded["wait_for_nonblank"] = True
        forwarded.setdefault("render_guard", "wait")
        forwarded.setdefault("render_retry_count", 4)
        forwarded.setdefault("render_retry_interval_ms", 500)
    else:
        forwarded.setdefault("wait_for_nonblank", False)
        forwarded.setdefault("render_guard", "save")
    return modes


def action_guardian_perceive(args):
    try:
        task = str(args.get("task") or "quick_look").strip().lower()
        allowed_tasks = ("quick_look", "read_text", "debug_ui", "capture_window", "watch_change", "hold_file")
        if task not in allowed_tasks:
            return error("task must be quick_look, read_text, debug_ui, capture_window, watch_change, or hold_file")
        forwarded = guardian_base_context(args, f"guardian-{task}")
        modes = apply_guardian_capture_modes(forwarded, args)
        budget = apply_guardian_budget(forwarded, args.get("context_budget") or "normal")
        if task == "hold_file":
            forwarded["context_policy"] = "hold_file"
            forwarded["marked_file_only"] = True
        if task == "read_text":
            forwarded["preprocess"] = "text"
            forwarded["analyze"] = True
        elif task == "debug_ui":
            forwarded["preprocess"] = "ui"
            forwarded["analyze"] = True
        for key in ("duration_seconds", "interval_seconds", "change_threshold", "max_captures"):
            if key in args:
                forwarded[key] = args[key]
        target_type = apply_guardian_target(forwarded, args.get("target"))
        if task == "capture_window":
            target_type = "window"
        if "wait_error" in modes:
            detected_target_type = wait_for_error_signal(args, forwarded)
            if detected_target_type:
                target_type = detected_target_type
        if task == "watch_change":
            return action_watch_screen(forwarded)
        if target_type == "window":
            return action_capture_window(forwarded)
        if target_type == "region":
            if not all(key in forwarded for key in ("left", "top", "width", "height")):
                return error("target.box is required for a region target")
            return action_capture_region(forwarded)
        return action_capture_screen(forwarded)
    except Exception as exc:
        return error(str(exc))


def normalize_window_survey_capture_mode(args):
    mode = str(args.get("capture_mode") or "status_only").strip().lower()
    aliases = {
        "none": "status_only",
        "off": "status_only",
        "list": "status_only",
        "status": "status_only",
        "capture": "hold_file",
        "captures": "hold_file",
        "save": "hold_file",
        "paths": "return_paths",
        "return_path": "return_paths",
    }
    mode = aliases.get(mode, mode)
    if mode not in ("status_only", "hold_file", "return_paths"):
        raise ValueError("capture_mode must be status_only, hold_file, or return_paths")
    return mode


def filtered_survey_windows(args):
    enum_args = {}
    for key in ("title_contains", "title_contains_any", "process_name", "process_names"):
        if key in args:
            enum_args[key] = args[key]
    windows = enum_windows(enum_args)
    exact_title = str(args.get("exact_title") or "").strip().lower()
    if exact_title:
        windows = [window for window in windows if str(window.get("title") or "").lower() == exact_title]
    hwnds = []
    if args.get("hwnd"):
        hwnds.append(int(args.get("hwnd")))
    for item in args.get("hwnds") or []:
        hwnds.append(int(item))
    if hwnds:
        wanted = set(hwnds)
        by_hwnd = {int(window.get("hwnd")): window for window in windows}
        for hwnd in hwnds:
            if hwnd not in by_hwnd:
                info = window_info_for_hwnd(hwnd)
                if info and info.get("is_visible") and info.get("title"):
                    by_hwnd[hwnd] = info
        windows = [by_hwnd[hwnd] for hwnd in hwnds if hwnd in by_hwnd]
    return windows


def compact_visibility_probe(probe):
    if not isinstance(probe, dict) or not probe.get("available"):
        return probe
    samples = []
    for sample in probe.get("samples") or []:
        top_window = sample.get("top_window") if isinstance(sample.get("top_window"), dict) else {}
        samples.append(
            {
                "point": sample.get("point"),
                "target_match": bool(sample.get("target_match", False)),
                "top_hwnd": sample.get("top_hwnd"),
                "top_title": top_window.get("title"),
                "top_process_name": top_window.get("process_name"),
                "top_pid": top_window.get("pid"),
            }
        )
    return {
        "available": True,
        "identity_verified": bool(probe.get("identity_verified", False)),
        "target_match_ratio": probe.get("target_match_ratio"),
        "target_match_count": probe.get("target_match_count"),
        "sample_count": probe.get("sample_count"),
        "samples": samples,
        "note": probe.get("note"),
    }


def window_survey_status(window, include_visibility_probe):
    rect = window.get("rect") if isinstance(window.get("rect"), dict) else {}
    virtual = virtual_screen_rect()
    visible_ratio = rect_intersection_ratio(rect, virtual)
    states = []
    if bool(window.get("is_minimized", False)):
        states.append("minimized")
    if visible_ratio <= 0:
        states.append("offscreen")
    elif visible_ratio < 0.95:
        states.append("partly_offscreen")
    probe = {}
    if include_visibility_probe and not bool(window.get("is_minimized", False)) and visible_ratio > 0:
        probe = compact_visibility_probe(bbox_identity_probe(window))
        if probe.get("available"):
            if probe.get("identity_verified"):
                states.append("visible_at_sample_points")
            else:
                states.append("possibly_occluded")
    if not states:
        states.append("ready")
    return {
        "hwnd": window.get("hwnd"),
        "title": window.get("title"),
        "process_name": window.get("process_name"),
        "pid": window.get("pid"),
        "rect": rect,
        "is_visible": bool(window.get("is_visible", False)),
        "is_minimized": bool(window.get("is_minimized", False)),
        "visible_ratio": round(float(visible_ratio), 3),
        "states": states,
        "visibility_probe": probe,
    }


def apply_window_survey_budget(forwarded, context_budget, capture_mode):
    budget = str(context_budget or ("hold_file" if capture_mode == "hold_file" else "low")).strip().lower()
    if budget not in ("low", "normal", "high", "hold_file"):
        raise ValueError("context_budget must be low, normal, high, or hold_file")
    if budget == "low":
        forwarded.setdefault("max_width", 640)
    elif budget in ("normal", "hold_file"):
        forwarded.setdefault("max_width", 960)
    if budget == "hold_file" or capture_mode == "hold_file":
        forwarded["context_policy"] = "hold_file"
        forwarded["marked_file_only"] = True
    return budget


def window_survey_capture_args(args, window, index, capture_mode):
    forwarded = guardian_base_context(args, "window-survey")
    for key in (
        "format",
        "scale",
        "max_width",
        "max_height",
        "quality",
        "preprocess",
        "analyze",
        "context_policy",
        "marked_file_only",
        "write_metadata",
        "output_dirs",
        "mirror_dirs",
    ):
        if key in args:
            forwarded[key] = args[key]
    budget = apply_window_survey_budget(forwarded, args.get("context_budget"), capture_mode)
    forwarded["hwnd"] = int(window.get("hwnd"))
    process = str(window.get("process_name") or "window").replace(".exe", "")
    forwarded["source_label"] = safe_filename_part(f"window-survey-{index + 1}-{process}", "window-survey")
    return forwarded, budget


def select_window_survey_capture_records(records, selection):
    selection = str(selection or "first_n").strip().lower()
    if selection not in ("first_n", "ready_only", "suspected_problem"):
        raise ValueError("capture_selection must be first_n, ready_only, or suspected_problem")
    if selection == "ready_only":
        return [record for record in records if "minimized" not in record["states"] and "offscreen" not in record["states"]]
    if selection == "suspected_problem":
        return [record for record in records if any(state in record["states"] for state in ("minimized", "offscreen", "partly_offscreen", "possibly_occluded"))]
    return records


def action_guardian_survey_windows(args):
    try:
        require_feature("window_capture", args)
        capture_mode = normalize_window_survey_capture_mode(args)
        limits = runtime_limits(args)
        window_limit = int(args.get("limit", 50))
        if window_limit < 1:
            raise ValueError("limit must be at least 1")
        check_min_max(window_limit, 1, limits.get("window_survey_window_count_max"), "limit")
        default_capture_limit = 0 if capture_mode == "status_only" else min(6, window_limit)
        capture_limit = int(args.get("capture_limit", default_capture_limit))
        if capture_limit < 0:
            raise ValueError("capture_limit must be zero or greater")
        check_min_max(capture_limit, 0, limits.get("window_survey_capture_count_max"), "capture_limit")
        include_visibility_probe = bool(args.get("include_visibility_probe", True))
        all_windows = filtered_survey_windows(args)
        windows = all_windows[:window_limit]
        records = [window_survey_status(window, include_visibility_probe) for window in windows]
        captures = []
        capture_errors = []
        if capture_mode != "status_only" and capture_limit > 0 and records:
            status, libs = window_adapter_status()
            if not status.get("available"):
                raise RuntimeError(status.get("import_error") or "Window capture adapter is unavailable")
            by_hwnd = {int(window.get("hwnd")): window for window in windows}
            selected_records = select_window_survey_capture_records(records, args.get("capture_selection"))[: min(capture_limit, len(records))]
            for record in selected_records:
                hwnd = int(record.get("hwnd"))
                window = by_hwnd.get(hwnd)
                if not window:
                    continue
                capture_args, budget = window_survey_capture_args(args, window, len(captures), capture_mode)
                try:
                    image, source, libs = grab_known_window_image(capture_args, window, status, libs)
                    result = save_or_warn_capture(image, source, libs, capture_args)
                    item = {
                        "hwnd": hwnd,
                        "title": record.get("title"),
                        "process_name": record.get("process_name"),
                        "states": record.get("states"),
                        "context_budget": budget,
                        "result": result,
                    }
                    captures.append(item)
                    record["capture"] = {
                        "ok": bool(result.get("ok", False)),
                        "path": result.get("path", ""),
                        "metadata_path": result.get("metadata_path", ""),
                        "capture_deferred": bool(result.get("capture_deferred", False)),
                        "reason": result.get("reason", ""),
                    }
                except Exception as exc:
                    failure = {
                        "hwnd": hwnd,
                        "title": record.get("title"),
                        "process_name": record.get("process_name"),
                        "error": str(exc),
                    }
                    capture_errors.append(failure)
                    record["capture"] = {"ok": False, "error": str(exc)}
        saved_count = sum(1 for item in captures if item.get("result", {}).get("path"))
        deferred_count = sum(1 for item in captures if item.get("result", {}).get("capture_deferred"))
        return write_json(
            {
                "ok": True,
                "capture_mode": capture_mode,
                "windows_total": len(all_windows),
                "windows_reported": len(records),
                "window_limit": window_limit,
                "capture_limit": capture_limit,
                "saved_count": saved_count,
                "deferred_count": deferred_count,
                "error_count": len(capture_errors),
                "windows": records,
                "captures": captures,
                "capture_errors": capture_errors,
                "runtime_limits": {
                    "window_survey_window_count_max": limits.get("window_survey_window_count_max"),
                    "window_survey_capture_count_max": limits.get("window_survey_capture_count_max"),
                },
                "recommended_next": "Review windows first, then open only the relevant saved paths or retry individual capture_window calls with hwnd-specific settings.",
                "privacy": "Local window enumeration and optional local captures only; no upload, model call, subagent call, or background monitor.",
            }
        )
    except Exception as exc:
        return error(str(exc))


def action_guardian_prepare_workflow(args):
    workflow_type = str(args.get("workflow_type") or "").strip().lower()
    if workflow_type not in ("model_request", "decision_request", "monitor_tick", "capture_chain"):
        return error("workflow_type must be model_request, decision_request, monitor_tick, or capture_chain")
    settings = args.get("settings") if isinstance(args.get("settings"), dict) else {}
    objective = str(args.get("objective") or "").strip()
    source_path = str(args.get("source_path") or "").strip()
    common = {}
    for key in ("output_dir", "project_id", "workflow_id"):
        if key in args:
            common[key] = args[key]
    if workflow_type == "model_request":
        forwarded = {
            **common,
            "path": source_path,
            "prompt": objective or "Describe this artifact compactly for an AI agent.",
            "settings": settings,
        }
        if args.get("route_id"):
            forwarded["route_id"] = str(args.get("route_id"))
        return action_prepare_model_request(forwarded)
    if workflow_type == "decision_request":
        observation = {"source_path": source_path} if source_path else {}
        forwarded = {
            **common,
            "objective": objective,
            "observation": observation,
            "settings": settings,
        }
        if args.get("policy_id"):
            forwarded["policy_id"] = str(args.get("policy_id"))
        return action_prepare_decision_request(forwarded)
    if workflow_type == "capture_chain":
        forwarded = {
            **common,
            "objective": objective or "Prepare a guided capture chain.",
            "route": str(args.get("route") or settings.get("route") or "auto"),
            "trigger": args.get("trigger") if isinstance(args.get("trigger"), dict) else settings.get("trigger") if isinstance(settings.get("trigger"), dict) else {"type": "manual"},
            "steps": args.get("steps") if isinstance(args.get("steps"), list) else settings.get("steps") if isinstance(settings.get("steps"), list) else [],
            "quiet": bool(args.get("quiet", settings.get("quiet", True))),
            "settings": settings,
        }
        if args.get("decision_policy_id"):
            forwarded["decision_policy_id"] = str(args.get("decision_policy_id"))
        return action_prepare_capture_chain(forwarded)
    observations = {"objective": objective}
    if source_path:
        observations["source_path"] = source_path
    if settings:
        observations["settings"] = settings
    forwarded = {**common, "observations": observations}
    if args.get("profile_id"):
        forwarded["profile_id"] = str(args.get("profile_id"))
    return action_prepare_monitor_tick(forwarded)


def command_by_id(command_id):
    for command in CAPABILITY_COMMANDS:
        if command.get("id") == command_id:
            return copy.deepcopy(command)
    return None


def command_is_active(command, args=None):
    flags = feature_flags(args or {})
    required = command.get("required_features") or []
    return all(bool(flags.get(feature, False)) for feature in required)


def decorated_command(command, args=None):
    decorated = copy.deepcopy(command)
    required = decorated.get("required_features") or []
    flags = feature_flags(args or {})
    decorated["active"] = all(bool(flags.get(feature, False)) for feature in required)
    decorated["inactive_reasons"] = [
        f"Feature '{feature}' is inactive." for feature in required if not bool(flags.get(feature, False))
    ]
    return decorated


def action_guardian_list_commands(args):
    category = str(args.get("category") or "").strip().lower()
    include_disabled = bool(args.get("include_disabled", True))
    commands = []
    for command in CAPABILITY_COMMANDS:
        if category and command.get("category") != category:
            continue
        decorated = decorated_command(command, args)
        if not include_disabled and not decorated["active"]:
            continue
        commands.append(decorated)
    return write_json(
        {
            "ok": True,
            "commands": commands,
            "contract": {
                "normal_path": "Use registered commands to reduce main-AI tool selection load.",
                "no_arbitrary_code": "guardian_run_command only runs registry entries; arbitrary code belongs to guardian_prepare_exec/guardian_run_exec.",
                "break_glass": "guardian_run_exec requires persistent raw_local_exec=true and user_confirmed=true for every call.",
            },
        }
    )


def action_guardian_run_command(args):
    command_id = str(args.get("command_id") or "").strip()
    if not command_id:
        return error("command_id is required")
    command = command_by_id(command_id)
    if not command:
        return error("Unknown command_id", command_id=command_id, available=[item["id"] for item in CAPABILITY_COMMANDS])
    if not command_is_active(command, args):
        return error(
            "Command required feature flags are inactive.",
            command=decorated_command(command, args),
        )
    provided_args = args.get("args") if isinstance(args.get("args"), dict) else {}
    merged_args = deep_merge(command.get("default_args") or {}, provided_args)
    maps_to = command.get("maps_to")
    if maps_to in ("guardian_run_command", ""):
        return error("Invalid command mapping", command_id=command_id, maps_to=maps_to)
    handler = ACTIONS.get(maps_to)
    if not handler:
        return error("Registered command maps to an unknown action", command_id=command_id, maps_to=maps_to)
    return handler(merged_args)


def exec_audit_path(args):
    output_dir = ensure_cache_dir(get_cache_dir(args))
    return output_dir / f"{PLUGIN_NAME}-audit.jsonl"


def code_digest(code):
    return hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest()


def append_exec_audit(event, args):
    event = copy.deepcopy(event)
    event.setdefault("plugin", PLUGIN_NAME)
    event.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    path = exec_audit_path(args)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        json.dump(event, file, ensure_ascii=False, separators=(",", ":"))
        file.write("\n")
    return str(path)


def normalize_exec_language(language):
    language = str(language or "python").strip().lower()
    aliases = {"py": "python", "ps": "powershell", "pwsh": "powershell", "js": "node", "javascript": "node"}
    language = aliases.get(language, language)
    if language not in ("python", "powershell", "node"):
        raise ValueError("language must be python, powershell, or node")
    return language


def exec_timeout(args, request=None):
    request = request or {}
    limits = runtime_limits(args)
    timeout = float(args.get("timeout_seconds") or request.get("timeout_seconds") or 30)
    if timeout <= 0:
        raise ValueError("timeout_seconds must be greater than 0")
    check_min_max(timeout, 0.1, limits.get("raw_exec_timeout_seconds_max"), "timeout_seconds")
    return timeout


def exec_output_limit(args):
    limits = runtime_limits(args)
    limit = int(limits.get("raw_exec_output_chars_max") or 12000)
    return max(1000, limit)


def truncate_exec_text(text, limit):
    text = str(text or "")
    if len(text) <= limit:
        return {"text": text, "truncated": False, "original_chars": len(text)}
    half = max(1, (limit - 80) // 2)
    truncated = text[:half] + "\n...[screen-guardian truncated output]...\n" + text[-half:]
    return {"text": truncated, "truncated": True, "original_chars": len(text)}


def exec_cwd(value):
    path = Path(str(value or PLUGIN_ROOT)).expanduser()
    if not path.exists() or not path.is_dir():
        raise ValueError("cwd must be an existing directory")
    return path


def action_guardian_prepare_exec(args):
    code = str(args.get("code") or "")
    if not code:
        return error("code is required")
    try:
        language = normalize_exec_language(args.get("language"))
        timeout = exec_timeout(args)
        cwd = str(exec_cwd(args.get("cwd") or PLUGIN_ROOT))
    except Exception as exc:
        return error(str(exc))
    request = {
        "plugin": PLUGIN_NAME,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": "break_glass_exec_request",
        "language": language,
        "code": code,
        "code_sha256": code_digest(code),
        "code_length": len(code),
        "cwd": cwd,
        "timeout_seconds": timeout,
        "reason": str(args.get("reason") or "").strip(),
        "expected_output": str(args.get("expected_output") or "").strip(),
        "risk_note": str(args.get("risk_note") or "").strip(),
        "context": capture_context(args),
        "execution": {
            "status": "prepared",
            "note": "This envelope does not execute code. guardian_run_exec requires raw_local_exec=true and user_confirmed=true.",
        },
    }
    output_dir = ensure_cache_dir(get_cache_dir(args))
    filename = output_filename({"source_label": "break-glass-exec", **args}, "json")
    request_path = output_dir / filename
    write_json_file(request_path, request)
    audit_path = append_exec_audit(
        {
            "type": "break_glass_exec_prepared",
            "language": language,
            "code_sha256": request["code_sha256"],
            "code_length": request["code_length"],
            "cwd": cwd,
            "request_path": str(request_path),
            "reason": request["reason"],
        },
        args,
    )
    return write_json({"ok": True, "request_path": str(request_path), "audit_path": audit_path, "request": request})


def load_exec_request(args):
    envelope_path = str(args.get("envelope_path") or "").strip()
    if not envelope_path:
        return {}
    path = Path(envelope_path).expanduser()
    if not path.exists():
        raise ValueError("envelope_path does not exist")
    data = read_json_file(path, {})
    if data.get("type") != "break_glass_exec_request":
        raise ValueError("envelope_path is not a break_glass_exec_request")
    data["_envelope_path"] = str(path)
    return data


def exec_command_for(language, code):
    if language == "python":
        return [sys.executable, "-c", code]
    if language == "powershell":
        executable = shutil.which("powershell") or shutil.which("pwsh")
        if not executable:
            raise RuntimeError("PowerShell executable was not found on PATH")
        return [executable, "-NoProfile", "-NonInteractive", "-Command", code]
    if language == "node":
        executable = shutil.which("node")
        if not executable:
            raise RuntimeError("node executable was not found on PATH")
        return [executable, "-e", code]
    raise ValueError("language must be python, powershell, or node")


def action_guardian_run_exec(args):
    try:
        require_feature("raw_local_exec", args)
    except Exception as exc:
        return error(str(exc), feature="raw_local_exec")
    if not bool(args.get("user_confirmed", False)):
        return error("user_confirmed=true is required for every break-glass local execution call")
    try:
        request = load_exec_request(args)
        code = str(args.get("code") if args.get("code") is not None else request.get("code") or "")
        if not code:
            return error("code is required when envelope_path is not provided")
        language = normalize_exec_language(args.get("language") or request.get("language"))
        timeout = exec_timeout(args, request)
        cwd = exec_cwd(args.get("cwd") or request.get("cwd") or PLUGIN_ROOT)
        output_limit = exec_output_limit(args)
        command = exec_command_for(language, code)
    except Exception as exc:
        return error(str(exc))

    event = {
        "type": "break_glass_exec_started",
        "language": language,
        "code_sha256": code_digest(code),
        "code_length": len(code),
        "cwd": str(cwd),
        "timeout_seconds": timeout,
        "reason": str(args.get("reason") or request.get("reason") or "").strip(),
        "envelope_path": request.get("_envelope_path", ""),
    }
    audit_path = append_exec_audit(event, args)
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        stdout = truncate_exec_text(completed.stdout, output_limit)
        stderr = truncate_exec_text(completed.stderr, output_limit)
        status = {
            "type": "break_glass_exec_completed",
            "language": language,
            "code_sha256": event["code_sha256"],
            "exit_code": completed.returncode,
            "stdout_chars": stdout["original_chars"],
            "stderr_chars": stderr["original_chars"],
        }
        append_exec_audit(status, args)
        ok = completed.returncode == 0
        payload = {
            "ok": ok,
            "executed": True,
            "exit_code": completed.returncode,
            "language": language,
            "cwd": str(cwd),
            "timeout_seconds": timeout,
            "stdout": stdout["text"],
            "stderr": stderr["text"],
            "stdout_truncated": stdout["truncated"],
            "stderr_truncated": stderr["truncated"],
            "audit_path": audit_path,
            "privacy": "Break-glass local execution only. No upload, background service, or automatic retry was performed.",
        }
        if not ok:
            payload["error"] = "Raw local execution exited with a nonzero status."
        return write_json(payload)
    except subprocess.TimeoutExpired as exc:
        stdout = truncate_exec_text(exc.stdout or "", output_limit)
        stderr = truncate_exec_text(exc.stderr or "", output_limit)
        append_exec_audit(
            {
                "type": "break_glass_exec_timeout",
                "language": language,
                "code_sha256": event["code_sha256"],
                "timeout_seconds": timeout,
            },
            args,
        )
        return write_json(
            {
                "ok": False,
                "executed": True,
                "error": "Raw local execution timed out.",
                "language": language,
                "cwd": str(cwd),
                "timeout_seconds": timeout,
                "stdout": stdout["text"],
                "stderr": stderr["text"],
                "stdout_truncated": stdout["truncated"],
                "stderr_truncated": stderr["truncated"],
                "audit_path": audit_path,
            }
        )


def action_check(args):
    status, libs = mss_adapter_status()
    python_path = sys.executable
    if not status["available"]:
        return error(
            "Python screenshot dependencies are missing.",
            python=python_path,
            install_hint=status.get("install_hint"),
            import_error=status.get("import_error"),
            adapters=[status],
        )

    return write_json(
        {
            "ok": True,
            "python": python_path,
            "mss_version": getattr(libs["mss"], "__version__", "unknown"),
            "pillow_version": getattr(libs["Image"], "__version__", "unknown"),
            "default_cache_dir": str(DEFAULT_CACHE_DIR),
            "active_cache_dir": str(get_cache_dir(args)),
            "adapters": [status, window_adapter_status()[0], audio_adapter_status(args)[0], ffmpeg_status(), webpage_adapter_status(args)[0]],
            "privacy": "Captures are saved locally only. No upload or long-term recording is performed by this plugin.",
        }
    )


def action_list_adapters(args):
    mss_status, _libs = mss_adapter_status()
    window_status, _libs2 = window_adapter_status()
    audio_status, _audio_libs = audio_adapter_status(args)
    ffmpeg = ffmpeg_status()
    webpage_status, _web_libs = webpage_adapter_status(args)
    return write_json(
        {
            "ok": True,
            "selected": "auto",
            "adapters": [mss_status, window_status, audio_status, ffmpeg, webpage_status],
            "contract": {
                "request_adapter": "Use adapter='auto' unless a specific backend is needed.",
                "stable_result_fields": [
                    "ok",
                    "adapter",
                    "path",
                    "metadata_path",
                    "source",
                    "display",
                    "capture_box",
                    "original_size",
                    "saved_size",
                    "analysis",
                    "privacy",
                ],
            },
        }
    )


def action_list_audio_devices(args):
    probe = bool(args.get("probe", True))
    status, libs = audio_adapter_status(args)
    if not probe or not status.get("available"):
        return write_json(
            {
                "ok": True,
                "adapter": status,
                "devices": [],
                "note": "Audio device probing is optional and only runs when audio_capture is active.",
            }
        )
    try:
        sd = libs["sounddevice"]
        raw_devices = sd.query_devices()
        hostapis = sd.query_hostapis()
        devices = []
        for index, device in enumerate(raw_devices):
            hostapi_index = int(device.get("hostapi", -1))
            hostapi_name = hostapis[hostapi_index]["name"] if 0 <= hostapi_index < len(hostapis) else ""
            devices.append(
                {
                    "index": index,
                    "name": str(device.get("name", "")),
                    "hostapi": hostapi_name,
                    "max_input_channels": int(device.get("max_input_channels", 0)),
                    "max_output_channels": int(device.get("max_output_channels", 0)),
                    "default_samplerate": float(device.get("default_samplerate", 0)),
                    "loopback_candidate": "wasapi" in hostapi_name.lower() and int(device.get("max_output_channels", 0)) > 0,
                }
            )
        default_device = sd.default.device
        return write_json({"ok": True, "adapter": status, "default_device": list(default_device), "devices": devices})
    except Exception as exc:
        return error(str(exc), adapter=status)


def action_record_audio(args):
    try:
        require_feature("audio_capture", args)
        status, libs = audio_adapter_status(args)
        if not status.get("available"):
            return error("Audio capture adapter is unavailable.", adapter=status)
        limits = runtime_limits(args)
        duration = float(args.get("duration_seconds", 5))
        sample_rate = int(args.get("sample_rate", 44100))
        channels = int(args.get("channels", 1))
        if duration <= 0:
            raise ValueError("duration_seconds must be greater than 0")
        check_min_max(duration, None, limits.get("audio_duration_seconds_max"), "duration_seconds")
        check_min_max(sample_rate, 1, limits.get("audio_sample_rate_max"), "sample_rate")
        check_min_max(channels, 1, limits.get("audio_channels_max"), "channels")
        source = str(args.get("source") or "microphone").lower()
        loopback = bool(args.get("loopback", False)) or source in ("system", "system_loopback", "speaker", "output")
        device = args.get("device")
        sd = libs["sounddevice"]
        extra_settings = None
        if loopback:
            if os.name != "nt" or not hasattr(sd, "WasapiSettings"):
                return error("System loopback recording requires Windows WASAPI support in sounddevice.", adapter=status)
            extra_settings = sd.WasapiSettings(loopback=True)
            if device is None:
                default_device = sd.default.device
                if isinstance(default_device, (list, tuple)) and len(default_device) > 1:
                    device = default_device[1]
        frames = int(round(duration * sample_rate))
        output_path = audio_output_path({**args, "source_label": args.get("source_label") or source}, "wav")
        recording = sd.rec(frames, samplerate=sample_rate, channels=channels, dtype="int16", device=device, extra_settings=extra_settings)
        sd.wait()
        write_wav(output_path, recording.tobytes(), sample_rate, channels)
        analysis = analyze_wav_file(output_path, args) if bool(args.get("analyze", False)) else skipped_analysis("audio analysis not requested")
        metadata = {
            "plugin": PLUGIN_NAME,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": "audio_recording",
            "path": str(output_path),
            "source": {"type": source, "loopback": loopback, "device": device, "adapter": status["id"]},
            "format": "wav",
            "duration_seconds": duration,
            "sample_rate": sample_rate,
            "channels": channels,
            "analysis": analysis,
            "context": audio_context_payload(args),
            "privacy": "Saved locally only.",
        }
        metadata_path = write_media_metadata_sidecar(output_path, metadata, args)
        mirror_paths, mirror_metadata_paths = mirror_media_file(output_path, metadata, args)
        return write_json(
            {
                "ok": True,
                "path": str(output_path),
                "metadata_path": metadata_path,
                "mirror_paths": mirror_paths,
                "mirror_metadata_paths": mirror_metadata_paths,
                "source": metadata["source"],
                "duration_seconds": duration,
                "sample_rate": sample_rate,
                "channels": channels,
                "analysis": analysis,
                "privacy": metadata["privacy"],
            }
        )
    except Exception as exc:
        return error(str(exc))


def action_analyze_audio(args):
    try:
        path = Path(str(args.get("path") or "")).expanduser()
        if not path.exists():
            return error("path does not exist")
        if path.suffix.lower() != ".wav":
            return error("Only WAV analysis is supported by the lightweight analyzer. Extract or convert audio to WAV first.")
        analysis = analyze_wav_file(path, args)
        return write_json({"ok": True, "path": str(path), "analysis": analysis})
    except Exception as exc:
        return error(str(exc))


def action_extract_audio_track(args):
    try:
        require_feature("video_audio_extract", args)
        input_path = Path(str(args.get("path") or args.get("input_path") or "")).expanduser()
        if not input_path.exists():
            return error("input video path does not exist")
        ffmpeg = ffmpeg_status()
        if not ffmpeg["available"]:
            return error("FFmpeg is unavailable.", adapter=ffmpeg)
        limits = runtime_limits(args)
        duration = args.get("duration_seconds")
        if duration is not None:
            duration = float(duration)
            check_min_max(duration, None, limits.get("audio_extract_duration_seconds_max"), "duration_seconds")
        sample_rate = int(args.get("sample_rate", 44100))
        channels = int(args.get("channels", 1))
        output_path = audio_output_path({**args, "source_label": args.get("source_label") or f"{input_path.stem}-audio"}, "wav")
        command = [ffmpeg["executable"], "-y"]
        if args.get("start_seconds") is not None:
            command.extend(["-ss", str(float(args.get("start_seconds")))])
        command.extend(["-i", str(input_path)])
        if duration is not None:
            command.extend(["-t", str(duration)])
        command.extend(["-vn", "-acodec", "pcm_s16le", "-ar", str(sample_rate), "-ac", str(channels), str(output_path)])
        completed = subprocess.run(command, cwd=str(PLUGIN_ROOT), capture_output=True, text=True, timeout=int(args.get("timeout_seconds", 120)))
        if completed.returncode != 0:
            return error("FFmpeg failed to extract audio.", stderr=completed.stderr[-2000:], command=command)
        analysis = analyze_wav_file(output_path, args) if bool(args.get("analyze", False)) else skipped_analysis("audio analysis not requested")
        metadata = {
            "plugin": PLUGIN_NAME,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "type": "video_audio_extract",
            "path": str(output_path),
            "source": {"type": "video", "input_path": str(input_path), "adapter": "ffmpeg"},
            "format": "wav",
            "sample_rate": sample_rate,
            "channels": channels,
            "analysis": analysis,
            "context": audio_context_payload(args),
            "privacy": "Saved locally only.",
        }
        metadata_path = write_media_metadata_sidecar(output_path, metadata, args)
        mirror_paths, mirror_metadata_paths = mirror_media_file(output_path, metadata, args)
        return write_json(
            {
                "ok": True,
                "path": str(output_path),
                "metadata_path": metadata_path,
                "mirror_paths": mirror_paths,
                "mirror_metadata_paths": mirror_metadata_paths,
                "source": metadata["source"],
                "sample_rate": sample_rate,
                "channels": channels,
                "analysis": analysis,
                "privacy": metadata["privacy"],
            }
        )
    except Exception as exc:
        return error(str(exc))


def action_list_displays(args):
    try:
        adapter_id, libs = resolve_capture_adapter(args)
    except Exception as exc:
        return error(str(exc))

    with libs["mss"].MSS() as sct:
        monitors = [monitor_to_dict(i, monitor) for i, monitor in enumerate(sct.monitors)]

    return write_json(
        {
            "ok": True,
            "adapter": adapter_id,
            "displays": monitors,
            "note": "Index 0 is the full virtual desktop. Index 1 and above are individual displays.",
        }
    )


def action_list_windows(args):
    try:
        require_feature("window_capture", args)
        windows = enum_windows(args)
        limit = int(args.get("limit", 50))
        return write_json({"ok": True, "windows": windows[: max(1, min(limit, 200))], "count": len(windows)})
    except Exception as exc:
        return error(str(exc))


def save_capture_from_args(args, region=None):
    require_feature("screen_capture", args)
    args = dict(args)
    if region is not None:
        args["region"] = region
    image, source, libs = grab_screen_image(args)
    return write_json(save_or_warn_capture(image, source, libs, args))


def action_capture_screen(args):
    try:
        return save_capture_from_args(args)
    except Exception as exc:
        return error(str(exc))


def action_capture_region(args):
    region = {
        "left": args.get("left", 0),
        "top": args.get("top", 0),
        "width": args.get("width", 0),
        "height": args.get("height", 0),
        "relative_to_display": args.get("relative_to_display", True),
    }
    forwarded = {k: v for k, v in args.items() if k not in region}
    try:
        return save_capture_from_args(forwarded, region=region)
    except Exception as exc:
        return error(str(exc))


def action_capture_window(args):
    try:
        require_feature("window_capture", args)
        status, libs = window_adapter_status()
        if not status["available"]:
            raise RuntimeError(status.get("import_error") or "Window capture adapter is unavailable")
        window = find_window(args)
        preflight = window_pre_capture_guard_payload(args, window, status)
        if preflight:
            return write_json(preflight)
        image, source, libs = grab_known_window_image(args, window, status, libs)
        return write_json(save_or_warn_capture(image, source, libs, args))
    except WindowMatchError as exc:
        return error(str(exc), **exc.payload)
    except Exception as exc:
        return error(str(exc))


def action_analyze_image(args):
    try:
        require_feature("image_analysis", args)
    except Exception as exc:
        return error(str(exc), feature="image_analysis")
    path = Path(str(args.get("path") or "")).expanduser()
    if not path.exists():
        return error("path does not exist")
    libs, import_error = import_capture_libs()
    if import_error:
        return error("Python image dependencies are missing.", import_error=import_error)
    image = libs["Image"].open(path)
    analysis = analyze_image_object(image, libs)
    return write_json({"ok": True, "path": str(path), "analysis": analysis})


def action_preprocess_image(args):
    try:
        require_feature("image_preprocess", args)
    except Exception as exc:
        return error(str(exc), feature="image_preprocess")
    path = Path(str(args.get("path") or "")).expanduser()
    if not path.exists():
        return error("path does not exist")
    libs, import_error = import_capture_libs()
    if import_error:
        return error("Python image dependencies are missing.", import_error=import_error)
    image = libs["Image"].open(path).convert("RGB")
    source = {"type": "image_file", "adapter": "pillow", "input_path": str(path)}
    merged_args = dict(args)
    merged_args.setdefault("source_label", path.stem)
    return write_json(save_capture_image(image, source, libs, merged_args))


def action_watch_screen(args):
    try:
        require_feature("bounded_watch", args)
        watch_args = args_with_region_from_flat(args)
        limits = runtime_limits(args)
        duration = float(args.get("duration_seconds", 3))
        interval = float(args.get("interval_seconds", 0.5))
        threshold = float(args.get("change_threshold", 8.0))
        max_captures = int(args.get("max_captures", 10))
        burst_frames = int(args.get("burst_frames", 1))
        save_initial = bool(args.get("save_initial", False))
        if duration <= 0:
            raise ValueError("duration_seconds must be greater than 0")
        check_min_max(duration, None, limits.get("watch_duration_seconds_max"), "duration_seconds")
        check_min_max(interval, limits.get("watch_interval_seconds_min"), limits.get("watch_interval_seconds_max"), "interval_seconds")
        if threshold < 0:
            raise ValueError("change_threshold must be zero or greater")
        if max_captures < 1:
            raise ValueError("max_captures must be at least 1")
        check_min_max(max_captures, None, limits.get("watch_max_captures_max"), "max_captures")
        if burst_frames < 1:
            raise ValueError("burst_frames must be at least 1")
        check_min_max(burst_frames, None, limits.get("watch_burst_frames_max"), "burst_frames")

        deadline = time.time() + duration
        captures = []
        previous = None
        samples = 0
        events = 0
        while time.time() <= deadline and len(captures) < max_captures:
            image, source, libs = grab_watch_image(watch_args)
            samples += 1
            changed = previous is None
            score = 0.0
            if previous is not None:
                score = image_difference_score(image, previous, libs)
                changed = score >= threshold
            if (previous is None and save_initial) or (previous is not None and changed):
                events += 1
                frames_to_save = 1 if previous is None else burst_frames
                for burst_index in range(frames_to_save):
                    if len(captures) >= max_captures or time.time() > deadline:
                        break
                    frame = image
                    frame_source = source
                    if burst_index > 0:
                        time.sleep(min(interval, max(0.1, deadline - time.time())))
                        frame, frame_source, libs = grab_watch_image(watch_args)
                        samples += 1
                    capture_args = dict(watch_args)
                    capture_args["source_label"] = capture_args.get("source_label") or "watch"
                    result = save_capture_image(frame, frame_source, libs, capture_args)
                    result["change_score"] = round(score, 2)
                    result["watch_event_index"] = events
                    result["burst_index"] = burst_index
                    captures.append(result)
            previous = image
            if time.time() < deadline:
                time.sleep(interval)
        return write_json(
            {
                "ok": True,
                "samples": samples,
                "captures": captures,
                "events": events,
                "target": "window" if source.get("type") == "window" else "screen",
                "duration_seconds": duration,
                "interval_seconds": interval,
                "change_threshold": threshold,
                "burst_frames": burst_frames,
                "runtime_limits": limits,
                "privacy": "Bounded local watch only; no background service remains running.",
            }
        )
    except WindowMatchError as exc:
        return error(str(exc), **exc.payload)
    except Exception as exc:
        return error(str(exc))


def read_plugin_metadata(path):
    try:
        with Path(path).open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def cache_file_owned_by_plugin(path):
    path = Path(path)
    if path.name.endswith(".meta.json"):
        return read_plugin_metadata(path).get("plugin") == PLUGIN_NAME
    metadata_path = path.with_suffix(path.suffix + ".meta.json")
    if metadata_path.exists():
        return read_plugin_metadata(metadata_path).get("plugin") == PLUGIN_NAME
    return path.name.startswith(f"{PLUGIN_NAME}-")


def action_clear_cache(args):
    explicit_dir = str(args.get("output_dir") or args.get("cache_dir") or "").strip()
    if explicit_dir:
        cache_dir = Path(explicit_dir).expanduser()
        if not is_configured_cache_dir(cache_dir):
            return error(
                "clear_cache only accepts the default cache path or a path already configured with set_cache_path/set_storage_routes.",
                requested=str(cache_dir),
                allowed=serialize_paths(configured_cache_dirs()),
            )
    else:
        cache_dir = get_cache_dir({})
    if not cache_dir.exists():
        return write_json({"ok": True, "deleted": 0, "cache_dir": str(cache_dir)})

    all_files = bool(args.get("all", False))
    older_than_days = args.get("older_than_days")
    cutoff = None
    if older_than_days is not None:
        cutoff = time.time() - float(older_than_days) * 86400

    deleted = 0
    skipped = 0
    seen = set()
    patterns = [
        f"{PLUGIN_NAME}-*.png",
        f"{PLUGIN_NAME}-*.jpg",
        f"{PLUGIN_NAME}-*.jpeg",
        f"{PLUGIN_NAME}-*.wav",
        f"{PLUGIN_NAME}-*.json",
        f"{PLUGIN_NAME}-*.png.meta.json",
        f"{PLUGIN_NAME}-*.jpg.meta.json",
        f"{PLUGIN_NAME}-*.jpeg.meta.json",
        f"{PLUGIN_NAME}-*.wav.meta.json",
    ]
    for pattern in patterns:
        for path in cache_dir.glob(pattern):
            if not path.is_file():
                continue
            key = path_key(path)
            if key in seen:
                continue
            seen.add(key)
            if not cache_file_owned_by_plugin(path):
                skipped += 1
                continue
            if not all_files and cutoff is not None and path.stat().st_mtime > cutoff:
                continue
            if not all_files and cutoff is None:
                continue
            path.unlink()
            deleted += 1

    return write_json(
        {
            "ok": True,
            "deleted": deleted,
            "skipped_not_owned": skipped,
            "cache_dir": str(cache_dir),
            "allowed_cache_dirs": serialize_paths(configured_cache_dirs()),
            "scope": "default-or-configured-cache-only",
        }
    )


ACTIONS = {
    "guardian_check": action_guardian_check,
    "guardian_capture_targets": action_guardian_capture_targets,
    "guardian_sniff_context": action_guardian_sniff_context,
    "guardian_perceive": action_guardian_perceive,
    "guardian_survey_windows": action_guardian_survey_windows,
    "guardian_prepare_workflow": action_guardian_prepare_workflow,
    "guardian_list_commands": action_guardian_list_commands,
    "guardian_run_command": action_guardian_run_command,
    "guardian_prepare_exec": action_guardian_prepare_exec,
    "guardian_run_exec": action_guardian_run_exec,
    "list_capture_routes": action_list_capture_routes,
    "prepare_capture_chain": action_prepare_capture_chain,
    "check": action_check,
    "get_runtime_settings": action_get_runtime_settings,
    "set_cache_path": action_set_cache_path,
    "set_storage_routes": action_set_storage_routes,
    "set_runtime_limits": action_set_runtime_limits,
    "set_feature_flags": action_set_feature_flags,
    "list_extension_routes": action_list_extension_routes,
    "set_extension_route": action_set_extension_route,
    "prepare_model_request": action_prepare_model_request,
    "list_decision_policies": action_list_decision_policies,
    "set_decision_policy": action_set_decision_policy,
    "prepare_decision_request": action_prepare_decision_request,
    "list_monitor_profiles": action_list_monitor_profiles,
    "set_monitor_profile": action_set_monitor_profile,
    "prepare_monitor_tick": action_prepare_monitor_tick,
    "get_display_profile": action_get_display_profile,
    "set_display_name": action_set_display_name,
    "apply_display_profile": action_apply_display_profile,
    "list_adapters": action_list_adapters,
    "list_audio_devices": action_list_audio_devices,
    "record_audio": action_record_audio,
    "analyze_audio": action_analyze_audio,
    "extract_audio_track": action_extract_audio_track,
    "list_displays": action_list_displays,
    "list_windows": action_list_windows,
    "capture_screen": action_capture_screen,
    "capture_region": action_capture_region,
    "capture_window": action_capture_window,
    "prepare_webpage_capture": action_prepare_webpage_capture,
    "capture_webpage": action_capture_webpage,
    "watch_screen": action_watch_screen,
    "analyze_image": action_analyze_image,
    "preprocess_image": action_preprocess_image,
    "clear_cache": action_clear_cache,
}


def normalize_json_request(raw_request):
    text = str(raw_request or "").lstrip("\ufeff\ufffe")
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        return stripped
    starts = [pos for pos in (stripped.find("{"), stripped.find("[")) if pos >= 0]
    if starts:
        first_start = min(starts)
        if first_start <= 8:
            return stripped[first_start:]
    quote_start = stripped.find('"')
    if quote_start >= 0 and quote_start <= 8:
        possible_object = stripped[quote_start:]
        if '":' in possible_object[:80] and possible_object.rstrip().endswith("}"):
            return "{" + possible_object
    return stripped


def main():
    if len(sys.argv) < 2:
        if not sys.stdin.isatty():
            raw_request = sys.stdin.read()
        else:
            return error("Missing JSON request.")
    elif sys.argv[1] in ("--stdin", "-"):
        raw_request = sys.stdin.read()
    else:
        raw_request = sys.argv[1]
    try:
        request = json.loads(normalize_json_request(raw_request))
    except Exception as exc:
        return error(f"Invalid JSON request: {exc}")

    action = request.get("action")
    args = request.get("args") or {}
    handler = ACTIONS.get(action)
    if not handler:
        return error(f"Unknown action: {action}")
    result = handler(args)
    return 0 if result is None else result


if __name__ == "__main__":
    raise SystemExit(main())
