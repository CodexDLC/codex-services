"""Validation of the installer-owned manifest and AGENTS.md block."""

import hashlib
import json
import re
from typing import Any

MARKER_START = b"<!-- codex-services:skill:start -->"
MARKER_END = b"<!-- codex-services:skill:end -->"
MANIFEST_NAME = ".manifest.json"
SKILL_ID = "codex-services"
_INSTRUCTION = b"Use [codex-services](.agents/skills/codex-services/SKILL.md) for codex_services work."
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_INVALID_WINDOWS = set('<>:"\\|?*')


class ManifestError(Exception):
    pass


def hash_content(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_normalized_posix_path(path_str: str) -> None:
    if not isinstance(path_str, str) or not path_str or path_str.startswith("/"):
        raise ManifestError(f"Invalid relative path: {path_str!r}")
    for segment in path_str.split("/"):
        if (
            not segment
            or segment in {".", ".."}
            or segment[-1] in ". "
            or any(c in _INVALID_WINDOWS or ord(c) < 32 for c in segment)
        ):
            raise ManifestError(f"Invalid path segment: {path_str!r}")
        device = segment.split(".", 1)[0].upper()
        if device in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(r"(?:COM|LPT)[1-9]", device):
            raise ManifestError(f"Windows device path: {path_str!r}")


def _validate_file_names(names: set[str]) -> None:
    if "SKILL.md" not in names:
        raise ManifestError("SKILL.md missing")
    aliases: set[str] = set()
    for name in names:
        validate_normalized_posix_path(name)
        if name.rsplit("/", 1)[-1].casefold() in {MANIFEST_NAME.casefold(), "agents.md"}:
            raise ManifestError(f"Reserved owned path: {name}")
        alias = name.casefold()
        if alias in aliases:
            raise ManifestError(f"Case alias: {name}")
        aliases.add(alias)
    for alias in aliases:
        parts = alias.split("/")
        if any("/".join(parts[:i]) in aliases for i in range(1, len(parts))):
            raise ManifestError(f"File and parent conflict: {alias}")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_manifest(content: bytes) -> dict[str, Any]:
    try:
        data = json.loads(content.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise ManifestError("Malformed manifest JSON") from exc
    if not isinstance(data, dict) or set(data) != {"version", "skill", "package_version", "files", "agents_created"}:
        raise ManifestError("Invalid manifest schema")
    if (
        data["version"] != "1.0"
        or data["skill"] != SKILL_ID
        or not isinstance(data["package_version"], str)
        or not data["package_version"]
    ):
        raise ManifestError("Invalid manifest identity")
    if type(data["agents_created"]) is not bool or not isinstance(data["files"], dict):
        raise ManifestError("Invalid manifest fields")
    files = data["files"]
    _validate_file_names(set(files))
    for name, digest in files.items():
        if not isinstance(digest, str) or not _HASH.fullmatch(digest):
            raise ManifestError(f"Invalid SHA256 hash for {name}")
    return data


def build_manifest(package_version: str, files: dict[str, bytes], agents_created: bool = False) -> bytes:
    _validate_file_names(set(files))
    if not package_version:
        raise ManifestError("Missing package version")
    data = {
        "version": "1.0",
        "skill": SKILL_ID,
        "package_version": package_version,
        "files": {name: hash_content(value) for name, value in sorted(files.items())},
        "agents_created": agents_created,
    }
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")


def _block_bounds(content: bytes) -> tuple[int, int, bool] | None:
    body = content[3:] if content.startswith(b"\xef\xbb\xbf") else content
    if body.count(MARKER_START) != body.count(MARKER_END) or body.count(MARKER_START) > 1:
        raise ManifestError("Missing or duplicate AGENTS.md marker")
    if MARKER_START not in body:
        return None
    start = body.index(MARKER_START)
    end = body.index(MARKER_END, start) if MARKER_END in body[start:] else -1
    if end < 0 or (start and body[start - 1 : start] != b"\n"):
        raise ManifestError("Malformed AGENTS.md block")
    newline = b"\r\n" if body[start + len(MARKER_START) :].startswith(b"\r\n") else b"\n"
    for separator in (True, False):
        metadata = b"<!-- codex-services:skill:separator=" + (b"1" if separator else b"0") + b" -->"
        expected = newline.join((MARKER_START, metadata, _INSTRUCTION, MARKER_END))
        if body[start : start + len(expected)] == expected:
            finish = start + len(expected)
            if body[finish : finish + len(newline)] == newline:
                finish += len(newline)
            elif finish != len(body):
                raise ManifestError("Malformed AGENTS.md block ending")
            if separator and (start == 0 or body[start - len(newline) : start] != newline):
                raise ManifestError("Malformed AGENTS.md separator")
            offset = 3 if content.startswith(b"\xef\xbb\xbf") else 0
            return start + offset, finish + offset, separator
    raise ManifestError("AGENTS.md instruction modified or corrupt")


def has_valid_agents_block(content: bytes) -> bool:
    return _block_bounds(content) is not None


def update_agents_md_bytes(content: bytes, remove: bool = False) -> bytes:
    bounds = _block_bounds(content)
    if bounds is not None:
        start, end, separator = bounds
        if remove:
            if separator:
                start -= 2 if content[start - 2 : start] == b"\r\n" else 1
            return content[:start] + content[end:]
        return content
    if remove:
        return content
    body = content[3:] if content.startswith(b"\xef\xbb\xbf") else content
    newline = b"\r\n" if b"\r\n" in body else b"\n"
    separator = bool(body and not body.endswith(b"\n"))
    metadata = b"<!-- codex-services:skill:separator=" + (b"1" if separator else b"0") + b" -->"
    block = newline.join((MARKER_START, metadata, _INSTRUCTION, MARKER_END)) + newline
    return content + (newline if separator else b"") + block
