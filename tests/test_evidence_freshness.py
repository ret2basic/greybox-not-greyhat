from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from inferforge.config import resolve_config
from inferforge.reporting import generate_reports
from inferforge.scanner import run_scan
from inferforge.triage import record_triage
from inferforge.workspace import load_artifact


class EvidenceFreshnessTests(unittest.TestCase):
    def test_changed_evidence_file_reopens_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "app.py"
            source.write_text(
                "\n".join(
                    [
                        "from flask import Flask, request, send_file",
                        "app = Flask(__name__)",
                        '@app.route("/download")',
                        "def download():",
                        '    path = request.args["path"]',
                        "    return send_file(path)",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            workspace = root / ".evidence"
            config = resolve_config(root, workspace=workspace)
            run_scan(config)
            candidate = next(
                item
                for item in load_artifact(workspace, "candidates.json")["candidates"]
                if item["rule_id"] == "IFW004"
            )
            record_triage(
                workspace=workspace,
                source_root=root,
                candidate=candidate,
                status="confirmed",
                note="Request path reaches the file response without a canonical-root boundary.",
                evidence=["app.py:6"],
                verification=["tests/security/test_download.py::rejects_traversal"],
                impact="high",
                likelihood="high",
                analyst="unit-test",
            )
            first_report = generate_reports(workspace)
            self.assertEqual(first_report["confirmed"], 1)
            finding_path = workspace / "reports" / f"{candidate['id']}.md"
            self.assertTrue(finding_path.is_file())

            source.write_text(source.read_text(encoding="utf-8") + "# source changed\n", encoding="utf-8")
            result = run_scan(config)
            self.assertEqual(len(result["summary"]["stale_triage_records"]), 1)
            refreshed = next(
                item
                for item in load_artifact(workspace, "candidates.json")["candidates"]
                if item["id"] == candidate["id"]
            )
            self.assertEqual(refreshed["status"], "needs-review")
            report = generate_reports(workspace)
            self.assertEqual(report["confirmed"], 0)
            self.assertEqual(report["stale_confirmed_withheld"], [candidate["id"]])
            self.assertFalse(finding_path.exists())


if __name__ == "__main__":
    unittest.main()
