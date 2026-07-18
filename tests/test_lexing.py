from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from inferforge.config import resolve_config
from inferforge.inventory import build_inventory
from inferforge.lexing import mask_non_code
from inferforge.routes import discover_routes
from inferforge.scanner import run_scan
from inferforge.workspace import load_artifact


class LexicalMaskTests(unittest.TestCase):
    def test_comments_and_pattern_strings_are_not_code(self) -> None:
        source = (
            'PATTERNS = {"route": "@app.route(\\"/fake\\")", "sink": "eval("}\n'
            '# @app.route("/comment")\n'
            'compiled = re.compile(r"exec\\s*\\(")\n'
        )
        masked = mask_non_code(source, "python")
        self.assertNotIn("@app.route", masked)
        self.assertNotIn("exec", masked)
        self.assertIn("re.compile", masked)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "patterns.py").write_text(source, encoding="utf-8")
            workspace = root / ".results"
            config = resolve_config(root, workspace=workspace)
            inventory = build_inventory(config)
            self.assertEqual(discover_routes(inventory), [])
            run_scan(config)
            self.assertEqual(load_artifact(workspace, "review-plan.json")["summary"]["tasks"], 0)
            self.assertFalse(
                any(sink["rule_id"] == "IFW008" for sink in load_artifact(workspace, "signals.json")["sinks"])
            )


if __name__ == "__main__":
    unittest.main()
