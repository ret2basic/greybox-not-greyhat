from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ConfigurationError
from .models import SEVERITIES
from .util import path_is_within

SCHEMA_VERSION = 2

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".inferforge",
    ".greybox",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    "target",
    ".next",
    ".nuxt",
    ".svelte-kit",
}

DEFAULT_EXTENSIONS = {
    ".cjs",
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scala",
    ".ts",
    ".tsx",
}

MANIFEST_NAMES = {
    "build.gradle",
    "build.gradle.kts",
    "composer.json",
    "Gemfile",
    "go.mod",
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
}

LEGACY_KEYS = {
    "assessment_mode",
    "blackbox",
    "bounty_program",
    "burp",
    "burp_mcp",
    "scope_hosts",
    "target",
}

ALLOWED_ROOT_KEYS = {
    "$schema",
    "schema_version",
    "exclude",
    "include_extensions",
    "limits",
    "rules",
    "trust_boundaries",
}


@dataclass
class ScanConfig:
    source_root: Path
    workspace: Path
    config_path: Path | None
    exclude_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDE_DIRS))
    exclude_globs: list[str] = field(default_factory=list)
    include_extensions: set[str] = field(default_factory=lambda: set(DEFAULT_EXTENSIONS))
    max_file_bytes: int = 1_048_576
    max_files: int = 25_000
    max_total_bytes: int = 128 * 1024 * 1024
    disabled_rules: set[str] = field(default_factory=set)
    severity_overrides: dict[str, str] = field(default_factory=dict)
    trust_boundaries: list[dict[str, str]] = field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "source_root": ".",
            "workspace": (
                self.workspace.relative_to(self.source_root).as_posix()
                if path_is_within(self.workspace, self.source_root)
                else str(self.workspace)
            ),
            "exclude_dirs": sorted(self.exclude_dirs),
            "exclude_globs": self.exclude_globs,
            "include_extensions": sorted(self.include_extensions),
            "limits": {
                "max_file_bytes": self.max_file_bytes,
                "max_files": self.max_files,
                "max_total_bytes": self.max_total_bytes,
            },
            "rules": {
                "disabled": sorted(self.disabled_rules),
                "severity_overrides": self.severity_overrides,
            },
            "trust_boundaries": self.trust_boundaries,
        }


def _positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigurationError(f"{label} must be a positive integer")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ConfigurationError(f"{label} must be an array of non-empty strings")
    return value


def _load_document(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as error:
        raise ConfigurationError(f"configuration file does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigurationError(f"invalid JSON configuration at {path}: {error}") from error
    if not isinstance(value, dict):
        raise ConfigurationError("configuration root must be an object")
    legacy = sorted(LEGACY_KEYS.intersection(value))
    if legacy:
        joined = ", ".join(legacy)
        raise ConfigurationError(
            f"legacy black-box configuration keys are not supported in v2: {joined}; "
            "InferForge now requires local source and has no remote-target mode"
        )
    unknown = sorted(set(value).difference(ALLOWED_ROOT_KEYS))
    if unknown:
        raise ConfigurationError(f"unknown v2 configuration keys: {', '.join(unknown)}")
    return value


def resolve_config(
    source_root: str | Path,
    *,
    workspace: str | Path | None = None,
    config_path: str | Path | None = None,
) -> ScanConfig:
    root = Path(source_root).expanduser().resolve()
    if not root.is_dir():
        raise ConfigurationError(f"source root is not a directory: {root}")

    if workspace is None:
        workspace_path = root / ".inferforge"
    else:
        raw_workspace = Path(workspace).expanduser()
        workspace_path = (
            (root / raw_workspace).resolve() if not raw_workspace.is_absolute() else raw_workspace.resolve()
        )

    selected_config: Path | None
    if config_path:
        raw_config = Path(config_path).expanduser()
        selected_config = (
            (root / raw_config).resolve() if not raw_config.is_absolute() else raw_config.resolve()
        )
    elif (root / "inferforge.json").is_file():
        selected_config = root / "inferforge.json"
    else:
        selected_config = None

    config = ScanConfig(source_root=root, workspace=workspace_path, config_path=selected_config)
    if selected_config is None:
        return config

    document = _load_document(selected_config)
    schema_version = document.get("schema_version", SCHEMA_VERSION)
    if schema_version != SCHEMA_VERSION:
        raise ConfigurationError(
            f"unsupported configuration schema_version={schema_version!r}; expected {SCHEMA_VERSION}"
        )

    exclude = document.get("exclude", {})
    if exclude:
        if not isinstance(exclude, dict):
            raise ConfigurationError("exclude must be an object")
        config.exclude_dirs.update(_string_list(exclude.get("directories", []), "exclude.directories"))
        config.exclude_globs.extend(_string_list(exclude.get("globs", []), "exclude.globs"))

    extensions = document.get("include_extensions")
    if extensions is not None:
        values = _string_list(extensions, "include_extensions")
        config.include_extensions = {value if value.startswith(".") else f".{value}" for value in values}

    limits = document.get("limits", {})
    if limits:
        if not isinstance(limits, dict):
            raise ConfigurationError("limits must be an object")
        if "max_file_bytes" in limits:
            config.max_file_bytes = _positive_int(limits["max_file_bytes"], "limits.max_file_bytes")
        if "max_files" in limits:
            config.max_files = _positive_int(limits["max_files"], "limits.max_files")
        if "max_total_bytes" in limits:
            config.max_total_bytes = _positive_int(limits["max_total_bytes"], "limits.max_total_bytes")

    rules = document.get("rules", {})
    if rules:
        if not isinstance(rules, dict):
            raise ConfigurationError("rules must be an object")
        config.disabled_rules = set(_string_list(rules.get("disabled", []), "rules.disabled"))
        overrides = rules.get("severity_overrides", {})
        if not isinstance(overrides, dict) or any(
            not isinstance(rule_id, str) or severity not in SEVERITIES
            for rule_id, severity in overrides.items()
        ):
            raise ConfigurationError("rules.severity_overrides must map rule ids to valid severities")
        config.severity_overrides = dict(overrides)

    boundaries = document.get("trust_boundaries", [])
    if not isinstance(boundaries, list) or any(
        not isinstance(item, dict)
        or not isinstance(item.get("name"), str)
        or not isinstance(item.get("pattern"), str)
        for item in boundaries
    ):
        raise ConfigurationError("trust_boundaries must contain objects with string name and pattern")
    config.trust_boundaries = boundaries
    return config


def starter_config() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "exclude": {
            "directories": [],
            "globs": [],
        },
        "limits": {
            "max_file_bytes": 1_048_576,
            "max_files": 25_000,
            "max_total_bytes": 134_217_728,
        },
        "rules": {
            "disabled": [],
            "severity_overrides": {},
        },
        "trust_boundaries": [],
    }
