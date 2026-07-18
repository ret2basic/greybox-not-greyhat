from __future__ import annotations

import posixpath
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .inventory import InventoryResult
from .lexing import mask_non_code, match_starts_in_code
from .models import Route
from .util import stable_id

DEFINITION_PATTERNS = (
    re.compile(r"\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("),
    re.compile(r"\b(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\("),
    re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE),
    re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(", re.MULTILINE),
    re.compile(
        r"\b(?:public|private|protected|static|final|suspend|async|\s)+\s+"
        r"[A-Za-z_<>\[\],?]+\s+([A-Za-z_]\w*)\s*\("
    ),
)

JS_IMPORT_PATTERN = re.compile(
    r"\bimport\s+(?P<bindings>[^;\n]+?)\s+from\s+['\"](?P<module>[^'\"]+)['\"]"
    r"|\brequire\s*\(\s*['\"](?P<require>[^'\"]+)['\"]\s*\)"
)

PYTHON_IMPORT_PATTERN = re.compile(
    r"^\s*from\s+(?P<module>\.{1,}[A-Za-z0-9_.]*)\s+import\s+(?P<bindings>[^\n#]+)",
    re.MULTILINE,
)

RUBY_IMPORT_PATTERN = re.compile(r"\brequire_relative\s+['\"](?P<module>[^'\"]+)['\"]")

CALL_PATTERN = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(")

CALL_KEYWORDS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "function",
    "def",
    "return",
    "typeof",
    "sizeof",
    "new",
    "match",
}


@dataclass
class TopologyResult:
    artifact: dict[str, Any]
    reachable_routes_by_file: dict[str, list[str]]


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _resolve_js_import(source_path: str, module: str, known_files: set[str]) -> str | None:
    if not module.startswith("."):
        return None
    parent = Path(source_path).parent
    base = (parent / module).as_posix()
    candidates = [
        base,
        *(f"{base}{extension}" for extension in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")),
        *(f"{base}/index{extension}" for extension in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")),
    ]
    normalized = [posixpath.normpath(candidate) for candidate in candidates]
    return next((candidate for candidate in normalized if candidate in known_files), None)


def _resolve_python_import(source_path: str, module: str, known_files: set[str]) -> str | None:
    dots = len(module) - len(module.lstrip("."))
    suffix = module[dots:].replace(".", "/")
    parent = Path(source_path).parent
    for _ in range(max(0, dots - 1)):
        parent = parent.parent
    base = parent / suffix if suffix else parent
    candidates = [f"{base.as_posix()}.py", f"{base.as_posix()}/__init__.py"]
    return next((candidate for candidate in candidates if candidate in known_files), None)


def _resolve_ruby_import(source_path: str, module: str, known_files: set[str]) -> str | None:
    base = (Path(source_path).parent / module).as_posix()
    candidates = [posixpath.normpath(base), posixpath.normpath(f"{base}.rb")]
    return next((candidate for candidate in candidates if candidate in known_files), None)


def _definitions(path: str, text: str, masked: str) -> list[dict[str, Any]]:
    found: dict[tuple[str, int], dict[str, Any]] = {}
    for pattern in DEFINITION_PATTERNS:
        for match in pattern.finditer(masked):
            name = match.group(1)
            line = _line_number(text, match.start())
            found[(name, line)] = {
                "id": stable_id("symbol", path, name, line),
                "name": name,
                "path": path,
                "line": line,
            }
    return sorted(found.values(), key=lambda item: (item["line"], item["name"]))


def _imports(path: str, text: str, masked: str, known_files: set[str]) -> list[dict[str, Any]]:
    imports: list[dict[str, Any]] = []
    for match in JS_IMPORT_PATTERN.finditer(text):
        if not match_starts_in_code(masked, match.start()):
            continue
        module = match.group("module") or match.group("require")
        resolved = _resolve_js_import(path, module, known_files)
        if resolved:
            imports.append(
                {
                    "id": stable_id("import", path, resolved, match.start()),
                    "from": path,
                    "to": resolved,
                    "module": module,
                    "line": _line_number(text, match.start()),
                    "kind": "javascript-local-import",
                }
            )
    for match in PYTHON_IMPORT_PATTERN.finditer(text):
        if not match_starts_in_code(masked, match.start()):
            continue
        module = match.group("module")
        resolved = _resolve_python_import(path, module, known_files)
        if resolved:
            imports.append(
                {
                    "id": stable_id("import", path, resolved, match.start()),
                    "from": path,
                    "to": resolved,
                    "module": module,
                    "line": _line_number(text, match.start()),
                    "kind": "python-relative-import",
                }
            )
    for match in RUBY_IMPORT_PATTERN.finditer(text):
        if not match_starts_in_code(masked, match.start()):
            continue
        module = match.group("module")
        resolved = _resolve_ruby_import(path, module, known_files)
        if resolved:
            imports.append(
                {
                    "id": stable_id("import", path, resolved, match.start()),
                    "from": path,
                    "to": resolved,
                    "module": module,
                    "line": _line_number(text, match.start()),
                    "kind": "ruby-relative-import",
                }
            )
    unique = {item["id"]: item for item in imports}
    return sorted(unique.values(), key=lambda item: (item["from"], item["line"], item["to"]))


def _symbol_for_line(definitions: list[dict[str, Any]], line: int) -> dict[str, Any] | None:
    preceding = [definition for definition in definitions if definition["line"] <= line]
    return max(preceding, key=lambda item: item["line"]) if preceding else None


def build_topology(inventory: InventoryResult, routes: list[Route]) -> TopologyResult:
    source_files = {file.path for file in inventory.files if not file.manifest and not file.generated}
    language_by_path = {file.path: file.language for file in inventory.files}
    masked_by_file = {
        path: mask_non_code(text, language_by_path[path])
        for path, text in inventory.texts.items()
        if path in source_files
    }
    definitions_by_file = {
        path: _definitions(path, text, masked_by_file[path])
        for path, text in inventory.texts.items()
        if path in source_files
    }
    definitions = [definition for values in definitions_by_file.values() for definition in values]
    imports = [
        item
        for path, text in inventory.texts.items()
        if path in source_files
        for item in _imports(path, text, masked_by_file[path], source_files)
    ]

    symbols_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for definition in definitions:
        symbols_by_name[definition["name"]].append(definition)
    calls: list[dict[str, Any]] = []
    for path, text in inventory.texts.items():
        if path not in source_files:
            continue
        local_definitions = definitions_by_file[path]
        for match in CALL_PATTERN.finditer(masked_by_file[path]):
            name = match.group(1)
            if name in CALL_KEYWORDS:
                continue
            line = _line_number(text, match.start())
            caller = _symbol_for_line(local_definitions, line)
            targets = symbols_by_name.get(name, [])
            if not caller or len(targets) != 1 or caller["id"] == targets[0]["id"]:
                continue
            target = targets[0]
            calls.append(
                {
                    "id": stable_id("call", caller["id"], target["id"], line),
                    "from": caller["id"],
                    "to": target["id"],
                    "path": path,
                    "line": line,
                    "name": name,
                    "resolution": "unique-local-symbol",
                }
            )

    adjacency: dict[str, set[str]] = defaultdict(set)
    for item in imports:
        adjacency[item["from"]].add(item["to"])
    routes_by_file: dict[str, list[str]] = defaultdict(list)
    for route in routes:
        routes_by_file[route.location.path].append(route.id)
    reachable_routes_by_file: dict[str, set[str]] = defaultdict(set)
    for root_file, route_ids in routes_by_file.items():
        queue: deque[tuple[str, int]] = deque([(root_file, 0)])
        visited: set[str] = set()
        while queue:
            current, depth = queue.popleft()
            if current in visited or depth > 16:
                continue
            visited.add(current)
            reachable_routes_by_file[current].update(route_ids)
            for child in adjacency.get(current, set()):
                queue.append((child, depth + 1))

    route_symbol_edges: list[dict[str, Any]] = []
    for route in routes:
        candidates = definitions_by_file.get(route.location.path, [])
        target = None
        if route.handler:
            named = [item for item in candidates if item["name"] == route.handler]
            if named:
                target = min(named, key=lambda item: abs(item["line"] - route.location.line))
        if target is None and candidates:
            target = min(candidates, key=lambda item: abs(item["line"] - route.location.line))
        if target:
            route_symbol_edges.append(
                {
                    "id": stable_id("entry", route.id, target["id"]),
                    "from": route.id,
                    "to": target["id"],
                    "type": "entry-symbol",
                }
            )

    artifact = {
        "schema_version": 2,
        "source_digest": inventory.digest,
        "semantics": {
            "import_reachability_is_static_and_bounded": True,
            "unique_symbol_calls_are_hints_not_complete_call_graph_proof": True,
            "dynamic_dispatch_and_generated_routes_require_manual_review": True,
        },
        "summary": {
            "symbols": len(definitions),
            "local_imports": len(imports),
            "resolved_calls": len(calls),
            "route_symbol_edges": len(route_symbol_edges),
            "route_reachable_files": sum(bool(value) for value in reachable_routes_by_file.values()),
        },
        "symbols": definitions,
        "imports": imports,
        "calls": calls,
        "route_symbol_edges": route_symbol_edges,
        "reachable_routes_by_file": {
            path: sorted(route_ids) for path, route_ids in sorted(reachable_routes_by_file.items())
        },
    }
    return TopologyResult(
        artifact=artifact,
        reachable_routes_by_file={
            path: sorted(route_ids) for path, route_ids in reachable_routes_by_file.items()
        },
    )
