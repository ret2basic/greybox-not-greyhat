from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .config import ScanConfig
from .inventory import InventoryResult
from .lexing import mask_non_code, match_starts_in_code
from .models import Candidate, Location, Route
from .rules import FLOW_RULES, SOURCE_PATTERNS, STATIC_RULES, FlowRule, SourcePattern, StaticRule
from .util import normalize_code, redact_snippet, stable_id

MAX_FLOW_DISTANCE = 220


@dataclass
class Taint:
    variable: str
    kind: str
    label: str
    line: int
    expression: str
    parent: str | None = None

    def source_dict(self, path: str) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "variable": self.variable,
            "location": {
                "path": path,
                "line": self.line,
                "snippet": redact_snippet(self.expression),
            },
        }


ASSIGNMENT_PATTERNS = (
    re.compile(
        r"^\s*(?:(?:const|let|var|final|var|String|Object|Map|List|def|auto)\s+)?"
        r"(?P<lhs>[$A-Za-z_][\w$]*)\s*(?::[^=]+)?\s*(?::=|=(?!=))\s*(?P<rhs>.+?)\s*;?\s*$"
    ),
    re.compile(r"^\s*(?P<lhs>\$[A-Za-z_]\w*)\s*=\s*(?P<rhs>.+?)\s*;?\s*$"),
)

DESTRUCTURE_PATTERN = re.compile(
    r"^\s*(?:(?:const|let|var)\s+)?[\{\[](?P<names>[^\}\]]+)[\}\]]\s*=\s*(?P<rhs>.+?)\s*;?\s*$"
)

PYTHON_DEF_PATTERN = re.compile(r"^\s*(?:async\s+)?def\s+[A-Za-z_]\w*\s*\((?P<args>[^)]*)\)")

SANITIZER_PATTERNS = (
    r"\bsanitize",
    r"\bescape",
    r"\bvalidate",
    r"\bschema\.(?:parse|safeparse)",
    r"\bparse_url\b",
    r"\bsecure_filename\b",
)


def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _source_hit(value: str, patterns: Iterable[SourcePattern] = SOURCE_PATTERNS) -> SourcePattern | None:
    for source in patterns:
        if re.search(source.pattern, value, re.IGNORECASE):
            return source
    return None


def _variable_names(value: str) -> set[str]:
    return set(re.findall(r"(?<![\w$])[$A-Za-z_][\w$]*(?![\w$])", value))


def _assignment(line: str) -> tuple[list[str], str] | None:
    destructured = DESTRUCTURE_PATTERN.match(line)
    if destructured:
        names: list[str] = []
        for item in destructured.group("names").split(","):
            name = item.strip().split(":", 1)[0].strip()
            name = re.sub(r"^\.\.\.", "", name)
            if re.fullmatch(r"[$A-Za-z_][\w$]*", name):
                names.append(name)
        return (names, destructured.group("rhs")) if names else None
    for pattern in ASSIGNMENT_PATTERNS:
        match = pattern.match(line)
        if match:
            return [match.group("lhs")], match.group("rhs")
    return None


def _route_parameter_taints(path: str, lines: list[str], routes: list[Route]) -> list[Taint]:
    taints: list[Taint] = []
    for route in routes:
        if route.location.path != path or route.framework not in {"fastapi", "flask"}:
            continue
        start = max(route.location.line, 1)
        for line_number in range(start, min(start + 8, len(lines)) + 1):
            match = PYTHON_DEF_PATTERN.match(lines[line_number - 1])
            if not match:
                continue
            for raw in match.group("args").split(","):
                part = raw.strip()
                if not part or "Depends(" in part:
                    continue
                name = re.split(r"[:=]", part, maxsplit=1)[0].strip()
                if name in {"self", "cls", "request", "response"} or not re.fullmatch(r"[A-Za-z_]\w*", name):
                    continue
                taints.append(
                    Taint(
                        variable=name,
                        kind="request-input",
                        label="framework-bound route parameter",
                        line=line_number,
                        expression=lines[line_number - 1],
                    )
                )
            break
    return taints


def _collect_taints(
    path: str,
    text: str,
    masked: str,
    routes: list[Route],
) -> dict[str, list[Taint]]:
    lines = text.splitlines()
    masked_lines = masked.splitlines()
    taints: dict[str, list[Taint]] = {}
    assignments: list[tuple[int, list[str], str, str]] = []

    for line_number, masked_line in enumerate(masked_lines, start=1):
        line = lines[line_number - 1]
        parsed = _assignment(masked_line)
        if parsed:
            names, rhs = parsed
            assignments.append((line_number, names, rhs, line))
            source = _source_hit(rhs)
            if source:
                for name in names:
                    taints.setdefault(name, []).append(
                        Taint(
                            variable=name,
                            kind=source.kind,
                            label=source.label,
                            line=line_number,
                            expression=line,
                        )
                    )

    for taint in _route_parameter_taints(path, lines, routes):
        taints.setdefault(taint.variable, []).append(taint)

    for _ in range(8):
        changed = False
        for line_number, names, rhs, line in assignments:
            referenced = _variable_names(rhs)
            parent_taints = [
                taint
                for variable in referenced
                for taint in taints.get(variable, [])
                if taint.line <= line_number
            ]
            if not parent_taints:
                continue
            parent = max(parent_taints, key=lambda item: item.line)
            for name in names:
                existing = taints.setdefault(name, [])
                marker = (line_number, parent.kind, parent.variable)
                if any((item.line, item.kind, item.parent) == marker for item in existing):
                    continue
                existing.append(
                    Taint(
                        variable=name,
                        kind=parent.kind,
                        label=parent.label,
                        line=line_number,
                        expression=line,
                        parent=parent.variable,
                    )
                )
                changed = True
        if not changed:
            break
    return taints


def _statement_window(lines: list[str], line_number: int, *, before: int = 2, after: int = 4) -> str:
    start = max(0, line_number - 1 - before)
    end = min(len(lines), line_number + after)
    return "\n".join(lines[start:end])


def _comment_only(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("//", "#", "/*", "*"))


def _nearest_taint(
    fragment: str,
    sink_line: int,
    taints: dict[str, list[Taint]],
    allowed_kinds: tuple[str, ...],
) -> Taint | None:
    candidates: list[Taint] = []
    variables = _variable_names(fragment)
    for variable in variables:
        for taint in taints.get(variable, []):
            if (
                taint.kind in allowed_kinds
                and taint.line <= sink_line
                and sink_line - taint.line <= MAX_FLOW_DISTANCE
            ):
                candidates.append(taint)
    return max(candidates, key=lambda item: item.line) if candidates else None


def _direct_source(fragment: str, sink_line: int, allowed_kinds: tuple[str, ...]) -> Taint | None:
    for source in SOURCE_PATTERNS:
        if source.kind in allowed_kinds and re.search(source.pattern, fragment, re.IGNORECASE):
            return Taint(
                variable="<direct-expression>",
                kind=source.kind,
                label=source.label,
                line=sink_line,
                expression=fragment,
            )
    return None


def _controls_for_flow(
    rule: FlowRule,
    lines: list[str],
    masked_lines: list[str],
    source_line: int,
    sink_line: int,
    path: str,
) -> list[dict[str, Any]]:
    start = max(1, min(source_line, sink_line) - 8)
    end = min(len(lines), max(source_line, sink_line) + 8)
    controls: list[dict[str, Any]] = []
    patterns = (*rule.control_patterns, *SANITIZER_PATTERNS)
    for line_number in range(start, end + 1):
        line = lines[line_number - 1]
        searchable_line = masked_lines[line_number - 1]
        for pattern in patterns:
            if re.search(pattern, searchable_line, re.IGNORECASE):
                controls.append(
                    {
                        "pattern": pattern,
                        "location": {
                            "path": path,
                            "line": line_number,
                            "snippet": redact_snippet(line.strip()),
                        },
                        "effect": "review-required",
                    }
                )
                break
    return controls[:12]


def _routes_for_sink(routes: list[Route], path: str, sink_line: int) -> list[str]:
    local = [route for route in routes if route.location.path == path]
    if not local:
        return []
    preceding = [route for route in local if route.location.line <= sink_line]
    if preceding:
        nearest_line = max(route.location.line for route in preceding)
        selected = [route for route in preceding if route.location.line == nearest_line]
    elif len(local) == 1:
        selected = local
    else:
        selected = []
    return sorted(route.id for route in selected)


def _confidence_for_flow(source: Taint, controls: list[dict[str, Any]], fragment: str) -> str:
    confidence = "high" if source.variable == "<direct-expression>" or source.parent is None else "medium"
    if controls:
        confidence = "medium" if confidence == "high" else "low"
    if "\n" in fragment and len(fragment) > 800:
        confidence = "low"
    return confidence


def _rule_applicable_to_language(rule: FlowRule, language: str, fragment: str) -> bool:
    if rule.id == "IFW001" and language == "python":
        return bool(re.search(r"\b(?:os\.(?:system|popen)|subprocess\.)", fragment))
    if rule.id == "IFW008" and language in {"javascript", "typescript"}:
        return bool(re.search(r"(?<![\w.])eval\s*\(|\bnew\s+Function\s*\(", fragment))
    if rule.id == "IFW008" and language == "python":
        return bool(re.search(r"(?<![\w.])(?:eval|exec|compile)\s*\(", fragment))
    if rule.id == "IFW010":
        return bool(re.search(r"\b(?:ldap|LdapTemplate|search_s|search_ext)\b", fragment, re.IGNORECASE))
    return True


def _candidate_from_flow(
    config: ScanConfig,
    rule: FlowRule,
    path: str,
    text: str,
    masked: str,
    language: str,
    match: re.Match[str],
    taints: dict[str, list[Taint]],
    routes: list[Route],
) -> Candidate | None:
    lines = text.splitlines()
    masked_lines = masked.splitlines()
    sink_line = _line_for_offset(text, match.start())
    line = lines[sink_line - 1] if lines else ""
    if _comment_only(line):
        return None
    masked_fragment = _statement_window(masked_lines, sink_line)
    if not _rule_applicable_to_language(rule, language, masked_fragment):
        return None

    source = _direct_source(masked_fragment, sink_line, rule.source_kinds)
    if source is None:
        source = _nearest_taint(masked_fragment, sink_line, taints, rule.source_kinds)
    if source is None:
        return None

    controls = _controls_for_flow(rule, lines, masked_lines, source.line, sink_line, path)
    normalized_sink = normalize_code(line or match.group(0))
    fingerprint = stable_id("fp", rule.id, path, normalized_sink, source.kind, length=32)
    candidate_id = stable_id("cand", fingerprint)
    source_location = Location(
        path,
        source.line,
        snippet=redact_snippet(source.expression.strip()),
    )
    sink_location = Location(path, sink_line, snippet=redact_snippet(line.strip()))
    trace = [
        {
            "step": "source",
            "kind": source.kind,
            "variable": source.variable,
            "location": source_location.to_dict(),
        }
    ]
    if source.parent:
        trace.append({"step": "propagation", "from": source.parent, "to": source.variable})
    trace.append(
        {
            "step": "sink",
            "rule_id": rule.id,
            "location": sink_location.to_dict(),
        }
    )
    severity = config.severity_overrides.get(rule.id, rule.severity)
    return Candidate(
        id=candidate_id,
        fingerprint=fingerprint,
        rule_id=rule.id,
        title=rule.title,
        description=rule.description,
        severity=severity,
        confidence=_confidence_for_flow(source, controls, masked_fragment),
        cwe=rule.cwe,
        owasp=rule.owasp,
        origin="inferforge-native",
        kind="source-to-sink",
        status="needs-review",
        primary_location=sink_location,
        locations=[source_location, sink_location],
        route_ids=_routes_for_sink(routes, path, sink_line),
        source=source.source_dict(path),
        sink={
            "kind": "dangerous-operation",
            "pattern": match.group(0),
            "location": sink_location.to_dict(),
        },
        controls=controls,
        trace=trace,
        tags=list(rule.tags),
        remediation=rule.remediation,
        verification={
            "mode": "source-derived-test-harness",
            "questions": list(rule.verification_questions),
            "requirements": [
                "Trace the complete call path and prove attacker control.",
                "Add a minimal local regression test or deterministic harness.",
                "Record a negative control and the observable security impact.",
            ],
        },
    )


def _static_match_candidate(
    config: ScanConfig,
    rule: StaticRule,
    path: str,
    text: str,
    match: re.Match[str],
    routes: list[Route],
) -> Candidate | None:
    line_number = _line_for_offset(text, match.start())
    lines = text.splitlines()
    line = lines[line_number - 1] if lines else ""
    if _comment_only(line):
        return None
    normalized = normalize_code(line or match.group(0))
    fingerprint = stable_id("fp", rule.id, path, normalized, length=32)
    location = Location(path, line_number, snippet=redact_snippet(line.strip()))
    severity = config.severity_overrides.get(rule.id, rule.severity)
    return Candidate(
        id=stable_id("cand", fingerprint),
        fingerprint=fingerprint,
        rule_id=rule.id,
        title=rule.title,
        description=rule.description,
        severity=severity,
        confidence=rule.confidence,
        cwe=rule.cwe,
        owasp=rule.owasp,
        origin="inferforge-native",
        kind="unsafe-configuration",
        status="needs-review",
        primary_location=location,
        locations=[location],
        route_ids=_routes_for_sink(routes, path, line_number),
        source=None,
        sink={
            "kind": "configuration",
            "pattern": "<redacted-match>" if rule.id == "IFC006" else redact_snippet(match.group(0)),
            "location": location.to_dict(),
        },
        controls=[],
        trace=[{"step": "configuration-signal", "rule_id": rule.id, "location": location.to_dict()}],
        tags=list(rule.tags),
        remediation=rule.remediation,
        verification={
            "mode": "source-and-runtime-configuration-review",
            "questions": list(rule.verification_questions),
            "requirements": [
                "Prove the configuration is selected in a production-capable path.",
                "Add a regression assertion for the secure setting.",
            ],
        },
    )


def analyze_sources(
    config: ScanConfig,
    inventory: InventoryResult,
    routes: list[Route],
) -> list[Candidate]:
    file_by_path = {file.path: file for file in inventory.files}
    candidates: dict[str, Candidate] = {}

    for path, text in inventory.texts.items():
        source_file = file_by_path[path]
        if source_file.manifest or source_file.generated:
            continue
        masked = mask_non_code(text, source_file.language)
        taints = _collect_taints(path, text, masked, routes)

        for rule in FLOW_RULES:
            if rule.id in config.disabled_rules:
                continue
            for pattern in rule.sink_patterns:
                for match in re.finditer(pattern, masked, re.IGNORECASE | re.MULTILINE):
                    candidate = _candidate_from_flow(
                        config,
                        rule,
                        path,
                        text,
                        masked,
                        source_file.language,
                        match,
                        taints,
                        routes,
                    )
                    if candidate:
                        candidates[candidate.id] = candidate

        for rule in STATIC_RULES:
            if rule.id in config.disabled_rules:
                continue
            for pattern in rule.patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                    if not match_starts_in_code(masked, match.start()):
                        continue
                    candidate = _static_match_candidate(config, rule, path, text, match, routes)
                    if candidate:
                        candidates[candidate.id] = candidate

    return sorted(
        candidates.values(),
        key=lambda item: (
            -{"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}[item.severity],
            -{"high": 2, "medium": 1, "low": 0}[item.confidence],
            item.primary_location.path,
            item.primary_location.line,
            item.rule_id,
        ),
    )


def candidates_artifact(candidates: list[Candidate], source_digest: str) -> dict[str, Any]:
    severity_counts: dict[str, int] = {}
    rule_counts: dict[str, int] = {}
    for candidate in candidates:
        severity_counts[candidate.severity] = severity_counts.get(candidate.severity, 0) + 1
        rule_counts[candidate.rule_id] = rule_counts.get(candidate.rule_id, 0) + 1
    return {
        "schema_version": 2,
        "source_digest": source_digest,
        "semantics": {
            "items_are_candidates_not_confirmed_vulnerabilities": True,
            "confirmation_requires_triage_and_independent_verification": True,
        },
        "summary": {
            "candidates": len(candidates),
            "severity_counts": dict(sorted(severity_counts.items())),
            "rule_counts": dict(sorted(rule_counts.items())),
        },
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
