from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from inferforge.util import load_json, write_json_atomic
from inferforge.workspace import verify_artifacts, write_artifact_set


class WorkspaceIntegrityTests(unittest.TestCase):
    def test_manifest_entry_cannot_escape_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "workspace"
            write_artifact_set(
                workspace,
                source_digest="src-test",
                json_artifacts={"run.json": {"inferforge_version": "2.0.0"}},
                text_artifacts={},
            )
            manifest_path = workspace / "artifact-manifest.json"
            manifest = load_json(manifest_path)
            manifest["files"].append(
                {
                    "path": "../outside",
                    "bytes": 0,
                    "sha256": "0" * 64,
                }
            )
            write_json_atomic(manifest_path, manifest)
            result = verify_artifacts(workspace)
            self.assertEqual(result["status"], "invalid")
            self.assertTrue(any(problem["kind"] == "artifact-path-escape" for problem in result["problems"]))


if __name__ == "__main__":
    unittest.main()
