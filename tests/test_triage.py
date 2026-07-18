from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from inferforge.errors import TriageError
from inferforge.triage import record_triage


class TriageContractTests(unittest.TestCase):
    def test_confirmation_requires_evidence_verification_and_risk_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "app.py"
            source.write_text("print('test')\n", encoding="utf-8")
            candidate = {"id": "cand-test", "fingerprint": "fp-test"}
            with self.assertRaisesRegex(TriageError, "source evidence"):
                record_triage(
                    workspace=root / ".inferforge",
                    source_root=root,
                    candidate=candidate,
                    status="confirmed",
                    note="This decision has enough explanatory characters.",
                    evidence=[],
                    verification=["test reference"],
                    impact="high",
                    likelihood="high",
                    analyst=None,
                )

    def test_evidence_cannot_escape_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text("print('test')\n", encoding="utf-8")
            candidate = {"id": "cand-test", "fingerprint": "fp-test"}
            with self.assertRaisesRegex(TriageError, "outside source root"):
                record_triage(
                    workspace=root / ".inferforge",
                    source_root=root,
                    candidate=candidate,
                    status="confirmed",
                    note="This decision has enough explanatory characters.",
                    evidence=["../outside.py:1"],
                    verification=["test reference"],
                    impact="high",
                    likelihood="high",
                    analyst=None,
                )


if __name__ == "__main__":
    unittest.main()
