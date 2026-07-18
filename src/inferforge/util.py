from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Iterable
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SECRET_VALUE_RE = re.compile(
    r"(?i)(?P<prefix>(?:api[_-]?key|secret|token|password|private[_-]?key)\s*[:=]\s*)"
    r"(?P<quote>['\"]?)(?P<value>[^\s,'\"}]{6,})(?P=quote)"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_id(prefix: str, *parts: object, length: int = 16) -> str:
    material = "\0".join(str(part) for part in parts)
    digest = hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(value)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(temporary_name)


def write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            if value and not value.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(temporary_name)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def redact_snippet(value: str, *, max_chars: int = 500) -> str:
    value = SECRET_VALUE_RE.sub(lambda match: f"{match.group('prefix')}<redacted>", value)
    value = re.sub(
        r"(?i)(-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----).*",
        r"\1 <redacted>",
        value,
    )
    value = value.replace("\x00", "")
    return value[:max_chars]


def normalize_code(value: str) -> str:
    without_comments = re.sub(r"//.*|#.*", "", value)
    return re.sub(r"\s+", " ", without_comments).strip()


def dedupe_dicts(items: Iterable[dict[str, Any]], *, key: str = "id") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for item in items:
        marker = item.get(key)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def git_metadata(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", "-C", str(root), *args],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return None
        return completed.stdout.strip() or None

    top_level = run("rev-parse", "--show-toplevel")
    if not top_level:
        return {"repository": False}
    commit = run("rev-parse", "HEAD")
    branch = run("branch", "--show-current")
    status = run("status", "--porcelain", "--untracked-files=no")
    return {
        "repository": True,
        "commit": commit,
        "branch": branch,
        "tracked_worktree_dirty": bool(status),
    }


def severity_rank(value: str) -> int:
    return {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}.get(value, -1)
