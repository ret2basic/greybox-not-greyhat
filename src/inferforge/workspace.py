from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ArtifactError
from .util import (
    load_json,
    path_is_within,
    sha256_file,
    utc_now,
    write_json_atomic,
    write_text_atomic,
)

MANIFEST_NAME = "artifact-manifest.json"


def write_artifact_set(
    workspace: Path,
    *,
    source_digest: str,
    json_artifacts: dict[str, Any],
    text_artifacts: dict[str, str],
) -> dict[str, Any]:
    workspace.mkdir(parents=True, exist_ok=True)
    for name, value in json_artifacts.items():
        write_json_atomic(workspace / name, value)
    for name, value in text_artifacts.items():
        write_text_atomic(workspace / name, value)

    files: list[dict[str, Any]] = []
    for name in sorted([*json_artifacts, *text_artifacts]):
        path = workspace / name
        files.append(
            {
                "path": name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "schema_version": 2,
        "source_digest": source_digest,
        "generated_at": utc_now(),
        "files": files,
    }
    write_json_atomic(workspace / MANIFEST_NAME, manifest)
    return manifest


def load_manifest(workspace: Path) -> dict[str, Any]:
    path = workspace / MANIFEST_NAME
    if not path.is_file():
        raise ArtifactError(f"scan artifact manifest is missing: {path}; run scan first")
    document = load_json(path)
    if not isinstance(document, dict) or document.get("schema_version") != 2:
        raise ArtifactError(f"unsupported or malformed artifact manifest: {path}")
    if not isinstance(document.get("files"), list):
        raise ArtifactError(f"manifest file list is malformed: {path}")
    return document


def verify_artifacts(
    workspace: Path,
    *,
    current_source_digest: str | None = None,
    current_engine_version: str | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(workspace)
    problems: list[dict[str, Any]] = []
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            problems.append({"kind": "malformed-manifest-entry"})
            continue
        relative = Path(entry["path"])
        path = workspace / relative
        if relative.is_absolute() or not path_is_within(path, workspace):
            problems.append({"kind": "artifact-path-escape", "path": entry["path"]})
            continue
        if not path.is_file():
            problems.append({"kind": "missing-artifact", "path": entry["path"]})
            continue
        actual_size = path.stat().st_size
        if actual_size != entry.get("bytes"):
            problems.append(
                {
                    "kind": "size-mismatch",
                    "path": entry["path"],
                    "expected": entry.get("bytes"),
                    "actual": actual_size,
                }
            )
            continue
        actual_hash = sha256_file(path)
        if actual_hash != entry.get("sha256"):
            problems.append(
                {
                    "kind": "digest-mismatch",
                    "path": entry["path"],
                    "expected": entry.get("sha256"),
                    "actual": actual_hash,
                }
            )
    if current_source_digest is not None and manifest.get("source_digest") != current_source_digest:
        problems.append(
            {
                "kind": "source-digest-mismatch",
                "artifact_source_digest": manifest.get("source_digest"),
                "current_source_digest": current_source_digest,
            }
        )
    if current_engine_version is not None:
        run_path = workspace / "run.json"
        run_document = load_json(run_path) if run_path.is_file() else {}
        artifact_engine_version = (
            run_document.get("inferforge_version") if isinstance(run_document, dict) else None
        )
        if artifact_engine_version != current_engine_version:
            problems.append(
                {
                    "kind": "engine-version-mismatch",
                    "artifact_engine_version": artifact_engine_version,
                    "current_engine_version": current_engine_version,
                }
            )
    return {
        "status": "valid" if not problems else "invalid",
        "source_digest": manifest.get("source_digest"),
        "checked": len(manifest["files"]),
        "problems": problems,
    }


def require_valid_artifacts(workspace: Path) -> dict[str, Any]:
    result = verify_artifacts(workspace)
    if result["status"] != "valid":
        raise ArtifactError(f"scan artifacts failed integrity verification: {result['problems']}")
    return result


def load_artifact(workspace: Path, name: str) -> dict[str, Any]:
    path = workspace / name
    if not path.is_file():
        raise ArtifactError(f"required scan artifact is missing: {path}")
    value = load_json(path)
    if not isinstance(value, dict):
        raise ArtifactError(f"artifact root must be an object: {path}")
    return value
