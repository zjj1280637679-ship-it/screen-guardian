import ctypes
import ctypes.wintypes
import copy
import json
import locale
import math
import os
import shutil
import sys
import time
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
    "jpeg_quality_min": 1,
    "jpeg_quality_max": 95,
}

DEFAULT_FEATURE_FLAGS = {
    "screen_capture": True,
    "window_capture": True,
    "bounded_watch": True,
    "workflow_metadata": True,
    "multi_storage_routes": True,
    "image_analysis": True,
    "image_preprocess": True,
    "extension_routes": True,
    "model_request_envelopes": True,
    "ocr_routes": False,
    "image_narration_routes": False,
    "video_narration_routes": False,
    "external_api_handoff": False,
    "codex_subagent_handoff": False,
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
    "external_api_handoff": {
        "status": "interface",
        "cost_when_inactive": "No external API request is made.",
    },
    "codex_subagent_handoff": {
        "status": "interface",
        "cost_when_inactive": "No subagent handoff is started.",
    },
}

ROLE_FEATURES = {
    "ocr": "ocr_routes",
    "vision_summary": "image_narration_routes",
    "video_summary": "video_narration_routes",
    "transcription": "video_narration_routes",
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
}

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
    if isinstance(args.get("runtime_limits"), dict):
        limits = deep_merge(limits, args["runtime_limits"])
    if isinstance(args.get("limit_overrides"), dict):
        limits = deep_merge(limits, args["limit_overrides"])
    return limits


def feature_flags(args=None):
    config = load_config()
    flags = deep_merge(DEFAULT_FEATURE_FLAGS, config.get("feature_flags") or {})
    args = args or {}
    if isinstance(args.get("feature_flags"), dict):
        flags = deep_merge(flags, args["feature_flags"])
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
        "capabilities": ["list_windows", "capture_window", "non_topmost_best_effort"],
        "compatibility_note": "Best-effort HWND capture. Some GPU, minimized, or protected windows may return blank frames.",
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
    return {
        "index": index,
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
        return monitor, monitor_to_dict(display_index, monitor)

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
    return box, monitor_to_dict(display_index, monitor)


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
    adapter_id, libs = resolve_capture_adapter(args)
    with libs["mss"].MSS() as sct:
        box, display = capture_box(sct, args)
        shot = sct.grab(box)
        image = libs["Image"].frombytes("RGB", shot.size, shot.rgb)
    source = {
        "type": "screen",
        "adapter": adapter_id,
        "display": display,
        "capture_box": {
            "left": int(box["left"]),
            "top": int(box["top"]),
            "width": int(box["width"]),
            "height": int(box["height"]),
        },
    }
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


def save_capture_image(image, source, libs, args):
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
        "format": fmt,
        "path": str(output_path),
        "original_size": {"width": original_width, "height": original_height},
        "saved_size": {"width": processed.size[0], "height": processed.size[1]},
        "preprocess": {"requested": str(args.get("preprocess", "none")), "applied": applied_preprocess},
        "analysis": analysis_after,
        "analysis_before_preprocess": analysis_before,
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


def enum_windows(args=None):
    if os.name != "nt":
        return []
    args = args or {}
    user32 = ctypes.windll.user32
    windows = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        title_buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title_buffer, length + 1)
        title = title_buffer.value.strip()
        rect = window_rect(hwnd)
        if not rect or rect["width"] <= 0 or rect["height"] <= 0:
            return True
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_name = process_name_for_pid(pid.value)
        windows.append(
            {
                "hwnd": int(hwnd),
                "title": title,
                "pid": int(pid.value),
                "process_name": process_name,
                "rect": rect,
                "is_minimized": bool(user32.IsIconic(hwnd)),
            }
        )
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


def find_window(args):
    hwnd = args.get("hwnd")
    if hwnd:
        rect = window_rect(int(hwnd))
        if rect:
            return {"hwnd": int(hwnd), "title": "", "pid": 0, "process_name": "", "rect": rect}
    windows = enum_windows(args)
    exact_title = str(args.get("exact_title") or "").lower()
    if exact_title:
        windows = [w for w in windows if w["title"].lower() == exact_title]
    if not windows:
        raise ValueError("No matching window found")
    return windows[0]


def image_looks_black(image, libs):
    stat = libs["ImageStat"].Stat(image.convert("RGB"))
    mean = sum(stat.mean) / 3.0
    contrast = sum(stat.stddev) / 3.0
    return mean < 1.0 and contrast < 0.5


def grab_window_image(args):
    status, libs = window_adapter_status()
    if not status["available"]:
        raise RuntimeError(status.get("import_error") or "Window capture adapter is unavailable")
    window = find_window(args)
    hwnd = int(window["hwnd"])
    capture_method = "pillow-imagegrab-window"
    try:
        image = libs["ImageGrab"].grab(window=hwnd)
        if image_looks_black(image, libs):
            rect = window.get("rect") or {}
            if rect:
                capture_method = "pillow-imagegrab-bbox-after-black-window-frame"
                image = libs["ImageGrab"].grab(
                    bbox=(rect["left"], rect["top"], rect["right"], rect["bottom"]),
                    all_screens=True,
                )
    except TypeError:
        rect = window.get("rect") or {}
        if not rect:
            raise
        capture_method = "pillow-imagegrab-bbox-fallback"
        image = libs["ImageGrab"].grab(
            bbox=(rect["left"], rect["top"], rect["right"], rect["bottom"]),
            all_screens=True,
        )
    source = {
        "type": "window",
        "adapter": status["id"],
        "capture_method": capture_method,
        "window": window,
        "capture_box": window.get("rect"),
        "compatibility_note": "HWND capture is best-effort. Minimized, protected, or GPU-rendered windows may return blank or stale frames.",
    }
    return image.convert("RGB"), source, libs


def image_difference_score(a, b, libs):
    ImageChops = libs["ImageChops"]
    ImageStat = libs["ImageStat"]
    if a.size != b.size:
        b = b.resize(a.size)
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    stat = ImageStat.Stat(diff)
    return sum(stat.mean) / 3.0


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
                "jpeg_quality_min": "encoder quality",
                "jpeg_quality_max": "encoder quality",
            },
            "feature_flags": config.get("feature_flags", {}),
            "feature_catalog": FEATURE_CATALOG,
            "extension_routes": config.get("extension_routes", []),
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
            "note": "Use null, 'none', or 'unbounded' to remove a configurable upper/lower limit where the underlying encoder or geometry still permits it.",
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
            "note": "Inactive features return at the tool boundary or skip their optional work so they do not drag the active capture path.",
        }
    )


def normalized_route(args):
    route_id = safe_filename_part(args.get("id") or args.get("route_id") or "", "")
    if not route_id:
        raise ValueError("route id is required")
    role = str(args.get("role") or "vision_summary").strip().lower()
    allowed_roles = ("judgment", "ocr", "vision_summary", "video_summary", "transcription", "custom")
    if role not in allowed_roles:
        raise ValueError("role must be judgment, ocr, vision_summary, video_summary, transcription, or custom")
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
            "feature": "video_narration_routes",
            "input_types": ["audio", "video"],
            "handoff_modes": ["prepared_file", "external_api", "codex_subagent"],
            "settings": ["language", "temperature", "timestamps"],
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
                "roles": ["judgment", "ocr", "vision_summary", "video_summary", "transcription", "custom"],
                "settings_examples": ["temperature", "quality", "max_tokens", "detail", "language"],
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
            "adapters": [status, window_adapter_status()[0]],
            "privacy": "Captures are saved locally only. No upload or long-term recording is performed by this plugin.",
        }
    )


def action_list_adapters(args):
    mss_status, _libs = mss_adapter_status()
    window_status, _libs2 = window_adapter_status()
    return write_json(
        {
            "ok": True,
            "selected": "auto",
            "adapters": [mss_status, window_status],
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
    return write_json(save_capture_image(image, source, libs, args))


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
        image, source, libs = grab_window_image(args)
        return write_json(save_capture_image(image, source, libs, args))
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
    except Exception as exc:
        return error(str(exc))


def action_clear_cache(args):
    cache_dir = get_cache_dir(args)
    if not cache_dir.exists():
        return write_json({"ok": True, "deleted": 0, "cache_dir": str(cache_dir)})

    all_files = bool(args.get("all", False))
    older_than_days = args.get("older_than_days")
    cutoff = None
    if older_than_days is not None:
        cutoff = time.time() - float(older_than_days) * 86400

    deleted = 0
    patterns = [f"{PLUGIN_NAME}-*.png", f"{PLUGIN_NAME}-*.jpg", f"{PLUGIN_NAME}-*.jpeg", f"{PLUGIN_NAME}-*.png.meta.json", f"{PLUGIN_NAME}-*.jpg.meta.json"]
    for pattern in patterns:
        for path in cache_dir.glob(pattern):
            if not path.is_file():
                continue
            if not all_files and cutoff is not None and path.stat().st_mtime > cutoff:
                continue
            if not all_files and cutoff is None:
                continue
            path.unlink()
            deleted += 1

    return write_json({"ok": True, "deleted": deleted, "cache_dir": str(cache_dir)})


ACTIONS = {
    "check": action_check,
    "get_runtime_settings": action_get_runtime_settings,
    "set_cache_path": action_set_cache_path,
    "set_storage_routes": action_set_storage_routes,
    "set_runtime_limits": action_set_runtime_limits,
    "set_feature_flags": action_set_feature_flags,
    "list_extension_routes": action_list_extension_routes,
    "set_extension_route": action_set_extension_route,
    "prepare_model_request": action_prepare_model_request,
    "get_display_profile": action_get_display_profile,
    "set_display_name": action_set_display_name,
    "apply_display_profile": action_apply_display_profile,
    "list_adapters": action_list_adapters,
    "list_displays": action_list_displays,
    "list_windows": action_list_windows,
    "capture_screen": action_capture_screen,
    "capture_region": action_capture_region,
    "capture_window": action_capture_window,
    "watch_screen": action_watch_screen,
    "analyze_image": action_analyze_image,
    "preprocess_image": action_preprocess_image,
    "clear_cache": action_clear_cache,
}


def main():
    if len(sys.argv) < 2:
        return error("Missing JSON request.")
    try:
        request = json.loads(sys.argv[1])
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
