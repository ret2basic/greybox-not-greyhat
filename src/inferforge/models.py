from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SEVERITIES = ("info", "low", "medium", "high", "critical")
CONFIDENCES = ("low", "medium", "high")
TRIAGE_STATUSES = ("needs-review", "confirmed", "rejected", "accepted-risk", "fixed")


@dataclass(frozen=True)
class Location:
    path: str
    line: int
    column: int = 1
    end_line: int | None = None
    snippet: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class SourceFile:
    path: str
    language: str
    size: int
    sha256: str
    generated: bool = False
    manifest: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Route:
    id: str
    framework: str
    methods: list[str]
    path: str
    handler: str | None
    location: Location
    state_changing: bool
    dynamic_parameters: list[str] = field(default_factory=list)
    security_signals: list[str] = field(default_factory=list)
    source_kind: str = "declared-route"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["location"] = self.location.to_dict()
        return result


@dataclass
class Candidate:
    id: str
    fingerprint: str
    rule_id: str
    title: str
    description: str
    severity: str
    confidence: str
    cwe: str
    owasp: str
    origin: str
    kind: str
    status: str
    primary_location: Location
    locations: list[Location]
    route_ids: list[str]
    source: dict[str, Any] | None
    sink: dict[str, Any]
    controls: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    tags: list[str]
    remediation: str
    verification: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["primary_location"] = self.primary_location.to_dict()
        result["locations"] = [location.to_dict() for location in self.locations]
        return result


@dataclass
class ReviewTask:
    id: str
    kind: str
    title: str
    priority: str
    reason: str
    route_ids: list[str]
    candidate_ids: list[str]
    locations: list[Location]
    questions: list[str]
    completion_evidence: list[str]
    status: str = "open"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["locations"] = [location.to_dict() for location in self.locations]
        return result
