from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .models import Candidate, Location, Route
from .util import normalize_code, path_is_within, redact_snippet, relative_path, stable_id


@dataclass
class SarifImport:
    candidates: list[Candidate]
    diagnostics: list[dict[str, Any]]


def _message(result: dict[str, Any]) -> str:
    message = result.get("message", {})
    if isinstance(message, dict):
        value = message.get("text") or message.get("markdown") or ""
    else:
        value = str(message)
    return redact_snippet(str(value), max_chars=1000)


def _severity(result: dict[str, Any]) -> str:
    properties = result.get("properties", {})
    score: float | None = None
    if isinstance(properties, dict):
        raw_score = properties.get("security-severity") or properties.get("security_severity")
        if isinstance(raw_score, (int, float, str)):
            with suppress(ValueError):
                score = float(raw_score)
    if score is not None:
        if score >= 9.0:
            return "critical"
        if score >= 7.0:
            return "high"
        if score >= 4.0:
            return "medium"
        if score > 0:
            return "low"
    return {
        "error": "high",
        "warning": "medium",
        "note": "low",
        "none": "info",
    }.get(str(result.get("level", "warning")).lower(), "medium")


def _resolve_uri(uri: str, source_root: Path) -> Path | None:
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        path = Path(unquote(parsed.path))
    elif parsed.scheme:
        return None
    else:
        path = Path(unquote(uri))
    resolved = path.resolve() if path.is_absolute() else (source_root / path).resolve()
    return resolved if path_is_within(resolved, source_root) else None


def _locations(
    result: dict[str, Any],
    source_root: Path,
    diagnostics: list[dict[str, Any]],
) -> list[Location]:
    locations: list[Location] = []
    for entry in result.get("locations", []):
        if not isinstance(entry, dict):
            continue
        physical = entry.get("physicalLocation", {})
        if not isinstance(physical, dict):
            continue
        artifact = physical.get("artifactLocation", {})
        region = physical.get("region", {})
        if not isinstance(artifact, dict) or not isinstance(region, dict):
            continue
        uri = artifact.get("uri")
        if not isinstance(uri, str):
            continue
        resolved = _resolve_uri(uri, source_root)
        if resolved is None:
            diagnostics.append({"kind": "location-outside-source-root", "uri": redact_snippet(uri)})
            continue
        locations.append(
            Location(
                path=relative_path(resolved, source_root),
                line=max(1, int(region.get("startLine", 1))),
                column=max(1, int(region.get("startColumn", 1))),
                end_line=int(region["endLine"]) if isinstance(region.get("endLine"), int) else None,
                snippet=(
                    redact_snippet(region["snippet"].get("text", ""))
                    if isinstance(region.get("snippet"), dict)
                    else None
                ),
            )
        )
    return locations


def _route_ids(routes: list[Route], location: Location) -> list[str]:
    local = [route for route in routes if route.location.path == location.path]
    if not local:
        return []
    preceding = [route for route in local if route.location.line <= location.line]
    if preceding:
        line = max(route.location.line for route in preceding)
        return sorted(route.id for route in preceding if route.location.line == line)
    return [local[0].id] if len(local) == 1 else []


def _rule_metadata(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tool = run.get("tool", {})
    driver = tool.get("driver", {}) if isinstance(tool, dict) else {}
    rules = driver.get("rules", []) if isinstance(driver, dict) else []
    metadata: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if isinstance(rule, dict) and isinstance(rule.get("id"), str):
            metadata[rule["id"]] = rule
    return metadata


def import_sarif(paths: list[Path], source_root: Path, routes: list[Route]) -> SarifImport:
    candidates: dict[str, Candidate] = {}
    diagnostics: list[dict[str, Any]] = []
    for path in paths:
        try:
            with path.open(encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            diagnostics.append(
                {
                    "kind": "sarif-read-error",
                    "path": str(path),
                    "error": error.__class__.__name__,
                }
            )
            continue
        if not isinstance(document, dict) or not isinstance(document.get("runs"), list):
            diagnostics.append({"kind": "invalid-sarif", "path": str(path)})
            continue

        for run in document["runs"]:
            if not isinstance(run, dict):
                continue
            tool = run.get("tool", {})
            driver = tool.get("driver", {}) if isinstance(tool, dict) else {}
            tool_name = str(driver.get("name", "sarif-tool")) if isinstance(driver, dict) else "sarif-tool"
            rules = _rule_metadata(run)
            for result in run.get("results", []):
                if not isinstance(result, dict):
                    continue
                locations = _locations(result, source_root, diagnostics)
                if not locations:
                    diagnostics.append(
                        {
                            "kind": "sarif-result-without-local-location",
                            "tool": tool_name,
                            "rule_id": result.get("ruleId"),
                        }
                    )
                    continue
                primary = locations[0]
                rule_id = str(result.get("ruleId") or "external-rule")
                rule = rules.get(rule_id, {})
                short = rule.get("shortDescription", {}) if isinstance(rule, dict) else {}
                full = rule.get("fullDescription", {}) if isinstance(rule, dict) else {}
                title = (short.get("text") if isinstance(short, dict) else None) or rule_id
                description = (full.get("text") if isinstance(full, dict) else None) or _message(result)
                partials = result.get("partialFingerprints", {})
                external_fingerprint = ""
                if isinstance(partials, dict) and partials:
                    external_fingerprint = "|".join(f"{key}={partials[key]}" for key in sorted(partials))
                message = _message(result)
                fingerprint = stable_id(
                    "fp",
                    "sarif",
                    tool_name,
                    rule_id,
                    external_fingerprint or f"{primary.path}:{normalize_code(message)}",
                    length=32,
                )
                candidate = Candidate(
                    id=stable_id("cand", fingerprint),
                    fingerprint=fingerprint,
                    rule_id=rule_id,
                    title=redact_snippet(str(title), max_chars=300),
                    description=redact_snippet(str(description), max_chars=1000),
                    severity=_severity(result),
                    confidence="medium",
                    cwe=str(
                        result.get("properties", {}).get("cwe", "CWE-unknown")
                        if isinstance(result.get("properties"), dict)
                        else "CWE-unknown"
                    ),
                    owasp="external-rule",
                    origin=f"sarif:{tool_name}",
                    kind="external-static-analysis",
                    status="needs-review",
                    primary_location=primary,
                    locations=locations,
                    route_ids=_route_ids(routes, primary),
                    source=None,
                    sink={
                        "kind": "external-analysis-result",
                        "tool": tool_name,
                        "rule_id": rule_id,
                        "location": primary.to_dict(),
                    },
                    controls=[],
                    trace=[
                        {
                            "step": "external-static-analysis",
                            "tool": tool_name,
                            "message": message,
                            "location": primary.to_dict(),
                        }
                    ],
                    tags=["sarif", tool_name.lower().replace(" ", "-")],
                    remediation="Follow the external rule guidance, then add a repository-local regression test.",
                    verification={
                        "mode": "source-derived-test-harness",
                        "questions": [
                            message,
                            "Does the external engine model the actual framework composition and sanitizer semantics?",
                        ],
                        "requirements": [
                            "Trace the complete local call path.",
                            "Reproduce the security boundary with a deterministic test and negative control.",
                        ],
                    },
                )
                candidates[candidate.id] = candidate
    return SarifImport(
        candidates=sorted(
            candidates.values(), key=lambda item: (item.primary_location.path, item.primary_location.line)
        ),
        diagnostics=diagnostics,
    )
