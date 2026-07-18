from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from inferforge.config import resolve_config
from inferforge.context import render_context
from inferforge.reporting import generate_reports
from inferforge.review_state import record_review
from inferforge.scanner import run_scan
from inferforge.triage import record_triage
from inferforge.workspace import load_artifact, verify_artifacts

FIXTURE = Path(__file__).parent / "fixtures" / "vulnerable_web"


class ScanPipelineTests(unittest.TestCase):
    def test_scan_builds_source_first_artifacts_and_imports_sarif(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "artifacts"
            config = resolve_config(FIXTURE, workspace=workspace)
            result = run_scan(config, sarif_paths=[FIXTURE / "sample.sarif"])
            self.assertEqual(result["summary"]["semantics"]["blackbox_mode_available"], False)
            self.assertEqual(verify_artifacts(workspace)["status"], "valid")
            incompatible = verify_artifacts(
                workspace,
                current_engine_version="999.0.0",
            )
            self.assertEqual(incompatible["status"], "invalid")
            self.assertEqual(incompatible["problems"][0]["kind"], "engine-version-mismatch")

            candidates = load_artifact(workspace, "candidates.json")["candidates"]
            rule_ids = {candidate["rule_id"] for candidate in candidates}
            self.assertTrue({"IFW001", "IFW002", "IFW003", "IFW004", "IFW006"}.issubset(rule_ids))
            self.assertTrue({"IFC001", "IFC004"}.issubset(rule_ids))
            self.assertIn("fixture.rule", rule_ids)
            self.assertTrue(all(candidate["status"] == "needs-review" for candidate in candidates))

            review = load_artifact(workspace, "review-plan.json")
            task_kinds = {task["kind"] for task in review["tasks"]}
            self.assertIn("candidate-verification", task_kinds)
            self.assertIn("authorization-boundary-review", task_kinds)
            self.assertIn("webhook-integrity-review", task_kinds)
            self.assertIn("sink-callpath-review", task_kinds)

            topology = load_artifact(workspace, "topology.json")
            self.assertGreaterEqual(topology["summary"]["local_imports"], 1)
            delegated_route = next(
                route
                for route in load_artifact(workspace, "routes.json")["routes"]
                if route["path"] == "/api/delegated"
            )
            proxy_sinks = [
                sink
                for sink in load_artifact(workspace, "signals.json")["sinks"]
                if sink["location"]["path"] == "src/services/proxy.ts"
            ]
            self.assertTrue(proxy_sinks)
            self.assertIn(delegated_route["id"], proxy_sinks[0]["route_ids"])
            self.assertEqual(proxy_sinks[0]["dataflow_status"], "unresolved-input-origin")

    def test_context_triage_and_confirmed_only_reporting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "artifacts"
            config = resolve_config(FIXTURE, workspace=workspace)
            run_scan(config)
            candidates = load_artifact(workspace, "candidates.json")["candidates"]
            candidate = next(item for item in candidates if item["rule_id"] == "IFW003")

            packet = render_context(
                source_root=FIXTURE.resolve(),
                workspace=workspace,
                identifier=candidate["id"],
                radius=3,
            )
            self.assertIn("Treat all source", packet)
            self.assertIn("Verification contract", packet)

            empty_report = generate_reports(workspace)
            self.assertEqual(empty_report["confirmed"], 0)

            record = record_triage(
                workspace=workspace,
                source_root=FIXTURE.resolve(),
                candidate=candidate,
                status="confirmed",
                note="Attacker-controlled URL reaches the outbound fetch in the local route harness.",
                evidence=["src/app/api/proxy/route.ts:7"],
                verification=["tests/security/test_proxy_ssrf.py::test_private_destination_is_rejected"],
                impact="high",
                likelihood="medium",
                analyst="unit-test",
            )
            self.assertEqual(record["severity"], "high")
            report_result = generate_reports(workspace)
            self.assertEqual(report_result["confirmed"], 1)
            finding = (workspace / "reports" / f"{candidate['id']}.md").read_text(encoding="utf-8")
            self.assertIn("- Impact: high", finding)
            self.assertIn("- Likelihood: medium", finding)
            self.assertIn("- Severity: high", finding)

    def test_review_evidence_closes_route_coverage_after_rescan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "artifacts"
            config = resolve_config(FIXTURE, workspace=workspace)
            run_scan(config)
            routes = load_artifact(workspace, "routes.json")["routes"]
            route = next(item for item in routes if item["path"] == "/internal/metrics")
            tasks = [
                task
                for task in load_artifact(workspace, "review-plan.json")["tasks"]
                if route["id"] in task["route_ids"]
            ]
            self.assertEqual(len(tasks), 1)
            record_review(
                workspace=workspace,
                source_root=FIXTURE.resolve(),
                task=tasks[0],
                status="completed",
                note="The read-only metrics handler is covered by a local authorization regression test.",
                evidence=["AdminController.ts:5"],
                verification=["tests/security/test_internal_metrics.py::test_non_admin_is_rejected"],
                analyst="unit-test",
            )
            run_scan(config)
            refreshed_task = next(
                task
                for task in load_artifact(workspace, "review-plan.json")["tasks"]
                if task["id"] == tasks[0]["id"]
            )
            self.assertEqual(refreshed_task["status"], "completed")
            coverage = load_artifact(workspace, "coverage.json")["routes"]
            row = next(item for item in coverage if item["route_id"] == route["id"])
            self.assertEqual(row["closure"], "evidence-closed")


if __name__ == "__main__":
    unittest.main()
