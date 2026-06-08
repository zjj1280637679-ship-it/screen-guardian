import argparse
import base64
import copy
import datetime as dt
import hashlib
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_OUTPUT_DIR = Path.home() / "Pictures" / "ScreenGuardian" / "ArkRuns"
DEFAULT_API_KEY_ENV = "ARK_API_KEY"

LOCAL_MEDIA_LIMITS = {
    "image": 20 * 1024 * 1024,
    "video": 50 * 1024 * 1024,
    "audio": 25 * 1024 * 1024,
}

AUDIO_FORMATS = {
    ".aac": "aac",
    ".flac": "flac",
    ".m4a": "m4a",
    ".mp3": "mp3",
    ".ogg": "ogg",
    ".wav": "wav",
    ".webm": "webm",
}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(payload):
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    sys.stdout.flush()


def load_json(path):
    with Path(path).expanduser().open("r", encoding="utf-8") as file:
        return json.load(file)


def safe_label(value, fallback="run"):
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


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def infer_media_kind(path=None, url=None, role=None, explicit="auto"):
    if explicit and explicit != "auto":
        return explicit
    role = str(role or "").lower()
    if role in ("video_summary",):
        return "video"
    if role in ("audio_summary", "transcription", "sound_diagnostics"):
        return "audio"
    name = str(path or url or "").split("?")[0].lower()
    guess, _encoding = mimetypes.guess_type(name)
    if guess:
        if guess.startswith("image/"):
            return "image"
        if guess.startswith("video/"):
            return "video"
        if guess.startswith("audio/"):
            return "audio"
    suffix = Path(name).suffix
    if suffix in AUDIO_FORMATS:
        return "audio"
    if suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
        return "image"
    if suffix in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"):
        return "video"
    return "text" if not path and not url else "image"


def media_mime(path, kind):
    guessed, _encoding = mimetypes.guess_type(str(path))
    if guessed:
        return guessed
    if kind == "image":
        return "image/png"
    if kind == "video":
        return "video/mp4"
    if kind == "audio":
        return "audio/wav"
    return "application/octet-stream"


def ensure_local_size(path, kind, allow_large):
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"media path does not exist: {path}")
    size = path.stat().st_size
    limit = LOCAL_MEDIA_LIMITS.get(kind)
    if limit and size > limit and not allow_large:
        raise ValueError(
            f"local {kind} file is {size} bytes, above the conservative {limit} byte inline limit; "
            "use --url for hosted media or pass --allow-large-local intentionally"
        )
    return size


def local_data_url(path, kind, allow_large):
    path = Path(path).expanduser()
    ensure_local_size(path, kind, allow_large)
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_mime(path, kind)};base64,{encoded}"


def local_audio_data(path, allow_large):
    path = Path(path).expanduser()
    ensure_local_size(path, "audio", allow_large)
    suffix = path.suffix.lower()
    audio_format = AUDIO_FORMATS.get(suffix, suffix.lstrip(".") or "wav")
    return {
        "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        "format": audio_format,
    }


def build_prompt(args, envelope):
    prompt = args.prompt
    if not prompt and envelope:
        prompt = envelope.get("prompt")
    prompt = str(prompt or "").strip()
    questions = list(args.question or [])
    if envelope and isinstance(envelope.get("questions"), list):
        questions.extend(str(item) for item in envelope["questions"] if str(item).strip())
    if questions:
        followups = "\n".join(f"- {item}" for item in questions)
        prompt = f"{prompt}\n\nFollow-up questions:\n{followups}".strip()
    if not prompt:
        prompt = "Describe this artifact compactly for an AI agent."
    return prompt


def merged_settings(args, envelope):
    settings = {}
    if envelope and isinstance(envelope.get("route"), dict) and isinstance(envelope["route"].get("settings"), dict):
        settings.update(envelope["route"]["settings"])
    if envelope and isinstance(envelope.get("settings"), dict):
        settings.update(envelope["settings"])
    for key in ("temperature", "max_tokens", "detail", "fps", "language", "quality", "thinking"):
        value = getattr(args, key, None)
        if value is not None:
            settings[key] = value
    return settings


def resolve_value(args_value, env_value, setting_value, default=""):
    if args_value not in (None, ""):
        return args_value
    if env_value not in (None, ""):
        return env_value
    if setting_value not in (None, ""):
        return setting_value
    return default


def build_chat_url(base_or_endpoint):
    value = str(base_or_endpoint or DEFAULT_BASE_URL).rstrip("/")
    if value.endswith("/chat/completions"):
        return value
    return f"{value}/chat/completions"


def build_content(args, envelope, kind, settings, prompt):
    path = args.path or (envelope or {}).get("input_path") or ""
    url = args.url or ""
    content = []
    media_source = {
        "kind": kind,
        "path": str(Path(path).expanduser()) if path else "",
        "url": url,
    }

    if kind == "image":
        image_url = url or local_data_url(path, kind, args.allow_large_local)
        image_payload = {"url": image_url}
        detail = settings.get("detail")
        if detail:
            image_payload["detail"] = str(detail)
        content.append({"type": "image_url", "image_url": image_payload})
    elif kind == "video":
        video_url = url or local_data_url(path, kind, args.allow_large_local)
        video_payload = {"url": video_url}
        fps = settings.get("fps")
        if fps is not None:
            video_payload["fps"] = float(fps)
        content.append({"type": "video_url", "video_url": video_payload})
    elif kind == "audio":
        if url:
            audio_payload = {"url": url}
            audio_format = settings.get("format") or Path(url.split("?")[0]).suffix.lstrip(".")
            if audio_format:
                audio_payload["format"] = str(audio_format)
        else:
            audio_payload = local_audio_data(path, args.allow_large_local)
        content.append({"type": "input_audio", "input_audio": audio_payload})

    content.append({"type": "text", "text": prompt})
    return content, media_source


def build_payload(args, envelope):
    settings = merged_settings(args, envelope)
    route = (envelope or {}).get("route") or {}
    model = resolve_value(args.model, os.environ.get("ARK_MODEL"), route.get("model") or settings.get("model"))
    if not model:
        raise ValueError("model is required; pass --model or set ARK_MODEL")

    role = args.role or (envelope or {}).get("role") or "vision_summary"
    path = args.path or (envelope or {}).get("input_path") or ""
    kind = infer_media_kind(path=path, url=args.url, role=role, explicit=args.media_kind)
    prompt = build_prompt(args, envelope)
    content, media_source = build_content(args, envelope, kind, settings, prompt)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
    }
    if settings.get("temperature") is not None:
        payload["temperature"] = float(settings["temperature"])
    if settings.get("max_tokens") is not None:
        payload["max_tokens"] = int(settings["max_tokens"])
    if settings.get("thinking") in ("enabled", "disabled", "auto"):
        payload["thinking"] = {"type": settings["thinking"]}

    return payload, {
        "model": model,
        "role": role,
        "media_kind": kind,
        "media_source": media_source,
        "settings": settings,
        "prompt_sha256": sha256_text(prompt),
        "prompt_chars": len(prompt),
    }


def redact_large_values(value):
    if isinstance(value, dict):
        return {key: redact_large_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_large_values(item) for item in value]
    if isinstance(value, str):
        if value.startswith("data:") and ";base64," in value:
            prefix, encoded = value.split(";base64,", 1)
            return f"{prefix};base64,<redacted {len(encoded)} chars sha256={sha256_text(encoded)}>"
        if len(value) > 600 and re.fullmatch(r"[A-Za-z0-9+/=\r\n]+", value):
            return f"<redacted base64-like {len(value)} chars sha256={sha256_text(value)}>"
    return value


def call_chat_completions(chat_url, payload, api_key, timeout):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        chat_url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw), response.status
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ark API HTTP {exc.code}: {body_text[:2000]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ark API request failed: {exc}") from exc


def extract_output_text(response):
    try:
        choices = response.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or ""))
                else:
                    parts.append(str(item))
            return "\n".join(part for part in parts if part).strip()
    except Exception:
        return ""
    return ""


def run_id_for(args, meta):
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    label = safe_label(args.label or meta.get("media_kind") or meta.get("role"))
    seed = json.dumps({"label": label, "meta": meta, "time": time.time()}, sort_keys=True, ensure_ascii=False)
    return f"ark-{timestamp}-{label}-{sha256_text(seed)[:8]}"


def write_artifacts(args, payload, meta, response=None, status=None):
    output_dir = Path(args.output_dir or DEFAULT_OUTPUT_DIR).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_id_for(args, meta)
    request_path = output_dir / f"{run_id}.request.redacted.json"
    summary_path = output_dir / f"{run_id}.summary.json"
    response_path = output_dir / f"{run_id}.response.json"
    ledger_path = Path(args.ledger_path).expanduser() if args.ledger_path else output_dir / "volcengine-ark-ledger.jsonl"

    redacted_request = {
        "created_at": now_iso(),
        "chat_url": build_chat_url(args.base_url),
        "request": redact_large_values(payload),
        "meta": meta,
        "privacy": "API key is read from an environment variable and never written. Inline media bytes are redacted in this request artifact.",
    }
    request_path.write_text(json.dumps(redacted_request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if response is not None:
        response_path.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        response_path = None

    output_text = extract_output_text(response or {})
    usage = (response or {}).get("usage") or {}
    summary = {
        "ok": status in ("ok", "dry_run"),
        "status": status,
        "created_at": now_iso(),
        "run_id": run_id,
        "model": meta.get("model"),
        "role": meta.get("role"),
        "media_kind": meta.get("media_kind"),
        "media_source": meta.get("media_source"),
        "settings": meta.get("settings"),
        "usage": usage,
        "output_text": output_text,
        "request_path": str(request_path),
        "response_path": str(response_path) if response_path else "",
        "summary_path": str(summary_path),
        "ledger_path": str(ledger_path),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if not args.no_ledger:
        ledger_entry = {
            "created_at": summary["created_at"],
            "run_id": run_id,
            "status": status,
            "model": meta.get("model"),
            "role": meta.get("role"),
            "media_kind": meta.get("media_kind"),
            "media_source": meta.get("media_source"),
            "settings": meta.get("settings"),
            "usage": usage,
            "request_path": str(request_path),
            "response_path": str(response_path) if response_path else "",
            "summary_path": str(summary_path),
        }
        with ledger_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(ledger_entry, ensure_ascii=False) + "\n")

    return summary


def parse_args():
    parser = argparse.ArgumentParser(description="Run a real Volcengine Ark multimodal experiment from a Screen Guardian file or request envelope.")
    parser.add_argument("--envelope", help="Path to a Screen Guardian prepare_model_request JSON envelope.")
    parser.add_argument("--path", help="Local image, video, or audio file.")
    parser.add_argument("--url", help="Hosted image, video, or audio URL. Prefer URL for large videos.")
    parser.add_argument("--media-kind", choices=["auto", "image", "video", "audio", "text"], default="auto")
    parser.add_argument("--role", choices=["vision_summary", "video_summary", "audio_summary", "transcription", "ocr", "judgment", "custom"], default="")
    parser.add_argument("--prompt", help="Primary prompt. Defaults to the envelope prompt or a compact description prompt.")
    parser.add_argument("--question", action="append", help="Follow-up question. Can be repeated.")
    parser.add_argument("--model", default="", help="Ark model id. Defaults to ARK_MODEL or the route model in an envelope.")
    parser.add_argument("--base-url", default=os.environ.get("ARK_BASE_URL", DEFAULT_BASE_URL), help="Ark API base URL or full chat/completions endpoint.")
    parser.add_argument("--api-key-env", default="", help=f"Environment variable containing the API key. Defaults to {DEFAULT_API_KEY_ENV} or the envelope route.")
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--detail", choices=["low", "high", "xhigh"])
    parser.add_argument("--fps", type=float, help="Video sampling fps. Official range is 0.2 to 5 for video understanding.")
    parser.add_argument("--language", help="Preferred output language.")
    parser.add_argument("--quality", help="Provider-specific quality label to carry in local artifacts.")
    parser.add_argument("--thinking", choices=["enabled", "disabled", "auto"], help="Ark thinking mode when supported by the selected model.")
    parser.add_argument("--allow-large-local", action="store_true", help="Allow inline local media above conservative script limits.")
    parser.add_argument("--dry-run", action="store_true", help="Build and save a redacted request artifact without calling Ark.")
    parser.add_argument("--print-request", action="store_true", help="Print the redacted request payload to stdout.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for request, response, summary, and ledger files.")
    parser.add_argument("--ledger-path", default="", help="Optional JSONL ledger path.")
    parser.add_argument("--no-ledger", action="store_true", help="Do not append to the JSONL ledger.")
    parser.add_argument("--label", default="", help="Short run label used in artifact filenames.")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        envelope = load_json(args.envelope) if args.envelope else None
        if not args.path and not args.url and envelope and envelope.get("input_path"):
            args.path = envelope["input_path"]
        if not args.role and envelope:
            args.role = envelope.get("role") or ""
        route = (envelope or {}).get("route") or {}
        if not args.api_key_env:
            args.api_key_env = route.get("api_key_env") or DEFAULT_API_KEY_ENV
        if route.get("endpoint") and args.base_url == DEFAULT_BASE_URL:
            args.base_url = route["endpoint"]

        payload, meta = build_payload(args, envelope)
        chat_url = build_chat_url(args.base_url)
        meta["chat_url"] = chat_url
        if args.path and Path(args.path).expanduser().exists():
            meta["media_source"]["sha256"] = sha256_file(Path(args.path).expanduser())
            meta["media_source"]["bytes"] = Path(args.path).expanduser().stat().st_size

        if args.print_request:
            write_json({"chat_url": chat_url, "request": redact_large_values(payload), "meta": meta})

        if args.dry_run:
            summary = write_artifacts(args, payload, meta, response=None, status="dry_run")
            summary["ok"] = True
            summary["dry_run"] = True
            write_json(summary)
            return 0

        api_key = os.environ.get(args.api_key_env or DEFAULT_API_KEY_ENV)
        if not api_key:
            raise ValueError(f"missing API key; set ${args.api_key_env or DEFAULT_API_KEY_ENV} or pass --dry-run")
        response, http_status = call_chat_completions(chat_url, payload, api_key, args.timeout_seconds)
        meta["http_status"] = http_status
        summary = write_artifacts(args, payload, meta, response=response, status="ok")
        write_json(summary)
        return 0
    except Exception as exc:
        write_json({"ok": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
