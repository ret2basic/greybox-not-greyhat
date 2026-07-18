from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from inferforge.cli import build_parser, main
from inferforge.config import resolve_config
from inferforge.scanner import run_scan


class CliContractTests(unittest.TestCase):
    def test_command_surface_is_source_first_only(self) -> None:
        parser = build_parser()
        subparser_action = next(
            action
            for action in parser._actions
            if hasattr(action, "choices") and isinstance(action.choices, dict)
        )
        choices = subparser_action.choices
        self.assertIsInstance(choices, dict)
        assert isinstance(choices, dict)
        self.assertEqual(
            set(choices),
            {
                "init",
                "scan",
                "doctor",
                "context",
                "triage",
                "review",
                "report",
                "verify-artifacts",
                "status",
                "rules",
            },
        )

    def test_removed_mode_is_not_parseable(self) -> None:
        parser = build_parser()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["blackbox-profile"])

    def test_scan_refuses_a_directory_without_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main(["scan", "--source-root", temporary])
            self.assertEqual(result, 2)
            self.assertIn("source-required", stderr.getvalue())
            self.assertFalse((Path(temporary) / ".inferforge").exists())

    def test_artifact_commands_reject_a_stale_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "app.py"
            source.write_text("print('first')\n", encoding="utf-8")
            workspace = root / ".results"
            run_scan(resolve_config(root, workspace=workspace))
            source.write_text("print('changed')\n", encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                verify_result = main(
                    [
                        "verify-artifacts",
                        "--source-root",
                        str(root),
                        "--workspace",
                        str(workspace),
                    ]
                )
            self.assertEqual(verify_result, 2)
            self.assertIn("source-digest-mismatch", stdout.getvalue())

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                status_result = main(
                    [
                        "status",
                        "--source-root",
                        str(root),
                        "--workspace",
                        str(workspace),
                    ]
                )
            self.assertEqual(status_result, 2)
            self.assertIn("stale", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
