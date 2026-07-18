from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from inferforge.config import resolve_config
from inferforge.errors import ConfigurationError


class ConfigTests(unittest.TestCase):
    def test_legacy_remote_target_configuration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text("print('source')\n", encoding="utf-8")
            (root / "inferforge.json").write_text(
                json.dumps({"schema_version": 2, "assessment_mode": "blackbox"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigurationError, "legacy black-box"):
                resolve_config(root)

    def test_source_root_must_exist(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "not a directory"):
            resolve_config("/definitely/not/a/source/root")

    def test_unknown_configuration_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app.py").write_text("print('source')\n", encoding="utf-8")
            (root / "inferforge.json").write_text(
                json.dumps({"schema_version": 2, "surprise": True}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ConfigurationError, "unknown v2"):
                resolve_config(root)


if __name__ == "__main__":
    unittest.main()
