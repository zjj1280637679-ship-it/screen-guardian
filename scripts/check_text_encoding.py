#!/usr/bin/env python3
"""Guard repository text against unstable localized command examples."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

TEXT_GLOBS = [
    "README.md",
    "SECURITY.md",
    ".editorconfig",
    ".gitattributes",
    ".mcp.json",
    ".codex-plugin/plugin.json",
    "package.json",
    "docs/**/*.md",
    "docs/**/*.txt",
    "scenario-cards/**/*.md",
    "reference-source/**/*.md",
    "optimized-runtime/**/*.md",
    "traceability/**/*.md",
    "traceability/**/*.yml",
    "skills/**/*.md",
    "scripts/*.py",
    "scripts/*.ps1",
    "mcp/*.cjs",
]

README_ASCII_ONLY = {ROOT / "README.md"}
COMMAND_EXAMPLE_FILES = {
    ROOT / "README.md",
    ROOT / "docs" / "VOLCENGINE_EXPERIMENTS.md",
}

COMMAND_LINE_MARKERS = (
    "--prompt",
    "prompt =",
    "questions =",
)

MOJIBAKE_PATTERNS = {
    "replacement character": "\ufffd",
    "screen guardian mojibake": "\u705e\u5fd3\u7bb7",
    "guardian mojibake": "\u7039\u581f\u59e2",
    "prompt mojibake": "\u7487\u98ce",
    "prompt mojibake alt": "\u7487\u5cf0",
    "chinese-language mojibake": "\u6d93\ue15f\u6783",
    "brief mojibake": "\u7ee0\u20ac",
    "usage mojibake": "\u9422\u3129\u567a",
    "japanese-name mojibake": "\u9288",
    "korean-name mojibake": "\u9780",
    "traditional-name mojibake": "\u94fb",
    "punctuation mojibake": "\u951b",
    "full-stop mojibake": "\u9286",
}


def iter_text_paths() -> list[Path]:
    paths: set[Path] = set()
    for pattern in TEXT_GLOBS:
        for path in ROOT.glob(pattern):
            if path.is_file() and "__pycache__" not in path.parts:
                paths.add(path)
    return sorted(paths)


def has_non_ascii(value: str) -> bool:
    return any(ord(ch) > 127 for ch in value)


def first_non_ascii(value: str) -> str:
    for ch in value:
        if ord(ch) > 127:
            return f"U+{ord(ch):04X}"
    return ""


def check_file(path: Path) -> list[str]:
    rel = path.relative_to(ROOT).as_posix()
    errors: list[str] = []
    try:
        data = path.read_bytes()
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"{rel}: not valid UTF-8 at byte {exc.start}"]

    if path in README_ASCII_ONLY and has_non_ascii(text):
        errors.append(f"{rel}: README must stay ASCII-only; found {first_non_ascii(text)}")

    for label, pattern in MOJIBAKE_PATTERNS.items():
        if pattern in text:
            errors.append(f"{rel}: possible mojibake pattern '{label}'")

    for line_no, line in enumerate(text.splitlines(), 1):
        if any(0xE000 <= ord(ch) <= 0xF8FF for ch in line):
            errors.append(f"{rel}:{line_no}: private-use character often means mojibake")
        if path in COMMAND_EXAMPLE_FILES:
            if any(marker in line for marker in COMMAND_LINE_MARKERS) and has_non_ascii(line):
                errors.append(f"{rel}:{line_no}: command prompt/question line should be ASCII-only")

    return errors


def main() -> int:
    paths = iter_text_paths()
    errors: list[str] = []
    for path in paths:
        errors.extend(check_file(path))

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        print(f"\nSummary: checked {len(paths)} files, {len(errors)} encoding issue(s)")
        return 1

    print(f"PASS checked {len(paths)} UTF-8 text files")
    print("PASS README command examples are ASCII-only")
    print("PASS localized command prompts use runtime decoding or variables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
