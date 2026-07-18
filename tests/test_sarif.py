from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from inferforge.sarif import import_sarif


class SarifBoundaryTests(unittest.TestCase):
    def test_sarif_location_cannot_escape_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "source"
            root.mkdir()
            (root / "app.py").write_text("print('source')\n", encoding="utf-8")
            (base / "outside.py").write_text("print('outside')\n", encoding="utf-8")
            sarif = base / "outside.sarif"
            sarif.write_text(
                json.dumps(
                    {
                        "version": "2.1.0",
                        "runs": [
                            {
                                "tool": {"driver": {"name": "BoundaryFixture"}},
                                "results": [
                                    {
                                        "ruleId": "escape",
                                        "message": {"text": "outside"},
                                        "locations": [
                                            {
                                                "physicalLocation": {
                                                    "artifactLocation": {"uri": "../outside.py"},
                                                    "region": {"startLine": 1},
                                                }
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = import_sarif([sarif], root, [])
            self.assertEqual(result.candidates, [])
            self.assertTrue(
                any(item["kind"] == "location-outside-source-root" for item in result.diagnostics)
            )


if __name__ == "__main__":
    unittest.main()
