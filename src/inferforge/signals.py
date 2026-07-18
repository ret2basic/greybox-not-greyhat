from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .config import ScanConfig
from .inventory import InventoryResult
from .lexing import mask_non_code
from .models import Candidate
from .rules import FLOW_RULES, SOURCE_PATTERNS
from .util import redact_snippet, stable_id


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _signal_applicable(
    rule_id: str,
    language: str,
    masked: str,
    match: re.Match[str],
    route_ids: list[str],
) -> bool:
    start = max(0, match.start() - 80)
    end = min(len(masked), match.end() + 160)
    fragment = masked[start:end]
    matched = masked[match.start() : match.end()]
    if rule_id == "IFW008":
        if language == "python":
            previous = masked[match.start() - 1] if match.start() else ""
            return bool(
                (previous not in (".", "_") and re.search(r"\b(?:eval|exec|compile)\s*\(", matched))
                or "ScriptEngine" in fragment
            )
        return bool(
            re.search(r"(?<![\w.])eval\s*\(|\bnew\s+Function\s*\(", fragment) or "ScriptEngine" in fragment
        )
    if rule_id == "IFW010":
        return bool(re.search(r"\b(?:ldap|LdapTemplate|search_s|search_ext)\b", fragment, re.IGNORECASE))
    if rule_id == "IFW013":
        return bool(route_ids)
    return True


def collect_signals(
    config: ScanConfig,
    inventory: InventoryResult,
    candidates: list[Candidate],
    reachable_routes_by_file: dict[str, list[str]],
) -> dict[str, Any]:
    file_by_path = {file.path: file for file in inventory.files}
    candidate_index: dict[tuple[str, int, str], list[str]] = {}
    for candidate in candidates:
        key = (
            candidate.primary_location.path,
            candidate.primary_location.line,
            candidate.rule_id,
        )
        candidate_index.setdefault(key, []).append(candidate.id)

    sources: list[dict[str, Any]] = []
    sinks: list[dict[str, Any]] = []
    for path, text in inventory.texts.items():
        source_file = file_by_path[path]
        if source_file.manifest or source_file.generated:
            continue
        masked = mask_non_code(text, source_file.language)
        lines = text.splitlines()
        for source_pattern in SOURCE_PATTERNS:
            for match in list(re.finditer(source_pattern.pattern, masked, re.IGNORECASE | re.MULTILINE))[
                :500
            ]:
                line = _line_number(text, match.start())
                snippet = lines[line - 1] if lines else ""
                sources.append(
                    {
                        "id": stable_id("source", path, line, source_pattern.kind, match.group(0)),
                        "kind": source_pattern.kind,
                        "label": source_pattern.label,
                        "location": {
                            "path": path,
                            "line": line,
                            "snippet": redact_snippet(snippet.strip()),
                        },
                        "route_ids": reachable_routes_by_file.get(path, []),
                    }
                )
        for rule in FLOW_RULES:
            if rule.id in config.disabled_rules:
                continue
            for pattern in rule.sink_patterns:
                for match in list(re.finditer(pattern, masked, re.IGNORECASE | re.MULTILINE))[:500]:
                    line = _line_number(text, match.start())
                    snippet = lines[line - 1] if lines else ""
                    key = (path, line, rule.id)
                    route_ids = reachable_routes_by_file.get(path, [])
                    if not _signal_applicable(
                        rule.id,
                        source_file.language,
                        masked,
                        match,
                        route_ids,
                    ):
                        continue
                    sinks.append(
                        {
                            "id": stable_id("sink", path, line, rule.id, match.group(0)),
                            "rule_id": rule.id,
                            "title": rule.title,
                            "severity": config.severity_overrides.get(rule.id, rule.severity),
                            "cwe": rule.cwe,
                            "location": {
                                "path": path,
                                "line": line,
                                "snippet": redact_snippet(snippet.strip()),
                            },
                            "route_ids": route_ids,
                            "candidate_ids": candidate_index.get(key, []),
                            "dataflow_status": "linked-candidate"
                            if key in candidate_index
                            else "unresolved-input-origin",
                            "verification_questions": list(rule.verification_questions),
                        }
                    )

    unique_sources = {item["id"]: item for item in sources}
    unique_sinks = {item["id"]: item for item in sinks}
    sink_status_counts = Counter(item["dataflow_status"] for item in unique_sinks.values())
    return {
        "schema_version": 2,
        "source_digest": inventory.digest,
        "semantics": {
            "sink_without_candidate_is_a_callpath_review_gap": True,
            "sink_presence_alone_is_not_a_vulnerability": True,
        },
        "summary": {
            "sources": len(unique_sources),
            "sinks": len(unique_sinks),
            "sink_status_counts": dict(sorted(sink_status_counts.items())),
        },
        "sources": sorted(unique_sources.values(), key=lambda item: item["id"]),
        "sinks": sorted(unique_sinks.values(), key=lambda item: item["id"]),
    }
