from __future__ import annotations

import fnmatch
import json
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import MANIFEST_NAMES, ScanConfig
from .errors import ConfigurationError
from .lexing import mask_non_code
from .models import SourceFile
from .util import relative_path, sha256_bytes, stable_id

LANGUAGE_BY_EXTENSION = {
    ".cjs": "javascript",
    ".cs": "csharp",
    ".go": "go",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".kt": "kotlin",
    ".mjs": "javascript",
    ".php": "php",
    ".py": "python",
    ".rb": "ruby",
    ".rs": "rust",
    ".scala": "scala",
    ".ts": "typescript",
    ".tsx": "typescript",
}

GENERATED_NAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "Cargo.lock",
    "composer.lock",
}

FRAMEWORK_DEPENDENCIES = {
    "@nestjs/core": "nestjs",
    "@sveltejs/kit": "sveltekit",
    "actix-web": "actix-web",
    "axum": "axum",
    "django": "django",
    "express": "express",
    "fastapi": "fastapi",
    "fastify": "fastify",
    "flask": "flask",
    "gin-gonic/gin": "gin",
    "github.com/labstack/echo": "echo",
    "laravel/framework": "laravel",
    "next": "nextjs",
    "rails": "rails",
    "spring-boot": "spring",
}


@dataclass
class InventoryResult:
    files: list[SourceFile]
    texts: dict[str, str]
    skipped: list[dict[str, Any]]
    frameworks: list[dict[str, Any]]
    coverage_status: str
    coverage_reasons: list[str]
    digest: str

    def artifact(self) -> dict[str, Any]:
        languages = Counter(file.language for file in self.files if not file.manifest)
        return {
            "schema_version": 2,
            "source_digest": self.digest,
            "coverage_status": self.coverage_status,
            "coverage_reasons": self.coverage_reasons,
            "summary": {
                "files": len(self.files),
                "source_files": sum(not item.manifest for item in self.files),
                "manifest_files": sum(item.manifest for item in self.files),
                "bytes": sum(item.size for item in self.files),
                "languages": dict(sorted(languages.items())),
                "skipped": len(self.skipped),
            },
            "frameworks": self.frameworks,
            "files": [file.to_dict() for file in self.files],
            "skipped": self.skipped,
        }


def _excluded(relative: str, config: ScanConfig) -> bool:
    return any(
        fnmatch.fnmatch(relative, pattern)
        or fnmatch.fnmatch(f"/{relative}", pattern)
        or Path(relative).match(pattern)
        for pattern in config.exclude_globs
    )


def _looks_generated(path: Path, text: str) -> bool:
    if path.name in GENERATED_NAMES:
        return True
    head = "\n".join(text.splitlines()[:8]).lower()
    if "@generated" in head or "code generated" in head or "do not edit" in head:
        return True
    lines = text.splitlines()
    return bool(lines and max((len(line) for line in lines[:200]), default=0) > 10_000)


def _read_candidate(path: Path, max_bytes: int) -> tuple[bytes | None, str | None]:
    try:
        size = path.stat().st_size
    except OSError as error:
        return None, f"stat-error:{error.__class__.__name__}"
    if size > max_bytes:
        return None, "file-too-large"
    try:
        data = path.read_bytes()
    except OSError as error:
        return None, f"read-error:{error.__class__.__name__}"
    if b"\x00" in data[:8192]:
        return None, "binary-file"
    return data, None


def _manifest_framework_evidence(path: str, text: str) -> list[tuple[str, str]]:
    evidence: list[tuple[str, str]] = []
    name = Path(path).name
    if name == "package.json":
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            return evidence
        dependencies: dict[str, Any] = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            value = document.get(key, {})
            if isinstance(value, dict):
                dependencies.update(value)
        for dependency, framework in FRAMEWORK_DEPENDENCIES.items():
            if dependency in dependencies:
                evidence.append((framework, f"{path}:{dependency}"))
    else:
        lowered = text.lower()
        token_evidence = {
            "django": ("django",),
            "fastapi": ("fastapi",),
            "flask": ("flask",),
            "spring": ("spring-boot", "org.springframework"),
            "rails": ("rails",),
            "laravel": ("laravel/framework",),
            "gin": ("gin-gonic/gin",),
            "echo": ("labstack/echo",),
            "axum": ("axum",),
            "actix-web": ("actix-web",),
        }
        for framework, tokens in token_evidence.items():
            if any(token in lowered for token in tokens):
                evidence.append((framework, path))
    return evidence


def _detect_frameworks(files: list[SourceFile], texts: dict[str, str]) -> list[dict[str, Any]]:
    by_framework: dict[str, set[str]] = {}
    for file in files:
        if not file.manifest:
            continue
        for framework, evidence in _manifest_framework_evidence(file.path, texts[file.path]):
            by_framework.setdefault(framework, set()).add(evidence)

    source_markers = {
        "nextjs": ("next/server", "next/navigation"),
        "express": ("express()", "express.router("),
        "fastapi": ("fastapi(", "apirouter("),
        "flask": ("flask(", "@app.route(", "@blueprint.route("),
        "django": ("django.urls", "urlpatterns"),
        "spring": ("@restcontroller", "@requestmapping"),
        "laravel": ("route::get(", "route::post("),
        "rails": ("rails.application.routes.draw",),
        "gin": ("gin.default()", "gin.new()"),
        "echo": ("echo.new()",),
        "axum": ("axum::router", "router::new()"),
        "actix-web": ("#[get(", "#[post(", "actix_web"),
    }
    language_by_path = {file.path: file.language for file in files}
    for path, text in texts.items():
        lowered = mask_non_code(text, language_by_path[path]).lower()
        for framework, markers in source_markers.items():
            if any(marker in lowered for marker in markers):
                by_framework.setdefault(framework, set()).add(path)

    return [
        {"name": name, "evidence": sorted(evidence)[:20]} for name, evidence in sorted(by_framework.items())
    ]


def build_inventory(config: ScanConfig) -> InventoryResult:
    root = config.source_root
    files: list[SourceFile] = []
    texts: dict[str, str] = {}
    skipped: list[dict[str, Any]] = []
    coverage_reasons: list[str] = []
    total_bytes = 0

    for directory, directory_names, file_names in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        relative_directory = relative_path(current, root) if current != root else ""
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            candidate = current / name
            relative = f"{relative_directory}/{name}".strip("/")
            if name in config.exclude_dirs or _excluded(relative, config):
                continue
            if candidate.is_symlink():
                skipped.append({"path": relative, "reason": "symlink-directory"})
                continue
            kept_directories.append(name)
        directory_names[:] = kept_directories

        for name in sorted(file_names):
            path = current / name
            relative = f"{relative_directory}/{name}".strip("/")
            if _excluded(relative, config):
                continue
            if path.is_symlink():
                skipped.append({"path": relative, "reason": "symlink-file"})
                continue
            extension = path.suffix.lower()
            is_manifest = name in MANIFEST_NAMES
            if extension not in config.include_extensions and not is_manifest:
                continue
            if len(files) >= config.max_files:
                coverage_reasons.append("max-files-reached")
                break
            data, problem = _read_candidate(path, config.max_file_bytes)
            if problem:
                skipped.append({"path": relative, "reason": problem})
                if problem != "binary-file":
                    coverage_reasons.append(f"{problem}:{relative}")
                continue
            assert data is not None
            if total_bytes + len(data) > config.max_total_bytes:
                skipped.append({"path": relative, "reason": "total-byte-budget"})
                coverage_reasons.append("max-total-bytes-reached")
                continue
            text = data.decode("utf-8", errors="replace")
            total_bytes += len(data)
            language = "manifest" if is_manifest else LANGUAGE_BY_EXTENSION.get(extension, "unknown")
            source_file = SourceFile(
                path=relative,
                language=language,
                size=len(data),
                sha256=sha256_bytes(data),
                generated=_looks_generated(path, text),
                manifest=is_manifest,
            )
            files.append(source_file)
            texts[relative] = text
        if "max-files-reached" in coverage_reasons:
            break

    source_files = [file for file in files if not file.manifest and not file.generated]
    if not source_files:
        raise ConfigurationError(
            "no supported source files were found; InferForge v2 is source-required and cannot run as a black-box tool"
        )

    effective_config = config.public_dict()
    effective_config.pop("workspace", None)
    digest_material = "\n".join(
        [
            json.dumps(effective_config, ensure_ascii=False, sort_keys=True),
            *(f"{file.path}\0{file.sha256}" for file in sorted(files, key=lambda item: item.path)),
        ]
    )
    digest = stable_id("src", digest_material, length=32)
    reasons = sorted(set(coverage_reasons))
    return InventoryResult(
        files=files,
        texts=texts,
        skipped=skipped,
        frameworks=_detect_frameworks(files, texts),
        coverage_status="incomplete" if reasons else "complete",
        coverage_reasons=reasons,
        digest=digest,
    )
