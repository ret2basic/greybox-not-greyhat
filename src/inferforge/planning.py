from __future__ import annotations

from collections import Counter
from typing import Any

from .models import Candidate, Location, ReviewTask, Route
from .util import stable_id

PRIORITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def _candidate_task(candidate: Candidate) -> ReviewTask:
    return ReviewTask(
        id=stable_id("task", "candidate", candidate.id),
        kind="candidate-verification",
        title=f"Verify {candidate.rule_id}: {candidate.title}",
        priority=candidate.severity if candidate.severity in PRIORITY_RANK else "low",
        reason=(
            f"InferForge linked a {candidate.source.get('kind') if candidate.source else 'configuration'} "
            f"signal to {candidate.sink.get('kind', 'a sensitive operation')}. "
            "This is a hypothesis until the complete path and impact are independently reproduced."
        ),
        route_ids=list(candidate.route_ids),
        candidate_ids=[candidate.id],
        locations=list(candidate.locations),
        questions=list(candidate.verification.get("questions", [])),
        completion_evidence=list(candidate.verification.get("requirements", [])),
    )


def _gap_task(
    route: Route,
    *,
    kind: str,
    title: str,
    priority: str,
    reason: str,
    questions: list[str],
    completion_evidence: list[str],
) -> ReviewTask:
    return ReviewTask(
        id=stable_id("task", kind, route.id),
        kind=kind,
        title=title,
        priority=priority,
        reason=reason,
        route_ids=[route.id],
        candidate_ids=[],
        locations=[route.location],
        questions=questions,
        completion_evidence=completion_evidence,
    )


def build_review_tasks(
    routes: list[Route],
    candidates: list[Candidate],
    sink_signals: list[dict[str, Any]] | None = None,
) -> list[ReviewTask]:
    tasks: list[ReviewTask] = [
        _candidate_task(candidate) for candidate in candidates if candidate.status == "needs-review"
    ]
    for route in routes:
        methods = "/".join(route.methods)
        endpoint = f"{methods} {route.path}"
        signals = set(route.security_signals)

        if route.state_changing and "authentication" not in signals:
            tasks.append(
                _gap_task(
                    route,
                    kind="authentication-boundary-review",
                    title=f"Locate the authentication boundary for {endpoint}",
                    priority="high",
                    reason=(
                        "No authentication signal was observed in the declaring file. Authentication may live in "
                        "middleware; static absence is a coverage gap, not proof of a vulnerability."
                    ),
                    questions=[
                        "Which middleware or framework guard establishes the principal?",
                        "Can the route be reached through an alternate mount, rewrite, or internal call without that guard?",
                    ],
                    completion_evidence=[
                        "Source location for the effective authentication guard.",
                        "A local unauthenticated negative test covering the actual route composition.",
                    ],
                )
            )

        if route.state_changing and "authorization" not in signals:
            tasks.append(
                _gap_task(
                    route,
                    kind="authorization-boundary-review",
                    title=f"Prove object and action authorization for {endpoint}",
                    priority="high",
                    reason=(
                        "The route mutates state and no authorization signal was observed in its declaring file. "
                        "Trace service and persistence layers before concluding."
                    ),
                    questions=[
                        "Where is the actor bound to the affected tenant, owner, role, or resource?",
                        "Is the check made on the server-loaded object rather than a request-supplied owner field?",
                    ],
                    completion_evidence=[
                        "Source trace from authenticated principal to the authorization predicate.",
                        "Cross-user or cross-tenant negative test using two isolated fixtures.",
                    ],
                )
            )

        if route.dynamic_parameters:
            tasks.append(
                _gap_task(
                    route,
                    kind="object-scope-review",
                    title=f"Review dynamic object scope for {endpoint}",
                    priority="high" if route.state_changing else "medium",
                    reason=f"Dynamic parameters {route.dynamic_parameters!r} select a resource at this boundary.",
                    questions=[
                        "Can one principal substitute another principal's identifier?",
                        "Does every downstream load/update include tenant or ownership scope?",
                        "Are bulk, export, nested, and error paths governed by the same predicate?",
                    ],
                    completion_evidence=[
                        "The scoped repository/query predicate.",
                        "A two-principal negative regression test.",
                    ],
                )
            )

        lowered_path = route.path.lower()
        if (
            any(token in lowered_path for token in ("webhook", "callback", "hook"))
            and "signature" not in signals
        ):
            tasks.append(
                _gap_task(
                    route,
                    kind="webhook-integrity-review",
                    title=f"Prove authenticity and replay controls for {endpoint}",
                    priority="high",
                    reason="The route name suggests an externally triggered callback, but no signature signal was observed.",
                    questions=[
                        "Is the raw request body authenticated before parsing or mutation?",
                        "Are timestamp, nonce, event identity, and replay windows enforced transactionally?",
                    ],
                    completion_evidence=[
                        "Source trace for signature verification and replay storage.",
                        "Invalid-signature and duplicate-event negative tests.",
                    ],
                )
            )

        if any(token in lowered_path for token in ("upload", "import", "attachment", "avatar")):
            tasks.append(
                _gap_task(
                    route,
                    kind="file-boundary-review",
                    title=f"Review file trust boundaries for {endpoint}",
                    priority="high",
                    reason="The route name suggests file ingestion or storage.",
                    questions=[
                        "Are size, type, extension, archive expansion, filename, and storage destination enforced server-side?",
                        "Can uploaded content become executable, same-origin active content, or a parser input?",
                    ],
                    completion_evidence=[
                        "Source trace from multipart/parser input to final storage and serving policy.",
                        "Negative tests for traversal, oversize, mismatched type, and archive expansion.",
                    ],
                )
            )

        if "admin" in lowered_path and "authorization" not in signals:
            tasks.append(
                _gap_task(
                    route,
                    kind="privileged-route-review",
                    title=f"Locate the privileged role guard for {endpoint}",
                    priority="critical",
                    reason="An admin-like route lacks a nearby authorization signal.",
                    questions=[
                        "Which exact role/capability is required?",
                        "Is the guard applied to every method, alias, batch endpoint, and internal invocation?",
                    ],
                    completion_evidence=[
                        "Source location of the role or capability check.",
                        "Authenticated non-admin negative regression test.",
                    ],
                )
            )

        tasks.append(
            _gap_task(
                route,
                kind="route-threat-model-review",
                title=f"Complete a source threat model for {endpoint}",
                priority="medium" if route.state_changing else "low",
                reason=(
                    "Every source entrypoint needs business-logic and indirect-call review. Native candidates cover "
                    "only modeled source-to-sink patterns and cannot establish route safety."
                ),
                questions=[
                    "What assets and trust boundaries does this route cross?",
                    "Which service, persistence, queue, template, filesystem, or outbound-call paths are reachable?",
                    "What invariant should a negative regression test preserve?",
                ],
                completion_evidence=[
                    "A call-path note with source locations.",
                    "At least one abuse-case test or a documented not-applicable rationale per relevant lane.",
                ],
            )
        )

    for sink in sink_signals or []:
        if sink.get("dataflow_status") != "unresolved-input-origin":
            continue
        if not sink.get("route_ids"):
            continue
        location = sink.get("location", {})
        if not isinstance(location, dict) or not isinstance(location.get("path"), str):
            continue
        raw_priority = sink.get("severity")
        priority = (
            raw_priority if isinstance(raw_priority, str) and raw_priority in PRIORITY_RANK else "medium"
        )
        tasks.append(
            ReviewTask(
                id=stable_id("task", "sink-callpath", sink.get("id")),
                kind="sink-callpath-review",
                title=f"Trace inputs to {sink.get('rule_id')} sink at {location.get('path')}:{location.get('line')}",
                priority=priority,
                reason=(
                    "A dangerous operation exists in source, but the bounded native analysis did not prove a local "
                    "attacker-controlled source-to-sink flow. Trace callers, dependency injection, dynamic dispatch, "
                    "and framework binding before classifying it."
                ),
                route_ids=list(sink.get("route_ids", [])),
                candidate_ids=[],
                locations=[
                    Location(
                        path=location["path"],
                        line=int(location.get("line", 1)),
                        snippet=location.get("snippet"),
                    )
                ],
                questions=list(sink.get("verification_questions", [])),
                completion_evidence=[
                    "A caller-to-sink source trace or a documented proof that every input is server-owned.",
                    "A focused regression test when an untrusted path exists.",
                    "A negative control demonstrating the intended validation or invariant.",
                ],
            )
        )

    unique = {task.id: task for task in tasks}
    return sorted(
        unique.values(),
        key=lambda task: (
            -PRIORITY_RANK.get(task.priority, 0),
            task.kind,
            task.title,
        ),
    )


def build_coverage(
    routes: list[Route],
    candidates: list[Candidate],
    source_digest: str,
    tasks: list[ReviewTask] | None = None,
) -> dict[str, Any]:
    candidates_by_route: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        for route_id in candidate.route_ids:
            candidates_by_route.setdefault(route_id, []).append(candidate)

    route_rows: list[dict[str, Any]] = []
    tasks_by_route: dict[str, list[ReviewTask]] = {}
    for task in tasks or []:
        for route_id in task.route_ids:
            tasks_by_route.setdefault(route_id, []).append(task)
    for route in routes:
        signals = set(route.security_signals)
        linked = candidates_by_route.get(route.id, [])
        lanes = {
            "authentication": "signal-present" if "authentication" in signals else "review-required",
            "authorization": "signal-present" if "authorization" in signals else "review-required",
            "input-validation": "signal-present" if "validation" in signals else "review-required",
            "request-integrity": (
                "signal-present"
                if {"csrf", "signature"}.intersection(signals)
                else ("review-required" if route.state_changing else "not-applicable-by-method")
            ),
            "abuse-controls": "signal-present" if "rate-limit" in signals else "review-required",
            "dangerous-dataflow": "candidate-present" if linked else "no-native-candidate",
        }
        route_tasks = tasks_by_route.get(route.id, [])
        open_task_ids = [task.id for task in route_tasks if task.status == "open"]
        route_rows.append(
            {
                "route_id": route.id,
                "endpoint": f"{'/'.join(route.methods)} {route.path}",
                "location": route.location.to_dict(),
                "lanes": lanes,
                "candidate_ids": [candidate.id for candidate in linked],
                "task_ids": [task.id for task in route_tasks],
                "open_task_ids": open_task_ids,
                "closure": "open" if open_task_ids or not route_tasks else "evidence-closed",
                "semantics": "missing signals are review gaps, not vulnerability claims",
            }
        )

    lane_counts = Counter(status for row in route_rows for status in row["lanes"].values())
    return {
        "schema_version": 2,
        "source_digest": source_digest,
        "semantics": {
            "route_coverage_is_open_until_human_or_agent_evidence_closes_each_relevant_lane": True,
            "no_native_candidate_does_not_mean_safe": True,
        },
        "summary": {
            "routes": len(route_rows),
            "open_routes": sum(row["closure"] == "open" for row in route_rows),
            "evidence_closed_routes": sum(row["closure"] == "evidence-closed" for row in route_rows),
            "lane_status_counts": dict(sorted(lane_counts.items())),
        },
        "routes": route_rows,
    }


def review_plan_artifact(tasks: list[ReviewTask], source_digest: str) -> dict[str, Any]:
    priority_counts = Counter(task.priority for task in tasks)
    kind_counts = Counter(task.kind for task in tasks)
    status_counts = Counter(task.status for task in tasks)
    return {
        "schema_version": 2,
        "source_digest": source_digest,
        "semantics": {
            "tasks_are_source-derived_review_work": True,
            "remote_blackbox_discovery_tasks": False,
        },
        "summary": {
            "tasks": len(tasks),
            "priority_counts": dict(sorted(priority_counts.items())),
            "kind_counts": dict(sorted(kind_counts.items())),
            "status_counts": dict(sorted(status_counts.items())),
        },
        "tasks": [task.to_dict() for task in tasks],
    }
