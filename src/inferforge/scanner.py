from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from . import __version__
from .analyzer import analyze_sources, candidates_artifact
from .config import ScanConfig
from .graph import build_evidence_graph
from .inventory import build_inventory
from .planning import build_coverage, build_review_tasks, review_plan_artifact
from .review_state import apply_review_state, load_review_state
from .routes import discover_routes, routes_artifact
from .rules import rule_catalog
from .sarif import import_sarif
from .signals import collect_signals
from .topology import build_topology
from .triage import apply_triage, load_triage
from .util import git_metadata, severity_rank, utc_now
from .workspace import write_artifact_set


def _scan_summary_markdown(
    config: ScanConfig,
    inventory_summary: dict[str, Any],
    routes_summary: dict[str, Any],
    candidates_summary: dict[str, Any],
    review_summary: dict[str, Any],
    sarif_diagnostics: list[dict[str, Any]],
) -> str:
    frameworks = (
        ", ".join(item["name"] for item in inventory_summary.get("frameworks", [])) or "none detected"
    )
    severity_counts = candidates_summary["summary"].get("severity_counts", {})
    lines = [
        "# InferForge white-box scan summary",
        "",
        f"- Generated: {utc_now()}",
        f"- Source identity: {inventory_summary['source_digest']}",
        f"- Inventory coverage: {inventory_summary['coverage_status']}",
        f"- Source files: {inventory_summary['summary']['source_files']}",
        f"- Frameworks: {frameworks}",
        f"- Routes: {routes_summary['summary']['routes']}",
        f"- Candidate hypotheses: {candidates_summary['summary']['candidates']}",
        f"- Candidate severities: {severity_counts}",
        f"- Open review tasks: {review_summary['summary']['tasks']}",
        f"- Imported-analysis diagnostics: {len(sarif_diagnostics)}",
        "",
        "## Interpretation",
        "",
        "Candidate hypotheses are not confirmed vulnerabilities. A missing security signal is a review gap, not "
        "proof that a control is absent. Confirmation requires a complete source trace, an independent local "
        "verification or regression test, a negative control, and explicit impact/likelihood triage.",
        "",
        "This run performed no remote discovery, HTTP probing, browser automation, Burp operation, process "
        "management, or target interaction.",
        "",
        "## Next step",
        "",
        "Start with review-plan.json, open one bounded task, use context to collect its source packet, and record "
        "the result with triage. coverage.json remains open until every relevant route lane has evidence.",
    ]
    return "\n".join(lines)


def run_scan(
    config: ScanConfig,
    *,
    sarif_paths: list[Path] | None = None,
) -> dict[str, Any]:
    inventory = build_inventory(config)
    routes = discover_routes(inventory)
    topology = build_topology(inventory, routes)
    native_candidates = analyze_sources(config, inventory, routes)
    sarif_import = import_sarif(sarif_paths or [], config.source_root, routes)

    merged = {candidate.id: candidate for candidate in native_candidates}
    for candidate in sarif_import.candidates:
        merged[candidate.id] = candidate
    candidates = sorted(
        merged.values(),
        key=lambda item: (
            -severity_rank(item.severity),
            item.primary_location.path,
            item.primary_location.line,
            item.rule_id,
        ),
    )
    file_hashes = {source_file.path: source_file.sha256 for source_file in inventory.files}
    for candidate in candidates:
        inherited_routes = topology.reachable_routes_by_file.get(candidate.primary_location.path, [])
        candidate.route_ids = sorted(set(candidate.route_ids).union(inherited_routes))
    triage = load_triage(config.workspace)
    stale_triage = apply_triage(candidates, triage, file_hashes)
    signals_doc = collect_signals(
        config,
        inventory,
        candidates,
        topology.reachable_routes_by_file,
    )
    tasks = build_review_tasks(routes, candidates, signals_doc["sinks"])
    review_state = load_review_state(config.workspace)
    stale_reviews = apply_review_state(tasks, review_state, file_hashes)

    inventory_doc = inventory.artifact()
    routes_doc = routes_artifact(routes, inventory.digest)
    candidates_doc = candidates_artifact(candidates, inventory.digest)
    coverage_doc = build_coverage(routes, candidates, inventory.digest, tasks)
    review_doc = review_plan_artifact(tasks, inventory.digest)
    graph_doc = build_evidence_graph(
        config,
        inventory,
        routes,
        candidates,
        tasks,
        topology=topology.artifact,
        signals=signals_doc,
    )
    run_doc = {
        "schema_version": 2,
        "inferforge_version": __version__,
        "generated_at": utc_now(),
        "source_digest": inventory.digest,
        "source_root": ".",
        "git": git_metadata(config.source_root),
        "mode": "source-required-whitebox",
        "network_activity": False,
        "active_probes": False,
        "sarif_inputs": [str(path) for path in sarif_paths or []],
        "sarif_diagnostics": sarif_import.diagnostics,
        "stale_triage_records": stale_triage,
        "stale_review_records": stale_reviews,
    }
    summary_doc = {
        "schema_version": 2,
        "source_digest": inventory.digest,
        "status": "complete-with-gaps" if inventory.coverage_status == "incomplete" else "complete",
        "counts": {
            "files": inventory_doc["summary"]["source_files"],
            "routes": routes_doc["summary"]["routes"],
            "candidates": candidates_doc["summary"]["candidates"],
            "review_tasks": review_doc["summary"]["tasks"],
        },
        "candidate_status_counts": dict(
            sorted(Counter(candidate.status for candidate in candidates).items())
        ),
        "candidate_severity_counts": candidates_doc["summary"]["severity_counts"],
        "coverage_status": inventory.coverage_status,
        "coverage_reasons": inventory.coverage_reasons,
        "stale_triage_records": stale_triage,
        "stale_review_records": stale_reviews,
        "semantics": {
            "scan_success_does_not_mean_application_safe": True,
            "candidate_count_does_not_equal_vulnerability_count": True,
            "blackbox_mode_available": False,
        },
    }

    summary_markdown = _scan_summary_markdown(
        config,
        inventory_doc,
        routes_doc,
        candidates_doc,
        review_doc,
        sarif_import.diagnostics,
    )
    manifest = write_artifact_set(
        config.workspace,
        source_digest=inventory.digest,
        json_artifacts={
            "run.json": run_doc,
            "effective-config.json": config.public_dict(),
            "inventory.json": inventory_doc,
            "routes.json": routes_doc,
            "topology.json": topology.artifact,
            "signals.json": signals_doc,
            "rule-catalog.json": rule_catalog(),
            "candidates.json": candidates_doc,
            "coverage.json": coverage_doc,
            "review-plan.json": review_doc,
            "evidence-graph.json": graph_doc,
            "scan-summary.json": summary_doc,
        },
        text_artifacts={"scan-summary.md": summary_markdown},
    )
    return {
        "workspace": str(config.workspace),
        "source_digest": inventory.digest,
        "summary": summary_doc,
        "manifest": manifest,
    }
