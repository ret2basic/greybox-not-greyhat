from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .inventory import InventoryResult
from .lexing import mask_non_code, match_starts_in_code
from .models import Location, Route
from .util import redact_snippet, stable_id

ENTRY_METHODS = {
    "GET",
    "HEAD",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
    "WS",
    "ACTION",
    "GRAPHQL",
}
STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE", "WS", "ACTION"}

SECURITY_SIGNAL_PATTERNS: dict[str, tuple[str, ...]] = {
    "authentication": (
        r"\bauth(?:enticate|entication)?\b",
        r"\bsession\b",
        r"\bpassport\b",
        r"\bcurrent_user\b",
        r"\bget_current_user\b",
        r"\bsecuritycontext\b",
        r"\buserprincip",
    ),
    "authorization": (
        r"\bauthoriz",
        r"\bpermission",
        r"\bpolicy\b",
        r"\bcan\(",
        r"\bhasrole\b",
        r"\bhaspermission\b",
        r"\bownership\b",
        r"\btenant[_-]?id\b",
    ),
    "validation": (
        r"\bzod\b",
        r"\bjoi\b",
        r"\bvalidate",
        r"\bschema\.(?:parse|safeparse)",
        r"\bpydantic\b",
        r"\bserializer\b",
        r"\bformrequest\b",
    ),
    "csrf": (r"\bcsrf\b", r"\bxsrf\b"),
    "rate-limit": (r"\brate.?limit", r"\bthrottl"),
    "signature": (r"\bsignature\b", r"\bhmac\b", r"\bverify[_-]?(?:webhook|signature)"),
    "ownership": (r"\bowner(?:ship|_id|id)?\b", r"\baccount[_-]?id\b", r"\btenant[_-]?id\b"),
}


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _code_matches(
    pattern: str | re.Pattern[str],
    text: str,
    masked: str,
    flags: int = 0,
):
    matches = pattern.finditer(text) if isinstance(pattern, re.Pattern) else re.finditer(pattern, text, flags)

    def starts_in_code(match: re.Match[str]) -> bool:
        offset = match.start()
        while offset < match.end() and text[offset].isspace():
            offset += 1
        return match_starts_in_code(masked, offset)

    return (match for match in matches if starts_in_code(match))


def _signals(text: str) -> list[str]:
    lowered = text.lower()
    return [
        signal
        for signal, patterns in SECURITY_SIGNAL_PATTERNS.items()
        if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in patterns)
    ]


def _dynamic_parameters(path: str) -> list[str]:
    values: list[str] = []
    patterns = (
        r"\[+\.{3}([A-Za-z0-9_]+)\]+",
        r"\[([A-Za-z0-9_]+)\]",
        r":([A-Za-z0-9_]+)",
        r"<(?:[^:>]*:)?([A-Za-z0-9_]+)>",
        r"\{([A-Za-z0-9_]+)\}",
    )
    for pattern in patterns:
        values.extend(re.findall(pattern, path))
    return sorted(set(value for value in values if value))


def _route(
    *,
    framework: str,
    methods: Iterable[str],
    path: str,
    source_path: str,
    line: int,
    handler: str | None,
    snippet: str,
    signals: list[str],
    source_kind: str = "declared-route",
    state_changing_override: bool | None = None,
) -> Route:
    normalized_methods = sorted({method.upper() for method in methods if method.upper() in ENTRY_METHODS})
    if not normalized_methods:
        normalized_methods = ["ANY"]
    route_id = stable_id("route", framework, ",".join(normalized_methods), path, source_path, handler or "")
    return Route(
        id=route_id,
        framework=framework,
        methods=normalized_methods,
        path=path or "/",
        handler=handler,
        location=Location(source_path, line, snippet=redact_snippet(snippet.strip())),
        state_changing=(
            state_changing_override
            if state_changing_override is not None
            else bool(STATE_CHANGING_METHODS.intersection(normalized_methods) or "ANY" in normalized_methods)
        ),
        dynamic_parameters=_dynamic_parameters(path),
        security_signals=signals,
        source_kind=source_kind,
    )


def _next_app_path(source_path: str) -> str | None:
    match = re.search(
        r"(?:^|/)(?:src/)?app(?:/(.*))?/route\.(?:[cm]?[jt]sx?)$",
        source_path,
    )
    if not match:
        return None
    parts: list[str] = []
    for part in (match.group(1) or "").split("/"):
        if not part:
            continue
        if part.startswith("(") and part.endswith(")"):
            continue
        if part.startswith("@"):
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def _next_pages_path(source_path: str) -> str | None:
    match = re.search(r"(?:^|/)(?:src/)?pages/api/(.+)\.(?:[cm]?[jt]sx?)$", source_path)
    if not match:
        return None
    value = match.group(1)
    if value == "index":
        value = ""
    elif value.endswith("/index"):
        value = value[: -len("/index")]
    return "/api" + (f"/{value}" if value else "")


def _sveltekit_path(source_path: str) -> str | None:
    match = re.search(r"(?:^|/)src/routes(?:/(.*))?/\+server\.(?:[cm]?[jt]s)$", source_path)
    if not match:
        return None
    value = match.group(1) or ""
    parts = [part for part in value.split("/") if part and not (part.startswith("(") and part.endswith(")"))]
    return "/" + "/".join(parts)


def _discover_next_routes(path: str, text: str, masked: str, signals: list[str]) -> list[Route]:
    routes: list[Route] = []
    app_path = _next_app_path(path)
    if app_path:
        patterns = (
            r"\bexport\s+(?:async\s+)?function\s+(GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)\b",
            r"\bexport\s+const\s+(GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)\s*=",
        )
        for pattern in patterns:
            for match in _code_matches(pattern, text, masked):
                line = _line_number(text, match.start())
                routes.append(
                    _route(
                        framework="nextjs",
                        methods=[match.group(1)],
                        path=app_path,
                        source_path=path,
                        line=line,
                        handler=match.group(1),
                        snippet=text.splitlines()[line - 1],
                        signals=signals,
                        source_kind="nextjs-app-router",
                    )
                )
        if not routes:
            routes.append(
                _route(
                    framework="nextjs",
                    methods=["ANY"],
                    path=app_path,
                    source_path=path,
                    line=1,
                    handler=None,
                    snippet=path,
                    signals=signals,
                    source_kind="nextjs-app-router-unresolved",
                )
            )

    pages_path = _next_pages_path(path)
    if pages_path:
        method_matches = re.findall(
            r"(?:req|request)\.method\s*(?:===|==|!==|!=)\s*['\"]([A-Za-z]+)['\"]",
            text,
        )
        routes.append(
            _route(
                framework="nextjs",
                methods=method_matches or ["ANY"],
                path=pages_path,
                source_path=path,
                line=1,
                handler="default",
                snippet=path,
                signals=signals,
                source_kind="nextjs-pages-api",
            )
        )
    return routes


JS_ROUTE_PATTERN = re.compile(
    r"\b(?P<object>app|router|server|fastify)\s*\.\s*"
    r"(?P<method>get|head|post|put|patch|delete|options|all|ws)\s*\(\s*"
    r"(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)"
    r"(?:\s*,\s*(?P<handler>[A-Za-z_$][\w$]*))?",
    re.IGNORECASE,
)

PYTHON_ROUTE_PATTERN = re.compile(
    r"@(?P<object>[A-Za-z_][\w.]*)\."
    r"(?P<method>get|head|post|put|patch|delete|options|route|websocket)\s*\(\s*"
    r"(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)"
    r"(?P<rest>[^)]*)\)",
    re.IGNORECASE,
)

PHP_ROUTE_PATTERN = re.compile(
    r"\bRoute::(?P<method>get|post|put|patch|delete|options|any|match)\s*\(\s*"
    r"(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)",
    re.IGNORECASE,
)

GO_ROUTE_PATTERN = re.compile(
    r"\b(?P<object>[A-Za-z_]\w*)\."
    r"(?P<method>GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)\s*\(\s*"
    r"(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)",
)

GO_STD_ROUTE_PATTERN = re.compile(r"\bhttp\.HandleFunc\s*\(\s*(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)")

RUST_AXUM_PATTERN = re.compile(
    r"\.route\s*\(\s*\"(?P<path>[^\"]+)\"\s*,\s*"
    r"(?P<method>get|post|put|patch|delete|head|options)\s*\(\s*(?P<handler>[A-Za-z_]\w*)",
    re.IGNORECASE,
)

RUST_ACTIX_PATTERN = re.compile(
    r"#\[(?P<method>get|post|put|patch|delete|head)\s*\(\s*\"(?P<path>[^\"]+)\"\s*\)\]",
    re.IGNORECASE,
)

SPRING_METHOD_PATTERN = re.compile(
    r"@(?P<method>Get|Post|Put|Patch|Delete|Request)Mapping\s*\(\s*"
    r"(?:(?:value|path)\s*=\s*)?(?P<quote>['\"])(?P<path>[^'\"]*)(?P=quote)",
)

RUBY_ROUTE_PATTERN = re.compile(
    r"^\s*(?P<method>get|post|put|patch|delete)\s+"
    r"(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)",
    re.MULTILINE,
)

DJANGO_ROUTE_PATTERN = re.compile(
    r"\b(?:path|re_path)\s*\(\s*(?P<quote>['\"])(?P<path>[^'\"]*)(?P=quote)"
    r"\s*,\s*(?P<handler>[A-Za-z_][\w.]*)",
)

NEST_CONTROLLER_PATTERN = re.compile(
    r"@Controller\s*\(\s*(?:(?P<quote>['\"])(?P<path>[^'\"]*)(?P=quote))?\s*\)",
)

NEST_METHOD_PATTERN = re.compile(
    r"@(?P<method>Get|Post|Put|Patch|Delete|Options|Head|All)\s*\(\s*"
    r"(?:(?P<quote>['\"])(?P<path>[^'\"]*)(?P=quote))?\s*\)",
)

GRAPHQL_MAP_PATTERN = re.compile(
    r"(?P<type>Query|Mutation)\s*:\s*\{(?P<body>.*?)\n\s*\}",
    re.DOTALL,
)

GRAPHQL_FIELD_PATTERN = re.compile(
    r"^\s*(?P<field>[A-Za-z_]\w*)\s*(?::|\()",
    re.MULTILINE,
)


def _discover_pattern_routes(
    path: str,
    text: str,
    masked: str,
    language: str,
    signals: list[str],
) -> list[Route]:
    routes: list[Route] = []
    if language in {"javascript", "typescript"}:
        for match in _code_matches(JS_ROUTE_PATTERN, text, masked):
            method = match.group("method").upper()
            if method == "WS":
                framework = "express-ws"
            else:
                framework = "fastify" if match.group("object").lower() in {"server", "fastify"} else "express"
            line = _line_number(text, match.start())
            routes.append(
                _route(
                    framework=framework,
                    methods=["ANY" if method == "ALL" else method],
                    path=match.group("path"),
                    source_path=path,
                    line=line,
                    handler=match.group("handler"),
                    snippet=text.splitlines()[line - 1],
                    signals=signals,
                )
            )
    elif language == "python":
        lines = text.splitlines()
        for match in _code_matches(PYTHON_ROUTE_PATTERN, text, masked):
            method = match.group("method").upper()
            rest = match.group("rest")
            methods = [method]
            if method == "ROUTE":
                methods = re.findall(r"['\"](GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)['\"]", rest, re.I) or [
                    "ANY"
                ]
            elif method == "WEBSOCKET":
                methods = ["WS"]
            line = _line_number(text, match.start())
            following = lines[line] if line < len(lines) else ""
            handler_match = re.search(r"(?:async\s+)?def\s+([A-Za-z_]\w*)", following)
            object_name = match.group("object").lower()
            flask_source = bool(re.search(r"\bfrom\s+flask\b|\bFlask\s*\(", text))
            framework = (
                "flask" if flask_source or (method == "ROUTE" and "router" not in object_name) else "fastapi"
            )
            routes.append(
                _route(
                    framework=framework,
                    methods=methods,
                    path=match.group("path"),
                    source_path=path,
                    line=line,
                    handler=handler_match.group(1) if handler_match else None,
                    snippet=lines[line - 1],
                    signals=signals,
                )
            )
    elif language == "php":
        for match in _code_matches(PHP_ROUTE_PATTERN, text, masked):
            line = _line_number(text, match.start())
            method = match.group("method").upper()
            routes.append(
                _route(
                    framework="laravel",
                    methods=["ANY" if method in {"ANY", "MATCH"} else method],
                    path=match.group("path"),
                    source_path=path,
                    line=line,
                    handler=None,
                    snippet=text.splitlines()[line - 1],
                    signals=signals,
                )
            )
    elif language == "go":
        for match in _code_matches(GO_ROUTE_PATTERN, text, masked):
            line = _line_number(text, match.start())
            routes.append(
                _route(
                    framework="go-router",
                    methods=[match.group("method")],
                    path=match.group("path"),
                    source_path=path,
                    line=line,
                    handler=None,
                    snippet=text.splitlines()[line - 1],
                    signals=signals,
                )
            )
        for match in _code_matches(GO_STD_ROUTE_PATTERN, text, masked):
            line = _line_number(text, match.start())
            routes.append(
                _route(
                    framework="net-http",
                    methods=["ANY"],
                    path=match.group("path"),
                    source_path=path,
                    line=line,
                    handler=None,
                    snippet=text.splitlines()[line - 1],
                    signals=signals,
                )
            )
    elif language == "rust":
        for pattern, framework in ((RUST_AXUM_PATTERN, "axum"), (RUST_ACTIX_PATTERN, "actix-web")):
            for match in _code_matches(pattern, text, masked):
                line = _line_number(text, match.start())
                routes.append(
                    _route(
                        framework=framework,
                        methods=[match.group("method")],
                        path=match.group("path"),
                        source_path=path,
                        line=line,
                        handler=match.groupdict().get("handler"),
                        snippet=text.splitlines()[line - 1],
                        signals=signals,
                    )
                )
    elif language in {"java", "kotlin"}:
        for match in _code_matches(SPRING_METHOD_PATTERN, text, masked):
            line = _line_number(text, match.start())
            method = match.group("method").upper()
            routes.append(
                _route(
                    framework="spring",
                    methods=["ANY" if method == "REQUEST" else method],
                    path=match.group("path") or "/",
                    source_path=path,
                    line=line,
                    handler=None,
                    snippet=text.splitlines()[line - 1],
                    signals=signals,
                )
            )
    elif language == "ruby":
        for match in _code_matches(RUBY_ROUTE_PATTERN, text, masked):
            line = _line_number(text, match.start())
            routes.append(
                _route(
                    framework="rails",
                    methods=[match.group("method")],
                    path=match.group("path"),
                    source_path=path,
                    line=line,
                    handler=None,
                    snippet=text.splitlines()[line - 1],
                    signals=signals,
                )
            )
    return routes


def _join_route_path(prefix: str, suffix: str) -> str:
    parts = [part.strip("/") for part in (prefix, suffix) if part.strip("/")]
    return "/" + "/".join(parts)


def _discover_special_entrypoints(
    path: str,
    text: str,
    masked: str,
    language: str,
    signals: list[str],
) -> list[Route]:
    routes: list[Route] = []
    lines = text.splitlines()

    svelte_path = _sveltekit_path(path)
    if svelte_path:
        for match in _code_matches(
            r"\bexport\s+(?:async\s+)?function\s+(GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)\b"
            r"|\bexport\s+const\s+(GET|HEAD|POST|PUT|PATCH|DELETE|OPTIONS)\s*=",
            text,
            masked,
        ):
            method = match.group(1) or match.group(2)
            line = _line_number(text, match.start())
            routes.append(
                _route(
                    framework="sveltekit",
                    methods=[method],
                    path=svelte_path,
                    source_path=path,
                    line=line,
                    handler=method,
                    snippet=lines[line - 1],
                    signals=signals,
                    source_kind="sveltekit-server-route",
                )
            )

    first_meaningful = "\n".join(lines[:20])
    if re.search(r"^\s*['\"]use server['\"]\s*;?", first_meaningful, re.MULTILINE):
        for match in _code_matches(
            r"\bexport\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\b"
            r"|\bexport\s+const\s+([A-Za-z_$][\w$]*)\s*=",
            text,
            masked,
        ):
            name = match.group(1) or match.group(2)
            line = _line_number(text, match.start())
            routes.append(
                _route(
                    framework="nextjs",
                    methods=["ACTION"],
                    path=f"action://{path}#{name}",
                    source_path=path,
                    line=line,
                    handler=name,
                    snippet=lines[line - 1],
                    signals=signals,
                    source_kind="nextjs-server-action",
                    state_changing_override=True,
                )
            )

    if language in {"javascript", "typescript"}:
        controller = next(_code_matches(NEST_CONTROLLER_PATTERN, text, masked), None)
        if controller:
            prefix = controller.group("path") or ""
            for match in _code_matches(NEST_METHOD_PATTERN, text, masked):
                method = match.group("method").upper()
                suffix = match.group("path") or ""
                line = _line_number(text, match.start())
                routes.append(
                    _route(
                        framework="nestjs",
                        methods=["ANY" if method == "ALL" else method],
                        path=_join_route_path(prefix, suffix),
                        source_path=path,
                        line=line,
                        handler=None,
                        snippet=lines[line - 1],
                        signals=signals,
                    )
                )

        for type_match in _code_matches(GRAPHQL_MAP_PATTERN, text, masked):
            operation_type = type_match.group("type")
            body = type_match.group("body")
            body_offset = type_match.start("body")
            masked_body = masked[body_offset : body_offset + len(body)]
            for field_match in _code_matches(GRAPHQL_FIELD_PATTERN, body, masked_body):
                field = field_match.group("field")
                absolute_offset = body_offset + field_match.start()
                line = _line_number(text, absolute_offset)
                routes.append(
                    _route(
                        framework="graphql",
                        methods=["GRAPHQL"],
                        path=f"graphql://{operation_type}/{field}",
                        source_path=path,
                        line=line,
                        handler=field,
                        snippet=lines[line - 1],
                        signals=signals,
                        source_kind=f"graphql-{operation_type.lower()}",
                        state_changing_override=operation_type == "Mutation",
                    )
                )

        for match in _code_matches(
            r"\b(?:server|wss)\.on\s*\(\s*['\"](?:upgrade|connection)['\"]",
            text,
            masked,
        ):
            line = _line_number(text, match.start())
            routes.append(
                _route(
                    framework="websocket",
                    methods=["WS"],
                    path=f"websocket://{path}#{line}",
                    source_path=path,
                    line=line,
                    handler=None,
                    snippet=lines[line - 1],
                    signals=signals,
                    source_kind="websocket-handler",
                    state_changing_override=True,
                )
            )

    if language == "python":
        for match in _code_matches(DJANGO_ROUTE_PATTERN, text, masked):
            line = _line_number(text, match.start())
            routes.append(
                _route(
                    framework="django",
                    methods=["ANY"],
                    path="/" + match.group("path").lstrip("/"),
                    source_path=path,
                    line=line,
                    handler=match.group("handler"),
                    snippet=lines[line - 1],
                    signals=signals,
                    source_kind="django-urlpattern",
                )
            )
        for match in _code_matches(
            r"@(?:strawberry\.)?(?P<type>mutation|field)\b.*?\n\s*(?:async\s+)?def\s+(?P<field>[A-Za-z_]\w*)",
            text,
            masked,
            re.DOTALL,
        ):
            operation_type = "Mutation" if match.group("type") == "mutation" else "Query"
            line = _line_number(text, match.start())
            routes.append(
                _route(
                    framework="graphql",
                    methods=["GRAPHQL"],
                    path=f"graphql://{operation_type}/{match.group('field')}",
                    source_path=path,
                    line=line,
                    handler=match.group("field"),
                    snippet=lines[line - 1],
                    signals=signals,
                    source_kind=f"graphql-{operation_type.lower()}",
                    state_changing_override=operation_type == "Mutation",
                )
            )
    return routes


def discover_routes(inventory: InventoryResult) -> list[Route]:
    file_by_path = {file.path: file for file in inventory.files}
    routes: list[Route] = []
    for path, text in inventory.texts.items():
        source_file = file_by_path[path]
        if source_file.manifest or source_file.generated:
            continue
        masked = mask_non_code(text, source_file.language)
        signals = _signals(masked)
        routes.extend(_discover_next_routes(path, text, masked, signals))
        routes.extend(_discover_pattern_routes(path, text, masked, source_file.language, signals))
        routes.extend(_discover_special_entrypoints(path, text, masked, source_file.language, signals))

    deduped: dict[str, Route] = {}
    for route in routes:
        deduped[route.id] = route
    return sorted(
        deduped.values(),
        key=lambda item: (item.location.path, item.location.line, item.path, item.methods),
    )


def routes_artifact(routes: list[Route], source_digest: str) -> dict[str, Any]:
    frameworks: dict[str, int] = {}
    for route in routes:
        frameworks[route.framework] = frameworks.get(route.framework, 0) + 1
    return {
        "schema_version": 2,
        "source_digest": source_digest,
        "summary": {
            "routes": len(routes),
            "state_changing": sum(route.state_changing for route in routes),
            "dynamic_parameter_routes": sum(bool(route.dynamic_parameters) for route in routes),
            "frameworks": dict(sorted(frameworks.items())),
        },
        "routes": [route.to_dict() for route in routes],
    }
