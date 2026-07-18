from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ArtifactError, TriageError
from .evidence import artifact_source_digest, evidence_is_current, source_evidence
from .models import ReviewTask
from .util import load_json, utc_now, write_json_atomic

REVIEW_STATE_ARTIFACT = "review-state.json"
REVIEW_STATUSES = ("open", "completed", "not-applicable")


def load_review_state(workspace: Path) -> dict[str, Any]:
    path = workspace / REVIEW_STATE_ARTIFACT
    if not path.is_file():
        return {"schema_version": 2, "records": {}, "history": []}
    value = load_json(path)
    if not isinstance(value, dict) or value.get("schema_version") != 2:
        raise ArtifactError(f"invalid review-state artifact: {path}")
    if not isinstance(value.get("records"), dict) or not isinstance(value.get("history"), list):
        raise ArtifactError(f"invalid review-state record structure: {path}")
    return value


def apply_review_state(
    tasks: list[ReviewTask],
    state: dict[str, Any],
    file_hashes: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    records = state.get("records", {})
    stale: list[dict[str, Any]] = []
    for task in tasks:
        record = records.get(task.id)
        if isinstance(record, dict) and record.get("status") in REVIEW_STATUSES:
            if file_hashes is not None and not evidence_is_current(record, file_hashes):
                stale.append(
                    {
                        "task_id": task.id,
                        "recorded_status": record.get("status"),
                        "reason": "evidence-file-digest-changed-or-missing",
                    }
                )
                continue
            task.status = record["status"]
    return stale


def record_review(
    *,
    workspace: Path,
    source_root: Path,
    task: dict[str, Any],
    status: str,
    note: str,
    evidence: list[str],
    verification: list[str],
    analyst: str | None,
) -> dict[str, Any]:
    if status not in REVIEW_STATUSES:
        raise TriageError(f"unsupported review status: {status}")
    if len(note.strip()) < 12:
        raise TriageError("review note must explain the decision in at least 12 characters")
    evidence_rows = [source_evidence(value, source_root) for value in evidence]
    verification_rows = [value.strip() for value in verification if value.strip()]
    if status == "completed" and (not evidence_rows or not verification_rows):
        raise TriageError(
            "completed review requires source evidence and an independent verification reference"
        )
    if status == "not-applicable" and not evidence_rows:
        raise TriageError("not-applicable review requires source evidence for the rationale")

    now = utc_now()
    record = {
        "task_id": task["id"],
        "status": status,
        "note": note.strip(),
        "evidence": evidence_rows,
        "verification": verification_rows,
        "analyst": analyst,
        "source_digest": artifact_source_digest(workspace),
        "updated_at": now,
    }
    state = load_review_state(workspace)
    previous = state["records"].get(task["id"])
    history = dict(record)
    if isinstance(previous, dict):
        history["previous_status"] = previous.get("status")
    state["records"][task["id"]] = record
    state["history"].append(history)
    write_json_atomic(workspace / REVIEW_STATE_ARTIFACT, state)
    return record


def record_for_task(state: dict[str, Any], task: dict[str, Any]) -> dict[str, Any] | None:
    record = state.get("records", {}).get(task.get("id"))
    return record if isinstance(record, dict) else None
