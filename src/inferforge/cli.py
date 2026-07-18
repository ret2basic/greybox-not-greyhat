from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .config import resolve_config, starter_config
from .context import render_context
from .doctor import run_doctor
from .errors import InferForgeError
from .inventory import build_inventory
from .reporting import generate_reports
from .review_state import load_review_state, record_review
from .rules import rule_catalog
from .scanner import run_scan
from .triage import load_triage, record_triage
from .util import severity_rank, write_json_atomic, write_text_atomic
from .workspace import load_artifact, verify_artifacts


def _add_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source-root",
        default=".",
        help="Local source-code root. InferForge has no remote-target or source-free mode.",
    )
    parser.add_argument(
        "--workspace",
        help="Artifact directory. Defaults to SOURCE_ROOT/.inferforge.",
    )
    parser.add_argument(
        "--config",
        help="JSON configuration path. Defaults to SOURCE_ROOT/inferforge.json when present.",
    )


def _print(value: Any, *, as_json: bool = False) -> None:
    if as_json or not isinstance(value, str):
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(value, end="" if value.endswith("\n") else "\n")


def _resolved(args: argparse.Namespace):
    return resolve_config(
        args.source_root,
        workspace=args.workspace,
        config_path=args.config,
    )


def _current_artifacts(config) -> dict[str, Any]:
    current_digest = build_inventory(config).digest
    result = verify_artifacts(
        config.workspace,
        current_source_digest=current_digest,
        current_engine_version=__version__,
    )
    if result["status"] != "valid":
        raise InferForgeError(
            f"scan artifacts are missing, invalid, or stale: {result['problems']}; run scan again"
        )
    return result


def _candidate_by_id(config, identifier: str) -> dict[str, Any]:
    _current_artifacts(config)
    for candidate in load_artifact(config.workspace, "candidates.json").get("candidates", []):
        if candidate.get("id") == identifier or candidate.get("fingerprint") == identifier:
            return candidate
    raise InferForgeError(f"candidate not found: {identifier}")


def command_init(args: argparse.Namespace) -> int:
    root = Path(args.source_root).expanduser().resolve()
    if not root.is_dir():
        raise InferForgeError(f"source root is not a directory: {root}")
    output = (
        (root / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output).resolve()
    )
    if output.exists() and not args.force:
        raise InferForgeError(f"configuration already exists: {output}; use --force to replace it")
    write_json_atomic(output, starter_config())
    _print({"created": str(output), "schema_version": 2}, as_json=args.json)
    return 0


def command_scan(args: argparse.Namespace) -> int:
    config = _resolved(args)
    sarif_paths = [Path(value).expanduser().resolve() for value in args.sarif]
    result = run_scan(config, sarif_paths=sarif_paths)
    summary = result["summary"]
    output = {
        "workspace": result["workspace"],
        "source_digest": result["source_digest"],
        **summary["counts"],
        "coverage_status": summary["coverage_status"],
        "candidate_severity_counts": summary["candidate_severity_counts"],
        "semantics": "candidates are hypotheses, not confirmed vulnerabilities",
    }
    _print(output, as_json=args.json)
    if args.fail_on:
        candidates = load_artifact(config.workspace, "candidates.json").get("candidates", [])
        threshold = severity_rank(args.fail_on)
        if any(
            candidate.get("status") not in {"rejected", "fixed"}
            and severity_rank(str(candidate.get("severity"))) >= threshold
            for candidate in candidates
        ):
            return 3
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    result = run_doctor(_resolved(args))
    _print(result, as_json=True)
    return 0 if result["status"] == "ready" else 2


def command_context(args: argparse.Namespace) -> int:
    config = _resolved(args)
    _current_artifacts(config)
    rendered = render_context(
        source_root=config.source_root,
        workspace=config.workspace,
        identifier=args.id,
        radius=args.radius,
    )
    if args.output:
        output = Path(args.output).expanduser()
        output = (config.source_root / output).resolve() if not output.is_absolute() else output.resolve()
        write_text_atomic(output, rendered)
        _print({"written": str(output), "id": args.id}, as_json=args.json)
    else:
        _print(rendered)
    return 0


def command_triage(args: argparse.Namespace) -> int:
    config = _resolved(args)
    candidate = _candidate_by_id(config, args.id)
    record = record_triage(
        workspace=config.workspace,
        source_root=config.source_root,
        candidate=candidate,
        status=args.status,
        note=args.note,
        evidence=args.evidence,
        verification=args.verification,
        impact=args.impact,
        likelihood=args.likelihood,
        analyst=args.analyst,
    )
    _print(
        {
            "candidate_id": candidate["id"],
            "status": record["status"],
            "severity": record.get("severity"),
            "triage_artifact": str(config.workspace / "triage.json"),
            "next_step": "Run scan again to refresh lifecycle status in derived artifacts.",
        },
        as_json=args.json,
    )
    return 0


def command_review(args: argparse.Namespace) -> int:
    config = _resolved(args)
    _current_artifacts(config)
    tasks = load_artifact(config.workspace, "review-plan.json").get("tasks", [])
    task = next((item for item in tasks if item.get("id") == args.id), None)
    if not isinstance(task, dict):
        raise InferForgeError(f"review task not found: {args.id}")
    record = record_review(
        workspace=config.workspace,
        source_root=config.source_root,
        task=task,
        status=args.status,
        note=args.note,
        evidence=args.evidence,
        verification=args.verification,
        analyst=args.analyst,
    )
    _print(
        {
            "task_id": task["id"],
            "status": record["status"],
            "review_state_artifact": str(config.workspace / "review-state.json"),
            "next_step": "Run scan again to refresh task and route-coverage closure.",
        },
        as_json=args.json,
    )
    return 0


def command_report(args: argparse.Namespace) -> int:
    config = _resolved(args)
    _current_artifacts(config)
    output = Path(args.output).expanduser().resolve() if args.output else None
    result = generate_reports(config.workspace, output)
    _print(result, as_json=args.json)
    return 0


def command_verify(args: argparse.Namespace) -> int:
    config = _resolved(args)
    current_digest = build_inventory(config).digest
    result = verify_artifacts(
        config.workspace,
        current_source_digest=current_digest,
        current_engine_version=__version__,
    )
    _print(result, as_json=True)
    return 0 if result["status"] == "valid" else 2


def command_status(args: argparse.Namespace) -> int:
    config = _resolved(args)
    integrity = _current_artifacts(config)
    summary = load_artifact(config.workspace, "scan-summary.json")
    review = load_artifact(config.workspace, "review-plan.json")
    triage = load_triage(config.workspace)
    result = {
        "integrity": integrity,
        "scan": summary,
        "triage_records": len(triage.get("records", {})),
        "review_records": len(load_review_state(config.workspace).get("records", {})),
        "top_review_tasks": review.get("tasks", [])[: args.top],
    }
    _print(result, as_json=True)
    return 0


def command_rules(args: argparse.Namespace) -> int:
    catalog = rule_catalog()
    if args.json:
        _print(catalog, as_json=True)
        return 0
    lines = ["InferForge v2 native rule catalog", ""]
    for group in ("flow_rules", "static_rules"):
        lines.append(group.replace("_", " ").title())
        for rule in catalog[group]:
            lines.append(f"  {rule['id']}  {rule['severity']:8s}  {rule['cwe']:10s}  {rule['title']}")
        lines.append("")
    _print("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inferforge",
        description=(
            "Source-first Web security review evidence engine. "
            "A local source tree is mandatory; no black-box or remote-target mode exists."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    init = subcommands.add_parser("init", help="Create a v2 source-review configuration")
    init.add_argument("--source-root", default=".")
    init.add_argument("--output", default="inferforge.json")
    init.add_argument("--force", action="store_true")
    init.add_argument("--json", action="store_true")
    init.set_defaults(func=command_init)

    scan = subcommands.add_parser(
        "scan", help="Index source, build evidence, and create a bounded review plan"
    )
    _add_source_arguments(scan)
    scan.add_argument(
        "--sarif",
        action="append",
        default=[],
        help="Import one Semgrep, CodeQL, or other SARIF 2.1 result. Repeat as needed.",
    )
    scan.add_argument(
        "--fail-on",
        choices=("low", "medium", "high", "critical"),
        help="Exit 3 when an unresolved candidate meets or exceeds this scanner severity.",
    )
    scan.add_argument("--json", action="store_true")
    scan.set_defaults(func=command_scan)

    doctor = subcommands.add_parser(
        "doctor", help="Validate source access and optional static-analysis tooling"
    )
    _add_source_arguments(doctor)
    doctor.set_defaults(func=command_doctor)

    context = subcommands.add_parser(
        "context", help="Render a bounded source packet for a candidate, task, or route"
    )
    _add_source_arguments(context)
    context.add_argument("--id", required=True, help="Candidate fingerprint/id, review task id, or route id")
    context.add_argument("--radius", type=int, default=10, choices=range(2, 31), metavar="2..30")
    context.add_argument("--output")
    context.add_argument("--json", action="store_true")
    context.set_defaults(func=command_context)

    triage = subcommands.add_parser("triage", help="Record an evidence-backed candidate lifecycle decision")
    _add_source_arguments(triage)
    triage.add_argument("--id", required=True, help="Candidate id or fingerprint")
    triage.add_argument(
        "--status",
        required=True,
        choices=("needs-review", "confirmed", "rejected", "accepted-risk", "fixed"),
    )
    triage.add_argument("--note", required=True)
    triage.add_argument("--evidence", action="append", default=[], metavar="PATH:LINE")
    triage.add_argument(
        "--verification",
        action="append",
        default=[],
        help="Regression test, harness, trace, or other independent verification reference.",
    )
    triage.add_argument("--impact", choices=("low", "medium", "high", "critical"))
    triage.add_argument("--likelihood", choices=("low", "medium", "high"))
    triage.add_argument("--analyst")
    triage.add_argument("--json", action="store_true")
    triage.set_defaults(func=command_triage)

    review = subcommands.add_parser(
        "review", help="Close or reopen a source-derived review task with evidence"
    )
    _add_source_arguments(review)
    review.add_argument("--id", required=True, help="Review task id")
    review.add_argument("--status", required=True, choices=("open", "completed", "not-applicable"))
    review.add_argument("--note", required=True)
    review.add_argument("--evidence", action="append", default=[], metavar="PATH:LINE")
    review.add_argument(
        "--verification",
        action="append",
        default=[],
        help="Regression test, harness, trace, or not-applicable proof reference.",
    )
    review.add_argument("--analyst")
    review.add_argument("--json", action="store_true")
    review.set_defaults(func=command_review)

    report = subcommands.add_parser("report", help="Render reports only for explicitly confirmed candidates")
    _add_source_arguments(report)
    report.add_argument("--output", help="Output directory. Defaults to WORKSPACE/reports.")
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=command_report)

    verify = subcommands.add_parser("verify-artifacts", help="Verify the scan artifact integrity manifest")
    _add_source_arguments(verify)
    verify.set_defaults(func=command_verify)

    status = subcommands.add_parser("status", help="Show scan, integrity, triage, and top review-task state")
    _add_source_arguments(status)
    status.add_argument("--top", type=int, default=10)
    status.set_defaults(func=command_status)

    rules = subcommands.add_parser("rules", help="Show the native source-analysis rule catalog")
    rules.add_argument("--json", action="store_true")
    rules.set_defaults(func=command_rules)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (InferForgeError, OSError, ValueError) as error:
        print(f"inferforge: error: {error}", file=sys.stderr)
        return 2
