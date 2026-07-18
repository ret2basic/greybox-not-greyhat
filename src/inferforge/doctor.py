from __future__ import annotations

import shutil
from typing import Any

from . import __version__
from .config import ScanConfig
from .inventory import build_inventory
from .workspace import MANIFEST_NAME, verify_artifacts


def run_doctor(config: ScanConfig) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "name": "source-root",
            "status": "pass" if config.source_root.is_dir() else "fail",
            "detail": str(config.source_root),
            "required": True,
        }
    )
    inventory = build_inventory(config)
    checks.append(
        {
            "name": "source-inventory",
            "status": "pass" if inventory.files else "fail",
            "detail": {
                "files": len(inventory.files),
                "coverage_status": inventory.coverage_status,
                "frameworks": [item["name"] for item in inventory.frameworks],
            },
            "required": True,
        }
    )
    for tool in ("git", "rg", "semgrep", "codeql"):
        found = shutil.which(tool)
        checks.append(
            {
                "name": f"optional-tool:{tool}",
                "status": "pass" if found else "optional-missing",
                "detail": found,
                "required": False,
            }
        )
    if (config.workspace / MANIFEST_NAME).is_file():
        integrity = verify_artifacts(
            config.workspace,
            current_source_digest=inventory.digest,
            current_engine_version=__version__,
        )
        checks.append(
            {
                "name": "artifact-integrity",
                "status": "pass" if integrity["status"] == "valid" else "fail",
                "detail": integrity,
                "required": True,
            }
        )
    else:
        checks.append(
            {
                "name": "artifact-integrity",
                "status": "not-scanned",
                "detail": "No artifact manifest exists yet.",
                "required": False,
            }
        )
    failures = [check for check in checks if check["required"] and check["status"] == "fail"]
    return {
        "schema_version": 2,
        "status": "ready" if not failures else "not-ready",
        "mode": "source-required-whitebox",
        "network_activity": False,
        "checks": checks,
    }
