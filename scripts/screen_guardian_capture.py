import json
import locale
import os
import sys
import time
from pathlib import Path


PLUGIN_NAME = "screen-guardian"
DEFAULT_CACHE_DIR = Path.home() / "Pictures" / "ScreenGuardian"
PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
CONFIG_DIR = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "ScreenGuardian"
CONFIG_PATH = CONFIG_DIR / "config.json"
DEFAULT_DISPLAY_CONFIG = {
    "mode": "auto",
    "manual_name": "",
    "manual_short_description": "",
}
DISPLAY_PROFILES = {
    "en": {
        "display_name": "Screen Guardian",
        "short_description": "Ultra-light AI screen access without forced upgrades.",
    },
    "zh": {
        "display_name": "屏幕守护者",
        "short_description": "不强迫升级的超轻量 AI 屏幕访问。",
    },
    "zh-cn": {
        "display_name": "屏幕守护者",
        "short_description": "不强迫升级的超轻量 AI 屏幕访问。",
    },
    "zh-tw": {
        "display_name": "螢幕守護者",
        "short_description": "不強迫升級的超輕量 AI 螢幕存取。",
    },
    "ja": {
        "display_name": "スクリーンガーディアン",
        "short_description": "アップグレードを強制しない軽量 AI 画面アクセス。",
    },
    "ko": {
        "display_name": "스크린 가디언",
        "short_description": "강제 업그레이드 없는 초경량 AI 화면 접근.",
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


def read_json_file(path, default):
    try:
        if not path.exists():
            return dict(default)
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            return dict(default)
        merged = dict(default)
        merged.update(data)
        return merged
    except Exception:
        return dict(default)


def write_json_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


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
    try:
        value = locale.getlocale()[0]
    except Exception:
        value = None
    if value:
        candidates.append(value)
    try:
        value = locale.getlocale(locale.LC_CTYPE)[0]
    except Exception:
        value = None
    if value:
        candidates.append(value)
    try:
        value = locale.setlocale(locale.LC_CTYPE)
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
        profile = DISPLAY_PROFILES[locale_key]
        return profile, locale_key
    language = locale_key.split("-")[0]
    if language in DISPLAY_PROFILES:
        profile = DISPLAY_PROFILES[language]
        return profile, language
    return DISPLAY_PROFILES["en"], "en"


def load_display_config():
    config = read_json_file(CONFIG_PATH, DEFAULT_DISPLAY_CONFIG)
    mode = str(config.get("mode", "auto")).lower()
    if mode not in ("auto", "manual"):
        config["mode"] = "auto"
    return config


def build_display_profile(config=None):
    config = config or load_display_config()
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

    config = load_display_config()
    config["mode"] = mode
    if mode == "manual":
        config["manual_name"] = display_name
        config["manual_short_description"] = short_description
    elif bool(args.get("clear_manual", False)):
        config["manual_name"] = ""
        config["manual_short_description"] = ""
    config["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_json_file(CONFIG_PATH, config)

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


def import_capture_libs():
    try:
        import mss
        from PIL import Image
        return mss, Image, None
    except Exception as exc:
        return None, None, str(exc)


def mss_adapter_status():
    mss, Image, import_error = import_capture_libs()
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
            "mss": getattr(mss, "__version__", "unknown"),
            "Pillow": getattr(Image, "__version__", "unknown"),
        }
    return status, mss, Image


def action_list_adapters(args):
    status, _mss, _Image = mss_adapter_status()
    return write_json(
        {
            "ok": True,
            "selected": "auto",
            "adapters": [status],
            "contract": {
                "request_adapter": "Use adapter='auto' unless a specific backend is needed.",
                "stable_result_fields": [
                    "ok",
                    "adapter",
                    "path",
                    "display",
                    "capture_box",
                    "original_size",
                    "saved_size",
                    "privacy",
                ],
            },
        }
    )


def resolve_capture_adapter(args):
    requested = str(args.get("adapter", "auto")).lower()
    if requested not in ("auto", "python-mss", "mss"):
        raise ValueError("adapter must be auto or python-mss")

    status, mss, Image = mss_adapter_status()
    if not status["available"]:
        raise RuntimeError(
            "No capture adapter is available. Install the lightweight dependencies with: "
            + status["install_hint"]
        )
    return status["id"], mss, Image


def get_cache_dir(args):
    output_dir = args.get("output_dir")
    if output_dir:
        return Path(output_dir).expanduser()
    return DEFAULT_CACHE_DIR


def ensure_cache_dir(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def monitor_to_dict(index, monitor):
    return {
        "index": index,
        "left": int(monitor["left"]),
        "top": int(monitor["top"]),
        "width": int(monitor["width"]),
        "height": int(monitor["height"]),
    }


def action_check(args):
    status, mss, Image = mss_adapter_status()
    python_path = sys.executable
    if not status["available"]:
        return error(
            "Python screenshot dependencies are missing.",
            python=python_path,
            install_hint=status["install_hint"],
            import_error=status.get("import_error"),
            adapters=[status],
        )

    cache_dir = get_cache_dir(args)
    return write_json(
        {
            "ok": True,
            "python": python_path,
            "mss_version": getattr(mss, "__version__", "unknown"),
            "pillow_version": getattr(Image, "__version__", "unknown"),
            "default_cache_dir": str(cache_dir),
            "adapters": [status],
            "privacy": "Captures are saved locally only. No upload or long-term recording is performed by this plugin.",
        }
    )


def action_list_displays(args):
    try:
        adapter_id, mss, _Image = resolve_capture_adapter(args)
    except Exception as exc:
        return error(str(exc))

    with mss.MSS() as sct:
        monitors = [monitor_to_dict(i, monitor) for i, monitor in enumerate(sct.monitors)]

    return write_json(
        {
            "ok": True,
            "adapter": adapter_id,
            "displays": monitors,
            "note": "Index 0 is the full virtual desktop. Index 1 and above are individual displays.",
        }
    )


def normalized_format(value):
    fmt = str(value or "png").lower().strip(".")
    if fmt in ("jpg", "jpeg"):
        return "jpg"
    if fmt == "png":
        return "png"
    raise ValueError("format must be png or jpg")


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
    scale = args.get("scale")
    max_width = args.get("max_width")
    max_height = args.get("max_height")

    new_width = int(width)
    new_height = int(height)

    if scale is not None:
        scale = float(scale)
        if scale <= 0 or scale > 1:
            raise ValueError("scale must be greater than 0 and no more than 1")
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


def save_capture(args, region=None):
    args = dict(args)
    if region is not None:
        args["region"] = region

    try:
        adapter_id, mss, Image = resolve_capture_adapter(args)
        fmt = normalized_format(args.get("format", "png"))
        output_dir = ensure_cache_dir(get_cache_dir(args))
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        suffix = int((time.time() % 1) * 1000)
        filename = f"{PLUGIN_NAME}-{timestamp}-{suffix:03d}.{fmt}"
        output_path = output_dir / filename

        with mss.MSS() as sct:
            box, display = capture_box(sct, args)
            shot = sct.grab(box)
            image = Image.frombytes("RGB", shot.size, shot.rgb)

        original_width, original_height = image.size
        target_width, target_height = resize_dimensions(original_width, original_height, args)
        if (target_width, target_height) != image.size:
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)

        quality = int(args.get("quality", 90))
        if fmt == "jpg":
            quality = max(1, min(95, quality))
            image.save(output_path, "JPEG", quality=quality)
        else:
            image.save(output_path, "PNG")

        return write_json(
            {
                "ok": True,
                "adapter": adapter_id,
                "path": str(output_path),
                "format": fmt,
                "display": display,
                "capture_box": {
                    "left": int(box["left"]),
                    "top": int(box["top"]),
                    "width": int(box["width"]),
                    "height": int(box["height"]),
                },
                "original_size": {
                    "width": original_width,
                    "height": original_height,
                },
                "saved_size": {
                    "width": image.size[0],
                    "height": image.size[1],
                },
                "cursor_included": False,
                "privacy": "Saved locally only.",
            }
        )
    except Exception as exc:
        return error(str(exc))


def action_capture_screen(args):
    return save_capture(args)


def action_capture_region(args):
    region = {
        "left": args.get("left", 0),
        "top": args.get("top", 0),
        "width": args.get("width", 0),
        "height": args.get("height", 0),
        "relative_to_display": args.get("relative_to_display", True),
    }
    forwarded = {k: v for k, v in args.items() if k not in region}
    return save_capture(forwarded, region=region)


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
    patterns = [f"{PLUGIN_NAME}-*.png", f"{PLUGIN_NAME}-*.jpg", f"{PLUGIN_NAME}-*.jpeg"]
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
    "get_display_profile": action_get_display_profile,
    "set_display_name": action_set_display_name,
    "apply_display_profile": action_apply_display_profile,
    "list_adapters": action_list_adapters,
    "list_displays": action_list_displays,
    "capture_screen": action_capture_screen,
    "capture_region": action_capture_region,
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
