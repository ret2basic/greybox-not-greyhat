from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ArtifactError, TriageError
from .evidence import artifact_source_digest, evidence_is_current, source_evidence
from .models import TRIAGE_STATUSES, Candidate
from .util import load_json, utc_now, write_json_atomic

TRIAGE_ARTIFACT = "triage.json"


def load_triage(workspace: Path) -> dict[str, Any]:
    path = workspace / TRIAGE_ARTIFACT
    if not path.is_file():
        return {"schema_version": 2, "records": {}, "history": []}
    value = load_json(path)
    if not isinstance(value, dict) or value.get("schema_version") != 2:
        raise ArtifactError(f"invalid triage artifact: {path}")
    if not isinstance(value.get("records"), dict) or not isinstance(value.get("history"), list):
        raise ArtifactError(f"invalid triage record structure: {path}")
    return value


def apply_triage(
    candidates: list[Candidate],
    triage: dict[str, Any],
    file_hashes: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    records = triage.get("records", {})
    stale: list[dict[str, Any]] = []
    for candidate in candidates:
        record = records.get(candidate.fingerprint)
        if isinstance(record, dict) and record.get("status") in TRIAGE_STATUSES:
            if file_hashes is not None and not evidence_is_current(record, file_hashes):
                stale.append(
                    {
                        "candidate_id": candidate.id,
                        "fingerprint": candidate.fingerprint,
                        "recorded_status": record.get("status"),
                        "reason": "evidence-file-digest-changed-or-missing",
                    }
                )
                continue
            candidate.status = record["status"]
    return stale


def derived_severity(impact: str, likelihood: str) -> str:
    matrix = {
        ("low", "low"): "low",
        ("low", "medium"): "low",
        ("low", "high"): "medium",
        ("medium", "low"): "low",
        ("medium", "medium"): "medium",
        ("medium", "high"): "high",
        ("high", "low"): "medium",
        ("high", "medium"): "high",
        ("high", "high"): "high",
        ("critical", "low"): "medium",
        ("critical", "medium"): "high",
        ("critical", "high"): "critical",
    }
    try:
        return matrix[(impact, likelihood)]
    except KeyError as error:
        raise TriageError(
            "impact must be low|medium|high|critical and likelihood must be low|medium|high"
        ) from error


def record_triage(
    *,
    workspace: Path,
    source_root: Path,
    candidate: dict[str, Any],
    status: str,
    note: str,
    evidence: list[str],
    verification: list[str],
    impact: str | None,
    likelihood: str | None,
    analyst: str | None,
) -> dict[str, Any]:
    if status not in TRIAGE_STATUSES:
        raise TriageError(f"unsupported status: {status}")
    if len(note.strip()) < 12:
        raise TriageError("triage note must explain the decision in at least 12 characters")

    evidence_rows = [source_evidence(value, source_root) for value in evidence]
    verification_rows = [value.strip() for value in verification if value.strip()]
    if status in {"confirmed", "rejected", "accepted-risk", "fixed"} and not evidence_rows:
        raise TriageError(f"{status} status requires at least one source evidence location")
    if status == "confirmed":
        if not verification_rows:
            raise TriageError(
                "confirmed status requires an independent verification or regression-test reference"
            )
        if not impact or not likelihood:
            raise TriageError("confirmed status requires explicit impact and likelihood")
    if status == "fixed" and (not evidence_rows or not verification_rows):
        raise TriageError("fixed status requires source evidence and a regression-test reference")

    severity = derived_severity(impact, likelihood) if impact and likelihood else None
    now = utc_now()
    record = {
        "candidate_id": candidate["id"],
        "fingerprint": candidate["fingerprint"],
        "status": status,
        "note": note.strip(),
        "evidence": evidence_rows,
        "verification": verification_rows,
        "impact": impact,
        "likelihood": likelihood,
        "severity": severity,
        "analyst": analyst,
        "source_digest": artifact_source_digest(workspace),
        "updated_at": now,
    }
    document = load_triage(workspace)
    previous = document["records"].get(candidate["fingerprint"])
    history_item = dict(record)
    if isinstance(previous, dict):
        history_item["previous_status"] = previous.get("status")
    document["records"][candidate["fingerprint"]] = record
    document["history"].append(history_item)
    write_json_atomic(workspace / TRIAGE_ARTIFACT, document)
    return record


def record_for_candidate(triage: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any] | None:
    record = triage.get("records", {}).get(candidate.get("fingerprint"))
    return record if isinstance(record, dict) else None
