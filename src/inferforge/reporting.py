from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from .evidence import evidence_is_current
from .triage import load_triage, record_for_candidate
from .util import load_json, utc_now, write_json_atomic, write_text_atomic
from .workspace import load_artifact, require_valid_artifacts

REPORT_MANIFEST = "report-manifest.json"


def _remove_previous_generated_findings(output: Path) -> None:
    manifest_path = output / REPORT_MANIFEST
    if not manifest_path.is_file():
        return
    value = load_json(manifest_path)
    if not isinstance(value, dict) or not isinstance(value.get("files"), list):
        return
    for name in value["files"]:
        if not isinstance(name, str) or not re.fullmatch(r"cand-[0-9a-f]{16}\.md", name):
            continue
        path = output / name
        if path.is_file() and not path.is_symlink():
            path.unlink()


def _finding_markdown(candidate: dict[str, Any], record: dict[str, Any]) -> str:
    locations = candidate.get("locations", [])
    evidence_lines = [f"- {item.get('path')}:{item.get('line')}" for item in record.get("evidence", [])]
    source_lines = [
        f"- {item.get('path')}:{item.get('line')}" for item in locations if isinstance(item, dict)
    ]
    verification_lines = [f"- {item}" for item in record.get("verification", [])]
    control_lines = [
        f"- {control.get('location', {}).get('path')}:{control.get('location', {}).get('line')} "
        f"({control.get('effect')})"
        for control in candidate.get("controls", [])
    ] or ["- No nearby control signal was recorded; inspect the complete call path."]
    return "\n".join(
        [
            f"# {candidate.get('title')}",
            "",
            f"- Candidate ID: {candidate.get('id')}",
            f"- Rule: {candidate.get('rule_id')} ({candidate.get('cwe')})",
            f"- Impact: {record.get('impact')}",
            f"- Likelihood: {record.get('likelihood')}",
            f"- Severity: {record.get('severity')}",
            f"- Confirmed at: {record.get('updated_at')}",
            "",
            "## Summary",
            "",
            record.get("note", ""),
            "",
            "## Source path",
            "",
            *source_lines,
            "",
            "## Independent verification",
            "",
            *verification_lines,
            "",
            "## Confirmation evidence",
            "",
            *evidence_lines,
            "",
            "## Observed controls and negative checks",
            "",
            *control_lines,
            "",
            "## Remediation",
            "",
            candidate.get("remediation", ""),
            "",
            "## Scope and evidence caveat",
            "",
            "This report is generated only from an explicitly confirmed lifecycle record. Severity is derived "
            "from the recorded Impact and Likelihood fields. Re-check deployment reachability, version identity, "
            "and trust assumptions before external submission.",
        ]
    )


def generate_reports(workspace: Path, output_dir: Path | None = None) -> dict[str, Any]:
    require_valid_artifacts(workspace)
    output = output_dir or workspace / "reports"
    candidates = load_artifact(workspace, "candidates.json").get("candidates", [])
    inventory = load_artifact(workspace, "inventory.json")
    file_hashes = {
        item["path"]: item["sha256"]
        for item in inventory.get("files", [])
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and isinstance(item.get("sha256"), str)
    }
    triage = load_triage(workspace)
    confirmed: list[tuple[dict[str, Any], dict[str, Any]]] = []
    stale_confirmed: list[str] = []
    for candidate in candidates:
        record = record_for_candidate(triage, candidate)
        if record and record.get("status") == "confirmed":
            if evidence_is_current(record, file_hashes):
                confirmed.append((candidate, record))
            else:
                stale_confirmed.append(candidate["id"])

    output.mkdir(parents=True, exist_ok=True)
    _remove_previous_generated_findings(output)
    generated: list[str] = []
    for candidate, record in confirmed:
        path = output / f"{candidate['id']}.md"
        write_text_atomic(path, _finding_markdown(candidate, record))
        generated.append(path.name)

    severity_counts = Counter(record.get("severity") for _, record in confirmed)
    index_lines = [
        "# Confirmed InferForge findings",
        "",
        f"- Confirmed findings: {len(confirmed)}",
        f"- Stale confirmations withheld: {len(stale_confirmed)}",
        f"- Severity counts: {dict(sorted(severity_counts.items()))}",
        "",
    ]
    if confirmed:
        index_lines.extend(
            f"- [{candidate['id']}]({candidate['id']}.md): {candidate.get('title')}"
            for candidate, _ in confirmed
        )
    else:
        index_lines.append(
            "No candidate has satisfied the confirmation contract. Scanner candidates are intentionally not rendered "
            "as vulnerability reports."
        )
    write_text_atomic(output / "README.md", "\n".join(index_lines))
    generated.append("README.md")
    report_manifest = {
        "schema_version": 2,
        "generated_at": utc_now(),
        "source_digest": inventory.get("source_digest"),
        "confirmed_candidate_ids": [candidate["id"] for candidate, _ in confirmed],
        "stale_confirmed_withheld": stale_confirmed,
        "files": sorted(name for name in generated if re.fullmatch(r"cand-[0-9a-f]{16}\.md", name)),
    }
    write_json_atomic(output / REPORT_MANIFEST, report_manifest)
    generated.append(REPORT_MANIFEST)
    return {
        "output_dir": str(output),
        "confirmed": len(confirmed),
        "stale_confirmed_withheld": stale_confirmed,
        "severity_counts": dict(sorted(severity_counts.items())),
        "files": sorted(generated),
    }
