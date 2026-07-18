from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import TriageError
from .util import load_json, path_is_within, sha256_file


def source_evidence(value: str, source_root: Path) -> dict[str, Any]:
    raw_path, separator, raw_line = value.rpartition(":")
    if not separator or not raw_path or not raw_line.isdigit():
        raise TriageError(f"evidence must use PATH:LINE syntax: {value!r}")
    raw = Path(raw_path)
    resolved = raw.resolve() if raw.is_absolute() else (source_root / raw).resolve()
    if not path_is_within(resolved, source_root):
        raise TriageError(f"evidence is outside source root: {raw_path}")
    if not resolved.is_file():
        raise TriageError(f"evidence file does not exist: {raw_path}")
    line = int(raw_line)
    if line <= 0:
        raise TriageError("evidence line must be positive")
    with resolved.open(encoding="utf-8", errors="replace") as handle:
        if not any(line_number == line for line_number, _ in enumerate(handle, start=1)):
            raise TriageError(f"evidence line does not exist: {raw_path}:{line}")
    return {
        "path": resolved.relative_to(source_root).as_posix(),
        "line": line,
        "sha256": sha256_file(resolved),
    }


def evidence_is_current(record: dict[str, Any], file_hashes: dict[str, str]) -> bool:
    evidence = record.get("evidence", [])
    if not isinstance(evidence, list):
        return False
    for item in evidence:
        if not isinstance(item, dict):
            return False
        path = item.get("path")
        expected = item.get("sha256")
        if not isinstance(path, str) or not isinstance(expected, str):
            return False
        if file_hashes.get(path) != expected:
            return False
    return True


def artifact_source_digest(workspace: Path) -> str | None:
    path = workspace / "artifact-manifest.json"
    if not path.is_file():
        return None
    value = load_json(path)
    digest = value.get("source_digest") if isinstance(value, dict) else None
    return digest if isinstance(digest, str) else None
