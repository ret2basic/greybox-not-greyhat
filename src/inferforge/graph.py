from __future__ import annotations

from typing import Any

from .config import ScanConfig
from .inventory import InventoryResult
from .models import Candidate, ReviewTask, Route
from .util import stable_id


def build_evidence_graph(
    config: ScanConfig,
    inventory: InventoryResult,
    routes: list[Route],
    candidates: list[Candidate],
    tasks: list[ReviewTask],
    *,
    topology: dict[str, Any] | None = None,
    signals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    file_ids: dict[str, str] = {}
    for source_file in inventory.files:
        if source_file.manifest:
            continue
        node_id = stable_id("file", source_file.path)
        file_ids[source_file.path] = node_id
        nodes.append(
            {
                "id": node_id,
                "type": "source-file",
                "label": source_file.path,
                "properties": {
                    "language": source_file.language,
                    "sha256": source_file.sha256,
                    "generated": source_file.generated,
                },
            }
        )

    for route in routes:
        nodes.append(
            {
                "id": route.id,
                "type": "route",
                "label": f"{'/'.join(route.methods)} {route.path}",
                "properties": {
                    "framework": route.framework,
                    "state_changing": route.state_changing,
                    "dynamic_parameters": route.dynamic_parameters,
                    "security_signals": route.security_signals,
                },
            }
        )
        file_id = file_ids.get(route.location.path)
        if file_id:
            edges.append(
                {
                    "id": stable_id("edge", route.id, "declared-in", file_id),
                    "from": route.id,
                    "to": file_id,
                    "type": "declared-in",
                    "evidence": route.location.to_dict(),
                }
            )

    if topology:
        for symbol in topology.get("symbols", []):
            nodes.append(
                {
                    "id": symbol["id"],
                    "type": "symbol",
                    "label": symbol["name"],
                    "properties": {
                        "path": symbol["path"],
                        "line": symbol["line"],
                    },
                }
            )
            file_id = file_ids.get(symbol["path"])
            if file_id:
                edges.append(
                    {
                        "id": stable_id("edge", symbol["id"], "defined-in", file_id),
                        "from": symbol["id"],
                        "to": file_id,
                        "type": "defined-in",
                    }
                )
        for item in topology.get("imports", []):
            source_id = file_ids.get(item["from"])
            target_id = file_ids.get(item["to"])
            if source_id and target_id:
                edges.append(
                    {
                        "id": stable_id("edge", source_id, "imports", target_id, item["line"]),
                        "from": source_id,
                        "to": target_id,
                        "type": "imports",
                        "evidence": {"path": item["from"], "line": item["line"]},
                    }
                )
        for item in topology.get("calls", []):
            edges.append(
                {
                    "id": item["id"],
                    "from": item["from"],
                    "to": item["to"],
                    "type": "may-call",
                    "evidence": {"path": item["path"], "line": item["line"]},
                }
            )
        for item in topology.get("route_symbol_edges", []):
            edges.append(
                {
                    "id": item["id"],
                    "from": item["from"],
                    "to": item["to"],
                    "type": item["type"],
                }
            )

    if signals:
        for kind, node_type in (("sources", "untrusted-source-signal"), ("sinks", "dangerous-sink-signal")):
            for signal in signals.get(kind, []):
                nodes.append(
                    {
                        "id": signal["id"],
                        "type": node_type,
                        "label": signal.get("title") or signal.get("label") or signal["id"],
                        "properties": {
                            key: signal[key]
                            for key in ("kind", "rule_id", "severity", "dataflow_status")
                            if key in signal
                        },
                    }
                )
                location = signal.get("location", {})
                file_id = file_ids.get(location.get("path"))
                if file_id:
                    edges.append(
                        {
                            "id": stable_id("edge", signal["id"], "observed-in", file_id),
                            "from": signal["id"],
                            "to": file_id,
                            "type": "observed-in",
                            "evidence": location,
                        }
                    )
                for route_id in signal.get("route_ids", []):
                    edges.append(
                        {
                            "id": stable_id("edge", route_id, "may-reach-signal", signal["id"]),
                            "from": route_id,
                            "to": signal["id"],
                            "type": "may-reach-signal",
                        }
                    )
                for candidate_id in signal.get("candidate_ids", []):
                    edges.append(
                        {
                            "id": stable_id("edge", signal["id"], "supports", candidate_id),
                            "from": signal["id"],
                            "to": candidate_id,
                            "type": "supports",
                        }
                    )

    for candidate in candidates:
        nodes.append(
            {
                "id": candidate.id,
                "type": "candidate",
                "label": f"{candidate.rule_id}: {candidate.title}",
                "properties": {
                    "severity": candidate.severity,
                    "confidence": candidate.confidence,
                    "status": candidate.status,
                    "origin": candidate.origin,
                    "tags": candidate.tags,
                },
            }
        )
        file_id = file_ids.get(candidate.primary_location.path)
        if file_id:
            edges.append(
                {
                    "id": stable_id("edge", candidate.id, "observed-in", file_id),
                    "from": candidate.id,
                    "to": file_id,
                    "type": "observed-in",
                    "evidence": candidate.primary_location.to_dict(),
                }
            )
        for route_id in candidate.route_ids:
            edges.append(
                {
                    "id": stable_id("edge", route_id, "may-reach", candidate.id),
                    "from": route_id,
                    "to": candidate.id,
                    "type": "may-reach",
                }
            )

    for task in tasks:
        nodes.append(
            {
                "id": task.id,
                "type": "review-task",
                "label": task.title,
                "properties": {
                    "kind": task.kind,
                    "priority": task.priority,
                    "status": task.status,
                },
            }
        )
        for route_id in task.route_ids:
            edges.append(
                {
                    "id": stable_id("edge", task.id, "reviews", route_id),
                    "from": task.id,
                    "to": route_id,
                    "type": "reviews",
                }
            )
        for candidate_id in task.candidate_ids:
            edges.append(
                {
                    "id": stable_id("edge", task.id, "verifies", candidate_id),
                    "from": task.id,
                    "to": candidate_id,
                    "type": "verifies",
                }
            )

    for boundary in config.trust_boundaries:
        boundary_id = stable_id("boundary", boundary["name"], boundary["pattern"])
        nodes.append(
            {
                "id": boundary_id,
                "type": "declared-trust-boundary",
                "label": boundary["name"],
                "properties": {"pattern": boundary["pattern"]},
            }
        )
        for path, file_id in file_ids.items():
            if boundary["pattern"] in path:
                edges.append(
                    {
                        "id": stable_id("edge", file_id, "crosses", boundary_id),
                        "from": file_id,
                        "to": boundary_id,
                        "type": "crosses",
                    }
                )

    return {
        "schema_version": 2,
        "source_digest": inventory.digest,
        "semantics": {
            "edges_represent_static_evidence_or_review_hypotheses": True,
            "may_reach_is_not_runtime_reachability_proof": True,
        },
        "summary": {
            "nodes": len(nodes),
            "edges": len(edges),
            "node_types": {
                kind: sum(node["type"] == kind for node in nodes)
                for kind in sorted({node["type"] for node in nodes})
            },
        },
        "nodes": sorted(nodes, key=lambda item: item["id"]),
        "edges": sorted(edges, key=lambda item: item["id"]),
    }
