#!/usr/bin/env python3
"""InferForge local greybox runner.

This intentionally stays small and dependency-free: Burp remains the security
workbench, while this script records repeatable local probes and source peeks.
"""

from __future__ import annotations

import argparse
import ast
import base64
import contextlib
from email.utils import parsedate_to_datetime
import hashlib
import html
import http.client
import inspect
import io
import ipaddress
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = "http://127.0.0.1:3100"
DEFAULT_ARTIFACT_DIR = ROOT / ".greybox"
DEFAULT_SOURCE_ROOT = ROOT / "infrafi-web"
DEFAULT_PROFILE_PATH = ROOT / "profiles/infrafi-web.json"
DEFAULT_NODE = "/home/ret2basic/.npm/_npx/52027bd8fc0022aa/node_modules/node/bin/node"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDTEL_MINT = "dawn7ZUF7h7anFuEsDdAU1Y3HYwikwqNMAENZsQJdNL"
DEFAULT_TEST_WALLET = "EzDmLUHTj53mSLN4BBrsuW8w3Gvc1iDGiYCXrkwm4vrR"
PLACEHOLDER_REAL_WALLET = "REPLACE_WITH_REAL_WALLET"
PLACEHOLDER_APPROVED_POOL_ADDRESS = "REPLACE_WITH_APPROVED_POOL_ADDRESS"
PLACEHOLDER_APPROVED_CONCRETE_PATH = "REPLACE_WITH_APPROVED_CONCRETE_LOCAL_PATH"
MAX_RESPONSE_BYTES = 256 * 1024
MAX_BODY_SAMPLE_CHARS = 1200
MAX_REQUEST_CONTEXTS_PER_ENDPOINT = 6
REDACTED_VALUE = "[redacted]"
BASE64_CANDIDATE_RE = re.compile(r"(?<![A-Za-z0-9+/=])([A-Za-z0-9+/]{80,}={0,2})(?![A-Za-z0-9+/=])")
PLACEHOLDER_ENV_RE = re.compile(r"^YOUR_[A-Z0-9_]+_HERE$", re.IGNORECASE)
COMMAND_PLACEHOLDER_RE = re.compile(r"REPLACE_WITH_[A-Z0-9_]+")
MANIFEST_NAME = "artifact-manifest.json"
TARGET_PROFILE_ARTIFACT = "target-profile.json"
STRATEGY_REGISTRY_ARTIFACT = "strategy-registry.json"
PROFILE_VALIDATION_ARTIFACT = "profile-validation.json"
ROUTE_INVENTORY_ARTIFACT = "route-inventory.json"
DISCOVERED_PROFILE_ARTIFACT = "discovered-profile.json"
DISCOVERY_COVERAGE_ARTIFACT = "discovery-coverage.json"
DISCOVERY_COVERAGE_SELFTEST_ARTIFACT = "discovery-coverage-selftest.json"
REVIEW_BLOCKERS_ARTIFACT = "review-blockers.json"
REVIEW_BLOCKERS_MARKDOWN_ARTIFACT = "review-blockers.md"
REVIEW_BLOCKERS_SELFTEST_ARTIFACT = "review-blockers-selftest.json"
COMMAND_SAFETY_SELFTEST_ARTIFACT = "command-safety-selftest.json"
ARTIFACT_HEALTH_SELFTEST_ARTIFACT = "artifact-health-selftest.json"
MANIFEST_REFRESH_SELFTEST_ARTIFACT = "manifest-refresh-selftest.json"
NO_WRITE_SELFTEST_ARTIFACT = "no-write-selftest.json"
REQUIRED_ARTIFACTS = [
    "index.html",
    "report.md",
    "reproduction-steps.md",
    TARGET_PROFILE_ARTIFACT,
    STRATEGY_REGISTRY_ARTIFACT,
    PROFILE_VALIDATION_ARTIFACT,
    "config.json",
    "endpoint-clusters.json",
    "probe-plan.json",
    "probe-ranking.json",
    "probe-results.jsonl",
    "response-delta-analysis.json",
    "warmup-results.json",
    "traffic-index.json",
    "source-peek-requests.json",
    "source-peek-results.json",
    "burp-capabilities.json",
    "burp-history-observations.jsonl",
    "burp-observation-run.json",
    "burp-observation-coverage.json",
    "blackbox-coverage.json",
    "evidence-chain.json",
    "evidence-appendix.json",
    "verification-queue.json",
    "adjudication.json",
    "finding-gate.json",
    "findings.json",
    "hardening-notes.json",
    "evidence-gaps.json",
    "rpc-method-policy.json",
    "transaction-intent.json",
    "transaction-decoder-selftest.json",
    "quote-collection.json",
]
REVIEW_ARTIFACTS = [
    "review-observation-candidates.json",
    "reviewed-profile.json",
    "reviewed-profile-validation.json",
    "reviewed-observation-promotion.json",
]
DISCOVERY_ARTIFACTS = [
    ROUTE_INVENTORY_ARTIFACT,
    DISCOVERED_PROFILE_ARTIFACT,
    "discovered-profile-validation.json",
    DISCOVERY_COVERAGE_ARTIFACT,
]
KNOWN_OPTIONAL_ARTIFACTS = [
    *DISCOVERY_ARTIFACTS,
    *REVIEW_ARTIFACTS,
    "attack-strategy.json",
    "burp-mcp-sync.json",
    "burp-mcp-history-latest.txt",
    "burp-mcp-websocket-history-latest.txt",
    "burp-transaction-candidates.json",
    "collection-summary.json",
    "environment-readiness.json",
    "artifact-health.json",
    "regression-suite.json",
    "orca-baseline.json",
    REVIEW_BLOCKERS_ARTIFACT,
    REVIEW_BLOCKERS_MARKDOWN_ARTIFACT,
    "profile-routing-selftest.json",
    DISCOVERY_COVERAGE_SELFTEST_ARTIFACT,
    REVIEW_BLOCKERS_SELFTEST_ARTIFACT,
    COMMAND_SAFETY_SELFTEST_ARTIFACT,
    ARTIFACT_HEALTH_SELFTEST_ARTIFACT,
    MANIFEST_REFRESH_SELFTEST_ARTIFACT,
    NO_WRITE_SELFTEST_ARTIFACT,
    "transaction-intent-policy.json",
]
REPORT_FRESHNESS_INPUTS = [
    "verification-queue.json",
    REVIEW_BLOCKERS_ARTIFACT,
    REVIEW_BLOCKERS_MARKDOWN_ARTIFACT,
    "attack-strategy.json",
    "blackbox-coverage.json",
    "burp-observation-coverage.json",
    DISCOVERY_COVERAGE_ARTIFACT,
    "response-delta-analysis.json",
    "source-peek-requests.json",
    "evidence-chain.json",
    "evidence-appendix.json",
    "adjudication.json",
    "environment-readiness.json",
    "transaction-intent.json",
    "finding-gate.json",
    "hardening-notes.json",
    "probe-results.jsonl",
    "burp-history-observations.jsonl",
]
DERIVED_ARTIFACT_FRESHNESS_RULES = [
    {
        "outputs": ["report.md", "index.html"],
        "inputs": REPORT_FRESHNESS_INPUTS,
        "reason": "derived-report-stale",
        "next_step": "Run `python3 scripts/inferforge.py report` for this artifact directory.",
    },
    {
        "outputs": ["reproduction-steps.md"],
        "inputs": ["verification-queue.json"],
        "reason": "derived-reproduction-steps-stale",
        "next_step": "Run `python3 scripts/inferforge.py verification-queue` for this artifact directory.",
    },
    {
        "outputs": [REVIEW_BLOCKERS_MARKDOWN_ARTIFACT],
        "inputs": [REVIEW_BLOCKERS_ARTIFACT],
        "reason": "derived-review-blockers-markdown-stale",
        "next_step": "Run `python3 scripts/inferforge.py review-blockers` for this artifact directory.",
    },
]
INDEX_ARTIFACT_ORDER = [
    "report.md",
    MANIFEST_NAME,
    "artifact-health.json",
    "regression-suite.json",
    REVIEW_BLOCKERS_ARTIFACT,
    REVIEW_BLOCKERS_MARKDOWN_ARTIFACT,
    DISCOVERY_COVERAGE_ARTIFACT,
    DISCOVERY_COVERAGE_SELFTEST_ARTIFACT,
    REVIEW_BLOCKERS_SELFTEST_ARTIFACT,
    COMMAND_SAFETY_SELFTEST_ARTIFACT,
    ARTIFACT_HEALTH_SELFTEST_ARTIFACT,
    MANIFEST_REFRESH_SELFTEST_ARTIFACT,
    NO_WRITE_SELFTEST_ARTIFACT,
    TARGET_PROFILE_ARTIFACT,
    STRATEGY_REGISTRY_ARTIFACT,
    PROFILE_VALIDATION_ARTIFACT,
    *DISCOVERY_ARTIFACTS,
    *REVIEW_ARTIFACTS,
    "config.json",
    "collection-summary.json",
    "endpoint-clusters.json",
    "probe-plan.json",
    "probe-ranking.json",
    "probe-results.jsonl",
    "response-delta-analysis.json",
    "warmup-results.json",
    "traffic-index.json",
    "source-peek-requests.json",
    "source-peek-results.json",
    "attack-strategy.json",
    "burp-capabilities.json",
    "burp-history-observations.jsonl",
    "burp-observation-run.json",
    "burp-observation-coverage.json",
    "burp-mcp-sync.json",
    "burp-mcp-history-latest.txt",
    "burp-mcp-websocket-history-latest.txt",
    "burp-transaction-candidates.json",
    "blackbox-coverage.json",
    "evidence-chain.json",
    "evidence-appendix.json",
    "verification-queue.json",
    "reproduction-steps.md",
    "adjudication.json",
    "finding-gate.json",
    "findings.json",
    "hardening-notes.json",
    "suspicions.json",
    "evidence-gaps.json",
    "rpc-method-policy.json",
    "transaction-intent.json",
    "transaction-decoder-selftest.json",
    "transaction-intent-policy.json",
    "quote-collection.json",
    "orca-baseline.json",
]
MANUAL_PLACEHOLDER_TOKENS = [
    PLACEHOLDER_REAL_WALLET,
    PLACEHOLDER_APPROVED_POOL_ADDRESS,
    PLACEHOLDER_APPROVED_CONCRETE_PATH,
    "REPLACE_WITH_",
]
SERVER_ACTION_REVIEW_KEYWORDS = {
    "approve",
    "burn",
    "create",
    "delete",
    "insert",
    "mint",
    "mutate",
    "pay",
    "remove",
    "send",
    "sign",
    "submit",
    "swap",
    "transfer",
    "update",
    "upsert",
    "withdraw",
}
STRATEGY_REGISTRY: dict[str, dict[str, Any]] = {
    "nextjs-api-routes": {
        "title": "Next.js API route baseline",
        "description": "Baseline local route availability, CORS preflight, and low-risk method handling for profile-defined Next.js routes.",
        "cluster_ids": ["health"],
        "probe_categories": ["health", "profile-defined-nextjs-api-routes"],
        "safety": "Local health, HEAD/OPTIONS, and GET method-confusion checks only.",
    },
    "solana-json-rpc-proxy": {
        "title": "Solana JSON-RPC proxy controls",
        "description": "Origin, method, content-type, JSON shape, batch, transaction-method, and WebSocket policy probes.",
        "cluster_ids": ["solana-rpc-http", "solana-rpc-ws"],
        "probe_categories": ["solana-rpc-http", "solana-rpc-ws"],
        "safety": "Uses invalid transaction payloads only; no signing or submission.",
    },
    "quote-transaction-decoder": {
        "title": "Quote orchestration and transaction decoding",
        "description": "Quote route validation, quote corpus collection hooks, and inspect-only Solana transaction decoding.",
        "cluster_ids": ["quote"],
        "probe_categories": ["quote"],
        "safety": "Quote collection and decoding only; no wallet signing or transaction submission.",
    },
    "fixed-upstream-proxy": {
        "title": "Fixed-upstream proxy boundary",
        "description": "Path, method, query, and identifier-shape checks for bounded fixed-upstream proxy routes.",
        "cluster_ids": ["orca-pools"],
        "probe_categories": ["orca-pools"],
        "safety": "Invalid-shape probes and optional single known-address baseline only; no upstream enumeration.",
    },
}
SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "proxy-authorization",
    "set-cookie",
    "x-api-key",
    "x-m0-api-key",
}
SECRET_TEXT_RE = re.compile(
    r"(?i)(authorization\s*[:=]\s*bearer\s+)[^,\s\"']+|"
    r"((?:api[_-]?key|token|secret|password|cookie)\s*[:=]\s*)[^,\s\"';&]+"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=False) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def load_optional_json(path: Path) -> dict[str, Any] | None:
    return json.loads(read_text(path)) if path.exists() else None


def json_clone(data: Any) -> Any:
    return json.loads(json.dumps(data))


def concrete_local_path_problem(path: Any) -> str | None:
    if not isinstance(path, str):
        return "path must be a string"
    if not path:
        return "path is empty"
    if any(token and token in path for token in MANUAL_PLACEHOLDER_TOKENS):
        return "path still contains a manual REPLACE_WITH_* placeholder"
    parsed = urllib.parse.urlparse(path)
    if parsed.scheme or parsed.netloc:
        return "full URLs are not allowed; use a local path beginning with /"
    if not path.startswith("/") or path.startswith("//"):
        return "path must be a local absolute path beginning with a single /"
    if "{" in path or "}" in path:
        return "path contains template braces and is not concrete"
    if "<" in path or ">" in path:
        return "path contains angle-bracket placeholder text"
    if re.search(r"\s", path):
        return "path contains whitespace"
    return None


def is_active_observation_item(item: dict[str, Any]) -> bool:
    return not (
        item.get("enabled") is False
        or item.get("review_only")
        or item.get("status") == "review-only"
    )


def active_observation_label(item: dict[str, Any], index: int) -> str:
    return str(item.get("id") or f"index-{index}")


def default_target_profile() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "infrafi-web",
        "display_name": "InfraFi Web",
        "description": "Default regression target used to develop InferForge as a reusable Burp-first greybox tool.",
        "target_type": "nextjs-web3-defi-app",
        "frameworks": ["Next.js App Router", "Solana", "M0 orchestration", "Orca"],
        "default_target": DEFAULT_TARGET,
        "default_source_root": "infrafi-web",
        "strategy_sets": [
            "nextjs-api-routes",
            "solana-json-rpc-proxy",
            "quote-transaction-decoder",
            "fixed-upstream-proxy",
        ],
        "safety": {
            "no_wallet_signing": True,
            "no_transaction_submission": True,
            "no_burp_scanner": True,
            "no_broad_fuzzing": True,
            "prefer_loopback_targets": True,
        },
        "probe_targets": {
            "health": {
                "path": "/health",
            },
            "quote": {
                "path": "/api/quote",
            },
            "solana-rpc-http": {
                "path": "/api/rpc/solana/devnet",
                "root_path": "/api/rpc",
                "unknown_cluster_path": "/api/rpc/solana/localnet",
                "cluster": "devnet",
                "unknown_cluster": "localnet",
            },
            "solana-rpc-ws": {
                "path": "/api/rpc/solana/devnet",
            },
            "orca-pools": {
                "path_template": "/api/orca/pools/{address}",
                "invalid_address_path": "/api/orca/pools/not-an-address",
                "invalid_base58_path": "/api/orca/pools/0OIlnotbase58",
                "too_short_path": "/api/orca/pools/1111111111111111111111111111111",
                "too_long_path": "/api/orca/pools/111111111111111111111111111111111111111111111",
                "encoded_traversal_path": "/api/orca/pools/%2e%2e%2fhealth",
                "extra_segment_path": "/api/orca/pools/not-an-address/extra",
                "query_injection_path": "/api/orca/pools/not-an-address?url=https://evil.example",
            },
        },
        "clusters": [
            {
                "id": "health",
                "method": "GET",
                "path": "/health",
                "kind": "health",
                "priority": "low",
                "strategy_set": "nextjs-api-routes",
                "match": {"methods": ["GET"], "paths": ["/health"]},
                "source_refs": ["src/app/health/route.ts"],
            },
            {
                "id": "solana-rpc-http",
                "method": "POST",
                "path": "/api/rpc/solana/{cluster}",
                "kind": "json-rpc-proxy",
                "priority": "high",
                "strategy_set": "solana-json-rpc-proxy",
                "match": {
                    "path_prefixes": ["/api/rpc/solana/"],
                    "paths": ["/api/rpc"],
                    "exclude_methods": ["WS"],
                },
                "source_refs": [
                    "src/app/api/rpc/_shared.ts",
                    "src/app/api/rpc/route.ts",
                    "src/app/api/rpc/solana/[cluster]/route.ts",
                ],
            },
            {
                "id": "solana-rpc-ws",
                "method": "WS",
                "path": "/api/rpc/solana/{cluster}",
                "kind": "websocket-json-rpc-proxy",
                "priority": "high",
                "strategy_set": "solana-json-rpc-proxy",
                "match": {
                    "methods": ["WS"],
                    "path_prefixes": ["/api/rpc/solana/"],
                },
                "source_refs": ["server.js"],
            },
            {
                "id": "quote",
                "method": "POST",
                "path": "/api/quote",
                "kind": "orchestration-proxy",
                "priority": "high",
                "strategy_set": "quote-transaction-decoder",
                "match": {"paths": ["/api/quote"]},
                "source_refs": ["src/app/api/quote/route.ts", "src/lib/m0.ts"],
            },
            {
                "id": "orca-pools",
                "method": "GET",
                "path": "/api/orca/pools/{address}",
                "kind": "fixed-upstream-proxy",
                "priority": "medium",
                "strategy_set": "fixed-upstream-proxy",
                "match": {"path_prefixes": ["/api/orca/pools/"]},
                "source_refs": ["src/app/api/orca/pools/[address]/route.ts"],
            },
        ],
        "source_peeks": [
            {
                "endpoint": "POST /api/rpc and /api/rpc/solana/[cluster]",
                "cluster_ids": ["solana-rpc-http"],
                "files": [
                    "src/app/api/rpc/_shared.ts",
                    "src/app/api/rpc/route.ts",
                ],
                "line_patterns": {
                    "root_route_default_cluster": {
                        "file": "src/app/api/rpc/route.ts",
                        "pattern": "handleSolanaRpc(req, 'mainnet')",
                    },
                    "allowed_methods": {
                        "file": "src/app/api/rpc/_shared.ts",
                        "pattern": "DEFAULT_ALLOWED_METHODS",
                    },
                    "transaction_method_gate": {
                        "file": "src/app/api/rpc/_shared.ts",
                        "pattern": "SOLANA_RPC_PROXY_ALLOW_TRANSACTION_METHODS",
                    },
                    "blocked_methods": {
                        "file": "src/app/api/rpc/_shared.ts",
                        "pattern": "BLOCKED_METHODS",
                    },
                    "content_type_validation": {
                        "file": "src/app/api/rpc/_shared.ts",
                        "pattern": "Unsupported content type",
                    },
                    "duplicate_key_validation": {
                        "file": "src/app/api/rpc/_shared.ts",
                        "pattern": "function findDuplicateJsonKey",
                    },
                    "payload_validation": {
                        "file": "src/app/api/rpc/_shared.ts",
                        "pattern": "function validateRpcPayload",
                    },
                    "handler": {
                        "file": "src/app/api/rpc/_shared.ts",
                        "pattern": "export async function handleSolanaRpc",
                    },
                },
                "conclusion": "RPC HTTP proxy has local source, content-type, duplicate-key, method, body, batch, and cluster controls before upstream forwarding.",
            },
            {
                "endpoint": "WS /api/rpc/solana/[cluster]",
                "cluster_ids": ["solana-rpc-ws"],
                "files": ["server.js"],
                "line_patterns": {
                    "allowed_methods": {"file": "server.js", "pattern": "WS_ALLOWED_METHODS"},
                    "batch_limit": {"file": "server.js", "pattern": "MAX_WS_BATCH_SIZE"},
                    "duplicate_key_validation": {
                        "file": "server.js",
                        "pattern": "function findDuplicateJsonKey",
                    },
                    "message_validation": {
                        "file": "server.js",
                        "pattern": "function isAllowedWsRpcMessage",
                    },
                    "origin_check": {"file": "server.js", "pattern": "function handleSolanaWsProxy"},
                    "policy_close": {
                        "file": "server.js",
                        "pattern": "Solana WS RPC method is not allowed",
                    },
                },
                "conclusion": "WS proxy performs origin, binary-frame, duplicate-key, batch-size, and method allowlist checks before forwarding messages.",
            },
            {
                "endpoint": "POST /api/quote",
                "cluster_ids": ["quote"],
                "files": ["src/app/api/quote/route.ts"],
                "line_patterns": {
                    "json_parse": {
                        "file": "src/app/api/quote/route.ts",
                        "pattern": "rawBody = await req.json()",
                    },
                    "local_validation": {
                        "file": "src/app/api/quote/route.ts",
                        "pattern": "function validateQuoteRequestBody",
                    },
                    "upstream_forward": {
                        "file": "src/app/api/quote/route.ts",
                        "pattern": "fetch(M0_QUOTE_API",
                    },
                    "upstream_error_sanitization": {
                        "file": "src/app/api/quote/route.ts",
                        "pattern": "M0 orchestration quote failed",
                    },
                    "generic_error_handler": {
                        "file": "src/app/api/quote/route.ts",
                        "pattern": "catch (err)",
                    },
                },
                "conclusion": "Quote route performs strict local schema and policy validation, forwards only normalized allowlisted bodies to M0, and avoids reflecting upstream error bodies.",
            },
            {
                "endpoint": "GET /api/orca/pools/[address]",
                "cluster_ids": ["orca-pools"],
                "files": ["src/app/api/orca/pools/[address]/route.ts"],
                "line_patterns": {
                    "address_guard": {
                        "file": "src/app/api/orca/pools/[address]/route.ts",
                        "pattern": "base58 Solana-style addresses",
                    },
                    "fixed_upstream": {
                        "file": "src/app/api/orca/pools/[address]/route.ts",
                        "pattern": "https://api.orca.so",
                    },
                },
                "conclusion": "Orca route uses a fixed upstream and rejects non-base58 address shapes.",
            },
        ],
        "burp_observation_plan": [
            {
                "id": "burp_observe_health",
                "method": "GET",
                "path": "/health",
                "headers": {"User-Agent": "InferForge-Burp-Observe/0.1"},
                "expected_statuses": [200],
                "cluster": "health",
            },
            {
                "id": "burp_observe_quote_invalid_body",
                "method": "POST",
                "path": "/api/quote",
                "headers": {
                    "User-Agent": "InferForge-Burp-Observe/0.1",
                    "Origin": "{origin}",
                    "Content-Type": "application/json",
                },
                "body": "{}",
                "expected_statuses": [400],
                "cluster": "quote",
            },
            {
                "id": "burp_observe_rpc_get_health",
                "method": "POST",
                "path": "/api/rpc/solana/devnet",
                "headers": {
                    "User-Agent": "InferForge-Burp-Observe/0.1",
                    "Origin": "{origin}",
                    "Content-Type": "application/json",
                },
                "body_json": {"jsonrpc": "2.0", "id": 1, "method": "getHealth"},
                "expected_statuses": [200],
                "cluster": "solana-rpc-http",
            },
            {
                "id": "burp_observe_orca_invalid_address",
                "method": "GET",
                "path": "/api/orca/pools/not-an-address",
                "headers": {"User-Agent": "InferForge-Burp-Observe/0.1"},
                "expected_statuses": [400],
                "cluster": "orca-pools",
            },
        ],
        "websocket_observation": {
            "id": "burp_observe_ws_upgrade",
            "path": "/api/rpc/solana/devnet",
            "cluster": "solana-rpc-ws",
            "expected_statuses": [101],
            "subscribe_method": "slotSubscribe",
        },
    }


def neutral_target_profile_defaults(
    profile: dict[str, Any],
    *,
    profile_path: Path | None = None,
) -> dict[str, Any]:
    name = str(profile.get("name") or (profile_path.stem if profile_path else "custom-target"))
    return {
        "schema_version": 1,
        "name": name,
        "display_name": str(profile.get("display_name") or name),
        "description": "",
        "target_type": "custom-web-app",
        "frameworks": [],
        "default_target": DEFAULT_TARGET,
        "default_source_root": ".",
        "strategy_sets": [],
        "safety": {
            "no_wallet_signing": True,
            "no_transaction_submission": True,
            "no_burp_scanner": True,
            "no_broad_fuzzing": True,
            "prefer_loopback_targets": True,
        },
        "probe_targets": {},
        "clusters": [],
        "source_peeks": [],
        "burp_observation_plan": [],
        "review_observation_candidates": [],
        "websocket_observation": None,
    }


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()


def public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        key: json_clone(value)
        for key, value in profile.items()
        if not str(key).startswith("_")
    }


def normalize_target_profile(profile: dict[str, Any], *, profile_path: Path | None = None) -> dict[str, Any]:
    builtin_default = not (profile_path and profile_path.exists())
    defaults = default_target_profile() if builtin_default else neutral_target_profile_defaults(profile, profile_path=profile_path)
    normalized = json_clone(profile)
    defaulted_keys: list[str] = []
    for key in [
        "schema_version",
        "name",
        "display_name",
        "description",
        "target_type",
        "frameworks",
        "default_target",
        "default_source_root",
        "strategy_sets",
        "safety",
        "probe_targets",
        "clusters",
        "source_peeks",
        "burp_observation_plan",
        "review_observation_candidates",
        "websocket_observation",
    ]:
        if key not in normalized:
            normalized[key] = json_clone(defaults[key])
            defaulted_keys.append(key)
    normalized["_profile_path"] = str(profile_path) if profile_path else "builtin-default"
    normalized["_profile_loaded_from"] = "file" if profile_path and profile_path.exists() else "builtin-default"
    normalized["_profile_defaulted_keys"] = defaulted_keys
    return normalized


def default_strategy_set_for_cluster(cluster_id: str) -> str | None:
    for strategy_id, strategy in STRATEGY_REGISTRY.items():
        if cluster_id in strategy.get("cluster_ids", []):
            return strategy_id
    return None


def enabled_strategy_set_ids(profile: dict[str, Any] | None) -> set[str]:
    if not profile:
        return set(STRATEGY_REGISTRY)
    raw = profile.get("strategy_sets")
    if raw is None:
        return set(STRATEGY_REGISTRY)
    return {str(item) for item in raw}


def strategy_set_enabled(profile: dict[str, Any] | None, strategy_set: str | None) -> bool:
    if strategy_set is None:
        return True
    return strategy_set in enabled_strategy_set_ids(profile)


def strategy_set_for_cluster(cluster: dict[str, Any]) -> str | None:
    return cluster.get("strategy_set") or default_strategy_set_for_cluster(str(cluster.get("id")))


def strategy_set_for_probe(probe: "Probe") -> str | None:
    return probe.strategy_set or default_strategy_set_for_cluster(probe.category)


def uses_builtin_target_defaults(profile: dict[str, Any] | None) -> bool:
    return not profile or profile.get("_profile_loaded_from") == "builtin-default"


def declared_cluster_by_id(profile: dict[str, Any] | None, cluster_id: str) -> dict[str, Any] | None:
    for cluster in (profile or {}).get("clusters", []):
        if str(cluster.get("id")) == cluster_id:
            return cluster
    if profile and profile.get("_profile_loaded_from") != "builtin-default":
        return None
    for cluster in default_target_profile().get("clusters", []):
        if str(cluster.get("id")) == cluster_id:
            return cluster
    return None


def render_path_template(path: str, replacements: dict[str, str] | None = None) -> str:
    rendered = str(path)
    for key, value in (replacements or {}).items():
        rendered = rendered.replace("{" + key + "}", str(value))
        rendered = rendered.replace("{" + key + "*}", str(value))
    return rendered


def cluster_default_path(
    profile: dict[str, Any] | None,
    cluster_id: str,
    fallback: str,
    replacements: dict[str, str] | None = None,
) -> str:
    cluster = declared_cluster_by_id(profile, cluster_id)
    path = str((cluster or {}).get("path") or fallback)
    return render_path_template(path, replacements)


def probe_target_config(profile: dict[str, Any] | None, cluster_id: str) -> dict[str, Any]:
    configured = (profile or {}).get("probe_targets", {}).get(cluster_id, {})
    if not isinstance(configured, dict):
        configured = {}
    if not uses_builtin_target_defaults(profile):
        return json_clone(configured)
    defaults = default_target_profile().get("probe_targets", {}).get(cluster_id, {})
    return {**json_clone(defaults), **json_clone(configured)}


def explicit_probe_target_config(profile: dict[str, Any] | None, cluster_id: str) -> dict[str, Any]:
    configured = (profile or {}).get("probe_targets", {}).get(cluster_id, {})
    return json_clone(configured) if isinstance(configured, dict) else {}


def websocket_observation_config(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if profile and "websocket_observation" in profile:
        configured = profile.get("websocket_observation")
    else:
        configured = default_target_profile().get("websocket_observation")

    if configured is None or configured is False:
        return None
    config = json_clone(configured) if isinstance(configured, dict) else {}
    if not config.get("path"):
        ws_target = explicit_probe_target_config(profile, "solana-rpc-ws")
        rpc_target = explicit_probe_target_config(profile, "solana-rpc-http")
        target_path = (ws_target or rpc_target).get("path")
        if target_path:
            config["path"] = target_path
        else:
            cluster = declared_cluster_by_id(profile, "solana-rpc-ws") or declared_cluster_by_id(profile, "solana-rpc-http")
            if cluster and cluster.get("path"):
                config["path"] = render_path_template(str(cluster["path"]), {"cluster": "devnet"})
            elif uses_builtin_target_defaults(profile):
                config["path"] = "/api/rpc/solana/devnet"
            else:
                return None
    return config


def probe_target_path(
    profile: dict[str, Any] | None,
    cluster_id: str,
    field: str,
    fallback: str,
    replacements: dict[str, str] | None = None,
) -> str:
    configured = explicit_probe_target_config(profile, cluster_id)
    value = configured.get(field)
    if value:
        return render_path_template(str(value), replacements)
    if field == "path":
        return cluster_default_path(profile, cluster_id, fallback, replacements)
    if uses_builtin_target_defaults(profile):
        value = default_target_profile().get("probe_targets", {}).get(cluster_id, {}).get(field)
        if value:
            return render_path_template(str(value), replacements)
    return render_path_template(fallback, replacements)


def rpc_probe_paths(profile: dict[str, Any] | None) -> dict[str, str]:
    config = explicit_probe_target_config(profile, "solana-rpc-http")
    cluster = str(config.get("cluster") or "devnet")
    unknown_cluster = str(config.get("unknown_cluster") or "localnet")
    primary = probe_target_path(
        profile,
        "solana-rpc-http",
        "path",
        "/api/rpc/solana/{cluster}",
        {"cluster": cluster},
    )
    root_candidates = [
        str(path)
        for path in (declared_cluster_by_id(profile, "solana-rpc-http") or {}).get("match", {}).get("paths", [])
    ]
    root = str(config.get("root_path") or (root_candidates[0] if root_candidates else "/api/rpc"))
    unknown = (
        render_path_template(str(config["unknown_cluster_path"]), {"cluster": unknown_cluster})
        if config.get("unknown_cluster_path")
        else cluster_default_path(profile, "solana-rpc-http", "/api/rpc/solana/{cluster}", {"cluster": unknown_cluster})
    )
    return {
        "path": primary,
        "root_path": root,
        "unknown_cluster_path": unknown,
        "cluster": cluster,
        "unknown_cluster": unknown_cluster,
    }


def orca_probe_paths(profile: dict[str, Any] | None) -> dict[str, str]:
    config = explicit_probe_target_config(profile, "orca-pools")
    template = str(
        config.get("path_template")
        or cluster_default_path(profile, "orca-pools", "/api/orca/pools/{address}")
    )

    def from_address(address: str) -> str:
        return render_path_template(template, {"address": address})

    return {
        "path_template": template,
        "invalid_address_path": str(config.get("invalid_address_path") or from_address("not-an-address")),
        "invalid_base58_path": str(config.get("invalid_base58_path") or from_address("0OIlnotbase58")),
        "too_short_path": str(config.get("too_short_path") or from_address("1111111111111111111111111111111")),
        "too_long_path": str(
            config.get("too_long_path")
            or from_address("111111111111111111111111111111111111111111111")
        ),
        "encoded_traversal_path": str(config.get("encoded_traversal_path") or from_address("%2e%2e%2fhealth")),
        "extra_segment_path": str(config.get("extra_segment_path") or (from_address("not-an-address") + "/extra")),
        "query_injection_path": str(
            config.get("query_injection_path")
            or (from_address("not-an-address") + "?url=https://evil.example")
        ),
    }


def is_concrete_probe_path(path: str | None) -> bool:
    return bool(path and str(path).startswith("/") and "{" not in str(path) and "}" not in str(path))


def cluster_declared_methods(cluster: dict[str, Any]) -> set[str]:
    methods = {str(cluster.get("method") or "").upper()}
    match = cluster.get("match") or {}
    methods.update(str(method).upper() for method in match.get("methods", []))
    methods.discard("")
    methods.discard("WS")
    return {method for method in methods if method in HTTP_METHODS}


def generic_nextjs_route_targets(profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for cluster in (profile or {}).get("clusters", []):
        cluster_id = str(cluster.get("id") or "")
        if not cluster_id or cluster_id == "health":
            continue
        if strategy_set_for_cluster(cluster) != "nextjs-api-routes":
            continue
        path = probe_target_path(profile, cluster_id, "path", str(cluster.get("path") or ""))
        if not is_concrete_probe_path(path):
            continue
        targets.append(
            {
                "id": cluster_id,
                "path": path,
                "methods": sorted(cluster_declared_methods(cluster)),
                "kind": cluster.get("kind") or "api-route",
                "priority": cluster.get("priority") or "low",
            }
        )
    return targets


def safe_probe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower() or "route"


def build_strategy_registry_artifact(
    profile: dict[str, Any],
    clusters: dict[str, Any],
) -> dict[str, Any]:
    enabled = enabled_strategy_set_ids(profile)
    unknown_enabled = sorted(strategy_id for strategy_id in enabled if strategy_id not in STRATEGY_REGISTRY)
    registry = {}
    for strategy_id, strategy in STRATEGY_REGISTRY.items():
        registry[strategy_id] = {
            **json_clone(strategy),
            "enabled": strategy_id in enabled,
        }
    return {
        "generated_at": utc_now(),
        "status": "loaded",
        "profile": profile_summary(profile),
        "enabled_strategy_sets": sorted(enabled),
        "unknown_enabled_strategy_sets": unknown_enabled,
        "registry": registry,
        "effective_clusters": [
            {
                "id": cluster.get("id"),
                "kind": cluster.get("kind"),
                "strategy_set": cluster.get("strategy_set"),
                "priority": cluster.get("priority"),
            }
            for cluster in clusters.get("clusters", [])
        ],
        "safety": "Strategy registry controls bounded probe selection only; it does not enable signing, transaction submission, Burp Scanner, or broad fuzzing.",
    }


def build_profile_validation_artifact(
    profile: dict[str, Any],
    clusters: dict[str, Any],
    source_root: Path,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    enabled = enabled_strategy_set_ids(profile)
    defaulted_keys = [str(key) for key in profile.get("_profile_defaulted_keys", [])]
    unknown_strategy_sets = sorted(strategy_id for strategy_id in enabled if strategy_id not in STRATEGY_REGISTRY)
    for strategy_id in unknown_strategy_sets:
        issues.append(
            {
                "id": f"unknown-strategy-set:{strategy_id}",
                "severity": "error",
                "message": f"Profile enables strategy set `{strategy_id}`, but it is not in the InferForge registry.",
            }
        )

    if profile.get("_profile_loaded_from") == "file":
        for key in sorted(set(defaulted_keys) & {
            "clusters",
            "probe_targets",
            "source_peeks",
            "burp_observation_plan",
            "websocket_observation",
        }):
            warnings.append(
                {
                    "id": f"profile:defaulted-{key}",
                    "severity": "warning",
                    "message": (
                        f"Profile did not declare `{key}`; InferForge used a neutral empty default "
                        "instead of the regression target defaults."
                    ),
                }
            )

    seen_cluster_ids: set[str] = set()
    declared_clusters = profile.get("clusters", [])
    active_burp_observation_count = 0
    for index, cluster in enumerate(declared_clusters):
        cluster_id = str(cluster.get("id") or "")
        if not cluster_id:
            issues.append(
                {
                    "id": f"cluster-{index}-missing-id",
                    "severity": "error",
                    "message": "Cluster is missing required `id`.",
                }
            )
            continue
        if cluster_id in seen_cluster_ids:
            issues.append(
                {
                    "id": f"duplicate-cluster:{cluster_id}",
                    "severity": "error",
                    "message": f"Cluster id `{cluster_id}` is declared more than once.",
                }
            )
        seen_cluster_ids.add(cluster_id)

        for field in ["method", "path", "kind", "priority"]:
            if not cluster.get(field):
                issues.append(
                    {
                        "id": f"cluster:{cluster_id}:missing-{field}",
                        "severity": "error",
                        "message": f"Cluster `{cluster_id}` is missing required `{field}`.",
                    }
                )
        strategy_set = strategy_set_for_cluster(cluster)
        if strategy_set and strategy_set not in STRATEGY_REGISTRY:
            issues.append(
                {
                    "id": f"cluster:{cluster_id}:unknown-strategy-set",
                    "severity": "error",
                    "message": f"Cluster `{cluster_id}` references unknown strategy set `{strategy_set}`.",
                }
            )
        if strategy_set and strategy_set not in enabled:
            warnings.append(
                {
                    "id": f"cluster:{cluster_id}:strategy-disabled",
                    "severity": "warning",
                    "message": f"Cluster `{cluster_id}` belongs to disabled strategy set `{strategy_set}` and will not be active.",
                }
            )
        if strategy_set and strategy_set in enabled and cluster_id in {
            "health",
            "quote",
            "solana-rpc-http",
            "solana-rpc-ws",
            "orca-pools",
        }:
            probe_target = explicit_probe_target_config(profile, cluster_id)
            if not probe_target and cluster_id != "solana-rpc-ws":
                warnings.append(
                    {
                        "id": f"cluster:{cluster_id}:missing-probe-target",
                        "severity": "warning",
                        "message": (
                            f"Cluster `{cluster_id}` has no explicit `probe_targets.{cluster_id}` entry. "
                            "InferForge will derive bounded probe paths from the cluster path when possible."
                        ),
                    }
                )
            if cluster_id == "solana-rpc-ws" and websocket_observation_config(profile) is None:
                warnings.append(
                    {
                        "id": "cluster:solana-rpc-ws:missing-websocket-observation",
                        "severity": "warning",
                        "message": (
                            "Cluster `solana-rpc-ws` is active, but no WebSocket observation/probe path "
                            "can be resolved from `websocket_observation`, `probe_targets`, or cluster path."
                        ),
                    }
                )
        if strategy_set == "nextjs-api-routes" and cluster_id != "health":
            generic_path = probe_target_path(profile, cluster_id, "path", str(cluster.get("path") or ""))
            if not is_concrete_probe_path(generic_path):
                warnings.append(
                    {
                        "id": f"cluster:{cluster_id}:generic-route-missing-concrete-probe-path",
                        "severity": "warning",
                        "message": (
                            f"Cluster `{cluster_id}` is a generic Next.js route, but its probe path "
                            "is not concrete. Add `probe_targets.{cluster_id}.path` to enable bounded "
                            "HEAD/OPTIONS/GET method probes."
                        ),
                    }
                )

        match = cluster.get("match") or {}
        if not (match.get("paths") or match.get("path_prefixes") or match.get("path_patterns")):
            warnings.append(
                {
                    "id": f"cluster:{cluster_id}:missing-match",
                    "severity": "warning",
                    "message": f"Cluster `{cluster_id}` has no explicit match rules; endpoint classification will fall back to its path pattern.",
                }
                )

        for ref in cluster.get("source_refs", []):
            ref_path = source_ref_to_path(source_root, str(ref))
            if not ref_path.exists():
                warnings.append(
                    {
                        "id": f"cluster:{cluster_id}:missing-source-ref",
                        "severity": "warning",
                        "message": f"Source reference `{ref}` does not exist under the effective source root.",
                    }
                )

    observation_plan = profile.get("burp_observation_plan", [])
    if not isinstance(observation_plan, list):
        issues.append(
            {
                "id": "burp-observation-plan:not-list",
                "severity": "error",
                "message": "`burp_observation_plan` must be a list.",
            }
        )
    else:
        for index, item in enumerate(observation_plan):
            if not isinstance(item, dict):
                issues.append(
                    {
                        "id": f"burp-observation-plan:index-{index}:not-object",
                        "severity": "error",
                        "message": "Each `burp_observation_plan` entry must be an object.",
                    }
                )
                continue
            if not is_active_observation_item(item):
                continue
            active_burp_observation_count += 1
            label = active_observation_label(item, index)
            method = str(item.get("method") or "").upper()
            if method not in HTTP_METHODS:
                issues.append(
                    {
                        "id": f"burp-observation-plan:{label}:invalid-method",
                        "severity": "error",
                        "message": (
                            f"Active Burp observation `{label}` has invalid method `{method or '(missing)'}`."
                        ),
                    }
                )
            path_problem = concrete_local_path_problem(item.get("path"))
            if path_problem:
                issues.append(
                    {
                        "id": f"burp-observation-plan:{label}:unsafe-path",
                        "severity": "error",
                        "message": (
                            f"Active Burp observation `{label}` path is unsafe: {path_problem}. "
                            "Move placeholders to `review_observation_candidates` or promote one reviewed concrete path."
                        ),
                    }
                )
            cluster_id = item.get("cluster")
            if declared_clusters and cluster_id and str(cluster_id) not in seen_cluster_ids:
                warnings.append(
                    {
                        "id": f"burp-observation-plan:{label}:unknown-cluster",
                        "severity": "warning",
                        "message": (
                            f"Active Burp observation `{label}` references cluster `{cluster_id}`, "
                            "which is not declared by the profile."
                        ),
                    }
                )

    websocket_raw = profile.get("websocket_observation")
    if websocket_raw not in (None, False):
        if not isinstance(websocket_raw, dict):
            issues.append(
                {
                    "id": "websocket-observation:not-object",
                    "severity": "error",
                    "message": "`websocket_observation` must be an object, null, or false.",
                }
            )
        else:
            ws_config = websocket_observation_config(profile)
            if ws_config is not None:
                path_problem = concrete_local_path_problem(ws_config.get("path"))
                if path_problem:
                    issues.append(
                        {
                            "id": "websocket-observation:unsafe-path",
                            "severity": "error",
                            "message": (
                                f"Active WebSocket observation path is unsafe: {path_problem}. "
                                "Set a reviewed concrete local path or disable WebSocket observation."
                            ),
                        }
                    )

    if declared_clusters and not clusters.get("clusters"):
        issues.append(
            {
                "id": "no-effective-clusters",
                "severity": "error",
                "message": "Profile declares clusters, but none are active after strategy-set filtering.",
            }
        )
    elif not declared_clusters:
        warnings.append(
            {
                "id": "no-declared-clusters",
                "severity": "warning",
                "message": "Profile has no clusters. Run discover-profile or add clusters before auditing.",
            }
        )

    status = "failed" if issues else ("warnings" if warnings else "passed")
    return {
        "generated_at": utc_now(),
        "status": status,
        "profile": profile_summary(profile),
        "source_root": str(source_root),
        "summary": {
            "declared_clusters": len(declared_clusters),
            "effective_clusters": len(clusters.get("clusters", [])),
            "enabled_strategy_sets": sorted(enabled),
            "unknown_strategy_sets": unknown_strategy_sets,
            "defaulted_keys": defaulted_keys,
            "active_burp_observations": active_burp_observation_count,
            "review_observation_candidates": len(profile.get("review_observation_candidates", []) or []),
            "issue_count": len(issues),
            "warning_count": len(warnings),
        },
        "issues": issues,
        "warnings": warnings,
        "safety": "Profile validation is static and read-only except for writing this artifact.",
    }


HTTP_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}
ROUTE_FILE_NAMES = {"route.js", "route.jsx", "route.ts", "route.tsx"}
PAGES_API_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx"}
NEXT_CONFIG_FILE_NAMES = {
    "next.config.js",
    "next.config.mjs",
    "next.config.cjs",
    "next.config.ts",
}


def repo_relative_or_absolute(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def source_root_relative_or_repo(path: Path, source_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(source_root.resolve()))
    except ValueError:
        return repo_relative_or_absolute(path)


def route_segment_to_path_segment(segment: str) -> str | None:
    if not segment or segment.startswith("(") and segment.endswith(")"):
        return None
    if segment.startswith("@"):
        return None
    if segment.startswith("[[...") and segment.endswith("]]"):
        return "{" + segment[5:-2] + "*}"
    if segment.startswith("[...") and segment.endswith("]"):
        return "{" + segment[4:-1] + "*}"
    if segment.startswith("[") and segment.endswith("]"):
        return "{" + segment[1:-1] + "}"
    return segment


def app_roots(source_root: Path) -> list[Path]:
    return [source_root / "src/app", source_root / "app"]


def nextjs_route_path(route_file: Path, source_root: Path) -> str | None:
    relative = None
    for app_root in app_roots(source_root):
        try:
            relative = route_file.relative_to(app_root)
            break
        except ValueError:
            continue
    if relative is None:
        return None
    if relative.name not in ROUTE_FILE_NAMES:
        return None
    segments = []
    for segment in relative.parent.parts:
        path_segment = route_segment_to_path_segment(segment)
        if path_segment:
            segments.append(path_segment)
    return "/" + "/".join(segments) if segments else "/"


def pages_api_roots(source_root: Path) -> list[Path]:
    return [source_root / "src/pages/api", source_root / "pages/api"]


def nextjs_pages_api_path(api_file: Path, source_root: Path) -> str | None:
    if api_file.suffix not in PAGES_API_EXTENSIONS or api_file.name.endswith(".d.ts"):
        return None
    if api_file.name.startswith("_"):
        return None
    for api_root in pages_api_roots(source_root):
        try:
            relative = api_file.relative_to(api_root)
        except ValueError:
            continue
        stemmed = relative.with_suffix("")
        if stemmed.name.endswith((".test", ".spec")):
            return None
        segments = []
        parts = list(stemmed.parts)
        for index, segment in enumerate(parts):
            if index == len(parts) - 1 and segment == "index":
                continue
            path_segment = route_segment_to_path_segment(segment)
            if path_segment:
                segments.append(path_segment)
        return "/api" + ("/" + "/".join(segments) if segments else "")
    return None


def extract_route_methods(source: str) -> list[str]:
    methods = set(re.findall(r"export\s+(?:async\s+)?function\s+([A-Z]+)\b", source))
    methods.update(re.findall(r"export\s+const\s+([A-Z]+)\s*=", source))
    return sorted(method for method in methods if method in HTTP_METHODS)


def extract_pages_api_methods(source: str) -> list[str]:
    methods = set(extract_route_methods(source))
    methods.update(
        re.findall(
            r"\b(?:req|request)\.method\s*(?:={2,3}|!={1,2})\s*['\"]([A-Z]+)['\"]",
            source,
        )
    )
    methods.update(re.findall(r"\bcase\s+['\"]([A-Z]+)['\"]\s*:", source))
    return sorted(method for method in methods if method in HTTP_METHODS)


def extract_fixed_upstreams(source: str) -> list[str]:
    urls = []
    for match in re.finditer(r"https?://[A-Za-z0-9._~:/?#\[\]@!&*+,;=%-]+", source):
        url = match.group(0).rstrip("'),\"`};]")
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in urls:
                urls.append(origin)
    return urls[:20]


def js_string_literal_value(expr: str) -> str | None:
    expr = expr.strip()
    if len(expr) < 2:
        return None
    quote = expr[0]
    if quote not in {"'", '"', "`"}:
        return None
    if quote == "`":
        if not expr.endswith("`"):
            return None
        return expr[1:-1]
    try:
        value = json.loads(expr) if quote == '"' else None
    except json.JSONDecodeError:
        value = None
    if value is not None:
        return str(value)
    if not expr.endswith(quote):
        return None
    return bytes(expr[1:-1], "utf-8").decode("unicode_escape")


def extract_next_config_env_defaults(source: str) -> dict[str, dict[str, str]]:
    defaults: dict[str, dict[str, str]] = {}
    pattern = re.compile(
        r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
        r"process\.env\.([A-Za-z_][A-Za-z0-9_]*)\s*(?:\?\?|\|\|)\s*"
        r"((?:'[^']*')|(?:\"[^\"]*\")|(?:`[^`]*`))",
        re.S,
    )
    for match in pattern.finditer(source):
        value = js_string_literal_value(match.group(3))
        if value is None:
            continue
        defaults[match.group(1)] = {
            "env": match.group(2),
            "default": value,
        }
    return defaults


def extract_js_string_constants(source: str) -> dict[str, str]:
    constants: dict[str, str] = {}
    pattern = re.compile(
        r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
        r"((?:'[^']*')|(?:\"[^\"]*\")|(?:`[^`]*`))",
        re.S,
    )
    for match in pattern.finditer(source):
        value = js_string_literal_value(match.group(2))
        if value is not None:
            constants[match.group(1)] = value
    return constants


def render_static_template_literal(
    value: str,
    env_defaults: dict[str, dict[str, str]],
) -> tuple[str, list[str]]:
    variables: list[str] = []

    def replace_var(match: re.Match[str]) -> str:
        expression = match.group(1).strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", expression):
            variables.append(expression)
            if expression in env_defaults:
                return env_defaults[expression]["default"]
        return "${" + expression + "}"

    return re.sub(r"\$\{([^{}]+)\}", replace_var, value), variables


def rewrite_source_to_profile_path(source: str) -> str:
    path = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)\*", r"{\1*}", source)
    path = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", path)
    return path


def normalize_next_path(path: str) -> str:
    if not path:
        return "/"
    normalized = "/" + path.strip("/")
    return "/" if normalized == "//" else normalized


def join_next_paths(prefix: str | None, path: str) -> str:
    normalized_path = normalize_next_path(path)
    if not prefix:
        return normalized_path
    normalized_prefix = normalize_next_path(prefix)
    if normalized_prefix == "/":
        return normalized_path
    if normalized_path == "/":
        return normalized_prefix
    if normalized_path == normalized_prefix or normalized_path.startswith(normalized_prefix + "/"):
        return normalized_path
    return normalized_prefix.rstrip("/") + normalized_path


def apply_trailing_slash(path: str, trailing_slash: bool | None) -> str:
    if trailing_slash is None:
        return path
    if path == "/":
        return path
    if trailing_slash:
        if path.endswith("/") or re.search(r"\{[^{}]+\*\}$", path):
            return path
        return path + "/"
    return path.rstrip("/") or "/"


def alternate_trailing_path(path: str, trailing_slash: bool | None) -> str | None:
    if trailing_slash is None or path == "/" or re.search(r"\{[^{}]+\*\}$", path):
        return None
    alternate = path.rstrip("/") if trailing_slash else path + "/"
    return alternate if alternate and alternate != path else None


def extract_js_array_string_literals(expression: str | None) -> list[str]:
    if not expression or not expression.strip().startswith("["):
        return []
    values = []
    for item in split_js_array_items(expression.strip()):
        value = js_string_literal_value(item)
        if value is not None:
            values.append(value)
    return values


def next_config_root_body(source: str) -> str | None:
    candidates: list[tuple[int, str]] = []
    patterns = [
        r"\b(?:const|let|var)\s+[A-Za-z_$][\w$]*(?:\s*:\s*[^=]+)?\s*=\s*\{",
        r"\bmodule\.exports\s*=\s*\{",
        r"\bexport\s+default\s+\{",
    ]
    config_props = {"basePath", "trailingSlash", "i18n", "rewrites", "redirects", "headers"}
    for pattern in patterns:
        for match in re.finditer(pattern, source):
            start = source.find("{", match.start(), match.end())
            if start < 0:
                continue
            end = find_js_object_end(source, start)
            if end is None:
                continue
            body = source[start + 1 : end]
            direct_props = js_object_direct_property_names(body)
            score = len(direct_props & config_props)
            if score:
                candidates.append((score, body))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def discover_next_config_runtime(source_root: Path) -> dict[str, Any]:
    configs = []
    for config_file in next_config_files(source_root):
        try:
            source = read_text(config_file)
        except UnicodeDecodeError:
            continue
        config_body = next_config_root_body(source) or source
        base_path = js_string_literal_value(extract_js_direct_property_expression(config_body, "basePath") or "")
        trailing_slash = js_boolean_literal_value(extract_js_direct_property_expression(config_body, "trailingSlash"))
        i18n_expression = extract_js_direct_property_expression(config_body, "i18n")
        i18n = {
            "locales": [],
            "default_locale": None,
            "locale_prefixes": [],
            "configured": False,
        }
        if i18n_expression and i18n_expression.startswith("{"):
            locales = extract_js_array_string_literals(extract_js_property_expression(i18n_expression, "locales"))
            default_locale = js_string_literal_value(extract_js_property_expression(i18n_expression, "defaultLocale") or "")
            i18n = {
                "locales": locales,
                "default_locale": default_locale,
                "locale_prefixes": [locale for locale in locales if locale != default_locale],
                "configured": bool(locales),
            }
        config_doc = {
            "file": source_root_relative_or_repo(config_file, source_root),
            "repo_file": repo_relative_or_absolute(config_file),
            "base_path": normalize_next_path(base_path) if base_path else None,
            "trailing_slash": trailing_slash,
            "i18n": i18n,
            "line_patterns": {
                "base_path": "basePath",
                "trailing_slash": "trailingSlash",
                "i18n": "i18n",
                "locales": "locales",
                "default_locale": "defaultLocale",
            },
        }
        configs.append(config_doc)

    base_path = next((item.get("base_path") for item in configs if item.get("base_path")), None)
    trailing_slash = next(
        (item.get("trailing_slash") for item in configs if item.get("trailing_slash") is not None),
        None,
    )
    i18n = next(
        (item.get("i18n") for item in configs if (item.get("i18n") or {}).get("configured")),
        {"locales": [], "default_locale": None, "locale_prefixes": [], "configured": False},
    )
    reasons = []
    if base_path:
        reasons.append("next-config-basePath")
    if trailing_slash is not None:
        reasons.append("next-config-trailingSlash")
    if i18n.get("configured"):
        reasons.append("next-config-i18n")
    return {
        "status": "configured" if reasons else ("next-config-found" if configs else "not-found"),
        "files": configs,
        "base_path": base_path,
        "trailing_slash": trailing_slash,
        "i18n": i18n,
        "inference_reasons": reasons,
    }


def next_config_entry_base_path_enabled(body: str) -> bool:
    value = js_boolean_literal_value(extract_js_property_expression(body, "basePath"))
    return value is not False


def next_config_entry_locale_enabled(body: str) -> bool:
    value = js_boolean_literal_value(extract_js_property_expression(body, "locale"))
    return value is not False


def next_runtime_path_variants(
    source_path: str,
    runtime_config: dict[str, Any] | None,
    *,
    apply_base_path: bool = True,
    locale_aware: bool = True,
) -> dict[str, Any]:
    runtime_config = runtime_config or {}
    base_path = runtime_config.get("base_path") if apply_base_path else None
    trailing_slash = runtime_config.get("trailing_slash")
    i18n = runtime_config.get("i18n") or {}
    locale_prefixes = list(i18n.get("locale_prefixes") or []) if locale_aware else []

    framework_path = normalize_next_path(source_path)
    default_path = apply_trailing_slash(join_next_paths(base_path, framework_path), trailing_slash)
    variants = [default_path]
    alternate = alternate_trailing_path(default_path, trailing_slash)
    if alternate:
        variants.append(alternate)

    locale_variants: dict[str, list[str]] = {}
    for locale in locale_prefixes:
        locale_path = apply_trailing_slash(join_next_paths(join_next_paths(base_path, f"/{locale}"), framework_path), trailing_slash)
        locale_items = [locale_path]
        locale_alternate = alternate_trailing_path(locale_path, trailing_slash)
        if locale_alternate:
            locale_items.append(locale_alternate)
        locale_variants[locale] = locale_items
        variants.extend(locale_items)

    deduped = list(dict.fromkeys(variants))
    return {
        "source_path": framework_path,
        "path": default_path,
        "variants": deduped,
        "locale_variants": locale_variants,
        "base_path": base_path,
        "base_path_applied": bool(base_path),
        "trailing_slash": trailing_slash,
        "i18n": {
            "configured": bool(i18n.get("configured")),
            "locales": list(i18n.get("locales") or []),
            "default_locale": i18n.get("default_locale"),
            "locale_prefixes": locale_prefixes,
            "locale_aware": bool(locale_prefixes),
        },
    }


def match_for_path_variants(paths: list[str], methods: list[str] | None = None) -> dict[str, Any]:
    match: dict[str, Any] = {}
    if methods:
        match["methods"] = methods
    for path in dict.fromkeys(paths):
        if "{" in path:
            match.setdefault("path_patterns", []).append(path)
            prefix = catchall_prefix_for_path(path)
            if prefix:
                match.setdefault("path_prefixes", []).append(prefix)
        else:
            match.setdefault("paths", []).append(path)
    return match


def next_runtime_match_for_path(source_path: str, methods: list[str] | None, runtime_config: dict[str, Any] | None) -> dict[str, Any]:
    runtime = next_runtime_path_variants(source_path, runtime_config)
    return match_for_path_variants(runtime["variants"], methods or [])


def next_runtime_reasons(runtime: dict[str, Any]) -> list[str]:
    reasons = []
    if runtime.get("base_path_applied"):
        reasons.append("next-config-basePath")
    if runtime.get("trailing_slash") is not None:
        reasons.append("next-config-trailingSlash")
    if (runtime.get("i18n") or {}).get("locale_aware"):
        reasons.append("next-config-i18n")
    return reasons


def catchall_prefix_for_path(path: str) -> str | None:
    match = re.search(r"\{[^{}]+\*\}", path)
    if not match:
        return None
    prefix = path[: match.start()]
    if not prefix or prefix == "/":
        return None
    return prefix if prefix.endswith("/") else prefix + "/"


def extract_rewrite_prop(body: str, name: str) -> str | None:
    match = re.search(
        rf"\b{name}\s*:\s*((?:'[^']*')|(?:\"[^\"]*\")|(?:`[^`]*`)|[^,\n}}]+)",
        body,
        re.S,
    )
    return match.group(1).strip() if match else None


def looks_like_next_redirect_body(body: str) -> bool:
    return bool(re.search(r"\b(?:permanent|statusCode)\s*:", body))


def find_js_object_end(source: str, start: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    index = start
    while index < len(source):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def js_object_direct_property_names(body: str) -> set[str]:
    names: set[str] = set()
    index = 0
    depth = 0
    quote: str | None = None
    escaped = False
    while index < len(body):
        char = body[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char in "{[(":
            depth += 1
            index += 1
            continue
        if char in "}])":
            depth = max(0, depth - 1)
            index += 1
            continue
        if depth == 0:
            match = re.match(r"\s*([A-Za-z_$][\w$]*)\s*:", body[index:])
            if match:
                names.add(match.group(1))
                index += match.end()
                continue
        index += 1
    return names


def js_object_bodies_with_props(source: str, props: set[str]) -> list[str]:
    bodies: list[str] = []
    for index, char in enumerate(source):
        if char != "{":
            continue
        end = find_js_object_end(source, index)
        if end is None:
            continue
        body = source[index + 1 : end]
        direct_props = js_object_direct_property_names(body)
        if props.issubset(direct_props):
            bodies.append(body)
    return bodies


def js_object_bodies_with_props_and_locations(source: str, props: set[str]) -> list[tuple[str, int, int]]:
    bodies: list[tuple[str, int, int]] = []
    for index, char in enumerate(source):
        if char != "{":
            continue
        end = find_js_object_end(source, index)
        if end is None:
            continue
        body = source[index + 1 : end]
        direct_props = js_object_direct_property_names(body)
        if props.issubset(direct_props):
            bodies.append((body, index, end))
    return bodies


def next_config_files(source_root: Path) -> list[Path]:
    return [
        source_root / name
        for name in sorted(NEXT_CONFIG_FILE_NAMES)
        if (source_root / name).is_file()
    ]


def nearest_next_config_rewrite_phase(source: str, object_start: int) -> str:
    prefix = source[:object_start]
    phase_positions = {
        phase: prefix.rfind(f"{phase}:")
        for phase in ["beforeFiles", "afterFiles", "fallback"]
    }
    phase, position = max(phase_positions.items(), key=lambda item: item[1])
    return phase if position >= 0 else "array"


def extract_next_config_conditions(body: str) -> dict[str, list[dict[str, Any]]]:
    conditions: dict[str, list[dict[str, Any]]] = {"has": [], "missing": []}
    for key in ["has", "missing"]:
        expression = extract_js_property_expression(body, key)
        if not expression or not expression.startswith("["):
            continue
        for item in split_js_array_items(expression):
            if not item.strip().startswith("{"):
                continue
            condition_type = js_string_literal_value(extract_js_property_expression(item, "type") or "")
            condition_key = js_string_literal_value(extract_js_property_expression(item, "key") or "")
            condition_value = js_string_literal_value(extract_js_property_expression(item, "value") or "")
            if not condition_type and not condition_key:
                continue
            conditions[key].append(
                {
                    "type": condition_type,
                    "key": condition_key,
                    "value": condition_value,
                }
            )
    return conditions


def next_config_conditions_present(conditions: dict[str, list[dict[str, Any]]] | None) -> bool:
    return bool((conditions or {}).get("has") or (conditions or {}).get("missing"))


def discover_nextjs_rewrites(source_root: Path, runtime_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rewrites: list[dict[str, Any]] = []
    for config_file in next_config_files(source_root):
        try:
            source = read_text(config_file)
        except UnicodeDecodeError:
            continue
        env_defaults = extract_next_config_env_defaults(source)
        for index, (body, start, _end) in enumerate(js_object_bodies_with_props_and_locations(source, {"source", "destination"}), start=1):
            if looks_like_next_redirect_body(body):
                continue
            source_expr = extract_rewrite_prop(body, "source")
            destination_expr = extract_rewrite_prop(body, "destination")
            source_value = js_string_literal_value(source_expr or "")
            destination_template = js_string_literal_value(destination_expr or "")
            if not source_value or not destination_template or not source_value.startswith("/"):
                continue
            destination_resolved, variables = render_static_template_literal(destination_template, env_defaults)
            source_path = rewrite_source_to_profile_path(source_value)
            runtime = next_runtime_path_variants(
                source_path,
                runtime_config,
                apply_base_path=next_config_entry_base_path_enabled(body),
                locale_aware=next_config_entry_locale_enabled(body),
            )
            path = runtime["path"]
            upstreams = extract_fixed_upstreams(destination_resolved)
            reasons = ["next-config-rewrite"]
            if upstreams:
                reasons.append("rewrite-destination-fixed-upstream")
            if variables:
                reasons.append("rewrite-destination-template-env")
            reasons.extend(reason for reason in next_runtime_reasons(runtime) if reason not in reasons)
            phase = nearest_next_config_rewrite_phase(source, start)
            conditions = extract_next_config_conditions(body)
            if next_config_conditions_present(conditions):
                reasons.append("rewrite-conditions")
            rewrite_doc = {
                "cluster_id": cluster_id_from_route_path(source_path),
                "path": path,
                "source_path": source_path,
                "methods": [],
                "file": source_root_relative_or_repo(config_file, source_root),
                "repo_file": repo_relative_or_absolute(config_file),
                "dynamic_segments": route_dynamic_segments(source_path),
                "fixed_upstreams": upstreams,
                "strategy_set": "fixed-upstream-proxy",
                "kind": "rewrite-proxy",
                "priority": "medium",
                "inference_reasons": reasons,
                "next_config": runtime,
                "match": match_for_path_variants(runtime["variants"], []),
                "rewrite": {
                    "source": source_value,
                    "source_pattern": path,
                    "source_framework_pattern": source_path,
                    "destination_template": destination_template,
                    "destination_resolved": destination_resolved,
                    "destination_expression": destination_expr,
                    "template_variables": variables,
                    "env_defaults_used": {
                        variable: env_defaults[variable]
                        for variable in variables
                        if variable in env_defaults
                    },
                    "phase": phase,
                    "conditions": conditions,
                    "conditional": next_config_conditions_present(conditions),
                    "index": index,
                },
            }
            rewrites.append(rewrite_doc)
    return rewrites


def custom_server_files(source_root: Path) -> list[Path]:
    names = [
        "server.js",
        "server.mjs",
        "server.cjs",
        "server.ts",
        "src/server.js",
        "src/server.ts",
    ]
    return [source_root / name for name in names if (source_root / name).is_file()]


def custom_ws_cluster_id_for_prefix(prefix: str) -> str:
    if prefix.startswith("/api/rpc/solana/"):
        return "solana-rpc-ws"
    return f"custom-ws-{safe_probe_id(prefix.strip('/') or 'root')}"


def custom_ws_path_for_prefix(prefix: str) -> str:
    normalized = prefix if prefix.endswith("/") else prefix + "/"
    if normalized.startswith("/api/rpc/solana/"):
        return normalized + "{cluster}"
    return normalized + "{path*}"


def discover_custom_server_entrypoints(source_root: Path) -> list[dict[str, Any]]:
    entrypoints: list[dict[str, Any]] = []
    for server_file in custom_server_files(source_root):
        try:
            source = read_text(server_file)
        except UnicodeDecodeError:
            continue
        if "server.on(" not in source or "upgrade" not in source:
            continue
        if "WebSocketServer" not in source and ".getUpgradeHandler(" not in source:
            continue

        constants = extract_js_string_constants(source)
        fixed_upstreams = [
            url
            for url in extract_fixed_upstreams(source)
            if urllib.parse.urlparse(url).hostname not in {"localhost", "127.0.0.1", "::1"}
        ]
        for const_name, value in sorted(constants.items()):
            if not value.startswith("/") or not value.endswith("/"):
                continue
            if f"startsWith({const_name})" not in source:
                continue
            path = custom_ws_path_for_prefix(value)
            cluster_id = custom_ws_cluster_id_for_prefix(value)
            line_patterns = {
                "path_prefix_const": const_name,
                "upgrade_handler": ["server.on('upgrade'", 'server.on("upgrade"'],
                "websocket_server": "new WebSocketServer",
            }
            if "getSolanaClusterFromPathname" in source:
                line_patterns["route_extractor"] = "function getSolanaClusterFromPathname"
            if "handleSolanaWsProxy" in source:
                line_patterns["proxy_handler"] = "function handleSolanaWsProxy"
            if "isAllowedOrigin" in source:
                line_patterns["origin_check"] = "function isAllowedOrigin"

            entrypoints.append(
                {
                    "cluster_id": cluster_id,
                    "path": path,
                    "methods": ["WS"],
                    "file": source_root_relative_or_repo(server_file, source_root),
                    "repo_file": repo_relative_or_absolute(server_file),
                    "dynamic_segments": route_dynamic_segments(path),
                    "fixed_upstreams": fixed_upstreams,
                    "strategy_set": "solana-json-rpc-proxy" if cluster_id == "solana-rpc-ws" else "custom-server-upgrade",
                    "kind": "websocket-json-rpc-proxy" if cluster_id == "solana-rpc-ws" else "custom-websocket-upgrade",
                    "priority": "high" if cluster_id == "solana-rpc-ws" else "medium",
                    "inference_reasons": [
                        "custom-server-upgrade-handler",
                        "custom-server-path-prefix",
                        "custom-server-websocket",
                    ],
                    "match": {
                        "methods": ["WS"],
                        "path_patterns": [path],
                        "path_prefixes": [value],
                    },
                    "custom_server": {
                        "path_prefix_constant": const_name,
                        "path_prefix": value,
                        "upgrade_handler": "server.on('upgrade')",
                    },
                    "line_patterns": line_patterns,
                }
            )
    return entrypoints


def middleware_files(source_root: Path) -> list[Path]:
    candidates = []
    for base in [source_root, source_root / "src"]:
        for stem in ["middleware", "proxy"]:
            for suffix in PAGES_API_EXTENSIONS:
                path = base / f"{stem}{suffix}"
                if path.is_file() and not path.name.endswith(".d.ts"):
                    candidates.append(path)
    return sorted(dict.fromkeys(candidates))


def extract_js_property_expression(source: str, property_name: str) -> str | None:
    match = re.search(rf"\b{re.escape(property_name)}\s*:", source)
    if not match:
        return None
    index = match.end()
    while index < len(source) and source[index].isspace():
        index += 1
    if index >= len(source):
        return None

    opening = source[index]
    if opening in {"'", '"', "`"}:
        quote = opening
        escaped = False
        index += 1
        while index < len(source):
            char = source[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                return source[match.end(): index + 1].strip()
            index += 1
        return None

    closing_by_opening = {"[": "]", "{": "}", "(": ")"}
    if opening in closing_by_opening:
        stack = [closing_by_opening[opening]]
        quote: str | None = None
        escaped = False
        index += 1
        while index < len(source):
            char = source[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue
            if char in {"'", '"', "`"}:
                quote = char
                index += 1
                continue
            if char in closing_by_opening:
                stack.append(closing_by_opening[char])
            elif stack and char == stack[-1]:
                stack.pop()
                if not stack:
                    return source[match.end(): index + 1].strip()
            index += 1
        return None

    end = index
    while end < len(source) and source[end] not in {",", "\n", "}"}:
        end += 1
    return source[index:end].strip()


def extract_js_direct_property_expression(body: str, property_name: str) -> str | None:
    index = 0
    depth = 0
    quote: str | None = None
    escaped = False
    while index < len(body):
        char = body[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            index += 1
            continue
        if char in "{[(":
            depth += 1
            index += 1
            continue
        if char in "}])":
            depth = max(0, depth - 1)
            index += 1
            continue
        if depth == 0:
            match = re.match(rf"\s*{re.escape(property_name)}\s*:", body[index:])
            if match:
                return extract_js_property_expression(body[index:], property_name)
        index += 1
    return None


def split_js_array_items(expression: str) -> list[str]:
    expression = expression.strip()
    if not expression.startswith("[") or not expression.endswith("]"):
        return []
    body = expression[1:-1]
    items: list[str] = []
    start = 0
    index = 0
    depth = 0
    quote: str | None = None
    escaped = False
    while index < len(body):
        char = body[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
        elif char in "[{(":
            depth += 1
        elif char in "]})" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            item = body[start:index].strip()
            if item:
                items.append(item)
            start = index + 1
        index += 1
    tail = body[start:].strip()
    if tail:
        items.append(tail)
    return items


def extract_middleware_matchers(source: str, runtime_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    expression = extract_js_property_expression(source, "matcher")
    if not expression:
        return []
    matcher_docs: list[dict[str, Any]] = []

    def add_literal(value: str, *, source_kind: str) -> None:
        if not value.startswith("/"):
            return
        source_pattern = rewrite_source_to_profile_path(value)
        runtime = next_runtime_path_variants(source_pattern, runtime_config)
        matcher_docs.append(
            {
                "source": value,
                "source_path_pattern": source_pattern,
                "path_pattern": runtime["path"],
                "path_patterns": runtime["variants"],
                "source_kind": source_kind,
                "simple": all(middleware_matcher_is_simple(pattern) for pattern in runtime["variants"]),
                "next_config": runtime,
            }
        )

    if expression[0] in {"'", '"', "`"}:
        value = js_string_literal_value(expression)
        if value is not None:
            add_literal(value, source_kind="literal")
        return matcher_docs

    if expression.startswith("["):
        for item in split_js_array_items(expression):
            if item and item[0] in {"'", '"', "`"}:
                value = js_string_literal_value(item)
                if value is not None:
                    add_literal(value, source_kind="array-literal")
                continue
            source_expression = extract_js_property_expression(item, "source")
            if source_expression:
                value = js_string_literal_value(source_expression)
                if value is not None:
                    add_literal(value, source_kind="object-source")
        return matcher_docs

    source_expression = extract_js_property_expression(expression, "source")
    if source_expression:
        value = js_string_literal_value(source_expression)
        if value is not None:
            add_literal(value, source_kind="object-source")
    return matcher_docs


def middleware_matcher_is_simple(pattern: str) -> bool:
    return not any(marker in pattern for marker in ["(", ")", "[", "]", "|", "?=", "?!", "+"])


def discover_nextjs_middleware(source_root: Path, runtime_config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    middleware_entries: list[dict[str, Any]] = []
    for path in middleware_files(source_root):
        try:
            source = read_text(path)
        except UnicodeDecodeError:
            continue
        stem = path.stem
        matchers = extract_middleware_matchers(source, runtime_config)
        reasons = [f"nextjs-{stem}-file"]
        if matchers:
            reasons.append("static-matcher-config")
        else:
            reasons.append("default-all-paths")
        if runtime_config:
            for reason in runtime_config.get("inference_reasons", []):
                if reason not in reasons:
                    reasons.append(reason)
        middleware_entries.append(
            {
                "id": f"{stem}-{safe_probe_id(source_root_relative_or_repo(path, source_root))}",
                "kind": f"nextjs-{stem}",
                "file": source_root_relative_or_repo(path, source_root),
                "repo_file": repo_relative_or_absolute(path),
                "matchers": matchers,
                "match_strategy": "static-matchers" if matchers else "default-all-paths",
                "inference_reasons": reasons,
                "line_patterns": {
                    "handler": [
                        "export function middleware",
                        "export async function middleware",
                        "export default function middleware",
                        "export function proxy",
                        "export async function proxy",
                        "export default function proxy",
                    ],
                    "config": "export const config",
                    "matcher": "matcher",
                },
                "safety": "Static middleware/proxy source context only. Does not execute middleware or send HTTP requests.",
            }
        )
    return middleware_entries


def server_action_scan_roots(source_root: Path) -> list[Path]:
    candidates = [
        *app_roots(source_root),
        source_root / "src/actions",
        source_root / "actions",
    ]
    return sorted(dict.fromkeys(path for path in candidates if path.is_dir()))


def server_action_candidate_files(source_root: Path) -> list[Path]:
    excluded_parts = {"node_modules", ".next", "dist", "build", "coverage"}
    files: list[Path] = []
    for root in server_action_scan_roots(source_root):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in PAGES_API_EXTENSIONS or path.name.endswith(".d.ts"):
                continue
            if any(part in excluded_parts for part in path.parts):
                continue
            files.append(path)
    return sorted(dict.fromkeys(files))


def has_file_level_use_server(source: str) -> bool:
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        return stripped in {"'use server'", '"use server"', "'use server';", '"use server";'}
    return False


def use_server_directive_count(source: str) -> int:
    return len(re.findall(r"(?m)^\s*['\"]use server['\"]\s*;?\s*$", source))


def extract_server_action_exports(source: str) -> list[str]:
    names: set[str] = set()
    patterns = [
        r"\bexport\s+async\s+function\s+([A-Za-z_$][\w$]*)\b",
        r"\bexport\s+function\s+([A-Za-z_$][\w$]*)\b",
        r"\bexport\s+const\s+([A-Za-z_$][\w$]*)\s*=\s*async\b",
        r"\bexport\s+const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(",
    ]
    for pattern in patterns:
        names.update(re.findall(pattern, source))
    return sorted(names)


def discover_nextjs_server_actions(source_root: Path) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for path in server_action_candidate_files(source_root):
        try:
            source = read_text(path)
        except UnicodeDecodeError:
            continue
        directive_count = use_server_directive_count(source)
        if directive_count == 0:
            continue
        file_level = has_file_level_use_server(source)
        action_names = extract_server_action_exports(source)
        source_ref = source_root_relative_or_repo(path, source_root)
        line_patterns: dict[str, Any] = {"use_server": "use server"}
        for name in action_names[:12]:
            line_patterns[f"action:{name}"] = name
        actions.append(
            {
                "id": f"server_action_{safe_probe_id(source_ref)}",
                "kind": "nextjs-server-action",
                "file": source_ref,
                "repo_file": repo_relative_or_absolute(path),
                "scope": "file-level-use-server" if file_level else "inline-use-server",
                "action_names": action_names,
                "action_count": len(action_names),
                "use_server_directive_count": directive_count,
                "inference_reasons": [
                    "nextjs-use-server-directive",
                    "server-action-source-context",
                    "file-level-use-server" if file_level else "inline-use-server",
                ],
                "line_patterns": line_patterns,
                "safety": "Static Server Actions source context only. Does not execute actions, submit forms, send HTTP requests, sign wallets, or mutate state.",
            }
        )
    return actions


def js_boolean_literal_value(expr: str | None) -> bool | None:
    if expr is None:
        return None
    value = str(expr).strip().rstrip(",")
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def js_integer_literal_value(expr: str | None) -> int | None:
    if expr is None:
        return None
    value = str(expr).strip().rstrip(",")
    return int(value) if re.fullmatch(r"\d{3}", value) else None


def next_config_route_policy_match(path: str) -> dict[str, Any]:
    if "{" in path:
        match = {"path_patterns": [path]}
        prefix = catchall_prefix_for_path(path)
        if prefix:
            match["path_prefixes"] = [prefix]
        return match
    return {"paths": [path]}


def extract_next_config_headers(body: str) -> list[dict[str, Any]]:
    expression = extract_js_property_expression(body, "headers")
    if not expression or not expression.startswith("["):
        return []
    headers = []
    for item in split_js_array_items(expression):
        key_expr = extract_js_property_expression(item, "key")
        value_expr = extract_js_property_expression(item, "value")
        key = js_string_literal_value(key_expr or "")
        value = js_string_literal_value(value_expr or "")
        if not key:
            continue
        headers.append(
            {
                "key": key,
                "value": value,
                "key_expression": key_expr,
                "value_expression": value_expr,
            }
        )
    return headers


def discover_next_config_route_policies(source_root: Path, runtime_config: dict[str, Any] | None = None) -> dict[str, list[dict[str, Any]]]:
    redirects: list[dict[str, Any]] = []
    headers: list[dict[str, Any]] = []
    for config_file in next_config_files(source_root):
        try:
            source = read_text(config_file)
        except UnicodeDecodeError:
            continue
        env_defaults = extract_next_config_env_defaults(source)

        for index, (body, _start, _end) in enumerate(js_object_bodies_with_props_and_locations(source, {"source", "destination"}), start=1):
            if not looks_like_next_redirect_body(body):
                continue
            source_expr = extract_rewrite_prop(body, "source")
            destination_expr = extract_rewrite_prop(body, "destination")
            source_value = js_string_literal_value(source_expr or "")
            destination_template = js_string_literal_value(destination_expr or "")
            if not source_value or not destination_template or not source_value.startswith("/"):
                continue
            destination_resolved, variables = render_static_template_literal(destination_template, env_defaults)
            source_path = rewrite_source_to_profile_path(source_value)
            runtime = next_runtime_path_variants(
                source_path,
                runtime_config,
                apply_base_path=next_config_entry_base_path_enabled(body),
                locale_aware=next_config_entry_locale_enabled(body),
            )
            path = runtime["path"]
            permanent_expr = extract_rewrite_prop(body, "permanent")
            status_expr = extract_rewrite_prop(body, "statusCode")
            permanent = js_boolean_literal_value(permanent_expr)
            status_code = js_integer_literal_value(status_expr)
            if status_code is None and permanent is not None:
                status_code = 308 if permanent else 307
            conditions = extract_next_config_conditions(body)
            redirects.append(
                {
                    "id": f"redirect_{safe_probe_id(source_root_relative_or_repo(config_file, source_root))}_{index}",
                    "kind": "next-config-redirect",
                    "path": path,
                    "source_path": source_path,
                    "file": source_root_relative_or_repo(config_file, source_root),
                    "repo_file": repo_relative_or_absolute(config_file),
                    "dynamic_segments": route_dynamic_segments(source_path),
                    "match": match_for_path_variants(runtime["variants"], []),
                    "inference_reasons": ["next-config-redirect", *next_runtime_reasons(runtime)],
                    "next_config": runtime,
                    "route_policy": {
                        "type": "redirect",
                        "source": source_value,
                        "source_pattern": path,
                        "source_framework_pattern": source_path,
                        "destination_template": destination_template,
                        "destination_resolved": destination_resolved,
                        "destination_expression": destination_expr,
                        "permanent": permanent,
                        "status_code": status_code,
                        "conditions": conditions,
                        "conditional": next_config_conditions_present(conditions),
                        "template_variables": variables,
                        "env_defaults_used": {
                            variable: env_defaults[variable]
                            for variable in variables
                            if variable in env_defaults
                        },
                        "index": index,
                    },
                    "line_patterns": {
                        "source": source_value,
                        "destination": [str(destination_expr or ""), destination_template, destination_resolved],
                        "permanent": "permanent",
                        "status_code": "statusCode",
                        "has_conditions": "has",
                        "missing_conditions": "missing",
                    },
                }
            )

        for index, (body, _start, _end) in enumerate(js_object_bodies_with_props_and_locations(source, {"source", "headers"}), start=1):
            source_expr = extract_rewrite_prop(body, "source")
            source_value = js_string_literal_value(source_expr or "")
            if not source_value or not source_value.startswith("/"):
                continue
            header_entries = extract_next_config_headers(body)
            conditions = extract_next_config_conditions(body)
            source_path = rewrite_source_to_profile_path(source_value)
            runtime = next_runtime_path_variants(
                source_path,
                runtime_config,
                apply_base_path=next_config_entry_base_path_enabled(body),
                locale_aware=next_config_entry_locale_enabled(body),
            )
            path = runtime["path"]
            headers.append(
                {
                    "id": f"headers_{safe_probe_id(source_root_relative_or_repo(config_file, source_root))}_{index}",
                    "kind": "next-config-headers",
                    "path": path,
                    "source_path": source_path,
                    "file": source_root_relative_or_repo(config_file, source_root),
                    "repo_file": repo_relative_or_absolute(config_file),
                    "dynamic_segments": route_dynamic_segments(source_path),
                    "match": match_for_path_variants(runtime["variants"], []),
                    "inference_reasons": ["next-config-headers", *next_runtime_reasons(runtime)],
                    "next_config": runtime,
                    "route_policy": {
                        "type": "headers",
                        "source": source_value,
                        "source_pattern": path,
                        "source_framework_pattern": source_path,
                        "headers": [
                            {"key": item["key"], "value": item.get("value")}
                            for item in header_entries
                        ],
                        "header_keys": [item["key"] for item in header_entries],
                        "conditions": conditions,
                        "conditional": next_config_conditions_present(conditions),
                        "index": index,
                    },
                    "line_patterns": {
                        "source": source_value,
                        "headers": "headers",
                        "has_conditions": "has",
                        "missing_conditions": "missing",
                        **{
                            f"header:{item['key']}": str(item.get("key_expression") or item["key"])
                            for item in header_entries
                        },
                    },
                }
            )
    return {"redirects": redirects, "headers": headers}


def route_dynamic_segments(path: str) -> list[str]:
    return re.findall(r"\{([^{}]+)\}", path)


def cluster_id_from_route_path(path: str) -> str:
    if path == "/health":
        return "health"
    if path == "/api/quote":
        return "quote"
    if path == "/api/rpc" or path.startswith("/api/rpc/solana/"):
        return "solana-rpc-http"
    if path.startswith("/api/orca/pools/"):
        return "orca-pools"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", path.strip("/")).strip("-").lower()
    return f"route-{slug or 'root'}"


def infer_route_strategy(path: str, methods: list[str], source: str, upstreams: list[str]) -> dict[str, Any]:
    lowered = source.lower()
    reasons = []
    if path == "/health":
        return {
            "strategy_set": "nextjs-api-routes",
            "kind": "health",
            "priority": "low",
            "reasons": ["path:/health"],
        }
    if path == "/api/quote" or "quote" in path.lower() or "m0" in lowered:
        if "quote" in path.lower():
            reasons.append("path-contains-quote")
        if "m0" in lowered:
            reasons.append("source-mentions-m0")
        return {
            "strategy_set": "quote-transaction-decoder",
            "kind": "orchestration-proxy",
            "priority": "high",
            "reasons": reasons or ["quote-like-route"],
        }
    if path == "/api/rpc" or "/rpc/" in path or "jsonrpc" in lowered:
        if "jsonrpc" in lowered:
            reasons.append("source-mentions-jsonrpc")
        if "solana" in lowered:
            reasons.append("source-mentions-solana")
        if "/rpc" in path:
            reasons.append("path-contains-rpc")
        return {
            "strategy_set": "solana-json-rpc-proxy",
            "kind": "json-rpc-proxy",
            "priority": "high",
            "reasons": reasons or ["rpc-like-route"],
        }
    if upstreams:
        if "solana" in lowered:
            reasons.append("source-mentions-solana")
        return {
            "strategy_set": "fixed-upstream-proxy",
            "kind": "fixed-upstream-proxy",
            "priority": "medium",
            "reasons": ["source-contains-fixed-http-upstream", *reasons],
        }
    return {
        "strategy_set": "nextjs-api-routes",
        "kind": "api-route",
        "priority": "medium" if any(method in {"POST", "PUT", "PATCH", "DELETE"} for method in methods) else "low",
        "reasons": ["generic-nextjs-route"],
    }


def discover_nextjs_routes(source_root: Path) -> dict[str, Any]:
    discovered_app_roots = app_roots(source_root)
    api_roots = pages_api_roots(source_root)
    routes = []
    runtime_config = discover_next_config_runtime(source_root)
    rewrites = discover_nextjs_rewrites(source_root, runtime_config)
    custom_server_entrypoints = discover_custom_server_entrypoints(source_root)
    middleware_entries = discover_nextjs_middleware(source_root, runtime_config)
    server_actions = discover_nextjs_server_actions(source_root)
    route_policies = discover_next_config_route_policies(source_root, runtime_config)
    redirects = route_policies["redirects"]
    header_routes = route_policies["headers"]

    for app_root in discovered_app_roots:
        if not app_root.is_dir():
            continue
        for route_file in sorted(app_root.rglob("route.*")):
            if route_file.name not in ROUTE_FILE_NAMES or not route_file.is_file():
                continue
            source_path = nextjs_route_path(route_file, source_root)
            if not source_path:
                continue
            runtime = next_runtime_path_variants(source_path, runtime_config)
            route_path = runtime["path"]
            try:
                source = read_text(route_file)
            except UnicodeDecodeError:
                continue
            methods = extract_route_methods(source)
            upstreams = extract_fixed_upstreams(source)
            inference = infer_route_strategy(source_path, methods, source, upstreams)
            routes.append(
                {
                    "cluster_id": cluster_id_from_route_path(source_path),
                    "path": route_path,
                    "source_path": source_path,
                    "methods": methods,
                    "file": source_root_relative_or_repo(route_file, source_root),
                    "repo_file": repo_relative_or_absolute(route_file),
                    "router": "app",
                    "dynamic_segments": route_dynamic_segments(source_path),
                    "fixed_upstreams": upstreams,
                    "strategy_set": inference["strategy_set"],
                    "kind": inference["kind"],
                    "priority": inference["priority"],
                    "inference_reasons": [*inference["reasons"], *next_runtime_reasons(runtime)],
                    "match": match_for_path_variants(runtime["variants"], methods),
                    "next_config": runtime,
                }
            )

    for api_root in api_roots:
        if not api_root.is_dir():
            continue
        for route_file in sorted(api_root.rglob("*")):
            if not route_file.is_file():
                continue
            source_path = nextjs_pages_api_path(route_file, source_root)
            if not source_path:
                continue
            runtime = next_runtime_path_variants(source_path, runtime_config)
            route_path = runtime["path"]
            try:
                source = read_text(route_file)
            except UnicodeDecodeError:
                continue
            methods = extract_pages_api_methods(source)
            upstreams = extract_fixed_upstreams(source)
            inference = infer_route_strategy(source_path, methods, source, upstreams)
            routes.append(
                {
                    "cluster_id": cluster_id_from_route_path(source_path),
                    "path": route_path,
                    "source_path": source_path,
                    "methods": methods,
                    "file": source_root_relative_or_repo(route_file, source_root),
                    "repo_file": repo_relative_or_absolute(route_file),
                    "router": "pages",
                    "dynamic_segments": route_dynamic_segments(source_path),
                    "fixed_upstreams": upstreams,
                    "strategy_set": inference["strategy_set"],
                    "kind": inference["kind"],
                    "priority": inference["priority"],
                    "inference_reasons": ["pages-router-api-route", *inference["reasons"], *next_runtime_reasons(runtime)],
                    "match": match_for_path_variants(runtime["variants"], methods),
                    "next_config": runtime,
                }
            )

    if routes:
        status = "discovered"
    elif rewrites or custom_server_entrypoints or middleware_entries or server_actions or redirects or header_routes:
        status = "discovered-without-route-handlers"
    else:
        status = "source-root-missing-nextjs-routes"

    return {
        "generated_at": utc_now(),
        "status": status,
        "source_root": str(source_root),
        "app_root": str(discovered_app_roots[0]),
        "app_roots": [str(path) for path in discovered_app_roots],
        "pages_api_roots": [str(path) for path in api_roots],
        "summary": {
            "route_count": len(routes),
            "app_router_route_count": sum(1 for route in routes if route.get("router") == "app"),
            "pages_router_api_route_count": sum(1 for route in routes if route.get("router") == "pages"),
            "rewrite_count": len(rewrites),
            "custom_server_entrypoint_count": len(custom_server_entrypoints),
            "middleware_count": len(middleware_entries),
            "server_action_file_count": len(server_actions),
            "server_action_export_count": sum(int(item.get("action_count", 0) or 0) for item in server_actions),
            "redirect_count": len(redirects),
            "header_route_count": len(header_routes),
            "route_policy_count": len(redirects) + len(header_routes),
            "next_config_runtime": {
                "base_path": runtime_config.get("base_path"),
                "trailing_slash": runtime_config.get("trailing_slash"),
                "i18n_configured": bool((runtime_config.get("i18n") or {}).get("configured")),
                "locale_count": len((runtime_config.get("i18n") or {}).get("locales") or []),
            },
            "entrypoint_count": len(routes) + len(rewrites) + len(custom_server_entrypoints),
            "surface_count": (
                len(routes)
                + len(rewrites)
                + len(custom_server_entrypoints)
                + len(middleware_entries)
                + len(server_actions)
                + len(redirects)
                + len(header_routes)
            ),
            "api_route_count": sum(1 for route in routes if str(route.get("source_path") or route["path"]).startswith("/api/")),
            "strategy_sets": sorted({route["strategy_set"] for route in [*routes, *rewrites, *custom_server_entrypoints]}),
        },
        "next_config": runtime_config,
        "routes": routes,
        "rewrites": rewrites,
        "custom_server_entrypoints": custom_server_entrypoints,
        "middleware": middleware_entries,
        "server_actions": server_actions,
        "redirects": redirects,
        "headers": header_routes,
        "safety": "Discovery is static source inspection only; no HTTP requests, signing, transaction submission, or upstream enumeration are performed.",
    }


def route_match_for_path(path: str, methods: list[str]) -> dict[str, Any]:
    match: dict[str, Any] = {}
    if methods:
        match["methods"] = methods
    if "{" in path:
        match["path_patterns"] = [path]
        prefix = catchall_prefix_for_path(path)
        if prefix:
            match["path_prefixes"] = [prefix]
    else:
        match["paths"] = [path]
    return match


def merge_discovered_clusters(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for route in routes:
        cluster_id = str(route.get("cluster_id") or cluster_id_from_route_path(str(route["path"])))
        route_methods = list(route.get("methods", []))
        route_match = json_clone(route.get("match") or route_match_for_path(str(route["path"]), route_methods))
        default_method = str(route.get("method") or (route_methods[0] if route_methods else "ANY"))
        cluster = by_id.setdefault(
            cluster_id,
            {
                "id": cluster_id,
                "method": default_method,
                "path": route["path"],
                "kind": route["kind"],
                "priority": route["priority"],
                "strategy_set": route["strategy_set"],
                "match": {"paths": [], "path_patterns": [], "path_prefixes": [], "methods": []},
                "source_refs": [],
                "discovery": {
                    "routes": [],
                    "rewrites": [],
                    "inference_reasons": [],
                    "fixed_upstreams": [],
                },
            },
        )
        if priority_rank(str(route["priority"])) > priority_rank(str(cluster["priority"])):
            cluster["priority"] = route["priority"]
        if route["path"] == "/api/rpc/solana/{cluster}":
            cluster["path"] = route["path"]
        elif "{" not in str(cluster["path"]) and "{" in str(route["path"]):
            cluster["path"] = route["path"]
        methods = cluster["match"].setdefault("methods", [])
        for method in route_match.get("methods", []):
            if method not in methods:
                methods.append(method)
        for match_key in ["paths", "path_patterns", "path_prefixes"]:
            target_items = cluster["match"].setdefault(match_key, [])
            for item in route_match.get(match_key, []):
                if item not in target_items:
                    target_items.append(item)
        if route["file"] not in cluster["source_refs"]:
            cluster["source_refs"].append(route["file"])
        if route.get("kind") == "rewrite-proxy":
            cluster["discovery"]["rewrites"].append(
                {
                    "source": route.get("rewrite", {}).get("source"),
                    "source_pattern": route.get("rewrite", {}).get("source_pattern"),
                    "source_framework_pattern": route.get("rewrite", {}).get("source_framework_pattern"),
                    "destination_resolved": route.get("rewrite", {}).get("destination_resolved"),
                    "destination_template": route.get("rewrite", {}).get("destination_template"),
                    "phase": route.get("rewrite", {}).get("phase"),
                    "conditions": route.get("rewrite", {}).get("conditions"),
                    "conditional": route.get("rewrite", {}).get("conditional"),
                    "next_config": route.get("next_config"),
                }
            )
        else:
            cluster["discovery"]["routes"].append(
                {
                    "path": route["path"],
                    "source_path": route.get("source_path"),
                    "methods": route.get("methods", []),
                    "router": route.get("router"),
                    "next_config": route.get("next_config"),
                }
            )
        for reason in route.get("inference_reasons", []):
            if reason not in cluster["discovery"]["inference_reasons"]:
                cluster["discovery"]["inference_reasons"].append(reason)
        for upstream in route.get("fixed_upstreams", []):
            if upstream not in cluster["discovery"]["fixed_upstreams"]:
                cluster["discovery"]["fixed_upstreams"].append(upstream)

    clusters = []
    for cluster in by_id.values():
        match = cluster["match"]
        if not match.get("methods"):
            match.pop("methods", None)
        for key in ["paths", "path_patterns", "path_prefixes"]:
            if not match.get(key):
                match.pop(key, None)
        if not cluster["discovery"].get("routes"):
            cluster["discovery"].pop("routes", None)
        if not cluster["discovery"].get("rewrites"):
            cluster["discovery"].pop("rewrites", None)
        clusters.append(cluster)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    clusters.sort(key=lambda item: (priority_order.get(str(item.get("priority")), 9), str(item.get("id"))))
    return clusters


def build_probe_targets_from_clusters(clusters: list[dict[str, Any]]) -> dict[str, Any]:
    targets: dict[str, Any] = {}
    for cluster in clusters:
        cluster_id = str(cluster.get("id"))
        path = str(cluster.get("path") or "")
        if not path:
            continue
        if cluster_id == "health":
            targets["health"] = {"path": path}
        elif cluster_id == "quote":
            targets["quote"] = {"path": path}
        elif cluster_id == "solana-rpc-http":
            root_paths = [
                path_item
                for path_item in (cluster.get("match") or {}).get("paths", [])
                if str(path_item) == "/api/rpc" or str(path_item).endswith("/rpc")
            ]
            cluster_value = "devnet"
            dynamic_match = re.search(r"\{([^{}]+)\}", path)
            concrete_path = render_path_template(path, {dynamic_match.group(1): cluster_value}) if dynamic_match else path
            unknown_path = render_path_template(path, {dynamic_match.group(1): "localnet"}) if dynamic_match else path
            targets["solana-rpc-http"] = {
                "path": concrete_path,
                "root_path": root_paths[0] if root_paths else "/api/rpc",
                "unknown_cluster_path": unknown_path,
                "cluster": cluster_value,
                "unknown_cluster": "localnet",
            }
            targets.setdefault("solana-rpc-ws", {"path": concrete_path})
        elif cluster_id == "solana-rpc-ws":
            targets["solana-rpc-ws"] = {"path": render_path_template(path, {"cluster": "devnet"})}
        elif cluster_id == "orca-pools":
            template = path
            targets["orca-pools"] = {
                "path_template": template,
                "invalid_address_path": render_path_template(template, {"address": "not-an-address"}),
                "invalid_base58_path": render_path_template(template, {"address": "0OIlnotbase58"}),
                "too_short_path": render_path_template(template, {"address": "1111111111111111111111111111111"}),
                "too_long_path": render_path_template(
                    template,
                    {"address": "111111111111111111111111111111111111111111111"},
                ),
                "encoded_traversal_path": render_path_template(template, {"address": "%2e%2e%2fhealth"}),
                "extra_segment_path": render_path_template(template, {"address": "not-an-address"}) + "/extra",
                "query_injection_path": render_path_template(template, {"address": "not-an-address"}) + "?url=https://evil.example",
            }
        else:
            targets[cluster_id] = {"path": path}
    return targets


def build_discovered_burp_observation_plan(
    clusters: list[dict[str, Any]],
    probe_targets: dict[str, Any],
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    cluster_ids = {str(cluster.get("id")) for cluster in clusters}

    def add_once(item: dict[str, Any]) -> None:
        if any(existing.get("id") == item.get("id") for existing in plan):
            return
        plan.append(item)

    if "health" in cluster_ids and (probe_targets.get("health") or {}).get("path"):
        add_once(
            {
                "id": "burp_observe_health",
                "method": "GET",
                "path": probe_targets["health"]["path"],
                "headers": {"User-Agent": "InferForge-Burp-Observe/0.1"},
                "expected_statuses": [200],
                "cluster": "health",
            }
        )

    if "quote" in cluster_ids and (probe_targets.get("quote") or {}).get("path"):
        add_once(
            {
                "id": "burp_observe_quote_invalid_body",
                "method": "POST",
                "path": probe_targets["quote"]["path"],
                "headers": {
                    "User-Agent": "InferForge-Burp-Observe/0.1",
                    "Origin": "{origin}",
                    "Content-Type": "application/json",
                },
                "body": "{}",
                "expected_statuses": [400, 422],
                "cluster": "quote",
            }
        )

    rpc_target = probe_targets.get("solana-rpc-http") or {}
    if "solana-rpc-http" in cluster_ids and rpc_target.get("path"):
        add_once(
            {
                "id": "burp_observe_rpc_get_health",
                "method": "POST",
                "path": rpc_target["path"],
                "headers": {
                    "User-Agent": "InferForge-Burp-Observe/0.1",
                    "Origin": "{origin}",
                    "Content-Type": "application/json",
                },
                "body_json": {"jsonrpc": "2.0", "id": 1, "method": "getHealth"},
                "expected_statuses": [200, 400, 403, 502],
                "cluster": "solana-rpc-http",
            }
        )

    orca_target = probe_targets.get("orca-pools") or {}
    if "orca-pools" in cluster_ids and orca_target.get("invalid_address_path"):
        add_once(
            {
                "id": "burp_observe_orca_invalid_address",
                "method": "GET",
                "path": orca_target["invalid_address_path"],
                "headers": {"User-Agent": "InferForge-Burp-Observe/0.1"},
                "expected_statuses": [400, 404],
                "cluster": "orca-pools",
            }
        )

    for cluster in clusters:
        cluster_id = str(cluster.get("id") or "")
        if cluster_id in {"health", "quote", "solana-rpc-http", "solana-rpc-ws", "orca-pools"}:
            continue
        if cluster.get("kind") == "rewrite-proxy":
            continue
        target = probe_targets.get(cluster_id) or {}
        path = target.get("path")
        if not is_concrete_probe_path(path):
            continue
        add_once(
            {
                "id": f"burp_observe_{safe_probe_id(cluster_id)}",
                "method": "HEAD",
                "path": path,
                "headers": {"User-Agent": "InferForge-Burp-Observe/0.1"},
                "expected_statuses": [200, 204, 400, 403, 404, 405],
                "cluster": cluster_id,
            }
        )

    return plan


def build_rewrite_review_observation_candidate(cluster: dict[str, Any]) -> dict[str, Any] | None:
    if cluster.get("kind") != "rewrite-proxy":
        return None
    cluster_id = str(cluster.get("id") or "")
    path_template = str(cluster.get("path") or "")
    if not cluster_id or not path_template:
        return None

    discovery = cluster.get("discovery") or {}
    rewrites = discovery.get("rewrites") or []
    fixed_upstreams = list(discovery.get("fixed_upstreams") or [])
    example_path = render_path_template(path_template, {"path": "<approved-read-only-path>"})
    if example_path == path_template and "{" not in path_template:
        example_path = path_template

    return {
        "id": f"review_observe_{safe_probe_id(cluster_id)}_approved_path",
        "cluster": cluster_id,
        "type": "burp-http-observation",
        "status": "review-only",
        "method": "GET",
        "path_template": path_template,
        "example_path": example_path,
        "source_refs": list(cluster.get("source_refs") or []),
        "rewrites": rewrites,
        "fixed_upstreams": fixed_upstreams,
        "approval_required": [
            "Choose exactly one known safe read-only concrete path under this rewrite source.",
            "Confirm the upstream request is non-mutating and does not require secrets in the URL.",
            f"Add the concrete path to `burp_observation_plan` for cluster `{cluster_id}` before automated Burp observation.",
        ],
        "promote_to_burp_observation_plan": {
            "id": f"burp_observe_{safe_probe_id(cluster_id)}_reviewed_path",
            "method": "GET",
            "path": PLACEHOLDER_APPROVED_CONCRETE_PATH,
            "headers": {"User-Agent": "InferForge-Burp-Observe/0.1"},
            "expected_statuses": [200, 204, 400, 403, 404, 405, 502],
            "cluster": cluster_id,
        },
        "safety": "Review-only candidate. InferForge will not execute this until the profile contains a concrete approved observation path.",
    }


def review_observation_candidates_for_cluster(cluster: dict[str, Any]) -> list[dict[str, Any]]:
    discovery = cluster.get("discovery") or {}
    candidates = [
        json_clone(item)
        for item in discovery.get("review_observation_candidates", [])
        if isinstance(item, dict)
    ]
    if candidates:
        return candidates
    rewrite_candidate = build_rewrite_review_observation_candidate(cluster)
    return [rewrite_candidate] if rewrite_candidate else []


def build_discovered_review_observation_candidates(clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cluster in clusters:
        cluster_candidates = review_observation_candidates_for_cluster(cluster)
        if not cluster_candidates:
            continue
        discovery = cluster.setdefault("discovery", {})
        discovery["review_observation_candidates"] = cluster_candidates
        for candidate in cluster_candidates:
            candidate_id = str(candidate.get("id") or "")
            if not candidate_id or candidate_id in seen:
                continue
            seen.add(candidate_id)
            candidates.append(json_clone(candidate))
    return candidates


def build_orca_baseline_review_candidate() -> dict[str, Any]:
    return {
        "id": "review_orca_single_pool_baseline",
        "cluster": "orca-pools",
        "type": "single-address-baseline",
        "status": "review-only",
        "command_templates": [
            f"python3 scripts/inferforge.py collect-orca-baseline --address {PLACEHOLDER_APPROVED_POOL_ADDRESS}",
            "python3 scripts/inferforge.py audit --include-external --ws-resource-probes",
        ],
        "approval_required": [
            "Use one approved known pool address only, or rely on a source-known pool list reviewed for the target.",
            "Do not enumerate pool addresses or run repeated upstream baseline requests.",
            "Review cache headers and response shape only; do not store full upstream bodies.",
        ],
        "safety": "Single approved/source-known address baseline only. No pool enumeration is performed.",
    }


def collect_review_observation_candidates(profile: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(item: dict[str, Any]) -> None:
        candidate_id = str(item.get("id") or "")
        if not candidate_id or candidate_id in seen:
            return
        seen.add(candidate_id)
        candidates.append(json_clone(item))

    for item in profile.get("review_observation_candidates", []) or []:
        if isinstance(item, dict):
            add(item)
    for cluster in profile.get("clusters", []) or []:
        if not isinstance(cluster, dict):
            continue
        for item in review_observation_candidates_for_cluster(cluster):
            add(item)
    return candidates


def find_review_observation_candidate(profile: dict[str, Any], candidate_id: str) -> dict[str, Any] | None:
    for candidate in collect_review_observation_candidates(profile):
        if str(candidate.get("id") or "") == candidate_id:
            return candidate
    return None


def is_safe_concrete_local_path(path: str) -> bool:
    return concrete_local_path_problem(path) is None


def validate_candidate_promotion_path(candidate: dict[str, Any], path: str) -> None:
    if not is_safe_concrete_local_path(path):
        raise ValueError("Approved path must be a concrete local path such as /api/proxy/status; URLs, placeholders, braces, angle brackets, and whitespace are not allowed.")
    path_template = str(candidate.get("path_template") or "")
    if path_template and not path_pattern_matches(path_template, path.split("?", 1)[0]):
        raise ValueError(f"Approved path `{path}` does not match candidate template `{path_template}`.")


def promote_review_observation_candidate(
    profile: dict[str, Any],
    *,
    candidate_id: str,
    approved_path: str,
    observation_id: str | None = None,
    method: str | None = None,
    expected_statuses: list[int] | None = None,
    note: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = find_review_observation_candidate(profile, candidate_id)
    if candidate is None:
        raise ValueError(f"Review observation candidate not found: {candidate_id}")
    if candidate.get("type") != "burp-http-observation":
        raise ValueError(f"Candidate `{candidate_id}` is type `{candidate.get('type')}`, not a Burp HTTP observation candidate.")
    validate_candidate_promotion_path(candidate, approved_path)

    template = json_clone(candidate.get("promote_to_burp_observation_plan") or {})
    observation = {
        "id": observation_id or template.get("id") or f"burp_observe_{safe_probe_id(candidate_id)}",
        "method": str(method or template.get("method") or candidate.get("method") or "GET").upper(),
        "path": approved_path,
        "headers": template.get("headers") or {"User-Agent": "InferForge-Burp-Observe/0.1"},
        "expected_statuses": expected_statuses or template.get("expected_statuses") or [200, 204, 400, 403, 404, 405, 502],
        "cluster": template.get("cluster") or candidate.get("cluster") or "unknown",
        "source_candidate_id": candidate_id,
        "reviewed": True,
    }
    if note:
        observation["review_note"] = note

    promoted_profile = public_profile(profile)
    promoted_profile.setdefault("review_observation_candidates", collect_review_observation_candidates(profile))
    plan = [json_clone(item) for item in promoted_profile.get("burp_observation_plan", []) or []]
    for item in plan:
        if item.get("id") != observation["id"]:
            continue
        if item.get("method") == observation["method"] and item.get("path") == observation["path"] and item.get("cluster") == observation["cluster"]:
            promoted_profile["burp_observation_plan"] = plan
            return promoted_profile, observation
        raise ValueError(f"Observation id `{observation['id']}` already exists with a different path or method.")
    plan.append(observation)
    promoted_profile["burp_observation_plan"] = plan
    promotions = promoted_profile.setdefault("review_promotions", [])
    promotions.append(
        {
            "generated_at": utc_now(),
            "candidate_id": candidate_id,
            "observation_id": observation["id"],
            "path": approved_path,
            "cluster": observation["cluster"],
            "method": observation["method"],
            "note": note,
            "safety": "Profile edit only. Promotion does not send HTTP traffic; run burp-sync --observe separately to collect evidence.",
        }
    )
    return promoted_profile, observation


def priority_rank(priority: str) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(priority, 0)


def build_discovered_profile(
    route_inventory: dict[str, Any],
    *,
    name: str,
    display_name: str,
    target: str,
    source_root: Path,
) -> dict[str, Any]:
    routes = route_inventory.get("routes", [])
    rewrites = route_inventory.get("rewrites", [])
    custom_server_entrypoints = route_inventory.get("custom_server_entrypoints", [])
    middleware_entries = route_inventory.get("middleware", [])
    server_action_entries = route_inventory.get("server_actions", [])
    entrypoints = [*routes, *rewrites, *custom_server_entrypoints]
    clusters = merge_discovered_clusters(entrypoints)
    enabled_strategy_sets = sorted({cluster["strategy_set"] for cluster in clusters if cluster.get("strategy_set")})
    source_peeks = [
        {
            "endpoint": f"{cluster.get('method')} {cluster.get('path')}",
            "cluster_ids": [cluster["id"]],
            "files": cluster.get("source_refs", []),
            "line_patterns": {},
            "conclusion": "Discovered route source context; add profile-specific line patterns before relying on source claims.",
        }
        for cluster in clusters
    ]
    probe_targets = build_probe_targets_from_clusters(clusters)
    burp_observation_plan = build_discovered_burp_observation_plan(clusters, probe_targets)
    review_observation_candidates = build_discovered_review_observation_candidates(clusters)
    websocket_observation = None
    if "solana-rpc-ws" in {cluster.get("id") for cluster in clusters} or "solana-rpc-http" in {cluster.get("id") for cluster in clusters}:
        websocket_observation = {
            "id": "burp_observe_ws_upgrade",
            "path": (probe_targets.get("solana-rpc-ws") or probe_targets.get("solana-rpc-http") or {}).get("path", "/api/rpc/solana/devnet"),
            "cluster": "solana-rpc-ws",
            "expected_statuses": [101],
            "subscribe_method": "slotSubscribe",
        }

    try:
        source_root_value = str(source_root.resolve().relative_to(ROOT))
    except ValueError:
        source_root_value = str(source_root.resolve())

    frameworks = ["Next.js"]
    if route_inventory.get("summary", {}).get("app_router_route_count"):
        frameworks.append("Next.js App Router")
    if route_inventory.get("summary", {}).get("pages_router_api_route_count"):
        frameworks.append("Next.js Pages Router")
    if middleware_entries:
        frameworks.append("Next.js Middleware")
    if server_action_entries:
        frameworks.append("Next.js Server Actions")
    next_config_runtime = (route_inventory.get("summary", {}) or {}).get("next_config_runtime") or {}
    if next_config_runtime.get("base_path"):
        frameworks.append("Next.js basePath")
    if next_config_runtime.get("trailing_slash") is not None:
        frameworks.append("Next.js trailingSlash")
    if next_config_runtime.get("i18n_configured"):
        frameworks.append("Next.js i18n")

    return {
        "schema_version": 1,
        "name": name,
        "display_name": display_name,
        "description": "Starter target profile generated from static Next.js route, rewrite, middleware, and custom-server discovery. Review and edit before a full audit.",
        "target_type": "discovered-nextjs-app",
        "frameworks": frameworks,
        "default_target": target,
        "default_source_root": source_root_value,
        "strategy_sets": enabled_strategy_sets,
        "safety": {
            "no_wallet_signing": True,
            "no_transaction_submission": True,
            "no_burp_scanner": True,
            "no_broad_fuzzing": True,
            "prefer_loopback_targets": True,
        },
        "probe_targets": probe_targets,
        "clusters": clusters,
        "source_peeks": source_peeks,
        "burp_observation_plan": burp_observation_plan,
        "review_observation_candidates": review_observation_candidates,
        "websocket_observation": websocket_observation,
        "discovery": {
            "generated_at": route_inventory.get("generated_at"),
            "route_inventory": ROUTE_INVENTORY_ARTIFACT,
            "route_count": route_inventory.get("summary", {}).get("route_count", 0),
            "rewrite_count": route_inventory.get("summary", {}).get("rewrite_count", 0),
            "custom_server_entrypoint_count": route_inventory.get("summary", {}).get("custom_server_entrypoint_count", 0),
            "middleware_count": route_inventory.get("summary", {}).get("middleware_count", 0),
            "server_action_file_count": route_inventory.get("summary", {}).get("server_action_file_count", 0),
            "server_action_export_count": route_inventory.get("summary", {}).get("server_action_export_count", 0),
            "redirect_count": route_inventory.get("summary", {}).get("redirect_count", 0),
            "header_route_count": route_inventory.get("summary", {}).get("header_route_count", 0),
            "route_policy_count": route_inventory.get("summary", {}).get("route_policy_count", 0),
            "entrypoint_count": route_inventory.get("summary", {}).get("entrypoint_count", len(entrypoints)),
            "surface_count": route_inventory.get("summary", {}).get("surface_count", len(entrypoints) + len(middleware_entries)),
            "next_config": route_inventory.get("next_config"),
            "review_required": True,
            "notes": [
                "Static discovery can identify likely routes and strategy sets, but probe templates may still need profile-specific tuning.",
                "Unknown or generic routes are included as nextjs-api-routes clusters and should be reviewed before active probing.",
                "Next.js rewrites are included as fixed-upstream rewrite-proxy clusters for classification/source context; review before adding active probes.",
                "Next.js middleware/proxy files are included as cross-cutting source context only; they do not generate active probes.",
                "Next.js redirects and headers are included as route-policy source context only; they do not generate active probes.",
                "Custom server WebSocket upgrade handlers are included when static path prefixes can be resolved; review generated WS probes before active testing.",
            ],
        },
    }


def load_target_profile(profile_path: str | None) -> dict[str, Any]:
    path = resolve_repo_path(profile_path or DEFAULT_PROFILE_PATH)
    if path.exists():
        return normalize_target_profile(json.loads(read_text(path)), profile_path=path)
    return normalize_target_profile(default_target_profile(), profile_path=path)


def profile_display_name(profile: dict[str, Any] | None) -> str:
    if not profile:
        return "Target"
    return str(profile.get("display_name") or profile.get("name") or "Target")


def profile_summary(profile: dict[str, Any] | None) -> dict[str, Any]:
    if not profile:
        return {}
    return {
        "schema_version": profile.get("schema_version"),
        "name": profile.get("name"),
        "display_name": profile.get("display_name"),
        "target_type": profile.get("target_type"),
        "frameworks": profile.get("frameworks", []),
        "strategy_sets": profile.get("strategy_sets", []),
        "profile_path": profile.get("_profile_path"),
        "loaded_from": profile.get("_profile_loaded_from"),
    }


def resolve_target(args: argparse.Namespace, profile: dict[str, Any]) -> str:
    return str(args.target or profile.get("default_target") or DEFAULT_TARGET).rstrip("/")


def resolve_source_root(args: argparse.Namespace, profile: dict[str, Any]) -> Path:
    source_root = args.source_root or profile.get("default_source_root") or str(DEFAULT_SOURCE_ROOT)
    return resolve_repo_path(source_root)


def resolve_run_context(args: argparse.Namespace) -> tuple[dict[str, Any], Path, str, Path]:
    profile = load_target_profile(args.profile)
    artifact_dir = Path(args.artifact_dir).resolve()
    target = resolve_target(args, profile)
    source_root = resolve_source_root(args, profile)
    return profile, artifact_dir, target, source_root


def source_ref_to_path(source_root: Path, ref: str) -> Path:
    raw = str(ref)
    path = Path(raw)
    if path.is_absolute():
        return path
    if raw == source_root.name or raw.startswith(f"{source_root.name}/"):
        return (ROOT / raw).resolve()
    return (source_root / raw).resolve()


def source_ref_for_artifact(source_root: Path, ref: str) -> str:
    path = source_ref_to_path(source_root, ref)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_target_profile_artifact(
    artifact_dir: Path,
    profile: dict[str, Any],
    target: str,
    source_root: Path,
) -> dict[str, Any]:
    doc = public_profile(profile)
    declared_clusters = json_clone(doc.get("clusters", []))
    clusters = build_clusters(profile, source_root)
    doc["generated_at"] = utc_now()
    doc["status"] = "loaded"
    doc["profile_path"] = profile.get("_profile_path")
    doc["loaded_from"] = profile.get("_profile_loaded_from")
    doc["declared_clusters"] = declared_clusters
    doc["effective"] = {
        "target": target,
        "source_root": str(source_root),
        "artifact_dir": str(artifact_dir),
        "enabled_strategy_sets": sorted(enabled_strategy_set_ids(profile)),
        "strategy_registry": STRATEGY_REGISTRY_ARTIFACT,
    }
    doc["clusters"] = clusters["clusters"]
    write_json(artifact_dir / TARGET_PROFILE_ARTIFACT, doc)
    write_json(artifact_dir / STRATEGY_REGISTRY_ARTIFACT, build_strategy_registry_artifact(profile, clusters))
    write_json(artifact_dir / PROFILE_VALIDATION_ARTIFACT, build_profile_validation_artifact(profile, clusters, source_root))
    return doc


def target_profile_artifact_paths(artifact_dir: Path) -> list[Path]:
    return [
        artifact_dir / TARGET_PROFILE_ARTIFACT,
        artifact_dir / STRATEGY_REGISTRY_ARTIFACT,
        artifact_dir / PROFILE_VALIDATION_ARTIFACT,
    ]


def redact_text(value: str | None, *, max_chars: int = 500) -> str | None:
    if value is None:
        return None
    redacted = SECRET_TEXT_RE.sub(lambda match: f"{match.group(1) or match.group(2)}[redacted]", value)
    if len(redacted) > max_chars:
        return redacted[:max_chars] + "...[truncated]"
    return redacted


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADER_NAMES:
            redacted[key] = REDACTED_VALUE
        else:
            redacted[key] = value
    return redacted


def sensitive_param_name(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ["token", "secret", "password", "api_key", "apikey", "key", "auth", "cookie"])


def redact_observed_value(key: str, value: str, *, sensitive: bool = False) -> str:
    if sensitive or sensitive_param_name(key):
        return REDACTED_VALUE
    redacted = redact_text(value, max_chars=500)
    return REDACTED_VALUE if redacted is None else redacted


def parse_cookie_header(value: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in value.split(";"):
        item = part.strip()
        if not item:
            continue
        if "=" in item:
            key, cookie_value = item.split("=", 1)
        else:
            key, cookie_value = item, ""
        key = key.strip()
        if key:
            cookies[key] = cookie_value.strip()
    return cookies


def parse_query_context(path: str) -> dict[str, list[str]]:
    parsed = urllib.parse.urlparse(path)
    query: dict[str, list[str]] = {}
    for key, values in urllib.parse.parse_qs(parsed.query, keep_blank_values=True).items():
        query[key] = [redact_observed_value(key, str(value)) for value in values]
    return query


def build_request_context(method: str, path: str, headers: dict[str, str] | None = None, host: str | None = None) -> dict[str, Any]:
    raw_headers = headers or {}
    normalized_headers = {str(key).lower(): str(value) for key, value in raw_headers.items()}
    observed_host = host or normalized_headers.get("host", "")
    redacted_headers = {
        key: redact_observed_value(key, value, sensitive=key in SENSITIVE_HEADER_NAMES)
        for key, value in normalized_headers.items()
    }
    cookie_header = normalized_headers.get("cookie", "")
    raw_cookies = {} if cookie_header == REDACTED_VALUE else parse_cookie_header(cookie_header)
    cookies = {name: REDACTED_VALUE for name in raw_cookies}
    query = parse_query_context(path)
    return {
        "method": str(method).upper(),
        "path": path,
        "path_without_query": path.split("?", 1)[0],
        "host": observed_host,
        "headers": redacted_headers,
        "header_names": sorted(redacted_headers),
        "query": query,
        "query_keys": sorted(query),
        "cookies": cookies,
        "cookie_names": sorted(cookies),
        "redaction": {
            "sensitive_headers": sorted(key for key in normalized_headers if key in SENSITIVE_HEADER_NAMES),
            "cookie_values": "redacted" if cookies else "absent",
        },
    }


def request_context_signature(context: dict[str, Any]) -> str:
    return json.dumps(
        {
            "method": context.get("method"),
            "path": context.get("path"),
            "host": context.get("host"),
            "headers": context.get("headers", {}),
            "query": context.get("query", {}),
            "cookie_names": context.get("cookie_names", []),
        },
        sort_keys=True,
    )


def parse_http_headers(lines: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in lines:
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def split_http_message(raw: str) -> tuple[str, list[str], str]:
    head, sep, body = raw.partition("\r\n\r\n")
    if not sep:
        head, _, body = raw.partition("\n\n")
    lines = head.replace("\r\n", "\n").splitlines()
    start_line = lines[0] if lines else ""
    return start_line, lines[1:], body


def normalize_request_path(target: str) -> str:
    parsed = urllib.parse.urlparse(target)
    if parsed.scheme and parsed.netloc:
        path = parsed.path or "/"
        return urllib.parse.urlunparse(("", "", path, "", parsed.query, ""))
    return target or "/"


def parse_raw_http_request(raw: str) -> dict[str, Any]:
    start_line, header_lines, _ = split_http_message(raw)
    parts = start_line.split()
    method = parts[0].upper() if parts else ""
    path = normalize_request_path(parts[1]) if len(parts) > 1 else "/"
    headers = parse_http_headers(header_lines)
    return {
        "method": method,
        "path": path,
        "headers": headers,
        "host": headers.get("host", ""),
        "user_agent": headers.get("user-agent", ""),
    }


def parse_raw_http_response(raw: str) -> dict[str, Any]:
    if not raw:
        return {"status": None, "headers": {}, "body": ""}

    start_line, header_lines, body = split_http_message(raw)
    parts = start_line.split()
    status = None
    if len(parts) > 1:
        try:
            status = int(parts[1])
        except ValueError:
            status = None
    headers = parse_http_headers(header_lines)
    return {"status": status, "headers": headers, "body": body}


def parse_http_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_json_object(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def is_placeholder_env_value(value: str | None) -> bool:
    return bool(value and PLACEHOLDER_ENV_RE.fullmatch(value.strip()))


def parse_dotenv_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def classify_env_value(value: str | None, *, secret: bool) -> dict[str, Any]:
    if value is None:
        return {"status": "missing"}
    if value == "":
        return {"status": "empty"}
    if is_placeholder_env_value(value):
        return {"status": "placeholder"}
    result: dict[str, Any] = {"status": "configured"}
    if not secret:
        result["value"] = value
    return result


def is_websocket_upgrade_observation(request: dict[str, Any], response: dict[str, Any]) -> bool:
    request_headers = request.get("headers", {})
    response_headers = response.get("headers", {})
    request_upgrade = request_headers.get("upgrade", "").lower() == "websocket"
    response_upgrade = response_headers.get("upgrade", "").lower() == "websocket"
    request_connection = request_headers.get("connection", "").lower()
    response_connection = response_headers.get("connection", "").lower()
    return (
        response.get("status") == 101
        and request_upgrade
        and response_upgrade
        and "upgrade" in request_connection
        and "upgrade" in response_connection
    )


def decode_mcp_text_payload(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""

    try:
        parsed = json.loads(stripped, strict=False)
    except json.JSONDecodeError:
        return text

    if isinstance(parsed, list) and all(isinstance(item, dict) for item in parsed):
        chunks = [
            item.get("text", "")
            for item in parsed
            if item.get("type") == "text" and isinstance(item.get("text"), str)
        ]
        if chunks:
            return "\n\n".join(chunks)

    if isinstance(parsed, dict) and isinstance(parsed.get("text"), str):
        return parsed["text"]

    return text


def parse_burp_mcp_history_items(text: str) -> list[dict[str, Any]]:
    payload = decode_mcp_text_payload(text)
    stripped = payload.strip()
    if not stripped:
        return []

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        return [parsed]

    decoder = json.JSONDecoder(strict=False)
    index = 0
    items: list[dict[str, Any]] = []
    while index < len(payload):
        while index < len(payload) and payload[index].isspace():
            index += 1
        if index >= len(payload):
            break
        try:
            item, next_index = decoder.raw_decode(payload, index)
        except json.JSONDecodeError as error:
            snippet = payload[index:index + 120].replace("\n", "\\n")
            raise ValueError(f"Could not parse Burp MCP history item near offset {index}: {snippet}") from error
        if isinstance(item, dict):
            items.append(item)
        index = next_index

    return items


def normalize_burp_history_items(
    items: list[dict[str, Any]],
    *,
    target_netloc: str | None,
    source: str,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []

    for item in items:
        request = parse_raw_http_request(str(item.get("request") or ""))
        response = parse_raw_http_response(str(item.get("response") or ""))
        host = request["host"]
        if target_netloc and host != target_netloc:
            continue

        response_headers = response["headers"]
        response_body = response["body"]
        method = "WS" if is_websocket_upgrade_observation(request, response) else request["method"]
        request_context = build_request_context(method, request["path"], request.get("headers", {}), host)
        observations.append(
            {
                "ts": parse_http_date(response_headers.get("date")) or utc_now(),
                "source": source,
                "method": method,
                "path": request["path"],
                "host": host,
                "status": response["status"],
                "content_type": response_headers.get("content-type"),
                "request_user_agent": request["user_agent"],
                "request_context": request_context,
                "response_sample": response_body[:500],
                "notes": item.get("notes", ""),
            }
        )

    return observations


def dedupe_observations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = (
            row.get("method"),
            row.get("path"),
            row.get("host"),
            row.get("status"),
            row.get("request_user_agent"),
            row.get("response_sample"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def origin_for(target: str) -> str:
    parsed = urllib.parse.urlparse(target)
    return f"{parsed.scheme}://{parsed.netloc}"


def target_to_ws(target: str) -> str:
    parsed = urllib.parse.urlparse(target)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urllib.parse.urlunparse((scheme, parsed.netloc, "", "", "", ""))


def socket_open(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def target_lock_key(target: str) -> str:
    parsed = urllib.parse.urlparse(target)
    key = f"{parsed.scheme or 'http'}://{parsed.netloc or parsed.path}".rstrip("/")
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"target-{digest}"


def process_is_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def read_lock_metadata(path: Path) -> dict[str, Any]:
    try:
        return json.loads(read_text(path))
    except (OSError, json.JSONDecodeError):
        return {}


class TargetProbeLock:
    def __init__(self, target: str, *, purpose: str, stale_after_seconds: int = 3600) -> None:
        self.target = target.rstrip("/")
        self.purpose = purpose
        self.stale_after_seconds = stale_after_seconds
        self.path = DEFAULT_ARTIFACT_DIR / "locks" / f"{target_lock_key(self.target)}.json"
        self.acquired = False

    def __enter__(self) -> "TargetProbeLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                existing = read_lock_metadata(self.path)
                pid = existing.get("pid")
                age = time.time() - self.path.stat().st_mtime if self.path.exists() else 0
                stale = age > self.stale_after_seconds or not process_is_alive(int(pid) if isinstance(pid, int) else None)
                if stale:
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                raise RuntimeError(
                    "Active probes are already running for this target: "
                    f"target={existing.get('target', self.target)} "
                    f"purpose={existing.get('purpose', 'unknown')} "
                    f"pid={existing.get('pid', 'unknown')} "
                    f"lock={self.path}"
                )
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "created_at": utc_now(),
                        "pid": os.getpid(),
                        "target": self.target,
                        "purpose": self.purpose,
                        "safety": "Prevents concurrent active probes from creating resource-control false positives.",
                    },
                    handle,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
            self.acquired = True
            return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if not self.acquired:
            return
        try:
            existing = read_lock_metadata(self.path)
            if existing.get("pid") == os.getpid():
                self.path.unlink()
        except FileNotFoundError:
            pass
        finally:
            self.acquired = False


def command_result(cmd: list[str], cwd: Path = ROOT, timeout: int = 10) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "output": proc.stdout[-4000:],
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "returncode": None, "output": str(error)}


class McpSseClient:
    def __init__(self, url: str, *, timeout: int = 10) -> None:
        self.url = url.rstrip("/") + "/"
        self.timeout = timeout
        self.response: Any = None
        self.message_url: str | None = None
        self.next_id = 1

    def __enter__(self) -> "McpSseClient":
        request = urllib.request.Request(
            self.url,
            headers={"Accept": "text/event-stream"},
        )
        self.response = urllib.request.urlopen(request, timeout=self.timeout)
        endpoint = self._read_sse_data(expected_event="endpoint")
        if not endpoint:
            raise RuntimeError("Burp MCP SSE endpoint did not provide a session endpoint")
        self.message_url = urllib.parse.urljoin(self.url, endpoint)
        self._initialize()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.response:
            self.response.close()

    def _readline(self) -> str:
        if not self.response:
            raise RuntimeError("MCP SSE connection is not open")
        return self.response.readline().decode("utf-8", errors="replace").rstrip("\r\n")

    def _read_sse_data(self, *, expected_event: str | None = None, request_id: int | None = None) -> Any:
        event: str | None = None
        data_lines: list[str] = []
        while True:
            line = self._readline()
            if line == "":
                if not data_lines:
                    continue
                data = "\n".join(data_lines)
                if expected_event and event != expected_event:
                    event = None
                    data_lines = []
                    continue
                if request_id is None:
                    return data
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    event = None
                    data_lines = []
                    continue
                if payload.get("id") == request_id:
                    if payload.get("error"):
                        raise RuntimeError(json.dumps(payload["error"], sort_keys=True))
                    return payload.get("result")
                event = None
                data_lines = []
                continue
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].strip())

    def _post(self, payload: dict[str, Any]) -> None:
        if not self.message_url:
            raise RuntimeError("MCP message endpoint is not ready")
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.message_url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            response.read()

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        request_id = self.next_id
        self.next_id += 1
        self._post(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        return self._read_sse_data(request_id=request_id)

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._post({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _initialize(self) -> None:
        self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "inferforge", "version": "0.1"},
            },
        )
        self.notify("notifications/initialized", {})

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self.request("tools/call", {"name": name, "arguments": arguments or {}})
        return result if isinstance(result, dict) else {"raw": result}


def mcp_tool_text(result: dict[str, Any]) -> str:
    content = result.get("content", [])
    chunks = [
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)
    ]
    if chunks:
        return "\n\n".join(chunks)
    if "raw" in result:
        return str(result["raw"])
    return json.dumps(result, sort_keys=False)


def http_request(
    target: str,
    method: str,
    path: str,
    body: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    url = urllib.parse.urljoin(target.rstrip("/") + "/", path.lstrip("/"))
    raw_body = None if body is None else body.encode("utf-8")
    req = urllib.request.Request(url, method=method, data=raw_body, headers=headers or {})
    started = time.monotonic()

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read(MAX_RESPONSE_BYTES + 1)
            response_headers = dict(resp.headers.items())
            status = resp.status
    except urllib.error.HTTPError as error:
        resp_body = error.read(MAX_RESPONSE_BYTES + 1)
        response_headers = dict(error.headers.items())
        status = error.code
    except urllib.error.URLError as error:
        return {
            "ok": False,
            "status": None,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "error": str(error.reason),
            "body_sample": "",
            "body_text": "",
            "body_sha256": None,
            "body_truncated": False,
            "body_length": 0,
            "headers": {},
        }
    except (TimeoutError, socket.timeout) as error:
        return {
            "ok": False,
            "status": None,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "error": str(error),
            "body_sample": "",
            "body_text": "",
            "body_sha256": None,
            "body_truncated": False,
            "body_length": 0,
            "headers": {},
        }

    body_truncated = len(resp_body) > MAX_RESPONSE_BYTES
    if body_truncated:
        resp_body = resp_body[:MAX_RESPONSE_BYTES]
    body_text = resp_body.decode("utf-8", errors="replace")

    return {
        "ok": True,
        "status": status,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "error": None,
        "body_sample": body_text[:MAX_BODY_SAMPLE_CHARS],
        "body_text": body_text,
        "body_sha256": hashlib.sha256(resp_body).hexdigest(),
        "body_truncated": body_truncated,
        "body_length": len(resp_body),
        "headers": response_headers,
    }


def http_request_through_proxy(
    target: str,
    proxy: str,
    method: str,
    path: str,
    body: str | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> dict[str, Any]:
    target_url = urllib.parse.urljoin(target.rstrip("/") + "/", path.lstrip("/"))
    parsed_target = urllib.parse.urlparse(target_url)
    parsed_proxy = urllib.parse.urlparse(proxy)
    if parsed_target.scheme != "http":
        return {
            "ok": False,
            "status": None,
            "duration_ms": 0,
            "error": "burp-observe currently supports HTTP targets only",
            "body_sample": "",
            "body_text": "",
            "body_sha256": None,
            "body_truncated": False,
            "body_length": 0,
            "headers": {},
        }
    if parsed_proxy.scheme != "http" or not parsed_proxy.hostname:
        return {
            "ok": False,
            "status": None,
            "duration_ms": 0,
            "error": "proxy must be an http://host:port URL",
            "body_sample": "",
            "body_text": "",
            "body_sha256": None,
            "body_truncated": False,
            "body_length": 0,
            "headers": {},
        }

    request_headers = dict(headers or {})
    request_headers.setdefault("Host", parsed_target.netloc)
    request_headers.setdefault("Connection", "close")
    raw_body = None if body is None else body.encode("utf-8")
    if raw_body is not None:
        request_headers.setdefault("Content-Length", str(len(raw_body)))

    started = time.monotonic()
    conn = http.client.HTTPConnection(
        parsed_proxy.hostname,
        parsed_proxy.port or 8080,
        timeout=timeout,
    )
    try:
        conn.request(method, target_url, body=raw_body, headers=request_headers)
        resp = conn.getresponse()
        resp_body = resp.read(MAX_RESPONSE_BYTES + 1)
        response_headers = {key: value for key, value in resp.getheaders()}
        status = resp.status
    except (OSError, http.client.HTTPException) as error:
        return {
            "ok": False,
            "status": None,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "error": str(error),
            "body_sample": "",
            "body_text": "",
            "body_sha256": None,
            "body_truncated": False,
            "body_length": 0,
            "headers": {},
        }
    finally:
        conn.close()

    body_truncated = len(resp_body) > MAX_RESPONSE_BYTES
    if body_truncated:
        resp_body = resp_body[:MAX_RESPONSE_BYTES]
    body_text = resp_body.decode("utf-8", errors="replace")

    return {
        "ok": True,
        "status": status,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "error": None,
        "body_sample": body_text[:MAX_BODY_SAMPLE_CHARS],
        "body_text": body_text,
        "body_sha256": hashlib.sha256(resp_body).hexdigest(),
        "body_truncated": body_truncated,
        "body_length": len(resp_body),
        "headers": response_headers,
    }


def is_loopback_target(target: str) -> bool:
    hostname = urllib.parse.urlparse(target).hostname
    if not hostname:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def render_profile_headers(headers: dict[str, Any], target: str) -> dict[str, str]:
    origin = origin_for(target)
    rendered = {}
    for key, value in headers.items():
        rendered[str(key)] = str(value).replace("{origin}", origin)
    return rendered


def build_burp_observation_plan(target: str, profile: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if profile and "burp_observation_plan" in profile:
        plan = []
        for index, item in enumerate(profile.get("burp_observation_plan") or []):
            if not isinstance(item, dict):
                raise ValueError(f"Invalid Burp observation entry at index {index}: expected object.")
            if not is_active_observation_item(item):
                continue
            label = active_observation_label(item, index)
            method = str(item.get("method") or "").upper()
            if method not in HTTP_METHODS:
                raise ValueError(f"Invalid active Burp observation `{label}`: unsupported method `{method or '(missing)'}`.")
            path_problem = concrete_local_path_problem(item.get("path"))
            if path_problem:
                raise ValueError(f"Invalid active Burp observation `{label}`: {path_problem}.")
            body = item.get("body")
            if "body_json" in item:
                body = json.dumps(item["body_json"])
            plan.append(
                {
                    "id": item.get("id") or f"burp_observe_{index}",
                    "method": method,
                    "path": item["path"],
                    "headers": render_profile_headers(item.get("headers", {}), target),
                    "body": body,
                    "expected_statuses": item.get("expected_statuses", []),
                    "cluster": item.get("cluster", "unknown"),
                }
            )
        return plan

    origin = origin_for(target)
    return [
        {
            "id": "burp_observe_health",
            "method": "GET",
            "path": "/health",
            "headers": {"User-Agent": "InferForge-Burp-Observe/0.1"},
            "body": None,
            "expected_statuses": [200],
            "cluster": "health",
        },
        {
            "id": "burp_observe_quote_invalid_body",
            "method": "POST",
            "path": "/api/quote",
            "headers": {
                "User-Agent": "InferForge-Burp-Observe/0.1",
                "Origin": origin,
                "Content-Type": "application/json",
            },
            "body": "{}",
            "expected_statuses": [400],
            "cluster": "quote",
        },
        {
            "id": "burp_observe_rpc_get_health",
            "method": "POST",
            "path": "/api/rpc/solana/devnet",
            "headers": {
                "User-Agent": "InferForge-Burp-Observe/0.1",
                "Origin": origin,
                "Content-Type": "application/json",
            },
            "body": json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getHealth"}),
            "expected_statuses": [200],
            "cluster": "solana-rpc-http",
        },
        {
            "id": "burp_observe_orca_invalid_address",
            "method": "GET",
            "path": "/api/orca/pools/not-an-address",
            "headers": {"User-Agent": "InferForge-Burp-Observe/0.1"},
            "body": None,
            "expected_statuses": [400],
            "cluster": "orca-pools",
        },
    ]


def build_burp_history_regex(
    target: str,
    observation_plan: list[dict[str, Any]],
    *,
    include_ws_upgrade: bool = False,
) -> str:
    history_regex_terms = []
    for item in observation_plan:
        user_agent = (item.get("headers") or {}).get("User-Agent")
        if user_agent:
            history_regex_terms.append(re.escape(f"User-Agent: {user_agent}"))
    if not history_regex_terms:
        history_regex_terms.extend(
            re.escape(f"{item['method']} {item['path']}")
            for item in observation_plan
        )
    if include_ws_upgrade:
        history_regex_terms.append(r"Upgrade: websocket")
    return "|".join(dict.fromkeys(history_regex_terms))


def run_ws_upgrade_observation_through_proxy(
    target: str,
    proxy: str,
    node: str,
    source_root: Path,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ws_profile = websocket_observation_config(profile)
    if ws_profile is None:
        return {
            "id": "burp_observe_ws_upgrade",
            "ok": True,
            "skipped": True,
            "status": None,
            "path": None,
            "cluster": "solana-rpc-ws",
            "expected_statuses": [],
            "error": "WebSocket observation disabled by target profile.",
        }
    ws_path = str(ws_profile.get("path") or "/api/rpc/solana/devnet")
    ws_cluster = str(ws_profile.get("cluster") or "solana-rpc-ws")
    ws_expected_statuses = list(ws_profile.get("expected_statuses") or [101])
    subscribe_method = str(ws_profile.get("subscribe_method") or "slotSubscribe")
    path_problem = concrete_local_path_problem(ws_path)
    if path_problem:
        return {
            "id": "burp_observe_ws_upgrade",
            "ok": False,
            "status": None,
            "path": ws_path,
            "cluster": ws_cluster,
            "expected_statuses": ws_expected_statuses,
            "error": f"WebSocket observation path is unsafe: {path_problem}",
        }
    node_path = Path(node)
    if not node_path.exists():
        fallback = command_result(["node", "-v"])
        if not fallback["ok"]:
            return {
                "id": "burp_observe_ws_upgrade",
                "ok": False,
                "status": None,
                "error": f"Node not found at {node}",
            }
        node = "node"

    parsed = urllib.parse.urlparse(target)
    if parsed.scheme != "http":
        return {
            "id": "burp_observe_ws_upgrade",
            "ok": False,
            "status": None,
            "error": "WebSocket upgrade observation currently supports HTTP targets only",
        }
    ws_url = urllib.parse.urlunparse(("ws", parsed.netloc, ws_path, "", "", ""))
    script = """
import fs from 'node:fs'
import { WebSocket } from 'ws'
import proxyAgentPkg from 'https-proxy-agent'

const { HttpsProxyAgent } = proxyAgentPkg
const input = JSON.parse(fs.readFileSync(0, 'utf8'))
const agent = new HttpsProxyAgent(input.proxy)
const started = Date.now()
let opened = false
let messageSeen = false

const ws = new WebSocket(input.url, {
  agent,
  headers: { Origin: input.origin },
  handshakeTimeout: 5000,
  perMessageDeflate: false,
})

const finish = (status, error = null) => {
  console.log(JSON.stringify({
    id: 'burp_observe_ws_upgrade',
    ok: opened,
    status,
    duration_ms: Date.now() - started,
    opened,
    message_seen: messageSeen,
    error,
  }))
  process.exit(opened ? 0 : 1)
}

const timer = setTimeout(() => {
  ws.terminate()
  finish(opened ? 101 : null, opened ? null : 'timeout')
}, 10000)

ws.on('open', () => {
  opened = true
  ws.send(JSON.stringify({ jsonrpc: '2.0', id: 1, method: input.subscribeMethod }))
  setTimeout(() => ws.close(1000, 'done'), 500)
})
ws.on('message', () => {
  messageSeen = true
  clearTimeout(timer)
  ws.close(1000, 'done')
})
ws.on('close', (code, reason) => {
  clearTimeout(timer)
  finish(opened ? 101 : null, opened ? null : `closed ${code} ${reason.toString()}`)
})
ws.on('error', (error) => {
  clearTimeout(timer)
  finish(opened ? 101 : null, error.message)
})
"""
    if not source_root.is_dir():
        return {
            "id": "burp_observe_ws_upgrade",
            "ok": False,
            "status": None,
            "error": f"Source root not found: {source_root}",
        }

    proc = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=str(source_root),
        input=json.dumps(
            {
                "url": ws_url,
                "proxy": proxy,
                "origin": origin_for(target),
                "subscribeMethod": subscribe_method,
            }
        ),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=15,
        check=False,
    )

    parsed_output = parse_json_object(proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "")
    if parsed_output:
        parsed_output["path"] = ws_path
        parsed_output["method"] = "WS"
        parsed_output["cluster"] = ws_cluster
        parsed_output["expected_statuses"] = ws_expected_statuses
        return parsed_output
    return {
        "id": "burp_observe_ws_upgrade",
        "ok": False,
        "status": None,
        "path": ws_path,
        "method": "WS",
        "cluster": ws_cluster,
        "expected_statuses": ws_expected_statuses,
        "error": proc.stdout[-1000:],
    }


def compact_response_attempt(response: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": response.get("status"),
        "duration_ms": response.get("duration_ms"),
        "error": response.get("error"),
        "body_sha256": response.get("body_sha256"),
        "body_sample": response.get("body_sample", "")[:240],
    }


@dataclass(frozen=True)
class Probe:
    id: str
    label: str
    method: str
    path: str
    body: str | None = None
    origin: str | None = None
    content_type: str | None = None
    expected_statuses: tuple[int, ...] = ()
    category: str = "http"
    external: bool = False
    policy_field: str | None = None
    risk: str = "safe"
    referer: str | None = None
    expectation: str = "status"
    strategy_set: str | None = None


def build_probe_headers(probe: Probe) -> dict[str, str]:
    headers: dict[str, str] = {"User-Agent": "InferForge-Local/0.1"}
    if probe.origin:
        headers["Origin"] = probe.origin
    if probe.referer:
        headers["Referer"] = probe.referer
    if probe.content_type:
        headers["Content-Type"] = probe.content_type
    if probe.method == "OPTIONS":
        headers["Access-Control-Request-Method"] = "POST"
        headers["Access-Control-Request-Headers"] = "content-type"
    return headers


def is_next_dev_manifest_error(response: dict[str, Any]) -> bool:
    if response.get("status") != 500:
        return False
    body = response.get("body_text") or response.get("body_sample") or ""
    return (
        "loadManifest" in body
        and "Unexpected end of JSON input" in body
        and ("next-dev-server" in body or "/_error" in body)
    )


def retry_reason_for_probe_response(probe: Probe, response: dict[str, Any]) -> str | None:
    if probe.external:
        return None
    is_generic_nextjs_route = str(probe.risk).startswith("safe-generic-route-")
    if probe.category not in {"quote", "solana-rpc-http", "orca-pools"} and not is_generic_nextjs_route:
        return None
    if response.get("status") is None:
        return "local-request-timeout-or-transport-error"
    if is_next_dev_manifest_error(response):
        return "next-dev-manifest-transient-500"
    return None


def run_probe_request(
    target: str,
    probe: Probe,
    *,
    timeout: int = 20,
    max_attempts: int = 1,
) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
    attempts = []
    retry_reason = None
    response: dict[str, Any] | None = None
    headers = build_probe_headers(probe)

    for attempt_number in range(1, max_attempts + 1):
        response = http_request(
            target=target,
            method=probe.method,
            path=probe.path,
            body=probe.body,
            headers=headers,
            timeout=timeout,
        )
        attempts.append({"attempt": attempt_number, **compact_response_attempt(response)})
        retry_reason = retry_reason_for_probe_response(probe, response)
        if retry_reason is None or attempt_number == max_attempts:
            break
        time.sleep(0.4)

    if response is None:
        raise RuntimeError("probe request produced no response")
    return response, attempts, retry_reason if len(attempts) > 1 else None


def jsonrpc_response_is_error_only(value: Any) -> bool:
    responses = value if isinstance(value, list) else [value]
    if not responses:
        return False

    for item in responses:
        if not isinstance(item, dict):
            return False
        if "result" in item:
            return False
        if "error" not in item:
            return False
    return True


def response_has_internal_error_leak(response: dict[str, Any]) -> bool:
    body = response.get("body_text") or response.get("body_sample") or ""
    lowered = body.lower()
    return any(
        marker in lowered
        for marker in [
            "traceback",
            "syntaxerror:",
            "typeerror:",
            "referenceerror:",
            "at async",
            "node_modules",
            "webpack-internal",
        ]
    )


def evaluate_probe_response(
    probe: Probe,
    status: int | None,
    response: dict[str, Any],
) -> tuple[bool, str]:
    if probe.expectation == "jsonrpc-error-or-local-reject":
        if status in {400, 403, 413, 415}:
            return True, "local-reject"
        if status != 200:
            return False, "expected local rejection or JSON-RPC error"
        if response_has_internal_error_leak(response):
            return False, "internal-error-leak"
        try:
            payload = json.loads(response.get("body_text") or "")
        except json.JSONDecodeError:
            return False, "invalid-json-rpc-response-body"
        if jsonrpc_response_is_error_only(payload):
            return True, "jsonrpc-error"
        return False, "jsonrpc-result-for-invalid-transaction-payload"

    if not probe.expected_statuses:
        return True, "status-unconstrained"
    if status in probe.expected_statuses:
        return True, "status"
    return False, "unexpected-status"


def build_probe_plan(
    target: str,
    include_external: bool,
    selected_clusters: set[str] | None = None,
    profile: dict[str, Any] | None = None,
) -> list[Probe]:
    allowed_origin = origin_for(target)
    evil_origin = "https://evil.example"
    allowed_referer = f"{allowed_origin}/swap"
    evil_referer = "https://evil.example/swap"
    valid_rpc = '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
    blocked_rpc = '{"jsonrpc":"2.0","id":2,"method":"getProgramAccounts","params":[]}'
    unknown_rpc = '{"jsonrpc":"2.0","id":3,"method":"requestAirdrop","params":[]}'
    wrong_method_type_rpc = '{"jsonrpc":"2.0","id":4,"method":123,"params":[]}'
    invalid_transaction_payload = "inferforge-not-a-valid-solana-transaction"
    duplicate_method_blocked_then_allowed_rpc = (
        '{"jsonrpc":"2.0","id":5,"method":"getProgramAccounts","method":"getHealth","params":[]}'
    )
    duplicate_method_allowed_then_blocked_rpc = (
        '{"jsonrpc":"2.0","id":6,"method":"getHealth","method":"getProgramAccounts","params":[]}'
    )
    batch_11 = json.dumps(
        [{"jsonrpc": "2.0", "id": i, "method": "getHealth"} for i in range(1, 12)]
    )
    mixed_blocked_batch = json.dumps(
        [
            {"jsonrpc": "2.0", "id": 7, "method": "getHealth"},
            {"jsonrpc": "2.0", "id": 8, "method": "getProgramAccounts", "params": []},
        ]
    )
    valid_wallet = DEFAULT_TEST_WALLET
    alternate_wallet = "11111111111111111111111111111111"
    health_path = probe_target_path(profile, "health", "path", "/health")
    quote_path = probe_target_path(profile, "quote", "path", "/api/quote")
    rpc_paths = rpc_probe_paths(profile)
    rpc_path = rpc_paths["path"]
    rpc_root_path = rpc_paths["root_path"]
    rpc_unknown_cluster_path = rpc_paths["unknown_cluster_path"]
    orca_paths = orca_probe_paths(profile)

    def quote_body(
        *,
        amount_in: Any = "1000000",
        sender: Any = valid_wallet,
        recipient: Any = valid_wallet,
        source_chain: Any = "Solana",
        source_address: Any = USDC_MINT,
        destination_chain: Any = "Solana",
        destination_address: Any = USDTEL_MINT,
        max_num_quotes: Any = 1,
        include_route: bool = True,
        include_source: bool = True,
        include_destination: bool = True,
        include_amount: bool = True,
        include_sender: bool = True,
        include_recipient: bool = True,
        include_max_num_quotes: bool = True,
        extra: dict[str, Any] | None = None,
    ) -> str:
        body: dict[str, Any] = {}
        if include_route:
            route: dict[str, Any] = {}
            if include_source:
                route["source"] = {"chain": source_chain, "address": source_address}
            if include_destination:
                route["destination"] = {
                    "chain": destination_chain,
                    "address": destination_address,
                }
            body["route"] = route
        if include_amount:
            body["amountIn"] = amount_in
        if include_sender:
            body["sender"] = sender
        if include_recipient:
            body["recipient"] = recipient
        if include_max_num_quotes:
            body["maxNumQuotes"] = max_num_quotes
        if extra:
            body.update(extra)
        return json.dumps(body)

    def quote_probe(
        probe_id: str,
        label: str,
        body: str,
        *,
        external: bool = False,
        policy_field: str | None = None,
        risk: str = "safe-local-validation",
    ) -> Probe:
        return Probe(
            probe_id,
            label,
            "POST",
            "/api/quote",
            body,
            allowed_origin,
            "application/json",
            (400,),
            category="quote",
            external=external,
            policy_field=policy_field,
            risk=risk,
        )

    def generic_route_probes() -> list[Probe]:
        generated: list[Probe] = []
        for route in generic_nextjs_route_targets(profile):
            cluster_id = route["id"]
            path = route["path"]
            methods = set(route.get("methods", []))
            prefix = safe_probe_id(cluster_id)
            generated.append(
                Probe(
                    f"nextjs_{prefix}_head",
                    f"Next.js route HEAD baseline {cluster_id}",
                    "HEAD",
                    path,
                    expected_statuses=(200, 204, 400, 403, 404, 405),
                    category=cluster_id,
                    policy_field="method",
                    risk="safe-generic-route-method-probe",
                    strategy_set="nextjs-api-routes",
                )
            )
            generated.append(
                Probe(
                    f"nextjs_{prefix}_options_preflight",
                    f"Next.js route OPTIONS preflight {cluster_id}",
                    "OPTIONS",
                    path,
                    origin=allowed_origin,
                    expected_statuses=(200, 204, 400, 403, 404, 405),
                    category=cluster_id,
                    policy_field="cors-preflight",
                    risk="safe-generic-route-preflight-probe",
                    strategy_set="nextjs-api-routes",
                )
            )
            if not methods:
                continue
            if "GET" in methods:
                generated.append(
                    Probe(
                        f"nextjs_{prefix}_get_availability",
                        f"Next.js route GET availability {cluster_id}",
                        "GET",
                        path,
                        expected_statuses=(200, 204, 304, 400, 403, 404),
                        category=cluster_id,
                        policy_field="availability",
                        risk="safe-generic-route-availability-probe",
                        strategy_set="nextjs-api-routes",
                    )
                )
            else:
                generated.append(
                    Probe(
                        f"nextjs_{prefix}_get_method_confusion",
                        f"Next.js route GET method confusion {cluster_id}",
                        "GET",
                        path,
                        expected_statuses=(400, 403, 404, 405),
                        category=cluster_id,
                        policy_field="method",
                        risk="safe-generic-route-method-probe",
                        strategy_set="nextjs-api-routes",
                    )
                )
        return generated

    probes = [
        Probe("health", "GET /health", "GET", "/health", expected_statuses=(200,), category="health"),
        Probe(
            "rpc_options_allowed",
            "RPC OPTIONS allowed Origin",
            "OPTIONS",
            "/api/rpc/solana/devnet",
            origin=allowed_origin,
            expected_statuses=(204,),
            category="solana-rpc-http",
        ),
        Probe(
            "rpc_options_disallowed",
            "RPC OPTIONS disallowed Origin",
            "OPTIONS",
            "/api/rpc/solana/devnet",
            origin=evil_origin,
            expected_statuses=(403,),
            category="solana-rpc-http",
        ),
        Probe(
            "rpc_root_options_allowed",
            "RPC root OPTIONS allowed Origin",
            "OPTIONS",
            "/api/rpc",
            origin=allowed_origin,
            expected_statuses=(204,),
            category="solana-rpc-http",
            policy_field="root-route-source",
        ),
        Probe(
            "rpc_root_options_disallowed",
            "RPC root OPTIONS disallowed Origin",
            "OPTIONS",
            "/api/rpc",
            origin=evil_origin,
            expected_statuses=(403,),
            category="solana-rpc-http",
            policy_field="root-route-source",
        ),
        Probe(
            "rpc_get_health",
            "RPC getHealth",
            "POST",
            "/api/rpc/solana/devnet",
            valid_rpc,
            allowed_origin,
            "application/json",
            (200,),
            category="solana-rpc-http",
        ),
        Probe(
            "rpc_no_origin_dev",
            "RPC no Origin in dev",
            "POST",
            "/api/rpc/solana/devnet",
            valid_rpc,
            None,
            "application/json",
            (200,),
            category="solana-rpc-http",
        ),
        Probe(
            "rpc_referer_allowed",
            "RPC Referer-only allowed source",
            "POST",
            "/api/rpc/solana/devnet",
            body=valid_rpc,
            referer=allowed_referer,
            content_type="application/json",
            expected_statuses=(200,),
            category="solana-rpc-http",
            policy_field="source",
        ),
        Probe(
            "rpc_referer_disallowed",
            "RPC Referer-only disallowed source",
            "POST",
            "/api/rpc/solana/devnet",
            body=valid_rpc,
            referer=evil_referer,
            content_type="application/json",
            expected_statuses=(403,),
            category="solana-rpc-http",
            policy_field="source",
        ),
        Probe(
            "rpc_disallowed_origin",
            "RPC POST disallowed Origin",
            "POST",
            "/api/rpc/solana/devnet",
            valid_rpc,
            evil_origin,
            "application/json",
            (403,),
            category="solana-rpc-http",
        ),
        Probe(
            "rpc_get_method_confusion",
            "RPC GET method confusion",
            "GET",
            "/api/rpc/solana/devnet",
            expected_statuses=(405,),
            category="solana-rpc-http",
            policy_field="method",
        ),
        Probe(
            "rpc_root_get_method_confusion",
            "RPC root GET method confusion",
            "GET",
            "/api/rpc",
            expected_statuses=(405,),
            category="solana-rpc-http",
            policy_field="root-route-method",
        ),
        Probe(
            "rpc_text_plain_valid_json",
            "RPC text/plain valid JSON",
            "POST",
            "/api/rpc/solana/devnet",
            valid_rpc,
            allowed_origin,
            "text/plain",
            (415,),
            category="solana-rpc-http",
            policy_field="content-type",
        ),
        Probe(
            "rpc_root_text_plain_valid_json",
            "RPC root text/plain valid JSON",
            "POST",
            "/api/rpc",
            valid_rpc,
            allowed_origin,
            "text/plain",
            (415,),
            category="solana-rpc-http",
            policy_field="root-route-content-type",
        ),
        Probe(
            "rpc_blocked_method",
            "RPC blocked method",
            "POST",
            "/api/rpc/solana/devnet",
            blocked_rpc,
            allowed_origin,
            "application/json",
            (403,),
            category="solana-rpc-http",
        ),
        Probe(
            "rpc_root_blocked_method",
            "RPC root blocked method",
            "POST",
            "/api/rpc",
            blocked_rpc,
            allowed_origin,
            "application/json",
            (403,),
            category="solana-rpc-http",
            policy_field="root-route-method",
        ),
        Probe(
            "rpc_method_wrong_type",
            "RPC method wrong type",
            "POST",
            "/api/rpc/solana/devnet",
            wrong_method_type_rpc,
            allowed_origin,
            "application/json",
            (400,),
            category="solana-rpc-http",
            policy_field="method",
        ),
        Probe(
            "rpc_duplicate_method_blocked_then_allowed",
            "RPC duplicate method blocked then allowed",
            "POST",
            "/api/rpc/solana/devnet",
            duplicate_method_blocked_then_allowed_rpc,
            allowed_origin,
            "application/json",
            (400,),
            category="solana-rpc-http",
            policy_field="json-duplicate-keys",
        ),
        Probe(
            "rpc_duplicate_method_allowed_then_blocked",
            "RPC duplicate method allowed then blocked",
            "POST",
            "/api/rpc/solana/devnet",
            duplicate_method_allowed_then_blocked_rpc,
            allowed_origin,
            "application/json",
            (400,),
            category="solana-rpc-http",
            policy_field="json-duplicate-keys",
        ),
        Probe(
            "rpc_allowlist_miss",
            "RPC allowlist miss",
            "POST",
            "/api/rpc/solana/devnet",
            unknown_rpc,
            allowed_origin,
            "application/json",
            (403,),
            category="solana-rpc-http",
        ),
        Probe(
            "rpc_malformed_json",
            "RPC malformed JSON",
            "POST",
            "/api/rpc/solana/devnet",
            "{bad json",
            allowed_origin,
            "application/json",
            (400,),
            category="solana-rpc-http",
        ),
        Probe(
            "rpc_empty_batch",
            "RPC empty batch",
            "POST",
            "/api/rpc/solana/devnet",
            "[]",
            allowed_origin,
            "application/json",
            (400,),
            category="solana-rpc-http",
        ),
        Probe(
            "rpc_mixed_batch_blocked_method",
            "RPC mixed batch blocked method",
            "POST",
            "/api/rpc/solana/devnet",
            mixed_blocked_batch,
            allowed_origin,
            "application/json",
            (403,),
            category="solana-rpc-http",
            policy_field="batch-method",
        ),
        Probe(
            "rpc_batch_over_limit",
            "RPC batch over limit",
            "POST",
            "/api/rpc/solana/devnet",
            batch_11,
            allowed_origin,
            "application/json",
            (413,),
            category="solana-rpc-http",
        ),
        Probe(
            "rpc_unknown_cluster",
            "RPC unknown cluster",
            "POST",
            "/api/rpc/solana/localnet",
            valid_rpc,
            allowed_origin,
            "application/json",
            (404,),
            category="solana-rpc-http",
        ),
        Probe(
            "rpc_simulate_transaction_invalid_payload",
            "RPC simulateTransaction invalid transaction payload",
            "POST",
            "/api/rpc/solana/devnet",
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 42,
                    "method": "simulateTransaction",
                    "params": [
                        invalid_transaction_payload,
                        {"encoding": "base64", "sigVerify": True},
                    ],
                }
            ),
            allowed_origin,
            "application/json",
            (200, 400, 403, 413, 415),
            category="solana-rpc-http",
            policy_field="transaction-method",
            risk="safe-invalid-transaction-rpc-probe",
            expectation="jsonrpc-error-or-local-reject",
        ),
        Probe(
            "rpc_send_transaction_invalid_payload",
            "RPC sendTransaction invalid transaction payload",
            "POST",
            "/api/rpc/solana/devnet",
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 43,
                    "method": "sendTransaction",
                    "params": [
                        invalid_transaction_payload,
                        {"encoding": "base64", "skipPreflight": False},
                    ],
                }
            ),
            allowed_origin,
            "application/json",
            (200, 400, 403, 413, 415),
            category="solana-rpc-http",
            policy_field="transaction-method",
            risk="safe-invalid-transaction-rpc-probe",
            expectation="jsonrpc-error-or-local-reject",
        ),
        Probe(
            "rpc_root_send_transaction_invalid_payload",
            "RPC root sendTransaction invalid transaction payload",
            "POST",
            "/api/rpc",
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 44,
                    "method": "sendTransaction",
                    "params": [
                        invalid_transaction_payload,
                        {"encoding": "base64", "skipPreflight": False},
                    ],
                }
            ),
            allowed_origin,
            "application/json",
            (200, 400, 403, 413, 415),
            category="solana-rpc-http",
            policy_field="root-route-transaction-method",
            risk="safe-invalid-transaction-rpc-probe",
            expectation="jsonrpc-error-or-local-reject",
        ),
        quote_probe("quote_invalid_body", "Quote invalid body", "{}", policy_field="body"),
        quote_probe(
            "quote_missing_route",
            "Quote missing route",
            quote_body(include_route=False),
            policy_field="route",
        ),
        quote_probe(
            "quote_missing_source",
            "Quote missing source route",
            quote_body(include_source=False),
            policy_field="route.source",
        ),
        quote_probe(
            "quote_missing_destination",
            "Quote missing destination route",
            quote_body(include_destination=False),
            policy_field="route.destination",
        ),
        quote_probe(
            "quote_missing_amount",
            "Quote missing amountIn",
            quote_body(include_amount=False),
            policy_field="amountIn",
        ),
        quote_probe(
            "quote_missing_sender",
            "Quote missing sender",
            quote_body(include_sender=False),
            policy_field="sender",
        ),
        Probe(
            "quote_malformed_json",
            "Quote malformed JSON",
            "POST",
            "/api/quote",
            "{bad json",
            allowed_origin,
            "application/json",
            (400,),
            category="quote",
            policy_field="json",
            risk="safe-local-validation",
        ),
        Probe(
            "quote_text_plain_invalid_json",
            "Quote text/plain invalid JSON",
            "POST",
            "/api/quote",
            "not-json",
            allowed_origin,
            "text/plain",
            (415,),
            category="quote",
            policy_field="json",
            risk="safe-local-validation",
        ),
        quote_probe(
            "quote_wrong_amount_type",
            "Quote wrong amountIn type",
            quote_body(amount_in=1),
            policy_field="amountIn",
        ),
        quote_probe(
            "quote_wrong_sender_type",
            "Quote wrong sender type",
            quote_body(sender=1),
            policy_field="sender",
        ),
        quote_probe(
            "quote_route_wrong_type",
            "Quote wrong route type",
            json.dumps(
                {
                    "route": "not-an-object",
                    "amountIn": "1000000",
                    "sender": valid_wallet,
                    "recipient": valid_wallet,
                    "maxNumQuotes": 1,
                }
            ),
            policy_field="route",
        ),
        Probe(
            "orca_invalid_address",
            "Orca invalid address",
            "GET",
            "/api/orca/pools/not-an-address",
            expected_statuses=(400,),
            category="orca-pools",
            policy_field="address-shape",
        ),
        Probe(
            "orca_invalid_base58_character",
            "Orca invalid base58 character",
            "GET",
            "/api/orca/pools/0OIlnotbase58",
            expected_statuses=(400,),
            category="orca-pools",
            policy_field="address-base58",
        ),
        Probe(
            "orca_address_too_short",
            "Orca address too short",
            "GET",
            "/api/orca/pools/1111111111111111111111111111111",
            expected_statuses=(400,),
            category="orca-pools",
            policy_field="address-length",
        ),
        Probe(
            "orca_address_too_long",
            "Orca address too long",
            "GET",
            "/api/orca/pools/111111111111111111111111111111111111111111111",
            expected_statuses=(400,),
            category="orca-pools",
            policy_field="address-length",
        ),
        Probe(
            "orca_encoded_path_traversal",
            "Orca encoded path traversal",
            "GET",
            "/api/orca/pools/%2e%2e%2fhealth",
            expected_statuses=(400, 404),
            category="orca-pools",
            policy_field="path-traversal",
        ),
        Probe(
            "orca_extra_path_segment",
            "Orca extra path segment",
            "GET",
            "/api/orca/pools/not-an-address/extra",
            expected_statuses=(404,),
            category="orca-pools",
            policy_field="path-segment",
        ),
        Probe(
            "orca_query_injection_invalid_address",
            "Orca query injection invalid address",
            "GET",
            "/api/orca/pools/not-an-address?url=https://evil.example",
            expected_statuses=(400,),
            category="orca-pools",
            policy_field="query-ignored",
        ),
        Probe(
            "orca_head_method_confusion",
            "Orca HEAD method confusion",
            "HEAD",
            "/api/orca/pools/not-an-address",
            expected_statuses=(400, 405),
            category="orca-pools",
            policy_field="method",
        ),
        Probe(
            "orca_method_confusion",
            "Orca method confusion",
            "POST",
            "/api/orca/pools/not-an-address",
            "{}",
            allowed_origin,
            "application/json",
            (405,),
            category="orca-pools",
        ),
    ]
    probes.extend(generic_route_probes())

    if include_external:
        external_quote_risk = "bounded-m0-validation-probe"
        probes.extend(
            [
                quote_probe(
                    "quote_shape_valid_invalid_business_values",
                    "Quote shape-valid invalid business values",
                    quote_body(
                        source_chain="NotSolana",
                        source_address="not-a-mint",
                        destination_chain="AlsoNotSolana",
                        destination_address="not-a-destination",
                        amount_in="1",
                        sender="not-a-wallet",
                        recipient="also-not-a-wallet",
                        max_num_quotes=999,
                    ),
                    external=True,
                    policy_field="combined",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_invalid_source_chain",
                    "Quote invalid source chain",
                    quote_body(source_chain="Ethereum"),
                    external=True,
                    policy_field="route.source.chain",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_invalid_destination_chain",
                    "Quote invalid destination chain",
                    quote_body(destination_chain="Ethereum"),
                    external=True,
                    policy_field="route.destination.chain",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_invalid_source_mint",
                    "Quote invalid source mint",
                    quote_body(source_address="not-a-mint"),
                    external=True,
                    policy_field="route.source.address",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_invalid_destination_mint",
                    "Quote invalid destination mint",
                    quote_body(destination_address="not-a-mint"),
                    external=True,
                    policy_field="route.destination.address",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_source_mint_wrong_type",
                    "Quote source mint wrong type",
                    quote_body(source_address=123),
                    external=True,
                    policy_field="route.source.address",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_destination_mint_wrong_type",
                    "Quote destination mint wrong type",
                    quote_body(destination_address=123),
                    external=True,
                    policy_field="route.destination.address",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_sender_invalid_public_key",
                    "Quote sender invalid public key",
                    quote_body(sender="not-a-wallet"),
                    external=True,
                    policy_field="sender",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_recipient_invalid_public_key",
                    "Quote recipient invalid public key",
                    quote_body(recipient="not-a-wallet"),
                    external=True,
                    policy_field="recipient",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_missing_recipient",
                    "Quote missing recipient",
                    quote_body(include_recipient=False),
                    external=True,
                    policy_field="recipient",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_sender_recipient_mismatch",
                    "Quote sender recipient mismatch",
                    quote_body(recipient=alternate_wallet),
                    external=True,
                    policy_field="recipient",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_amount_zero",
                    "Quote amountIn zero",
                    quote_body(amount_in="0"),
                    external=True,
                    policy_field="amountIn",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_amount_negative",
                    "Quote amountIn negative",
                    quote_body(amount_in="-1"),
                    external=True,
                    policy_field="amountIn",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_amount_decimal",
                    "Quote amountIn decimal",
                    quote_body(amount_in="1.5"),
                    external=True,
                    policy_field="amountIn",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_amount_scientific",
                    "Quote amountIn scientific notation",
                    quote_body(amount_in="1e9"),
                    external=True,
                    policy_field="amountIn",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_amount_huge",
                    "Quote amountIn huge integer",
                    quote_body(amount_in="9" * 80),
                    external=True,
                    policy_field="amountIn",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_amount_non_numeric",
                    "Quote amountIn non-numeric",
                    quote_body(amount_in="not-a-number"),
                    external=True,
                    policy_field="amountIn",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_max_num_quotes_wrong_type",
                    "Quote maxNumQuotes wrong type",
                    quote_body(max_num_quotes="1"),
                    external=True,
                    policy_field="maxNumQuotes",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_max_num_quotes_zero",
                    "Quote maxNumQuotes zero",
                    quote_body(max_num_quotes=0),
                    external=True,
                    policy_field="maxNumQuotes",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_max_num_quotes_high",
                    "Quote maxNumQuotes high",
                    quote_body(max_num_quotes=999),
                    external=True,
                    policy_field="maxNumQuotes",
                    risk=external_quote_risk,
                ),
                quote_probe(
                    "quote_unknown_extra_fields",
                    "Quote unknown extra fields",
                    quote_body(extra={"unexpectedField": "inferforge", "debug": True}),
                    external=True,
                    policy_field="unknown-fields",
                    risk=external_quote_risk,
                ),
            ]
        )

    path_rewrites = {
        "/health": health_path,
        "/api/quote": quote_path,
        "/api/rpc/solana/devnet": rpc_path,
        "/api/rpc": rpc_root_path,
        "/api/rpc/solana/localnet": rpc_unknown_cluster_path,
        "/api/orca/pools/not-an-address": orca_paths["invalid_address_path"],
        "/api/orca/pools/0OIlnotbase58": orca_paths["invalid_base58_path"],
        "/api/orca/pools/1111111111111111111111111111111": orca_paths["too_short_path"],
        "/api/orca/pools/111111111111111111111111111111111111111111111": orca_paths["too_long_path"],
        "/api/orca/pools/%2e%2e%2fhealth": orca_paths["encoded_traversal_path"],
        "/api/orca/pools/not-an-address/extra": orca_paths["extra_segment_path"],
        "/api/orca/pools/not-an-address?url=https://evil.example": orca_paths["query_injection_path"],
    }
    probes = [replace(probe, path=path_rewrites.get(probe.path, probe.path)) for probe in probes]

    filtered = [
        probe
        for probe in probes
        if strategy_set_enabled(profile, strategy_set_for_probe(probe))
    ]

    if selected_clusters is None:
        return filtered

    return [probe for probe in filtered if probe.category in selected_clusters]


def build_warmup_probes(
    target: str,
    profile: dict[str, Any] | None = None,
    selected_clusters: set[str] | None = None,
) -> list[Probe]:
    allowed_origin = origin_for(target)
    evil_referer = "https://evil.example/swap"
    valid_rpc = '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
    health_path = probe_target_path(profile, "health", "path", "/health")
    quote_path = probe_target_path(profile, "quote", "path", "/api/quote")
    rpc_path = rpc_probe_paths(profile)["path"]
    orca_paths = orca_probe_paths(profile)
    probes = [
        Probe("warmup_health", "Warm up /health", "GET", health_path, expected_statuses=(200,), category="health"),
        Probe(
            "warmup_quote_invalid_body",
            "Warm up quote validation route",
            "POST",
            quote_path,
            "{}",
            allowed_origin,
            "application/json",
            (400,),
            category="quote",
            risk="warmup-local-route",
        ),
        Probe(
            "warmup_rpc_get_health",
            "Warm up RPC route module",
            "POST",
            rpc_path,
            valid_rpc,
            allowed_origin,
            "application/json",
            (200,),
            category="solana-rpc-http",
            risk="warmup-local-route",
        ),
        Probe(
            "warmup_rpc_referer_disallowed",
            "Warm up RPC referer policy",
            "POST",
            rpc_path,
            valid_rpc,
            referer=evil_referer,
            content_type="application/json",
            expected_statuses=(403,),
            category="solana-rpc-http",
            policy_field="source",
            risk="warmup-local-route",
        ),
        Probe(
            "warmup_orca_invalid_address",
            "Warm up Orca route module",
            "GET",
            orca_paths["invalid_address_path"],
            expected_statuses=(400,),
            category="orca-pools",
            risk="warmup-local-route",
        ),
        Probe(
            "warmup_orca_extra_path_segment",
            "Warm up Orca not-found route",
            "GET",
            orca_paths["extra_segment_path"],
            expected_statuses=(404,),
            category="orca-pools",
            risk="warmup-local-route",
        ),
    ]
    probes = [
        probe
        for probe in probes
        if strategy_set_enabled(profile, strategy_set_for_probe(probe))
    ]
    if selected_clusters is not None:
        probes = [probe for probe in probes if probe.category in selected_clusters]
    return probes


def run_http_probes(
    target: str,
    probes: list[Probe],
    *,
    phase: str = "probe",
    timeout: int = 20,
    max_attempts: int = 1,
) -> list[dict[str, Any]]:
    results = []
    for probe in probes:
        request_headers = build_probe_headers(probe)
        raw_request_body = (probe.body or "").encode("utf-8")
        request_body_truncated = bool(probe.body is not None and len(probe.body) > 500)
        response, attempts, retry_reason = run_probe_request(
            target,
            probe,
            timeout=timeout,
            max_attempts=max_attempts,
        )
        status = response["status"]
        expected, expectation_result = evaluate_probe_response(probe, status, response)
        result = {
            "ts": utc_now(),
            "phase": phase,
            "probe_id": probe.id,
            "label": probe.label,
            "target": target,
            "method": probe.method,
            "path": probe.path,
            "origin": probe.origin,
            "referer": probe.referer,
            "request": {
                "method": probe.method,
                "path": probe.path,
                "headers": redact_headers(request_headers),
                "body_sha256": hashlib.sha256(raw_request_body).hexdigest() if probe.body is not None else None,
                "body_length": len(raw_request_body),
                "body_sample": redact_text(probe.body, max_chars=500),
                "body_truncated": request_body_truncated,
            },
            "category": probe.category,
            "external": probe.external,
            "policy_field": probe.policy_field,
            "risk": probe.risk,
            "expectation": probe.expectation,
            "expectation_result": expectation_result,
            "expected_statuses": list(probe.expected_statuses),
            "status": status,
            "expected": expected,
            "duration_ms": response["duration_ms"],
            "error": response["error"],
            "body_sample": response["body_sample"],
            "body_text": response["body_text"],
            "body_sha256": response["body_sha256"],
            "body_truncated": response["body_truncated"],
            "body_length": response["body_length"],
            "interesting": (not expected) or is_interesting(probe, status, response["body_sample"]),
            "attempt_count": len(attempts),
        }
        if len(attempts) > 1:
            result["attempts"] = attempts
            result["retry_reason"] = retry_reason
            result["first_attempt"] = attempts[0]
        results.append(result)
    return results


def run_audit_warmup(
    target: str,
    artifact_dir: Path,
    profile: dict[str, Any] | None = None,
    selected_clusters: set[str] | None = None,
) -> dict[str, Any]:
    warmup_results = run_http_probes(
        target,
        build_warmup_probes(target, profile, selected_clusters),
        phase="warmup",
        timeout=35,
        max_attempts=3,
    )
    payload = {
        "generated_at": utc_now(),
        "target": target,
        "note": "Local route warm-up before audit probes. Results are not counted as findings.",
        "selected_clusters": sorted(selected_clusters) if selected_clusters is not None else None,
        "ready": all(row["expected"] for row in warmup_results),
        "results": warmup_results,
    }
    write_json(artifact_dir / "warmup-results.json", payload)
    return payload


def run_ws_probes(
    target: str,
    node: str,
    source_root: Path | None = None,
    profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    source_root = source_root or DEFAULT_SOURCE_ROOT
    ws_profile = websocket_observation_config(profile)
    if ws_profile is None:
        return [
            {
                "ts": utc_now(),
                "probe_id": "ws_profile_disabled",
                "label": "WebSocket probes disabled by profile",
                "target": target_to_ws(target),
                "method": "WS",
                "path": None,
                "category": "solana-rpc-ws",
                "external": False,
                "policy_field": "profile",
                "risk": "profile-disabled",
                "expected_statuses": [],
                "status": None,
                "expected": True,
                "duration_ms": None,
                "error": None,
                "body_sample": "",
                "body_text": "",
                "body_sha256": None,
                "body_truncated": False,
                "body_length": 0,
                "interesting": False,
                "skipped": True,
            }
        ]
    ws_path = str(ws_profile.get("path") or "/api/rpc/solana/devnet")
    ws_cluster = str(ws_profile.get("cluster") or "solana-rpc-ws")
    subscribe_method = str(ws_profile.get("subscribe_method") or "slotSubscribe")
    node_path = Path(node)
    if not node_path.exists():
        fallback = command_result(["node", "-v"])
        if not fallback["ok"]:
            return [
                {
                    "ts": utc_now(),
                    "probe_id": "ws_runtime_unavailable",
                    "label": "WebSocket runtime unavailable",
                    "status": None,
                    "expected": False,
                    "error": f"Node not found at {node}",
                    "body_sample": "",
                    "interesting": True,
                }
            ]
        node = "node"

    script_root = source_root if source_root.is_dir() else DEFAULT_SOURCE_ROOT
    ws_base = target_to_ws(target)
    allowed_origin = origin_for(target)
    script = f"""
import {{ WebSocket }} from 'ws'

async function one(name, origin, payload, options = {{}}) {{
  return new Promise((resolve) => {{
    const ws = new WebSocket('{ws_base}{ws_path}', {{
      headers: {{ Origin: origin }},
      perMessageDeflate: false,
    }})
    const timeout = setTimeout(() => {{
      try {{ ws.close() }} catch {{}}
      resolve({{ name, status: null, error: 'timeout', body_sample: '' }})
    }}, 10000)
    ws.on('open', () => {{
      if (options.binary) {{
        ws.send(Buffer.from(payload))
      }} else if (options.raw) {{
        ws.send(payload)
      }} else if (payload !== null && payload !== undefined) {{
        ws.send(JSON.stringify(payload))
      }}
    }})
    ws.on('message', (data) => {{
      console.log(`${{name}} message ${{data.toString().slice(0, 180)}}`)
    }})
    ws.on('close', (code, reason) => {{
      clearTimeout(timeout)
      resolve({{ name, status: code, error: null, body_sample: reason.toString() }})
    }})
    ws.on('error', (error) => {{
      clearTimeout(timeout)
      resolve({{ name, status: error.message.includes('403') ? 403 : null, error: error.message, body_sample: '' }})
    }})
  }})
}}

const results = []
const overLimitBatch = Array.from({{ length: 11 }}, (_, index) => ({{
  jsonrpc: '2.0',
  id: index + 20,
  method: '{subscribe_method}',
}}))
results.push(await one('ws_blocked_method', '{allowed_origin}', {{ jsonrpc: '2.0', id: 1, method: 'getProgramAccounts', params: [] }}))
results.push(await one('ws_malformed_json', '{allowed_origin}', '{{"jsonrpc":"2.0","id":2,"method":', {{ raw: true }}))
results.push(await one('ws_binary_message', '{allowed_origin}', JSON.stringify({{ jsonrpc: '2.0', id: 3, method: '{subscribe_method}' }}), {{ binary: true }}))
results.push(await one('ws_method_wrong_type', '{allowed_origin}', {{ jsonrpc: '2.0', id: 4, method: 123, params: [] }}))
results.push(await one('ws_duplicate_method_blocked_then_allowed', '{allowed_origin}', '{{"jsonrpc":"2.0","id":5,"method":"getProgramAccounts","method":"{subscribe_method}"}}', {{ raw: true }}))
results.push(await one('ws_duplicate_method_allowed_then_blocked', '{allowed_origin}', '{{"jsonrpc":"2.0","id":6,"method":"{subscribe_method}","method":"getProgramAccounts"}}', {{ raw: true }}))
results.push(await one('ws_empty_batch', '{allowed_origin}', []))
results.push(await one('ws_batch_over_limit', '{allowed_origin}', overLimitBatch))
results.push(await one('ws_mixed_batch_blocked_method', '{allowed_origin}', [
  {{ jsonrpc: '2.0', id: 31, method: '{subscribe_method}' }},
  {{ jsonrpc: '2.0', id: 32, method: 'getProgramAccounts', params: [] }},
]))
results.push(await one('ws_disallowed_origin', 'https://evil.example', null))
console.log(JSON.stringify(results))
"""

    proc = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=str(script_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=15,
        check=False,
    )

    output = proc.stdout.strip().splitlines()
    raw_json = output[-1] if output else "[]"
    try:
        raw_results = json.loads(raw_json)
    except json.JSONDecodeError:
        raw_results = [{"name": "ws_probe_parse_error", "status": None, "error": proc.stdout, "body_sample": ""}]

    results = []
    policy_fields = {
        "ws_blocked_method": "method",
        "ws_malformed_json": "json",
        "ws_binary_message": "frame-type",
        "ws_method_wrong_type": "method",
        "ws_duplicate_method_blocked_then_allowed": "json-duplicate-keys",
        "ws_duplicate_method_allowed_then_blocked": "json-duplicate-keys",
        "ws_empty_batch": "batch",
        "ws_batch_over_limit": "batch",
        "ws_mixed_batch_blocked_method": "batch-method",
        "ws_disallowed_origin": "origin",
    }
    for item in raw_results:
        probe_id = item["name"]
        status = item.get("status")
        expected_statuses = [403] if probe_id == "ws_disallowed_origin" else [1008, 1006]
        expected = status in expected_statuses
        expectation_result = "status"
        review_note = None
        if probe_id != "ws_disallowed_origin" and status == 1006:
            expectation_result = "policy-close-without-close-frame"
            review_note = "The server closed the WebSocket without a policy close frame; the message was still blocked."
        results.append(
            {
                "ts": utc_now(),
                "probe_id": probe_id,
                "label": probe_id.replace("_", " "),
                "target": ws_base,
                "method": "WS",
                "path": ws_path,
                "origin": "https://evil.example" if probe_id == "ws_disallowed_origin" else allowed_origin,
                "category": ws_cluster,
                "external": False,
                "policy_field": policy_fields.get(probe_id, "message"),
                "risk": "safe-websocket-validation",
                "expected_statuses": expected_statuses,
                "status": status,
                "expected": expected,
                "expectation_result": expectation_result,
                "duration_ms": None,
                "error": item.get("error"),
                "body_sample": item.get("body_sample", ""),
                "body_text": item.get("body_sample", ""),
                "body_sha256": None,
                "body_truncated": False,
                "body_length": len(item.get("body_sample", "")),
                "interesting": (not expected) or review_note is not None,
                "review_note": review_note,
            }
        )
    return results


def run_ws_resource_probes(
    target: str,
    node: str,
    source_root: Path | None = None,
    profile: dict[str, Any] | None = None,
    *,
    connection_attempts: int = 11,
) -> list[dict[str, Any]]:
    connection_attempts = max(2, min(connection_attempts, 12))
    source_root = source_root or DEFAULT_SOURCE_ROOT
    ws_profile = websocket_observation_config(profile)
    if ws_profile is None:
        return [
            {
                "ts": utc_now(),
                "probe_id": "ws_resource_profile_disabled",
                "label": "WebSocket resource probes disabled by profile",
                "target": target_to_ws(target),
                "method": "WS",
                "path": None,
                "category": "solana-rpc-ws",
                "external": False,
                "policy_field": "profile",
                "risk": "profile-disabled",
                "expected_statuses": [],
                "status": None,
                "expected": True,
                "duration_ms": None,
                "error": None,
                "body_sample": "",
                "body_text": "",
                "body_sha256": None,
                "body_truncated": False,
                "body_length": 0,
                "interesting": False,
                "skipped": True,
            }
        ]
    ws_path = str(ws_profile.get("path") or "/api/rpc/solana/devnet")
    ws_cluster = str(ws_profile.get("cluster") or "solana-rpc-ws")
    node_path = Path(node)
    if not node_path.exists():
        fallback = command_result(["node", "-v"])
        if not fallback["ok"]:
            return [
                {
                    "ts": utc_now(),
                    "probe_id": "ws_resource_runtime_unavailable",
                    "label": "WebSocket resource runtime unavailable",
                    "target": target_to_ws(target),
                    "method": "WS",
                    "path": ws_path,
                    "category": ws_cluster,
                    "external": False,
                    "policy_field": "resource-runtime",
                    "risk": "approval-gated-low-volume-websocket-resource-probe",
                    "expected_statuses": [429],
                    "status": None,
                    "expected": False,
                    "duration_ms": None,
                    "error": f"Node not found at {node}",
                    "body_sample": "",
                    "body_text": "",
                    "body_sha256": None,
                    "body_truncated": False,
                    "body_length": 0,
                    "interesting": True,
                }
            ]
        node = "node"

    script_root = source_root if source_root.is_dir() else DEFAULT_SOURCE_ROOT
    ws_base = target_to_ws(target)
    allowed_origin = origin_for(target)
    script = f"""
import {{ WebSocket }} from 'ws'

const sockets = []

function one(index) {{
  return new Promise((resolve) => {{
    const ws = new WebSocket('{ws_base}{ws_path}', {{
      headers: {{ Origin: '{allowed_origin}' }},
      perMessageDeflate: false,
    }})
    sockets.push(ws)
    const timeout = setTimeout(() => {{
      resolve({{ index, state: 'timeout', status: null, error: 'timeout' }})
    }}, 5000)
    ws.on('open', () => {{
      clearTimeout(timeout)
      resolve({{ index, state: 'open', status: 101, error: null }})
    }})
    ws.on('error', (error) => {{
      clearTimeout(timeout)
      const match = /Unexpected server response: (\\d+)/.exec(error.message)
      resolve({{
        index,
        state: 'error',
        status: match ? Number(match[1]) : null,
        error: error.message,
      }})
    }})
  }})
}}

const started = Date.now()
const results = await Promise.all(Array.from({{ length: {connection_attempts} }}, (_, index) => one(index)))
for (const ws of sockets) {{
  try {{ ws.close(1000, 'InferForge resource probe complete') }} catch {{}}
}}
await new Promise((resolve) => setTimeout(resolve, 250))
console.log(JSON.stringify({{
  duration_ms: Date.now() - started,
  connection_attempts: {connection_attempts},
  results,
}}))
"""

    proc = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=str(script_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=10,
        check=False,
    )

    output = proc.stdout.strip().splitlines()
    raw_json = output[-1] if output else "{}"
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        payload = {
            "duration_ms": None,
            "connection_attempts": connection_attempts,
            "results": [],
            "parse_error": proc.stdout[-1000:],
        }

    attempts = payload.get("results", [])
    statuses = [item.get("status") for item in attempts if isinstance(item, dict)]
    rejected_429 = sum(1 for status in statuses if status == 429)
    opened = sum(1 for status in statuses if status == 101)
    timed_out = sum(1 for item in attempts if isinstance(item, dict) and item.get("state") == "timeout")
    status = 429 if rejected_429 > 0 else (101 if opened > 0 else None)
    expected_statuses = [429]
    expected = status in expected_statuses and timed_out == 0
    body = {
        "connection_attempts": payload.get("connection_attempts", connection_attempts),
        "opened": opened,
        "rejected_429": rejected_429,
        "timed_out": timed_out,
        "attempts": attempts,
    }
    if payload.get("parse_error"):
        body["parse_error"] = payload["parse_error"]
    body_text = json.dumps(body, sort_keys=False)

    return [
        {
            "ts": utc_now(),
            "probe_id": "ws_resource_connection_limit",
            "label": "WS connection limit low-volume probe",
            "target": ws_base,
            "method": "WS",
            "path": ws_path,
            "origin": allowed_origin,
            "category": ws_cluster,
            "external": False,
            "policy_field": "connection-limit",
            "risk": "approval-gated-low-volume-websocket-resource-probe",
            "expected_statuses": expected_statuses,
            "status": status,
            "expected": expected,
            "duration_ms": payload.get("duration_ms"),
            "error": None if expected else payload.get("parse_error"),
            "body_sample": body_text[:MAX_BODY_SAMPLE_CHARS],
            "body_text": body_text,
            "body_sha256": hashlib.sha256(body_text.encode("utf-8")).hexdigest(),
            "body_truncated": False,
            "body_length": len(body_text),
            "interesting": not expected,
        }
    ]


def is_interesting(probe: Probe, status: int | None, body: str) -> bool:
    if probe.id in {"quote_malformed_json", "quote_text_plain_invalid_json"} and status == 500:
        return True
    if str(probe.risk).startswith("safe-generic-route-") and probe.policy_field and status not in set(probe.expected_statuses):
        return True
    if probe.category == "quote" and probe.external and probe.policy_field and status not in {400, None}:
        return True
    if probe.category == "quote" and probe.policy_field and not probe.external and status not in set(probe.expected_statuses):
        return True
    if probe.category == "solana-rpc-http" and probe.policy_field and status not in set(probe.expected_statuses):
        return True
    if probe.category == "orca-pools" and probe.policy_field and status not in set(probe.expected_statuses):
        return True
    return False


def line_of(path: Path, pattern: str, base: Path) -> str:
    try:
        for index, line in enumerate(read_text(path).splitlines(), start=1):
            if pattern in line:
                return f"{path.relative_to(base)}:{index}"
    except FileNotFoundError:
        return f"{path.relative_to(base)}:missing"
    return f"{path.relative_to(base)}:not-found"


def line_of_any(path: Path, patterns: list[str], base: Path) -> str:
    for pattern in patterns:
        if not pattern:
            continue
        location = line_of(path, pattern, base)
        if not location.endswith(":not-found") and not location.endswith(":missing"):
            return location
    return line_of(path, patterns[0] if patterns else "", base)


def entrypoint_source_ref(source_root: Path, entrypoint: dict[str, Any]) -> str:
    if entrypoint.get("repo_file"):
        return str(entrypoint["repo_file"])
    return source_ref_for_artifact(source_root, str(entrypoint.get("file") or ""))


def entrypoint_line_refs(source_root: Path, entrypoint: dict[str, Any], method: str) -> dict[str, str]:
    source_file = source_ref_to_path(source_root, str(entrypoint.get("file") or ""))
    if entrypoint.get("line_patterns"):
        refs: dict[str, str] = {}
        for key, pattern_spec in (entrypoint.get("line_patterns") or {}).items():
            patterns = pattern_spec if isinstance(pattern_spec, list) else [str(pattern_spec)]
            refs[str(key)] = line_of_any(source_file, [str(pattern) for pattern in patterns], source_root)
        return refs

    if entrypoint.get("kind") == "rewrite-proxy":
        rewrite = entrypoint.get("rewrite") or {}
        refs = {
            "rewrite_source": line_of(source_file, str(rewrite.get("source") or entrypoint.get("path") or ""), source_root),
            "rewrite_destination": line_of_any(
                source_file,
                [
                    str(rewrite.get("destination_expression") or ""),
                    str(rewrite.get("destination_template") or ""),
                    str(rewrite.get("destination_resolved") or ""),
                ],
                source_root,
            ),
        }
        for variable, env_doc in (rewrite.get("env_defaults_used") or {}).items():
            refs[f"env_default:{variable}"] = line_of(source_file, str(env_doc.get("env") or variable), source_root)
        if next_config_conditions_present(rewrite.get("conditions")):
            refs["has_conditions"] = line_of(source_file, "has", source_root)
            refs["missing_conditions"] = line_of(source_file, "missing", source_root)
        return refs

    normalized_method = method.upper()
    refs: dict[str, str] = {}
    if normalized_method in HTTP_METHODS:
        refs["handler"] = line_of_any(
            source_file,
            [
                f"export async function {normalized_method}",
                f"export function {normalized_method}",
                f"export const {normalized_method}",
                f"function {normalized_method}",
            ],
            source_root,
        )
    return refs


def request_contexts_for_condition_evaluation(request_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not request_context:
        return []
    contexts = request_context.get("contexts")
    if isinstance(contexts, list):
        return [item for item in contexts if isinstance(item, dict)]
    return [request_context]


def observed_condition_values(condition: dict[str, Any], request_context: dict[str, Any]) -> dict[str, Any]:
    condition_type = str(condition.get("type") or "").lower()
    key = str(condition.get("key") or "")
    if condition_type == "header":
        if not key:
            return {"status": "unknown", "reason": "header-condition-missing-key", "values": []}
        headers = request_context.get("headers") or {}
        normalized_key = key.lower()
        if normalized_key not in headers:
            return {"status": "absent", "values": []}
        return {"status": "present", "values": [str(headers[normalized_key])]}
    if condition_type == "query":
        if not key:
            return {"status": "unknown", "reason": "query-condition-missing-key", "values": []}
        query = request_context.get("query") or {}
        if key not in query:
            return {"status": "absent", "values": []}
        return {"status": "present", "values": [str(value) for value in query.get(key, [])]}
    if condition_type == "cookie":
        if not key:
            return {"status": "unknown", "reason": "cookie-condition-missing-key", "values": []}
        cookies = request_context.get("cookies") or {}
        if key not in cookies:
            return {"status": "absent", "values": []}
        return {"status": "present", "values": [str(cookies[key])]}
    if condition_type == "host":
        host = str(request_context.get("host") or "")
        if not host:
            return {"status": "unknown", "reason": "request-host-unavailable", "values": []}
        return {"status": "present", "values": [host]}
    return {"status": "unknown", "reason": f"unsupported-condition-type:{condition_type or 'missing'}", "values": []}


def next_config_condition_value_status(expected_value: str, observed_values: list[str]) -> str:
    if not expected_value:
        return "satisfied" if observed_values else "not-satisfied"
    if not observed_values:
        return "not-satisfied"
    if any(value == REDACTED_VALUE for value in observed_values):
        return "unknown"
    if any(value == expected_value for value in observed_values):
        return "satisfied"
    try:
        pattern = re.compile(expected_value)
    except re.error:
        return "unknown"
    return "satisfied" if any(pattern.fullmatch(value) for value in observed_values) else "not-satisfied"


def evaluate_next_config_condition(scope: str, condition: dict[str, Any], request_context: dict[str, Any]) -> dict[str, Any]:
    observed = observed_condition_values(condition, request_context)
    observed_status = str(observed.get("status") or "unknown")
    observed_values = [str(value) for value in observed.get("values", [])]
    expected_value = str(condition.get("value") or "")
    result = {
        "scope": scope,
        "type": condition.get("type"),
        "key": condition.get("key"),
        "value": expected_value,
        "observed": observed_status,
        "observed_values": observed_values,
    }
    if observed.get("reason"):
        result["reason"] = observed.get("reason")

    if observed_status == "unknown":
        result["status"] = "unknown"
        return result

    has_match_status = next_config_condition_value_status(expected_value, observed_values)
    if scope == "has":
        result["status"] = has_match_status
        return result

    if scope == "missing":
        if has_match_status == "unknown":
            result["status"] = "unknown"
        elif has_match_status == "satisfied":
            result["status"] = "not-satisfied"
        else:
            result["status"] = "satisfied"
        return result

    result["status"] = "unknown"
    result["reason"] = f"unsupported-condition-scope:{scope}"
    return result


def evaluate_next_config_conditions_for_context(
    conditions: dict[str, list[dict[str, Any]]] | None,
    request_context: dict[str, Any],
) -> dict[str, Any]:
    results = []
    for scope in ["has", "missing"]:
        for condition in (conditions or {}).get(scope, []) or []:
            results.append(evaluate_next_config_condition(scope, condition, request_context))
    if not results:
        return {"status": "no-condition", "results": []}
    statuses = {str(item.get("status")) for item in results}
    if "not-satisfied" in statuses:
        status = "condition-not-satisfied"
    elif "unknown" in statuses:
        status = "condition-unknown"
    else:
        status = "condition-satisfied"
    return {
        "status": status,
        "results": results,
        "request_context_source": request_context.get("observed_sources", []),
    }


def evaluate_next_config_conditions(
    conditions: dict[str, list[dict[str, Any]]] | None,
    request_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not next_config_conditions_present(conditions):
        return {"status": "no-condition", "results": [], "evaluated_context_count": 0}
    contexts = request_contexts_for_condition_evaluation(request_context)
    if not contexts:
        return {
            "status": "condition-unknown",
            "reason": "request-context-unavailable",
            "results": [],
            "evaluated_context_count": 0,
        }

    context_evaluations = [
        evaluate_next_config_conditions_for_context(conditions, context)
        for context in contexts
    ]
    counts: dict[str, int] = {}
    for evaluation in context_evaluations:
        status = str(evaluation.get("status") or "condition-unknown")
        counts[status] = counts.get(status, 0) + 1

    selected = None
    for preferred_status in ["condition-satisfied", "condition-unknown", "condition-not-satisfied"]:
        selected = next(
            (item for item in context_evaluations if item.get("status") == preferred_status),
            None,
        )
        if selected is not None:
            break
    selected = selected or context_evaluations[0]
    if counts.get("condition-satisfied"):
        status = "condition-satisfied"
    elif counts.get("condition-unknown"):
        status = "condition-unknown"
    else:
        status = "condition-not-satisfied"

    return {
        "status": status,
        "results": selected.get("results", []),
        "evaluated_context_count": len(context_evaluations),
        "context_status_counts": counts,
        "selected_context_source": selected.get("request_context_source", []),
    }


def rewrite_condition_evaluation(entrypoint: dict[str, Any], request_context: dict[str, Any] | None) -> dict[str, Any] | None:
    rewrite = entrypoint.get("rewrite") or {}
    if not rewrite.get("conditional"):
        return None
    return evaluate_next_config_conditions(rewrite.get("conditions"), request_context)


def entrypoint_applicability(entrypoint: dict[str, Any], condition_evaluation: dict[str, Any] | None) -> str:
    if not condition_evaluation:
        return "path-and-method-match"
    status = condition_evaluation.get("status")
    if status == "condition-satisfied":
        return "path-match-condition-satisfied"
    if status == "condition-not-satisfied":
        return "path-match-condition-not-satisfied"
    return "path-match-condition-unknown"


def runtime_variant_matches(pattern: str, normalized_path: str) -> bool:
    return path_pattern_matches(pattern, normalized_path) if "{" in pattern else pattern == normalized_path


def next_runtime_match_reasons(runtime: dict[str, Any] | None, path: str) -> list[str]:
    if not runtime:
        return []
    normalized_path = path.split("?", 1)[0]
    reasons = []
    base_path = runtime.get("base_path")
    if base_path and (normalized_path == base_path or normalized_path.startswith(str(base_path).rstrip("/") + "/")):
        reasons.append(f"basePath:{base_path}")
    trailing_slash = runtime.get("trailing_slash")
    if trailing_slash is not None:
        canonical_patterns = [runtime.get("path")]
        for variants in (runtime.get("locale_variants") or {}).values():
            if variants:
                canonical_patterns.append(variants[0])
        canonical_patterns = [str(pattern) for pattern in canonical_patterns if pattern]
        alternate_patterns = [
            str(pattern)
            for pattern in runtime.get("variants", [])
            if pattern and str(pattern) not in set(canonical_patterns)
        ]
        canonical = any(runtime_variant_matches(pattern, normalized_path) for pattern in canonical_patterns)
        alternate = any(runtime_variant_matches(pattern, normalized_path) for pattern in alternate_patterns)
        if canonical:
            reasons.append("trailingSlash:canonical")
        elif alternate:
            reasons.append("trailingSlash:alternate")
        else:
            reasons.append("trailingSlash:configured")
    for locale, variants in (runtime.get("locale_variants") or {}).items():
        if any(runtime_variant_matches(str(pattern), normalized_path) for pattern in variants):
            reasons.append(f"locale-prefix:{locale}")
            break
    return reasons


def entrypoint_match_reasons(
    entrypoint: dict[str, Any],
    method: str,
    path: str,
    condition_evaluation: dict[str, Any] | None = None,
) -> list[str]:
    normalized_method = method.upper()
    normalized_path = path.split("?", 1)[0]
    methods = {str(item).upper() for item in entrypoint.get("methods", [])}
    match = entrypoint.get("match") or route_match_for_path(str(entrypoint.get("path") or ""), list(methods))
    reasons = []
    if methods:
        reasons.append("method-match" if normalized_method in methods else "method-mismatch")
    else:
        reasons.append("method-unconstrained")
    if normalized_path in {str(item) for item in match.get("paths", [])}:
        reasons.append("path-exact")
    if any(normalized_path.startswith(str(prefix)) for prefix in match.get("path_prefixes", [])):
        reasons.append("path-prefix")
    if any(path_pattern_matches(str(pattern), normalized_path) for pattern in match.get("path_patterns", [])):
        reasons.append("path-pattern")
    reasons.extend(reason for reason in next_runtime_match_reasons(entrypoint.get("next_config"), path) if reason not in reasons)
    rewrite = entrypoint.get("rewrite") or {}
    if rewrite.get("phase"):
        reasons.append(f"rewrite-phase:{rewrite.get('phase')}")
    if rewrite.get("conditional"):
        reasons.append("conditional-route")
        if condition_evaluation:
            reasons.append(str(condition_evaluation.get("status") or "condition-unknown"))
    return reasons


def entrypoint_matches_endpoint(
    entrypoint: dict[str, Any],
    method: str,
    path: str,
    *,
    path_only: bool = False,
) -> bool:
    methods = list(entrypoint.get("methods", []))
    match = json_clone(entrypoint.get("match") or route_match_for_path(str(entrypoint.get("path") or ""), methods))
    if path_only:
        match.pop("methods", None)
        match.pop("exclude_methods", None)
    cluster = {
        "id": cluster_id_from_route_path(str(entrypoint.get("path") or "")),
        "path": entrypoint.get("path"),
        "match": match,
    }
    return cluster_matches_endpoint(cluster, method, path)


def middleware_line_refs(source_root: Path, middleware: dict[str, Any]) -> dict[str, str]:
    source_file = source_ref_to_path(source_root, str(middleware.get("file") or ""))
    refs: dict[str, str] = {}
    for key, pattern_spec in (middleware.get("line_patterns") or {}).items():
        patterns = pattern_spec if isinstance(pattern_spec, list) else [str(pattern_spec)]
        refs[str(key)] = line_of_any(source_file, [str(pattern) for pattern in patterns], source_root)
    return refs


def middleware_match_status(middleware: dict[str, Any], path: str) -> str:
    normalized_path = path.split("?", 1)[0]
    matchers = middleware.get("matchers") or []
    if not matchers:
        return "matched-default-all-paths"
    unresolved = False
    for matcher in matchers:
        patterns = [
            str(pattern)
            for pattern in (matcher.get("path_patterns") or [matcher.get("path_pattern") or matcher.get("source") or ""])
            if str(pattern)
        ]
        if not patterns:
            continue
        if not matcher.get("simple"):
            unresolved = True
            continue
        if any(path_pattern_matches(pattern, normalized_path) for pattern in patterns):
            return "matched-static-matcher"
    return "possible-unresolved-matcher" if unresolved else "not-matched"


def middleware_context_for_endpoint(
    source_root: Path,
    middleware_entries: list[dict[str, Any]],
    method: str,
    path: str,
) -> list[dict[str, Any]]:
    if str(method).upper() not in HTTP_METHODS:
        return []
    context = []
    for middleware in middleware_entries:
        status = middleware_match_status(middleware, path)
        if status == "not-matched":
            continue
        context.append(
            {
                "id": middleware.get("id"),
                "kind": middleware.get("kind"),
                "source_ref": entrypoint_source_ref(source_root, middleware),
                "match_status": status,
                "match_strategy": middleware.get("match_strategy"),
                "matchers": middleware.get("matchers", []),
                "line_refs": middleware_line_refs(source_root, middleware),
                "inference_reasons": middleware.get("inference_reasons", []),
            }
        )
    return context


def route_policy_line_refs(source_root: Path, policy: dict[str, Any]) -> dict[str, str]:
    source_file = source_ref_to_path(source_root, str(policy.get("file") or ""))
    refs: dict[str, str] = {}
    conditions = (policy.get("route_policy") or {}).get("conditions")
    for key, pattern_spec in (policy.get("line_patterns") or {}).items():
        if key == "has_conditions" and not (conditions or {}).get("has"):
            continue
        if key == "missing_conditions" and not (conditions or {}).get("missing"):
            continue
        patterns = pattern_spec if isinstance(pattern_spec, list) else [str(pattern_spec)]
        refs[str(key)] = line_of_any(source_file, [str(pattern) for pattern in patterns if str(pattern)], source_root)
    return refs


def route_policy_match_status(policy: dict[str, Any], path: str) -> str:
    normalized_path = path.split("?", 1)[0]
    match = policy.get("match") or next_config_route_policy_match(str(policy.get("path") or ""))
    route_policy = policy.get("route_policy") or {}
    matched_status = "matched-conditional-policy" if route_policy.get("conditional") else "matched-static-policy"
    if normalized_path in {str(item) for item in match.get("paths", [])}:
        return matched_status
    if any(normalized_path.startswith(str(prefix)) for prefix in match.get("path_prefixes", [])):
        return matched_status
    for pattern in match.get("path_patterns", []):
        pattern_text = str(pattern)
        if middleware_matcher_is_simple(pattern_text):
            if path_pattern_matches(pattern_text, normalized_path):
                return matched_status
        else:
            return "possible-unresolved-policy"
    return "not-matched"


def route_policy_context_for_endpoint(
    source_root: Path,
    policies: list[dict[str, Any]],
    method: str,
    path: str,
    request_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if str(method).upper() not in HTTP_METHODS:
        return []
    context = []
    for policy in policies:
        status = route_policy_match_status(policy, path)
        if status == "not-matched":
            continue
        route_policy = policy.get("route_policy") or {}
        condition_evaluation = None
        if route_policy.get("conditional"):
            condition_evaluation = evaluate_next_config_conditions(route_policy.get("conditions"), request_context)
        context_item = {
            "id": policy.get("id"),
            "kind": policy.get("kind"),
            "source_ref": entrypoint_source_ref(source_root, policy),
            "match_status": status,
            "path": policy.get("path"),
            "route_policy": route_policy,
            "line_refs": route_policy_line_refs(source_root, policy),
            "inference_reasons": policy.get("inference_reasons", []),
            "applicability": entrypoint_applicability(policy, condition_evaluation),
        }
        if condition_evaluation:
            context_item["condition_status"] = condition_evaluation.get("status")
            context_item["condition_results"] = condition_evaluation.get("results", [])
            context_item["condition_context_status_counts"] = condition_evaluation.get("context_status_counts", {})
            context_item["condition_evaluated_context_count"] = condition_evaluation.get("evaluated_context_count", 0)
        context.append(
            context_item
        )
    return context


def resolve_endpoint_sources(
    source_root: Path,
    method: str,
    path: str,
    route_inventory: dict[str, Any] | None = None,
    request_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    route_inventory = route_inventory or discover_nextjs_routes(source_root)
    entrypoints = [
        *(route_inventory.get("routes") or []),
        *(route_inventory.get("rewrites") or []),
        *(route_inventory.get("custom_server_entrypoints") or []),
    ]
    middleware_entries = route_inventory.get("middleware") or []
    server_actions = route_inventory.get("server_actions") or []
    route_policies = [
        *(route_inventory.get("redirects") or []),
        *(route_inventory.get("headers") or []),
    ]
    matches = []
    for entrypoint in entrypoints:
        if not entrypoint_matches_endpoint(
            entrypoint,
            method,
            path,
            path_only=str(method).upper() in HTTP_METHODS,
        ):
            continue
        condition_evaluation = rewrite_condition_evaluation(entrypoint, request_context)
        match_item = {
            "cluster_id": str(entrypoint.get("cluster_id") or cluster_id_from_route_path(str(entrypoint.get("path") or ""))),
            "kind": entrypoint.get("kind"),
            "strategy_set": entrypoint.get("strategy_set"),
            "entrypoint_path": entrypoint.get("path"),
            "source_path": entrypoint.get("source_path"),
            "source_ref": entrypoint_source_ref(source_root, entrypoint),
            "line_refs": entrypoint_line_refs(source_root, entrypoint, method),
            "fixed_upstreams": entrypoint.get("fixed_upstreams", []),
            "rewrite": entrypoint.get("rewrite"),
            "custom_server": entrypoint.get("custom_server"),
            "match_reasons": entrypoint_match_reasons(entrypoint, method, path, condition_evaluation),
            "applicability": entrypoint_applicability(entrypoint, condition_evaluation),
        }
        if condition_evaluation:
            match_item["condition_status"] = condition_evaluation.get("status")
            match_item["condition_results"] = condition_evaluation.get("results", [])
            match_item["condition_context_status_counts"] = condition_evaluation.get("context_status_counts", {})
            match_item["condition_evaluated_context_count"] = condition_evaluation.get("evaluated_context_count", 0)
        matches.append(
            match_item
        )
    middleware_context = middleware_context_for_endpoint(source_root, middleware_entries, method, path)
    route_policy_context = route_policy_context_for_endpoint(source_root, route_policies, method, path, request_context)
    return {
        "method": method,
        "path": path,
        "request_context_available": bool(request_contexts_for_condition_evaluation(request_context)),
        "match_count": len(matches),
        "matches": matches,
        "middleware_count": len(middleware_context),
        "middleware_context": middleware_context,
        "route_policy_count": len(route_policy_context),
        "route_policy_context": route_policy_context,
    }


def request_context_for_observed_endpoint(endpoint: dict[str, Any]) -> dict[str, Any] | None:
    context = endpoint.get("request_context")
    if isinstance(context, dict):
        return context
    contexts = endpoint.get("request_contexts")
    if isinstance(contexts, list) and contexts:
        return {"contexts": [item for item in contexts if isinstance(item, dict)], "context_count": len(contexts)}
    return None


def build_endpoint_source_resolver(
    source_root: Path,
    observed_endpoints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    route_inventory = discover_nextjs_routes(source_root)
    entrypoints = [
        *(route_inventory.get("routes") or []),
        *(route_inventory.get("rewrites") or []),
        *(route_inventory.get("custom_server_entrypoints") or []),
    ]
    middleware_entries = route_inventory.get("middleware") or []
    server_actions = route_inventory.get("server_actions") or []
    route_policies = [
        *(route_inventory.get("redirects") or []),
        *(route_inventory.get("headers") or []),
    ]
    discovered_entrypoints = [
        {
            "cluster_id": str(entrypoint.get("cluster_id") or cluster_id_from_route_path(str(entrypoint.get("path") or ""))),
            "kind": entrypoint.get("kind"),
            "strategy_set": entrypoint.get("strategy_set"),
            "path": entrypoint.get("path"),
            "source_path": entrypoint.get("source_path"),
            "match": entrypoint.get("match"),
            "source_ref": entrypoint_source_ref(source_root, entrypoint),
            "fixed_upstreams": entrypoint.get("fixed_upstreams", []),
            "rewrite": entrypoint.get("rewrite"),
            "custom_server": entrypoint.get("custom_server"),
            "next_config": entrypoint.get("next_config"),
        }
        for entrypoint in entrypoints
    ]
    discovered_middleware = [
        {
            "id": middleware.get("id"),
            "kind": middleware.get("kind"),
            "source_ref": entrypoint_source_ref(source_root, middleware),
            "match_strategy": middleware.get("match_strategy"),
            "matchers": middleware.get("matchers", []),
            "inference_reasons": middleware.get("inference_reasons", []),
        }
        for middleware in middleware_entries
    ]
    discovered_server_actions = [
        {
            "id": action.get("id"),
            "kind": action.get("kind"),
            "source_ref": entrypoint_source_ref(source_root, action),
            "scope": action.get("scope"),
            "action_names": action.get("action_names", []),
            "action_count": action.get("action_count", 0),
            "use_server_directive_count": action.get("use_server_directive_count", 0),
            "line_refs": route_policy_line_refs(source_root, action),
            "inference_reasons": action.get("inference_reasons", []),
            "safety": action.get("safety"),
        }
        for action in server_actions
    ]
    discovered_route_policies = [
        {
            "id": policy.get("id"),
            "kind": policy.get("kind"),
            "source_ref": entrypoint_source_ref(source_root, policy),
            "path": policy.get("path"),
            "source_path": policy.get("source_path"),
            "match": policy.get("match"),
            "route_policy": policy.get("route_policy"),
            "next_config": policy.get("next_config"),
            "inference_reasons": policy.get("inference_reasons", []),
        }
        for policy in route_policies
    ]
    observed_resolution = [
        resolve_endpoint_sources(
            source_root,
            str(endpoint.get("method") or ""),
            str(endpoint.get("path") or ""),
            route_inventory,
            request_context_for_observed_endpoint(endpoint),
        )
        for endpoint in (observed_endpoints or [])
        if endpoint.get("method") and endpoint.get("path")
    ]
    return {
        "status": "resolved" if entrypoints or middleware_entries or server_actions or route_policies else "no-static-entrypoints",
        "methodology": "Static Next.js route, rewrite, custom-server, middleware, Server Actions, redirect, and header-policy resolver. Reads local source only; does not send HTTP requests.",
        "inventory_summary": route_inventory.get("summary", {}),
        "next_config": route_inventory.get("next_config"),
        "discovered_entrypoints": discovered_entrypoints,
        "discovered_middleware": discovered_middleware,
        "discovered_server_actions": discovered_server_actions,
        "discovered_route_policies": discovered_route_policies,
        "observed_endpoint_resolution": observed_resolution,
    }


def build_source_peeks(
    source_root: Path,
    profile: dict[str, Any] | None = None,
    observed_endpoints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profile = profile or default_target_profile()

    def display_path(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    def resolve_line(pattern_spec: Any, default_files: list[Path]) -> str:
        if isinstance(pattern_spec, dict):
            pattern = str(pattern_spec.get("pattern", ""))
            candidate_files = [source_ref_to_path(source_root, str(pattern_spec["file"]))] if pattern_spec.get("file") else default_files
        else:
            pattern = str(pattern_spec)
            candidate_files = default_files

        if not pattern:
            return "missing-pattern"

        for candidate in candidate_files:
            location = line_of(candidate, pattern, source_root)
            if not location.endswith(":not-found") and not location.endswith(":missing"):
                return location
        first = candidate_files[0] if candidate_files else source_root
        return line_of(first, pattern, source_root)

    source_peeks = []
    for item in profile.get("source_peeks", []):
        files = [source_ref_to_path(source_root, str(ref)) for ref in item.get("files", [])]
        source_peeks.append(
            {
                "endpoint": item.get("endpoint"),
                "cluster_ids": item.get("cluster_ids", []),
                "files": [display_path(path) for path in files],
                "relevant_lines": {
                    key: resolve_line(value, files)
                    for key, value in (item.get("line_patterns") or {}).items()
                },
                "conclusion": item.get("conclusion"),
            }
        )

    return {
        "generated_at": utc_now(),
        "target": profile.get("name"),
        "profile": profile_summary(profile),
        "source_root": str(source_root),
        "source_peeks": source_peeks,
        "endpoint_resolver": build_endpoint_source_resolver(source_root, observed_endpoints),
    }


def parse_typescript_string_set(source: str, const_name: str) -> list[str]:
    match = re.search(rf"const\s+{re.escape(const_name)}\s*=\s*new Set\(\[(.*?)\]\)", source, re.S)
    if not match:
        return []
    return re.findall(r"['\"]([^'\"]+)['\"]", match.group(1))


def source_references(source_root: Path, patterns: list[str]) -> list[dict[str, Any]]:
    refs = []
    extensions = {".js", ".jsx", ".ts", ".tsx"}
    for path in sorted((source_root / "src").rglob("*")):
        if path.suffix not in extensions or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for index, line in enumerate(lines, start=1):
            if any(pattern in line for pattern in patterns):
                refs.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "line": index,
                        "sample": line.strip()[:180],
                    }
                )
    return refs


def parse_source_orca_whirlpools(source_root: Path) -> list[dict[str, str]]:
    path = source_root / "src/lib/partners/orca.ts"
    if not path.exists():
        return []

    source = read_text(path)
    match = re.search(r"ORCA_WHIRLPOOLS\s*=\s*\{(.*?)\}\s+as const", source, re.S)
    if not match:
        return []

    pools = []
    for item in re.finditer(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", match.group(1)):
        pools.append({"strategy_id": item.group(1), "address": item.group(2)})
    return pools


def is_base58_solana_address(value: str) -> bool:
    return re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", value) is not None


def compact_json_shape(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        shape: dict[str, Any] = {
            "type": "object",
            "keys": sorted(str(key) for key in value.keys())[:40],
        }
        data = value.get("data")
        if isinstance(data, dict):
            shape["data_keys"] = sorted(str(key) for key in data.keys())[:80]
            shape["data_present"] = True
        else:
            shape["data_present"] = data is not None
        return shape
    if isinstance(value, list):
        return {"type": "array", "length": len(value)}
    return {"type": type(value).__name__}


def build_orca_baseline(
    target: str,
    source_root: Path,
    *,
    address: str | None = None,
    strategy_id: str | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_pools = parse_source_orca_whirlpools(source_root)
    selected = None
    if address:
        selected = {"strategy_id": strategy_id or "manual-address", "address": address}
    elif strategy_id:
        selected = next((pool for pool in source_pools if pool["strategy_id"] == strategy_id), None)
    elif source_pools:
        selected = source_pools[0]

    if not selected:
        return {
            "generated_at": utc_now(),
            "target": target,
            "success": False,
            "error": "No Orca pool address provided and no ORCA_WHIRLPOOLS source addresses found.",
            "source_pools": source_pools,
            "safety": "Single-address baseline only. No pool enumeration is performed.",
        }

    selected_address = selected["address"]
    if not is_base58_solana_address(selected_address):
        return {
            "generated_at": utc_now(),
            "target": target,
            "success": False,
            "error": "Selected Orca pool address is not a base58 Solana-style address.",
            "request": selected,
            "source_pools": source_pools,
            "safety": "Single-address baseline only. No pool enumeration is performed.",
        }

    path = render_path_template(orca_probe_paths(profile)["path_template"], {"address": selected_address})
    response = http_request(
        target,
        "GET",
        path,
        headers={"User-Agent": "InferForge-Orca-Baseline/0.1"},
        timeout=25,
    )
    parsed_body: Any = None
    body_json_ok = False
    if response.get("body_text"):
        try:
            parsed_body = json.loads(response["body_text"])
            body_json_ok = True
        except json.JSONDecodeError:
            parsed_body = None

    body_shape = compact_json_shape(parsed_body) if body_json_ok else {"type": "non-json"}
    data_present = bool(isinstance(parsed_body, dict) and parsed_body.get("data"))
    success = response.get("status") == 200 and body_json_ok and data_present

    return {
        "generated_at": utc_now(),
        "target": target,
        "success": success,
        "request": {
            "strategy_id": selected["strategy_id"],
            "address": selected_address,
            "path": path,
            "source": "cli" if address else f"source:{repo_relative_or_absolute(source_root / 'src/lib/partners/orca.ts')}",
        },
        "response": {
            "status": response["status"],
            "duration_ms": response["duration_ms"],
            "error": response["error"],
            "content_type": response["headers"].get("Content-Type") or response["headers"].get("content-type"),
            "cache_control": response["headers"].get("Cache-Control") or response["headers"].get("cache-control"),
            "body_sha256": response["body_sha256"],
            "body_length": response["body_length"],
            "body_truncated": response["body_truncated"],
            "body_sample": response["body_sample"][:500],
            "body_json": body_json_ok,
            "body_shape": body_shape,
        },
        "source_pools": source_pools,
        "safety": "Single approved/source-known address baseline only. No pool enumeration is performed.",
    }


def build_rpc_method_policy(source_root: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    rpc_path = source_root / "src/app/api/rpc/_shared.ts"
    rpc_source = read_text(rpc_path)
    default_methods = parse_typescript_string_set(rpc_source, "DEFAULT_ALLOWED_METHODS")
    transaction_methods = parse_typescript_string_set(rpc_source, "TRANSACTION_METHODS")
    high_impact_methods = ["sendTransaction", "simulateTransaction"]
    transaction_probe_ids = {
        "rpc_send_transaction_invalid_payload",
        "rpc_simulate_transaction_invalid_payload",
    }
    transaction_probe_results = [
        {
            "probe_id": row["probe_id"],
            "status": row.get("status"),
            "expected": row.get("expected"),
            "expectation_result": row.get("expectation_result"),
            "body_sample": row.get("body_sample", "")[:240],
        }
        for row in results
        if row.get("probe_id") in transaction_probe_ids
    ]
    default_high_impact = sorted(set(default_methods) & set(high_impact_methods))
    env_configured_methods = os.environ.get("SOLANA_RPC_PROXY_ALLOWED_METHODS")
    env_allow_transaction_methods = os.environ.get("SOLANA_RPC_PROXY_ALLOW_TRANSACTION_METHODS")
    explicit_gate_present = "SOLANA_RPC_PROXY_ALLOW_TRANSACTION_METHODS" in rpc_source
    frontend_transaction_refs = source_references(
        source_root,
        ["walletProvider.sendTransaction", "sendRawTransaction", "sendTransaction("],
    )
    proxy_connection_refs = source_references(
        source_root,
        ["/api/rpc/solana/", "getSolanaRpcProxyUrl", "getSolanaRpcProxyEndpoint"],
    )

    if default_high_impact:
        posture = "high-impact-methods-default-allowed"
    elif env_allow_transaction_methods == "true" or (
        env_configured_methods
        and any(method in {item.strip() for item in env_configured_methods.split(",")} for method in high_impact_methods)
    ):
        posture = "high-impact-methods-explicitly-enabled-in-runner-env"
    elif explicit_gate_present and transaction_methods:
        posture = "high-impact-methods-explicit-opt-in"
    else:
        posture = "high-impact-method-policy-unclear"

    return {
        "generated_at": utc_now(),
        "source": str(rpc_path.relative_to(ROOT)),
        "default_allowed_methods": default_methods,
        "transaction_methods": transaction_methods,
        "high_impact_methods": high_impact_methods,
        "default_high_impact_methods": default_high_impact,
        "explicit_transaction_method_gate_present": explicit_gate_present,
        "runner_environment": {
            "SOLANA_RPC_PROXY_ALLOW_TRANSACTION_METHODS": env_allow_transaction_methods,
            "SOLANA_RPC_PROXY_ALLOWED_METHODS_set": env_configured_methods is not None,
        },
        "frontend_transaction_dependency_refs": frontend_transaction_refs,
        "proxy_connection_refs": proxy_connection_refs,
        "transaction_probe_results": transaction_probe_results,
        "policy_posture": posture,
        "recommendation": (
            "Keep transaction methods out of DEFAULT_ALLOWED_METHODS. Enable them only with an explicit deployment decision "
            "and continue to require origin/rate-limit controls and transaction-intent review for returned quote payloads."
        ),
    }


def build_clusters(
    profile: dict[str, Any] | None = None,
    source_root: Path | None = None,
) -> dict[str, Any]:
    profile = profile or default_target_profile()
    source_root = source_root or resolve_repo_path(profile.get("default_source_root") or DEFAULT_SOURCE_ROOT)
    clusters = []
    for cluster in profile.get("clusters", []):
        normalized = json_clone(cluster)
        strategy_set = strategy_set_for_cluster(normalized)
        normalized["strategy_set"] = strategy_set
        if not strategy_set_enabled(profile, strategy_set):
            continue
        normalized["source_refs"] = [
            source_ref_for_artifact(source_root, str(ref))
            for ref in cluster.get("source_refs", [])
        ]
        clusters.append(normalized)
    return {
        "generated_at": utc_now(),
        "source": "InferForge profile-assisted clustering with optional Burp browser history observations.",
        "profile": profile_summary(profile),
        "clusters": clusters,
    }


def path_pattern_matches(pattern: str, path: str) -> bool:
    escaped = re.escape(pattern)
    escaped = re.sub(r"\\\{[^/{}]+\\\*\\\}", r".*", escaped)
    regex = re.sub(r"\\\{[^/{}]+\\\}", r"[^/]+", escaped)
    return re.fullmatch(regex, path) is not None


def cluster_matches_endpoint(cluster: dict[str, Any], method: str, path: str) -> bool:
    normalized_method = method.upper()
    normalized_path = path.split("?", 1)[0]
    match = cluster.get("match") or {}

    methods = {str(item).upper() for item in match.get("methods", [])}
    exclude_methods = {str(item).upper() for item in match.get("exclude_methods", [])}
    if methods and normalized_method not in methods:
        return False
    if exclude_methods and normalized_method in exclude_methods:
        return False

    paths = [str(item) for item in match.get("paths", [])]
    path_prefixes = [str(item) for item in match.get("path_prefixes", [])]
    path_patterns = [str(item) for item in match.get("path_patterns", [])]
    if not (paths or path_prefixes or path_patterns):
        path_patterns = [str(cluster.get("path", ""))]

    if normalized_path in paths:
        return True
    if any(normalized_path.startswith(prefix) for prefix in path_prefixes):
        return True
    return any(path_pattern_matches(pattern, normalized_path) for pattern in path_patterns if pattern)


def classify_endpoint(method: str, path: str, cluster_doc: dict[str, Any] | None = None) -> set[str]:
    cluster_doc = cluster_doc or build_clusters()
    clusters: set[str] = set()

    for cluster in cluster_doc.get("clusters", []):
        if cluster_matches_endpoint(cluster, method, path):
            clusters.add(str(cluster["id"]))

    return clusters


def source_cluster_ids(clusters: dict[str, Any]) -> set[str]:
    return {cluster["id"] for cluster in clusters["clusters"]}


def observed_cluster_ids(traffic_index: dict[str, Any], clusters: dict[str, Any]) -> set[str]:
    observed: set[str] = set()
    for endpoint in traffic_index.get("endpoints", []):
        observed.update(str(cluster_id) for cluster_id in endpoint.get("cluster_ids", []) or [])
        observed.update(classify_endpoint(endpoint["method"], endpoint["path"], clusters))
    return observed


def select_cluster_ids(
    traffic_index: dict[str, Any],
    clusters: dict[str, Any],
    *,
    source_assisted: bool,
) -> dict[str, Any]:
    observed = observed_cluster_ids(traffic_index, clusters)
    source_known = source_cluster_ids(clusters) if source_assisted else set()
    selected = observed | source_known

    return {
        "generated_at": utc_now(),
        "mode": "source-assisted" if source_assisted else "observed-only",
        "observed_cluster_ids": sorted(observed),
        "source_cluster_ids": sorted(source_known),
        "selected_cluster_ids": sorted(selected),
        "reasoning": [
            "Observed clusters come from Burp browser history and prior safe probe traffic.",
            "Source-assisted mode adds known source-defined attack surfaces even if the browser has not visited them yet.",
            "Observed-only mode is stricter and only schedules probes for currently observed endpoint kinds.",
        ],
    }


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def cluster_priority_scores(clusters: dict[str, Any]) -> dict[str, int]:
    scores = {"high": 90, "medium": 60, "low": 30}
    return {
        cluster["id"]: scores.get(cluster.get("priority", "low"), 30)
        for cluster in clusters.get("clusters", [])
    }


def build_probe_ranking(
    probes: list[Probe],
    selection: dict[str, Any],
    clusters: dict[str, Any],
    *,
    max_probes: int | None,
) -> dict[str, Any]:
    priority_by_cluster = cluster_priority_scores(clusters)
    observed = set(selection.get("observed_cluster_ids", []))
    source_known = set(selection.get("source_cluster_ids", []))
    ranked: list[dict[str, Any]] = []

    for original_index, probe in enumerate(probes):
        score = priority_by_cluster.get(probe.category, 30)
        reasons = [f"cluster-priority:{score}"]
        strategy_set = strategy_set_for_probe(probe)
        if strategy_set:
            reasons.append(f"strategy-set:{strategy_set}")

        if probe.category in observed:
            score += 50
            reasons.append("observed-in-burp-or-traffic")
        elif probe.category in source_known:
            score += 15
            reasons.append("source-defined-surface")

        if probe.category in {"solana-rpc-http", "solana-rpc-ws", "quote"}:
            score += 10
            reasons.append("asset-or-transaction-boundary")

        if probe.policy_field:
            score += 6
            reasons.append(f"policy-field:{probe.policy_field}")

        if probe.external:
            score -= 25
            reasons.append("external-upstream-cost")

        if probe.risk.startswith("safe"):
            score += 5
            reasons.append(probe.risk)

        ranked.append(
            {
                "probe_id": probe.id,
                "cluster_id": probe.category,
                "strategy_set": strategy_set,
                "score": score,
                "original_index": original_index,
                "external": probe.external,
                "policy_field": probe.policy_field,
                "risk": probe.risk,
                "expectation": probe.expectation,
                "reasons": reasons,
            }
        )

    ranked.sort(
        key=lambda item: (
            -item["score"],
            item["external"],
            item["cluster_id"],
            item["original_index"],
        )
    )
    selected_count = len(ranked) if max_probes is None else min(max_probes, len(ranked))
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
        item["rank_status"] = "selected" if rank <= selected_count else "deferred-by-budget"

    return {
        "generated_at": utc_now(),
        "selection_mode": selection["mode"],
        "max_probes": max_probes,
        "selected_probe_count": selected_count,
        "total_probe_count": len(ranked),
        "scoring": [
            "Base score comes from endpoint cluster priority.",
            "Observed Burp/traffic surfaces receive the largest bonus.",
            "Source-defined but unobserved surfaces remain eligible in source-assisted mode.",
            "Asset, transaction, and explicit policy-boundary probes receive smaller bonuses.",
            "External upstream probes are penalized so local evidence is gathered first.",
        ],
        "ranked_probes": ranked,
    }


def apply_probe_ranking(probes: list[Probe], ranking: dict[str, Any]) -> list[Probe]:
    by_id = {probe.id: probe for probe in probes}
    selected_ids = [
        item["probe_id"]
        for item in ranking["ranked_probes"]
        if item["rank_status"] == "selected"
    ]
    return [by_id[probe_id] for probe_id in selected_ids if probe_id in by_id]


def format_probe_plan_summary(probe: Probe, ranking_item: dict[str, Any] | None = None) -> str:
    ranking_item = ranking_item or {}
    parts = [
        f"#{ranking_item.get('rank', '?')}",
        f"{probe.id}:",
        probe.method,
        inline_summary_text(probe.path, max_chars=140),
        f"cluster={probe.category}",
    ]
    if ranking_item.get("score") is not None:
        parts.append(f"score={ranking_item.get('score')}")
    if probe.policy_field:
        parts.append(f"policy={probe.policy_field}")
    if probe.risk:
        parts.append(f"risk={probe.risk}")
    if probe.external:
        parts.append("external")
    reasons = ranking_item.get("reasons", []) or []
    if reasons:
        suffix = "" if len(reasons) <= 3 else f",+{len(reasons) - 3}"
        parts.append("reasons=" + ",".join(str(reason) for reason in reasons[:3]) + suffix)
    return " ".join(parts)


def top_probe_plan_summaries(
    probes: list[Probe],
    ranking: dict[str, Any],
    *,
    limit: int = 8,
) -> list[str]:
    rank_by_id = {
        str(item.get("probe_id") or ""): item
        for item in ranking.get("ranked_probes", []) or []
        if isinstance(item, dict)
    }
    return [
        format_probe_plan_summary(probe, rank_by_id.get(probe.id))
        for probe in probes[:limit]
    ]


def request_context_from_probe_result(row: dict[str, Any]) -> dict[str, Any]:
    request = row.get("request") or {}
    target = urllib.parse.urlparse(str(row.get("target") or ""))
    return build_request_context(
        str(request.get("method") or row.get("method") or ""),
        str(request.get("path") or row.get("path") or ""),
        request.get("headers") or {},
        target.netloc,
    )


def request_context_from_burp_history(row: dict[str, Any]) -> dict[str, Any]:
    context = row.get("request_context")
    if isinstance(context, dict) and context.get("path"):
        return context
    return build_request_context(
        str(row.get("method") or ""),
        str(row.get("path") or ""),
        {},
        str(row.get("host") or ""),
    )


def add_endpoint_request_context(item: dict[str, Any], context: dict[str, Any], source: str) -> None:
    if not context.get("method") or not context.get("path"):
        return
    context = json_clone(context)
    sources = context.setdefault("observed_sources", [])
    if source not in sources:
        sources.append(source)
    contexts = item.setdefault("request_contexts", [])
    signature = request_context_signature(context)
    for existing in contexts:
        if request_context_signature(existing) == signature:
            existing_sources = existing.setdefault("observed_sources", [])
            for source_item in sources:
                if source_item not in existing_sources:
                    existing_sources.append(source_item)
            return
    if len(contexts) < MAX_REQUEST_CONTEXTS_PER_ENDPOINT:
        contexts.append(context)
    else:
        item["request_contexts_truncated"] = True


def finalize_endpoint_request_contexts(item: dict[str, Any]) -> None:
    contexts = item.get("request_contexts") or []
    if not contexts:
        return
    item["request_context_count"] = len(contexts)
    item["request_context"] = contexts[0] if len(contexts) == 1 else {"contexts": contexts, "context_count": len(contexts)}


def build_traffic_index(
    results: list[dict[str, Any]],
    burp_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    endpoints: dict[str, dict[str, Any]] = {}
    for row in results:
        key = f"{row['method']} {row['path']}"
        item = endpoints.setdefault(
            key,
            {
                "method": row["method"],
                "path": row["path"],
                "statuses": [],
                "probe_ids": [],
                "cluster_ids": [],
                "observed_via": "safe-local-probe",
            },
        )
        if row["status"] not in item["statuses"]:
            item["statuses"].append(row["status"])
        item["probe_ids"].append(row["probe_id"])
        category = str(row.get("category") or "")
        if category and category != "unknown" and category not in item["cluster_ids"]:
            item["cluster_ids"].append(category)
        add_endpoint_request_context(item, request_context_from_probe_result(row), "safe-local-probe")

    for row in burp_history or []:
        key = f"{row['method']} {row['path']}"
        item = endpoints.setdefault(
            key,
            {
                "method": row["method"],
                "path": row["path"],
                "statuses": [],
                "probe_ids": [],
                "cluster_ids": [],
                "observed_via": "burp-built-in-browser",
            },
        )
        if row.get("status") not in item["statuses"]:
            item["statuses"].append(row.get("status"))
        item["probe_ids"].append("burp-history")
        if item["observed_via"] != "burp-built-in-browser":
            item["observed_via"] = "safe-local-probe-and-burp-history"
        add_endpoint_request_context(item, request_context_from_burp_history(row), "burp-built-in-browser")

    for item in endpoints.values():
        item["cluster_ids"] = sorted(item.get("cluster_ids", []))
        finalize_endpoint_request_contexts(item)

    return {
        "generated_at": utc_now(),
        "note": "Combines safe local probes with any available Burp built-in-browser history observations.",
        "endpoints": list(endpoints.values()),
    }


def build_attack_strategy(
    clusters: dict[str, Any],
    suspicions: list[dict[str, Any]],
    burp_history: list[dict[str, Any]],
) -> dict[str, Any]:
    strategies = [
        {
            "id": "strategy-scope-and-evidence",
            "title": "Evidence-first loop",
            "applies_to": ["all"],
            "phase_order": ["observe", "probe", "compare", "source-peek", "gate"],
            "rules": [
                "Prefer Burp built-in-browser history as black-box evidence when present.",
                "Use MCP direct requests for controlled, repeatable probes.",
                "Use source reads only to answer a concrete black-box question.",
                "Do not mark a finding valid without request/response evidence and an explicit attacker model.",
            ],
            "automation_state": "implemented-as-artifact-contract",
        },
        {
            "id": "strategy-rpc-http",
            "title": "Solana HTTP JSON-RPC proxy strategy",
            "applies_to": ["solana-rpc-http"],
            "attacker_model": "Unauthenticated browser or script that can send same-origin or cross-origin POSTs to the RPC proxy.",
            "primary_questions": [
                "Can blocked methods be reached through aliases, casing, batching, duplicate keys, or content-type variation?",
                "Are allowed methods safe for unauthenticated exposure, especially simulateTransaction and sendTransaction?",
                "Are body size, batch size, origin, and rate-limit controls enforced consistently?",
            ],
            "safe_probe_queue": [
                "implemented: origin matrix with allowed, disallowed, missing Origin, and Referer-only",
                "implemented: method matrix with blocked, unknown, allowed, wrong type, and duplicate JSON keys",
                "implemented: batch matrix with empty, over limit, and mixed allowed/blocked methods",
                "implemented: method/content-type confusion with GET, OPTIONS, text/plain, and malformed JSON",
                "implemented: invalid-payload negative probes for simulateTransaction and sendTransaction",
                "implemented: /api/rpc root compatibility route policy probes that stop before upstream forwarding",
                "bounded body-size tests below destructive thresholds",
            ],
            "source_peek_triggers": [
                "Any blocked method returns upstream-looking data.",
                "Any disallowed Origin receives CORS allow headers.",
                "Any batch with one blocked method partially succeeds.",
                "Any request reaches upstream before local validation.",
            ],
            "finding_gate": [
                "Show the exact JSON-RPC body.",
                "Show baseline versus mutated response.",
                "Identify whether the effect is local validation bypass or upstream behavior.",
            ],
            "safety": "No high-volume rate-limit testing by default; no real wallet transaction submission.",
        },
        {
            "id": "strategy-nextjs-api-routes",
            "title": "Generic Next.js API route strategy",
            "applies_to": ["nextjs-api-routes", "app-route", "pages-api-route"],
            "attacker_model": "Unauthenticated browser or script that can call local Next.js API routes directly.",
            "primary_questions": [
                "Are HTTP methods, content types, and malformed bodies handled consistently?",
                "Do route handlers expose debug data, stack traces, internal headers, or unexpected successful responses?",
                "Are source-only routes or Server Actions kept separate from reportable black-box findings until evidence exists?",
            ],
            "safe_probe_queue": [
                "implemented: low-volume method confusion for discovered API routes",
                "implemented: response-delta grouping so unexpected generic route responses become hardening notes unless impact is proven",
                "implemented: source-peek requests only when a concrete black-box question exists",
            ],
            "source_peek_triggers": [
                "Any generic route returns an unexpected successful response to a method confusion probe.",
                "Any source-discovered route lacks black-box or Burp evidence.",
                "Any Server Action is source-only and needs manual review before verification.",
            ],
            "finding_gate": [
                "Require a concrete attacker-controllable request and impact before reportability.",
                "Keep framework-default or low-impact generic-route behavior as hardening notes.",
            ],
            "safety": "No broad crawling; only route inventory-derived low-volume probes.",
        },
        {
            "id": "strategy-rpc-websocket",
            "title": "Solana WebSocket RPC proxy strategy",
            "applies_to": ["solana-rpc-ws"],
            "attacker_model": "Browser or script that can open a WebSocket to the local app's Solana RPC proxy.",
            "primary_questions": [
                "Does Origin enforcement happen before upgrade?",
                "Are binary, malformed, oversized, and blocked method messages rejected before upstream send?",
                "Can pending-message queues or connection limits be abused?",
            ],
            "safe_probe_queue": [
                "implemented: disallowed Origin handshake",
                "implemented: blocked and wrong-type method messages",
                "implemented: binary message close behavior",
                "implemented: malformed JSON close behavior",
                "implemented: duplicate JSON key and mixed batch rejection",
                "small over-limit pending queue simulation only after manual approval",
            ],
            "source_peek_triggers": [
                "Any disallowed Origin reaches upstream.",
                "Any non-allowlisted method receives an upstream response.",
                "Any client message is forwarded before validation.",
            ],
            "finding_gate": [
                "Capture close code/reason.",
                "Map the close behavior to server.js validation path.",
            ],
            "safety": "Do not run connection-exhaustion tests automatically.",
        },
        {
            "id": "strategy-quote",
            "title": "M0 quote orchestration proxy strategy",
            "applies_to": ["quote"],
            "attacker_model": "Unauthenticated client that can POST quote requests to the same-origin quote proxy.",
            "primary_questions": [
                "Does the server enforce chain, mint, wallet, amount, recipient, and maxNumQuotes policy before forwarding?",
                "Does malformed input produce server errors or internal/upstream detail leakage?",
                "Can executable transaction payloads be tied back to the user's intended swap?",
            ],
            "safe_probe_queue": [
                "implemented: malformed JSON and wrong content type",
                "implemented: missing local shape fields and wrong primitive types",
                "implemented behind --include-external: invalid chain, mint, wallet, amount, recipient, maxNumQuotes, and unknown fields",
                "implemented: transaction payload decoding artifact only; no signing",
            ],
            "source_peek_triggers": [
                "Any shape-valid invalid business request is forwarded upstream.",
                "Any parser/upstream detail is reflected to the client.",
                "Any returned transaction cannot be decoded or matched to UI intent.",
            ],
            "finding_gate": [
                "Separate hardening notes from exploitable validation bypass.",
                "Require proof of impact before escalating beyond informational.",
                "Never submit or sign returned transactions automatically.",
            ],
            "safety": "One low-risk upstream validation probe only when --include-external is set.",
        },
        {
            "id": "strategy-orca",
            "title": "Orca fixed-upstream proxy strategy",
            "applies_to": ["orca-pools"],
            "attacker_model": "Client that controls the pool address path segment.",
            "primary_questions": [
                "Can the path segment escape the fixed upstream route?",
                "Can invalid address shapes cause SSRF/open-proxy behavior or noisy upstream errors?",
                "Does caching expose stale or cross-address data?",
            ],
            "safe_probe_queue": [
                "implemented: invalid base58 characters",
                "implemented: too-short and too-long address shapes",
                "implemented: encoded path traversal markers and extra path segments",
                "implemented: query injection on invalid address shapes",
                "implemented: method confusion with HEAD and POST",
            ],
            "source_peek_triggers": [
                "Any invalid address reaches upstream.",
                "Any response includes upstream URL or internal fetch details.",
            ],
            "finding_gate": [
                "Show fixed upstream cannot be attacker-controlled before closing SSRF concern.",
            ],
            "safety": "No broad address enumeration.",
        },
        {
            "id": "strategy-fixed-upstream-rewrite",
            "title": "Generic fixed-upstream rewrite proxy strategy",
            "applies_to": ["fixed-upstream-proxy", "rewrite-proxy"],
            "attacker_model": "Client that controls a path segment or query string routed through a fixed upstream rewrite/proxy.",
            "primary_questions": [
                "Is the upstream origin fixed by configuration rather than attacker input?",
                "Can encoded traversal, absolute URLs, query injection, or extra path segments escape the intended upstream path?",
                "Does the proxy require a reviewed concrete read-only path before automated Burp observation?",
                "Are upstream errors, auth context, cache headers, and response shapes safe to expose?",
            ],
            "safe_probe_queue": [
                "review-only by default: promote exactly one approved concrete local read-only path before automated observation",
                "implemented for known pool-style fixed upstreams: invalid path segment and encoded traversal probes",
                "use Burp built-in-browser history to prove the reviewed path before adding broader replay evidence",
            ],
            "source_peek_triggers": [
                "Any dynamic rewrite source is discovered without an active reviewed observation path.",
                "Any fixed upstream destination is environment-derived or not resolved in source discovery.",
                "Any response suggests attacker-controlled upstream URL construction.",
            ],
            "finding_gate": [
                "Show the reviewed local path and upstream destination template.",
                "Show request/response evidence for one concrete path before claiming coverage.",
                "Do not enumerate upstream resources or guess private object identifiers.",
            ],
            "safety": "Review-gated for dynamic rewrites; no broad path enumeration.",
        },
    ]

    next_actions = [
        {
            "id": "NEXT-burp-history-ingest",
            "title": "Make Burp history collection first-class",
            "applies_to": ["all"],
            "reason": "Burp MCP history works; the CLI can now normalize raw MCP HTTP history output into reusable observations.",
            "status": "implemented-via-import-burp-history-command",
        },
        {
            "id": "NEXT-quote-validator",
            "title": "Implement quote-specific validator and transaction intent decoder",
            "applies_to": ["quote"],
            "reason": "The strongest current signal is thin local quote validation and executable payload trust boundary.",
            "status": "implemented-in-local-runner",
        },
        {
            "id": "NEXT-transaction-intent-corpus",
            "title": "Feed real quote transaction payloads into the decoder",
            "applies_to": ["quote"],
            "reason": "The decoder is implemented; it needs a successful quote payload corpus to compare transaction instructions against user intent.",
            "status": "waiting-for-real-quote-response",
        },
        {
            "id": "NEXT-transaction-intent-policy",
            "title": "Compare decoded transactions against swap intent",
            "applies_to": ["quote"],
            "reason": "A decoded transaction is only useful if it can be compared against the intended wallet, direction, and token mints without signing or submitting it.",
            "status": "implemented-via-intent-policy-checks",
        },
        {
            "id": "NEXT-probe-selection",
            "title": "Rank probes by endpoint kind and evidence gaps",
            "applies_to": ["all"],
            "reason": "The runner should choose probes from observed attack surface, not only a fixed list.",
            "status": "implemented-via-probe-ranking-artifact-and-max-probes",
        },
        {
            "id": "NEXT-ws-message-shape",
            "title": "Implement safe WebSocket message-shape probes",
            "applies_to": ["solana-rpc-ws"],
            "reason": "The WS proxy should reject malformed JSON, binary frames, duplicate keys, empty or oversized batches, and blocked methods before upstream forwarding.",
            "status": "implemented-via-ws-probes-and-server-validation",
        },
        {
            "id": "NEXT-rpc-high-impact-negative-probes",
            "title": "Exercise high-impact Solana RPC methods with invalid transaction payloads",
            "applies_to": ["solana-rpc-http"],
            "reason": "sendTransaction and simulateTransaction are high-impact allowlisted methods; safe negative probes should prove invalid, unsigned payloads do not succeed or leak internals.",
            "status": "implemented-via-invalid-transaction-rpc-probes",
        },
    ]
    cluster_rows = clusters.get("clusters", []) or []
    cluster_ids = [str(cluster.get("id") or "") for cluster in cluster_rows if cluster.get("id")]
    cluster_kinds = {str(cluster.get("kind") or "") for cluster in cluster_rows if cluster.get("kind")}
    cluster_strategy_sets = {str(cluster.get("strategy_set") or "") for cluster in cluster_rows if cluster.get("strategy_set")}

    def labels_apply_to_current_clusters(labels: list[Any]) -> bool:
        applies_to = {str(item) for item in labels or []}
        return (
            not applies_to
            or "all" in applies_to
            or bool(applies_to.intersection(cluster_ids))
            or bool(applies_to.intersection(cluster_kinds))
            or bool(applies_to.intersection(cluster_strategy_sets))
        )

    relevant_next_actions = [
        action
        for action in next_actions
        if labels_apply_to_current_clusters(action.get("applies_to", ["all"]))
    ]
    relevant_next_action_ids = {str(action.get("id") or "") for action in relevant_next_actions}
    annotated_next_actions = []
    for action in next_actions:
        item = json_clone(action)
        item["relevant"] = str(item.get("id") or "") in relevant_next_action_ids
        annotated_next_actions.append(item)
    next_action_status_counts: dict[str, int] = {}
    for action in relevant_next_actions:
        increment_count(next_action_status_counts, str(action.get("status") or "unknown"))

    def strategy_matches_cluster(strategy: dict[str, Any], cluster: dict[str, Any]) -> bool:
        applies_to = {str(item) for item in strategy.get("applies_to", []) or []}
        return (
            "all" in applies_to
            or str(cluster.get("id") or "") in applies_to
            or str(cluster.get("kind") or "") in applies_to
            or str(cluster.get("strategy_set") or "") in applies_to
        )

    specific_strategies = [
        strategy
        for strategy in strategies
        if "all" not in {str(item) for item in strategy.get("applies_to", []) or []}
    ]
    strategy_coverage = []
    uncovered_strategy_clusters = []
    for cluster in cluster_rows:
        cluster_id = str(cluster.get("id") or "")
        matching = [
            str(strategy.get("id"))
            for strategy in specific_strategies
            if strategy_matches_cluster(strategy, cluster)
        ]
        exempt = str(cluster.get("kind") or "") == "health" or cluster_id == "health"
        if not matching and not exempt:
            uncovered_strategy_clusters.append(cluster_id)
        strategy_coverage.append(
            {
                "cluster_id": cluster_id,
                "kind": cluster.get("kind"),
                "strategy_set": cluster.get("strategy_set"),
                "strategy_ids": matching,
                "exempt": exempt,
            }
        )

    waiting_action_count = sum(
        count
        for status, count in next_action_status_counts.items()
        if status.startswith("waiting-") or status in {"blocked", "blocked-external"}
    )
    if uncovered_strategy_clusters:
        status = "needs-strategy-review"
    elif suspicions:
        status = "active-investigation"
    elif not burp_history:
        status = "needs-burp-history"
    elif waiting_action_count:
        status = "needs-external-evidence"
    else:
        status = "ready-for-regression"

    return {
        "generated_at": utc_now(),
        "status": status,
        "methodology": "black-box-first greybox: Burp observations -> safe probes -> source peek -> finding gate",
        "summary": {
            "clusters": len(cluster_ids),
            "strategies": len(strategies),
            "clusters_with_specific_strategy": len(
                [
                    item
                    for item in strategy_coverage
                    if item.get("strategy_ids") and not item.get("exempt")
                ]
            ),
            "strategy_uncovered_clusters": uncovered_strategy_clusters,
            "burp_history_items": len(burp_history),
            "active_suspicions": len(suspicions),
            "next_action_status_counts": next_action_status_counts,
            "waiting_action_count": waiting_action_count,
            "relevant_next_actions": len(relevant_next_actions),
        },
        "clusters_seen": cluster_ids,
        "burp_history_items": len(burp_history),
        "active_suspicions": [item["id"] for item in suspicions],
        "strategy_coverage": strategy_coverage,
        "strategies": strategies,
        "next_development_actions": annotated_next_actions,
        "relevant_next_development_actions": [
            action for action in annotated_next_actions if action.get("relevant")
        ],
        "safety": "Strategy artifact only. It does not send requests, fuzz, invoke Burp Scanner, sign wallets, or submit transactions.",
    }


def is_waiting_attack_strategy_action(action: dict[str, Any]) -> bool:
    status = str(action.get("status") or "")
    return status.startswith("waiting-") or status in {"blocked", "blocked-external"}


def waiting_attack_strategy_actions(attack_strategy: dict[str, Any] | None) -> list[dict[str, Any]]:
    action_source = (attack_strategy or {}).get("relevant_next_development_actions")
    if action_source is None:
        action_source = (attack_strategy or {}).get("next_development_actions", []) or []
    return [
        action
        for action in action_source
        if isinstance(action, dict) and is_waiting_attack_strategy_action(action)
    ]


def format_attack_strategy_waiting_action(action: dict[str, Any]) -> str:
    action_id = str(action.get("id") or "unknown-action")
    status = str(action.get("status") or "unknown")
    title = str(action.get("title") or "Untitled action")
    return f"{action_id}: {status} - {title}"


def format_attack_strategy_waiting_action_overflow(
    total_count: int,
    shown_count: int,
    *,
    no_write: bool,
    output_path: Path,
) -> str | None:
    remaining = max(0, total_count - shown_count)
    if remaining <= 0:
        return None
    noun = "waiting action" if remaining == 1 else "waiting actions"
    output_label = repo_relative_or_absolute(output_path)
    if no_write:
        return f"Waiting action: {remaining} more {noun}; rerun without --no-write to write {output_label}"
    return f"Waiting action: {remaining} more in {output_label}"


def format_readiness_next_step_overflow(
    total_count: int,
    shown_count: int,
    *,
    no_write: bool,
    output_path: Path,
) -> str | None:
    remaining = max(0, total_count - shown_count)
    if remaining <= 0:
        return None
    noun = "step" if remaining == 1 else "steps"
    output_label = repo_relative_or_absolute(output_path)
    if no_write:
        return f"- {remaining} more {noun}; rerun without --no-write to write {output_label}"
    return f"- {remaining} more {noun} in {output_label}"


def discovered_server_actions_from_source_peeks(source_peeks: dict[str, Any] | None) -> list[dict[str, Any]]:
    endpoint_resolver = (source_peeks or {}).get("endpoint_resolver") or {}
    actions = endpoint_resolver.get("discovered_server_actions") or []
    return [item for item in actions if isinstance(item, dict)]


def identifier_words(value: str) -> set[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    return {
        token.lower()
        for token in re.split(r"[^A-Za-z0-9]+", spaced)
        if token
    }


def server_action_names(action: dict[str, Any]) -> list[str]:
    names = []
    for name in action.get("action_names", []) or []:
        text = str(name).strip()
        if text:
            names.append(text)
    return names


def risky_server_action_names(action_names: list[str]) -> list[str]:
    risky = []
    for name in action_names:
        words = identifier_words(name)
        if words & SERVER_ACTION_REVIEW_KEYWORDS:
            risky.append(name)
    return risky


def server_action_review_candidate(action: dict[str, Any]) -> dict[str, Any]:
    source_ref = str(action.get("source_ref") or action.get("file") or action.get("id") or "unknown")
    action_names = server_action_names(action)
    return {
        "id": f"review_server_action_{safe_probe_id(source_ref)}",
        "type": "server-action-source-review",
        "status": "manual-review",
        "source_ref": source_ref,
        "scope": action.get("scope"),
        "action_names": action_names,
        "action_count": int(action.get("action_count", len(action_names)) or len(action_names)),
        "line_refs": action.get("line_refs", {}),
        "review_questions": [
            "Authentication and authorization are checked before side effects.",
            "Input validation or schema checks happen before persistence, upstream calls, wallet, or transaction work.",
            "CSRF, origin, or same-site assumptions are explicit for browser-reachable mutations.",
            "Returned transaction payloads are decoded/reviewed only and are not signed or submitted automatically.",
            "External side effects are idempotent or guarded against replay where applicable.",
        ],
        "approval_required": [
            "Record the source-review conclusion before closing this evidence gap.",
            "Do not invoke the action or submit a form as part of automated verification.",
        ],
        "safety": "Source review only. No HTTP request, form submission, wallet signing, or mutation is generated.",
    }


def build_evidence_gaps(
    clusters: dict[str, Any],
    results: list[dict[str, Any]],
    burp_history: list[dict[str, Any]],
    transaction_intent: dict[str, Any],
    rpc_method_policy: dict[str, Any] | None = None,
    orca_baseline: dict[str, Any] | None = None,
    quote_collection: dict[str, Any] | None = None,
    source_peeks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    burp_cluster_ids = observed_cluster_ids(build_traffic_index([], burp_history), clusters)
    results_by_cluster: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        results_by_cluster.setdefault(row.get("category", "unknown"), []).append(row)

    gaps: list[dict[str, Any]] = []
    next_probe_candidates: list[dict[str, Any]] = []
    coverage_by_cluster = []
    cluster_ids = {str(cluster.get("id")) for cluster in clusters.get("clusters", []) if cluster.get("id")}

    def add_gap(
        gap_id: str,
        cluster_id: str,
        title: str,
        priority: str,
        reason: str,
        safe_next_step: str,
        safety_gate: str,
        *,
        review_candidates: list[dict[str, Any]] | None = None,
    ) -> None:
        gap = {
            "id": gap_id,
            "cluster_id": cluster_id,
            "title": title,
            "priority": priority,
            "reason": reason,
            "safe_next_step": safe_next_step,
            "safety_gate": safety_gate,
        }
        if review_candidates:
            gap["review_candidates"] = review_candidates
        gaps.append(gap)

    for cluster in clusters.get("clusters", []):
        cluster_id = cluster["id"]
        rows = results_by_cluster.get(cluster_id, [])
        unexpected = [row for row in rows if not row.get("expected")]
        policy_fields = sorted(
            {
                str(row["policy_field"])
                for row in rows
                if row.get("policy_field") is not None
            }
        )
        burp_observed = cluster_id in burp_cluster_ids
        if unexpected:
            coverage_status = "probe-review-needed"
        elif rows:
            coverage_status = "covered-by-safe-probes"
        else:
            coverage_status = "not-probed"

        coverage_by_cluster.append(
            {
                "cluster_id": cluster_id,
                "kind": cluster.get("kind"),
                "priority": cluster.get("priority"),
                "probe_count": len(rows),
                "unexpected_count": len(unexpected),
                "policy_fields_covered": policy_fields,
                "burp_browser_observed": burp_observed,
                "coverage_status": coverage_status,
            }
        )

        if not burp_observed and cluster_id != "health":
            review_candidates = review_observation_candidates_for_cluster(cluster)
            observation_reason = (
                "Safe probes cover this source-defined surface, but Burp built-in-browser history has not observed a normal user flow for it yet."
                if rows
                else "This source-defined surface is discovery-only until a Burp built-in-browser flow or reviewed profile probe target provides concrete black-box evidence."
            )
            observation_next_step = (
                "Review the generated observation candidate, choose one known safe concrete path, add it to the profile's `burp_observation_plan`, then rerun Burp observation."
                if review_candidates
                else "Use the Burp built-in browser to exercise the relevant UI flow, then import or read the matching Proxy history before comparing mutations."
            )
            add_gap(
                f"GAP-{cluster_id}-burp-observation",
                cluster_id,
                "Browser-flow observation missing",
                "medium" if cluster.get("priority") == "high" else "low",
                observation_reason,
                observation_next_step,
                "Keep Proxy Intercept off for automation; turn it on only for a human-edited request.",
                review_candidates=review_candidates,
            )

    seen_server_action_refs: set[str] = set()
    for action in discovered_server_actions_from_source_peeks(source_peeks):
        source_ref = str(action.get("source_ref") or action.get("file") or action.get("id") or "unknown")
        if source_ref in seen_server_action_refs:
            continue
        seen_server_action_refs.add(source_ref)
        action_names = server_action_names(action)
        risky_names = risky_server_action_names(action_names)
        name_summary = ", ".join(action_names[:8]) if action_names else "no exported action names statically extracted"
        risky_summary = (
            f" Mutation-sensitive action names: {', '.join(risky_names[:8])}."
            if risky_names
            else ""
        )
        add_gap(
            f"GAP-server-action-{safe_probe_id(source_ref)}-manual-review",
            "server-actions",
            "Server Action mutation boundary needs manual source review",
            "high" if risky_names else "medium",
            (
                f"Static discovery found Next.js Server Action source `{source_ref}` with actions: "
                f"{name_summary}. Server Actions are not invoked by this tool, so mutation boundaries "
                f"must be confirmed from source.{risky_summary}"
            ),
            (
                "Review authentication, authorization, CSRF/origin assumptions, input validation, "
                "wallet/transaction boundaries, idempotency, and external side effects in the Server Action source."
            ),
            "Source review only; do not invoke Server Actions, submit forms, sign wallets, or mutate state automatically.",
            review_candidates=[server_action_review_candidate(action)],
        )

    quote_rows = results_by_cluster.get("quote", [])
    quote_cluster_present = "quote" in cluster_ids or bool(quote_rows)
    if quote_cluster_present and transaction_intent.get("candidates_seen", 0) == 0:
        quote_diagnosis = (quote_collection or {}).get("diagnosis", {})
        quote_classification = quote_diagnosis.get("classification")
        quote_reason = "The transaction decoder is implemented, but this run did not receive a successful quote response containing a transaction candidate."
        quote_next_step = "Run collect-quote with a test wallet and amount once M0 returns a 200 quote, then compare decoded account keys, signer, mints, and program IDs against intent."
        if quote_classification == "m0-config-missing-or-placeholder":
            quote_reason = (
                "The transaction decoder is implemented, but the last quote collection did not reach M0 with real credentials: "
                "the local M0 orchestration key is missing or still set to a template placeholder."
            )
            quote_next_step = (
                "Configure a real M0_ORCHESTRATION_API_KEY, restart the target server, then rerun collect-quote. "
                "Only decode returned transactions; do not sign or submit them automatically."
            )
        elif quote_classification == "m0-upstream-auth-or-policy-rejected":
            quote_reason = (
                "The transaction decoder is implemented, but the last quote collection was rejected by upstream M0 authorization or business policy."
            )
            quote_next_step = (
                "Confirm the M0 key, account permissions, route, wallet, and amount are eligible, then rerun collect-quote. "
                "Only decode returned transactions; do not sign or submit them automatically."
            )
        add_gap(
            "GAP-quote-transaction-corpus",
            "quote",
            "No real quote transaction payload corpus",
            "high",
            quote_reason,
            quote_next_step,
            "Never sign or submit returned transactions automatically.",
        )
        next_probe_candidates.append(
            {
                "id": "NEXT-quote-collect-real-payload",
                "cluster_id": "quote",
                "priority": "high",
                "command": (
                    "python3 scripts/inferforge.py collect-quote --direction buy "
                    f"--wallet {DEFAULT_TEST_WALLET} --amount-in 1000000"
                ),
                "expected_evidence": ".greybox/transaction-payloads.json and .greybox/transaction-intent.json",
                "safety_gate": "Decode only; no signing or Solana submission.",
            }
        )

    if quote_cluster_present and not any(row.get("external") for row in quote_rows):
        add_gap(
            "GAP-quote-business-policy-probes",
            "quote",
            "Business-policy quote probes not executed",
            "medium",
            "The current run did not include chain, mint, wallet, recipient, amount, maxNumQuotes, and unknown-field policy probes.",
            "Rerun audit with --include-external when bounded M0-facing validation probes are acceptable.",
            "Stop if any probe would require a real signature, broad enumeration, or repeated upstream traffic.",
        )

    rpc_rows = results_by_cluster.get("solana-rpc-http", [])
    if rpc_rows:
        high_impact_rows = [
            row
            for row in rpc_rows
            if row.get("probe_id")
            in {
                "rpc_simulate_transaction_invalid_payload",
                "rpc_send_transaction_invalid_payload",
            }
        ]
        high_impact_passed = high_impact_rows and all(row.get("expected") for row in high_impact_rows)
        rpc_posture = (rpc_method_policy or {}).get("policy_posture")
        if rpc_posture == "high-impact-methods-explicit-opt-in" and high_impact_rows:
            pass
        elif high_impact_passed:
            add_gap(
                "GAP-rpc-high-impact-policy-decision",
                "solana-rpc-http",
                "High-impact allowed RPC methods need an explicit exposure decision",
                "medium",
                "Invalid-payload negative probes for sendTransaction and simulateTransaction passed, but the default unauthenticated allowlist still exposes high-impact transaction methods to browser clients.",
                "Decide whether sendTransaction and simulateTransaction should remain in the default allowlist, require authentication, or move behind transaction-intent policy checks.",
                "Any future positive-path test must use explicit approval and must not submit a real signed transaction automatically.",
            )
        else:
            add_gap(
                "GAP-rpc-high-impact-allowed-methods",
                "solana-rpc-http",
                "High-impact allowed RPC methods need safe negative probes",
                "high",
                "Source policy allows sendTransaction and simulateTransaction, but this run does not yet prove invalid, unsigned payloads fail safely.",
                "Add bounded negative probes using invalid transaction payloads, then decide whether these methods should require authentication, be removed from the default allowlist, or be constrained by transaction intent checks.",
                "Use invalid, unsigned payloads only; never submit a valid signed transaction.",
            )
            next_probe_candidates.append(
                {
                    "id": "NEXT-rpc-high-impact-negative-probes",
                    "cluster_id": "solana-rpc-http",
                    "priority": "high",
                    "probe_shapes": [
                        "simulateTransaction with syntactically invalid transaction data",
                        "sendTransaction with syntactically invalid transaction data",
                        "oversized-but-bounded request body below configured MAX_BODY_BYTES",
                    ],
                    "expected_evidence": "Local rejection or sanitized upstream JSON-RPC error without transaction submission.",
                    "safety_gate": "Invalid payloads only; no valid signatures; one request per method.",
                }
            )

    ws_resource_rows = [
        row
        for row in results_by_cluster.get("solana-rpc-ws", [])
        if row.get("probe_id") == "ws_resource_connection_limit"
    ]
    if results_by_cluster.get("solana-rpc-ws") and not (
        ws_resource_rows and all(row.get("expected") for row in ws_resource_rows)
    ):
        add_gap(
            "GAP-ws-resource-controls",
            "solana-rpc-ws",
            "WebSocket resource-control behavior remains manual",
            "medium",
            "Message-shape policy is covered, but connection-count and pending-queue pressure tests are intentionally not automated by default.",
            "Add an approval-gated low-volume resource probe that opens a small fixed number of sockets and records close/error behavior.",
            "Require explicit operator approval and hard limits before resource-pressure tests.",
        )

    if results_by_cluster.get("orca-pools") and not (orca_baseline or {}).get("success"):
        add_gap(
            "GAP-orca-real-address-cache-baseline",
            "orca-pools",
            "Real pool address cache behavior not baselined",
            "low",
            "Invalid address and route-escape probes pass, but this run does not compare behavior for a known real pool address or cache headers.",
            "With one approved known pool address, collect a single positive baseline and compare cache headers and response shape against invalid-address probes.",
            "No address enumeration or broad upstream Orca requests.",
            review_candidates=[build_orca_baseline_review_candidate()],
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda item: (priority_order.get(item["priority"], 9), item["cluster_id"], item["id"]))
    next_probe_candidates.sort(key=lambda item: (priority_order.get(item["priority"], 9), item["id"]))

    return {
        "generated_at": utc_now(),
        "methodology": "Evidence gaps are not findings; they are the next safe questions to answer before escalating risk.",
        "coverage_by_cluster": coverage_by_cluster,
        "gaps": gaps,
        "next_probe_candidates": next_probe_candidates,
    }


def compact_source_refs(values: list[Any]) -> list[str]:
    refs = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        refs.append(text)
    return refs


def endpoint_request_key(method: str, path: str) -> str:
    return f"{str(method or '').upper()} {str(path or '').split('?', 1)[0]}"


def observed_cluster_ids_from_traffic_index(
    traffic_index: dict[str, Any] | None,
    clusters: dict[str, Any],
) -> set[str]:
    observed: set[str] = set()
    for endpoint in (traffic_index or {}).get("endpoints", []) or []:
        observed.update(str(cluster_id) for cluster_id in endpoint.get("cluster_ids", []) or [])
        observed.update(
            classify_endpoint(
                str(endpoint.get("method") or ""),
                str(endpoint.get("path") or ""),
                clusters,
            )
        )
    return observed


def source_resolver_observed_resolution_map(source_peeks: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    endpoint_resolver = (source_peeks or {}).get("endpoint_resolver") or {}
    by_endpoint: dict[str, dict[str, Any]] = {}
    for resolution in endpoint_resolver.get("observed_endpoint_resolution", []) or []:
        key = endpoint_request_key(str(resolution.get("method") or ""), str(resolution.get("path") or ""))
        by_endpoint[key] = resolution
    return by_endpoint


def source_refs_from_observed_resolution(resolution: dict[str, Any] | None) -> list[str]:
    if not resolution:
        return []
    refs: list[Any] = []
    for match in resolution.get("matches", []) or []:
        refs.append(match.get("source_ref"))
    for item in resolution.get("middleware_context", []) or []:
        refs.append(item.get("source_ref"))
    for item in resolution.get("route_policy_context", []) or []:
        refs.append(item.get("source_ref"))
    return compact_source_refs(refs)


def cluster_source_refs_by_id(clusters: dict[str, Any]) -> dict[str, list[str]]:
    return {
        str(cluster.get("id")): compact_source_refs(cluster.get("source_refs", []) or [])
        for cluster in clusters.get("clusters", []) or []
        if cluster.get("id")
    }


def configured_source_peek_requests(
    source_peeks: dict[str, Any] | None,
    observed_cluster_ids: set[str],
) -> list[dict[str, Any]]:
    requests = []
    for item in (source_peeks or {}).get("source_peeks", []) or []:
        cluster_ids = [str(cluster_id) for cluster_id in item.get("cluster_ids", []) or []]
        if cluster_ids and observed_cluster_ids and not (set(cluster_ids) & observed_cluster_ids):
            continue
        endpoint = str(item.get("endpoint") or "profile source context")
        files = compact_source_refs(item.get("files", []) or [])
        requests.append(
            {
                "id": f"PEEK-profile-{safe_probe_id(endpoint)}",
                "trigger": "profile-source-context",
                "status": "answered" if files else "needs-resolution",
                "entrypoint": endpoint,
                "cluster_ids": cluster_ids,
                "reason": "Profile declared narrow source context for a cluster that has black-box evidence in this run.",
                "questions": [
                    "Which narrow source files explain the observed endpoint behavior?",
                    "Do the configured source line refs support the black-box policy checks?",
                ],
                "source_refs": files,
                "line_refs": item.get("relevant_lines", {}),
                "conclusion": item.get("conclusion"),
                "answer_artifact": "source-peek-results.json",
                "max_files": max(1, len(files)),
                "max_call_depth": 1,
            }
        )
    return requests


def server_action_source_peek_requests(source_peeks: dict[str, Any] | None) -> list[dict[str, Any]]:
    requests = []
    for action in discovered_server_actions_from_source_peeks(source_peeks):
        source_ref = str(action.get("source_ref") or action.get("file") or action.get("id") or "unknown")
        action_names = server_action_names(action)
        requests.append(
            {
                "id": f"PEEK-server-action-{safe_probe_id(source_ref)}",
                "trigger": "source-only-server-action-discovery",
                "status": "manual-review",
                "entrypoint": "Next.js Server Action",
                "cluster_ids": ["server-actions"],
                "reason": "Server Actions are source-discovered mutation boundaries; they are not invoked by the tool.",
                "questions": [
                    "Are authentication and authorization checked before side effects?",
                    "Are inputs validated before persistence, upstream calls, wallet, or transaction work?",
                    "Are CSRF, origin, replay, and idempotency assumptions explicit for browser-reachable mutations?",
                ],
                "source_refs": [source_ref],
                "line_refs": action.get("line_refs", {}),
                "action_names": action_names,
                "answer_artifact": "source-peek-results.json",
                "max_files": 1,
                "max_call_depth": 1,
                "safety": "Source review only; do not invoke the action or submit forms automatically.",
            }
        )
    return requests


def suspicion_source_peek_requests(suspicions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    requests = []
    for item in suspicions:
        suspicion_id = str(item.get("id") or "suspicion")
        evidence_refs = []
        for row in item.get("blackbox_evidence", []) or []:
            probe_id = row.get("probe_id")
            if probe_id:
                evidence_refs.append(f"PROBE-{probe_id}")
        source_refs = compact_source_refs(item.get("source_refs", []) or [])
        requests.append(
            {
                "id": f"PEEK-{safe_probe_id(suspicion_id)}",
                "trigger": "suspicion",
                "status": "answered" if source_refs else "needs-resolution",
                "suspicion_id": suspicion_id,
                "entrypoint": item.get("entrypoint"),
                "cluster_ids": compact_source_refs([row.get("category") for row in item.get("blackbox_evidence", []) or []]),
                "reason": item.get("hypothesis"),
                "questions": item.get("source_questions", []) or [
                    "Which source boundary explains the black-box behavior?"
                ],
                "source_refs": source_refs,
                "blackbox_evidence_refs": compact_source_refs(evidence_refs),
                "answer_artifact": "source-peek-results.json",
                "max_files": max(1, min(5, len(source_refs) or 5)),
                "max_call_depth": 2,
            }
        )
    return requests


def evidence_gap_source_peek_requests(
    evidence_gaps: dict[str, Any] | None,
    cluster_source_refs: dict[str, list[str]],
) -> list[dict[str, Any]]:
    requests = []
    for gap in (evidence_gaps or {}).get("gaps", []) or []:
        candidates = gap.get("review_candidates", []) or []
        source_candidates = [
            candidate
            for candidate in candidates
            if candidate.get("type") == "server-action-source-review"
            or candidate.get("source_ref")
            or candidate.get("source_refs")
        ]
        source_review_text = "source review" in str(gap.get("safe_next_step") or gap.get("safety_gate") or "").lower()
        if not source_candidates and not source_review_text:
            continue
        gap_id = str(gap.get("id") or "gap")
        cluster_id = str(gap.get("cluster_id") or "unknown")
        candidate_refs: list[Any] = []
        for candidate in source_candidates:
            candidate_refs.append(candidate.get("source_ref"))
            candidate_refs.extend(candidate.get("source_refs", []) or [])
        source_refs = compact_source_refs([*candidate_refs, *cluster_source_refs.get(cluster_id, [])])
        questions = [
            str(gap.get("safe_next_step") or "Review the source context for this evidence gap."),
        ]
        for candidate in source_candidates:
            questions.extend(candidate.get("review_questions", []) or [])
        requests.append(
            {
                "id": f"PEEK-gap-{safe_probe_id(gap_id)}",
                "trigger": "evidence-gap",
                "status": "manual-review",
                "gap_id": gap_id,
                "entrypoint": gap.get("title"),
                "cluster_ids": [cluster_id],
                "reason": gap.get("reason"),
                "questions": compact_source_refs(questions),
                "source_refs": source_refs,
                "review_candidate_ids": compact_source_refs([candidate.get("id") for candidate in source_candidates]),
                "answer_artifact": "source-peek-results.json",
                "max_files": max(1, min(5, len(source_refs) or 5)),
                "max_call_depth": 1,
                "safety": gap.get("safety_gate"),
            }
        )
    return requests


def endpoint_source_peek_requests(
    traffic_index: dict[str, Any] | None,
    clusters: dict[str, Any],
    source_peeks: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    requests = []
    cluster_refs = cluster_source_refs_by_id(clusters)
    resolution_by_endpoint = source_resolver_observed_resolution_map(source_peeks)
    for endpoint in (traffic_index or {}).get("endpoints", []) or []:
        method = str(endpoint.get("method") or "")
        path = str(endpoint.get("path") or "")
        if not method or not path:
            continue
        key = endpoint_request_key(method, path)
        cluster_ids = sorted(
            set(str(cluster_id) for cluster_id in endpoint.get("cluster_ids", []) or [])
            | classify_endpoint(method, path, clusters)
        )
        resolution = resolution_by_endpoint.get(key)
        source_refs = compact_source_refs(
            [
                *source_refs_from_observed_resolution(resolution),
                *[
                    ref
                    for cluster_id in cluster_ids
                    for ref in cluster_refs.get(cluster_id, [])
                ],
            ]
        )
        probe_ids = compact_source_refs(endpoint.get("probe_ids", []) or [])
        requests.append(
            {
                "id": f"PEEK-endpoint-{safe_probe_id(key)}",
                "trigger": "observed-endpoint",
                "status": "answered" if source_refs else "needs-resolution",
                "entrypoint": key,
                "method": method.upper(),
                "path": path,
                "cluster_ids": cluster_ids,
                "observed_via": endpoint.get("observed_via"),
                "observed_statuses": endpoint.get("statuses", []),
                "probe_refs": [f"PROBE-{probe_id}" for probe_id in probe_ids if probe_id != "burp-history"],
                "burp_history_observed": "burp-history" in probe_ids or "burp" in str(endpoint.get("observed_via") or ""),
                "reason": "Endpoint has black-box evidence from Burp history and/or bounded probes; source context should answer only the observed routing and policy question.",
                "questions": [
                    "Which local handler, rewrite, middleware, or route policy implements this observed endpoint?",
                    "Do the source-enforced method, input-shape, origin, and upstream boundaries explain the observed black-box behavior?",
                ],
                "source_refs": source_refs,
                "resolver_match_count": None if resolution is None else resolution.get("match_count", 0),
                "answer_artifact": "source-peek-results.json",
                "max_files": max(1, min(5, len(source_refs) or 5)),
                "max_call_depth": 1,
            }
        )
    return requests


def build_source_peek_requests(
    clusters: dict[str, Any],
    traffic_index: dict[str, Any] | None,
    source_peeks: dict[str, Any] | None,
    suspicions: list[dict[str, Any]] | None,
    evidence_gaps: dict[str, Any] | None,
) -> dict[str, Any]:
    cluster_refs = cluster_source_refs_by_id(clusters)
    observed_clusters = observed_cluster_ids_from_traffic_index(traffic_index, clusters)
    requests: list[dict[str, Any]] = []
    for item in [
        *endpoint_source_peek_requests(traffic_index, clusters, source_peeks),
        *configured_source_peek_requests(source_peeks, observed_clusters),
        *suspicion_source_peek_requests(suspicions or []),
        *server_action_source_peek_requests(source_peeks),
        *evidence_gap_source_peek_requests(evidence_gaps, cluster_refs),
    ]:
        requests.append(item)

    seen_ids: set[str] = set()
    deduped = []
    for item in requests:
        request_id = str(item.get("id") or f"PEEK-{len(deduped) + 1}")
        if request_id in seen_ids:
            continue
        seen_ids.add(request_id)
        deduped.append(item)
    requests = deduped

    trigger_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for item in requests:
        trigger = str(item.get("trigger") or "unknown")
        status = str(item.get("status") or "unknown")
        trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1

    if not requests:
        status = "no-source-peek-requests"
    elif status_counts.get("needs-resolution"):
        status = "needs-source-resolution"
    elif status_counts.get("manual-review"):
        status = "answered-with-manual-review"
    else:
        status = "answered"

    return {
        "generated_at": utc_now(),
        "status": status,
        "methodology": "Source-peek requests explain why source context was consulted: concrete observed endpoints, suspicions, source-only Server Actions, or evidence gaps. This artifact is read-only and does not run probes.",
        "summary": {
            "requests": len(requests),
            "trigger_counts": trigger_counts,
            "status_counts": status_counts,
            "observed_clusters": sorted(observed_clusters),
        },
        "requests": requests,
        "artifact_refs": {
            "traffic_index": "traffic-index.json",
            "source_peeks": "source-peek-results.json",
            "suspicions": "suspicions.json",
            "evidence_gaps": "evidence-gaps.json",
            "endpoint_clusters": "endpoint-clusters.json",
        },
        "safety": "Read-only source-context planning artifact. It does not send HTTP requests, invoke Server Actions, sign wallets, or submit transactions.",
    }


def observation_run_cluster_ids(burp_observation_run: dict[str, Any] | None) -> set[str]:
    clusters = {
        str(cluster_id)
        for cluster_id in ((burp_observation_run or {}).get("summary", {}) or {}).get("clusters", []) or []
        if cluster_id
    }
    for request in (burp_observation_run or {}).get("requests", []) or []:
        if request.get("cluster"):
            clusters.add(str(request.get("cluster")))
    websocket_upgrade = (burp_observation_run or {}).get("websocket_upgrade")
    if isinstance(websocket_upgrade, dict) and websocket_upgrade.get("cluster"):
        clusters.add(str(websocket_upgrade.get("cluster")))
    return clusters


def review_candidates_by_cluster(profile: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    by_cluster: dict[str, list[dict[str, Any]]] = {}
    for candidate in collect_review_observation_candidates(profile or {}):
        cluster_id = str(candidate.get("cluster") or "")
        if not cluster_id:
            continue
        by_cluster.setdefault(cluster_id, []).append(candidate)
    return by_cluster


def evidence_gap_ids_by_cluster(evidence_gaps: dict[str, Any] | None) -> dict[str, list[str]]:
    by_cluster: dict[str, list[str]] = {}
    for gap in (evidence_gaps or {}).get("gaps", []) or []:
        cluster_id = str(gap.get("cluster_id") or "")
        gap_id = str(gap.get("id") or "")
        if not cluster_id or not gap_id:
            continue
        by_cluster.setdefault(cluster_id, []).append(gap_id)
    return by_cluster


def build_burp_observation_coverage(
    target: str,
    profile: dict[str, Any] | None,
    clusters: dict[str, Any],
    burp_history: list[dict[str, Any]],
    burp_observation_run: dict[str, Any] | None,
    evidence_gaps: dict[str, Any] | None,
) -> dict[str, Any]:
    history_cluster_ids = observed_cluster_ids(build_traffic_index([], burp_history), clusters)
    run_cluster_ids = observation_run_cluster_ids(burp_observation_run)
    run_unexpected = int(((burp_observation_run or {}).get("summary", {}) or {}).get("unexpected", 0) or 0)
    active_plan_error = None
    try:
        active_plan = build_burp_observation_plan(target, profile)
    except ValueError as error:
        active_plan = []
        active_plan_error = str(error)
    active_plan_by_cluster: dict[str, list[dict[str, Any]]] = {}
    for item in active_plan:
        active_plan_by_cluster.setdefault(str(item.get("cluster") or "unknown"), []).append(item)
    ws_profile = websocket_observation_config(profile)
    if ws_profile is not None:
        active_plan_by_cluster.setdefault(str(ws_profile.get("cluster") or "solana-rpc-ws"), []).append(
            {
                "id": ws_profile.get("id") or "burp_observe_ws_upgrade",
                "method": "WS",
                "path": ws_profile.get("path"),
                "expected_statuses": ws_profile.get("expected_statuses", [101]),
                "cluster": ws_profile.get("cluster") or "solana-rpc-ws",
            }
        )
    review_by_cluster = review_candidates_by_cluster(profile)
    gap_by_cluster = evidence_gap_ids_by_cluster(evidence_gaps)

    cluster_rows = []
    status_counts: dict[str, int] = {}
    for cluster in clusters.get("clusters", []) or []:
        cluster_id = str(cluster.get("id") or "unknown")
        history_observed = cluster_id in history_cluster_ids
        observe_run_generated = cluster_id in run_cluster_ids
        active_items = active_plan_by_cluster.get(cluster_id, [])
        review_candidates = review_by_cluster.get(cluster_id, [])
        if history_observed:
            status = "burp-history-observed"
            next_action = "No Burp observation action is required for coverage; keep history fresh with burp-sync when flows change."
        elif observe_run_generated and run_unexpected:
            status = "observe-run-unexpected"
            next_action = "Inspect burp-observation-run.json before importing this flow as coverage evidence."
        elif observe_run_generated:
            status = "observe-run-generated-not-imported"
            next_action = "Run burp-sync to import the generated Burp Proxy history into burp-history-observations.jsonl."
        elif active_items:
            status = "ready-to-observe"
            next_action = "Run burp-sync --observe to generate and import this profile-defined Burp observation flow."
        elif review_candidates:
            status = "needs-reviewed-observation-promotion"
            next_action = "Review one concrete local read-only path, promote the review candidate into a reviewed profile, then run burp-sync --observe."
        else:
            status = "needs-manual-browser-flow"
            next_action = "Exercise the relevant UI flow in Burp's built-in browser, then run burp-sync to import the history."
        status_counts[status] = status_counts.get(status, 0) + 1
        cluster_rows.append(
            {
                "cluster_id": cluster_id,
                "kind": cluster.get("kind"),
                "priority": cluster.get("priority"),
                "status": status,
                "burp_history_observed": history_observed,
                "observe_run_generated": observe_run_generated,
                "active_observation_count": len(active_items),
                "active_observations": [
                    {
                        "id": item.get("id"),
                        "method": item.get("method"),
                        "path": item.get("path"),
                        "expected_statuses": item.get("expected_statuses", []),
                    }
                    for item in active_items
                ],
                "review_candidate_count": len(review_candidates),
                "review_candidate_ids": [candidate.get("id") for candidate in review_candidates],
                "evidence_gaps": gap_by_cluster.get(cluster_id, []),
                "next_action": next_action,
            }
        )

    if active_plan_error:
        status = "blocked-profile-validation"
    elif status_counts.get("observe-run-unexpected"):
        status = "observe-run-unexpected"
    elif status_counts.get("needs-reviewed-observation-promotion") or status_counts.get("needs-manual-browser-flow"):
        status = "needs-human-review"
    elif status_counts.get("ready-to-observe") or status_counts.get("observe-run-generated-not-imported"):
        status = "needs-burp-sync"
    elif cluster_rows:
        status = "covered"
    else:
        status = "no-clusters"

    return {
        "generated_at": utc_now(),
        "status": status,
        "target": target,
        "profile": profile_summary(profile),
        "summary": {
            "clusters": len(cluster_rows),
            "burp_history_observed_clusters": sorted(history_cluster_ids),
            "observe_run_clusters": sorted(run_cluster_ids),
            "active_observation_clusters": sorted(active_plan_by_cluster),
            "review_candidate_clusters": sorted(review_by_cluster),
            "status_counts": status_counts,
            "observe_run_unexpected": run_unexpected,
            "active_plan_error": active_plan_error,
        },
        "clusters": cluster_rows,
        "artifact_refs": {
            "burp_history": "burp-history-observations.jsonl",
            "burp_observation_run": "burp-observation-run.json",
            "evidence_gaps": "evidence-gaps.json",
            "target_profile": TARGET_PROFILE_ARTIFACT,
            "review_candidates": "review-observation-candidates.json",
            "reviewed_profile": "reviewed-profile.json",
        },
        "safety": "Read-only Burp coverage planning artifact. It does not send HTTP requests; use burp-sync --observe for deterministic low-volume observation traffic.",
    }


DISCOVERY_SURFACE_SOURCES = [
    ("route", "routes"),
    ("rewrite", "rewrites"),
    ("custom-server-entrypoint", "custom_server_entrypoints"),
    ("middleware", "middleware"),
    ("server-action", "server_actions"),
    ("redirect", "redirects"),
    ("header", "headers"),
]
SOURCE_ONLY_DISCOVERY_SURFACE_TYPES = {"middleware", "server-action", "redirect", "header"}
DISCOVERY_ANY_METHOD_MATCH_CANDIDATES = ["GET", "HEAD", "POST", "OPTIONS", "WS"]


def discovery_surface_source_refs(item: dict[str, Any]) -> list[str]:
    refs = []
    for key in ["repo_file", "file"]:
        value = str(item.get(key) or "")
        if value and value not in refs:
            refs.append(value)
    for value in item.get("source_refs", []) or []:
        ref = str(value)
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def discovery_surface_methods(surface_type: str, item: dict[str, Any]) -> list[str]:
    raw_methods = item.get("methods")
    if isinstance(raw_methods, list):
        methods = [str(method).upper() for method in raw_methods if str(method or "").strip()]
    else:
        method = str(item.get("method") or "").upper()
        methods = [method] if method else []
    if not methods and surface_type == "custom-server-entrypoint" and "websocket" in str(item.get("kind") or ""):
        methods = ["WS"]
    if not methods and surface_type in {"rewrite", "redirect", "header"}:
        methods = ["ANY"]
    return sorted(dict.fromkeys(methods))


def discovery_surface_path_candidates(item: dict[str, Any]) -> list[str]:
    candidates = []

    def add(value: Any) -> None:
        text = str(value or "")
        if text.startswith("/") and text not in candidates:
            candidates.append(text)

    add(item.get("path"))
    match = item.get("match") or {}
    for key in ["paths", "path_patterns"]:
        for value in match.get(key, []) or []:
            add(value)
    if not candidates:
        for prefix in match.get("path_prefixes", []) or []:
            prefix_text = str(prefix or "")
            if prefix_text.startswith("/"):
                add(prefix_text.rstrip("/") + "/__inferforge_path__")
    add(item.get("source_path"))
    return candidates


def normalize_discovery_surface(surface_type: str, key: str, item: dict[str, Any], index: int) -> dict[str, Any]:
    raw_id = item.get("id") or item.get("cluster_id") or item.get("path") or item.get("file") or f"{key}-{index}"
    path = str(item.get("path") or item.get("source_path") or "")
    surface_id = f"{surface_type}:{safe_probe_id(str(raw_id))}:{index}"
    return {
        "id": surface_id,
        "type": surface_type,
        "inventory_key": key,
        "index": index,
        "cluster_id": item.get("cluster_id"),
        "path": path or None,
        "methods": discovery_surface_methods(surface_type, item),
        "kind": item.get("kind"),
        "strategy_set": item.get("strategy_set"),
        "source_refs": discovery_surface_source_refs(item),
        "match": json_clone(item.get("match") or {}),
        "line_patterns": json_clone(item.get("line_patterns") or {}),
        "route_policy": json_clone(item.get("route_policy") or {}),
        "action_names": list(item.get("action_names") or []),
        "safety": item.get("safety"),
        "path_candidates": discovery_surface_path_candidates(item),
    }


def normalize_discovery_surfaces(route_inventory: dict[str, Any]) -> list[dict[str, Any]]:
    surfaces = []
    for surface_type, key in DISCOVERY_SURFACE_SOURCES:
        for index, item in enumerate(route_inventory.get(key, []) or []):
            if isinstance(item, dict):
                surfaces.append(normalize_discovery_surface(surface_type, key, item, index))
    return surfaces


def discovery_surface_match_methods(surface: dict[str, Any]) -> list[str]:
    methods = list(surface.get("methods") or [])
    if not methods or "ANY" in methods:
        return DISCOVERY_ANY_METHOD_MATCH_CANDIDATES
    return methods


def discovery_surface_matches_path(surface: dict[str, Any], method: str, path: str) -> bool:
    normalized_method = str(method or "").upper()
    surface_methods = {str(item).upper() for item in surface.get("methods", []) or []}
    if surface_methods and "ANY" not in surface_methods and normalized_method not in surface_methods:
        return False
    normalized_path = str(path or "").split("?", 1)[0]
    if not normalized_path.startswith("/"):
        return False

    match = surface.get("match") or {}
    paths = [str(item) for item in match.get("paths", []) or []]
    path_patterns = [str(item) for item in match.get("path_patterns", []) or []]
    path_prefixes = [str(item) for item in match.get("path_prefixes", []) or []]
    if not (paths or path_patterns or path_prefixes):
        candidate_path = str(surface.get("path") or "")
        if candidate_path:
            path_patterns = [candidate_path] if "{" in candidate_path else []
            paths = [] if "{" in candidate_path else [candidate_path]

    if normalized_path in paths:
        return True
    if any(normalized_path.startswith(prefix) for prefix in path_prefixes):
        return True
    return any(path_pattern_matches(pattern, normalized_path) for pattern in path_patterns if pattern)


def discovery_cluster_ids_for_surface(surface: dict[str, Any], clusters: dict[str, Any]) -> list[str]:
    cluster_ids: list[str] = []
    for cluster in clusters.get("clusters", []) or []:
        cluster_id = str(cluster.get("id") or "")
        if not cluster_id:
            continue
        matched = False
        for method in discovery_surface_match_methods(surface):
            for path in surface.get("path_candidates", []) or []:
                if cluster_matches_endpoint(cluster, method, path):
                    matched = True
                    break
            if matched:
                break
        if matched and cluster_id not in cluster_ids:
            cluster_ids.append(cluster_id)
    return sorted(cluster_ids)


def discovery_active_observations_for_surface(surface: dict[str, Any], active_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations = []
    for item in active_plan:
        method = str(item.get("method") or "").upper()
        path = str(item.get("path") or "")
        if not method or not path:
            continue
        if not discovery_surface_matches_path(surface, method, path):
            continue
        observations.append(
            {
                "id": item.get("id"),
                "method": method,
                "path": path,
                "cluster": item.get("cluster"),
                "expected_statuses": item.get("expected_statuses", []),
            }
        )
    return observations


def discovery_probe_results_for_surface(surface: dict[str, Any], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = []
    for row in results:
        method = str(row.get("method") or (row.get("request") or {}).get("method") or "").upper()
        path = str(row.get("path") or (row.get("request") or {}).get("path") or "")
        if not method or not path or not discovery_surface_matches_path(surface, method, path):
            continue
        matches.append(
            {
                "probe_id": row.get("probe_id"),
                "method": method,
                "path": path,
                "cluster": row.get("category"),
                "status": row.get("status"),
                "expected": row.get("expected"),
            }
        )
        if len(matches) >= 8:
            break
    return matches


def discovery_burp_history_for_surface(surface: dict[str, Any], burp_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches = []
    for row in burp_history:
        method = str(row.get("method") or "").upper()
        path = str(row.get("path") or (row.get("request_context") or {}).get("path") or "")
        if not method or not path or not discovery_surface_matches_path(surface, method, path):
            continue
        matches.append(
            {
                "method": method,
                "path": path,
                "status": row.get("status"),
                "source": row.get("source"),
            }
        )
        if len(matches) >= 8:
            break
    return matches


def discovery_review_candidates_for_surface(
    surface: dict[str, Any],
    review_candidates: list[dict[str, Any]],
    matching_cluster_ids: list[str],
) -> list[dict[str, Any]]:
    surface_cluster_id = str(surface.get("cluster_id") or "")
    candidates = []
    for candidate in review_candidates:
        candidate_cluster = str(candidate.get("cluster") or "")
        candidate_method = str(candidate.get("method") or "GET").upper()
        path_template = str(candidate.get("path_template") or "")
        cluster_matches = bool(
            candidate_cluster
            and (
                candidate_cluster == surface_cluster_id
                or candidate_cluster in matching_cluster_ids
            )
        )
        path_matches = bool(
            path_template
            and any(
                path_pattern_matches(path_template, path)
                or ("{" in path and path_pattern_matches(path, path_template))
                for path in surface.get("path_candidates", []) or []
            )
        )
        if not cluster_matches and not path_matches:
            continue
        if path_template and not any(
            path_pattern_matches(path_template, path)
            or ("{" in path and path_pattern_matches(path, path_template))
            for path in surface.get("path_candidates", []) or []
        ):
            continue
        candidates.append(
            {
                "id": candidate.get("id"),
                "type": candidate.get("type"),
                "status": candidate.get("status"),
                "method": candidate_method,
                "path_template": path_template or None,
                "cluster": candidate_cluster or None,
            }
        )
    return candidates


def source_only_discovery_next_action(surface: dict[str, Any]) -> str:
    surface_type = surface.get("type")
    if surface_type == "middleware":
        return "Review this Next.js middleware/proxy as cross-cutting source context; it is not executed by automated probes."
    if surface_type == "server-action":
        return "Review the Server Action source manually; InferForge does not invoke Server Actions or submit forms automatically."
    if surface_type in {"redirect", "header"}:
        return "Review this Next.js route policy as source context and confirm affected paths are represented by route clusters where relevant."
    return "Review this source-only discovery surface manually."


def build_discovery_coverage(
    target: str,
    profile: dict[str, Any],
    source_root: Path,
    route_inventory: dict[str, Any],
    clusters: dict[str, Any],
    *,
    route_inventory_path: Path | None = None,
    burp_history: list[dict[str, Any]] | None = None,
    probe_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    active_plan_error = None
    try:
        active_plan = build_burp_observation_plan(target, profile)
    except ValueError as error:
        active_plan = []
        active_plan_error = str(error)

    ws_profile = websocket_observation_config(profile)
    if ws_profile is not None:
        active_plan.append(
            {
                "id": ws_profile.get("id") or "burp_observe_ws_upgrade",
                "method": "WS",
                "path": ws_profile.get("path"),
                "expected_statuses": ws_profile.get("expected_statuses", [101]),
                "cluster": ws_profile.get("cluster") or "solana-rpc-ws",
            }
        )

    review_candidates = collect_review_observation_candidates(profile)
    surfaces = normalize_discovery_surfaces(route_inventory)
    rows = []
    status_counts: dict[str, int] = {}

    for surface in surfaces:
        matching_cluster_ids = discovery_cluster_ids_for_surface(surface, clusters)
        active_observations = discovery_active_observations_for_surface(surface, active_plan)
        probe_matches = discovery_probe_results_for_surface(surface, probe_results or [])
        burp_matches = discovery_burp_history_for_surface(surface, burp_history or [])
        review_matches = discovery_review_candidates_for_surface(surface, review_candidates, matching_cluster_ids)
        source_only = surface.get("type") in SOURCE_ONLY_DISCOVERY_SURFACE_TYPES

        if source_only:
            status = "source-only-context"
            next_action = source_only_discovery_next_action(surface)
        elif burp_matches:
            status = "covered-by-burp-history"
            next_action = "No static-discovery coverage action is required; keep Burp history fresh when this surface changes."
        elif probe_matches:
            status = "covered-by-probe-result"
            next_action = "No static-discovery coverage action is required; current probe results touch this surface."
        elif active_observations:
            status = "covered-by-active-observation"
            next_action = "Run burp-sync --observe when fresh Burp browser evidence is needed."
        elif review_matches:
            status = "review-gated"
            next_action = "Promote one approved concrete local read-only observation path before automated Burp observation."
        elif matching_cluster_ids:
            status = "covered-by-profile-cluster"
            next_action = "Profile routing covers this static surface; add a Burp observation or targeted probe when evidence is required."
        else:
            status = "uncovered"
            next_action = "Add this static surface to the target profile, or document why it is intentionally out of scope."

        increment_count(status_counts, status)
        row = {
            "id": surface["id"],
            "type": surface["type"],
            "path": surface.get("path"),
            "methods": surface.get("methods", []),
            "kind": surface.get("kind"),
            "strategy_set": surface.get("strategy_set"),
            "source_refs": surface.get("source_refs", []),
            "status": status,
            "profile_cluster_ids": matching_cluster_ids,
            "declared_cluster_id": surface.get("cluster_id"),
            "active_observation_count": len(active_observations),
            "active_observations": active_observations,
            "probe_result_count": len(probe_matches),
            "probe_results": probe_matches,
            "burp_history_count": len(burp_matches),
            "burp_history": burp_matches,
            "review_candidate_count": len(review_matches),
            "review_candidates": review_matches,
            "source_only": source_only,
            "next_action": next_action,
        }
        if surface.get("action_names"):
            row["action_names"] = surface["action_names"]
        if surface.get("route_policy"):
            row["route_policy"] = surface["route_policy"]
        rows.append(row)

    if active_plan_error:
        status = "profile-error"
    elif not surfaces:
        status = "no-surfaces"
    elif status_counts.get("uncovered"):
        status = "uncovered"
    elif status_counts.get("review-gated") or status_counts.get("source-only-context"):
        status = "needs-human-review"
    else:
        status = "covered"

    return {
        "generated_at": utc_now(),
        "status": status,
        "target": target,
        "source_root": repo_relative_or_absolute(source_root),
        "profile": profile_summary(profile),
        "summary": {
            "surfaces": len(rows),
            "status_counts": status_counts,
            "route_inventory_status": route_inventory.get("status"),
            "route_inventory_summary": route_inventory.get("summary", {}),
            "profile_clusters": len(clusters.get("clusters", []) or []),
            "review_candidates": len(review_candidates),
            "active_observations": len(active_plan),
            "active_plan_error": active_plan_error,
        },
        "surfaces": rows,
        "artifact_refs": {
            "route_inventory": repo_relative_or_absolute(route_inventory_path) if route_inventory_path else ROUTE_INVENTORY_ARTIFACT,
            "target_profile": TARGET_PROFILE_ARTIFACT,
            "endpoint_clusters": "endpoint-clusters.json",
            "burp_history": "burp-history-observations.jsonl",
            "probe_results": "probe-results.jsonl",
            "review_candidates": "review-observation-candidates.json",
            "reviewed_profile": "reviewed-profile.json",
        },
        "safety": "Read-only static-discovery coverage artifact. It reads local source/profile/artifacts only and does not send HTTP requests, invoke Server Actions, run Burp Scanner, sign wallets, or submit transactions.",
    }


def build_discovery_coverage_selftest_profile() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "discovery-coverage-selftest",
        "display_name": "Discovery Coverage Self-Test",
        "description": "Synthetic profile proving static discovery coverage classification.",
        "target_type": "self-test",
        "frameworks": ["Next.js App Router"],
        "default_target": "http://127.0.0.1:9998",
        "default_source_root": ".",
        "strategy_sets": [
            "nextjs-api-routes",
            "quote-transaction-decoder",
            "fixed-upstream-proxy",
        ],
        "safety": {
            "no_wallet_signing": True,
            "no_transaction_submission": True,
            "no_burp_scanner": True,
            "no_broad_fuzzing": True,
            "prefer_loopback_targets": True,
        },
        "probe_targets": {},
        "clusters": [
            {
                "id": "health",
                "method": "GET",
                "path": "/statusz",
                "kind": "health",
                "priority": "low",
                "strategy_set": "nextjs-api-routes",
                "match": {"methods": ["GET"], "paths": ["/statusz"]},
                "source_refs": ["selftest/app/statusz/route.ts"],
            },
            {
                "id": "quote",
                "method": "POST",
                "path": "/api/quote",
                "kind": "orchestration-proxy",
                "priority": "high",
                "strategy_set": "quote-transaction-decoder",
                "match": {"methods": ["POST"], "paths": ["/api/quote"]},
                "source_refs": ["selftest/app/api/quote/route.ts"],
            },
            {
                "id": "probed",
                "method": "GET",
                "path": "/api/probed",
                "kind": "api-route",
                "priority": "medium",
                "strategy_set": "nextjs-api-routes",
                "match": {"methods": ["GET"], "paths": ["/api/probed"]},
                "source_refs": ["selftest/app/api/probed/route.ts"],
            },
            {
                "id": "cluster-only",
                "method": "GET",
                "path": "/api/cluster-only",
                "kind": "api-route",
                "priority": "medium",
                "strategy_set": "nextjs-api-routes",
                "match": {"methods": ["GET"], "paths": ["/api/cluster-only"]},
                "source_refs": ["selftest/app/api/cluster-only/route.ts"],
            },
            {
                "id": "route-api-proxy-path",
                "method": "ANY",
                "path": "/api/proxy/{path*}",
                "kind": "rewrite-proxy",
                "priority": "medium",
                "strategy_set": "fixed-upstream-proxy",
                "match": {
                    "path_patterns": ["/api/proxy/{path*}"],
                    "path_prefixes": ["/api/proxy/"],
                },
                "source_refs": ["selftest/next.config.ts"],
            },
        ],
        "source_peeks": [],
        "burp_observation_plan": [
            {
                "id": "observe_statusz",
                "method": "GET",
                "path": "/statusz",
                "headers": {"User-Agent": "InferForge-SelfTest/0.1"},
                "expected_statuses": [200],
                "cluster": "health",
            },
            {
                "id": "observe_quote",
                "method": "POST",
                "path": "/api/quote",
                "headers": {
                    "User-Agent": "InferForge-SelfTest/0.1",
                    "Content-Type": "application/json",
                },
                "body": "{}",
                "expected_statuses": [400],
                "cluster": "quote",
            },
        ],
        "review_observation_candidates": [],
        "websocket_observation": None,
        "_profile_path": "self-test",
        "_profile_loaded_from": "self-test",
    }


def discovery_coverage_selftest_route(
    *,
    cluster_id: str,
    path: str,
    methods: list[str],
    kind: str = "api-route",
    strategy_set: str = "nextjs-api-routes",
) -> dict[str, Any]:
    return {
        "cluster_id": cluster_id,
        "path": path,
        "source_path": path,
        "methods": methods,
        "file": f"selftest/app{path}/route.ts",
        "repo_file": f"selftest/app{path}/route.ts",
        "router": "app",
        "dynamic_segments": route_dynamic_segments(path),
        "fixed_upstreams": [],
        "strategy_set": strategy_set,
        "kind": kind,
        "priority": "medium",
        "inference_reasons": ["self-test-route"],
        "match": route_match_for_path(path, methods),
        "next_config": {"path": path, "variants": [path]},
    }


def build_discovery_coverage_selftest_inventory(
    *,
    include_rewrite: bool = True,
    include_source_only: bool = True,
    include_uncovered: bool = True,
) -> dict[str, Any]:
    routes = [
        discovery_coverage_selftest_route(
            cluster_id="health",
            path="/statusz",
            methods=["GET"],
            kind="health",
        ),
        discovery_coverage_selftest_route(
            cluster_id="quote",
            path="/api/quote",
            methods=["POST"],
            kind="orchestration-proxy",
            strategy_set="quote-transaction-decoder",
        ),
        discovery_coverage_selftest_route(
            cluster_id="probed",
            path="/api/probed",
            methods=["GET"],
        ),
        discovery_coverage_selftest_route(
            cluster_id="cluster-only",
            path="/api/cluster-only",
            methods=["GET"],
        ),
    ]
    if include_uncovered:
        routes.append(
            discovery_coverage_selftest_route(
                cluster_id="unprofiled",
                path="/api/unprofiled",
                methods=["GET"],
            )
        )

    rewrites = []
    if include_rewrite:
        rewrites.append(
            {
                "cluster_id": "route-api-proxy-path",
                "path": "/api/proxy/{path*}",
                "source_path": "/api/proxy/{path*}",
                "methods": [],
                "file": "selftest/next.config.ts",
                "repo_file": "selftest/next.config.ts",
                "dynamic_segments": ["path*"],
                "fixed_upstreams": ["https://api.example.test"],
                "strategy_set": "fixed-upstream-proxy",
                "kind": "rewrite-proxy",
                "priority": "medium",
                "inference_reasons": ["self-test-rewrite"],
                "match": {
                    "path_patterns": ["/api/proxy/{path*}"],
                    "path_prefixes": ["/api/proxy/"],
                },
                "rewrite": {
                    "source": "/api/proxy/:path*",
                    "source_pattern": "/api/proxy/{path*}",
                    "destination_resolved": "https://api.example.test/:path*",
                },
                "next_config": {"path": "/api/proxy/{path*}", "variants": ["/api/proxy/{path*}"]},
            }
        )

    middleware_entries = []
    server_actions = []
    if include_source_only:
        middleware_entries.append(
            {
                "id": "middleware-selftest",
                "kind": "nextjs-middleware",
                "file": "selftest/middleware.ts",
                "repo_file": "selftest/middleware.ts",
                "matchers": [{"pattern": "/api/:path*", "variants": ["/api/{path*}"], "simple": True}],
                "match_strategy": "static-matchers",
                "inference_reasons": ["self-test-middleware"],
                "line_patterns": {"handler": "export function middleware"},
                "safety": "Static self-test middleware context only.",
            }
        )
        server_actions.append(
            {
                "id": "server_action_selftest",
                "kind": "nextjs-server-action",
                "file": "selftest/actions.ts",
                "repo_file": "selftest/actions.ts",
                "scope": "file-level-use-server",
                "action_names": ["mutateThing"],
                "action_count": 1,
                "use_server_directive_count": 1,
                "inference_reasons": ["self-test-server-action"],
                "line_patterns": {"use_server": "use server", "action:mutateThing": "mutateThing"},
                "safety": "Static self-test Server Action context only.",
            }
        )

    return {
        "generated_at": utc_now(),
        "status": "discovered",
        "source_root": "selftest",
        "app_root": "selftest/app",
        "app_roots": ["selftest/app"],
        "pages_api_roots": [],
        "summary": {
            "route_count": len(routes),
            "app_router_route_count": len(routes),
            "pages_router_api_route_count": 0,
            "rewrite_count": len(rewrites),
            "custom_server_entrypoint_count": 0,
            "middleware_count": len(middleware_entries),
            "server_action_file_count": len(server_actions),
            "server_action_export_count": sum(item["action_count"] for item in server_actions),
            "redirect_count": 0,
            "header_route_count": 0,
            "route_policy_count": 0,
            "entrypoint_count": len(routes) + len(rewrites),
            "surface_count": len(routes) + len(rewrites) + len(middleware_entries) + len(server_actions),
            "api_route_count": sum(1 for route in routes if str(route.get("path") or "").startswith("/api/")),
            "strategy_sets": sorted({item["strategy_set"] for item in [*routes, *rewrites]}),
        },
        "next_config": {},
        "routes": routes,
        "rewrites": rewrites,
        "custom_server_entrypoints": [],
        "middleware": middleware_entries,
        "server_actions": server_actions,
        "redirects": [],
        "headers": [],
        "safety": "Synthetic self-test inventory. No source files are read and no requests are sent.",
    }


def discovery_coverage_surface_statuses(coverage: dict[str, Any]) -> dict[str, str]:
    statuses = {}
    for surface in coverage.get("surfaces", []) or []:
        key = str(surface.get("path") or surface.get("id"))
        statuses[key] = str(surface.get("status") or "")
        if surface.get("type") and surface.get("path"):
            statuses[f"{surface.get('type')} {surface.get('path')}"] = str(surface.get("status") or "")
    return statuses


def build_discovery_coverage_selftest(source_root: Path) -> dict[str, Any]:
    target = "http://127.0.0.1:9998"
    profile = build_discovery_coverage_selftest_profile()
    clusters = build_clusters(profile, source_root)
    burp_history = [
        {
            "ts": utc_now(),
            "source": "self-test",
            "method": "GET",
            "path": "/statusz",
            "status": 200,
        }
    ]
    probe_results = [
        {
            "ts": utc_now(),
            "phase": "self-test",
            "probe_id": "selftest_probed",
            "method": "GET",
            "path": "/api/probed",
            "category": "probed",
            "status": 404,
            "expected": True,
        }
    ]

    full_inventory = build_discovery_coverage_selftest_inventory()
    full_coverage = build_discovery_coverage(
        target,
        profile,
        source_root,
        full_inventory,
        clusters,
        burp_history=burp_history,
        probe_results=probe_results,
    )
    review_inventory = build_discovery_coverage_selftest_inventory(include_uncovered=False)
    review_coverage = build_discovery_coverage(
        target,
        profile,
        source_root,
        review_inventory,
        clusters,
        burp_history=burp_history,
        probe_results=probe_results,
    )
    covered_inventory = build_discovery_coverage_selftest_inventory(
        include_rewrite=False,
        include_source_only=False,
        include_uncovered=False,
    )
    covered_coverage = build_discovery_coverage(
        target,
        profile,
        source_root,
        covered_inventory,
        clusters,
        burp_history=burp_history,
        probe_results=probe_results,
    )

    full_statuses = discovery_coverage_surface_statuses(full_coverage)
    assertions = [
        {
            "id": "full-status-uncovered",
            "passed": full_coverage.get("status") == "uncovered",
            "expected": "uncovered",
            "actual": full_coverage.get("status"),
        },
        {
            "id": "review-status-needs-human-review",
            "passed": review_coverage.get("status") == "needs-human-review",
            "expected": "needs-human-review",
            "actual": review_coverage.get("status"),
        },
        {
            "id": "covered-status-covered",
            "passed": covered_coverage.get("status") == "covered",
            "expected": "covered",
            "actual": covered_coverage.get("status"),
        },
        {
            "id": "burp-history-precedence",
            "passed": full_statuses.get("/statusz") == "covered-by-burp-history",
            "expected": "covered-by-burp-history",
            "actual": full_statuses.get("/statusz"),
        },
        {
            "id": "probe-result-coverage",
            "passed": full_statuses.get("/api/probed") == "covered-by-probe-result",
            "expected": "covered-by-probe-result",
            "actual": full_statuses.get("/api/probed"),
        },
        {
            "id": "active-observation-coverage",
            "passed": full_statuses.get("/api/quote") == "covered-by-active-observation",
            "expected": "covered-by-active-observation",
            "actual": full_statuses.get("/api/quote"),
        },
        {
            "id": "profile-cluster-coverage",
            "passed": full_statuses.get("/api/cluster-only") == "covered-by-profile-cluster",
            "expected": "covered-by-profile-cluster",
            "actual": full_statuses.get("/api/cluster-only"),
        },
        {
            "id": "rewrite-review-gate",
            "passed": full_statuses.get("/api/proxy/{path*}") == "review-gated",
            "expected": "review-gated",
            "actual": full_statuses.get("/api/proxy/{path*}"),
        },
        {
            "id": "uncovered-route-detected",
            "passed": full_statuses.get("/api/unprofiled") == "uncovered",
            "expected": "uncovered",
            "actual": full_statuses.get("/api/unprofiled"),
        },
        {
            "id": "source-only-context-detected",
            "passed": full_coverage.get("summary", {}).get("status_counts", {}).get("source-only-context") == 2,
            "expected": 2,
            "actual": full_coverage.get("summary", {}).get("status_counts", {}).get("source-only-context"),
        },
    ]
    passed = all(bool(item["passed"]) for item in assertions)
    return {
        "generated_at": utc_now(),
        "status": "passed" if passed else "failed",
        "profile": profile_summary(profile),
        "assertions": assertions,
        "cases": {
            "full": {
                "status": full_coverage.get("status"),
                "summary": full_coverage.get("summary", {}),
                "surface_statuses": full_statuses,
            },
            "review_only": {
                "status": review_coverage.get("status"),
                "summary": review_coverage.get("summary", {}),
            },
            "covered": {
                "status": covered_coverage.get("status"),
                "summary": covered_coverage.get("summary", {}),
            },
        },
        "safety": "Static discovery coverage self-test only. It does not read source files, send HTTP requests, call Burp, sign wallets, or submit transactions.",
    }


def source_peek_cluster_ids(source_peeks: dict[str, Any] | None) -> set[str]:
    observed: set[str] = set()
    for item in (source_peeks or {}).get("source_peeks", []):
        for cluster_id in item.get("cluster_ids", []):
            observed.add(str(cluster_id))
        endpoint = str(item.get("endpoint", ""))
        if "/api/quote" in endpoint:
            observed.add("quote")
        if "/api/rpc" in endpoint and endpoint.upper().startswith("WS"):
            observed.add("solana-rpc-ws")
        elif "/api/rpc" in endpoint:
            observed.add("solana-rpc-http")
        if "/api/orca/pools" in endpoint:
            observed.add("orca-pools")
        if "/health" in endpoint:
            observed.add("health")
    return observed


def build_blackbox_coverage(
    clusters: dict[str, Any],
    results: list[dict[str, Any]],
    burp_history: list[dict[str, Any]],
    source_peeks: dict[str, Any] | None,
    evidence_gaps: dict[str, Any] | None,
    burp_observation_run: dict[str, Any] | None,
    environment_readiness: dict[str, Any] | None,
    transaction_decoder_selftest: dict[str, Any] | None,
) -> dict[str, Any]:
    burp_cluster_ids = observed_cluster_ids(build_traffic_index([], burp_history), clusters)
    source_cluster_ids_seen = source_peek_cluster_ids(source_peeks)
    observation_clusters = set((burp_observation_run or {}).get("summary", {}).get("clusters", []))
    observation_unexpected = int((burp_observation_run or {}).get("summary", {}).get("unexpected", 0) or 0)
    gap_ids = [gap.get("id") for gap in (evidence_gaps or {}).get("gaps", [])]
    gap_ids_by_cluster: dict[str, list[str]] = {}
    for gap in (evidence_gaps or {}).get("gaps", []):
        gap_ids_by_cluster.setdefault(str(gap.get("cluster_id")), []).append(str(gap.get("id")))

    rows_by_cluster: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        rows_by_cluster.setdefault(str(row.get("category", "unknown")), []).append(row)

    cluster_coverage = []
    required_failures = []
    warnings = []
    external_blockers = []

    def make_check(check_id: str, status: str, evidence: Any, required: bool = True) -> dict[str, Any]:
        return {
            "id": check_id,
            "status": status,
            "required": required,
            "evidence": evidence,
        }

    for cluster in clusters.get("clusters", []):
        cluster_id = cluster["id"]
        cluster_kind = str(cluster.get("kind") or "")
        priority = cluster.get("priority")
        rows = rows_by_cluster.get(cluster_id, [])
        unexpected = [row for row in rows if not row.get("expected")]
        policy_fields = sorted(
            {
                str(row.get("policy_field"))
                for row in rows
                if row.get("policy_field") is not None
            }
        )
        active_probe_required = cluster_id != "health" and cluster_kind not in {"rewrite-proxy"}
        burp_observed = cluster_id in burp_cluster_ids
        safe_probe_status = (
            "failed"
            if unexpected
            else ("passed" if rows else ("failed" if active_probe_required else "not-applicable"))
        )
        policy_status = (
            "not-applicable"
            if cluster_id == "health" or not active_probe_required
            else ("passed" if policy_fields else "failed")
        )
        checks = [
            make_check(
                "burp-history-observed",
                "passed" if burp_observed else "warning",
                burp_observed,
                required=False,
            ),
            make_check(
                "safe-probes-executed",
                safe_probe_status,
                {"probe_count": len(rows), "unexpected_count": len(unexpected)},
                required=active_probe_required,
            ),
            make_check(
                "source-context-available",
                "passed" if cluster_id == "health" or cluster_id in source_cluster_ids_seen else "failed",
                cluster_id in source_cluster_ids_seen,
                required=cluster_id != "health",
            ),
            make_check(
                "policy-fields-covered",
                policy_status,
                policy_fields,
                required=active_probe_required,
            ),
            make_check(
                "burp-observe-flow-generated",
                "passed" if cluster_id in observation_clusters and observation_unexpected == 0 else "warning",
                {
                    "cluster_observed_in_burp_observation_run": cluster_id in observation_clusters,
                    "observation_unexpected": observation_unexpected,
                },
                required=False,
            ),
        ]

        cluster_gap_ids = gap_ids_by_cluster.get(cluster_id, [])
        if cluster_gap_ids == ["GAP-quote-transaction-corpus"]:
            checks.append(
                make_check(
                    "real-transaction-corpus",
                    "blocked",
                    "Waiting for a successful M0 quote transaction payload corpus.",
                    required=False,
                )
            )

        failed_required = [check for check in checks if check["required"] and check["status"] == "failed"]
        warning_checks = [check for check in checks if check["status"] in {"warning", "blocked"}]
        if failed_required:
            cluster_status = "failed"
            required_failures.extend([f"{cluster_id}:{check['id']}" for check in failed_required])
        elif warning_checks:
            cluster_status = "covered-with-open-items"
            warnings.extend([f"{cluster_id}:{check['id']}" for check in warning_checks])
        else:
            cluster_status = "covered"

        cluster_coverage.append(
            {
                "cluster_id": cluster_id,
                "kind": cluster.get("kind"),
                "priority": priority,
                "status": cluster_status,
                "checks": checks,
                "evidence_gaps": cluster_gap_ids,
            }
        )

    readiness_status = (environment_readiness or {}).get("status")
    if readiness_status and readiness_status != "ready":
        external_blockers.append(
            {
                "id": "environment-readiness",
                "status": readiness_status,
                "next_steps": (environment_readiness or {}).get("next_steps", []),
            }
        )
    if (transaction_decoder_selftest or {}).get("status") != "passed":
        required_failures.append("transaction-decoder-selftest")

    non_external_gaps = [gap_id for gap_id in gap_ids if gap_id != "GAP-quote-transaction-corpus"]
    if required_failures:
        status = "failed"
    elif non_external_gaps:
        status = "covered-with-evidence-gaps"
    elif external_blockers:
        status = "covered-with-external-blocker"
    else:
        status = "covered"

    return {
        "generated_at": utc_now(),
        "status": status,
        "methodology": "Burp-observed black-box surface plus safe probes, narrow source context, and finding/evidence gates.",
        "summary": {
            "cluster_count": len(cluster_coverage),
            "covered_clusters": sum(1 for item in cluster_coverage if item["status"] == "covered"),
            "covered_with_open_items": sum(1 for item in cluster_coverage if item["status"] == "covered-with-open-items"),
            "failed_clusters": sum(1 for item in cluster_coverage if item["status"] == "failed"),
            "evidence_gaps": gap_ids,
            "non_external_evidence_gaps": non_external_gaps,
            "required_failures": required_failures,
            "warnings": warnings,
        },
        "external_blockers": external_blockers,
        "cluster_coverage": cluster_coverage,
        "safety": "Coverage gate summarizes existing evidence only; it does not run active probes or submit transactions.",
    }


def source_peeks_for_cluster(source_peeks: dict[str, Any] | None, cluster_id: str) -> list[dict[str, Any]]:
    selected = []
    for item in (source_peeks or {}).get("source_peeks", []):
        endpoint = str(item.get("endpoint", ""))
        item_clusters = {str(item_cluster_id) for item_cluster_id in item.get("cluster_ids", [])}
        if "/api/quote" in endpoint:
            item_clusters.add("quote")
        if "/api/rpc" in endpoint and endpoint.upper().startswith("WS"):
            item_clusters.add("solana-rpc-ws")
        elif "/api/rpc" in endpoint:
            item_clusters.add("solana-rpc-http")
        if "/api/orca/pools" in endpoint:
            item_clusters.add("orca-pools")
        if "/health" in endpoint:
            item_clusters.add("health")
        if cluster_id in item_clusters:
            selected.append(
                {
                    "endpoint": item.get("endpoint"),
                    "files": item.get("files", []),
                    "relevant_lines": item.get("relevant_lines", {}),
                    "conclusion": item.get("conclusion"),
                }
            )
    return selected


def build_evidence_chain(
    clusters: dict[str, Any],
    results: list[dict[str, Any]],
    burp_history: list[dict[str, Any]],
    source_peeks: dict[str, Any] | None,
    finding_gate: dict[str, Any] | None,
    evidence_gaps: dict[str, Any] | None,
    blackbox_coverage: dict[str, Any] | None,
    environment_readiness: dict[str, Any] | None,
    transaction_intent: dict[str, Any] | None,
    transaction_decoder_selftest: dict[str, Any] | None,
) -> dict[str, Any]:
    rows_by_cluster: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        rows_by_cluster.setdefault(str(row.get("category", "unknown")), []).append(row)

    burp_by_cluster: dict[str, list[dict[str, Any]]] = {}
    for row in burp_history:
        for cluster_id in classify_endpoint(str(row.get("method", "")), str(row.get("path", "")), clusters):
            burp_by_cluster.setdefault(cluster_id, []).append(row)

    gaps_by_cluster: dict[str, list[dict[str, Any]]] = {}
    for gap in (evidence_gaps or {}).get("gaps", []):
        gaps_by_cluster.setdefault(str(gap.get("cluster_id")), []).append(gap)

    coverage_by_cluster = {
        item.get("cluster_id"): item
        for item in (blackbox_coverage or {}).get("cluster_coverage", [])
    }

    cluster_chains = []
    for cluster in clusters.get("clusters", []):
        cluster_id = cluster["id"]
        probe_rows = rows_by_cluster.get(cluster_id, [])
        burp_rows = burp_by_cluster.get(cluster_id, [])
        policy_fields = sorted(
            {
                str(row.get("policy_field"))
                for row in probe_rows
                if row.get("policy_field") is not None
            }
        )
        unexpected = [row for row in probe_rows if not row.get("expected")]
        cluster_chains.append(
            {
                "cluster_id": cluster_id,
                "kind": cluster.get("kind"),
                "priority": cluster.get("priority"),
                "coverage_status": (coverage_by_cluster.get(cluster_id) or {}).get("status"),
                "burp_observations": [
                    {
                        "method": row.get("method"),
                        "path": row.get("path"),
                        "host": row.get("host"),
                        "status": row.get("status"),
                        "source": row.get("source"),
                    }
                    for row in burp_rows
                ],
                "probe_evidence": {
                    "probe_count": len(probe_rows),
                    "unexpected_count": len(unexpected),
                    "policy_fields_covered": policy_fields,
                    "probes": [
                        {
                            "probe_id": row.get("probe_id"),
                            "method": row.get("method"),
                            "path": row.get("path"),
                            "status": row.get("status"),
                            "expected": row.get("expected"),
                            "policy_field": row.get("policy_field"),
                            "expectation": row.get("expectation_result"),
                        }
                        for row in probe_rows
                    ],
                },
                "source_context": source_peeks_for_cluster(source_peeks, cluster_id),
                "coverage_checks": (coverage_by_cluster.get(cluster_id) or {}).get("checks", []),
                "evidence_gaps": [
                    {
                        "id": gap.get("id"),
                        "priority": gap.get("priority"),
                        "title": gap.get("title"),
                        "safe_next_step": gap.get("safe_next_step"),
                    }
                    for gap in gaps_by_cluster.get(cluster_id, [])
                ],
            }
        )

    return {
        "generated_at": utc_now(),
        "status": (blackbox_coverage or {}).get("status", "unknown"),
        "purpose": "Machine-readable chain from Burp observations to probes, source context, gates, and remaining gaps.",
        "artifact_refs": {
            "burp_history": "burp-history-observations.jsonl",
            "probe_results": "probe-results.jsonl",
            "response_delta_analysis": "response-delta-analysis.json",
            "source_peeks": "source-peek-results.json",
            "source_peek_requests": "source-peek-requests.json",
            "finding_gate": "finding-gate.json",
            "evidence_gaps": "evidence-gaps.json",
            "blackbox_coverage": "blackbox-coverage.json",
            "environment_readiness": "environment-readiness.json",
            "transaction_intent": "transaction-intent.json",
            "transaction_decoder_selftest": "transaction-decoder-selftest.json",
        },
        "summary": {
            "clusters": len(cluster_chains),
            "burp_observations": len(burp_history),
            "probes": len(results),
            "unexpected_probes": sum(1 for row in results if not row.get("expected")),
            "finding_gates": len((finding_gate or {}).get("gates", [])),
            "evidence_gaps": [gap.get("id") for gap in (evidence_gaps or {}).get("gaps", [])],
            "readiness": (environment_readiness or {}).get("status"),
            "transaction_candidates": (transaction_intent or {}).get("candidates_seen", 0),
            "decoded_transactions": (transaction_intent or {}).get("decoded_transactions", 0),
            "transaction_decoder_selftest": (transaction_decoder_selftest or {}).get("status"),
        },
        "clusters": cluster_chains,
        "finding_gate": finding_gate or {"gates": []},
        "safety": "Evidence chain is an index over existing artifacts; it does not run probes, sign wallets, or submit transactions.",
    }


def cluster_docs_by_id(clusters: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(cluster.get("id")): cluster
        for cluster in (clusters or {}).get("clusters", [])
        if cluster.get("id")
    }


def source_refs_for_cluster(
    cluster_map: dict[str, dict[str, Any]],
    cluster_id: str,
    fallback: list[str],
    *,
    allow_fallback: bool,
) -> list[str]:
    if cluster_id in cluster_map:
        return list(cluster_map[cluster_id].get("source_refs", []))
    return list(fallback) if allow_fallback else []


def entrypoint_for_cluster(
    cluster_map: dict[str, dict[str, Any]],
    cluster_id: str,
    rows: list[dict[str, Any]],
    fallback: str,
) -> str:
    cluster = cluster_map.get(cluster_id, {})
    first = rows[0] if rows else {}
    method = str(cluster.get("method") or first.get("method") or "").upper()
    path = str(first.get("path") or cluster.get("path") or "")
    if method and path:
        return f"{method} {path}"
    return fallback


def is_generic_nextjs_route_result(row: dict[str, Any]) -> bool:
    return str(row.get("risk") or "").startswith("safe-generic-route-")


def build_suspicions(
    results: list[dict[str, Any]],
    clusters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    by_id = {row["probe_id"]: row for row in results}
    cluster_map = cluster_docs_by_id(clusters)
    allow_static_fallbacks = clusters is None
    suspicions = []

    malformed = [
        by_id.get("quote_malformed_json"),
        by_id.get("quote_text_plain_invalid_json"),
    ]
    if any(row and row.get("status") == 500 for row in malformed):
        suspicions.append(
            {
                "id": "SUSP-quote-json-001",
                "status": "hardening-note",
                "entrypoint": "POST /api/quote",
                "hypothesis": "Malformed request bodies are handled as server errors and leak parser details.",
                "blackbox_evidence": [
                    row for row in malformed if row and row.get("status") == 500
                ],
                "source_questions": [
                    "Does the route catch SyntaxError separately from upstream or runtime failures?"
                ],
                "source_refs": source_refs_for_cluster(
                    cluster_map,
                    "quote",
                    ["infrafi-web/src/app/api/quote/route.ts"],
                    allow_fallback=allow_static_fallbacks,
                ),
                "final_classification": "hardening-note",
            }
        )

    local_validation_misses = [
        row
        for row in results
        if row.get("category") == "quote"
        and row.get("policy_field")
        and not row.get("external")
        and row.get("probe_id") not in {"quote_malformed_json", "quote_text_plain_invalid_json"}
        and row.get("status") not in set(row.get("expected_statuses", []))
    ]
    if local_validation_misses:
        suspicions.append(
            {
                "id": "SUSP-quote-shape-validation-003",
                "status": "hardening-note",
                "entrypoint": "POST /api/quote",
                "hypothesis": "Some malformed or incomplete quote request shapes are not rejected by local validation.",
                "blackbox_evidence": local_validation_misses,
                "source_questions": [
                    "Is every required quote field type-checked before any upstream call or generic exception handler?"
                ],
                "source_refs": source_refs_for_cluster(
                    cluster_map,
                    "quote",
                    ["infrafi-web/src/app/api/quote/route.ts"],
                    allow_fallback=allow_static_fallbacks,
                ),
                "final_classification": "hardening-note",
            }
        )

    forwarded_policy_probes = [
        row
        for row in results
        if row.get("category") == "quote"
        and row.get("external")
        and row.get("policy_field")
        and row.get("status") not in {400, None}
    ]
    if forwarded_policy_probes:
        suspicions.append(
            {
                "id": "SUSP-quote-validation-002",
                "status": "hardening-note",
                "entrypoint": "POST /api/quote",
                "hypothesis": "Shape-valid but business-invalid quote bodies are forwarded to M0 before local policy validation.",
                "blackbox_evidence": forwarded_policy_probes,
                "source_questions": [
                    "Does the server validate chain, mint, wallet, amount, recipient, and maxNumQuotes before forwarding?"
                ],
                "source_refs": source_refs_for_cluster(
                    cluster_map,
                    "quote",
                    ["infrafi-web/src/app/api/quote/route.ts"],
                    allow_fallback=allow_static_fallbacks,
                ),
                "final_classification": "hardening-note",
            }
        )

    rpc_policy_misses = [
        row
        for row in results
        if row.get("category") == "solana-rpc-http"
        and row.get("policy_field")
        and not row.get("expected")
    ]
    if rpc_policy_misses:
        suspicions.append(
            {
                "id": "SUSP-rpc-policy-001",
                "status": "hardening-note",
                "entrypoint": "POST /api/rpc/solana/[cluster]",
                "hypothesis": "One or more Solana RPC proxy policy probes did not receive the expected local enforcement response.",
                "blackbox_evidence": rpc_policy_misses,
                "source_questions": [
                    "Are content type, request source, duplicate JSON keys, method allowlists, and mixed batches rejected before upstream forwarding?"
                ],
                "source_refs": source_refs_for_cluster(
                    cluster_map,
                    "solana-rpc-http",
                    ["infrafi-web/src/app/api/rpc/_shared.ts"],
                    allow_fallback=allow_static_fallbacks,
                ),
                "final_classification": "hardening-note",
            }
        )

    ws_policy_misses = [
        row
        for row in results
        if row.get("category") == "solana-rpc-ws"
        and row.get("policy_field")
        and not row.get("expected")
    ]
    if ws_policy_misses:
        suspicions.append(
            {
                "id": "SUSP-rpc-ws-policy-001",
                "status": "hardening-note",
                "entrypoint": "WS /api/rpc/solana/[cluster]",
                "hypothesis": "One or more Solana WebSocket RPC proxy policy probes did not receive the expected local close or handshake rejection.",
                "blackbox_evidence": ws_policy_misses,
                "source_questions": [
                    "Are origin, binary frame, malformed JSON, duplicate JSON keys, batch size, and method allowlist checks enforced before upstream forwarding?"
                ],
                "source_refs": source_refs_for_cluster(
                    cluster_map,
                    "solana-rpc-ws",
                    ["infrafi-web/server.js"],
                    allow_fallback=allow_static_fallbacks,
                ),
                "final_classification": "hardening-note",
            }
        )

    orca_policy_misses = [
        row
        for row in results
        if row.get("category") == "orca-pools"
        and row.get("policy_field")
        and not row.get("expected")
    ]
    if orca_policy_misses:
        suspicions.append(
            {
                "id": "SUSP-orca-policy-001",
                "status": "hardening-note",
                "entrypoint": "GET /api/orca/pools/[address]",
                "hypothesis": "One or more Orca fixed-upstream proxy probes did not receive the expected local address, method, or route guard response.",
                "blackbox_evidence": orca_policy_misses,
                "source_questions": [
                    "Are invalid base58 characters, address length boundaries, traversal markers, query injection attempts, and unsupported methods rejected before upstream forwarding?"
                ],
                "source_refs": source_refs_for_cluster(
                    cluster_map,
                    "orca-pools",
                    ["infrafi-web/src/app/api/orca/pools/[address]/route.ts"],
                    allow_fallback=allow_static_fallbacks,
                ),
                "final_classification": "hardening-note",
            }
        )

    generic_policy_misses_by_cluster: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        if not is_generic_nextjs_route_result(row):
            continue
        if not row.get("policy_field") or row.get("expected"):
            continue
        cluster_id = str(row.get("category") or "unknown-route")
        generic_policy_misses_by_cluster.setdefault(cluster_id, []).append(row)

    for cluster_id, rows in sorted(generic_policy_misses_by_cluster.items()):
        first = rows[0]
        path = str(first.get("path") or (cluster_map.get(cluster_id) or {}).get("path") or "unknown path")
        policy_fields = sorted({str(row.get("policy_field")) for row in rows if row.get("policy_field")})
        field_summary = ", ".join(policy_fields) if policy_fields else "route policy"
        source_refs = source_refs_for_cluster(
            cluster_map,
            cluster_id,
            [],
            allow_fallback=False,
        )
        suspicions.append(
            {
                "id": f"SUSP-nextjs-route-policy-{safe_probe_id(cluster_id)}",
                "status": "hardening-note",
                "entrypoint": entrypoint_for_cluster(
                    cluster_map,
                    cluster_id,
                    rows,
                    f"{str(first.get('method') or 'HTTP').upper()} {path}",
                ),
                "hypothesis": (
                    f"Generic Next.js route `{path}` did not match the expected low-risk "
                    f"{field_summary} probe baseline."
                ),
                "blackbox_evidence": rows,
                "source_questions": [
                    "Does the route intentionally expose the observed HEAD, OPTIONS, or GET behavior?",
                    "Are unsupported methods and CORS preflight responses enforced before handler logic or upstream calls?",
                ],
                "source_refs": source_refs,
                "observed_policy_fields": policy_fields,
                "final_classification": "hardening-note",
            }
        )

    return suspicions


def gate_index(finding_gate: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("suspicion_id")): item
        for item in (finding_gate or {}).get("gates", [])
    }


def build_findings(
    suspicions: list[dict[str, Any]],
    finding_gate: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    gates = gate_index(finding_gate)
    return [
        {
            "id": item["id"],
            "classification": item["final_classification"],
            "entrypoint": item["entrypoint"],
            "title": item["hypothesis"],
            "severity": item.get("severity", "needs-triage"),
            "source_refs": item["source_refs"],
            "gate_status": gates.get(item["id"], {}).get("gate_status"),
        }
        for item in suspicions
        if item["final_classification"] == "valid-finding"
        and gates.get(item["id"], {}).get("gate_status") == "passed"
    ]


def build_hardening_notes(
    suspicions: list[dict[str, Any]],
    finding_gate: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    gates = gate_index(finding_gate)
    notes = []
    for item in suspicions:
        gate = gates.get(item["id"], {})
        if item.get("final_classification") != "hardening-note":
            continue
        if gate.get("gate_status") != "accepted-hardening-note":
            continue
        notes.append(
            {
                "id": item["id"],
                "classification": item["final_classification"],
                "entrypoint": item["entrypoint"],
                "title": item["hypothesis"],
                "severity": "informational",
                "blackbox_evidence_count": len(item.get("blackbox_evidence", [])),
                "source_refs": item.get("source_refs", []),
                "gate_status": gate.get("gate_status"),
            }
        )
    return notes


def build_adjudication(
    suspicions: list[dict[str, Any]],
    finding_gate: dict[str, Any] | None,
    findings: list[dict[str, Any]],
    hardening_notes: list[dict[str, Any]],
    evidence_gaps: dict[str, Any] | None,
    blackbox_coverage: dict[str, Any] | None,
    environment_readiness: dict[str, Any] | None,
    evidence_chain: dict[str, Any] | None,
) -> dict[str, Any]:
    gates = (finding_gate or {}).get("gates", [])
    suspicion_by_id = {item.get("id"): item for item in suspicions}
    blocked_gates = [item for item in gates if item.get("gate_status") == "blocked"]
    manual_review_gates = [item for item in gates if item.get("gate_status") == "manual-review"]
    accepted_hardening = [
        item for item in gates if item.get("gate_status") == "accepted-hardening-note"
    ]
    external_blockers = list((blackbox_coverage or {}).get("external_blockers", []))
    readiness_status = (environment_readiness or {}).get("status")
    if readiness_status and readiness_status != "ready" and not external_blockers:
        external_blockers.append(
            {
                "id": "environment-readiness",
                "status": readiness_status,
                "next_steps": (environment_readiness or {}).get("next_steps", []),
            }
        )
    gap_ids = [gap.get("id") for gap in (evidence_gaps or {}).get("gaps", [])]

    decisions = []
    for gate in gates:
        suspicion = suspicion_by_id.get(gate.get("suspicion_id"), {})
        classification = gate.get("classification")
        gate_status = gate.get("gate_status")
        if classification == "valid-finding" and gate_status == "passed":
            bucket = "findings"
        elif classification == "hardening-note" and gate_status == "accepted-hardening-note":
            bucket = "hardening-notes"
        elif gate_status == "manual-review":
            bucket = "manual-review"
        elif gate_status == "blocked":
            bucket = "blocked"
        else:
            bucket = "not-reportable"
        decisions.append(
            {
                "suspicion_id": gate.get("suspicion_id"),
                "entrypoint": gate.get("entrypoint"),
                "classification": classification,
                "gate_status": gate_status,
                "report_bucket": bucket,
                "title": suspicion.get("hypothesis"),
                "checks": gate.get("checks", []),
            }
        )

    if findings:
        status = "reportable-findings"
    elif manual_review_gates:
        status = "manual-review"
    elif blocked_gates:
        status = "blocked"
    elif hardening_notes:
        status = "hardening-notes-only"
    elif external_blockers:
        status = "no-reportable-findings-with-external-blocker"
    else:
        status = "no-reportable-findings"

    return {
        "generated_at": utc_now(),
        "status": status,
        "policy": [
            "findings.json contains only valid-finding entries whose finding gate passed.",
            "hardening-notes.json contains accepted hardening-note entries and must not be reported as exploitable vulnerabilities.",
            "external blockers are not findings; they are prerequisites for collecting stronger evidence.",
        ],
        "summary": {
            "suspicions": len(suspicions),
            "reportable_findings": len(findings),
            "accepted_hardening_notes": len(hardening_notes),
            "manual_review": len(manual_review_gates),
            "blocked": len(blocked_gates),
            "evidence_gaps": gap_ids,
            "external_blockers": [item.get("id") for item in external_blockers],
            "coverage": (blackbox_coverage or {}).get("status"),
            "readiness": readiness_status,
            "evidence_chain": (evidence_chain or {}).get("status"),
        },
        "decisions": decisions,
        "external_blockers": external_blockers,
        "artifact_policy": {
            "findings": "findings.json",
            "hardening_notes": "hardening-notes.json",
            "finding_gate": "finding-gate.json",
            "evidence_chain": "evidence-chain.json",
            "coverage": "blackbox-coverage.json",
        },
        "safety": "Adjudication reads existing artifacts only; it does not run probes, sign wallets, or submit transactions.",
    }


def compact_probe_evidence(row: dict[str, Any]) -> dict[str, Any]:
    response_sample = row.get("body_sample")
    return {
        "evidence_id": f"PROBE-{row.get('probe_id', 'unknown')}",
        "artifact": "probe-results.jsonl",
        "ts": row.get("ts"),
        "phase": row.get("phase", "probe"),
        "probe_id": row.get("probe_id"),
        "label": row.get("label"),
        "method": row.get("method"),
        "path": row.get("path"),
        "request": row.get(
            "request",
            {
                "method": row.get("method"),
                "path": row.get("path"),
                "headers": {
                    key: value
                    for key, value in {
                        "Origin": row.get("origin"),
                        "Referer": row.get("referer"),
                    }.items()
                    if value
                },
                "body_sha256": None,
                "body_length": None,
                "body_sample": None,
            },
        ),
        "response": {
            "status": row.get("status"),
            "expected_statuses": row.get("expected_statuses", []),
            "expected": row.get("expected"),
            "expectation": row.get("expectation"),
            "expectation_result": row.get("expectation_result"),
            "duration_ms": row.get("duration_ms"),
            "error": row.get("error"),
            "body_sha256": row.get("body_sha256"),
            "body_length": row.get("body_length"),
            "body_truncated": row.get("body_truncated"),
            "body_sample": redact_text(response_sample, max_chars=500),
        },
        "classification": {
            "cluster_id": row.get("category"),
            "policy_field": row.get("policy_field"),
            "risk": row.get("risk"),
            "external": row.get("external"),
            "interesting": row.get("interesting"),
        },
        "retry": {
            "attempt_count": row.get("attempt_count", 1),
            "retry_reason": row.get("retry_reason"),
            "first_attempt": row.get("first_attempt"),
        },
    }


def compact_burp_evidence(row: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "evidence_id": f"BURP-{index:03d}",
        "artifact": "burp-history-observations.jsonl",
        "ts": row.get("ts"),
        "source": row.get("source"),
        "method": row.get("method"),
        "path": row.get("path"),
        "host": row.get("host"),
        "status": row.get("status"),
        "content_type": row.get("content_type"),
        "request_user_agent": row.get("request_user_agent"),
        "response_sample": redact_text(row.get("response_sample"), max_chars=500),
        "notes": row.get("notes"),
    }


def select_representative_probe_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def add(row: dict[str, Any]) -> None:
        probe_id = str(row.get("probe_id"))
        if probe_id in seen_ids or len(selected) >= limit:
            return
        seen_ids.add(probe_id)
        selected.append(row)

    for row in rows:
        if not row.get("expected") or row.get("interesting"):
            add(row)

    by_policy_field: dict[str, dict[str, Any]] = {}
    for row in rows:
        policy_field = row.get("policy_field")
        if policy_field and str(policy_field) not in by_policy_field:
            by_policy_field[str(policy_field)] = row
    for row in by_policy_field.values():
        add(row)

    for row in rows:
        add(row)
        if len(selected) >= limit:
            break
    return selected


def count_values(values: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = "null" if value is None else str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def response_shape_signature(row: dict[str, Any]) -> str:
    body_sample = row.get("body_sample")
    if body_sample is None:
        return "body:missing"
    text = str(body_sample)
    if not text:
        return "body:empty"
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        normalized = re.sub(r"\s+", " ", text.strip())[:80]
        return f"text:{normalized}"
    if isinstance(parsed, dict):
        keys = ",".join(sorted(str(key) for key in parsed.keys())[:16])
        return f"json-object:{keys}"
    if isinstance(parsed, list):
        item_types = ",".join(sorted({type(item).__name__ for item in parsed[:16]}))
        return f"json-array:{len(parsed)}:{item_types}"
    return f"json-{type(parsed).__name__}"


def body_length_range(rows: list[dict[str, Any]]) -> dict[str, int | None]:
    lengths = [
        int(row.get("body_length"))
        for row in rows
        if isinstance(row.get("body_length"), int)
    ]
    if not lengths:
        return {"min": None, "max": None}
    return {"min": min(lengths), "max": max(lengths)}


def response_delta_flags(rows: list[dict[str, Any]]) -> list[str]:
    statuses = {row.get("status") for row in rows}
    hashes = {row.get("body_sha256") for row in rows if row.get("body_sha256")}
    shapes = {response_shape_signature(row) for row in rows}
    expectation_results = {row.get("expectation_result") for row in rows if row.get("expectation_result")}
    flags = []
    if len(statuses) > 1:
        flags.append("status-variant")
    if len(hashes) > 1:
        flags.append("body-hash-variant")
    if len(shapes) > 1:
        flags.append("body-shape-variant")
    if len(expectation_results) > 1:
        flags.append("expectation-variant")
    if any(not row.get("expected") for row in rows):
        flags.append("unexpected-response")
    if any(row.get("interesting") for row in rows):
        flags.append("interesting-response")
    if any(row.get("error") and not row.get("expected") for row in rows):
        flags.append("transport-error")
    elif any(row.get("error") for row in rows):
        flags.append("expected-error-signal")
    if any(int(row.get("attempt_count") or 1) > 1 for row in rows):
        flags.append("retry-used")
    if any(row.get("body_truncated") for row in rows):
        flags.append("truncated-response")
    return flags


def response_delta_status(flags: list[str]) -> str:
    if any(flag in flags for flag in ["unexpected-response", "transport-error"]):
        return "review-needed"
    if any(flag in flags for flag in ["interesting-response", "retry-used", "truncated-response"]):
        return "interesting"
    if flags:
        return "expected-deltas"
    return "stable"


def summarize_response_delta_group(rows: list[dict[str, Any]], *, group_id: str) -> dict[str, Any]:
    flags = response_delta_flags(rows)
    policy_fields = sorted({str(row.get("policy_field")) for row in rows if row.get("policy_field")})
    risks = sorted({str(row.get("risk")) for row in rows if row.get("risk")})
    representatives = [
        compact_probe_evidence(row)
        for row in select_representative_probe_rows(rows, limit=5)
    ]
    return {
        "id": group_id,
        "status": response_delta_status(flags),
        "delta_flags": flags,
        "probe_count": len(rows),
        "unexpected_count": sum(1 for row in rows if not row.get("expected")),
        "interesting_count": sum(1 for row in rows if row.get("interesting")),
        "error_count": sum(1 for row in rows if row.get("error")),
        "retry_count": sum(1 for row in rows if int(row.get("attempt_count") or 1) > 1),
        "status_counts": count_values([row.get("status") for row in rows]),
        "expectation_result_counts": count_values([row.get("expectation_result") for row in rows if row.get("expectation_result")]),
        "body_hash_count": len({row.get("body_sha256") for row in rows if row.get("body_sha256")}),
        "body_shape_counts": count_values([response_shape_signature(row) for row in rows]),
        "body_length_range": body_length_range(rows),
        "policy_fields": policy_fields,
        "risks": risks,
        "representative_probe_evidence": representatives,
    }


def build_response_delta_analysis(
    clusters: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    cluster_docs = {
        str(cluster.get("id")): cluster
        for cluster in clusters.get("clusters", []) or []
        if cluster.get("id")
    }
    rows_by_cluster: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        rows_by_cluster.setdefault(str(row.get("category") or "unknown"), []).append(row)

    cluster_summaries = []
    total_endpoint_groups = 0
    review_needed = 0
    interesting = 0
    expected_delta_groups = 0
    stable_groups = 0

    for cluster_id in sorted(rows_by_cluster):
        rows = rows_by_cluster[cluster_id]
        endpoint_groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            endpoint_key = endpoint_request_key(str(row.get("method") or ""), str(row.get("path") or ""))
            endpoint_groups.setdefault(endpoint_key, []).append(row)
        endpoints = []
        for endpoint_key, endpoint_rows in sorted(endpoint_groups.items()):
            endpoint_summary = summarize_response_delta_group(
                endpoint_rows,
                group_id=f"DELTA-endpoint-{safe_probe_id(cluster_id + '-' + endpoint_key)}",
            )
            endpoint_summary["endpoint"] = endpoint_key
            endpoints.append(endpoint_summary)
            total_endpoint_groups += 1
            if endpoint_summary["status"] == "review-needed":
                review_needed += 1
            elif endpoint_summary["status"] == "interesting":
                interesting += 1
            elif endpoint_summary["status"] == "expected-deltas":
                expected_delta_groups += 1
            else:
                stable_groups += 1

        cluster_summary = summarize_response_delta_group(
            rows,
            group_id=f"DELTA-cluster-{safe_probe_id(cluster_id)}",
        )
        cluster_doc = cluster_docs.get(cluster_id, {})
        cluster_summary.update(
            {
                "cluster_id": cluster_id,
                "kind": cluster_doc.get("kind"),
                "priority": cluster_doc.get("priority"),
                "strategy_set": cluster_doc.get("strategy_set"),
                "endpoint_count": len(endpoints),
                "endpoints": endpoints,
            }
        )
        cluster_summaries.append(cluster_summary)

    unexpected_rows = sum(1 for row in results if not row.get("expected"))
    if not results:
        status = "no-probe-results"
    elif review_needed:
        status = "review-needed"
    elif interesting:
        status = "interesting-deltas"
    elif expected_delta_groups:
        status = "expected-deltas-indexed"
    else:
        status = "stable"

    return {
        "generated_at": utc_now(),
        "status": status,
        "methodology": "Read-only response delta analysis over probe-results.jsonl. Deltas are evidence indexes, not findings; unexpected or transport-error deltas still require the finding gate.",
        "summary": {
            "probe_rows": len(results),
            "clusters": len(cluster_summaries),
            "endpoint_groups": total_endpoint_groups,
            "unexpected_probe_rows": unexpected_rows,
            "review_needed_groups": review_needed,
            "interesting_groups": interesting,
            "expected_delta_groups": expected_delta_groups,
            "stable_groups": stable_groups,
        },
        "clusters": cluster_summaries,
        "artifact_refs": {
            "probe_results": "probe-results.jsonl",
            "endpoint_clusters": "endpoint-clusters.json",
            "evidence_appendix": "evidence-appendix.json",
            "suspicions": "suspicions.json",
        },
        "safety": "Read-only evidence analysis. It does not send HTTP requests, fuzz, sign wallets, submit transactions, or invoke Server Actions.",
    }


def build_evidence_appendix(
    clusters: dict[str, Any],
    results: list[dict[str, Any]],
    burp_history: list[dict[str, Any]],
    burp_observation_run: dict[str, Any] | None,
    blackbox_coverage: dict[str, Any] | None,
    evidence_chain: dict[str, Any] | None,
    adjudication: dict[str, Any] | None,
    environment_readiness: dict[str, Any] | None,
    *,
    examples_per_cluster: int = 8,
) -> dict[str, Any]:
    rows_by_cluster: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        rows_by_cluster.setdefault(str(row.get("category", "unknown")), []).append(row)

    burp_by_cluster: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, row in enumerate(burp_history, 1):
        for cluster_id in classify_endpoint(str(row.get("method", "")), str(row.get("path", "")), clusters):
            burp_by_cluster.setdefault(cluster_id, []).append((index, row))

    coverage_by_cluster = {
        item.get("cluster_id"): item
        for item in (blackbox_coverage or {}).get("cluster_coverage", [])
    }
    observation_clusters = set((burp_observation_run or {}).get("summary", {}).get("clusters", []))
    cluster_docs = []
    total_probe_examples = 0
    total_burp_examples = 0

    for cluster in clusters.get("clusters", []):
        cluster_id = cluster["id"]
        probe_rows = rows_by_cluster.get(cluster_id, [])
        selected_probes = select_representative_probe_rows(probe_rows, examples_per_cluster)
        burp_rows = burp_by_cluster.get(cluster_id, [])
        total_probe_examples += len(selected_probes)
        total_burp_examples += len(burp_rows)
        cluster_docs.append(
            {
                "cluster_id": cluster_id,
                "kind": cluster.get("kind"),
                "priority": cluster.get("priority"),
                "source_refs": cluster.get("source_refs", []),
                "coverage_status": (coverage_by_cluster.get(cluster_id) or {}).get("status"),
                "coverage_checks": (coverage_by_cluster.get(cluster_id) or {}).get("checks", []),
                "burp_observe_flow_generated": cluster_id in observation_clusters,
                "burp_evidence": [
                    compact_burp_evidence(row, index)
                    for index, row in burp_rows
                ],
                "probe_summary": {
                    "total": len(probe_rows),
                    "expected": sum(1 for row in probe_rows if row.get("expected")),
                    "unexpected": sum(1 for row in probe_rows if not row.get("expected")),
                    "policy_fields": sorted(
                        {
                            str(row.get("policy_field"))
                            for row in probe_rows
                            if row.get("policy_field") is not None
                        }
                    ),
                },
                "representative_probe_evidence": [
                    compact_probe_evidence(row)
                    for row in selected_probes
                ],
            }
        )

    external_blockers = (blackbox_coverage or {}).get("external_blockers", [])
    unexpected_probes = sum(1 for row in results if not row.get("expected"))
    if not results and not burp_history:
        status = "missing-evidence"
    elif unexpected_probes:
        status = "indexed-with-unexpected-probes"
    elif external_blockers:
        status = "indexed-with-external-blocker"
    else:
        status = "indexed"

    return {
        "generated_at": utc_now(),
        "status": status,
        "purpose": "Compact request/response evidence appendix for reproducing report claims without rerunning probes.",
        "summary": {
            "clusters": len(cluster_docs),
            "probe_rows": len(results),
            "representative_probe_examples": total_probe_examples,
            "burp_observations": len(burp_history),
            "burp_examples": total_burp_examples,
            "unexpected_probes": unexpected_probes,
            "coverage": (blackbox_coverage or {}).get("status"),
            "evidence_chain": (evidence_chain or {}).get("status"),
            "adjudication": (adjudication or {}).get("status"),
            "readiness": (environment_readiness or {}).get("status"),
            "external_blockers": [item.get("id") for item in external_blockers],
        },
        "artifact_refs": {
            "probe_results": "probe-results.jsonl",
            "response_delta_analysis": "response-delta-analysis.json",
            "burp_history": "burp-history-observations.jsonl",
            "burp_observation_run": "burp-observation-run.json",
            "coverage": "blackbox-coverage.json",
            "evidence_chain": "evidence-chain.json",
            "adjudication": "adjudication.json",
        },
        "redaction": {
            "headers": sorted(SENSITIVE_HEADER_NAMES),
            "text_patterns": "authorization bearer values and common api-key/token/secret/password/cookie assignments",
        },
        "clusters": cluster_docs,
        "safety": "Appendix indexes existing evidence only; it does not run probes, sign wallets, submit transactions, or enumerate upstream resources.",
    }


def curl_command_for_probe(target: str, evidence: dict[str, Any]) -> str | None:
    method = str(evidence.get("method") or "").upper()
    if not method or method == "WS":
        return None
    request = evidence.get("request", {})
    path = str(request.get("path") or evidence.get("path") or "/")
    url = target.rstrip("/") + path
    parts = ["curl", "-i", "-sS", "-X", method]
    for key, value in (request.get("headers") or {}).items():
        if value is None:
            continue
        parts.extend(["-H", f"{key}: {value}"])
    body_sample = request.get("body_sample")
    if body_sample is not None and not request.get("body_truncated"):
        parts.extend(["--data-raw", str(body_sample)])
    return " ".join(shlex.quote(part) for part in parts + [url])


def verification_command_prefix(clusters: dict[str, Any], artifact_dir: Path | None) -> str:
    parts = ["python3", "scripts/inferforge.py"]
    profile = clusters.get("profile") or {}
    profile_path = profile.get("profile_path")
    if profile_path and profile_path != "builtin-default":
        path = Path(str(profile_path))
        rendered = repo_relative_or_absolute(path) if path.is_absolute() else str(profile_path)
        parts.extend(["--profile", rendered])
    if artifact_dir is not None:
        parts.extend(["--artifact-dir", repo_relative_or_absolute(artifact_dir)])
    return " ".join(shlex.quote(part) for part in parts)


def verification_command(clusters: dict[str, Any], artifact_dir: Path | None, subcommand: str) -> str:
    return f"{verification_command_prefix(clusters, artifact_dir)} {subcommand}"


def verification_artifact_path(artifact_dir: Path | None, name: str) -> str:
    if artifact_dir is None:
        return f".greybox/{name}"
    return repo_relative_or_absolute(artifact_dir / name)


def normalize_manual_placeholder_command(command: str) -> str:
    return (
        command
        .replace("<real-wallet>", PLACEHOLDER_REAL_WALLET)
        .replace("<approved-pool-address>", PLACEHOLDER_APPROVED_POOL_ADDRESS)
        .replace("<approved-concrete-local-path>", PLACEHOLDER_APPROVED_CONCRETE_PATH)
    )


def classify_verification_command(command: str, *, source: str, item_status: str | None = None) -> dict[str, Any]:
    normalized = normalize_manual_placeholder_command(str(command))
    known_placeholders = [
        PLACEHOLDER_REAL_WALLET,
        PLACEHOLDER_APPROVED_POOL_ADDRESS,
        PLACEHOLDER_APPROVED_CONCRETE_PATH,
    ]
    placeholders = sorted(
        {
            token
            for token in [*known_placeholders, *COMMAND_PLACEHOLDER_RE.findall(normalized)]
            if token in normalized
        }
    )
    shell_angle_tokens = [
        token
        for token in ["<", ">"]
        if token in normalized
    ]
    unsafe_shell_operators = [
        token
        for token in ["&&", "||", ";", "`", "$(", "|", "\n", "\r"]
        if token in normalized
    ]
    issues = []
    if shell_angle_tokens:
        issues.append("shell-angle-placeholder-or-redirection")
    if unsafe_shell_operators:
        issues.append("shell-control-operator")

    if issues:
        classification = "unsafe-template"
        runnable = False
        requires_manual_input = True
    elif placeholders:
        classification = "manual-template"
        runnable = False
        requires_manual_input = True
    elif item_status in {"manual-review", "blocked", "blocked-external"}:
        classification = "review-gated"
        runnable = False
        requires_manual_input = item_status == "manual-review"
    else:
        classification = "ready"
        runnable = True
        requires_manual_input = False

    return {
        "command": normalized,
        "source": source,
        "classification": classification,
        "runnable": runnable,
        "requires_manual_input": requires_manual_input,
        "blocked_external": item_status == "blocked-external",
        "placeholders": placeholders,
        "issues": issues,
    }


def command_safety_summary(command_refs: list[dict[str, Any]]) -> dict[str, Any]:
    classification_counts: dict[str, int] = {}
    placeholder_counts: dict[str, int] = {}
    issue_counts: dict[str, int] = {}
    runnable_count = 0
    manual_count = 0
    blocked_external_count = 0
    for ref in command_refs:
        classification = str(ref.get("classification") or "unknown")
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
        if ref.get("runnable"):
            runnable_count += 1
        if ref.get("requires_manual_input"):
            manual_count += 1
        if ref.get("blocked_external"):
            blocked_external_count += 1
        for placeholder in ref.get("placeholders", []):
            placeholder_counts[str(placeholder)] = placeholder_counts.get(str(placeholder), 0) + 1
        for issue in ref.get("issues", []):
            issue_counts[str(issue)] = issue_counts.get(str(issue), 0) + 1
    return {
        "commands": len(command_refs),
        "runnable": runnable_count,
        "requires_manual_input": manual_count,
        "blocked_external": blocked_external_count,
        "classification_counts": classification_counts,
        "placeholder_counts": placeholder_counts,
        "issue_counts": issue_counts,
        "unsafe_template_count": classification_counts.get("unsafe-template", 0),
    }


def format_command_safety_summary(summary: dict[str, Any]) -> str:
    classification_counts = summary.get("classification_counts", {}) or {}
    placeholder_counts = summary.get("placeholder_counts", {}) or {}
    parts = [
        f"commands={summary.get('commands', 0)}",
        f"runnable={summary.get('runnable', 0)}",
        f"manual={summary.get('requires_manual_input', 0)}",
        f"external={summary.get('blocked_external', 0)}",
        f"unsafe={summary.get('unsafe_template_count', 0)}",
        f"classifications={json.dumps(classification_counts, sort_keys=True)}",
    ]
    if placeholder_counts:
        parts.append(f"placeholders={json.dumps(placeholder_counts, sort_keys=True)}")
    return " ".join(parts)


def verification_queue_exit_code(verification_queue: dict[str, Any]) -> int:
    if verification_queue.get("status") == "invalid-command-templates":
        return 2
    return 0


def build_command_safety_selftest() -> dict[str, Any]:
    cases = [
        {
            "id": "ready-command",
            "command": "python3 scripts/inferforge.py audit --no-ws",
            "item_status": "ready",
            "expected_classification": "ready",
            "expected_runnable": True,
            "expected_requires_manual_input": False,
            "expected_blocked_external": False,
        },
        {
            "id": "known-placeholder",
            "command": f"python3 scripts/inferforge.py collect-quote --wallet {PLACEHOLDER_REAL_WALLET}",
            "item_status": "ready",
            "expected_classification": "manual-template",
            "expected_placeholders": [PLACEHOLDER_REAL_WALLET],
        },
        {
            "id": "generic-placeholder",
            "command": "python3 scripts/inferforge.py collect --token REPLACE_WITH_API_TOKEN",
            "item_status": "ready",
            "expected_classification": "manual-template",
            "expected_placeholders": ["REPLACE_WITH_API_TOKEN"],
        },
        {
            "id": "review-gated-command",
            "command": "python3 scripts/inferforge.py burp-sync --observe",
            "item_status": "manual-review",
            "expected_classification": "review-gated",
            "expected_runnable": False,
            "expected_requires_manual_input": True,
        },
        {
            "id": "external-blocked-command",
            "command": "python3 scripts/inferforge.py decode-transactions --input .greybox/transaction-payloads.json",
            "item_status": "blocked-external",
            "expected_classification": "review-gated",
            "expected_runnable": False,
            "expected_requires_manual_input": False,
            "expected_blocked_external": True,
        },
        {
            "id": "angle-placeholder-unsafe",
            "command": "python3 scripts/inferforge.py promote-observation-candidate --path <approved-path>",
            "item_status": "ready",
            "expected_classification": "unsafe-template",
            "expected_issues": ["shell-angle-placeholder-or-redirection"],
        },
        {
            "id": "control-operator-unsafe",
            "command": "python3 scripts/inferforge.py audit; rm -rf .greybox",
            "item_status": "ready",
            "expected_classification": "unsafe-template",
            "expected_issues": ["shell-control-operator"],
        },
        {
            "id": "pipe-operator-unsafe",
            "command": "python3 scripts/inferforge.py audit | tee report.log",
            "item_status": "ready",
            "expected_classification": "unsafe-template",
            "expected_issues": ["shell-control-operator"],
        },
        {
            "id": "newline-operator-unsafe",
            "command": "python3 scripts/inferforge.py audit\npython3 scripts/inferforge.py manifest",
            "item_status": "ready",
            "expected_classification": "unsafe-template",
            "expected_issues": ["shell-control-operator"],
        },
    ]

    results = []
    assertions = []
    for case in cases:
        result = classify_verification_command(
            str(case["command"]),
            source=f"command-safety-selftest:{case['id']}",
            item_status=str(case.get("item_status") or ""),
        )
        results.append({**case, "result": result})
        assertions.append(
            {
                "id": f"{case['id']}:classification",
                "passed": result.get("classification") == case.get("expected_classification"),
                "expected": case.get("expected_classification"),
                "actual": result.get("classification"),
            }
        )
        for key, result_key in [
            ("expected_runnable", "runnable"),
            ("expected_requires_manual_input", "requires_manual_input"),
            ("expected_blocked_external", "blocked_external"),
        ]:
            if key in case:
                assertions.append(
                    {
                        "id": f"{case['id']}:{result_key}",
                        "passed": result.get(result_key) == case.get(key),
                        "expected": case.get(key),
                        "actual": result.get(result_key),
                    }
                )
        for placeholder in case.get("expected_placeholders", []) or []:
            assertions.append(
                {
                    "id": f"{case['id']}:placeholder:{placeholder}",
                    "passed": placeholder in (result.get("placeholders", []) or []),
                    "expected": placeholder,
                    "actual": result.get("placeholders", []),
                }
            )
        for issue in case.get("expected_issues", []) or []:
            assertions.append(
                {
                    "id": f"{case['id']}:issue:{issue}",
                    "passed": issue in (result.get("issues", []) or []),
                    "expected": issue,
                    "actual": result.get("issues", []),
                }
            )

    summary = command_safety_summary([item["result"] for item in results])
    queue_items = [
        {
            "id": "READY",
            "status": "ready",
            "commands": ["python3 scripts/inferforge.py coverage"],
        },
        {
            "id": "MANUAL",
            "status": "manual-review",
            "commands": [
                f"python3 scripts/inferforge.py collect-quote --wallet {PLACEHOLDER_REAL_WALLET}",
                "python3 scripts/inferforge.py burp-sync --observe",
            ],
            "review_candidates": [
                {
                    "id": "candidate",
                    "command_templates": [
                        f"python3 scripts/inferforge.py promote-observation-candidate --path {PLACEHOLDER_APPROVED_CONCRETE_PATH}",
                        "python3 scripts/inferforge.py audit --include-external",
                    ],
                }
            ],
        },
        {
            "id": "UNSAFE",
            "status": "ready",
            "commands": ["python3 scripts/inferforge.py audit && python3 scripts/inferforge.py manifest"],
        },
        {
            "id": "EXTERNAL",
            "status": "blocked-external",
            "commands": ["python3 scripts/inferforge.py decode-transactions --input .greybox/transaction-payloads.json"],
        },
    ]
    queue_summary = annotate_verification_queue_commands(queue_items)
    queue_counts = queue_summary.get("classification_counts", {})
    queue_safety_text = format_command_safety_summary(queue_summary)
    exit_code_cases = [
        {
            "id": "exit-code-ready",
            "status": "ready",
            "expected": 0,
        },
        {
            "id": "exit-code-needs-human-review",
            "status": "needs-human-review",
            "expected": 0,
        },
        {
            "id": "exit-code-ready-with-external-blockers",
            "status": "ready-with-external-blockers",
            "expected": 0,
        },
        {
            "id": "exit-code-invalid-command-templates",
            "status": "invalid-command-templates",
            "expected": 2,
        },
    ]
    queue_assertions = [
        {
            "id": "queue-ready-count",
            "passed": queue_counts.get("ready") == 1,
            "expected": 1,
            "actual": queue_counts.get("ready"),
        },
        {
            "id": "queue-manual-template-count",
            "passed": queue_counts.get("manual-template") == 2,
            "expected": 2,
            "actual": queue_counts.get("manual-template"),
        },
        {
            "id": "queue-review-gated-count",
            "passed": queue_counts.get("review-gated") == 3,
            "expected": 3,
            "actual": queue_counts.get("review-gated"),
        },
        {
            "id": "queue-unsafe-template-count",
            "passed": queue_summary.get("unsafe_template_count") == 1,
            "expected": 1,
            "actual": queue_summary.get("unsafe_template_count"),
        },
        {
            "id": "queue-blocked-external-count",
            "passed": queue_summary.get("blocked_external") == 1,
            "expected": 1,
            "actual": queue_summary.get("blocked_external"),
        },
        {
            "id": "queue-requires-manual-input-count",
            "passed": queue_summary.get("requires_manual_input") == 5,
            "expected": 5,
            "actual": queue_summary.get("requires_manual_input"),
        },
        {
            "id": "queue-summary-text-is-actionable",
            "passed": (
                "commands=7" in queue_safety_text
                and "runnable=1" in queue_safety_text
                and "manual=5" in queue_safety_text
                and "external=1" in queue_safety_text
                and "unsafe=1" in queue_safety_text
                and f'"{PLACEHOLDER_APPROVED_CONCRETE_PATH}": 1' in queue_safety_text
                and f'"{PLACEHOLDER_REAL_WALLET}": 1' in queue_safety_text
            ),
            "expected": "summary text includes runnable/manual/external/unsafe counts and placeholders",
            "actual": queue_safety_text,
        },
    ]
    for case in exit_code_cases:
        actual = verification_queue_exit_code({"status": case["status"]})
        queue_assertions.append(
            {
                "id": case["id"],
                "passed": actual == case["expected"],
                "expected": case["expected"],
                "actual": actual,
            }
        )
    assertions.extend(queue_assertions)
    failed = [item for item in assertions if not item["passed"]]
    return {
        "generated_at": utc_now(),
        "status": "failed" if failed else "passed",
        "summary": {
            "cases": len(cases),
            "assertions": len(assertions),
            "failed": len(failed),
            "classification_counts": summary.get("classification_counts", {}),
            "placeholder_counts": summary.get("placeholder_counts", {}),
            "issue_counts": summary.get("issue_counts", {}),
            "queue_classification_counts": queue_counts,
            "queue_unsafe_template_count": queue_summary.get("unsafe_template_count"),
            "exit_code_cases": len(exit_code_cases),
        },
        "cases": results,
        "queue": {
            "summary": queue_summary,
            "summary_text": queue_safety_text,
            "items": queue_items,
            "exit_code_cases": exit_code_cases,
        },
        "assertions": assertions,
        "safety": "Synthetic command-safety self-test. It classifies inert strings only and executes no generated commands.",
    }


def annotate_verification_queue_commands(items: list[dict[str, Any]]) -> dict[str, Any]:
    command_refs: list[dict[str, Any]] = []
    for item in items:
        item_id = str(item.get("id") or "unknown")
        item_status = str(item.get("status") or "")
        item_command_refs = []
        for index, command in enumerate(item.get("commands", []), start=1):
            ref = classify_verification_command(
                str(command),
                source=f"{item_id}:commands[{index}]",
                item_status=item_status,
            )
            item_command_refs.append(ref)
            command_refs.append(ref)
        if item_command_refs:
            item["command_safety"] = {
                "summary": command_safety_summary(item_command_refs),
                "commands": item_command_refs,
            }

        for candidate in item.get("review_candidates", []) or []:
            candidate_id = str(candidate.get("id") or "candidate")
            candidate_refs = []
            for index, command in enumerate(candidate.get("command_templates", []), start=1):
                ref = classify_verification_command(
                    str(command),
                    source=f"{item_id}:review_candidates:{candidate_id}:command_templates[{index}]",
                    item_status=item_status,
                )
                candidate_refs.append(ref)
                command_refs.append(ref)
            if candidate_refs:
                candidate["command_safety"] = {
                    "summary": command_safety_summary(candidate_refs),
                    "commands": candidate_refs,
                }

    return command_safety_summary(command_refs)


def verification_command_for_profile(profile_path: str, artifact_dir: Path | None, subcommand: str) -> str:
    parts = ["python3", "scripts/inferforge.py", "--profile", profile_path]
    if artifact_dir is not None:
        parts.extend(["--artifact-dir", repo_relative_or_absolute(artifact_dir)])
    return f"{' '.join(shlex.quote(part) for part in parts)} {subcommand}"


def review_candidate_command_templates(
    candidate: dict[str, Any],
    clusters: dict[str, Any],
    artifact_dir: Path | None,
) -> list[str]:
    if candidate.get("type") != "burp-http-observation":
        return []
    candidate_id = str(candidate.get("id") or "")
    if not candidate_id:
        return []
    reviewed_profile = verification_artifact_path(artifact_dir, "reviewed-profile.json")
    return [
        cmd
        for cmd in [
            verification_command(
                clusters,
                artifact_dir,
                (
                    "promote-observation-candidate "
                    f"--candidate-id {shlex.quote(candidate_id)} "
                    f"--path {PLACEHOLDER_APPROVED_CONCRETE_PATH} "
                    f"--output {shlex.quote(reviewed_profile)} "
                    "--no-write"
                ),
            ),
            verification_command(
                clusters,
                artifact_dir,
                (
                    "promote-observation-candidate "
                    f"--candidate-id {shlex.quote(candidate_id)} "
                    f"--path {PLACEHOLDER_APPROVED_CONCRETE_PATH} "
                    f"--output {shlex.quote(reviewed_profile)}"
                ),
            ),
            verification_command_for_profile(
                reviewed_profile,
                artifact_dir,
                "burp-sync --observe --ws-upgrade --replace --count 80",
            ),
            verification_command_for_profile(
                reviewed_profile,
                artifact_dir,
                "audit --include-external --ws-resource-probes",
            ),
        ]
        if cmd
    ]


def promoted_observation_followup_commands(output_path: Path, artifact_dir: Path | None) -> list[str]:
    reviewed_profile = repo_relative_or_absolute(output_path)
    return [
        verification_command_for_profile(
            reviewed_profile,
            artifact_dir,
            "burp-sync --observe --ws-upgrade --replace --count 80",
        ),
        verification_command_for_profile(
            reviewed_profile,
            artifact_dir,
            "audit --include-external --ws-resource-probes",
        ),
    ]


def contextualize_review_candidates(
    candidates: list[dict[str, Any]],
    clusters: dict[str, Any],
    artifact_dir: Path | None,
) -> list[dict[str, Any]]:
    contextualized = []
    prefix = "python3 scripts/inferforge.py "
    for candidate in candidates:
        item = json_clone(candidate)
        promote_template = item.get("promote_to_burp_observation_plan")
        if isinstance(promote_template, dict) and isinstance(promote_template.get("path"), str):
            promote_template["path"] = normalize_manual_placeholder_command(promote_template["path"])
        raw_templates = item.get("command_templates", [])
        generated_templates = False
        if not raw_templates:
            raw_templates = review_candidate_command_templates(item, clusters, artifact_dir)
            generated_templates = True
        templates = []
        for command in raw_templates:
            command_text = normalize_manual_placeholder_command(str(command))
            if not generated_templates and command_text.startswith(prefix):
                templates.append(verification_command(clusters, artifact_dir, command_text[len(prefix):]))
            else:
                templates.append(command_text)
        if templates:
            item["command_templates"] = templates
        contextualized.append(item)
    return contextualized


def build_verification_queue(
    target: str,
    clusters: dict[str, Any],
    evidence_appendix: dict[str, Any] | None,
    evidence_gaps: dict[str, Any] | None,
    blackbox_coverage: dict[str, Any] | None,
    adjudication: dict[str, Any] | None,
    environment_readiness: dict[str, Any] | None,
    artifact_dir: Path | None = None,
    attack_strategy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    cmd = lambda subcommand: verification_command(clusters, artifact_dir, subcommand)

    def add_item(
        item_id: str,
        title: str,
        status: str,
        priority: str,
        reason: str,
        *,
        commands: list[str] | None = None,
        evidence_refs: list[str] | None = None,
        prerequisites: list[str] | None = None,
        safety: str = "No signing, no transaction submission, and no broad fuzzing.",
        extra: dict[str, Any] | None = None,
    ) -> None:
        item = {
            "id": item_id,
            "title": title,
            "status": status,
            "priority": priority,
            "reason": reason,
            "commands": commands or [],
            "evidence_refs": evidence_refs or [],
            "prerequisites": prerequisites or [],
            "safety": safety,
        }
        if extra:
            item.update(extra)
        items.append(item)

    add_item(
        "VERIFY-safe-audit-loop",
        "Rerun the bounded safe audit loop",
        "ready",
        "high",
        "Refreshes probes, source peeks, coverage, adjudication, and reports in one deterministic pass.",
        commands=[cmd("audit --include-external --ws-resource-probes")],
        evidence_refs=[
            "probe-results.jsonl",
            "blackbox-coverage.json",
            "evidence-chain.json",
            "evidence-appendix.json",
            "adjudication.json",
        ],
    )
    add_item(
        "VERIFY-reportability-gates",
        "Recompute reportability gates without probing",
        "ready",
        "high",
        "Verifies that findings and hardening notes are separated from raw observations.",
        commands=[
            cmd("gate"),
            cmd("adjudicate"),
        ],
        evidence_refs=["finding-gate.json", "adjudication.json", "findings.json", "hardening-notes.json"],
    )
    add_item(
        "VERIFY-evidence-indexes",
        "Refresh evidence indexes without probing",
        "ready",
        "medium",
        "Rebuilds the strategy status, machine-readable evidence chain, and compact request/response appendix from current artifacts.",
        commands=[
            cmd("attack-strategy"),
            cmd("response-deltas"),
            cmd("source-peek-requests"),
            cmd("evidence-chain"),
            cmd("evidence-appendix"),
            cmd("report"),
        ],
        evidence_refs=[
            "attack-strategy.json",
            "response-delta-analysis.json",
            "source-peek-requests.json",
            "evidence-chain.json",
            "evidence-appendix.json",
            "report.md",
            "index.html",
        ],
    )
    add_item(
        "VERIFY-burp-observation-coverage",
        "Refresh Burp observation coverage without probing",
        "ready",
        "medium",
        "Rebuilds the per-cluster view of Burp history coverage, generated observe flows, active observation paths, and review-only observation candidates.",
        commands=[cmd("burp-observation-coverage")],
        evidence_refs=[
            "burp-observation-coverage.json",
            "burp-history-observations.jsonl",
            "burp-observation-run.json",
            "evidence-gaps.json",
        ],
        safety="Read-only artifact refresh. Use burp-sync --observe separately when observation traffic is needed.",
    )

    attack_strategy_status = str((attack_strategy or {}).get("status") or "")
    attack_strategy_summary = (attack_strategy or {}).get("summary", {}) or {}
    uncovered_strategy_clusters = [
        str(item)
        for item in attack_strategy_summary.get("strategy_uncovered_clusters", []) or []
        if item
    ]
    if attack_strategy_status == "needs-strategy-review":
        extra: dict[str, Any] = {
            "attack_strategy_status": attack_strategy_status,
            "strategy_uncovered_clusters": uncovered_strategy_clusters,
            "strategy_coverage": [
                item
                for item in (attack_strategy or {}).get("strategy_coverage", []) or []
                if not item.get("strategy_ids") and not item.get("exempt")
            ],
        }
        if len(uncovered_strategy_clusters) == 1:
            extra["cluster_id"] = uncovered_strategy_clusters[0]
        add_item(
            "REVIEW-attack-strategy-coverage",
            "Review uncovered attack strategy coverage",
            "manual-review",
            "high",
            (
                "Attack strategy coverage is missing a specific strategy for: "
                + (", ".join(uncovered_strategy_clusters) or "one or more clusters")
            ),
            commands=[cmd("attack-strategy")],
            evidence_refs=[
                "attack-strategy.json",
                "endpoint-clusters.json",
                STRATEGY_REGISTRY_ARTIFACT,
                TARGET_PROFILE_ARTIFACT,
            ],
            prerequisites=[
                "Map each uncovered cluster to an existing specific strategy or add a bounded strategy before treating coverage as complete.",
                "Keep new probes low-volume and tied to observed or source-discovered endpoints.",
            ],
            safety="Strategy review only. Do not add broad crawling, destructive fuzzing, wallet signing, or transaction submission.",
            extra=extra,
        )
    elif attack_strategy_status == "needs-external-evidence":
        waiting_actions = waiting_attack_strategy_actions(attack_strategy)
        waiting_action_ids = {str(action.get("id") or "") for action in waiting_actions}
        commands = []
        if "NEXT-transaction-intent-corpus" in waiting_action_ids:
            transaction_payload_path = shlex.quote(
                verification_artifact_path(artifact_dir, "transaction-payloads.json")
            )
            commands.extend(
                [
                    cmd(f"collect-quote --direction buy --wallet {PLACEHOLDER_REAL_WALLET} --amount-in 1000000"),
                    cmd(f"decode-transactions --input {transaction_payload_path}"),
                ]
            )
        commands.append(cmd("audit --include-external --ws-resource-probes"))
        add_item(
            "RESOLVE-attack-strategy-external-evidence",
            "Resolve attack strategy external evidence",
            "blocked-external",
            "medium",
            "Attack strategy is waiting on external evidence before the reusable strategy loop is fully covered.",
            commands=commands,
            evidence_refs=[
                "attack-strategy.json",
                "evidence-gaps.json",
                "environment-readiness.json",
                "transaction-intent.json",
            ],
            prerequisites=[
                f"{action.get('id')}: {action.get('title')} ({action.get('status')})"
                for action in waiting_actions[:6]
            ]
            or ["Provide the external evidence requested by attack-strategy.json."],
            safety="External evidence collection only. Do not print secrets, sign wallets, submit transactions, or enumerate upstream resources.",
            extra={
                "attack_strategy_status": attack_strategy_status,
                "waiting_action_ids": sorted(waiting_action_ids),
            },
        )

    for cluster in (evidence_appendix or {}).get("clusters", []):
        cluster_id = str(cluster.get("cluster_id", "unknown"))
        replay_commands = []
        replay_refs = []
        for evidence in cluster.get("representative_probe_evidence", [])[:4]:
            command = curl_command_for_probe(target, evidence)
            if command:
                replay_commands.append(command)
            replay_refs.append(str(evidence.get("evidence_id")))
        if not replay_commands and cluster_id == "solana-rpc-ws":
            replay_commands.append(cmd("audit --ws-resource-probes"))
        add_item(
            f"REPLAY-{cluster_id}",
            f"Replay representative evidence for {cluster_id}",
            "ready" if replay_commands else "manual-review",
            str(cluster.get("priority") or "medium"),
            f"Cluster coverage is `{cluster.get('coverage_status')}` with {cluster.get('probe_summary', {}).get('total', 0)} probe rows.",
            commands=replay_commands,
            evidence_refs=replay_refs,
            safety="Representative replay only. Keep request volume low and stay within the configured target.",
            extra={"cluster_id": cluster_id},
        )

    for gap in (evidence_gaps or {}).get("gaps", []):
        gap_id = str(gap.get("id"))
        contextual_candidates = contextualize_review_candidates(
            gap.get("review_candidates") or [],
            clusters,
            artifact_dir,
        )
        candidate_commands = [
            command
            for candidate in contextual_candidates
            for command in candidate.get("command_templates", [])
        ]
        if gap_id == "GAP-quote-transaction-corpus":
            prerequisites = (environment_readiness or {}).get("next_steps", [])
            transaction_payload_path = shlex.quote(verification_artifact_path(artifact_dir, "transaction-payloads.json"))
            commands = [
                cmd(f"collect-quote --direction buy --wallet {PLACEHOLDER_REAL_WALLET} --amount-in 1000000"),
                cmd(f"decode-transactions --input {transaction_payload_path}"),
                cmd("audit --include-external --ws-resource-probes"),
            ]
            status = "blocked-external"
        elif gap_id == "GAP-orca-real-address-cache-baseline":
            prerequisites = [str(gap.get("safe_next_step"))]
            commands = [
                cmd(f"collect-orca-baseline --address {PLACEHOLDER_APPROVED_POOL_ADDRESS}"),
                cmd("audit --include-external --ws-resource-probes"),
            ]
            status = "manual-review"
        else:
            prerequisites = [str(gap.get("safe_next_step"))]
            commands = candidate_commands
            status = "manual-review"
        evidence_refs = ["evidence-gaps.json", "environment-readiness.json"]
        if any(candidate.get("type") == "server-action-source-review" for candidate in contextual_candidates):
            evidence_refs.append("source-peek-results.json")
        extra = {}
        if gap.get("cluster_id"):
            extra["cluster_id"] = gap.get("cluster_id")
        if contextual_candidates:
            extra["review_candidates"] = contextual_candidates
        add_item(
            f"RESOLVE-{gap_id}",
            str(gap.get("title") or gap_id),
            status,
            str(gap.get("priority") or "medium"),
            str(gap.get("reason") or gap.get("safe_next_step") or "Evidence gap requires follow-up."),
            commands=commands,
            evidence_refs=evidence_refs,
            prerequisites=prerequisites,
            safety=str(gap.get("safety_gate") or "Do not escalate without explicit evidence."),
            extra=extra,
        )

    for blocker in (adjudication or {}).get("external_blockers", []):
        add_item(
            f"BLOCKER-{blocker.get('id', 'external')}",
            f"External blocker: {blocker.get('id', 'external')}",
            "blocked-external",
            "high",
            f"Current status is `{blocker.get('status')}`.",
            evidence_refs=["adjudication.json", "environment-readiness.json"],
            prerequisites=blocker.get("next_steps", []),
            safety="Configuration follow-up only. Do not print secrets in artifacts or logs.",
        )

    gate_decisions = (adjudication or {}).get("decisions", [])
    for decision in gate_decisions:
        status = "ready"
        if decision.get("report_bucket") in {"manual-review", "blocked"}:
            status = str(decision.get("report_bucket"))
        add_item(
            f"VERIFY-{decision.get('suspicion_id', 'suspicion')}",
            f"Verify gated item {decision.get('suspicion_id', 'suspicion')}",
            status,
            "high",
            str(decision.get("title") or "Gated suspicion requires verification."),
            evidence_refs=["finding-gate.json", "adjudication.json"],
            safety="Do not report unless the finding gate passes and reproduction evidence is complete.",
        )

    status_counts: dict[str, int] = {}
    for item in items:
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1
    if status_counts.get("blocked") or status_counts.get("manual-review"):
        status = "needs-human-review"
    elif status_counts.get("blocked-external"):
        status = "ready-with-external-blockers"
    else:
        status = "ready"
    command_safety = annotate_verification_queue_commands(items)
    if command_safety.get("unsafe_template_count"):
        status = "invalid-command-templates"

    return {
        "generated_at": utc_now(),
        "status": status,
        "target": target,
        "summary": {
            "items": len(items),
            "status_counts": status_counts,
            "clusters": len(clusters.get("clusters", [])),
            "coverage": (blackbox_coverage or {}).get("status"),
            "adjudication": (adjudication or {}).get("status"),
            "readiness": (environment_readiness or {}).get("status"),
            "attack_strategy": (attack_strategy or {}).get("status"),
            "command_safety": command_safety,
        },
        "items": items,
        "artifact_refs": {
            "evidence_appendix": "evidence-appendix.json",
            "evidence_chain": "evidence-chain.json",
            "adjudication": "adjudication.json",
            "coverage": "blackbox-coverage.json",
            "readiness": "environment-readiness.json",
            "attack_strategy": "attack-strategy.json",
        },
        "safety": "Queue generation is read-only. Commands are bounded reproductions and must stay in target scope.",
    }


def write_reproduction_steps(artifact_dir: Path, verification_queue: dict[str, Any]) -> None:
    command_safety = (verification_queue.get("summary", {}) or {}).get("command_safety", {}) or {}
    lines = [
        "# InferForge Reproduction Steps",
        "",
        f"Generated: {utc_now()}",
        "",
        f"- Target: `{verification_queue.get('target')}`",
        f"- Queue status: `{verification_queue.get('status')}`",
        f"- Items: `{verification_queue.get('summary', {}).get('items', 0)}`",
        f"- Command safety: `{format_command_safety_summary(command_safety)}`",
        "",
        "## Safety",
        "",
        "- Keep Burp Proxy Intercept off for unattended automation.",
        "- Do not sign wallets or submit Solana transactions from these steps.",
        "- Keep replay volume low and stay within the configured target.",
        "- Replace REPLACE_WITH_* placeholders before running any manual-review command.",
        "",
        "## Queue",
        "",
    ]
    for item in verification_queue.get("items", []):
        lines.extend(
            [
                f"### {item.get('id')}",
                "",
                f"- Status: `{item.get('status')}`",
                f"- Priority: `{item.get('priority')}`",
                f"- Title: {item.get('title')}",
                f"- Reason: {item.get('reason')}",
            ]
        )
        prerequisites = item.get("prerequisites", [])
        if prerequisites:
            lines.append("- Prerequisites:")
            lines.extend(f"  - {entry}" for entry in prerequisites)
        commands = item.get("commands", [])
        if commands:
            command_summary = (item.get("command_safety", {}) or {}).get("summary", {})
            if command_summary:
                lines.append(f"- Command safety: `{format_command_safety_summary(command_summary)}`")
            lines.append("")
            lines.append("Commands:")
            lines.append("")
            lines.append("```bash")
            lines.extend(commands)
            lines.append("```")
        review_candidates = item.get("review_candidates", [])
        if review_candidates:
            lines.append("")
            lines.append("Review candidates:")
            for candidate in review_candidates:
                lines.append(f"- `{candidate.get('id')}` ({candidate.get('type')}, {candidate.get('status')})")
                if candidate.get("source_ref"):
                    lines.append(f"  - Source: `{candidate.get('source_ref')}`")
                if candidate.get("action_names"):
                    lines.append(f"  - Actions: `{', '.join(str(name) for name in candidate.get('action_names', []))}`")
                if candidate.get("line_refs"):
                    line_refs = [
                        f"{key}: {value}"
                        for key, value in list((candidate.get("line_refs") or {}).items())[:6]
                    ]
                    lines.append(f"  - Line refs: `{'; '.join(line_refs)}`")
                review_questions = candidate.get("review_questions", [])
                if review_questions:
                    lines.append("  - Review questions:")
                    lines.extend(f"    - {entry}" for entry in review_questions)
                if candidate.get("path_template"):
                    lines.append(f"  - Path template: `{candidate.get('path_template')}`")
                if candidate.get("example_path"):
                    lines.append(f"  - Example path: `{candidate.get('example_path')}`")
                if candidate.get("command_templates"):
                    command_summary = (candidate.get("command_safety", {}) or {}).get("summary", {})
                    if command_summary:
                        lines.append(f"  - Command safety: `{format_command_safety_summary(command_summary)}`")
                    lines.append("  - Command templates:")
                    for command in candidate.get("command_templates", []):
                        lines.append(f"    - `{command}`")
                approval_required = candidate.get("approval_required", [])
                if approval_required:
                    lines.append("  - Approval required:")
                    lines.extend(f"    - {entry}" for entry in approval_required)
        refs = item.get("evidence_refs", [])
        if refs:
            lines.append("")
            lines.append("Evidence refs: " + ", ".join(f"`{ref}`" for ref in refs))
        lines.extend(["", f"Safety: {item.get('safety')}", ""])
    (artifact_dir / "reproduction-steps.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def review_blocker_status_rank(status: str) -> int:
    return {
        "failed": 0,
        "needs-profile-update": 1,
        "needs-human-review": 2,
        "ready-with-external-blockers": 3,
        "ready": 4,
    }.get(status, 9)


def review_blocker_priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 9)


def review_blocker_group_key(blocker: dict[str, Any]) -> str:
    explicit_key = str(blocker.get("group_key") or "")
    if explicit_key:
        return explicit_key
    category = str(blocker.get("category") or "unknown")
    status = str(blocker.get("status") or "unknown")
    source_name = Path(str(blocker.get("source") or "")).name
    blocker_id = str(blocker.get("run_blocker_id") or blocker.get("id") or "")
    if source_name == "environment-readiness.json" and blocker_id.startswith("READINESS-"):
        return f"{category}:{status}:source:environment-readiness"
    cluster_id = str(blocker.get("cluster_id") or "")
    if cluster_id:
        return f"{category}:{status}:cluster:{cluster_id}"
    candidate_ids = sorted(
        str(candidate.get("id"))
        for candidate in blocker.get("review_candidates", []) or []
        if candidate.get("id")
    )
    if candidate_ids:
        return f"{category}:{status}:candidates:{'|'.join(candidate_ids)}"
    blocker_id = str(blocker.get("run_blocker_id") or blocker.get("id") or "")
    if blocker_id:
        return f"{category}:{status}:id:{blocker_id}"
    return f"{category}:{status}:title:{blocker.get('title') or 'blocker'}"


def sorted_unique_strings(values: list[Any]) -> list[str]:
    return sorted({str(value) for value in values if value not in {None, ""}})


def ordered_unique_strings(values: list[Any]) -> list[str]:
    rows = []
    seen: set[str] = set()
    for value in values:
        if value in {None, ""}:
            continue
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        rows.append(text)
    return rows


def inline_summary_text(value: Any, *, max_chars: int = 180) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def format_review_blocker_group_summary(group: dict[str, Any]) -> str:
    parts = [
        f"{group.get('id') or 'GROUP-unknown'}:",
        str(group.get("status") or "unknown"),
        f"count={group.get('count', 0)}",
        f"category={group.get('category') or 'unknown'}",
    ]
    if group.get("priority"):
        parts.append(f"priority={group.get('priority')}")
    if group.get("cluster_id"):
        parts.append(f"cluster={group.get('cluster_id')}")
    candidate_ids = [str(item) for item in group.get("review_candidate_ids", []) or []]
    if candidate_ids:
        suffix = "" if len(candidate_ids) <= 3 else f",+{len(candidate_ids) - 3}"
        parts.append(f"candidates={','.join(candidate_ids[:3])}{suffix}")
    title = inline_summary_text(group.get("title") or group.get("reason") or "")
    if title:
        parts.append(f"title={title}")
    next_action = inline_summary_text(group.get("next_action") or "")
    if next_action:
        parts.append(f"next={next_action}")
    return " ".join(parts)


def split_review_blocker_next_actions(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [
        item.strip()
        for item in text.split(";")
        if item.strip()
    ]


def review_blocker_group_followup_preview_lines(group: dict[str, Any], *, limit: int = 3) -> list[str]:
    status = str(group.get("status") or "")
    if status not in {"failed", "needs-profile-update", "needs-human-review", "ready-with-external-blockers"}:
        return []
    lines = []
    next_actions = split_review_blocker_next_actions(group.get("next_action"))
    for action in next_actions[:limit]:
        lines.append(f"  followup_next={inline_summary_text(action, max_chars=260)}")
    if len(next_actions) > limit:
        lines.append(f"  followup_next=... +{len(next_actions) - limit} more")

    artifact_dirs = sorted_unique_strings(group.get("artifact_dirs", []) or [])
    if artifact_dirs:
        suffix = "" if len(artifact_dirs) <= 4 else f",+{len(artifact_dirs) - 4}"
        lines.append(f"  artifact_dirs={','.join(artifact_dirs[:4])}{suffix}")

    sources = sorted_unique_strings(group.get("sources", []) or [])
    if sources:
        suffix = "" if len(sources) <= 4 else f",+{len(sources) - 4}"
        lines.append(f"  sources={','.join(sources[:4])}{suffix}")

    refs = sorted_unique_strings(group.get("artifact_refs", []) or [])
    if refs:
        suffix = "" if len(refs) <= 6 else f",+{len(refs) - 6}"
        lines.append(f"  evidence_refs={','.join(refs[:6])}{suffix}")

    source_counts = group.get("source_counts", {}) or {}
    if source_counts:
        rendered_counts = [
            f"{inline_summary_text(source, max_chars=100)}:{count}"
            for source, count in sorted(source_counts.items())[:4]
        ]
        suffix = "" if len(source_counts) <= 4 else f",+{len(source_counts) - 4}"
        lines.append(f"  source_counts={','.join(rendered_counts)}{suffix}")
    return lines


def top_review_blocker_group_summaries(review_blockers: dict[str, Any] | None, *, limit: int = 5) -> list[str]:
    groups = (review_blockers or {}).get("groups", []) or []
    return [format_review_blocker_group_summary(group) for group in groups[:limit]]


def review_blocker_group_command_templates(group: dict[str, Any]) -> list[str]:
    candidates = group.get("review_candidates", []) or []
    return ordered_unique_strings(
        [
            *(group.get("commands", []) or []),
            *[
                command
                for candidate in candidates
                for command in candidate.get("command_templates", []) or []
            ],
        ]
    )


def review_blocker_command_status(group_status: str) -> str | None:
    return {
        "needs-human-review": "manual-review",
        "needs-profile-update": "manual-review",
        "failed": "blocked",
        "ready-with-external-blockers": "blocked-external",
    }.get(group_status)


def review_blocker_group_command_safety(group: dict[str, Any]) -> dict[str, Any]:
    return command_safety_summary(review_blocker_group_command_refs(group))


def format_command_ref_label(ref: dict[str, Any]) -> str:
    parts = [f"[{ref.get('classification') or 'unknown'}]"]
    placeholders = ref.get("placeholders", []) or []
    if placeholders:
        parts.append("placeholders=" + ",".join(str(item) for item in placeholders))
    issues = ref.get("issues", []) or []
    if issues:
        parts.append("issues=" + ",".join(str(item) for item in issues))
    if ref.get("blocked_external"):
        parts.append("external-blocker")
    return " ".join(parts)


def review_blocker_group_command_refs(group: dict[str, Any]) -> list[dict[str, Any]]:
    commands = review_blocker_group_command_templates(group)
    item_status = review_blocker_command_status(str(group.get("status") or ""))
    return [
        classify_verification_command(
            command,
            source=f"{group.get('id') or 'GROUP-unknown'}:commands[{index}]",
            item_status=item_status,
        )
        for index, command in enumerate(commands, start=1)
    ]


def compact_review_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for field in ["id", "cluster", "type", "status", "method", "path_template", "example_path"]:
        if candidate.get(field):
            compact[field] = candidate.get(field)
    for field in ["approval_required", "fixed_upstreams", "source_refs"]:
        values = sorted_unique_strings(candidate.get(field, []) or [])
        if values:
            compact[field] = values
    command_templates = ordered_unique_strings(candidate.get("command_templates", []) or [])
    if command_templates:
        compact["command_templates"] = command_templates
    if candidate.get("promote_to_burp_observation_plan"):
        compact["promote_to_burp_observation_plan"] = candidate.get("promote_to_burp_observation_plan")
    return compact


def review_candidate_rewrite_summaries(candidate: dict[str, Any], *, limit: int = 3) -> list[str]:
    summaries: list[str] = []
    for rewrite in candidate.get("rewrites", []) or []:
        if not isinstance(rewrite, dict):
            continue
        source = rewrite.get("source") or rewrite.get("source_pattern") or rewrite.get("source_framework_pattern")
        destination = (
            rewrite.get("destination_resolved")
            or rewrite.get("destination")
            or rewrite.get("destination_template")
        )
        parts = []
        if source:
            parts.append(f"source={inline_summary_text(source, max_chars=120)}")
        if destination:
            parts.append(f"destination={inline_summary_text(destination, max_chars=160)}")
        if rewrite.get("phase"):
            parts.append(f"phase={inline_summary_text(rewrite.get('phase'), max_chars=60)}")
        if parts:
            summaries.append(" ".join(parts))
    if len(summaries) <= limit:
        return summaries
    return [*summaries[:limit], f"... +{len(summaries) - limit} more rewrites"]


def review_candidate_command_refs(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    commands = ordered_unique_strings(candidate.get("command_templates", []) or [])
    return [
        classify_verification_command(
            command,
            source=f"{candidate.get('id') or 'review-candidate'}:command_templates[{index}]",
            item_status="manual-review",
        )
        for index, command in enumerate(commands, start=1)
    ]


def format_review_candidate_cli_lines(candidate: dict[str, Any]) -> list[str]:
    compact = compact_review_candidate(candidate)
    lines = [
        (
            f"- {compact.get('id') or 'unknown'} "
            f"cluster={compact.get('cluster') or 'unknown'} "
            f"type={compact.get('type') or 'unknown'} "
            f"status={compact.get('status') or 'unknown'}"
        )
    ]
    for field in ["method", "path_template", "example_path"]:
        if compact.get(field):
            lines.append(f"  {field}={compact[field]}")
    for field in ["source_refs", "fixed_upstreams"]:
        values = compact.get(field, []) or []
        if values:
            suffix = "" if len(values) <= 4 else f",+{len(values) - 4}"
            lines.append(f"  {field}={','.join(str(value) for value in values[:4])}{suffix}")
    for rewrite_summary in review_candidate_rewrite_summaries(candidate):
        lines.append(f"  rewrite={rewrite_summary}")

    approval_required = ordered_unique_strings(candidate.get("approval_required", []) or [])
    if approval_required:
        lines.append("  approval_required:")
        for entry in approval_required:
            lines.append(f"    - {inline_summary_text(entry, max_chars=220)}")

    promote = compact.get("promote_to_burp_observation_plan")
    if isinstance(promote, dict):
        promote_parts = []
        for field in ["id", "cluster", "method", "path"]:
            if promote.get(field):
                promote_parts.append(f"{field}={inline_summary_text(promote.get(field), max_chars=160)}")
        expected_statuses = promote.get("expected_statuses")
        if isinstance(expected_statuses, list) and expected_statuses:
            promote_parts.append(
                "expected_statuses="
                + ",".join(str(status) for status in expected_statuses[:12])
                + (f",+{len(expected_statuses) - 12}" if len(expected_statuses) > 12 else "")
            )
        if promote_parts:
            lines.append("  promote_to_burp_observation_plan: " + " ".join(promote_parts))

    command_templates = compact.get("command_templates", []) or []
    if command_templates:
        command_refs = review_candidate_command_refs(compact)
        command_refs_by_command = {
            str(ref.get("command") or ""): ref
            for ref in command_refs
        }
        command_safety = command_safety_summary(command_refs)
        lines.append(f"  command_safety={format_command_safety_summary(command_safety)}")
        lines.append("  command_templates:")
        for command in command_templates[:4]:
            ref = command_refs_by_command.get(str(command))
            label = f"{format_command_ref_label(ref)} " if ref else ""
            lines.append(f"    - {label}{inline_summary_text(command, max_chars=500)}")
        if len(command_templates) > 4:
            lines.append(f"    - ... +{len(command_templates) - 4} more commands")
    return lines


def verification_queue_item_status_rank(status: str) -> int:
    return {
        "manual-review": 0,
        "blocked": 0,
        "blocked-external": 1,
        "ready": 2,
    }.get(status, 9)


def verification_queue_item_priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 9)


def format_verification_queue_item_summary(item: dict[str, Any]) -> str:
    parts = [
        f"{item.get('id') or 'ITEM-unknown'}:",
        str(item.get("status") or "unknown"),
        f"priority={item.get('priority') or 'unknown'}",
    ]
    if item.get("cluster_id"):
        parts.append(f"cluster={item.get('cluster_id')}")
    review_candidate_ids = [
        str(candidate.get("id"))
        for candidate in item.get("review_candidates", []) or []
        if isinstance(candidate, dict) and candidate.get("id")
    ]
    if review_candidate_ids:
        suffix = "" if len(review_candidate_ids) <= 3 else f",+{len(review_candidate_ids) - 3}"
        parts.append(f"candidates={','.join(review_candidate_ids[:3])}{suffix}")
    commands = item.get("commands", []) or []
    if commands:
        parts.append(f"commands={len(commands)}")
    command_safety = (item.get("command_safety", {}) or {}).get("summary", {}) or {}
    if command_safety:
        parts.append(
            "command_safety="
            f"runnable={command_safety.get('runnable', 0)},"
            f"manual={command_safety.get('requires_manual_input', 0)},"
            f"external={command_safety.get('blocked_external', 0)},"
            f"unsafe={command_safety.get('unsafe_template_count', 0)}"
        )
    title = inline_summary_text(item.get("title") or "", max_chars=120)
    if title:
        parts.append(f"title={title}")
    return " ".join(parts)


def top_verification_queue_item_summaries(
    verification_queue: dict[str, Any],
    *,
    limit: int = 8,
) -> list[str]:
    ranked_items = ranked_verification_queue_items(verification_queue)
    return [format_verification_queue_item_summary(item) for item in ranked_items[:limit]]


def ranked_verification_queue_items(verification_queue: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for _, item in sorted(
            enumerate(verification_queue.get("items", []) or []),
            key=lambda row: (
                verification_queue_item_status_rank(str(row[1].get("status") or "")),
                verification_queue_item_priority_rank(str(row[1].get("priority") or "")),
                row[0],
            ),
        )
    ]


def verification_queue_command_preview_lines(item: dict[str, Any], *, limit: int = 4) -> list[str]:
    command_refs = (item.get("command_safety", {}) or {}).get("commands", []) or []
    if not command_refs:
        return []
    lines = []
    for ref in command_refs[:limit]:
        command = inline_summary_text(ref.get("command"), max_chars=500)
        lines.append(f"    - {format_command_ref_label(ref)} {command}")
    if len(command_refs) > limit:
        lines.append(f"    - ... +{len(command_refs) - limit} more commands")
    return lines


def verification_queue_followup_preview_lines(item: dict[str, Any], *, limit: int = 3) -> list[str]:
    status = str(item.get("status") or "")
    if status not in {"manual-review", "blocked", "blocked-external"}:
        return []

    lines = []
    reason = inline_summary_text(item.get("reason") or "", max_chars=260)
    if reason:
        lines.append(f"    reason={reason}")

    prerequisites = [
        inline_summary_text(entry, max_chars=260)
        for entry in item.get("prerequisites", []) or []
        if str(entry or "").strip()
    ]
    for prerequisite in prerequisites[:limit]:
        lines.append(f"    prerequisite={prerequisite}")
    if len(prerequisites) > limit:
        lines.append(f"    prerequisite=... +{len(prerequisites) - limit} more")

    review_candidates = [
        candidate
        for candidate in item.get("review_candidates", []) or []
        if isinstance(candidate, dict)
    ]
    for candidate in review_candidates[:limit]:
        parts = [f"candidate={candidate.get('id') or 'candidate'}"]
        if candidate.get("type"):
            parts.append(f"type={candidate.get('type')}")
        if candidate.get("path_template"):
            parts.append(f"path_template={candidate.get('path_template')}")
        if candidate.get("source_refs"):
            parts.append(
                "source_refs="
                + ",".join(inline_summary_text(ref, max_chars=80) for ref in candidate.get("source_refs", [])[:3])
            )
        lines.append("    " + " ".join(parts))
    if len(review_candidates) > limit:
        lines.append(f"    candidate=... +{len(review_candidates) - limit} more")

    evidence_refs = [str(ref) for ref in item.get("evidence_refs", []) or [] if str(ref or "").strip()]
    if evidence_refs:
        suffix = "" if len(evidence_refs) <= 6 else f",+{len(evidence_refs) - 6}"
        lines.append(f"    evidence_refs={','.join(evidence_refs[:6])}{suffix}")

    safety = inline_summary_text(item.get("safety") or "", max_chars=260)
    if safety:
        lines.append(f"    safety={safety}")
    return lines


def merge_review_candidate_summary(existing: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    incoming = compact_review_candidate(candidate)
    for field in ["id", "cluster", "type", "status", "method", "path_template", "example_path"]:
        if not existing.get(field) and incoming.get(field):
            existing[field] = incoming[field]
    for field in ["approval_required", "fixed_upstreams", "source_refs"]:
        merged = sorted_unique_strings([*(existing.get(field, []) or []), *(incoming.get(field, []) or [])])
        if merged:
            existing[field] = merged
    command_templates = ordered_unique_strings(
        [*(existing.get("command_templates", []) or []), *(incoming.get("command_templates", []) or [])]
    )
    if command_templates:
        existing["command_templates"] = command_templates
    if not existing.get("promote_to_burp_observation_plan") and incoming.get("promote_to_burp_observation_plan"):
        existing["promote_to_burp_observation_plan"] = incoming["promote_to_burp_observation_plan"]
    return existing


def build_review_blocker_groups(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    review_candidate_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for blocker in blockers:
        key = review_blocker_group_key(blocker)
        group = grouped.get(key)
        if not group:
            group = {
                "id": f"GROUP-{safe_probe_id(key)}",
                "key": key,
                "status": str(blocker.get("status") or "unknown"),
                "category": str(blocker.get("category") or "unknown"),
                "priority": str(blocker.get("priority") or "medium"),
                "title": blocker.get("title"),
                "reason": blocker.get("reason"),
                "next_action": blocker.get("next_action"),
                "cluster_id": blocker.get("cluster_id"),
                "blocker_ids": [],
                "artifact_dirs": [],
                "sources": [],
                "source_review_blockers": [],
                "artifact_refs": [],
                "review_candidate_ids": [],
                "review_candidates": [],
                "commands": [],
                "source_counts": {},
            }
            grouped[key] = group
            review_candidate_maps[key] = {}
        else:
            status = str(blocker.get("status") or "unknown")
            if review_blocker_status_rank(status) < review_blocker_status_rank(str(group.get("status") or "")):
                group["status"] = status
            priority = str(blocker.get("priority") or "medium")
            if review_blocker_priority_rank(priority) < review_blocker_priority_rank(str(group.get("priority") or "")):
                group["priority"] = priority
            category = str(blocker.get("category") or "unknown")
            if group.get("category") != category:
                group["category"] = "mixed"
            if not group.get("cluster_id") and blocker.get("cluster_id"):
                group["cluster_id"] = blocker.get("cluster_id")

        group["blocker_ids"].append(str(blocker.get("id") or "blocker"))
        if blocker.get("artifact_dir"):
            group["artifact_dirs"].append(blocker.get("artifact_dir"))
        if blocker.get("source"):
            group["sources"].append(blocker.get("source"))
            increment_count(group["source_counts"], str(blocker.get("source")))
        if blocker.get("source_review_blockers"):
            group["source_review_blockers"].append(blocker.get("source_review_blockers"))
        group["artifact_refs"].extend(blocker.get("artifact_refs", []) or [])
        group["commands"].extend(blocker.get("commands", []) or [])
        for candidate in blocker.get("review_candidates", []) or []:
            if candidate.get("id"):
                candidate_id = str(candidate.get("id"))
                group["review_candidate_ids"].append(candidate_id)
                candidate_map = review_candidate_maps.setdefault(key, {})
                candidate_summary = candidate_map.setdefault(candidate_id, {"id": candidate_id})
                merge_review_candidate_summary(candidate_summary, candidate)

    groups = []
    for key, group in grouped.items():
        group["count"] = len(group["blocker_ids"])
        group["artifact_dirs"] = sorted_unique_strings(group["artifact_dirs"])
        group["sources"] = sorted_unique_strings(group["sources"])
        group["source_review_blockers"] = sorted_unique_strings(group["source_review_blockers"])
        group["artifact_refs"] = sorted_unique_strings(group["artifact_refs"])
        group["review_candidate_ids"] = sorted_unique_strings(group["review_candidate_ids"])
        group["review_candidates"] = sorted(
            review_candidate_maps.get(key, {}).values(),
            key=lambda item: str(item.get("id") or ""),
        )
        group["commands"] = ordered_unique_strings(
            [
                *group.get("commands", []),
                *[
                    command
                    for candidate in group["review_candidates"]
                    for command in candidate.get("command_templates", []) or []
                ],
            ]
        )
        command_refs = review_blocker_group_command_refs(group)
        group["command_safety"] = {
            "summary": command_safety_summary(command_refs),
            "commands": command_refs,
        }
        group["blocker_ids"] = sorted_unique_strings(group["blocker_ids"])
        groups.append(group)

    groups.sort(
        key=lambda item: (
            review_blocker_status_rank(str(item.get("status") or "")),
            review_blocker_priority_rank(str(item.get("priority") or "")),
            str(item.get("cluster_id") or ""),
            str(item.get("id") or ""),
        )
    )
    return groups


def build_review_blockers(
    *,
    target: str,
    profile: dict[str, Any] | None,
    artifact_dir: Path,
    discovery_coverage: dict[str, Any] | None = None,
    burp_observation_coverage: dict[str, Any] | None = None,
    verification_queue: dict[str, Any] | None = None,
    source_peek_requests: dict[str, Any] | None = None,
    environment_readiness: dict[str, Any] | None = None,
    artifact_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_blocker(
        *,
        blocker_id: str,
        source: str,
        category: str,
        status: str,
        title: str,
        reason: str,
        next_action: str | None = None,
        priority: str = "medium",
        cluster_id: str | None = None,
        artifact_refs: list[str] | None = None,
        commands: list[str] | None = None,
        review_candidates: list[dict[str, Any]] | None = None,
        evidence: dict[str, Any] | None = None,
        group_key: str | None = None,
    ) -> None:
        key = f"{source}:{blocker_id}"
        if key in seen:
            return
        seen.add(key)
        row: dict[str, Any] = {
            "id": blocker_id,
            "source": source,
            "category": category,
            "status": status,
            "priority": priority,
            "title": title,
            "reason": reason,
            "next_action": next_action,
            "cluster_id": cluster_id,
            "artifact_refs": artifact_refs or [],
            "commands": commands or [],
            "review_candidates": review_candidates or [],
        }
        if group_key:
            row["group_key"] = group_key
        if evidence:
            row["evidence"] = evidence
        blockers.append(row)

    for surface in (discovery_coverage or {}).get("surfaces", []) or []:
        surface_status = str(surface.get("status") or "")
        if surface_status not in {"review-gated", "source-only-context", "uncovered"}:
            continue
        category = "profile-update" if surface_status == "uncovered" else "human-review"
        status = "needs-profile-update" if surface_status == "uncovered" else "needs-human-review"
        add_blocker(
            blocker_id=f"DISCOVERY-{surface.get('id')}",
            source=DISCOVERY_COVERAGE_ARTIFACT,
            category=category,
            status=status,
            priority="high" if surface_status == "uncovered" else "medium",
            title=f"Static discovery surface {surface_status}: {surface.get('path') or surface.get('id')}",
            reason=f"Discovery coverage marked this `{surface.get('type')}` surface as `{surface_status}`.",
            next_action=surface.get("next_action"),
            cluster_id=surface.get("declared_cluster_id") or (surface.get("profile_cluster_ids") or [None])[0],
            artifact_refs=[DISCOVERY_COVERAGE_ARTIFACT, ROUTE_INVENTORY_ARTIFACT, TARGET_PROFILE_ARTIFACT],
            review_candidates=surface.get("review_candidates", []),
            evidence={
                "type": surface.get("type"),
                "path": surface.get("path"),
                "methods": surface.get("methods", []),
                "source_refs": surface.get("source_refs", []),
                "profile_cluster_ids": surface.get("profile_cluster_ids", []),
            },
        )

    for cluster in (burp_observation_coverage or {}).get("clusters", []) or []:
        cluster_status = str(cluster.get("status") or "")
        if cluster_status not in {
            "needs-reviewed-observation-promotion",
            "needs-manual-browser-flow",
            "observe-run-unexpected",
        }:
            continue
        add_blocker(
            blocker_id=f"BURP-{cluster.get('cluster_id')}-{cluster_status}",
            source="burp-observation-coverage.json",
            category="human-review",
            status="needs-human-review",
            priority=str(cluster.get("priority") or "medium"),
            title=f"Burp observation coverage requires review for {cluster.get('cluster_id')}",
            reason=f"Burp observation coverage status is `{cluster_status}`.",
            next_action=cluster.get("next_action"),
            cluster_id=cluster.get("cluster_id"),
            artifact_refs=["burp-observation-coverage.json", "burp-history-observations.jsonl", "burp-observation-run.json"],
            review_candidates=[
                {"id": candidate_id}
                for candidate_id in cluster.get("review_candidate_ids", []) or []
            ],
            evidence={
                "active_observation_count": cluster.get("active_observation_count"),
                "evidence_gaps": cluster.get("evidence_gaps", []),
            },
        )

    for item in (verification_queue or {}).get("items", []) or []:
        item_status = str(item.get("status") or "")
        if item_status not in {"manual-review", "blocked", "blocked-external"}:
            continue
        if item_status == "blocked-external":
            category = "external-blocker"
            status = "ready-with-external-blockers"
        elif item_status == "blocked":
            category = "blocked"
            status = "failed"
        else:
            category = "human-review"
            status = "needs-human-review"
        add_blocker(
            blocker_id=f"QUEUE-{item.get('id')}",
            source="verification-queue.json",
            category=category,
            status=status,
            priority=str(item.get("priority") or "medium"),
            title=str(item.get("title") or item.get("id")),
            reason=str(item.get("reason") or f"Verification queue item status is `{item_status}`."),
            next_action="Review prerequisites and replace any REPLACE_WITH_* placeholders before running queued commands.",
            cluster_id=item.get("cluster_id"),
            artifact_refs=item.get("evidence_refs", []) or ["verification-queue.json"],
            commands=item.get("commands", []),
            review_candidates=item.get("review_candidates", []),
            evidence={
                "queue_status": item_status,
                "prerequisites": item.get("prerequisites", []),
                "command_safety": item.get("command_safety", {}),
            },
        )

    command_safety = (verification_queue or {}).get("summary", {}).get("command_safety", {}) or {}
    if int(command_safety.get("unsafe_template_count") or 0):
        add_blocker(
            blocker_id="QUEUE-unsafe-command-templates",
            source="verification-queue.json",
            category="unsafe-template",
            status="failed",
            priority="high",
            title="Verification queue contains unsafe command templates",
            reason="One or more command templates contain shell-sensitive placeholder or control-operator syntax.",
            next_action="Fix the command template generator before running or sharing reproduction commands.",
            artifact_refs=["verification-queue.json", "reproduction-steps.md"],
            evidence={"command_safety": command_safety},
        )

    for request in (source_peek_requests or {}).get("requests", []) or []:
        request_status = str(request.get("status") or "")
        if request_status != "manual-review":
            continue
        cluster_ids = request.get("cluster_ids", []) or []
        cluster_id = str(cluster_ids[0]) if cluster_ids else None
        add_blocker(
            blocker_id=f"SOURCE-PEEK-{request.get('id')}",
            source="source-peek-requests.json",
            category="human-review",
            status="needs-human-review",
            priority="medium",
            title=f"Source peek request requires review: {request.get('entrypoint') or request.get('id')}",
            reason=str(request.get("reason") or "Source-peek request is marked manual-review."),
            next_action="Answer the source-review questions and refresh source-peek-requests/evidence artifacts.",
            cluster_id=cluster_id,
            artifact_refs=["source-peek-requests.json", request.get("answer_artifact") or "source-peek-results.json"],
            review_candidates=[
                {"id": candidate_id}
                for candidate_id in request.get("review_candidate_ids", []) or []
            ],
            evidence={
                "trigger": request.get("trigger"),
                "gap_id": request.get("gap_id"),
                "questions": request.get("questions", []),
                "source_refs": request.get("source_refs", []),
                "safety": request.get("safety"),
            },
        )

    for check in (environment_readiness or {}).get("checks", []) or []:
        check_status = str(check.get("status") or "")
        if check_status not in {"blocked", "failed"}:
            continue
        add_blocker(
            blocker_id=f"READINESS-{check.get('id')}",
            source="environment-readiness.json",
            category="external-blocker" if check_status == "blocked" else "environment-failure",
            status="ready-with-external-blockers" if check_status == "blocked" else "failed",
            priority="high",
            title=f"Environment readiness check {check.get('id')} is {check_status}",
            reason=f"Readiness check `{check.get('id')}` returned `{check_status}`.",
            next_action="; ".join(str(item) for item in (environment_readiness or {}).get("next_steps", [])[:3]) or None,
            artifact_refs=["environment-readiness.json"],
            evidence={"check": check},
            group_key=(
                f"{'external-blocker' if check_status == 'blocked' else 'environment-failure'}:"
                f"{'ready-with-external-blockers' if check_status == 'blocked' else 'failed'}:"
                "source:environment-readiness"
            ),
        )

    for directory in (artifact_health or {}).get("directories", []) or []:
        directory_status = str(directory.get("status") or "")
        if directory_status not in {"failed", "needs-human-review", "ready-with-external-blockers"}:
            continue
        add_blocker(
            blocker_id=f"HEALTH-{safe_probe_id(str(directory.get('artifact_dir') or 'artifact-dir'))}",
            source="artifact-health.json",
            category="artifact-health",
            status=directory_status,
            priority="high" if directory_status == "failed" else "medium",
            title=f"Artifact health for {directory.get('artifact_dir')} is {directory_status}",
            reason="Artifact health summarized a non-ready state for this artifact directory.",
            next_action="Inspect the directory checks and source status summaries.",
            artifact_refs=["artifact-health.json", MANIFEST_NAME],
            evidence={
                "artifact_dir": directory.get("artifact_dir"),
                "checks": directory.get("checks", []),
                "statuses": directory.get("statuses", {}),
            },
        )

    status_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for blocker in blockers:
        increment_count(status_counts, str(blocker.get("status") or "unknown"))
        increment_count(category_counts, str(blocker.get("category") or "unknown"))
        increment_count(source_counts, str(blocker.get("source") or "unknown"))

    if not blockers:
        status = "ready"
    elif status_counts.get("failed"):
        status = "failed"
    elif status_counts.get("needs-profile-update"):
        status = "needs-profile-update"
    elif status_counts.get("needs-human-review"):
        status = "needs-human-review"
    elif status_counts.get("ready-with-external-blockers"):
        status = "ready-with-external-blockers"
    else:
        status = sorted(status_counts, key=review_blocker_status_rank)[0]

    blockers.sort(
        key=lambda item: (
            review_blocker_status_rank(str(item.get("status") or "")),
            review_blocker_priority_rank(str(item.get("priority") or "")),
            str(item.get("id") or ""),
        )
    )
    groups = build_review_blocker_groups(blockers)
    group_status_counts: dict[str, int] = {}
    group_category_counts: dict[str, int] = {}
    for group in groups:
        increment_count(group_status_counts, str(group.get("status") or "unknown"))
        increment_count(group_category_counts, str(group.get("category") or "unknown"))

    return {
        "generated_at": utc_now(),
        "status": status,
        "target": target,
        "profile": profile_summary(profile),
        "artifact_dir": str(artifact_dir),
        "summary": {
            "blockers": len(blockers),
            "groups": len(groups),
            "status_counts": status_counts,
            "category_counts": category_counts,
            "group_status_counts": group_status_counts,
            "group_category_counts": group_category_counts,
            "source_counts": source_counts,
            "discovery_coverage": (discovery_coverage or {}).get("status"),
            "burp_observation_coverage": (burp_observation_coverage or {}).get("status"),
            "verification_queue": (verification_queue or {}).get("status"),
            "source_peek_requests": (source_peek_requests or {}).get("status"),
            "environment_readiness": (environment_readiness or {}).get("status"),
            "artifact_health": (artifact_health or {}).get("status"),
        },
        "groups": groups,
        "blockers": blockers,
        "artifact_refs": {
            "discovery_coverage": DISCOVERY_COVERAGE_ARTIFACT,
            "burp_observation_coverage": "burp-observation-coverage.json",
            "verification_queue": "verification-queue.json",
            "source_peek_requests": "source-peek-requests.json",
            "environment_readiness": "environment-readiness.json",
            "artifact_health": "artifact-health.json",
        },
        "safety": "Read-only review blocker summary. It does not send HTTP requests, invoke Burp, run Burp Scanner, sign wallets, or submit transactions.",
    }


def build_review_blockers_rollup(
    *,
    target: str,
    profile: dict[str, Any] | None,
    artifact_dir: Path,
    check_dirs: list[Path],
    artifact_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    runs = []
    missing = []
    status_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    run_status_counts: dict[str, int] = {}

    for check_dir in check_dirs:
        path = check_dir / REVIEW_BLOCKERS_ARTIFACT
        relative_dir = repo_relative_or_absolute(check_dir)
        if not path.exists():
            missing.append(relative_dir)
            increment_count(run_status_counts, "missing-review-blockers")
            runs.append(
                {
                    "artifact_dir": relative_dir,
                    "status": "missing-review-blockers",
                    "review_blockers": repo_relative_or_absolute(path),
                    "summary": {},
                }
            )
            continue
        doc = load_optional_json(path) or {}
        run_status = str(doc.get("status") or "unknown")
        increment_count(run_status_counts, run_status)
        runs.append(
            {
                "artifact_dir": relative_dir,
                "status": run_status,
                "review_blockers": repo_relative_or_absolute(path),
                "summary": doc.get("summary", {}),
            }
        )
        for blocker in doc.get("blockers", []) or []:
            row = json_clone(blocker)
            original_id = str(row.get("id") or "blocker")
            row["id"] = f"RUN-{safe_probe_id(relative_dir)}-{original_id}"
            row["run_blocker_id"] = original_id
            row["artifact_dir"] = relative_dir
            row["source_review_blockers"] = repo_relative_or_absolute(path)
            row["source"] = f"{relative_dir}/{row.get('source')}"
            row["artifact_refs"] = [
                f"{relative_dir}/{ref}" if not str(ref).startswith("/") else str(ref)
                for ref in row.get("artifact_refs", []) or []
            ]
            blockers.append(row)

    for blocker in blockers:
        increment_count(status_counts, str(blocker.get("status") or "unknown"))
        increment_count(category_counts, str(blocker.get("category") or "unknown"))
        increment_count(source_counts, str(blocker.get("artifact_dir") or "unknown"))

    if missing:
        status = "failed"
    elif not blockers:
        status = "ready"
    elif status_counts.get("failed"):
        status = "failed"
    elif status_counts.get("needs-profile-update"):
        status = "needs-profile-update"
    elif status_counts.get("needs-human-review"):
        status = "needs-human-review"
    elif status_counts.get("ready-with-external-blockers"):
        status = "ready-with-external-blockers"
    else:
        status = sorted(status_counts, key=review_blocker_status_rank)[0]

    blockers.sort(
        key=lambda item: (
            review_blocker_status_rank(str(item.get("status") or "")),
            review_blocker_priority_rank(str(item.get("priority") or "")),
            str(item.get("artifact_dir") or ""),
            str(item.get("run_blocker_id") or item.get("id") or ""),
        )
    )
    groups = build_review_blocker_groups(blockers)
    group_status_counts: dict[str, int] = {}
    group_category_counts: dict[str, int] = {}
    for group in groups:
        increment_count(group_status_counts, str(group.get("status") or "unknown"))
        increment_count(group_category_counts, str(group.get("category") or "unknown"))

    return {
        "generated_at": utc_now(),
        "status": status,
        "target": target,
        "profile": profile_summary(profile),
        "artifact_dir": str(artifact_dir),
        "mode": "rollup",
        "summary": {
            "blockers": len(blockers),
            "groups": len(groups),
            "runs": len(runs),
            "missing_review_blockers": missing,
            "status_counts": status_counts,
            "category_counts": category_counts,
            "group_status_counts": group_status_counts,
            "group_category_counts": group_category_counts,
            "source_counts": source_counts,
            "run_status_counts": run_status_counts,
            "artifact_health": (artifact_health or {}).get("status"),
        },
        "runs": runs,
        "groups": groups,
        "blockers": blockers,
        "artifact_refs": {
            "artifact_health": "artifact-health.json",
            "review_blockers": REVIEW_BLOCKERS_ARTIFACT,
        },
        "safety": "Read-only review blocker rollup. It reads child review-blockers artifacts only and does not send HTTP requests, invoke Burp, run Burp Scanner, sign wallets, or submit transactions.",
    }


def review_blocker_group_by_cluster(doc: dict[str, Any], cluster_id: str) -> dict[str, Any] | None:
    for group in doc.get("groups", []) or []:
        if group.get("cluster_id") == cluster_id:
            return group
    return None


def build_review_blockers_selftest() -> dict[str, Any]:
    target = "http://127.0.0.1:9997"
    profile = {
        "schema_version": 1,
        "name": "review-blockers-selftest",
        "display_name": "Review Blockers Self-Test",
        "clusters": [
            {
                "id": "route-api-proxy-path",
                "method": "GET",
                "path": "/api/proxy/{path*}",
                "kind": "fixed-upstream-proxy",
                "priority": "medium",
                "strategy_set": "fixed-upstream-proxy",
            },
            {
                "id": "quote",
                "method": "POST",
                "path": "/api/quote",
                "kind": "orchestration-proxy",
                "priority": "high",
                "strategy_set": "quote-transaction-decoder",
            },
        ],
    }
    review_candidate = {
        "id": "review_observe_route_api_proxy_path_approved_path",
        "type": "burp-http-observation",
        "status": "review-only",
        "method": "GET",
        "path_template": "/api/proxy/{path*}",
        "cluster": "route-api-proxy-path",
        "example_path": "/api/proxy/<approved-read-only-path>",
        "command_templates": [
            (
                "python3 scripts/inferforge.py --profile .greybox/discovered-profile.json "
                "--artifact-dir .greybox/regression-discovered promote-observation-candidate "
                "--candidate-id review_observe_route_api_proxy_path_approved_path "
                f"--path {PLACEHOLDER_APPROVED_CONCRETE_PATH} "
                "--output .greybox/regression-discovered/reviewed-profile.json"
            ),
            (
                "python3 scripts/inferforge.py --profile .greybox/regression-discovered/reviewed-profile.json "
                "--artifact-dir .greybox/regression-discovered burp-sync --observe --ws-upgrade --replace --count 80"
            ),
        ],
    }
    discovery_coverage = {
        "status": "needs-human-review",
        "surfaces": [
            {
                "id": "rewrite:route_api_proxy_path:0",
                "type": "rewrite",
                "path": "/api/proxy/{path*}",
                "methods": ["ANY"],
                "status": "review-gated",
                "declared_cluster_id": "route-api-proxy-path",
                "profile_cluster_ids": ["route-api-proxy-path"],
                "source_refs": ["next.config.ts"],
                "next_action": "Promote one approved concrete local read-only observation path.",
                "review_candidates": [review_candidate],
            }
        ],
    }
    burp_observation_coverage = {
        "status": "needs-human-review",
        "clusters": [
            {
                "cluster_id": "route-api-proxy-path",
                "status": "needs-reviewed-observation-promotion",
                "priority": "medium",
                "next_action": "Review one concrete local read-only path, then run burp-sync --observe.",
                "review_candidate_ids": [review_candidate["id"]],
                "active_observation_count": 0,
                "evidence_gaps": ["GAP-route-api-proxy-path-burp-observation"],
            }
        ],
    }
    external_queue = {
        "status": "ready-with-external-blockers",
        "summary": {"command_safety": {"unsafe_template_count": 0}},
        "items": [
            {
                "id": "RESOLVE-GAP-quote-transaction-corpus",
                "title": "No real quote transaction payload corpus",
                "status": "blocked-external",
                "priority": "high",
                "reason": "A successful quote response with a transaction candidate is required.",
                "cluster_id": "quote",
                "commands": [],
                "evidence_refs": ["evidence-gaps.json", "environment-readiness.json"],
                "prerequisites": ["Set M0 configuration."],
            }
        ],
    }
    discovered_queue = json_clone(external_queue)
    discovered_queue["status"] = "needs-human-review"
    discovered_queue["items"].extend(
        [
            {
                "id": "REPLAY-route-api-proxy-path",
                "title": "Replay representative evidence for route-api-proxy-path",
                "status": "manual-review",
                "priority": "medium",
                "reason": "Cluster coverage is `covered-with-open-items` with 0 probe rows.",
                "cluster_id": "route-api-proxy-path",
                "commands": [],
                "evidence_refs": ["verification-queue.json"],
                "prerequisites": [],
            },
            {
                "id": "RESOLVE-GAP-route-api-proxy-path-burp-observation",
                "title": "Browser-flow observation missing",
                "status": "manual-review",
                "priority": "low",
                "reason": "A reviewed concrete local observation path is required.",
                "cluster_id": "route-api-proxy-path",
                "commands": [],
                "evidence_refs": ["evidence-gaps.json", "environment-readiness.json"],
                "prerequisites": ["Approve one local read-only path."],
                "review_candidates": [review_candidate],
            },
        ]
    )
    environment_readiness = {
        "status": "waiting-for-external-configuration",
        "next_steps": ["Set a real M0_ORCHESTRATION_API_KEY and restart the target server."],
        "checks": [
            {
                "id": "m0-orchestration-key-configured",
                "status": "blocked",
                "evidence": {"status": "placeholder", "source": ".env.local"},
            },
            {
                "id": "m0-preview-wallet-configured",
                "status": "blocked",
                "evidence": {"status": "missing", "source": "environment"},
            },
        ],
    }
    source_peek_requests = {
        "status": "answered-with-manual-review",
        "requests": [
            {
                "id": "PEEK-gap-gap_route_api_proxy_path_burp_observation",
                "trigger": "evidence-gap",
                "status": "manual-review",
                "gap_id": "GAP-route-api-proxy-path-burp-observation",
                "entrypoint": "Browser-flow observation missing",
                "cluster_ids": ["route-api-proxy-path"],
                "reason": "A reviewed concrete local observation path is required.",
                "questions": ["Choose one known safe concrete path before automated Burp observation."],
                "source_refs": ["next.config.ts"],
                "review_candidate_ids": [review_candidate["id"]],
                "answer_artifact": "source-peek-results.json",
                "safety": "Manual source review only.",
            }
        ],
    }

    default_blockers = build_review_blockers(
        target=target,
        profile=profile,
        artifact_dir=Path(".greybox/selftest-default"),
        verification_queue=external_queue,
        environment_readiness=environment_readiness,
    )
    discovered_blockers = build_review_blockers(
        target=target,
        profile=profile,
        artifact_dir=Path(".greybox/selftest-discovered"),
        discovery_coverage=discovery_coverage,
        burp_observation_coverage=burp_observation_coverage,
        verification_queue=discovered_queue,
        source_peek_requests=source_peek_requests,
        environment_readiness=environment_readiness,
    )

    with tempfile.TemporaryDirectory(prefix="inferforge-review-blockers-selftest-") as temp_dir:
        root = Path(temp_dir)
        default_dir = root / "default"
        discovered_dir = root / "discovered"
        manifest_only_dir = root / "manifest-only"
        write_json(default_dir / REVIEW_BLOCKERS_ARTIFACT, default_blockers)
        write_json(discovered_dir / REVIEW_BLOCKERS_ARTIFACT, discovered_blockers)
        write_json(
            manifest_only_dir / MANIFEST_NAME,
            {
                "generated_at": utc_now(),
                "status": "complete",
                "summary": {"artifact_count": 0, "missing_required": []},
            },
        )
        rollup = build_review_blockers_rollup(
            target=target,
            profile=profile,
            artifact_dir=root,
            check_dirs=[default_dir, discovered_dir],
        )
        markdown_path = root / REVIEW_BLOCKERS_MARKDOWN_ARTIFACT
        write_review_blockers_markdown(markdown_path, rollup)
        markdown = read_text(markdown_path)
        profile_path = root / "profile.json"
        no_write_output_dir = root / "no-write-output"
        write_json(profile_path, profile)
        parser = build_parser()
        no_write_args = parser.parse_args(
            [
                "--profile",
                str(profile_path),
                "--artifact-dir",
                str(no_write_output_dir),
                "--target",
                target,
                "--source-root",
                str(root),
                "review-blockers",
                "--check-dir",
                str(default_dir),
                "--check-dir",
                str(discovered_dir),
                "--no-write",
            ]
        )
        stdout_buffer = io.StringIO()
        with contextlib.redirect_stdout(stdout_buffer):
            no_write_return_code = no_write_args.func(no_write_args)
        no_write_stdout = stdout_buffer.getvalue()
        no_write_outputs_exist = {
            "artifact_dir": no_write_output_dir.exists(),
            REVIEW_BLOCKERS_ARTIFACT: (no_write_output_dir / REVIEW_BLOCKERS_ARTIFACT).exists(),
            REVIEW_BLOCKERS_MARKDOWN_ARTIFACT: (no_write_output_dir / REVIEW_BLOCKERS_MARKDOWN_ARTIFACT).exists(),
            MANIFEST_NAME: (no_write_output_dir / MANIFEST_NAME).exists(),
        }
        discover_no_write_args = parser.parse_args(
            [
                "--profile",
                str(profile_path),
                "--artifact-dir",
                str(root),
                "--target",
                target,
                "--source-root",
                str(root),
                "review-blockers",
                "--discover-child-runs",
                "--no-write",
            ]
        )
        discover_stdout_buffer = io.StringIO()
        with contextlib.redirect_stdout(discover_stdout_buffer):
            discover_no_write_return_code = discover_no_write_args.func(discover_no_write_args)
        discover_no_write_stdout = discover_stdout_buffer.getvalue()
        discovered_review_blocker_dirs = [
            path.name for path in discover_review_blocker_dirs(root)
        ]

    single_route_group = review_blocker_group_by_cluster(discovered_blockers, "route-api-proxy-path") or {}
    rollup_route_group = review_blocker_group_by_cluster(rollup, "route-api-proxy-path") or {}
    rollup_quote_group = review_blocker_group_by_cluster(rollup, "quote") or {}
    rollup_readiness_group = next(
        (
            item
            for item in rollup.get("groups", []) or []
            if item.get("key") == "external-blocker:ready-with-external-blockers:source:environment-readiness"
        ),
        {},
    )
    rollup_route_group_summary = format_review_blocker_group_summary(rollup_route_group)
    rollup_route_group_command_safety = (rollup_route_group.get("command_safety", {}) or {}).get("summary", {}) or {}
    rollup_route_group_command_refs = (rollup_route_group.get("command_safety", {}) or {}).get("commands", []) or []
    rollup_route_group_command_counts = rollup_route_group_command_safety.get("classification_counts", {}) or {}
    rollup_readiness_group_followups = review_blocker_group_followup_preview_lines(rollup_readiness_group)
    rollup_readiness_group_followup_text = "\n".join(rollup_readiness_group_followups)
    rollup_top_group_summaries = top_review_blocker_group_summaries(rollup, limit=2)
    assertions = [
        {
            "id": "default-status-external-only",
            "passed": default_blockers.get("status") == "ready-with-external-blockers",
            "expected": "ready-with-external-blockers",
            "actual": default_blockers.get("status"),
        },
        {
            "id": "discovered-status-needs-human-review",
            "passed": discovered_blockers.get("status") == "needs-human-review",
            "expected": "needs-human-review",
            "actual": discovered_blockers.get("status"),
        },
        {
            "id": "discovered-route-group-count",
            "passed": single_route_group.get("count") == 5,
            "expected": 5,
            "actual": single_route_group.get("count"),
        },
        {
            "id": "rollup-status-needs-human-review",
            "passed": rollup.get("status") == "needs-human-review",
            "expected": "needs-human-review",
            "actual": rollup.get("status"),
        },
        {
            "id": "rollup-groups-deduplicated",
            "passed": rollup.get("summary", {}).get("groups") == 3,
            "expected": 3,
            "actual": rollup.get("summary", {}).get("groups"),
        },
        {
            "id": "rollup-route-group-preserves-source-peek-blocker",
            "passed": rollup_route_group.get("count") == 5,
            "expected": 5,
            "actual": rollup_route_group.get("count"),
        },
        {
            "id": "rollup-quote-group-merges-runs",
            "passed": rollup_quote_group.get("count") == 2,
            "expected": 2,
            "actual": rollup_quote_group.get("count"),
        },
        {
            "id": "rollup-readiness-group-merges-checks-and-runs",
            "passed": rollup_readiness_group.get("count") == 4,
            "expected": 4,
            "actual": rollup_readiness_group.get("count"),
        },
        {
            "id": "rollup-readiness-group-followup-preview-rendered",
            "passed": (
                "followup_next=Set a real M0_ORCHESTRATION_API_KEY" in rollup_readiness_group_followup_text
                and "artifact_dirs=" in rollup_readiness_group_followup_text
                and all(
                    str(artifact_dir) in rollup_readiness_group_followup_text
                    for artifact_dir in (rollup_readiness_group.get("artifact_dirs", []) or [])[:2]
                )
                and "environment-readiness.json" in rollup_readiness_group_followup_text
                and "source_counts=" in rollup_readiness_group_followup_text
            ),
            "expected": "commandless readiness group no-write follow-up preview includes next steps and artifact context",
            "actual": rollup_readiness_group_followups,
        },
        {
            "id": "markdown-group-sources-rendered",
            "passed": "source-peek-requests.json" in markdown and "Source artifacts:" in markdown,
            "expected": "source-peek-requests.json in markdown group context",
            "actual": "source-peek-requests.json" in markdown,
        },
        {
            "id": "rollup-route-group-preserves-candidate-details",
            "passed": (
                bool(rollup_route_group.get("review_candidates"))
                and rollup_route_group["review_candidates"][0].get("path_template") == "/api/proxy/{path*}"
                and any(
                    "promote-observation-candidate" in command
                    for command in rollup_route_group.get("commands", []) or []
                )
            ),
            "expected": "route group candidate path template and promote command",
            "actual": {
                "review_candidates": rollup_route_group.get("review_candidates"),
                "commands": rollup_route_group.get("commands"),
            },
        },
        {
            "id": "rollup-route-group-command-safety-rendered",
            "passed": (
                rollup_route_group_command_safety.get("commands") == 2
                and len(rollup_route_group_command_refs) == 2
                and rollup_route_group_command_counts.get("manual-template") == 1
                and rollup_route_group_command_counts.get("review-gated") == 1
                and rollup_route_group_command_safety.get("unsafe_template_count") == 0
                and rollup_route_group_command_refs[0].get("classification") == "manual-template"
                and rollup_route_group_command_refs[1].get("classification") == "review-gated"
            ),
            "expected": "route group command safety summarizes manual-template and review-gated commands",
            "actual": rollup_route_group.get("command_safety"),
        },
        {
            "id": "markdown-group-command-templates-rendered",
            "passed": (
                "Candidate details:" in markdown
                and "Command safety:" in markdown
                and "Command templates:" in markdown
                and "# [manual-template]" in markdown
                and "# [review-gated]" in markdown
                and "promote-observation-candidate" in markdown
                and "REPLACE_WITH_APPROVED_CONCRETE_LOCAL_PATH" in markdown
            ),
            "expected": "group-level candidate command templates in markdown",
            "actual": {
                "candidate_details": "Candidate details:" in markdown,
                "command_safety": "Command safety:" in markdown,
                "command_templates": "Command templates:" in markdown,
                "manual_template_label": "# [manual-template]" in markdown,
                "review_gated_label": "# [review-gated]" in markdown,
                "promote": "promote-observation-candidate" in markdown,
                "placeholder": "REPLACE_WITH_APPROVED_CONCRETE_LOCAL_PATH" in markdown,
            },
        },
        {
            "id": "group-summary-is-actionable",
            "passed": (
                "needs-human-review" in rollup_route_group_summary
                and "count=5" in rollup_route_group_summary
                and "cluster=route-api-proxy-path" in rollup_route_group_summary
                and "review_observe_route_api_proxy_path_approved_path" in rollup_route_group_summary
                and "Review one concrete local read-only path" in rollup_route_group_summary
            ),
            "expected": "group summary includes status, count, cluster, candidate id, and next action",
            "actual": rollup_route_group_summary,
        },
        {
            "id": "top-group-summaries-prioritize-actionable-groups",
            "passed": (
                len(rollup_top_group_summaries) == 2
                and "needs-human-review" in rollup_top_group_summaries[0]
                and "route-api-proxy-path" in rollup_top_group_summaries[0]
            ),
            "expected": "top summaries start with the highest-priority human-review group",
            "actual": rollup_top_group_summaries,
        },
        {
            "id": "cli-no-write-skips-review-blocker-outputs",
            "passed": (
                no_write_return_code == 0
                and "Review blockers: needs-human-review" in no_write_stdout
                and "command_safety=commands=2" in no_write_stdout
                and "command_templates:" in no_write_stdout
                and "[manual-template]" in no_write_stdout
                and "[review-gated]" in no_write_stdout
                and "promote-observation-candidate" in no_write_stdout
                and "burp-sync --observe" in no_write_stdout
                and "followup_next=Set a real M0_ORCHESTRATION_API_KEY" in no_write_stdout
                and "artifact_dirs=" in no_write_stdout
                and "environment-readiness.json" in no_write_stdout
                and "No files written (--no-write)." in no_write_stdout
                and not any(no_write_outputs_exist.values())
            ),
            "expected": "review-blockers --no-write prints actionable group commands without writing output artifacts or manifests",
            "actual": {
                "return_code": no_write_return_code,
                "stdout": no_write_stdout.splitlines(),
                "outputs_exist": no_write_outputs_exist,
            },
        },
        {
            "id": "discover-child-runs-uses-review-blocker-artifacts",
            "passed": (
                discover_no_write_return_code == 0
                and discovered_review_blocker_dirs == ["default", "discovered"]
                and "Runs: 2 checked" in discover_no_write_stdout
                and "missing-review-blockers" not in discover_no_write_stdout
            ),
            "expected": "review-blockers --discover-child-runs discovers only child directories with review-blockers.json",
            "actual": {
                "return_code": discover_no_write_return_code,
                "discovered_dirs": discovered_review_blocker_dirs,
                "stdout": discover_no_write_stdout.splitlines(),
            },
        },
    ]
    failed = [item for item in assertions if not item["passed"]]
    return {
        "generated_at": utc_now(),
        "status": "failed" if failed else "passed",
        "target": target,
        "summary": {
            "assertions": len(assertions),
            "failed": len(failed),
            "default_blockers": default_blockers.get("summary", {}).get("blockers"),
            "default_groups": default_blockers.get("summary", {}).get("groups"),
            "discovered_blockers": discovered_blockers.get("summary", {}).get("blockers"),
            "discovered_groups": discovered_blockers.get("summary", {}).get("groups"),
            "rollup_blockers": rollup.get("summary", {}).get("blockers"),
            "rollup_groups": rollup.get("summary", {}).get("groups"),
        },
        "cases": {
            "default": {
                "status": default_blockers.get("status"),
                "summary": default_blockers.get("summary"),
            },
            "discovered": {
                "status": discovered_blockers.get("status"),
                "summary": discovered_blockers.get("summary"),
                "route_group": single_route_group,
            },
            "rollup": {
                "status": rollup.get("status"),
                "summary": rollup.get("summary"),
                "route_group": rollup_route_group,
                "route_group_summary": rollup_route_group_summary,
                "top_group_summaries": rollup_top_group_summaries,
                "quote_group": rollup_quote_group,
                "readiness_group": rollup_readiness_group,
            },
            "no_write": {
                "return_code": no_write_return_code,
                "stdout": no_write_stdout.splitlines(),
                "outputs_exist": no_write_outputs_exist,
            },
            "discover_child_runs_no_write": {
                "return_code": discover_no_write_return_code,
                "discovered_dirs": discovered_review_blocker_dirs,
                "stdout": discover_no_write_stdout.splitlines(),
            },
        },
        "assertions": assertions,
        "safety": "Synthetic review-blocker self-test. It writes temporary local artifacts only and sends no requests.",
    }


def markdown_text(value: Any) -> str:
    return str(value).replace("\n", " ").strip()


def write_review_blockers_markdown(path: Path, review_blockers: dict[str, Any]) -> None:
    summary = review_blockers.get("summary", {}) or {}
    groups = review_blockers.get("groups", []) or []
    blockers = review_blockers.get("blockers", []) or []
    status_counts = summary.get("status_counts", {}) or {}
    category_counts = summary.get("category_counts", {}) or {}
    group_status_counts = summary.get("group_status_counts", {}) or {}
    group_category_counts = summary.get("group_category_counts", {}) or {}
    source_counts = summary.get("source_counts", {}) or {}
    grouped_actionable = [
        item
        for item in groups
        if str(item.get("status") or "") in {"failed", "needs-profile-update", "needs-human-review"}
    ][:8]
    grouped_external = [
        item
        for item in groups
        if str(item.get("status") or "") == "ready-with-external-blockers"
    ][:8]
    actionable = grouped_actionable or [
        item
        for item in blockers
        if str(item.get("status") or "") in {"failed", "needs-profile-update", "needs-human-review"}
    ][:8]
    external = grouped_external or [
        item
        for item in blockers
        if str(item.get("status") or "") == "ready-with-external-blockers"
    ][:8]

    def append_group_context(item: dict[str, Any]) -> None:
        candidates = item.get("review_candidates", []) or []
        if candidates:
            lines.append("  - Candidate details:")
            for candidate in candidates[:4]:
                details = []
                if candidate.get("method"):
                    details.append(f"method=`{candidate.get('method')}`")
                if candidate.get("path_template"):
                    details.append(f"path_template=`{candidate.get('path_template')}`")
                if candidate.get("example_path"):
                    details.append(f"example=`{candidate.get('example_path')}`")
                suffix = f" {' '.join(details)}" if details else ""
                lines.append(f"    - `{candidate.get('id')}`{suffix}")
            if len(candidates) > 4:
                lines.append(f"    - ... +{len(candidates) - 4} more candidates")
        commands = review_blocker_group_command_templates(item)
        if commands:
            command_safety = (item.get("command_safety", {}) or {}).get("summary", {}) or {}
            if command_safety:
                lines.append(f"  - Command safety: `{format_command_safety_summary(command_safety)}`")
            command_refs_by_command = {
                str(ref.get("command") or ""): ref
                for ref in (item.get("command_safety", {}) or {}).get("commands", []) or []
            }
            lines.append("  - Command templates:")
            lines.append("    ```bash")
            for command in commands[:6]:
                ref = command_refs_by_command.get(str(command))
                if ref:
                    lines.append(f"    # {format_command_ref_label(ref)}")
                lines.append(f"    {command}")
            if len(commands) > 6:
                lines.append(f"    # ... +{len(commands) - 6} more commands")
            lines.append("    ```")
        sources = item.get("sources", []) or []
        if sources:
            lines.append("  - Source artifacts: " + ", ".join(f"`{source}`" for source in sources[:6]))
        refs = item.get("artifact_refs", []) or []
        if refs:
            suffix = "" if len(refs) <= 8 else f" (+{len(refs) - 8} more)"
            lines.append("  - Evidence refs: " + ", ".join(f"`{ref}`" for ref in refs[:8]) + suffix)

    lines = [
        "# InferForge Review Blockers",
        "",
        f"Generated: {utc_now()}",
        "",
        f"- Target: `{review_blockers.get('target')}`",
        f"- Status: `{review_blockers.get('status')}`",
        f"- Blockers: `{summary.get('blockers', 0)}`",
        f"- Blocker groups: `{summary.get('groups', len(groups))}`",
        f"- Mode: `{review_blockers.get('mode', 'single')}`",
        f"- Status counts: `{json.dumps(status_counts, sort_keys=True)}`",
        f"- Category counts: `{json.dumps(category_counts, sort_keys=True)}`",
        f"- Group status counts: `{json.dumps(group_status_counts, sort_keys=True)}`",
        f"- Group category counts: `{json.dumps(group_category_counts, sort_keys=True)}`",
        f"- Source counts: `{json.dumps(source_counts, sort_keys=True)}`",
        "",
        "## Safety",
        "",
        "- This file is generated from local artifacts only.",
        "- Do not sign wallets or submit Solana transactions from these steps.",
        "- Replace REPLACE_WITH_* placeholders before running manual-review commands.",
        "- Keep Burp Proxy Intercept off for unattended automation.",
        "",
        "## Next Actions",
        "",
    ]
    if actionable:
        for item in actionable:
            artifact_dirs = item.get("artifact_dirs", []) or []
            run_prefix = f"[{', '.join(artifact_dirs)}] " if artifact_dirs else f"[{item.get('artifact_dir')}] " if item.get("artifact_dir") else ""
            count_suffix = f" ({item.get('count')} blockers)" if item.get("count") else ""
            lines.append(
                f"- `{item.get('status')}` `{item.get('id')}`{count_suffix}: {run_prefix}{markdown_text(item.get('title'))}"
            )
            if item.get("next_action"):
                lines.append(f"  - Next: {markdown_text(item.get('next_action'))}")
            if item.get("review_candidate_ids"):
                lines.append("  - Review candidates: " + ", ".join(f"`{candidate_id}`" for candidate_id in item.get("review_candidate_ids", [])))
            append_group_context(item)
    elif external:
        lines.append("- No human-review blocker is first in line; resolve external configuration blockers below.")
    else:
        lines.append("- No blockers are currently reported.")

    if external:
        lines.extend(["", "## External Configuration", ""])
        for item in external:
            artifact_dirs = item.get("artifact_dirs", []) or []
            run_prefix = f"[{', '.join(artifact_dirs)}] " if artifact_dirs else f"[{item.get('artifact_dir')}] " if item.get("artifact_dir") else ""
            count_suffix = f" ({item.get('count')} blockers)" if item.get("count") else ""
            lines.append(
                f"- `{item.get('id')}`{count_suffix}: {run_prefix}{markdown_text(item.get('title'))}"
            )
            if item.get("next_action"):
                lines.append(f"  - Next: {markdown_text(item.get('next_action'))}")
            append_group_context(item)

    lines.extend(["", "## Blockers", ""])
    if not blockers:
        lines.append("No blockers were reported.")
    for item in blockers:
        lines.extend(
            [
                f"### {item.get('id')}",
                "",
                f"- Status: `{item.get('status')}`",
                f"- Category: `{item.get('category')}`",
                f"- Priority: `{item.get('priority')}`",
                f"- Source: `{item.get('source')}`",
                f"- Artifact dir: `{item.get('artifact_dir') or ''}`",
                f"- Cluster: `{item.get('cluster_id') or ''}`",
                f"- Title: {markdown_text(item.get('title'))}",
                f"- Reason: {markdown_text(item.get('reason'))}",
            ]
        )
        if item.get("next_action"):
            lines.append(f"- Next action: {markdown_text(item.get('next_action'))}")
        refs = item.get("artifact_refs", []) or []
        if refs:
            lines.append("- Artifact refs: " + ", ".join(f"`{ref}`" for ref in refs))
        candidates = item.get("review_candidates", []) or []
        if candidates:
            lines.append("- Review candidates:")
            for candidate in candidates:
                details = []
                if candidate.get("type"):
                    details.append(f"type=`{candidate.get('type')}`")
                if candidate.get("status"):
                    details.append(f"status=`{candidate.get('status')}`")
                suffix = f" {' '.join(details)}" if details else ""
                lines.append(f"  - `{candidate.get('id')}`{suffix}")
                if candidate.get("path_template"):
                    lines.append(f"    - Path template: `{candidate.get('path_template')}`")
                if candidate.get("example_path"):
                    lines.append(f"    - Example path: `{candidate.get('example_path')}`")
                approval_required = candidate.get("approval_required", []) or []
                if approval_required:
                    lines.append("    - Approval required:")
                    lines.extend(f"      - {markdown_text(entry)}" for entry in approval_required)
                command_templates = candidate.get("command_templates", []) or []
                if command_templates:
                    lines.append("    - Command templates:")
                    lines.append("      ```bash")
                    lines.extend(f"      {command}" for command in command_templates[:6])
                    if len(command_templates) > 6:
                        lines.append(f"      # ... +{len(command_templates) - 6} more commands")
                    lines.append("      ```")
        commands = item.get("commands", []) or []
        if commands:
            lines.extend(["", "Commands:", "", "```bash"])
            lines.extend(str(command) for command in commands)
            lines.append("```")
        lines.append("")

    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_kind(path: Path) -> str:
    if path.suffix == ".json":
        return "json"
    if path.suffix == ".jsonl":
        return "jsonl"
    if path.suffix in {".md", ".markdown"}:
        return "markdown"
    if path.suffix == ".html":
        return "html"
    if path.suffix == ".txt":
        return "text"
    if path.suffix == ".log":
        return "log"
    return path.suffix.lstrip(".") or "file"


def artifact_link_names(artifact_dir: Path) -> list[str]:
    existing = {path.name for path in artifact_dir.iterdir() if path.is_file()}
    always = set(REQUIRED_ARTIFACTS) | {MANIFEST_NAME}
    names: list[str] = []
    for name in INDEX_ARTIFACT_ORDER:
        if name in existing or name in always:
            if name not in names:
                names.append(name)
    for name in sorted(existing - set(names)):
        names.append(name)
    return names


def json_status_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for key in ["generated_at", "status", "target", "path", "safety"]:
        if key in data:
            snapshot[key] = data[key]
    if "summary" in data and isinstance(data["summary"], dict):
        snapshot["summary"] = data["summary"]
    if "diagnosis" in data and isinstance(data["diagnosis"], dict):
        snapshot["diagnosis"] = {
            key: data["diagnosis"].get(key)
            for key in ["classification", "summary", "next_step"]
            if key in data["diagnosis"]
        }
    return snapshot


def build_artifact_manifest(
    artifact_dir: Path,
    target: str,
    *,
    command: str,
) -> dict[str, Any]:
    artifact_rows = []
    status_sources: dict[str, Any] = {}
    status_source_names = {
        "blackbox-coverage.json",
        DISCOVERY_COVERAGE_ARTIFACT,
        "burp-observation-coverage.json",
        "evidence-chain.json",
        "evidence-appendix.json",
        "response-delta-analysis.json",
        "source-peek-requests.json",
        "verification-queue.json",
        REVIEW_BLOCKERS_ARTIFACT,
        "adjudication.json",
        "environment-readiness.json",
        "attack-strategy.json",
        PROFILE_VALIDATION_ARTIFACT,
        "discovered-profile-validation.json",
        "review-observation-candidates.json",
        "reviewed-profile-validation.json",
        "reviewed-observation-promotion.json",
        "profile-routing-selftest.json",
        DISCOVERY_COVERAGE_SELFTEST_ARTIFACT,
        ARTIFACT_HEALTH_SELFTEST_ARTIFACT,
        "burp-mcp-sync.json",
        "quote-collection.json",
        "transaction-intent.json",
        "transaction-decoder-selftest.json",
    }

    for path in sorted(artifact_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name == MANIFEST_NAME:
            continue
        stat = path.stat()
        row: dict[str, Any] = {
            "name": path.name,
            "kind": artifact_kind(path),
            "size_bytes": stat.st_size,
            "sha256": sha256_file(path),
            "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        if path.suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                row["json_error"] = str(error)
            else:
                row.update(
                    {
                        "generated_at": data.get("generated_at"),
                        "status": data.get("status"),
                    }
                )
                if path.name in status_source_names:
                    status_sources[path.name] = json_status_snapshot(data)
        elif path.suffix == ".jsonl":
            lines = path.read_text(encoding="utf-8").splitlines()
            row["line_count"] = sum(1 for line in lines if line.strip())
        artifact_rows.append(row)

    names = {row["name"] for row in artifact_rows}
    missing_required = [name for name in REQUIRED_ARTIFACTS if name not in names]
    review_artifacts_present = [name for name in REVIEW_ARTIFACTS if name in names]
    discovery_artifacts_present = [name for name in DISCOVERY_ARTIFACTS if name in names]
    optional_artifacts_present = [name for name in KNOWN_OPTIONAL_ARTIFACTS if name in names]
    stale_inputs = []
    readiness_status = (status_sources.get("environment-readiness.json") or {}).get("status")
    coverage_status = (status_sources.get("blackbox-coverage.json") or {}).get("status")
    discovery_coverage_status = (status_sources.get(DISCOVERY_COVERAGE_ARTIFACT) or {}).get("status")
    adjudication_status = (status_sources.get("adjudication.json") or {}).get("status")
    verification_status = (status_sources.get("verification-queue.json") or {}).get("status")
    review_blockers_status = (status_sources.get(REVIEW_BLOCKERS_ARTIFACT) or {}).get("status")
    profile_validation_status = (status_sources.get(PROFILE_VALIDATION_ARTIFACT) or {}).get("status")
    burp_observation_status = (status_sources.get("burp-observation-coverage.json") or {}).get("status")
    response_delta_status = (status_sources.get("response-delta-analysis.json") or {}).get("status")
    source_peek_request_status = (status_sources.get("source-peek-requests.json") or {}).get("status")
    attack_strategy_status = (status_sources.get("attack-strategy.json") or {}).get("status")
    external_blocked = any(
        status in {"covered-with-external-blocker", "no-reportable-findings-with-external-blocker", "ready-with-external-blockers", "waiting-for-external-configuration", "needs-external-evidence"}
        for status in [coverage_status, adjudication_status, verification_status, review_blockers_status, readiness_status, attack_strategy_status]
    )
    human_review_required = any(
        status in {"needs-human-review", "answered-with-manual-review", "covered-with-evidence-gaps", "needs-strategy-review"}
        for status in [
            coverage_status,
            discovery_coverage_status,
            verification_status,
            review_blockers_status,
            burp_observation_status,
            source_peek_request_status,
            attack_strategy_status,
        ]
    )
    if missing_required:
        manifest_status = "incomplete"
    elif profile_validation_status == "failed":
        manifest_status = "failed-profile-validation"
    elif human_review_required:
        manifest_status = "needs-human-review"
    elif external_blocked:
        manifest_status = "complete-with-external-blocker"
    else:
        manifest_status = "complete"

    return {
        "generated_at": utc_now(),
        "status": manifest_status,
        "target": target,
        "command": command,
        "artifact_dir": str(artifact_dir),
        "summary": {
            "artifact_count": len(artifact_rows),
            "required_count": len(REQUIRED_ARTIFACTS),
            "missing_required": missing_required,
            "stale_inputs": stale_inputs,
            "coverage": coverage_status,
            "discovery_coverage": discovery_coverage_status,
            "adjudication": adjudication_status,
            "verification_queue": verification_status,
            "review_blockers": review_blockers_status,
            "readiness": readiness_status,
            "profile_validation": profile_validation_status,
            "burp_observation_coverage": burp_observation_status,
            "response_delta_analysis": response_delta_status,
            "source_peek_requests": source_peek_request_status,
            "attack_strategy": attack_strategy_status,
            "review_artifacts_present": review_artifacts_present,
            "discovery_artifacts_present": discovery_artifacts_present,
            "known_optional_artifacts_present": optional_artifacts_present,
        },
        "required_artifacts": REQUIRED_ARTIFACTS,
        "optional_artifacts": {
            "review": REVIEW_ARTIFACTS,
            "discovery": DISCOVERY_ARTIFACTS,
            "known_optional": KNOWN_OPTIONAL_ARTIFACTS,
        },
        "status_sources": status_sources,
        "artifacts": artifact_rows,
        "integrity": {
            "hash_algorithm": "sha256",
            "self_excluded": MANIFEST_NAME,
            "note": "Manifest hashes artifacts as they existed when the manifest was generated. Regenerate after changing artifacts.",
        },
        "safety": "Manifest generation is read-only except for writing artifact-manifest.json.",
    }


def write_artifact_manifest(artifact_dir: Path, target: str, *, command: str) -> dict[str, Any]:
    manifest = build_artifact_manifest(artifact_dir, target, command=command)
    write_json(artifact_dir / MANIFEST_NAME, manifest)
    return manifest


def refresh_manifests_for_artifact_outputs(
    *,
    output_paths: list[Path],
    artifact_dir: Path,
    check_dirs: list[Path],
    target: str,
    command: str,
) -> list[dict[str, Any]]:
    output_parents = {path.resolve().parent for path in output_paths}
    candidates = [artifact_dir.resolve(), *[path.resolve() for path in check_dirs]]
    refreshed = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if candidate not in output_parents or not candidate.exists():
            continue
        manifest = write_artifact_manifest(candidate, target, command=command)
        refreshed.append(
            {
                "artifact_dir": str(candidate),
                "manifest": str(candidate / MANIFEST_NAME),
                "status": manifest.get("status"),
            }
        )
    return refreshed


def refresh_artifact_health_output_manifests(
    *,
    output_path: Path,
    artifact_dir: Path,
    check_dirs: list[Path],
    target: str,
) -> list[dict[str, Any]]:
    return refresh_manifests_for_artifact_outputs(
        output_paths=[output_path],
        artifact_dir=artifact_dir,
        check_dirs=check_dirs,
        target=target,
        command="artifact-health",
    )


def refresh_current_artifact_manifest(
    *,
    artifact_dir: Path,
    target: str,
    command: str,
    output_paths: list[Path],
) -> list[dict[str, Any]]:
    return refresh_manifests_for_artifact_outputs(
        output_paths=output_paths,
        artifact_dir=artifact_dir,
        check_dirs=[],
        target=target,
        command=command,
    )


def print_refreshed_manifests(refreshed_manifests: list[dict[str, Any]]) -> None:
    for item in refreshed_manifests:
        print(f"Refreshed {item['manifest']}: {item['status']}")


def format_artifact_health_stale_issue(issue: dict[str, Any]) -> str:
    parts = [
        f"{issue.get('file') or 'unknown'}",
        f"reason={issue.get('reason') or 'unknown'}",
    ]
    newer_inputs = [str(item) for item in issue.get("newer_inputs", []) or []]
    if newer_inputs:
        suffix = ""
        newer_input_count = issue.get("newer_input_count")
        if isinstance(newer_input_count, int) and newer_input_count > len(newer_inputs):
            suffix = f",+{newer_input_count - len(newer_inputs)}"
        parts.append(f"newer_inputs={','.join(newer_inputs)}{suffix}")
    next_step = issue.get("next_step")
    if next_step:
        parts.append(f"next_step={next_step}")
    return " ".join(parts)


def increment_count(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def artifact_statuses_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    summary = manifest.get("summary", {}) or {}
    return {
        "manifest": manifest.get("status"),
        "coverage": summary.get("coverage"),
        "discovery_coverage": summary.get("discovery_coverage"),
        "adjudication": summary.get("adjudication"),
        "verification_queue": summary.get("verification_queue"),
        "review_blockers": summary.get("review_blockers"),
        "readiness": summary.get("readiness"),
        "profile_validation": summary.get("profile_validation"),
        "burp_observation_coverage": summary.get("burp_observation_coverage"),
        "response_delta_analysis": summary.get("response_delta_analysis"),
        "source_peek_requests": summary.get("source_peek_requests"),
        "attack_strategy": summary.get("attack_strategy"),
    }


def parse_artifact_json(path: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as error:
        return None, {
            "file": path.name,
            "kind": "json",
            "error": str(error),
        }


def parse_artifact_jsonl(path: Path) -> tuple[int, list[dict[str, Any]]]:
    rows = 0
    errors = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        rows += 1
        try:
            json.loads(line)
        except Exception as error:
            errors.append(
                {
                    "file": path.name,
                    "line": lineno,
                    "kind": "jsonl",
                    "error": str(error),
                }
            )
            if len(errors) >= 10:
                break
    return rows, errors


def manifest_integrity_issues(artifact_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    issues = []
    rows_by_name: dict[str, dict[str, Any]] = {}
    for row in manifest.get("artifacts", []) or []:
        name = str(row.get("name") or "")
        if not name or name == MANIFEST_NAME:
            continue
        if "/" in name or "\\" in name:
            issues.append(
                {
                    "file": name,
                    "reason": "invalid-manifest-artifact-name",
                    "expected": "top-level artifact filename",
                }
            )
            continue
        rows_by_name[name] = row

    for name, row in sorted(rows_by_name.items()):
        path = artifact_dir / name
        if not path.exists() or not path.is_file():
            issues.append(
                {
                    "file": name,
                    "reason": "missing-after-manifest",
                    "expected_sha256": row.get("sha256"),
                    "expected_size_bytes": row.get("size_bytes"),
                }
            )
            continue
        stat = path.stat()
        actual_size = stat.st_size
        actual_sha256 = sha256_file(path)
        if row.get("size_bytes") != actual_size or row.get("sha256") != actual_sha256:
            issues.append(
                {
                    "file": name,
                    "reason": "manifest-hash-mismatch",
                    "expected_sha256": row.get("sha256"),
                    "actual_sha256": actual_sha256,
                    "expected_size_bytes": row.get("size_bytes"),
                    "actual_size_bytes": actual_size,
                }
            )

    for path in sorted(artifact_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name == MANIFEST_NAME:
            continue
        if path.name not in rows_by_name:
            issues.append(
                {
                    "file": path.name,
                    "reason": "not-listed-in-manifest",
                    "actual_sha256": sha256_file(path),
                    "actual_size_bytes": path.stat().st_size,
                }
            )

    return issues


def derived_artifact_freshness_issues(artifact_dir: Path) -> list[dict[str, Any]]:
    issues = []
    def stale_inputs_for(derived_path: Path, input_names: list[str]) -> list[dict[str, Any]]:
        if not derived_path.is_file():
            return []
        input_paths = [
            artifact_dir / name
            for name in input_names
            if (artifact_dir / name).is_file()
        ]
        if not input_paths:
            return []
        derived_mtime_ns = derived_path.stat().st_mtime_ns
        newer = []
        for input_path in input_paths:
            input_mtime_ns = input_path.stat().st_mtime_ns
            if input_mtime_ns > derived_mtime_ns:
                newer.append(
                    {
                        "file": input_path.name,
                        "mtime_ns": input_mtime_ns,
                    }
                )
        newer.sort(key=lambda item: (-int(item["mtime_ns"]), str(item["file"])))
        return newer

    for rule in DERIVED_ARTIFACT_FRESHNESS_RULES:
        input_names = [str(name) for name in rule.get("inputs", [])]
        for derived_name in rule.get("outputs", []):
            derived_path = artifact_dir / str(derived_name)
            newer_inputs = stale_inputs_for(derived_path, input_names)
            if not newer_inputs:
                continue
            issues.append(
                {
                    "file": str(derived_name),
                    "reason": rule.get("reason"),
                    "newer_inputs": [item["file"] for item in newer_inputs[:12]],
                    "newer_input_count": len(newer_inputs),
                    "next_step": rule.get("next_step"),
                }
            )
    return issues


def artifact_health_status(checks: list[dict[str, Any]], statuses: dict[str, Any]) -> str:
    if any(check.get("status") == "failed" for check in checks):
        return "failed"
    if (
        statuses.get("verification_queue") == "needs-human-review"
        or statuses.get("review_blockers") == "needs-human-review"
        or statuses.get("discovery_coverage") == "needs-human-review"
        or statuses.get("burp_observation_coverage") == "needs-human-review"
        or statuses.get("source_peek_requests") == "answered-with-manual-review"
        or statuses.get("coverage") == "covered-with-evidence-gaps"
    ):
        return "needs-human-review"
    if any(
        status in {
            "complete-with-external-blocker",
            "covered-with-external-blocker",
            "ready-with-external-blockers",
            "no-reportable-findings-with-external-blocker",
            "indexed-with-external-blocker",
            "waiting-for-external-configuration",
        }
        for status in statuses.values()
    ):
        return "ready-with-external-blockers"
    return "healthy"


def build_single_artifact_health(artifact_dir: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    json_files = []
    jsonl_files = []
    json_errors = []
    jsonl_errors = []
    jsonl_rows: dict[str, int] = {}
    manifest: dict[str, Any] | None = None
    stale_inputs: list[dict[str, Any]] = []

    if not artifact_dir.exists():
        checks.append(
            {
                "id": "artifact-dir-exists",
                "status": "failed",
                "message": "Artifact directory does not exist.",
            }
        )
        return {
            "artifact_dir": str(artifact_dir),
            "status": "failed",
            "checks": checks,
            "parse": {
                "json_files": 0,
                "jsonl_files": 0,
                "json_errors": json_errors,
                "jsonl_errors": jsonl_errors,
                "jsonl_rows": jsonl_rows,
            },
            "statuses": {},
            "missing_required": [],
            "stale_inputs": stale_inputs,
            "safety": "Read-only artifact health analysis. No requests are sent.",
        }

    for path in sorted(artifact_dir.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        if path.suffix == ".json":
            json_files.append(path.name)
            parsed, error = parse_artifact_json(path)
            if error:
                json_errors.append(error)
                continue
            if path.name == MANIFEST_NAME:
                manifest = parsed
        elif path.suffix == ".jsonl":
            jsonl_files.append(path.name)
            rows, errors = parse_artifact_jsonl(path)
            jsonl_rows[path.name] = rows
            jsonl_errors.extend(errors)

    if json_errors:
        checks.append(
            {
                "id": "json-parse",
                "status": "failed",
                "message": f"{len(json_errors)} JSON artifact(s) failed to parse.",
            }
        )
    else:
        checks.append(
            {
                "id": "json-parse",
                "status": "passed",
                "message": f"{len(json_files)} JSON artifact(s) parsed.",
            }
        )

    if jsonl_errors:
        checks.append(
            {
                "id": "jsonl-parse",
                "status": "failed",
                "message": f"{len(jsonl_errors)} JSONL parse error(s) found.",
            }
        )
    else:
        checks.append(
            {
                "id": "jsonl-parse",
                "status": "passed",
                "message": f"{len(jsonl_files)} JSONL artifact(s) parsed.",
            }
        )

    if manifest is None:
        checks.append(
            {
                "id": "manifest-present",
                "status": "failed",
                "message": f"{MANIFEST_NAME} is missing or invalid.",
            }
        )
        statuses = {}
        missing_required = []
    else:
        checks.append(
            {
                "id": "manifest-present",
                "status": "passed",
                "message": f"{MANIFEST_NAME} parsed.",
            }
        )
        statuses = artifact_statuses_from_manifest(manifest)
        missing_required = list((manifest.get("summary", {}) or {}).get("missing_required", []) or [])
        stale_inputs = manifest_integrity_issues(artifact_dir, manifest)
        stale_inputs.extend(derived_artifact_freshness_issues(artifact_dir))
        if missing_required:
            checks.append(
                {
                    "id": "required-artifacts",
                    "status": "failed",
                    "message": f"{len(missing_required)} required artifact(s) missing.",
                    "missing_required": missing_required,
                }
            )
        else:
            checks.append(
                {
                    "id": "required-artifacts",
                    "status": "passed",
                    "message": "No required artifacts are missing.",
                }
            )

        if stale_inputs:
            checks.append(
                {
                    "id": "manifest-integrity",
                    "status": "failed",
                    "message": f"{len(stale_inputs)} artifact integrity/freshness issue(s) found.",
                    "stale_inputs": stale_inputs[:20],
                }
            )
        else:
            checks.append(
                {
                    "id": "manifest-integrity",
                    "status": "passed",
                    "message": f"All artifacts listed in {MANIFEST_NAME} match current files.",
                }
            )

        profile_validation = statuses.get("profile_validation")
        if profile_validation == "failed":
            checks.append(
                {
                    "id": "profile-validation",
                    "status": "failed",
                    "message": "Profile validation failed.",
                }
            )

        response_delta_status = statuses.get("response_delta_analysis")
        if response_delta_status in {"review-needed", "no-probe-results"}:
            checks.append(
                {
                    "id": "response-delta-analysis",
                    "status": "failed",
                    "message": f"Response delta status is {response_delta_status}.",
                }
            )

        coverage_status = str(statuses.get("coverage") or "")
        if coverage_status.startswith("failed"):
            checks.append(
                {
                    "id": "coverage",
                    "status": "failed",
                    "message": f"Coverage status is {coverage_status}.",
                }
            )

        discovery_coverage_status = str(statuses.get("discovery_coverage") or "")
        if discovery_coverage_status in {"uncovered", "failed", "profile-error", "missing-route-inventory", "no-surfaces"}:
            checks.append(
                {
                    "id": "discovery-coverage",
                    "status": "failed",
                    "message": f"Discovery coverage status is {discovery_coverage_status}.",
                }
            )

        if statuses.get("verification_queue") == "invalid-command-templates":
            checks.append(
                {
                    "id": "verification-queue",
                    "status": "failed",
                    "message": "Verification queue generated unsafe command templates.",
                }
            )

        review_blockers_status = str(statuses.get("review_blockers") or "")
        if review_blockers_status in {"failed", "needs-profile-update"}:
            checks.append(
                {
                    "id": "review-blockers",
                    "status": "failed",
                    "message": f"Review blockers status is {review_blockers_status}.",
                }
            )

    status = artifact_health_status(checks, statuses)
    return {
        "artifact_dir": str(artifact_dir),
        "status": status,
        "checks": checks,
        "statuses": statuses,
        "missing_required": missing_required,
        "stale_inputs": stale_inputs,
        "parse": {
            "json_files": len(json_files),
            "jsonl_files": len(jsonl_files),
            "json_errors": json_errors,
            "jsonl_errors": jsonl_errors,
            "jsonl_rows": jsonl_rows,
        },
        "safety": "Read-only artifact health analysis. No requests are sent.",
    }


def artifact_dir_from_suite_value(value: Any) -> Path | None:
    if value is None:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return path.resolve()
    return resolve_repo_path(path)


def discover_regression_suite_artifact_health_dirs(root_dir: Path) -> list[Path]:
    suite = load_optional_json(root_dir / "regression-suite.json") or {}
    artifact_dirs = suite.get("artifact_dirs", {}) or {}
    dirs: list[Path] = []
    seen: set[str] = set()
    for suite_key in ["suite", "default", "discovered"]:
        path = artifact_dir_from_suite_value(artifact_dirs.get(suite_key))
        if not path:
            continue
        resolved = path.resolve()
        resolved_key = str(resolved)
        if resolved_key in seen:
            continue
        seen.add(resolved_key)
        dirs.append(resolved)
    return dirs


def discover_manifest_artifact_health_dirs(root_dir: Path) -> list[Path]:
    dirs: set[Path] = set()
    if (root_dir / MANIFEST_NAME).exists():
        dirs.add(root_dir)
    for manifest_path in sorted(root_dir.glob(f"*/{MANIFEST_NAME}")):
        dirs.add(manifest_path.parent)
    return sorted(dirs, key=lambda item: str(item))


def discover_artifact_health_dirs(root_dir: Path) -> list[Path]:
    regression_dirs = discover_regression_suite_artifact_health_dirs(root_dir)
    if regression_dirs:
        return regression_dirs
    return discover_manifest_artifact_health_dirs(root_dir)


def discover_review_blocker_dirs(root_dir: Path) -> list[Path]:
    return sorted(
        {path.parent for path in root_dir.glob(f"*/{REVIEW_BLOCKERS_ARTIFACT}")},
        key=lambda item: str(item),
    )


def build_artifact_health(artifact_dirs: list[Path]) -> dict[str, Any]:
    directories = [build_single_artifact_health(path.resolve()) for path in artifact_dirs]
    status_counts: dict[str, int] = {}
    failed_dirs = []
    human_review_dirs = []
    external_blocker_dirs = []
    parse_error_count = 0
    missing_required_count = 0
    stale_input_count = 0

    for item in directories:
        status = str(item.get("status") or "unknown")
        increment_count(status_counts, status)
        if status == "failed":
            failed_dirs.append(item["artifact_dir"])
        elif status == "needs-human-review":
            human_review_dirs.append(item["artifact_dir"])
        elif status == "ready-with-external-blockers":
            external_blocker_dirs.append(item["artifact_dir"])
        parse_doc = item.get("parse", {}) or {}
        parse_error_count += len(parse_doc.get("json_errors", []) or [])
        parse_error_count += len(parse_doc.get("jsonl_errors", []) or [])
        missing_required_count += len(item.get("missing_required", []) or [])
        stale_input_count += len(item.get("stale_inputs", []) or [])

    if not directories:
        status = "no-artifact-dirs"
    elif failed_dirs:
        status = "failed"
    elif human_review_dirs:
        status = "needs-human-review"
    elif external_blocker_dirs:
        status = "ready-with-external-blockers"
    else:
        status = "healthy"

    return {
        "generated_at": utc_now(),
        "status": status,
        "summary": {
            "artifact_dirs": len(directories),
            "status_counts": status_counts,
            "failed_dirs": failed_dirs,
            "human_review_dirs": human_review_dirs,
            "external_blocker_dirs": external_blocker_dirs,
            "parse_error_count": parse_error_count,
            "missing_required_count": missing_required_count,
            "stale_input_count": stale_input_count,
        },
        "directories": directories,
        "safety": "Local artifact health analysis only. It does not send HTTP requests, call Burp, fuzz, sign wallets, submit transactions, or invoke Server Actions.",
    }


def write_artifact_health_artifact(
    *,
    health: dict[str, Any],
    output_path: Path,
    artifact_dir: Path,
    check_dirs: list[Path],
    target: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    write_json(output_path, health)
    refreshed_manifests = refresh_artifact_health_output_manifests(
        output_path=output_path,
        artifact_dir=artifact_dir,
        check_dirs=check_dirs,
        target=target,
    )
    if not refreshed_manifests:
        return health, refreshed_manifests

    refreshed_health = build_artifact_health(check_dirs)
    write_json(output_path, refreshed_health)
    refreshed_manifests = refresh_artifact_health_output_manifests(
        output_path=output_path,
        artifact_dir=artifact_dir,
        check_dirs=check_dirs,
        target=target,
    )
    return refreshed_health, refreshed_manifests


def build_artifact_health_selftest() -> dict[str, Any]:
    def manifest_row(path: Path) -> dict[str, Any]:
        stat = path.stat()
        return {
            "name": path.name,
            "kind": artifact_kind(path),
            "size_bytes": stat.st_size,
            "sha256": sha256_file(path),
        }

    def write_minimal_manifest(artifact_dir: Path, artifact_names: list[str]) -> None:
        rows = [manifest_row(artifact_dir / name) for name in artifact_names]
        write_json(
            artifact_dir / MANIFEST_NAME,
            {
                "generated_at": utc_now(),
                "status": "complete",
                "summary": {"missing_required": []},
                "artifacts": rows,
            },
        )

    def write_sample_artifact(path: Path) -> None:
        if path.suffix == ".json":
            write_json(path, {"generated_at": utc_now(), "status": "ready", "summary": {}})
        elif path.suffix == ".jsonl":
            path.write_text('{"status":"ready"}\n', encoding="utf-8")
        else:
            path.write_text("ready\n", encoding="utf-8")

    def set_mtime_ns(path: Path, mtime_ns: int) -> None:
        os.utime(path, ns=(mtime_ns, mtime_ns))

    with tempfile.TemporaryDirectory(prefix="inferforge-artifact-health-selftest-") as temp_dir:
        root = Path(temp_dir)
        healthy_dir = root / "healthy"
        modified_dir = root / "modified"
        missing_dir = root / "missing"
        untracked_dir = root / "untracked"
        refresh_dir = root / "refresh"
        derived_dir = root / "derived"
        for directory in [healthy_dir, modified_dir, missing_dir, untracked_dir]:
            directory.mkdir(parents=True)
            write_json(directory / "ok.json", {"status": "ready"})
            write_minimal_manifest(directory, ["ok.json"])

        refresh_dir.mkdir(parents=True)
        for name in REQUIRED_ARTIFACTS:
            write_sample_artifact(refresh_dir / name)
        baseline_mtime_ns = 1_700_000_000_000_000_000
        for name in REPORT_FRESHNESS_INPUTS:
            path = refresh_dir / name
            if path.exists():
                set_mtime_ns(path, baseline_mtime_ns)
        set_mtime_ns(refresh_dir / "report.md", baseline_mtime_ns + 1_000)
        set_mtime_ns(refresh_dir / "index.html", baseline_mtime_ns + 1_000)
        write_artifact_manifest(refresh_dir, "http://127.0.0.1:9997", command="self-test-artifact-health")

        write_json(modified_dir / "ok.json", {"status": "changed"})
        (missing_dir / "ok.json").unlink()
        write_json(untracked_dir / "extra.json", {"status": "new"})

        healthy = build_single_artifact_health(healthy_dir)
        modified = build_single_artifact_health(modified_dir)
        missing = build_single_artifact_health(missing_dir)
        untracked = build_single_artifact_health(untracked_dir)
        aggregate = build_artifact_health([healthy_dir, modified_dir, missing_dir, untracked_dir])
        refresh_health = build_artifact_health([refresh_dir])
        refresh_output = refresh_dir / "artifact-health.json"
        write_json(refresh_output, refresh_health)
        refresh_stale_before = build_single_artifact_health(refresh_dir)
        refreshed_health, refreshed_manifests = write_artifact_health_artifact(
            health=refresh_health,
            output_path=refresh_output,
            artifact_dir=refresh_dir,
            check_dirs=[refresh_dir],
            target="http://127.0.0.1:9997",
        )
        refresh_after = build_single_artifact_health(refresh_dir)
        review_blockers_json = refresh_dir / REVIEW_BLOCKERS_ARTIFACT
        review_blockers_markdown = refresh_dir / REVIEW_BLOCKERS_MARKDOWN_ARTIFACT
        write_json(review_blockers_json, {"generated_at": utc_now(), "status": "ready", "summary": {}})
        review_blockers_markdown.write_text("# Review blockers\n\nready\n", encoding="utf-8")
        review_blockers_stale_before = build_single_artifact_health(refresh_dir)
        review_blockers_refreshed_manifests = refresh_manifests_for_artifact_outputs(
            output_paths=[review_blockers_json, review_blockers_markdown],
            artifact_dir=refresh_dir,
            check_dirs=[],
            target="http://127.0.0.1:9997",
            command="review-blockers",
        )
        review_blockers_refresh_after = build_single_artifact_health(refresh_dir)
        (refresh_dir / "report.md").write_text("refreshed report\n", encoding="utf-8")
        (refresh_dir / "index.html").write_text("<html>refreshed</html>\n", encoding="utf-8")
        report_refreshed_manifests = refresh_manifests_for_artifact_outputs(
            output_paths=[refresh_dir / "report.md", refresh_dir / "index.html"],
            artifact_dir=refresh_dir,
            check_dirs=[],
            target="http://127.0.0.1:9997",
            command="report",
        )
        report_refresh_after = build_single_artifact_health(refresh_dir)

        derived_dir.mkdir(parents=True)
        for name in REQUIRED_ARTIFACTS:
            write_sample_artifact(derived_dir / name)
        write_json(derived_dir / REVIEW_BLOCKERS_ARTIFACT, {"generated_at": utc_now(), "status": "ready", "summary": {}})
        (derived_dir / REVIEW_BLOCKERS_MARKDOWN_ARTIFACT).write_text("# Review blockers\n\nold\n", encoding="utf-8")
        write_json(derived_dir / "attack-strategy.json", {"generated_at": utc_now(), "status": "ready", "summary": {}})
        derived_baseline_ns = 1_710_000_000_000_000_000
        for path in derived_dir.iterdir():
            if path.is_file():
                set_mtime_ns(path, derived_baseline_ns)
        for name in ["verification-queue.json", REVIEW_BLOCKERS_ARTIFACT, "attack-strategy.json"]:
            path = derived_dir / name
            if path.exists():
                set_mtime_ns(path, derived_baseline_ns + 2_000)
        write_artifact_manifest(derived_dir, "http://127.0.0.1:9997", command="self-test-artifact-health")
        derived_stale = build_single_artifact_health(derived_dir)
        derived_stale_summaries = [
            format_artifact_health_stale_issue(issue)
            for issue in derived_stale.get("stale_inputs", []) or []
        ]
        for name in ["report.md", "index.html", "reproduction-steps.md", REVIEW_BLOCKERS_MARKDOWN_ARTIFACT]:
            path = derived_dir / name
            path.write_text(f"refreshed {name}\n", encoding="utf-8")
            set_mtime_ns(path, derived_baseline_ns + 3_000)
        derived_refreshed_manifests = refresh_manifests_for_artifact_outputs(
            output_paths=[
                derived_dir / "report.md",
                derived_dir / "index.html",
                derived_dir / "reproduction-steps.md",
                derived_dir / REVIEW_BLOCKERS_MARKDOWN_ARTIFACT,
            ],
            artifact_dir=derived_dir,
            check_dirs=[],
            target="http://127.0.0.1:9997",
            command="self-test-derived-refresh",
        )
        derived_refresh_after = build_single_artifact_health(derived_dir)

        suite_root = root / "suite-root"
        suite_default_dir = suite_root / "regression-default"
        suite_discovered_dir = suite_root / "regression-discovered"
        suite_scratch_dir = suite_root / "scratch"
        for directory in [suite_root, suite_default_dir, suite_discovered_dir, suite_scratch_dir]:
            directory.mkdir(parents=True)
            write_json(directory / "ok.json", {"status": "ready"})
        write_json(
            suite_root / "regression-suite.json",
            {
                "generated_at": utc_now(),
                "status": "needs-human-review",
                "artifact_dirs": {
                    "suite": str(suite_root),
                    "default": str(suite_default_dir),
                    "discovered": str(suite_discovered_dir),
                },
            },
        )
        write_minimal_manifest(suite_root, ["ok.json", "regression-suite.json"])
        write_minimal_manifest(suite_default_dir, ["ok.json"])
        write_minimal_manifest(suite_discovered_dir, ["ok.json"])
        write_minimal_manifest(suite_scratch_dir, ["ok.json"])
        discovered_suite_dirs = discover_artifact_health_dirs(suite_root)
        discovered_suite_dir_names = [path.name for path in discovered_suite_dirs]
        discovered_suite_health = build_artifact_health(discovered_suite_dirs)

        missing_suite_root = root / "suite-missing"
        missing_suite_default_dir = missing_suite_root / "regression-default"
        missing_suite_discovered_dir = missing_suite_root / "regression-discovered"
        for directory in [missing_suite_root, missing_suite_default_dir]:
            directory.mkdir(parents=True)
            write_json(directory / "ok.json", {"status": "ready"})
        write_json(
            missing_suite_root / "regression-suite.json",
            {
                "generated_at": utc_now(),
                "status": "failed",
                "artifact_dirs": {
                    "suite": str(missing_suite_root),
                    "default": str(missing_suite_default_dir),
                    "discovered": str(missing_suite_discovered_dir),
                },
            },
        )
        write_minimal_manifest(missing_suite_root, ["ok.json", "regression-suite.json"])
        write_minimal_manifest(missing_suite_default_dir, ["ok.json"])
        missing_suite_dirs = discover_artifact_health_dirs(missing_suite_root)
        missing_suite_dir_names = [path.name for path in missing_suite_dirs]
        missing_suite_health = build_artifact_health(missing_suite_dirs)

    def stale_reasons(item: dict[str, Any]) -> set[str]:
        return {str(entry.get("reason")) for entry in item.get("stale_inputs", []) or []}

    assertions = [
        {
            "id": "healthy-manifest-passes",
            "passed": healthy.get("status") == "healthy" and not healthy.get("stale_inputs"),
            "expected": "healthy with no stale inputs",
            "actual": {"status": healthy.get("status"), "stale_inputs": healthy.get("stale_inputs")},
        },
        {
            "id": "modified-artifact-fails",
            "passed": modified.get("status") == "failed" and "manifest-hash-mismatch" in stale_reasons(modified),
            "expected": "manifest-hash-mismatch",
            "actual": modified.get("stale_inputs"),
        },
        {
            "id": "missing-artifact-fails",
            "passed": missing.get("status") == "failed" and "missing-after-manifest" in stale_reasons(missing),
            "expected": "missing-after-manifest",
            "actual": missing.get("stale_inputs"),
        },
        {
            "id": "untracked-artifact-fails",
            "passed": untracked.get("status") == "failed" and "not-listed-in-manifest" in stale_reasons(untracked),
            "expected": "not-listed-in-manifest",
            "actual": untracked.get("stale_inputs"),
        },
        {
            "id": "aggregate-counts-stale-inputs",
            "passed": aggregate.get("status") == "failed" and aggregate.get("summary", {}).get("stale_input_count") == 3,
            "expected": 3,
            "actual": aggregate.get("summary", {}).get("stale_input_count"),
        },
        {
            "id": "artifact-health-output-refreshes-manifest",
            "passed": (
                refresh_stale_before.get("status") == "failed"
                and refresh_after.get("status") == "healthy"
                and refreshed_health.get("status") == "healthy"
                and len(refreshed_manifests) == 1
                and not refresh_after.get("stale_inputs")
            ),
            "expected": "writing artifact-health.json then refreshing manifest returns to healthy",
            "actual": {
                "before_status": refresh_stale_before.get("status"),
                "refreshed_health_status": refreshed_health.get("status"),
                "after_status": refresh_after.get("status"),
                "refreshed_manifests": refreshed_manifests,
                "after_stale_inputs": refresh_after.get("stale_inputs"),
            },
        },
        {
            "id": "multi-output-refreshes-manifest",
            "passed": (
                review_blockers_stale_before.get("status") == "failed"
                and review_blockers_refresh_after.get("status") == "failed"
                and "derived-report-stale" in stale_reasons(review_blockers_refresh_after)
                and len(review_blockers_refreshed_manifests) == 1
            ),
            "expected": "multiple generated outputs refresh the manifest but leave report freshness stale",
            "actual": {
                "before_status": review_blockers_stale_before.get("status"),
                "after_status": review_blockers_refresh_after.get("status"),
                "refreshed_manifests": review_blockers_refreshed_manifests,
                "after_stale_inputs": review_blockers_refresh_after.get("stale_inputs"),
            },
        },
        {
            "id": "report-refresh-clears-derived-staleness",
            "passed": (
                report_refresh_after.get("status") == "healthy"
                and len(report_refreshed_manifests) == 1
                and not report_refresh_after.get("stale_inputs")
            ),
            "expected": "refreshing report outputs clears derived-report-stale",
            "actual": {
                "after_status": report_refresh_after.get("status"),
                "refreshed_manifests": report_refreshed_manifests,
                "after_stale_inputs": report_refresh_after.get("stale_inputs"),
            },
        },
        {
            "id": "derived-artifact-freshness-detects-stale-outputs",
            "passed": (
                derived_stale.get("status") == "failed"
                and "derived-report-stale" in stale_reasons(derived_stale)
                and "derived-reproduction-steps-stale" in stale_reasons(derived_stale)
                and "derived-review-blockers-markdown-stale" in stale_reasons(derived_stale)
            ),
            "expected": "derived stale report, reproduction, and review-blocker markdown outputs",
            "actual": derived_stale.get("stale_inputs"),
        },
        {
            "id": "stale-input-summary-includes-actionable-context",
            "passed": any(
                "review-blockers.md" in line
                and "reason=derived-review-blockers-markdown-stale" in line
                and "newer_inputs=review-blockers.json" in line
                and "next_step=Run `python3 scripts/inferforge.py review-blockers`" in line
                for line in derived_stale_summaries
            ),
            "expected": "stale summaries include file, reason, newer inputs, and next step",
            "actual": derived_stale_summaries,
        },
        {
            "id": "derived-artifact-refresh-clears-staleness",
            "passed": (
                derived_refresh_after.get("status") == "healthy"
                and len(derived_refreshed_manifests) == 1
                and not derived_refresh_after.get("stale_inputs")
            ),
            "expected": "refreshing derived outputs clears all freshness issues",
            "actual": {
                "after_status": derived_refresh_after.get("status"),
                "refreshed_manifests": derived_refreshed_manifests,
                "after_stale_inputs": derived_refresh_after.get("stale_inputs"),
            },
        },
        {
            "id": "discover-child-runs-prefers-regression-suite-artifact-dirs",
            "passed": (
                discovered_suite_dir_names
                == ["suite-root", "regression-default", "regression-discovered"]
                and "scratch" not in discovered_suite_dir_names
                and discovered_suite_health.get("status") == "healthy"
            ),
            "expected": "discover-child-runs checks only root plus regression-suite managed child artifact dirs when regression-suite.json exists",
            "actual": {
                "discovered_dirs": discovered_suite_dir_names,
                "health_status": discovered_suite_health.get("status"),
                "status_counts": discovered_suite_health.get("summary", {}).get("status_counts"),
            },
        },
        {
            "id": "discover-child-runs-reports-missing-regression-suite-dirs",
            "passed": (
                missing_suite_dir_names
                == ["suite-missing", "regression-default", "regression-discovered"]
                and missing_suite_health.get("status") == "failed"
                and str(missing_suite_discovered_dir) in missing_suite_health.get("summary", {}).get("failed_dirs", [])
            ),
            "expected": "regression-suite managed dirs are checked even when a child dir or manifest is missing",
            "actual": {
                "discovered_dirs": missing_suite_dir_names,
                "health_status": missing_suite_health.get("status"),
                "failed_dirs": missing_suite_health.get("summary", {}).get("failed_dirs"),
            },
        },
    ]
    failed = [item for item in assertions if not item["passed"]]
    return {
        "generated_at": utc_now(),
        "status": "failed" if failed else "passed",
        "summary": {
            "assertions": len(assertions),
            "failed": len(failed),
            "aggregate_status": aggregate.get("status"),
            "stale_input_count": aggregate.get("summary", {}).get("stale_input_count"),
            "manifest_refreshes": (
                len(refreshed_manifests)
                + len(review_blockers_refreshed_manifests)
                + len(report_refreshed_manifests)
                + len(derived_refreshed_manifests)
            ),
        },
        "cases": {
            "healthy": healthy,
            "modified": modified,
            "missing": missing,
            "untracked": untracked,
            "aggregate": aggregate,
            "refresh_stale_before": refresh_stale_before,
            "refreshed_health": refreshed_health,
            "refresh_after": refresh_after,
            "refreshed_manifests": refreshed_manifests,
            "review_blockers_stale_before": review_blockers_stale_before,
            "review_blockers_refresh_after": review_blockers_refresh_after,
            "review_blockers_refreshed_manifests": review_blockers_refreshed_manifests,
            "report_refresh_after": report_refresh_after,
            "report_refreshed_manifests": report_refreshed_manifests,
            "derived_stale": derived_stale,
            "derived_stale_summaries": derived_stale_summaries,
            "derived_refresh_after": derived_refresh_after,
            "derived_refreshed_manifests": derived_refreshed_manifests,
            "regression_suite_discovery": {
                "discovered_dirs": discovered_suite_dir_names,
                "health": discovered_suite_health,
            },
            "missing_regression_suite_discovery": {
                "discovered_dirs": missing_suite_dir_names,
                "health": missing_suite_health,
            },
        },
        "assertions": assertions,
        "safety": "Synthetic artifact-health self-test. It writes temporary local files only and sends no requests.",
    }


def build_manifest_refresh_selftest() -> dict[str, Any]:
    compound_statement_types = (
        ast.If,
        ast.For,
        ast.While,
        ast.With,
        ast.AsyncWith,
        ast.Try,
        ast.Match,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )

    def parser_subcommands() -> set[str]:
        parser = build_parser()
        for action in parser._actions:
            choices = getattr(action, "choices", None)
            if isinstance(choices, dict):
                return {str(name) for name in choices}
        return set()

    def refresh_expectation(
        command: str,
        function: str,
        *,
        min_refreshes: int = 1,
        min_prints: int = 1,
    ) -> dict[str, Any]:
        return {
            "command": command,
            "function": function,
            "mode": "refresh-current-manifest",
            "markers": {
                "refresh_current_artifact_manifest(": min_refreshes,
                "print_refreshed_manifests(": min_prints,
            },
        }

    def called_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    def statement_has_call(statement: ast.AST, name: str) -> bool:
        return any(
            isinstance(node, ast.Call) and called_name(node.func) == name
            for node in ast.walk(statement)
        )

    def statement_writes_regression_suite(statement: ast.AST) -> bool:
        for node in ast.walk(statement):
            if not isinstance(node, ast.Call) or called_name(node.func) != "write_json":
                continue
            if node.args and any(
                isinstance(child, ast.Constant) and child.value == "regression-suite.json"
                for child in ast.walk(node.args[0])
            ):
                return True
        return False

    def is_return_one(statement: ast.AST) -> bool:
        return (
            isinstance(statement, ast.Return)
            and isinstance(statement.value, ast.Constant)
            and statement.value.value == 1
        )

    def regression_suite_return_manifest_checks() -> list[dict[str, Any]]:
        function = globals().get("run_regression_suite")
        if not function:
            return [
                {
                    "path": "run_regression_suite",
                    "passed": False,
                    "reason": "function-not-found",
                }
            ]

        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
        function_def = next((node for node in tree.body if isinstance(node, ast.FunctionDef)), None)
        if not function_def:
            return [
                {
                    "path": "run_regression_suite",
                    "passed": False,
                    "reason": "function-def-not-found",
                }
            ]

        checks: list[dict[str, Any]] = []

        def walk_block(
            block: list[ast.stmt],
            *,
            path: str,
            suite_written: bool,
            manifest_after_suite_write: bool,
        ) -> None:
            current_suite_written = suite_written
            current_manifest_after_suite_write = manifest_after_suite_write
            for index, statement in enumerate(block):
                statement_path = f"{path}/{type(statement).__name__}:{index}"
                if not isinstance(statement, compound_statement_types):
                    if statement_writes_regression_suite(statement):
                        current_suite_written = True
                        current_manifest_after_suite_write = False
                    if statement_has_call(statement, "write_artifact_manifest") and current_suite_written:
                        current_manifest_after_suite_write = True
                    if is_return_one(statement):
                        checks.append(
                            {
                                "path": statement_path,
                                "passed": (
                                    current_manifest_after_suite_write
                                    if current_suite_written
                                    else False
                                ),
                                "suite_written": current_suite_written,
                                "manifest_after_suite_write": current_manifest_after_suite_write,
                            }
                        )

                if isinstance(statement, (ast.If, ast.For, ast.While, ast.With, ast.AsyncWith)):
                    walk_block(
                        statement.body,
                        path=f"{statement_path}/body",
                        suite_written=current_suite_written,
                        manifest_after_suite_write=current_manifest_after_suite_write,
                    )
                    orelse = getattr(statement, "orelse", [])
                    if orelse:
                        walk_block(
                            orelse,
                            path=f"{statement_path}/orelse",
                            suite_written=current_suite_written,
                            manifest_after_suite_write=current_manifest_after_suite_write,
                        )
                elif isinstance(statement, ast.Try):
                    walk_block(
                        statement.body,
                        path=f"{statement_path}/body",
                        suite_written=current_suite_written,
                        manifest_after_suite_write=current_manifest_after_suite_write,
                    )
                    for handler_index, handler in enumerate(statement.handlers):
                        walk_block(
                            handler.body,
                            path=f"{statement_path}/handler:{handler_index}",
                            suite_written=current_suite_written,
                            manifest_after_suite_write=current_manifest_after_suite_write,
                        )
                    if statement.orelse:
                        walk_block(
                            statement.orelse,
                            path=f"{statement_path}/orelse",
                            suite_written=current_suite_written,
                            manifest_after_suite_write=current_manifest_after_suite_write,
                        )
                    if statement.finalbody:
                        walk_block(
                            statement.finalbody,
                            path=f"{statement_path}/finally",
                            suite_written=current_suite_written,
                            manifest_after_suite_write=current_manifest_after_suite_write,
                        )
                elif isinstance(statement, ast.Match):
                    for case_index, match_case in enumerate(statement.cases):
                        walk_block(
                            match_case.body,
                            path=f"{statement_path}/case:{case_index}",
                            suite_written=current_suite_written,
                            manifest_after_suite_write=current_manifest_after_suite_write,
                        )

        walk_block(
            function_def.body,
            path="run_regression_suite",
            suite_written=False,
            manifest_after_suite_write=False,
        )
        return checks

    expectations = [
        {
            "command": "audit",
            "function": "run_audit",
            "mode": "final-manifest",
            "markers": {"write_artifact_manifest(": 1},
        },
        {
            "command": "manifest",
            "function": "run_manifest",
            "mode": "final-manifest",
            "markers": {"write_artifact_manifest(": 1},
        },
        {
            "command": "regression-suite",
            "function": "run_regression_suite",
            "mode": "final-manifest",
            "markers": {"write_artifact_manifest(": 3},
        },
        {
            "command": "artifact-health",
            "function": "run_artifact_health",
            "mode": "managed-output-refresh",
            "markers": {"write_artifact_health_artifact(": 1},
        },
        {
            "command": "review-blockers",
            "function": "run_review_blockers",
            "mode": "multi-directory-refresh",
            "markers": {"refresh_manifests_for_artifact_outputs(": 1},
        },
        refresh_expectation("profile", "run_profile"),
        refresh_expectation("plan", "run_plan"),
        refresh_expectation("review-candidates", "run_review_candidates"),
        refresh_expectation("promote-observation-candidate", "run_promote_observation_candidate"),
        refresh_expectation("discover-profile", "run_discover_profile", min_refreshes=2, min_prints=2),
        refresh_expectation("collect", "run_collect"),
        refresh_expectation("burp-observe", "run_burp_observe", min_refreshes=3, min_prints=3),
        refresh_expectation("burp-sync", "run_burp_sync", min_refreshes=4, min_prints=4),
        refresh_expectation("import-burp-history", "run_import_burp_history", min_refreshes=2, min_prints=2),
        refresh_expectation("attack-strategy", "run_attack_strategy"),
        refresh_expectation("gate", "run_gate", min_refreshes=2, min_prints=2),
        refresh_expectation("coverage", "run_coverage"),
        refresh_expectation("burp-observation-coverage", "run_burp_observation_coverage"),
        refresh_expectation("discovery-coverage", "run_discovery_coverage"),
        refresh_expectation("response-deltas", "run_response_deltas"),
        refresh_expectation("source-peek-requests", "run_source_peek_requests"),
        refresh_expectation("evidence-chain", "run_evidence_chain"),
        refresh_expectation("evidence-appendix", "run_evidence_appendix"),
        refresh_expectation("report", "run_report"),
        refresh_expectation("verification-queue", "run_verification_queue"),
        refresh_expectation("adjudicate", "run_adjudicate"),
        refresh_expectation("capabilities", "run_capabilities"),
        refresh_expectation("readiness", "run_readiness"),
        refresh_expectation("decode-transactions", "run_decode_transactions"),
        refresh_expectation("self-test-profile-routing", "run_profile_routing_selftest"),
        refresh_expectation("self-test-discovery-coverage", "run_discovery_coverage_selftest"),
        refresh_expectation("self-test-command-safety", "run_command_safety_selftest"),
        refresh_expectation("self-test-review-blockers", "run_review_blockers_selftest"),
        refresh_expectation("self-test-artifact-health", "run_artifact_health_selftest"),
        refresh_expectation("self-test-manifest-refresh", "run_manifest_refresh_selftest"),
        refresh_expectation("self-test-no-write", "run_no_write_selftest"),
        refresh_expectation("self-test-transactions", "run_transaction_decoder_selftest"),
        refresh_expectation("collect-quote", "run_collect_quote", min_refreshes=2, min_prints=2),
        refresh_expectation("collect-orca-baseline", "run_collect_orca_baseline", min_refreshes=2, min_prints=2),
    ]

    expected_commands = {str(item["command"]) for item in expectations}
    registered_commands = parser_subcommands()
    missing_expectations = sorted(registered_commands - expected_commands)
    stale_expectations = sorted(expected_commands - registered_commands)
    assertions = []
    cases = []
    for expectation in expectations:
        function_name = expectation["function"]
        function = globals().get(function_name)
        source = inspect.getsource(function) if function else ""
        marker_counts = {
            marker: source.count(marker)
            for marker in expectation["markers"]
        }
        missing_markers = [
            {
                "marker": marker,
                "expected_min": expected_min,
                "actual": marker_counts.get(marker, 0),
            }
            for marker, expected_min in expectation["markers"].items()
            if marker_counts.get(marker, 0) < expected_min
        ]
        case = {
            "command": expectation["command"],
            "function": function_name,
            "mode": expectation["mode"],
            "marker_counts": marker_counts,
            "missing_markers": missing_markers,
        }
        cases.append(case)
        assertions.append(
            {
                "id": f"{expectation['command']}-manifest-refresh-marker",
                "passed": bool(function) and not missing_markers,
                "expected": expectation["markers"],
                "actual": marker_counts if function else "function-not-found",
            }
        )
    assertions.append(
        {
            "id": "parser-command-manifest-refresh-coverage",
            "passed": not missing_expectations and not stale_expectations,
            "expected": "every parser subcommand has a manifest-refresh self-test expectation",
            "actual": {
                "registered_commands": sorted(registered_commands),
                "missing_expectations": missing_expectations,
                "stale_expectations": stale_expectations,
            },
        }
    )
    regression_return_checks = regression_suite_return_manifest_checks()
    cases.append(
        {
            "command": "regression-suite",
            "function": "run_regression_suite",
            "mode": "return-path-manifest-refresh",
            "return_checks": regression_return_checks,
        }
    )
    assertions.append(
        {
            "id": "regression-suite-return-paths-refresh-manifest",
            "passed": bool(regression_return_checks)
            and all(item.get("passed") for item in regression_return_checks),
            "expected": "every run_regression_suite return 1 path follows a regression-suite.json write with write_artifact_manifest",
            "actual": regression_return_checks,
        }
    )

    mode_counts: dict[str, int] = {}
    for item in expectations:
        increment_count(mode_counts, item["mode"])
    failed = [item for item in assertions if not item["passed"]]
    return {
        "generated_at": utc_now(),
        "status": "failed" if failed else "passed",
        "summary": {
            "commands": len(expectations),
            "assertions": len(assertions),
            "failed": len(failed),
            "mode_counts": mode_counts,
            "registered_commands": len(registered_commands),
            "missing_expectations": missing_expectations,
            "stale_expectations": stale_expectations,
        },
        "cases": cases,
        "assertions": assertions,
        "safety": "Static source self-test. It reads local InferForge command functions only and sends no requests.",
    }


def build_no_write_selftest() -> dict[str, Any]:
    target = "http://127.0.0.1:9997"

    def stub_capabilities(target_url: str, artifact_dir: Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "generated_at": utc_now(),
            "target": {
                "base_url": target_url,
                "health_path": "/health",
                "health_status": 200,
                "reachable": True,
                "service": "no-write-selftest",
                "m0_key_present": False,
            },
            "burp": {
                "mcp_endpoint": "http://127.0.0.1:9876",
                "mcp_port_open": True,
                "proxy_8080_open": True,
                "proxy_8081_open": False,
                "codex_mcp_get_burp_ok": True,
                "check_script_ok": True,
                "approval_sensitive_tools": {
                    "observed_get_proxy_http_history": "stubbed",
                    "observed_send_http1_request": "stubbed",
                    "observed_create_repeater_tab": "stubbed",
                    "observed_set_proxy_intercept_state": "stubbed",
                },
            },
            "artifacts": {"directory": str(artifact_dir)},
        }

    def run_cli(argv: list[str]) -> tuple[int, list[str]]:
        parser = build_parser()
        parsed_args = parser.parse_args(argv)
        stdout_buffer = io.StringIO()
        with contextlib.redirect_stdout(stdout_buffer):
            return_code = parsed_args.func(parsed_args)
        return return_code, stdout_buffer.getvalue().splitlines()

    with tempfile.TemporaryDirectory(prefix="inferforge-no-write-selftest-") as temp_dir:
        root = Path(temp_dir)
        profile_path = root / "profile.json"
        profile = {
            "schema_version": 1,
            "name": "no-write-selftest",
            "display_name": "No-Write Self-Test",
            "default_target": target,
            "default_source_root": str(root),
            "strategy_sets": ["nextjs-api-routes"],
            "clusters": [
                {
                    "id": "no-write",
                    "method": "GET",
                    "path": "/api/no-write/status",
                    "kind": "app-route",
                    "priority": "medium",
                    "strategy_set": "nextjs-api-routes",
                    "paths": ["/api/no-write/status"],
                    "methods": ["GET"],
                }
            ],
            "review_observation_candidates": [
                {
                    "id": "review_no_write_candidate",
                    "type": "burp-http-observation",
                    "status": "review-only",
                    "method": "GET",
                    "path_template": "/api/no-write/{path*}",
                    "cluster": "no-write",
                    "example_path": "/api/no-write/status",
                    "source_refs": ["no-write.config.ts"],
                    "rewrites": [
                        {
                            "source": "/api/no-write/:path*",
                            "source_pattern": "/api/no-write/{path*}",
                            "destination_resolved": "https://example.test/:path*",
                            "destination_template": "${NO_WRITE_TARGET}/:path*",
                            "phase": "array",
                        }
                    ],
                    "fixed_upstreams": ["https://example.test"],
                    "approval_required": [
                        "Choose one known safe read-only path.",
                        "Confirm the upstream request is non-mutating.",
                    ],
                    "promote_to_burp_observation_plan": {
                        "id": "burp_observe_no_write_reviewed_path",
                        "method": "GET",
                        "path": PLACEHOLDER_APPROVED_CONCRETE_PATH,
                        "expected_statuses": [200, 204, 400, 403, 404, 405, 502],
                        "cluster": "no-write",
                    },
                    "safety": "Synthetic no-write candidate.",
                }
            ],
        }
        write_json(profile_path, profile)
        invalid_profile_path = root / "invalid-profile.json"
        invalid_profile = json_clone(profile)
        invalid_profile["strategy_sets"] = []
        write_json(invalid_profile_path, invalid_profile)
        review_candidates_output_dir = root / "review-candidates-output"
        plan_output_dir = root / "plan-output"
        capabilities_output_dir = root / "capabilities-output"
        readiness_output_dir = root / "readiness-output"
        attack_strategy_output_dir = root / "attack-strategy-output"
        verification_queue_output_dir = root / "verification-queue-output"
        promote_output_dir = root / "promote-output"
        invalid_promote_output_dir = root / "invalid-promote-output"

        original_build_capabilities = globals()["build_capabilities"]
        try:
            globals()["build_capabilities"] = stub_capabilities
            review_candidates_return_code, review_candidates_stdout = run_cli(
                [
                    "--profile",
                    str(profile_path),
                    "--artifact-dir",
                    str(review_candidates_output_dir),
                    "--target",
                    target,
                    "--source-root",
                    str(root),
                    "review-candidates",
                    "--no-write",
                ]
            )
            plan_return_code, plan_stdout = run_cli(
                [
                    "--profile",
                    str(profile_path),
                    "--artifact-dir",
                    str(plan_output_dir),
                    "--target",
                    target,
                    "--source-root",
                    str(root),
                    "plan",
                    "--no-write",
                ]
            )
            capabilities_return_code, capabilities_stdout = run_cli(
                [
                    "--profile",
                    str(profile_path),
                    "--artifact-dir",
                    str(capabilities_output_dir),
                    "--target",
                    target,
                    "--source-root",
                    str(root),
                    "capabilities",
                    "--no-write",
                ]
            )
            readiness_return_code, readiness_stdout = run_cli(
                [
                    "--profile",
                    str(profile_path),
                    "--artifact-dir",
                    str(readiness_output_dir),
                    "--target",
                    target,
                    "--source-root",
                    str(root),
                    "readiness",
                    "--no-write",
                ]
            )
            attack_strategy_return_code, attack_strategy_stdout = run_cli(
                [
                    "--profile",
                    str(profile_path),
                    "--artifact-dir",
                    str(attack_strategy_output_dir),
                    "--target",
                    target,
                    "--source-root",
                    str(root),
                    "attack-strategy",
                    "--no-write",
                ]
            )
            verification_queue_return_code, verification_queue_stdout = run_cli(
                [
                    "--profile",
                    str(profile_path),
                    "--artifact-dir",
                    str(verification_queue_output_dir),
                    "--target",
                    target,
                    "--source-root",
                    str(root),
                    "verification-queue",
                    "--no-write",
                ]
            )
            promote_return_code, promote_stdout = run_cli(
                [
                    "--profile",
                    str(profile_path),
                    "--artifact-dir",
                    str(promote_output_dir),
                    "--target",
                    target,
                    "--source-root",
                    str(root),
                    "promote-observation-candidate",
                    "--candidate-id",
                    "review_no_write_candidate",
                    "--path",
                    "/api/no-write/status",
                    "--no-write",
                ]
            )
            invalid_promote_return_code, invalid_promote_stdout = run_cli(
                [
                    "--profile",
                    str(invalid_profile_path),
                    "--artifact-dir",
                    str(invalid_promote_output_dir),
                    "--target",
                    target,
                    "--source-root",
                    str(root),
                    "promote-observation-candidate",
                    "--candidate-id",
                    "review_no_write_candidate",
                    "--path",
                    "/api/no-write/status",
                    "--no-write",
                ]
            )
        finally:
            globals()["build_capabilities"] = original_build_capabilities

        output_paths = {
            "review_candidates_dir": review_candidates_output_dir.exists(),
            "review_candidates_json": (review_candidates_output_dir / "review-observation-candidates.json").exists(),
            "review_candidates_profile_json": (review_candidates_output_dir / TARGET_PROFILE_ARTIFACT).exists(),
            "review_candidates_manifest": (review_candidates_output_dir / MANIFEST_NAME).exists(),
            "plan_dir": plan_output_dir.exists(),
            "plan_target_profile_json": (plan_output_dir / TARGET_PROFILE_ARTIFACT).exists(),
            "plan_endpoint_clusters_json": (plan_output_dir / "endpoint-clusters.json").exists(),
            "plan_probe_ranking_json": (plan_output_dir / "probe-ranking.json").exists(),
            "plan_probe_plan_json": (plan_output_dir / "probe-plan.json").exists(),
            "plan_attack_strategy_json": (plan_output_dir / "attack-strategy.json").exists(),
            "plan_manifest": (plan_output_dir / MANIFEST_NAME).exists(),
            "capabilities_dir": capabilities_output_dir.exists(),
            "capabilities_json": (capabilities_output_dir / "burp-capabilities.json").exists(),
            "capabilities_manifest": (capabilities_output_dir / MANIFEST_NAME).exists(),
            "readiness_dir": readiness_output_dir.exists(),
            "readiness_capabilities_json": (readiness_output_dir / "burp-capabilities.json").exists(),
            "readiness_json": (readiness_output_dir / "environment-readiness.json").exists(),
            "readiness_manifest": (readiness_output_dir / MANIFEST_NAME).exists(),
            "attack_strategy_dir": attack_strategy_output_dir.exists(),
            "attack_strategy_target_profile_json": (attack_strategy_output_dir / TARGET_PROFILE_ARTIFACT).exists(),
            "attack_strategy_json": (attack_strategy_output_dir / "attack-strategy.json").exists(),
            "attack_strategy_manifest": (attack_strategy_output_dir / MANIFEST_NAME).exists(),
            "verification_queue_dir": verification_queue_output_dir.exists(),
            "verification_queue_target_profile_json": (verification_queue_output_dir / TARGET_PROFILE_ARTIFACT).exists(),
            "verification_queue_json": (verification_queue_output_dir / "verification-queue.json").exists(),
            "verification_queue_reproduction_steps": (verification_queue_output_dir / "reproduction-steps.md").exists(),
            "verification_queue_review_blockers": (verification_queue_output_dir / REVIEW_BLOCKERS_ARTIFACT).exists(),
            "verification_queue_review_blockers_markdown": (
                verification_queue_output_dir / REVIEW_BLOCKERS_MARKDOWN_ARTIFACT
            ).exists(),
            "verification_queue_manifest": (verification_queue_output_dir / MANIFEST_NAME).exists(),
            "promote_dir": promote_output_dir.exists(),
            "promote_reviewed_profile": (promote_output_dir / "reviewed-profile.json").exists(),
            "promote_validation": (promote_output_dir / "reviewed-profile-validation.json").exists(),
            "promote_artifact": (promote_output_dir / "reviewed-observation-promotion.json").exists(),
            "promote_manifest": (promote_output_dir / MANIFEST_NAME).exists(),
            "invalid_promote_dir": invalid_promote_output_dir.exists(),
            "invalid_promote_reviewed_profile": (invalid_promote_output_dir / "reviewed-profile.json").exists(),
            "invalid_promote_validation": (invalid_promote_output_dir / "reviewed-profile-validation.json").exists(),
            "invalid_promote_artifact": (invalid_promote_output_dir / "reviewed-observation-promotion.json").exists(),
            "invalid_promote_manifest": (invalid_promote_output_dir / MANIFEST_NAME).exists(),
        }

    review_candidates_stdout_text = "\n".join(review_candidates_stdout)
    plan_stdout_text = "\n".join(plan_stdout)
    capabilities_stdout_text = "\n".join(capabilities_stdout)
    attack_strategy_stdout_text = "\n".join(attack_strategy_stdout)
    verification_queue_stdout_text = "\n".join(verification_queue_stdout)
    promote_stdout_text = "\n".join(promote_stdout)
    invalid_promote_stdout_text = "\n".join(invalid_promote_stdout)
    attack_strategy_overflow_no_write = format_attack_strategy_waiting_action_overflow(
        5,
        3,
        no_write=True,
        output_path=attack_strategy_output_dir / "attack-strategy.json",
    ) or ""
    attack_strategy_overflow_write = format_attack_strategy_waiting_action_overflow(
        5,
        3,
        no_write=False,
        output_path=attack_strategy_output_dir / "attack-strategy.json",
    ) or ""
    readiness_overflow_no_write = format_readiness_next_step_overflow(
        5,
        3,
        no_write=True,
        output_path=readiness_output_dir / "environment-readiness.json",
    ) or ""
    readiness_overflow_write = format_readiness_next_step_overflow(
        5,
        3,
        no_write=False,
        output_path=readiness_output_dir / "environment-readiness.json",
    ) or ""
    manual_followup_preview_lines = verification_queue_followup_preview_lines(
        {
            "id": "MANUAL-commandless",
            "status": "manual-review",
            "reason": "Review the browser-only flow before adding automated replay.",
            "prerequisites": ["Use Burp built-in browser to exercise the relevant UI flow."],
            "review_candidates": [
                {
                    "id": "review_manual_flow",
                    "type": "server-action-source-review",
                    "path_template": "/api/no-write/{path*}",
                    "source_refs": ["src/app/actions.ts"],
                }
            ],
            "evidence_refs": ["source-peek-results.json", "verification-queue.json"],
            "safety": "Manual source review only; no active request is generated.",
        }
    )
    manual_followup_preview_text = "\n".join(manual_followup_preview_lines)
    ready_followup_preview_lines = verification_queue_followup_preview_lines(
        {"id": "READY-commandless", "status": "ready", "reason": "No preview expected."}
    )
    assertions = [
        {
            "id": "review-candidates-no-write-skips-artifacts",
            "passed": (
                review_candidates_return_code == 0
                and "Review observation candidates: 1" in review_candidates_stdout
                and "review_no_write_candidate" in review_candidates_stdout_text
                and "method=GET" in review_candidates_stdout_text
                and "path_template=/api/no-write/{path*}" in review_candidates_stdout_text
                and "source_refs=no-write.config.ts" in review_candidates_stdout_text
                and "fixed_upstreams=https://example.test" in review_candidates_stdout_text
                and "rewrite=source=/api/no-write/:path* destination=https://example.test/:path* phase=array" in review_candidates_stdout_text
                and "approval_required:" in review_candidates_stdout_text
                and "Choose one known safe read-only path." in review_candidates_stdout_text
                and "promote_to_burp_observation_plan: id=burp_observe_no_write_reviewed_path" in review_candidates_stdout_text
                and f"path={PLACEHOLDER_APPROVED_CONCRETE_PATH}" in review_candidates_stdout_text
                and "command_safety=commands=4" in review_candidates_stdout_text
                and "command_templates:" in review_candidates_stdout_text
                and "[manual-template]" in review_candidates_stdout_text
                and "[review-gated]" in review_candidates_stdout_text
                and "promote-observation-candidate" in review_candidates_stdout_text
                and "--no-write" in review_candidates_stdout_text
                and "No files written (--no-write)." in review_candidates_stdout
                and not any(
                    output_paths[key]
                    for key in [
                        "review_candidates_dir",
                        "review_candidates_json",
                        "review_candidates_profile_json",
                        "review_candidates_manifest",
                    ]
                )
                and not any(line.startswith("Refreshed ") for line in review_candidates_stdout)
            ),
            "expected": "review-candidates --no-write prints candidates without writing artifacts or manifests",
            "actual": {
                "return_code": review_candidates_return_code,
                "stdout": review_candidates_stdout,
                "outputs_exist": output_paths,
            },
        },
        {
            "id": "plan-no-write-skips-artifacts",
            "passed": (
                plan_return_code == 0
                and "Planned " in plan_stdout_text
                and "Selection mode:" in plan_stdout_text
                and "Selected clusters:" in plan_stdout_text
                and "Selected probes:" in plan_stdout
                and "nextjs_no_write_head" in plan_stdout_text
                and "HEAD /api/no-write/status" in plan_stdout_text
                and "score=" in plan_stdout_text
                and "reasons=" in plan_stdout_text
                and "No files written (--no-write)." in plan_stdout
                and not any(
                    output_paths[key]
                    for key in [
                        "plan_dir",
                        "plan_target_profile_json",
                        "plan_endpoint_clusters_json",
                        "plan_probe_ranking_json",
                        "plan_probe_plan_json",
                        "plan_attack_strategy_json",
                        "plan_manifest",
                    ]
                )
                and not any(line.startswith("Refreshed ") for line in plan_stdout)
            ),
            "expected": "plan --no-write prints probe selection without writing artifacts or manifests",
            "actual": {
                "return_code": plan_return_code,
                "stdout": plan_stdout,
                "outputs_exist": output_paths,
            },
        },
        {
            "id": "promote-observation-candidate-no-write-skips-artifacts",
            "passed": (
                promote_return_code == 0
                and "Promotion preview: review_no_write_candidate" in promote_stdout
                and "Observation: GET /api/no-write/status cluster=no-write" in promote_stdout
                and "Profile validation:" in promote_stdout_text
                and "Next commands:" in promote_stdout
                and "burp-sync --observe" in promote_stdout_text
                and "audit --include-external --ws-resource-probes" in promote_stdout_text
                and "No files written (--no-write)." in promote_stdout
                and not any(
                    output_paths[key]
                    for key in [
                        "promote_dir",
                        "promote_reviewed_profile",
                        "promote_validation",
                        "promote_artifact",
                        "promote_manifest",
                    ]
                )
                and not any(line.startswith("Refreshed ") for line in promote_stdout)
            ),
            "expected": "promote-observation-candidate --no-write validates a concrete path without writing artifacts or manifests",
            "actual": {
                "return_code": promote_return_code,
                "stdout": promote_stdout,
                "outputs_exist": output_paths,
            },
        },
        {
            "id": "promote-observation-candidate-no-write-renders-validation-issues",
            "passed": (
                invalid_promote_return_code == 1
                and "Promotion preview: review_no_write_candidate" in invalid_promote_stdout
                and "Profile validation: failed" in invalid_promote_stdout
                and "Validation issues:" in invalid_promote_stdout
                and "no-effective-clusters" in invalid_promote_stdout_text
                and "No files written (--no-write)." in invalid_promote_stdout
                and not any(
                    output_paths[key]
                    for key in [
                        "invalid_promote_dir",
                        "invalid_promote_reviewed_profile",
                        "invalid_promote_validation",
                        "invalid_promote_artifact",
                        "invalid_promote_manifest",
                    ]
                )
                and not any(line.startswith("Refreshed ") for line in invalid_promote_stdout)
            ),
            "expected": "promote-observation-candidate --no-write prints validation issues without writing artifacts when preview validation fails",
            "actual": {
                "return_code": invalid_promote_return_code,
                "stdout": invalid_promote_stdout,
                "outputs_exist": output_paths,
            },
        },
        {
            "id": "verification-queue-no-write-skips-artifacts",
            "passed": (
                verification_queue_return_code == 0
                and "Verification queue: ready" in verification_queue_stdout
                and "Items: 4 total" in verification_queue_stdout_text
                and "Queue items:" in verification_queue_stdout
                and "Command previews:" in verification_queue_stdout
                and "- VERIFY-safe-audit-loop:" in verification_queue_stdout
                and "[ready]" in verification_queue_stdout_text
                and "audit --include-external --ws-resource-probes" in verification_queue_stdout_text
                and "No files written (--no-write)." in verification_queue_stdout
                and not any(
                    output_paths[key]
                    for key in [
                        "verification_queue_dir",
                        "verification_queue_target_profile_json",
                        "verification_queue_json",
                        "verification_queue_reproduction_steps",
                        "verification_queue_review_blockers",
                        "verification_queue_review_blockers_markdown",
                        "verification_queue_manifest",
                    ]
                )
                and not any(line.startswith("Refreshed ") for line in verification_queue_stdout)
            ),
            "expected": "verification-queue --no-write prints queue summary without writing artifacts or manifests",
            "actual": {
                "return_code": verification_queue_return_code,
                "stdout": verification_queue_stdout,
                "outputs_exist": output_paths,
            },
        },
        {
            "id": "verification-queue-followup-preview-renders-commandless-review",
            "passed": (
                "reason=Review the browser-only flow" in manual_followup_preview_text
                and "prerequisite=Use Burp built-in browser" in manual_followup_preview_text
                and "candidate=review_manual_flow" in manual_followup_preview_text
                and "type=server-action-source-review" in manual_followup_preview_text
                and "source_refs=src/app/actions.ts" in manual_followup_preview_text
                and "evidence_refs=source-peek-results.json,verification-queue.json" in manual_followup_preview_text
                and "safety=Manual source review only" in manual_followup_preview_text
                and ready_followup_preview_lines == []
            ),
            "expected": "commandless manual-review queue items render actionable no-write follow-up details",
            "actual": {
                "manual_preview": manual_followup_preview_lines,
                "ready_preview": ready_followup_preview_lines,
            },
        },
        {
            "id": "attack-strategy-no-write-skips-artifacts",
            "passed": (
                attack_strategy_return_code == 0
                and "Attack strategy: needs-burp-history" in attack_strategy_stdout
                and "Coverage:" in attack_strategy_stdout_text
                and "NEXT-transaction-intent-corpus" not in attack_strategy_stdout_text
                and "No files written (--no-write)." in attack_strategy_stdout
                and not any(
                    output_paths[key]
                    for key in [
                        "attack_strategy_dir",
                        "attack_strategy_target_profile_json",
                        "attack_strategy_json",
                        "attack_strategy_manifest",
                    ]
                )
                and not any(line.startswith("Refreshed ") for line in attack_strategy_stdout)
            ),
            "expected": "attack-strategy --no-write prints strategy coverage without writing artifacts or manifests",
            "actual": {
                "return_code": attack_strategy_return_code,
                "stdout": attack_strategy_stdout,
                "outputs_exist": output_paths,
            },
        },
        {
            "id": "attack-strategy-no-write-overflow-rerun-guidance",
            "passed": (
                "2 more waiting actions" in attack_strategy_overflow_no_write
                and "rerun without --no-write" in attack_strategy_overflow_no_write
                and "more in attack-strategy.json" not in attack_strategy_overflow_no_write
                and "2 more in" in attack_strategy_overflow_write
                and "rerun without --no-write" not in attack_strategy_overflow_write
            ),
            "expected": "attack-strategy --no-write overflow points to rerun instead of an unwritten artifact",
            "actual": {
                "no_write": attack_strategy_overflow_no_write,
                "write": attack_strategy_overflow_write,
            },
        },
        {
            "id": "capabilities-no-write-skips-artifacts",
            "passed": (
                capabilities_return_code == 0
                and "Capabilities: ready" in capabilities_stdout
                and "Burp tools:" in capabilities_stdout_text
                and "http_history=stubbed" in capabilities_stdout_text
                and "intercept=stubbed" in capabilities_stdout_text
                and "No files written (--no-write)." in capabilities_stdout
                and not any(output_paths[key] for key in ["capabilities_dir", "capabilities_json", "capabilities_manifest"])
                and not any(line.startswith("Refreshed ") for line in capabilities_stdout)
            ),
            "expected": "capabilities --no-write prints checks without writing artifacts or manifests",
            "actual": {
                "return_code": capabilities_return_code,
                "stdout": capabilities_stdout,
                "outputs_exist": output_paths,
            },
        },
        {
            "id": "readiness-no-write-skips-artifacts",
            "passed": (
                readiness_return_code == 1
                and "Readiness: waiting-for-external-configuration" in readiness_stdout
                and "No files written (--no-write)." in readiness_stdout
                and not any(output_paths[key] for key in ["readiness_dir", "readiness_capabilities_json", "readiness_json", "readiness_manifest"])
                and not any(line.startswith("Refreshed ") for line in readiness_stdout)
            ),
            "expected": "readiness --no-write prints checks without writing artifacts or manifests",
            "actual": {
                "return_code": readiness_return_code,
                "stdout": readiness_stdout,
                "outputs_exist": output_paths,
            },
        },
        {
            "id": "readiness-no-write-overflow-rerun-guidance",
            "passed": (
                "2 more steps" in readiness_overflow_no_write
                and "rerun without --no-write" in readiness_overflow_no_write
                and "more steps in" not in readiness_overflow_no_write
                and "2 more steps in" in readiness_overflow_write
                and "rerun without --no-write" not in readiness_overflow_write
            ),
            "expected": "readiness --no-write overflow points to rerun instead of an unwritten artifact",
            "actual": {
                "no_write": readiness_overflow_no_write,
                "write": readiness_overflow_write,
            },
        },
    ]
    failed = [item for item in assertions if not item["passed"]]
    return {
        "generated_at": utc_now(),
        "status": "failed" if failed else "passed",
        "target": target,
        "summary": {
            "assertions": len(assertions),
            "failed": len(failed),
        },
        "cases": {
            "review_candidates": {
                "return_code": review_candidates_return_code,
                "stdout": review_candidates_stdout,
            },
            "plan": {
                "return_code": plan_return_code,
                "stdout": plan_stdout,
            },
            "invalid_promote": {
                "return_code": invalid_promote_return_code,
                "stdout": invalid_promote_stdout,
            },
            "capabilities": {
                "return_code": capabilities_return_code,
                "stdout": capabilities_stdout,
            },
            "readiness": {
                "return_code": readiness_return_code,
                "stdout": readiness_stdout,
            },
            "attack_strategy": {
                "return_code": attack_strategy_return_code,
                "stdout": attack_strategy_stdout,
            },
            "outputs_exist": output_paths,
        },
        "assertions": assertions,
        "safety": "Synthetic no-write self-test. It monkeypatches capability checks, writes only temporary local input files, and sends no requests.",
    }


def inferforge_cli_command(
    args: argparse.Namespace,
    *,
    profile_path: Path,
    artifact_dir: Path,
    subcommand: str,
    extra: list[str] | None = None,
) -> list[str]:
    profile = load_target_profile(args.profile)
    target = resolve_target(args, profile)
    source_root = resolve_source_root(args, profile)
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--profile",
        repo_relative_or_absolute(profile_path),
        "--artifact-dir",
        repo_relative_or_absolute(artifact_dir),
        "--target",
        target,
        "--source-root",
        repo_relative_or_absolute(source_root),
        "--node",
        args.node,
        subcommand,
    ]
    command.extend(extra or [])
    return command


def run_regression_step(label: str, command: list[str], *, timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    doc: dict[str, Any] = {
        "label": label,
        "command": shlex.join(command),
        "started_at": utc_now(),
    }
    try:
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        duration_ms = int((time.monotonic() - started) * 1000)
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        doc.update(
            {
                "status": "timeout",
                "returncode": None,
                "duration_ms": duration_ms,
                "output_tail": str(output)[-12000:],
                "error": f"Timed out after {timeout} seconds.",
                "finished_at": utc_now(),
            }
        )
        return doc
    except OSError as error:
        duration_ms = int((time.monotonic() - started) * 1000)
        doc.update(
            {
                "status": "failed-to-start",
                "returncode": None,
                "duration_ms": duration_ms,
                "output_tail": "",
                "error": str(error),
                "finished_at": utc_now(),
            }
        )
        return doc

    duration_ms = int((time.monotonic() - started) * 1000)
    doc.update(
        {
            "status": "passed" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "duration_ms": duration_ms,
            "output_tail": proc.stdout[-12000:],
            "finished_at": utc_now(),
        }
    )
    return doc


def regression_step_failed(step: dict[str, Any]) -> bool:
    return step.get("status") != "passed" or step.get("returncode") not in {0}


def remove_stale_probe_results(artifact_dir: Path) -> dict[str, Any]:
    path = artifact_dir / "probe-results.jsonl"
    if not path.exists():
        return {
            "artifact_dir": repo_relative_or_absolute(artifact_dir),
            "file": "probe-results.jsonl",
            "status": "not-present",
        }
    rows = 0
    try:
        rows = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        path.unlink()
    except OSError as error:
        return {
            "artifact_dir": repo_relative_or_absolute(artifact_dir),
            "file": "probe-results.jsonl",
            "status": "failed",
            "rows": rows,
            "error": str(error),
        }
    return {
        "artifact_dir": repo_relative_or_absolute(artifact_dir),
        "file": "probe-results.jsonl",
        "status": "removed",
        "rows": rows,
    }


def regression_suite_status(steps: list[dict[str, Any]], health: dict[str, Any] | None, *, strict: bool) -> str:
    if any(regression_step_failed(step) for step in steps):
        return "failed"
    if not health:
        return "failed"
    health_status = health.get("status")
    if health_status == "failed":
        return "failed"
    if strict and health_status != "healthy":
        return "failed"
    return str(health_status or "unknown")


def decode_base64_candidate(value: str) -> bytes | None:
    normalized = "".join(value.strip().split())
    if len(normalized) < 80:
        return None
    try:
        padded = normalized + ("=" * ((4 - len(normalized) % 4) % 4))
        decoded = base64.b64decode(padded, validate=True)
    except ValueError:
        return None
    if len(decoded) < 48:
        return None
    return decoded


def add_transaction_candidate(
    candidates: list[dict[str, Any]],
    seen: set[str],
    value: str,
    *,
    source: str,
    json_path: str,
    probe_id: str | None = None,
) -> None:
    normalized = "".join(value.strip().split())
    decoded = decode_base64_candidate(normalized)
    if decoded is None:
        return

    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    if digest in seen:
        return
    seen.add(digest)
    candidates.append(
        {
            "id": f"txcand-{digest[:12]}",
            "source": source,
            "probe_id": probe_id,
            "json_path": json_path,
            "base64": normalized,
            "base64_length": len(normalized),
            "base64_sha256": digest,
            "decoded_byte_length": len(decoded),
        }
    )


def walk_transaction_json(
    value: Any,
    *,
    source: str,
    json_path: str,
    probe_id: str | None,
    candidates: list[dict[str, Any]],
    seen: set[str],
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{json_path}.{key}" if json_path else str(key)
            walk_transaction_json(
                child,
                source=source,
                json_path=child_path,
                probe_id=probe_id,
                candidates=candidates,
                seen=seen,
            )
        return

    if isinstance(value, list):
        for index, child in enumerate(value):
            walk_transaction_json(
                child,
                source=source,
                json_path=f"{json_path}[{index}]",
                probe_id=probe_id,
                candidates=candidates,
                seen=seen,
            )
        return

    if not isinstance(value, str):
        return

    path_lower = json_path.lower()
    if "transaction" in path_lower or decode_base64_candidate(value) is not None:
        add_transaction_candidate(
            candidates,
            seen,
            value,
            source=source,
            json_path=json_path,
            probe_id=probe_id,
        )


def extract_transaction_candidates_from_text(
    text: str,
    *,
    source: str,
    probe_id: str | None,
    candidates: list[dict[str, Any]],
    seen: set[str],
) -> None:
    if not text.strip():
        return

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None

    if parsed is not None:
        walk_transaction_json(
            parsed,
            source=source,
            json_path="$",
            probe_id=probe_id,
            candidates=candidates,
            seen=seen,
        )

    for match in BASE64_CANDIDATE_RE.finditer(text):
        add_transaction_candidate(
            candidates,
            seen,
            match.group(1),
            source=source,
            json_path="$regex",
            probe_id=probe_id,
        )


def extract_transaction_candidates_from_burp_items(
    items: list[dict[str, Any]],
    *,
    target_netloc: str | None,
    source: str,
    quote_path: str = "/api/quote",
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    quote_response_count = 0

    for item in items:
        request = parse_raw_http_request(str(item.get("request") or ""))
        response = parse_raw_http_response(str(item.get("response") or ""))
        if target_netloc and request["host"] != target_netloc:
            continue
        if request["method"] != "POST" or request["path"].split("?", 1)[0] != quote_path:
            continue

        quote_response_count += 1
        extract_transaction_candidates_from_text(
            response.get("body") or "",
            source=f"{source}:POST {quote_path}:{response.get('status')}",
            probe_id=None,
            candidates=candidates,
            seen=seen,
        )

    return {
        "generated_at": utc_now(),
        "source": source,
        "quote_path": quote_path,
        "quote_response_count": quote_response_count,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "safety": "Extracted from Burp HTTP history only. No wallet signing or transaction submission is performed.",
    }


def merge_transaction_candidate_docs(
    docs: list[dict[str, Any]],
    *,
    source: str,
) -> dict[str, Any]:
    seen: set[str] = set()
    candidates = []
    quote_response_count = 0

    for doc in docs:
        quote_response_count += int(doc.get("quote_response_count", 0))
        for candidate in doc.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            digest = candidate.get("base64_sha256")
            if not digest or digest in seen:
                continue
            seen.add(str(digest))
            candidates.append(candidate)

    return {
        "generated_at": utc_now(),
        "source": source,
        "quote_response_count": quote_response_count,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "safety": "Extracted transaction payload candidates only. No wallet signing or transaction submission is performed.",
    }


def ensure_burp_transaction_candidates_artifact(artifact_dir: Path) -> None:
    path = artifact_dir / "burp-transaction-candidates.json"
    if path.exists():
        return
    write_json(
        path,
        {
            "generated_at": utc_now(),
            "source": "not-imported",
            "quote_response_count": 0,
            "candidate_count": 0,
            "candidates": [],
            "safety": "No Burp quote transaction candidates imported yet. No wallet signing or transaction submission is performed.",
        },
    )


def ensure_initial_audit_artifacts(artifact_dir: Path) -> None:
    history_path = artifact_dir / "burp-history-observations.jsonl"
    if not history_path.exists():
        history_path.write_text("", encoding="utf-8")

    observation_path = artifact_dir / "burp-observation-run.json"
    if not observation_path.exists():
        write_json(
            observation_path,
            {
                "generated_at": utc_now(),
                "status": "not-run",
                "summary": {
                    "observations": 0,
                    "unexpected": 0,
                    "clusters": [],
                },
                "observations": [],
                "websocket_upgrade": None,
                "safety": "Placeholder only. Run burp-sync --observe to collect Burp Proxy observations.",
            },
        )

    quote_collection_path = artifact_dir / "quote-collection.json"
    if not quote_collection_path.exists():
        write_json(
            quote_collection_path,
            {
                "generated_at": utc_now(),
                "status": "not-collected",
                "success": False,
                "diagnosis": {
                    "classification": "quote-collection-not-run",
                    "next_step": "Run collect-quote after M0 configuration is ready; decode only, with no signing or Solana submission.",
                },
                "safety": "Placeholder only. No quote request was sent and no transaction payload was collected.",
            },
        )


def collect_transaction_candidates(
    artifact_dir: Path,
    results: list[dict[str, Any]],
    extra_inputs: list[Path] | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for row in results:
        if row.get("category") != "quote" and row.get("path") != "/api/quote":
            continue
        body_text = row.get("body_text") or row.get("body_sample") or ""
        extract_transaction_candidates_from_text(
            body_text,
            source="probe-results.jsonl",
            probe_id=row.get("probe_id"),
            candidates=candidates,
            seen=seen,
        )

    sidecars = [
        artifact_dir / "transaction-payloads.json",
        artifact_dir / "transaction-payloads.jsonl",
        artifact_dir / "transaction-payloads.txt",
        artifact_dir / "burp-transaction-candidates.json",
    ]
    if extra_inputs:
        sidecars.extend(extra_inputs)

    for path in sidecars:
        if not path.exists() or not path.is_file():
            continue
        if path.suffix == ".jsonl":
            for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                extract_transaction_candidates_from_text(
                    line,
                    source=f"{path.name}:{index}",
                    probe_id=None,
                    candidates=candidates,
                    seen=seen,
                )
        else:
            extract_transaction_candidates_from_text(
                read_text(path),
                source=path.name,
                probe_id=None,
                candidates=candidates,
                seen=seen,
            )

    return candidates


def fallback_decode_transactions(candidates: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    transactions = []
    for candidate in candidates:
        decoded = decode_base64_candidate(candidate["base64"])
        transactions.append(
            {
                "id": candidate["id"],
                "source": candidate["source"],
                "probe_id": candidate.get("probe_id"),
                "json_path": candidate["json_path"],
                "base64_length": candidate["base64_length"],
                "base64_sha256": candidate["base64_sha256"],
                "byte_length": len(decoded) if decoded is not None else None,
                "decoded": False,
                "classification": "unknown-versioned-transaction",
                "warnings": [reason],
            }
        )

    return {
        "decoder": {
            "mode": "base64-only",
            "reason": reason,
        },
        "transactions": transactions,
    }


def node_decode_transactions(
    candidates: list[dict[str, Any]],
    node: str,
    source_root: Path,
) -> dict[str, Any]:
    node_path = Path(node)
    if not node_path.exists():
        fallback = command_result(["node", "-v"])
        if not fallback["ok"]:
            return fallback_decode_transactions(candidates, f"Node not found at {node}")
        node = "node"

    script = """
import fs from 'node:fs'
import { VersionedTransaction } from '@solana/web3.js'

const input = JSON.parse(fs.readFileSync(0, 'utf8'))

function compactError(error) {
  return error && error.message ? error.message : String(error)
}

function messageKeys(message) {
  return Array.from(message.staticAccountKeys ?? message.accountKeys ?? []).map((key) => key.toBase58())
}

function boolFromMessage(message, name, index) {
  try {
    return Boolean(message[name](index))
  } catch {
    return null
  }
}

function instructionAccounts(ix) {
  return Array.from(ix.accountKeyIndexes ?? ix.accounts ?? [])
}

const transactions = input.candidates.map((candidate) => {
  const result = {
    id: candidate.id,
    source: candidate.source,
    probe_id: candidate.probe_id ?? null,
    json_path: candidate.json_path,
    base64_length: candidate.base64_length,
    base64_sha256: candidate.base64_sha256,
    byte_length: null,
    decoded: false,
    classification: 'decode-failed',
    warnings: [],
  }

  try {
    const bytes = Buffer.from(candidate.base64, 'base64')
    result.byte_length = bytes.length
    const tx = VersionedTransaction.deserialize(bytes)
    const message = tx.message
    const keys = messageKeys(message)
    result.decoded = true
    result.classification = 'solana-versioned-transaction'
    result.version = String(tx.version ?? message.version ?? 'legacy')
    result.signature_count = tx.signatures.length
    result.recent_blockhash = message.recentBlockhash
    result.static_account_keys = keys.map((key, index) => ({
      index,
      pubkey: key,
      signer: boolFromMessage(message, 'isAccountSigner', index),
      writable: boolFromMessage(message, 'isAccountWritable', index),
    }))
    result.compiled_instructions = Array.from(message.compiledInstructions ?? message.instructions ?? []).map((ix, index) => {
      const accountIndexes = instructionAccounts(ix)
      const programIdIndex = ix.programIdIndex
      return {
        index,
        program_id_index: programIdIndex,
        program_id: keys[programIdIndex] ?? null,
        account_indexes: accountIndexes,
        account_keys: accountIndexes.map((accountIndex) => keys[accountIndex] ?? null),
        data_length: ix.data ? ix.data.length : 0,
      }
    })
    result.address_table_lookups = Array.from(message.addressTableLookups ?? []).map((lookup, index) => ({
      index,
      account_key: lookup.accountKey?.toBase58 ? lookup.accountKey.toBase58() : String(lookup.accountKey),
      writable_indexes: Array.from(lookup.writableIndexes ?? []),
      readonly_indexes: Array.from(lookup.readonlyIndexes ?? []),
    }))
  } catch (error) {
    result.warnings.push(compactError(error))
  }

  return result
})

console.log(JSON.stringify({
  decoder: {
    mode: 'solana-web3.js',
    node: process.version,
    package: '@solana/web3.js',
  },
  transactions,
}, null, 2))
"""

    if not source_root.is_dir():
        return fallback_decode_transactions(candidates, f"Source root not found: {source_root}")

    proc = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=str(source_root),
        input=json.dumps({"candidates": candidates}),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )

    if proc.returncode != 0:
        return fallback_decode_transactions(
            candidates,
            f"solana-web3.js decoder failed: {proc.stdout[-1000:]}",
        )

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return fallback_decode_transactions(
            candidates,
            f"solana-web3.js decoder returned non-JSON output: {proc.stdout[-1000:]}",
        )


def expected_mints_for_direction(direction: str) -> tuple[str, str] | None:
    if direction == "buy":
        return USDC_MINT, USDTEL_MINT
    if direction == "sell":
        return USDTEL_MINT, USDC_MINT
    return None


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def normalize_transaction_intent_policy(raw: dict[str, Any]) -> dict[str, Any]:
    direction = raw.get("direction")
    wallet = raw.get("wallet") or raw.get("walletAddress") or raw.get("sender")
    amount_in = raw.get("amountIn") or raw.get("amount_in")
    source_mint = raw.get("sourceMint") or raw.get("source_mint")
    destination_mint = raw.get("destinationMint") or raw.get("destination_mint")
    allowed_programs = normalize_string_list(raw.get("allowedPrograms") or raw.get("allowed_programs"))

    if isinstance(direction, str):
        direction = direction.strip().lower()
    if isinstance(wallet, str):
        wallet = wallet.strip()
    if isinstance(amount_in, str):
        amount_in = amount_in.strip()

    expected = expected_mints_for_direction(direction) if isinstance(direction, str) else None
    if expected:
        source_mint = source_mint or expected[0]
        destination_mint = destination_mint or expected[1]

    policy = {
        "direction": direction,
        "wallet": wallet,
        "amountIn": amount_in,
        "sourceMint": source_mint,
        "destinationMint": destination_mint,
        "allowedPrograms": allowed_programs,
    }
    issues = []
    if direction not in {"buy", "sell"}:
        issues.append("direction must be buy or sell")
    if not isinstance(wallet, str) or not wallet:
        issues.append("wallet must be provided")
    if amount_in is not None and (not isinstance(amount_in, str) or not re.fullmatch(r"[1-9]\d*", amount_in)):
        issues.append("amountIn must be a positive integer string when provided")
    if not isinstance(source_mint, str) or not source_mint:
        issues.append("sourceMint must be provided or derivable from direction")
    if not isinstance(destination_mint, str) or not destination_mint:
        issues.append("destinationMint must be provided or derivable from direction")
    if raw.get("allowedPrograms") is not None and not allowed_programs:
        issues.append("allowedPrograms must be a non-empty string or array when provided")

    return {
        "configured": True,
        "valid": not issues,
        "issues": issues,
        **policy,
    }


def load_transaction_intent_policy(
    artifact_dir: Path,
    *,
    policy_path: Path | None = None,
    direction: str | None = None,
    wallet: str | None = None,
    amount_in: str | None = None,
    allowed_programs: list[str] | None = None,
) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    sources = []

    sidecar = artifact_dir / "transaction-intent-policy.json"
    paths = [path for path in [sidecar, policy_path] if path is not None]
    for path in paths:
        if path.exists():
            loaded = json.loads(read_text(path))
            if not isinstance(loaded, dict):
                return {
                    "configured": True,
                    "valid": False,
                    "issues": [f"{path} must contain a JSON object"],
                    "sources": [str(path)],
                }
            raw.update(loaded)
            sources.append(str(path))

    overrides = {
        "direction": direction,
        "wallet": wallet,
        "amountIn": amount_in,
        "allowedPrograms": allowed_programs,
    }
    raw.update({key: value for key, value in overrides.items() if value is not None})
    if any(value is not None for value in overrides.values()):
        sources.append("cli-arguments")

    if not raw:
        return {
            "configured": False,
            "valid": False,
            "issues": ["No transaction intent policy configured."],
            "sources": [],
        }

    policy = normalize_transaction_intent_policy(raw)
    policy["sources"] = sources
    return policy


def transaction_pubkeys(transaction: dict[str, Any]) -> set[str]:
    keys = {
        item.get("pubkey")
        for item in transaction.get("static_account_keys", [])
        if isinstance(item, dict) and item.get("pubkey")
    }
    for lookup in transaction.get("address_table_lookups", []):
        if isinstance(lookup, dict) and lookup.get("account_key"):
            keys.add(lookup["account_key"])
    return {str(key) for key in keys if key}


def transaction_signer_keys(transaction: dict[str, Any]) -> set[str]:
    return {
        str(item.get("pubkey"))
        for item in transaction.get("static_account_keys", [])
        if isinstance(item, dict) and item.get("pubkey") and item.get("signer") is True
    }


def transaction_program_ids(transaction: dict[str, Any]) -> set[str]:
    return {
        str(item.get("program_id"))
        for item in transaction.get("compiled_instructions", [])
        if isinstance(item, dict) and item.get("program_id")
    }


def make_intent_check(
    check_id: str,
    label: str,
    status: str,
    evidence: Any = None,
    severity: str = "required",
) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "severity": severity,
        "evidence": evidence,
    }


def build_transaction_intent_checks(
    transactions: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    if not policy.get("configured"):
        return {
            "status": "not-configured",
            "checks": [],
            "summary": "No transaction intent policy configured.",
        }
    if not policy.get("valid"):
        return {
            "status": "invalid-policy",
            "checks": [
                make_intent_check("policy-valid", "Intent policy is valid", "failed", policy.get("issues", []))
            ],
            "summary": "Transaction intent policy is invalid.",
        }
    if not transactions:
        return {
            "status": "waiting-for-transaction-candidates",
            "checks": [
                make_intent_check(
                    "transaction-candidates-present",
                    "Transaction payload candidates are present",
                    "waiting",
                    "No transaction payload candidates found.",
                )
            ],
            "summary": "Intent policy is configured, but no transaction payloads are available yet.",
        }

    checks = [
        make_intent_check(
            "policy-direction",
            "Policy direction is supported",
            "passed",
            policy.get("direction"),
        )
    ]

    for transaction in transactions:
        tx_id = transaction.get("id", "unknown")
        if not transaction.get("decoded"):
            checks.append(
                make_intent_check(
                    f"{tx_id}:decoded",
                    "Transaction decodes successfully",
                    "failed",
                    transaction.get("warnings", []),
                )
            )
            continue

        pubkeys = transaction_pubkeys(transaction)
        signer_keys = transaction_signer_keys(transaction)
        wallet = policy["wallet"]
        source_mint = policy["sourceMint"]
        destination_mint = policy["destinationMint"]
        allowed_programs = set(policy.get("allowedPrograms", []))
        program_ids = transaction_program_ids(transaction)
        unexpected_programs = sorted(program_ids - allowed_programs) if allowed_programs else []
        has_address_lookups = bool(transaction.get("address_table_lookups"))

        checks.extend(
            [
                make_intent_check(
                    f"{tx_id}:wallet-account",
                    "Wallet appears in transaction account keys",
                    "passed" if wallet in pubkeys else "failed",
                    wallet,
                ),
                make_intent_check(
                    f"{tx_id}:wallet-signer",
                    "Wallet is marked as a signer",
                    "passed" if wallet in signer_keys else "failed",
                    wallet,
                ),
                make_intent_check(
                    f"{tx_id}:source-mint",
                    "Expected source mint appears in static account keys",
                    "passed" if source_mint in pubkeys else "review",
                    source_mint,
                    severity="review" if has_address_lookups else "required",
                ),
                make_intent_check(
                    f"{tx_id}:destination-mint",
                    "Expected destination mint appears in static account keys",
                    "passed" if destination_mint in pubkeys else "review",
                    destination_mint,
                    severity="review" if has_address_lookups else "required",
                ),
                make_intent_check(
                    f"{tx_id}:instructions-present",
                    "Transaction contains compiled instructions",
                    "passed" if transaction.get("compiled_instructions") else "failed",
                    len(transaction.get("compiled_instructions", [])),
                ),
            ]
        )
        if allowed_programs:
            checks.append(
                make_intent_check(
                    f"{tx_id}:program-allowlist",
                    "Compiled instruction programs are in the configured allowlist",
                    "passed" if not unexpected_programs else "failed",
                    {
                        "allowedPrograms": sorted(allowed_programs),
                        "programIds": sorted(program_ids),
                        "unexpectedPrograms": unexpected_programs,
                    },
                )
            )

    required_failures = [
        check for check in checks if check["status"] == "failed" and check["severity"] == "required"
    ]
    review_items = [check for check in checks if check["status"] == "review"]
    if required_failures:
        status = "failed"
    elif review_items:
        status = "review-required"
    else:
        status = "passed"

    return {
        "status": status,
        "checks": checks,
        "summary": f"{len(required_failures)} required failures, {len(review_items)} review items.",
    }


def build_transaction_intent(
    artifact_dir: Path,
    results: list[dict[str, Any]],
    node: str,
    source_root: Path,
    extra_inputs: list[Path] | None = None,
    policy_path: Path | None = None,
    intent_direction: str | None = None,
    intent_wallet: str | None = None,
    intent_amount_in: str | None = None,
    intent_allowed_programs: list[str] | None = None,
) -> dict[str, Any]:
    candidates = collect_transaction_candidates(artifact_dir, results, extra_inputs)
    summaries = [
        {key: value for key, value in candidate.items() if key != "base64"}
        for candidate in candidates
    ]

    if candidates:
        decoded = node_decode_transactions(candidates, node, source_root)
        warnings: list[str] = []
    else:
        decoded = {"decoder": {"mode": "none"}, "transactions": []}
        warnings = [
            "No transaction payload candidates found in quote probe responses, Burp-derived candidates, or transaction-payloads sidecars."
        ]

    transactions = decoded.get("transactions", [])
    decoded_count = sum(1 for item in transactions if item.get("decoded"))
    policy = load_transaction_intent_policy(
        artifact_dir,
        policy_path=policy_path,
        direction=intent_direction,
        wallet=intent_wallet,
        amount_in=intent_amount_in,
        allowed_programs=intent_allowed_programs,
    )
    policy_checks = build_transaction_intent_checks(transactions, policy)
    return {
        "generated_at": utc_now(),
        "purpose": "Decode Solana transaction payloads for intent review only. This artifact never signs or submits transactions.",
        "candidate_sources": [
            "quote probe response bodies",
            "burp-transaction-candidates.json",
            "transaction-payloads.json",
            "transaction-payloads.jsonl",
            "transaction-payloads.txt",
        ],
        "candidates_seen": len(candidates),
        "decoded_transactions": decoded_count,
        "candidate_summaries": summaries,
        "decoder": decoded.get("decoder", {}),
        "intent_policy": policy,
        "intent_policy_checks": policy_checks,
        "transactions": transactions,
        "warnings": warnings,
    }


def generate_synthetic_transaction_payload(
    node: str,
    source_root: Path,
    *,
    direction: str,
    wallet: str,
) -> dict[str, Any]:
    node_path = Path(node)
    if not node_path.exists():
        fallback = command_result(["node", "-v"])
        if not fallback["ok"]:
            return {"ok": False, "error": f"Node not found at {node}"}
        node = "node"

    expected = expected_mints_for_direction(direction)
    if expected is None:
        return {"ok": False, "error": "direction must be buy or sell"}

    if not source_root.is_dir():
        return {"ok": False, "error": f"Source root not found: {source_root}"}

    script = """
import fs from 'node:fs'
import {
  PublicKey,
  SystemProgram,
  TransactionInstruction,
  TransactionMessage,
  VersionedTransaction,
} from '@solana/web3.js'

const input = JSON.parse(fs.readFileSync(0, 'utf8'))
const wallet = new PublicKey(input.wallet)
const sourceMint = new PublicKey(input.sourceMint)
const destinationMint = new PublicKey(input.destinationMint)
const ix = new TransactionInstruction({
  programId: SystemProgram.programId,
  keys: [
    { pubkey: wallet, isSigner: true, isWritable: true },
    { pubkey: sourceMint, isSigner: false, isWritable: false },
    { pubkey: destinationMint, isSigner: false, isWritable: false },
  ],
  data: Buffer.from([0]),
})
const message = new TransactionMessage({
  payerKey: wallet,
  recentBlockhash: '11111111111111111111111111111111',
  instructions: [ix],
}).compileToV0Message()
const tx = new VersionedTransaction(message)
const base64 = Buffer.from(tx.serialize()).toString('base64')
console.log(JSON.stringify({
  base64,
  sourceMint: sourceMint.toBase58(),
  destinationMint: destinationMint.toBase58(),
  wallet: wallet.toBase58(),
  allowedProgram: SystemProgram.programId.toBase58(),
}, null, 2))
"""
    proc = subprocess.run(
        [node, "--input-type=module", "--eval", script],
        cwd=str(source_root),
        input=json.dumps({"wallet": wallet, "sourceMint": expected[0], "destinationMint": expected[1]}),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )

    if proc.returncode != 0:
        return {"ok": False, "error": proc.stdout[-1000:]}
    parsed = parse_json_object(proc.stdout)
    if not parsed or not isinstance(parsed.get("base64"), str):
        return {"ok": False, "error": f"unexpected self-test output: {proc.stdout[-1000:]}"}
    parsed["ok"] = True
    return parsed


def build_transaction_decoder_selftest(
    artifact_dir: Path,
    source_root: Path,
    node: str,
    *,
    direction: str,
    wallet: str,
    amount_in: str,
) -> dict[str, Any]:
    payload = generate_synthetic_transaction_payload(
        node,
        source_root,
        direction=direction,
        wallet=wallet,
    )
    if not payload.get("ok"):
        return {
            "generated_at": utc_now(),
            "status": "failed",
            "error": payload.get("error"),
            "safety": "Synthetic transaction generation only. No signing with a real wallet and no Solana submission.",
        }

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    add_transaction_candidate(
        candidates,
        seen,
        str(payload["base64"]),
        source="synthetic-transaction-decoder-selftest",
        json_path="$.payloads[0].data.transaction",
        probe_id="transaction_decoder_selftest",
    )
    decoded = node_decode_transactions(candidates, node, source_root) if candidates else {"transactions": []}
    transactions = decoded.get("transactions", [])
    policy = normalize_transaction_intent_policy(
        {
            "direction": direction,
            "wallet": payload["wallet"],
            "amountIn": amount_in,
            "sourceMint": payload["sourceMint"],
            "destinationMint": payload["destinationMint"],
            "allowedPrograms": [payload["allowedProgram"]],
        }
    )
    policy_checks = build_transaction_intent_checks(transactions, policy)
    decoded_count = sum(1 for item in transactions if item.get("decoded"))
    status = "passed" if decoded_count == 1 and policy_checks.get("status") == "passed" else "failed"
    return {
        "generated_at": utc_now(),
        "status": status,
        "purpose": "Exercise the transaction candidate extractor, Solana decoder, and intent-policy checks using a local synthetic transaction.",
        "safety": "Synthetic transaction only. No real quote corpus, no wallet signing, and no Solana submission.",
        "input_intent": {
            "direction": direction,
            "wallet": payload["wallet"],
            "amountIn": amount_in,
            "sourceMint": payload["sourceMint"],
            "destinationMint": payload["destinationMint"],
            "allowedPrograms": [payload["allowedProgram"]],
        },
        "candidate_count": len(candidates),
        "decoded_transactions": decoded_count,
        "decoder": decoded.get("decoder", {}),
        "intent_policy_checks": policy_checks,
        "transactions": transactions,
        "note": "This self-test proves decoder mechanics only; it does not satisfy GAP-quote-transaction-corpus.",
    }


def build_finding_gate(
    suspicions: list[dict[str, Any]],
    burp_history: list[dict[str, Any]],
) -> dict[str, Any]:
    gates = []
    burp_paths = {row.get("path") for row in burp_history}

    for suspicion in suspicions:
        evidence = suspicion.get("blackbox_evidence", [])
        entrypoint_path = suspicion["entrypoint"].split(" ", 1)[-1]
        has_reproduction = bool(evidence)
        has_source = bool(suspicion.get("source_refs"))
        has_burp_context = entrypoint_path in burp_paths
        classification = suspicion.get("final_classification", "manual-review")

        checks = [
            {
                "id": "blackbox-reproduction",
                "passed": has_reproduction,
                "evidence": "probe-results.jsonl" if has_reproduction else None,
            },
            {
                "id": "source-context",
                "passed": has_source,
                "evidence": suspicion.get("source_refs", []),
            },
            {
                "id": "burp-observation",
                "passed": has_burp_context,
                "evidence": "burp-history-observations.jsonl" if has_burp_context else None,
                "note": "Helpful for black-box-first workflow; not required for a hardening note generated from controlled probes.",
            },
            {
                "id": "attacker-model",
                "passed": classification == "hardening-note",
                "evidence": "Implicit unauthenticated client for hardening notes; valid findings require explicit model.",
            },
            {
                "id": "impact",
                "passed": classification == "hardening-note",
                "evidence": "Informational/hardening impact only unless additional exploitation evidence is added.",
            },
        ]

        if classification == "valid-finding":
            gate_status = "passed" if all(check["passed"] for check in checks) else "blocked"
        elif classification == "hardening-note":
            gate_status = "accepted-hardening-note" if has_reproduction and has_source else "manual-review"
        else:
            gate_status = "manual-review"

        gates.append(
            {
                "suspicion_id": suspicion["id"],
                "entrypoint": suspicion["entrypoint"],
                "classification": classification,
                "gate_status": gate_status,
                "checks": checks,
            }
        )

    return {
        "generated_at": utc_now(),
        "policy": [
            "valid-finding requires black-box reproduction, source context when needed, explicit attacker model, impact, and counter-evidence review.",
            "hardening-note may pass with controlled probe reproduction plus source context, but must not be reported as an exploitable vulnerability.",
        ],
        "gates": gates,
    }


def build_capabilities(target: str, artifact_dir: Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    codex = command_result(["codex", "mcp", "get", "burp"], timeout=10)
    script = ROOT / "scripts/check-burp-mcp.sh"
    script_check = command_result([str(script)], timeout=30) if script.exists() else {"ok": False, "output": "missing"}
    health_path = probe_target_path(profile, "health", "path", "/health")
    health = http_request(target, "GET", health_path)
    health_json = parse_json_object(health.get("body_text") or "")
    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")
    history_status = (
        "ok_reads_builtin_browser_proxy_history"
        if burp_history
        else "not_observed_by_cli_run"
    )

    return {
        "generated_at": utc_now(),
        "target": {
            "base_url": target,
            "health_path": health_path,
            "health_status": health["status"],
            "reachable": health["status"] == 200,
            "service": (health_json or {}).get("service"),
            "m0_key_present": (health_json or {}).get("m0KeyPresent"),
        },
        "burp": {
            "mcp_endpoint": "http://127.0.0.1:9876",
            "mcp_port_open": socket_open("127.0.0.1", 9876),
            "proxy_8080_open": socket_open("127.0.0.1", 8080),
            "proxy_8081_open": socket_open("127.0.0.1", 8081),
            "codex_mcp_get_burp_ok": codex["ok"],
            "check_script_ok": script_check["ok"],
            "approval_sensitive_tools": {
                "observed_get_proxy_http_history": history_status,
                "observed_send_http1_request": "ok_after_127.0.0.1_3100_request_approval",
                "observed_create_repeater_tab": "ok_from_codex_tool_call",
                "observed_set_proxy_intercept_state": "ok_disabled_for_automation",
            },
        },
        "artifacts": {
            "directory": str(artifact_dir),
        },
    }


def build_report_capabilities_placeholder(target: str, artifact_dir: Path) -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "status": "placeholder",
        "target": {
            "base_url": target,
            "health_path": None,
            "health_status": "unknown",
            "reachable": None,
            "service": None,
            "m0_key_present": None,
        },
        "burp": {
            "mcp_endpoint": "http://127.0.0.1:9876",
            "mcp_port_open": "unknown",
            "proxy_8080_open": "unknown",
            "proxy_8081_open": "unknown",
            "codex_mcp_get_burp_ok": "unknown",
            "check_script_ok": "unknown",
            "approval_sensitive_tools": {
                "observed_get_proxy_http_history": "unknown",
                "observed_send_http1_request": "unknown",
                "observed_create_repeater_tab": "unknown",
                "observed_set_proxy_intercept_state": "unknown",
            },
        },
        "artifacts": {
            "directory": str(artifact_dir),
            "source": "placeholder-for-report-refresh",
        },
        "safety": "Placeholder used by report refresh only. No target, Burp, wallet, or upstream request was sent.",
    }


def build_report_transaction_intent_placeholder() -> dict[str, Any]:
    return {
        "generated_at": utc_now(),
        "status": "not-run",
        "candidates_seen": 0,
        "decoded_transactions": 0,
        "decoder": {"mode": "not-run"},
        "intent_policy_checks": {"status": "not-run"},
        "warnings": ["transaction-intent.json was not available when report was refreshed."],
        "safety": "Placeholder used by report refresh only. No wallet signing or transaction submission was performed.",
    }


def build_environment_readiness(
    target: str,
    source_root: Path,
    artifact_dir: Path,
    *,
    capabilities: dict[str, Any] | None = None,
    quote_collection: dict[str, Any] | None = None,
    transaction_intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env_paths = [source_root / ".env.local", source_root / ".env"]
    env_values: dict[str, tuple[Path, str]] = {}
    for path in env_paths:
        for key, value in parse_dotenv_file(path).items():
            env_values.setdefault(key, (path, value))

    def env_status(key: str, *, secret: bool) -> dict[str, Any]:
        item = env_values.get(key)
        value = item[1] if item else None
        result = classify_env_value(value, secret=secret)
        if item:
            result["source"] = str(item[0].relative_to(ROOT))
        return result

    quote_diagnosis = (quote_collection or {}).get("diagnosis", {})
    tx_candidates = int((transaction_intent or {}).get("candidates_seen", 0) or 0)
    decoded_transactions = int((transaction_intent or {}).get("decoded_transactions", 0) or 0)
    m0_key = env_status("M0_ORCHESTRATION_API_KEY", secret=True)
    preview_wallet = env_status("NEXT_PUBLIC_M0_QUOTE_PREVIEW_WALLET", secret=False)
    target_info = (capabilities or {}).get("target", {})

    checks = [
        {
            "id": "target-health",
            "status": "passed" if target_info.get("reachable") else "failed",
            "evidence": {
                "target": target,
                "health_status": target_info.get("health_status"),
            },
        },
        {
            "id": "m0-orchestration-key-configured",
            "status": "passed" if m0_key.get("status") == "configured" else "blocked",
            "evidence": m0_key,
        },
        {
            "id": "health-reports-m0-key-present",
            "status": "passed" if target_info.get("m0_key_present") is True else "blocked",
            "evidence": target_info.get("m0_key_present"),
        },
        {
            "id": "m0-preview-wallet-configured",
            "status": "passed" if preview_wallet.get("status") == "configured" else "blocked",
            "evidence": preview_wallet,
        },
        {
            "id": "quote-collection-ready",
            "status": "passed" if quote_diagnosis.get("classification") == "quote-payload-collected" else "blocked",
            "evidence": quote_diagnosis or "quote-collection.json not available",
        },
        {
            "id": "transaction-corpus-present",
            "status": "passed" if tx_candidates > 0 and decoded_transactions > 0 else "blocked",
            "evidence": {
                "candidates_seen": tx_candidates,
                "decoded_transactions": decoded_transactions,
            },
        },
    ]
    blocked = [check for check in checks if check["status"] == "blocked"]
    failed = [check for check in checks if check["status"] == "failed"]
    if failed:
        status = "failed"
    elif blocked:
        status = "waiting-for-external-configuration"
    else:
        status = "ready"

    next_steps = []
    if m0_key.get("status") != "configured":
        next_steps.append("Set a real M0_ORCHESTRATION_API_KEY and restart the target server.")
    if preview_wallet.get("status") != "configured":
        next_steps.append("Set NEXT_PUBLIC_M0_QUOTE_PREVIEW_WALLET to a real Solana wallet address for quote previews.")
    if quote_diagnosis.get("classification") != "quote-payload-collected":
        next_steps.append("Rerun collect-quote after M0 configuration is ready; decode only, with no signing or submission.")

    return {
        "generated_at": utc_now(),
        "status": status,
        "target": target_info,
        "source_root": str(source_root),
        "checks": checks,
        "next_steps": next_steps,
        "safety": "Readiness checks do not print secret values and do not sign or submit transactions.",
    }


def display_report_value(value: Any) -> str:
    if value is None or value == "":
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    return str(value)


def source_resolver_condition_counts(endpoint_resolver: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for resolution in endpoint_resolver.get("observed_endpoint_resolution", []) or []:
        for match in resolution.get("matches", []) or []:
            status = match.get("condition_status")
            if status:
                counts[str(status)] = counts.get(str(status), 0) + 1
        for policy in resolution.get("route_policy_context", []) or []:
            status = policy.get("condition_status")
            if status:
                counts[str(status)] = counts.get(str(status), 0) + 1
    return counts


def source_resolver_entrypoint_lines(endpoint_resolver: dict[str, Any]) -> list[str]:
    lines = []
    entrypoints = endpoint_resolver.get("discovered_entrypoints", []) or []
    priority_kinds = {"rewrite-proxy", "websocket-json-rpc-proxy", "custom-websocket-upgrade"}
    selected = [
        item
        for item in entrypoints
        if item.get("kind") in priority_kinds
        or item.get("source_path")
        or (item.get("next_config") or {}).get("base_path_applied")
        or (item.get("next_config") or {}).get("trailing_slash") is not None
        or ((item.get("next_config") or {}).get("i18n") or {}).get("locale_aware")
    ]
    if not selected:
        selected = entrypoints[:8]
    for item in selected[:16]:
        source_path = item.get("source_path") or item.get("path")
        runtime_path = item.get("path")
        details = [
            f"kind `{display_report_value(item.get('kind'))}`",
            f"strategy `{display_report_value(item.get('strategy_set'))}`",
        ]
        rewrite = item.get("rewrite") or {}
        if rewrite:
            details.append(f"phase `{display_report_value(rewrite.get('phase'))}`")
            details.append(f"conditional `{display_report_value(rewrite.get('conditional'))}`")
        upstreams = item.get("fixed_upstreams") or []
        if upstreams:
            details.append(f"upstreams `{display_report_value(upstreams[:3])}`")
        runtime = item.get("next_config") or {}
        runtime_reasons = next_runtime_reasons(runtime)
        if runtime_reasons:
            details.append(f"runtime `{display_report_value(runtime_reasons)}`")
        line = (
            f"- `{display_report_value(item.get('cluster_id'))}` "
            f"`{display_report_value(source_path)}` -> `{display_report_value(runtime_path)}` "
            + "; ".join(details)
        )
        lines.append(line)
    if not lines:
        lines.append("- No source resolver entrypoints are available.")
    return lines


def source_resolver_policy_lines(endpoint_resolver: dict[str, Any]) -> list[str]:
    lines = []
    for policy in (endpoint_resolver.get("discovered_route_policies", []) or [])[:16]:
        route_policy = policy.get("route_policy") or {}
        policy_type = route_policy.get("type") or policy.get("kind")
        source_path = policy.get("source_path") or route_policy.get("source_framework_pattern") or policy.get("path")
        runtime_path = policy.get("path")
        details = [
            f"type `{display_report_value(policy_type)}`",
            f"conditional `{display_report_value(route_policy.get('conditional'))}`",
        ]
        if route_policy.get("status_code"):
            details.append(f"status `{display_report_value(route_policy.get('status_code'))}`")
        if route_policy.get("header_keys"):
            details.append(f"headers `{display_report_value(route_policy.get('header_keys'))}`")
        runtime_reasons = next_runtime_reasons(policy.get("next_config") or {})
        if runtime_reasons:
            details.append(f"runtime `{display_report_value(runtime_reasons)}`")
        lines.append(
            f"- `{display_report_value(policy.get('id'))}` "
            f"`{display_report_value(source_path)}` -> `{display_report_value(runtime_path)}` "
            + "; ".join(details)
        )
    if not lines:
        lines.append("- No `next.config.*` redirect/header route-policy entries were discovered.")
    return lines


def source_resolver_server_action_lines(endpoint_resolver: dict[str, Any]) -> list[str]:
    lines = []
    for action in (endpoint_resolver.get("discovered_server_actions", []) or [])[:16]:
        action_names = action.get("action_names") or []
        details = [
            f"scope `{display_report_value(action.get('scope'))}`",
            f"exports `{display_report_value(action_names[:8])}`",
            f"directives `{display_report_value(action.get('use_server_directive_count'))}`",
        ]
        lines.append(
            f"- `{display_report_value(action.get('id'))}` "
            f"`{display_report_value(action.get('source_ref'))}` "
            + "; ".join(details)
        )
    if not lines:
        lines.append("- No Next.js Server Actions were statically discovered.")
    return lines


def source_resolver_observed_lines(endpoint_resolver: dict[str, Any]) -> list[str]:
    lines = []
    for resolution in endpoint_resolver.get("observed_endpoint_resolution", []) or []:
        endpoint = f"{resolution.get('method')} {resolution.get('path')}"
        for match in resolution.get("matches", []) or []:
            reasons = [
                reason
                for reason in match.get("match_reasons", [])
                if str(reason).startswith(("basePath:", "locale-prefix:", "trailingSlash:", "condition-"))
                or str(reason) in {"conditional-route"}
            ]
            interesting = bool(reasons or match.get("condition_status") or match.get("rewrite"))
            if not interesting:
                continue
            source_path = match.get("source_path") or match.get("entrypoint_path")
            line = (
                f"- `{endpoint}` -> `{display_report_value(match.get('cluster_id'))}` "
                f"source `{display_report_value(source_path)}` applicability `{display_report_value(match.get('applicability'))}`"
            )
            if match.get("condition_status"):
                line += f" condition `{display_report_value(match.get('condition_status'))}`"
            if reasons:
                line += f" reasons `{display_report_value(reasons)}`"
            lines.append(line)
        for policy in resolution.get("route_policy_context", []) or []:
            route_policy = policy.get("route_policy") or {}
            line = (
                f"- `{endpoint}` route-policy `{display_report_value(policy.get('kind'))}` "
                f"path `{display_report_value(policy.get('path'))}` applicability `{display_report_value(policy.get('applicability'))}`"
            )
            if policy.get("condition_status"):
                line += f" condition `{display_report_value(policy.get('condition_status'))}`"
            if route_policy.get("header_keys"):
                line += f" headers `{display_report_value(route_policy.get('header_keys'))}`"
            if route_policy.get("status_code"):
                line += f" status `{display_report_value(route_policy.get('status_code'))}`"
            lines.append(line)
    if not lines:
        lines.append("- No observed endpoint runtime rewrites or route-policy condition decisions were recorded.")
    return lines[:24]


def build_source_resolver_report_summary(source_peeks: dict[str, Any] | None) -> dict[str, Any]:
    endpoint_resolver = (source_peeks or {}).get("endpoint_resolver") or {}
    inventory_summary = endpoint_resolver.get("inventory_summary") or {}
    runtime = inventory_summary.get("next_config_runtime") or {}
    condition_counts = source_resolver_condition_counts(endpoint_resolver)
    summary_lines = [
        f"- Resolver status: `{display_report_value(endpoint_resolver.get('status'))}`",
        (
            "- Inventory: "
            f"`{inventory_summary.get('route_count', 0)}` routes, "
            f"`{inventory_summary.get('rewrite_count', 0)}` rewrites, "
            f"`{inventory_summary.get('route_policy_count', 0)}` route policies, "
            f"`{inventory_summary.get('middleware_count', 0)}` middleware/proxy files, "
            f"`{inventory_summary.get('server_action_file_count', 0)}` Server Action files"
        ),
        (
            "- Next.js runtime: "
            f"basePath `{display_report_value(runtime.get('base_path'))}`, "
            f"trailingSlash `{display_report_value(runtime.get('trailing_slash'))}`, "
            f"i18n `{display_report_value(runtime.get('i18n_configured'))}`, "
            f"locales `{display_report_value(runtime.get('locale_count'))}`"
        ),
        f"- Observed endpoint resolutions: `{len(endpoint_resolver.get('observed_endpoint_resolution', []) or [])}`",
        f"- Condition decisions: `{json.dumps(condition_counts, sort_keys=True)}`",
    ]
    if not endpoint_resolver:
        summary_lines = ["- Source resolver output is not available yet; run `audit` to write `source-peek-results.json`."]
    return {
        "summary_lines": summary_lines,
        "entrypoint_lines": source_resolver_entrypoint_lines(endpoint_resolver) if endpoint_resolver else ["- No source resolver entrypoints are available."],
        "policy_lines": source_resolver_policy_lines(endpoint_resolver) if endpoint_resolver else ["- No route-policy context is available."],
        "server_action_lines": source_resolver_server_action_lines(endpoint_resolver) if endpoint_resolver else ["- No Server Actions context is available."],
        "observed_lines": source_resolver_observed_lines(endpoint_resolver) if endpoint_resolver else ["- No observed endpoint resolver context is available."],
        "runtime": runtime,
        "condition_counts": condition_counts,
    }


def generate_report(
    artifact_dir: Path,
    target: str,
    results: list[dict[str, Any]],
    suspicions: list[dict[str, Any]],
    capabilities: dict[str, Any],
    attack_strategy: dict[str, Any],
    burp_history: list[dict[str, Any]],
    finding_gate: dict[str, Any],
    transaction_intent: dict[str, Any],
    warmup_results: dict[str, Any] | None = None,
    evidence_gaps: dict[str, Any] | None = None,
    rpc_method_policy: dict[str, Any] | None = None,
    environment_readiness: dict[str, Any] | None = None,
    transaction_decoder_selftest: dict[str, Any] | None = None,
    blackbox_coverage: dict[str, Any] | None = None,
    evidence_chain: dict[str, Any] | None = None,
    hardening_notes: list[dict[str, Any]] | None = None,
    adjudication: dict[str, Any] | None = None,
    evidence_appendix: dict[str, Any] | None = None,
    verification_queue: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> str:
    profile_name = profile_display_name(profile)
    report_title = f"InferForge {profile_name} Greybox Run"
    profile_info = profile_summary(profile)
    status_lines = [
        f"- Target profile: `{profile_info.get('display_name') or profile_info.get('name') or 'unknown'}`",
        f"- Target: `{target}`",
        f"- Target health status: `{capabilities['target']['health_status']}`",
        f"- Burp MCP port open: `{capabilities['burp']['mcp_port_open']}`",
        f"- Burp Proxy 8080 open: `{capabilities['burp']['proxy_8080_open']}`",
        f"- Burp Proxy 8081 open: `{capabilities['burp']['proxy_8081_open']}`",
        f"- Codex `burp` MCP registration: `{capabilities['burp']['codex_mcp_get_burp_ok']}`",
    ]
    profile_lines = [
        f"- Profile artifact: `{TARGET_PROFILE_ARTIFACT}`",
        f"- Strategy registry: `{STRATEGY_REGISTRY_ARTIFACT}`",
        f"- Profile validation: `{PROFILE_VALIDATION_ARTIFACT}`",
        f"- Profile path: `{profile_info.get('profile_path', 'unknown')}`",
        f"- Loaded from: `{profile_info.get('loaded_from', 'unknown')}`",
        f"- Target type: `{profile_info.get('target_type', 'unknown')}`",
        f"- Frameworks: `{', '.join(profile_info.get('frameworks', [])) or 'unknown'}`",
        f"- Enabled strategy sets: `{', '.join(sorted(enabled_strategy_set_ids(profile))) or 'none'}`",
    ]

    probe_lines = []
    for row in results:
        marker = "ok" if row["expected"] else "unexpected"
        interesting = " interesting" if row["interesting"] else ""
        expectation = ""
        if row.get("expectation") != "status":
            expectation = f", expectation `{row.get('expectation_result')}`"
        probe_lines.append(
            f"- `{row['probe_id']}` {row['method']} `{row['path']}` -> `{row['status']}` ({marker}{interesting}{expectation})"
        )

    suspicion_lines = []
    if suspicions:
        for item in suspicions:
            suspicion_lines.append(
                f"- `{item['id']}` `{item['entrypoint']}`: {item['hypothesis']} Classification: `{item['final_classification']}`."
            )
    else:
        suspicion_lines.append("- No suspicions generated from this run.")

    strategy_summary = attack_strategy.get("summary", {}) or {}
    strategy_lines = [
        f"- Strategy status: `{attack_strategy.get('status', 'unknown')}`",
        f"- Clusters with specific strategy: `{strategy_summary.get('clusters_with_specific_strategy', 0)}` / `{strategy_summary.get('clusters', 0)}`",
        (
            "- Strategy-uncovered clusters: "
            f"`{', '.join(strategy_summary.get('strategy_uncovered_clusters', []) or []) or 'none'}`"
        ),
        f"- Next action statuses: `{json.dumps(strategy_summary.get('next_action_status_counts', {}), sort_keys=True)}`",
        "",
        "Strategy registry:",
    ]
    strategy_lines.extend(
        f"- `{item['id']}`: {item['title']}"
        for item in attack_strategy["strategies"]
    )
    gate_lines = [
        f"- `{item['suspicion_id']}` `{item['entrypoint']}` -> `{item['gate_status']}`"
        for item in finding_gate["gates"]
    ] or ["- No finding gates generated."]
    burp_lines = [
        f"- `{row['method']} {row['path']}` `{row['host']}` -> `{row['status']}` via `{row['source']}`"
        for row in burp_history
    ] or ["- No Burp built-in-browser history observations recorded yet."]
    warmup_rows = (warmup_results or {}).get("results", [])
    warmup_lines = [
        (
            f"- `{row['probe_id']}` {row['method']} `{row['path']}` -> `{row['status']}` "
            f"({'ok' if row['expected'] else 'unexpected'}, attempts `{row.get('attempt_count', 1)}`)"
        )
        for row in warmup_rows
    ] or ["- No route warm-up results recorded."]
    transaction_lines = [
        f"- Candidates seen: `{transaction_intent.get('candidates_seen', 0)}`",
        f"- Decoded transactions: `{transaction_intent.get('decoded_transactions', 0)}`",
        f"- Decoder mode: `{transaction_intent.get('decoder', {}).get('mode', 'unknown')}`",
        f"- Intent policy status: `{transaction_intent.get('intent_policy_checks', {}).get('status', 'unknown')}`",
        f"- Decoder self-test: `{(transaction_decoder_selftest or {}).get('status', 'not-run')}`",
        "- Safety: decode only; no wallet signing or transaction submission.",
    ]
    for warning in transaction_intent.get("warnings", []):
        transaction_lines.append(f"- Warning: {warning}")
    rpc_policy_lines = [
        f"- Policy posture: `{(rpc_method_policy or {}).get('policy_posture', 'unknown')}`",
        (
            "- Default high-impact methods: "
            f"`{', '.join((rpc_method_policy or {}).get('default_high_impact_methods', [])) or 'none'}`"
        ),
        (
            "- Transaction method gate present: "
            f"`{(rpc_method_policy or {}).get('explicit_transaction_method_gate_present', 'unknown')}`"
        ),
        (
            "- Transaction method probe results: "
            f"`{len((rpc_method_policy or {}).get('transaction_probe_results', []))}`"
        ),
    ]
    evidence_gap_lines = [
        (
            f"- `{item['id']}` `{item['cluster_id']}` `{item['priority']}`: "
            f"{item['title']} Safe next step: {item['safe_next_step']}"
        )
        for item in (evidence_gaps or {}).get("gaps", [])
    ] or ["- No evidence gaps recorded."]
    readiness_lines = [
        f"- Overall readiness: `{(environment_readiness or {}).get('status', 'unknown')}`",
    ]
    for check in (environment_readiness or {}).get("checks", []):
        readiness_lines.append(f"- `{check['id']}` -> `{check['status']}`")
    coverage_lines = [
        f"- Overall coverage: `{(blackbox_coverage or {}).get('status', 'unknown')}`",
    ]
    for item in (blackbox_coverage or {}).get("cluster_coverage", []):
        coverage_lines.append(f"- `{item['cluster_id']}` -> `{item['status']}`")
    evidence_chain_lines = [
        f"- Evidence chain status: `{(evidence_chain or {}).get('status', 'unknown')}`",
        f"- Indexed clusters: `{(evidence_chain or {}).get('summary', {}).get('clusters', 0)}`",
        f"- Indexed probes: `{(evidence_chain or {}).get('summary', {}).get('probes', 0)}`",
        f"- Indexed Burp observations: `{(evidence_chain or {}).get('summary', {}).get('burp_observations', 0)}`",
    ]
    adjudication_summary = (adjudication or {}).get("summary", {})
    adjudication_lines = [
        f"- Overall adjudication: `{(adjudication or {}).get('status', 'unknown')}`",
        f"- Reportable findings: `{adjudication_summary.get('reportable_findings', 0)}`",
        f"- Accepted hardening notes: `{adjudication_summary.get('accepted_hardening_notes', 0)}`",
        f"- Manual review items: `{adjudication_summary.get('manual_review', 0)}`",
        f"- Blocked gate items: `{adjudication_summary.get('blocked', 0)}`",
        f"- External blockers: `{len((adjudication or {}).get('external_blockers', []))}`",
    ]
    hardening_note_lines = [
        f"- `{item['id']}` `{item['entrypoint']}`: {item['title']} Gate: `{item['gate_status']}`."
        for item in (hardening_notes or [])
    ] or ["- No accepted hardening notes generated."]
    evidence_appendix_summary = (evidence_appendix or {}).get("summary", {})
    evidence_appendix_lines = [
        f"- Appendix status: `{(evidence_appendix or {}).get('status', 'unknown')}`",
        f"- Probe rows indexed: `{evidence_appendix_summary.get('probe_rows', 0)}`",
        f"- Representative probe examples: `{evidence_appendix_summary.get('representative_probe_examples', 0)}`",
        f"- Burp observations indexed: `{evidence_appendix_summary.get('burp_observations', 0)}`",
        f"- Redaction: `{(evidence_appendix or {}).get('redaction', {}).get('text_patterns', 'unknown')}`",
    ]
    verification_summary = (verification_queue or {}).get("summary", {})
    command_safety_summary_doc = verification_summary.get("command_safety", {}) or {}
    verification_lines = [
        f"- Queue status: `{(verification_queue or {}).get('status', 'unknown')}`",
        f"- Queue items: `{verification_summary.get('items', 0)}`",
        f"- Status counts: `{json.dumps(verification_summary.get('status_counts', {}), sort_keys=True)}`",
        f"- Command safety: `{format_command_safety_summary(command_safety_summary_doc)}`",
        "- Reproduction steps: `reproduction-steps.md`",
    ]
    review_blockers = load_optional_json(artifact_dir / REVIEW_BLOCKERS_ARTIFACT) or {}
    review_blockers_summary = review_blockers.get("summary", {}) or {}
    review_blocker_lines = [
        f"- Review blocker status: `{review_blockers.get('status', 'unknown')}`",
        f"- Blockers: `{review_blockers_summary.get('blockers', 0)}`",
        f"- Groups: `{review_blockers_summary.get('groups', 0)}`",
        f"- Status counts: `{json.dumps(review_blockers_summary.get('status_counts', {}), sort_keys=True)}`",
        f"- Category counts: `{json.dumps(review_blockers_summary.get('category_counts', {}), sort_keys=True)}`",
    ]
    for group in (review_blockers.get("groups", []) or [])[:8]:
        count_suffix = f" ({group.get('count')} blockers)" if group.get("count") else ""
        line = (
            f"- `{group.get('status')}` `{group.get('id')}`{count_suffix}: "
            f"{markdown_text(group.get('title') or group.get('id'))}"
        )
        if group.get("next_action"):
            line += f" Next: {markdown_text(group.get('next_action'))}"
        review_blocker_lines.append(line)
        commands = ordered_unique_strings(group.get("commands", []) or [])
        if commands:
            review_blocker_lines.append(f"  - Command: `{commands[0]}`")
    review_artifact_lines = [
        f"- `{name}`"
        for name in [*DISCOVERY_ARTIFACTS, *REVIEW_ARTIFACTS]
        if (artifact_dir / name).exists()
    ] or ["- No discovery or review-only observation artifacts are present in this artifact directory yet."]
    burp_observation_coverage = load_optional_json(artifact_dir / "burp-observation-coverage.json") or {}
    burp_observation_summary = burp_observation_coverage.get("summary", {}) or {}
    burp_observation_coverage_lines = [
        f"- Coverage status: `{burp_observation_coverage.get('status', 'unknown')}`",
        f"- Clusters: `{burp_observation_summary.get('clusters', 0)}`",
        f"- Status counts: `{json.dumps(burp_observation_summary.get('status_counts', {}), sort_keys=True)}`",
        f"- Burp history clusters: `{display_report_value(burp_observation_summary.get('burp_history_observed_clusters', []))}`",
        f"- Active observation clusters: `{display_report_value(burp_observation_summary.get('active_observation_clusters', []))}`",
        f"- Review candidate clusters: `{display_report_value(burp_observation_summary.get('review_candidate_clusters', []))}`",
    ]
    for item in (burp_observation_coverage.get("clusters", []) or [])[:12]:
        burp_observation_coverage_lines.append(
            f"- `{item.get('cluster_id')}` `{item.get('status')}` "
            f"active `{item.get('active_observation_count')}` review `{item.get('review_candidate_count')}` "
            f"next: {item.get('next_action')}"
        )
    response_delta_analysis = load_optional_json(artifact_dir / "response-delta-analysis.json") or {}
    response_delta_summary = response_delta_analysis.get("summary", {}) or {}
    response_delta_lines = [
        f"- Delta status: `{response_delta_analysis.get('status', 'unknown')}`",
        f"- Probe rows: `{response_delta_summary.get('probe_rows', 0)}`",
        f"- Endpoint groups: `{response_delta_summary.get('endpoint_groups', 0)}`",
        f"- Review-needed groups: `{response_delta_summary.get('review_needed_groups', 0)}`",
        f"- Interesting groups: `{response_delta_summary.get('interesting_groups', 0)}`",
        f"- Expected-delta groups: `{response_delta_summary.get('expected_delta_groups', 0)}`",
    ]
    for item in (response_delta_analysis.get("clusters", []) or [])[:12]:
        response_delta_lines.append(
            f"- `{item.get('cluster_id')}` `{item.get('status')}` "
            f"probes `{item.get('probe_count')}` endpoints `{item.get('endpoint_count')}` "
            f"flags `{display_report_value(item.get('delta_flags', []))}`"
        )
    source_peek_requests = load_optional_json(artifact_dir / "source-peek-requests.json") or {}
    source_peek_request_summary = source_peek_requests.get("summary", {}) or {}
    source_peek_request_lines = [
        f"- Request status: `{source_peek_requests.get('status', 'unknown')}`",
        f"- Requests: `{source_peek_request_summary.get('requests', 0)}`",
        f"- Triggers: `{json.dumps(source_peek_request_summary.get('trigger_counts', {}), sort_keys=True)}`",
        f"- Status counts: `{json.dumps(source_peek_request_summary.get('status_counts', {}), sort_keys=True)}`",
    ]
    for item in (source_peek_requests.get("requests", []) or [])[:10]:
        source_peek_request_lines.append(
            f"- `{item.get('id')}` `{item.get('trigger')}` `{item.get('status')}` "
            f"{display_report_value(item.get('entrypoint'))} refs `{len(item.get('source_refs', []) or [])}`"
        )
    source_resolver_summary = build_source_resolver_report_summary(
        load_optional_json(artifact_dir / "source-peek-results.json")
    )

    source_summary_lines = []
    for cluster in (profile or {}).get("clusters", []):
        refs = ", ".join(f"`{ref}`" for ref in cluster.get("source_refs", [])) or "`none`"
        source_summary_lines.append(
            f"- `{cluster.get('id')}` `{cluster.get('kind')}` strategy `{strategy_set_for_cluster(cluster) or 'unassigned'}` source refs: {refs}"
        )
    if not source_summary_lines:
        source_summary_lines.append("- No source references declared by the target profile.")

    report = f"""# {report_title}

Generated: {utc_now()}

## Scope

{chr(10).join(status_lines)}

## Target Profile

{chr(10).join(profile_lines)}

## Artifact Manifest

- Manifest: `artifact-manifest.json`
- Integrity: SHA256 hashes for generated artifacts, excluding the manifest itself.

## Burp MCP Status

Burp MCP is installed and reachable on `127.0.0.1:9876`. Codex can send approved requests, create Repeater tabs, and read Proxy HTTP history after Burp's built-in browser generates traffic. For automation, Proxy Intercept should stay off unless a human explicitly wants to pause and edit a request.

## Environment Readiness

{chr(10).join(readiness_lines)}

## Black-Box Coverage Gate

{chr(10).join(coverage_lines)}

## Burp Observation Coverage

{chr(10).join(burp_observation_coverage_lines)}

## Response Delta Analysis

{chr(10).join(response_delta_lines)}

## Evidence Chain

{chr(10).join(evidence_chain_lines)}

## Evidence Appendix

{chr(10).join(evidence_appendix_lines)}

## Finding Adjudication

{chr(10).join(adjudication_lines)}

## Verification Queue

{chr(10).join(verification_lines)}

## Review Blockers

{chr(10).join(review_blocker_lines)}

## Discovery And Review Artifacts

{chr(10).join(review_artifact_lines)}

## Source Peek Requests

{chr(10).join(source_peek_request_lines)}

## Source Resolver And Route Policies

### Resolver Summary

{chr(10).join(source_resolver_summary['summary_lines'])}

### Runtime And Rewrite Entry Points

{chr(10).join(source_resolver_summary['entrypoint_lines'])}

### Redirect And Header Policies

{chr(10).join(source_resolver_summary['policy_lines'])}

### Server Actions

{chr(10).join(source_resolver_summary['server_action_lines'])}

### Observed Runtime And Condition Decisions

{chr(10).join(source_resolver_summary['observed_lines'])}

## Burp Browser History

{chr(10).join(burp_lines)}

## Local Route Warmup

{chr(10).join(warmup_lines)}

## Probe Results

{chr(10).join(probe_lines)}

## Suspicions

{chr(10).join(suspicion_lines)}

## Accepted Hardening Notes

{chr(10).join(hardening_note_lines)}

## Finding Gate

{chr(10).join(gate_lines)}

## Transaction Intent Decoder

{chr(10).join(transaction_lines)}

## RPC Method Policy

{chr(10).join(rpc_policy_lines)}

## Evidence Gaps

{chr(10).join(evidence_gap_lines)}

## Attack Strategy

{chr(10).join(strategy_lines)}

## Source Peek Summary

{chr(10).join(source_summary_lines)}

## Next Steps

1. Feed a successful M0 quote response into `transaction-intent.json` so decoded instructions can be checked against wallet, direction, and mint intent.
2. Add program-specific transaction intent parsers after a real M0 payload corpus is available.
3. Add manually approved WebSocket pending-queue and connection-limit probes with strict low-volume bounds.
"""
    (artifact_dir / "report.md").write_text(report, encoding="utf-8")
    generate_index_html(
        artifact_dir,
        target,
        results,
        suspicions,
        capabilities,
        transaction_intent,
        warmup_results,
        evidence_gaps,
        rpc_method_policy,
        environment_readiness,
        transaction_decoder_selftest,
        blackbox_coverage,
        evidence_chain,
        hardening_notes,
        adjudication,
        evidence_appendix,
        verification_queue,
        profile,
        attack_strategy=attack_strategy,
    )
    return report


def generate_index_html(
    artifact_dir: Path,
    target: str,
    results: list[dict[str, Any]],
    suspicions: list[dict[str, Any]],
    capabilities: dict[str, Any],
    transaction_intent: dict[str, Any],
    warmup_results: dict[str, Any] | None = None,
    evidence_gaps: dict[str, Any] | None = None,
    rpc_method_policy: dict[str, Any] | None = None,
    environment_readiness: dict[str, Any] | None = None,
    transaction_decoder_selftest: dict[str, Any] | None = None,
    blackbox_coverage: dict[str, Any] | None = None,
    evidence_chain: dict[str, Any] | None = None,
    hardening_notes: list[dict[str, Any]] | None = None,
    adjudication: dict[str, Any] | None = None,
    evidence_appendix: dict[str, Any] | None = None,
    verification_queue: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
    attack_strategy: dict[str, Any] | None = None,
) -> None:
    def e(value: Any) -> str:
        return html.escape(str(value))

    rows = []
    for row in results:
        state = "ok" if row["expected"] else "unexpected"
        rows.append(
            "<tr>"
            f"<td>{e(row['probe_id'])}</td>"
            f"<td>{e(row['method'])}</td>"
            f"<td><code>{e(row['path'])}</code></td>"
            f"<td>{e(row['status'])}</td>"
            f"<td class='{state}'>{state}</td>"
            f"<td>{e(row.get('expectation_result', ''))}</td>"
            f"<td>{e(row['body_sample'][:120])}</td>"
            "</tr>"
        )

    notes = []
    if suspicions:
        for item in suspicions:
            notes.append(
                "<li>"
                f"<strong>{e(item['id'])}</strong> "
                f"<code>{e(item['entrypoint'])}</code> "
                f"{e(item['hypothesis'])}"
                "</li>"
            )
    else:
        notes.append("<li>No suspicions generated.</li>")

    warmup_ready = (warmup_results or {}).get("ready", "unknown")
    warmup_count = len((warmup_results or {}).get("results", []))
    evidence_gap_count = len((evidence_gaps or {}).get("gaps", []))
    rpc_policy_posture = (rpc_method_policy or {}).get("policy_posture", "unknown")
    readiness_status = (environment_readiness or {}).get("status", "unknown")
    decoder_selftest_status = (transaction_decoder_selftest or {}).get("status", "not-run")
    blackbox_coverage_status = (blackbox_coverage or {}).get("status", "unknown")
    evidence_chain_status = (evidence_chain or {}).get("status", "unknown")
    adjudication_status = (adjudication or {}).get("status", "unknown")
    reportable_findings = (adjudication or {}).get("summary", {}).get("reportable_findings", 0)
    hardening_note_count = len(hardening_notes or [])
    evidence_appendix_status = (evidence_appendix or {}).get("status", "unknown")
    verification_queue_status = (verification_queue or {}).get("status", "unknown")
    review_blockers = load_optional_json(artifact_dir / REVIEW_BLOCKERS_ARTIFACT) or {}
    review_blocker_summary = review_blockers.get("summary", {}) or {}
    review_blocker_status = review_blockers.get("status", "unknown")
    review_blocker_lines = [
        f"- Status `{review_blocker_status}`",
        f"- Blockers `{review_blocker_summary.get('blockers', 0)}`",
        f"- Groups `{review_blocker_summary.get('groups', 0)}`",
        f"- Status counts `{json.dumps(review_blocker_summary.get('status_counts', {}), sort_keys=True)}`",
        f"- Category counts `{json.dumps(review_blocker_summary.get('category_counts', {}), sort_keys=True)}`",
    ]
    for group in (review_blockers.get("groups", []) or [])[:8]:
        count_suffix = f" ({group.get('count')} blockers)" if group.get("count") else ""
        line = (
            f"- `{group.get('status')}` `{group.get('id')}`{count_suffix}: "
            f"{markdown_text(group.get('title') or group.get('id'))}"
        )
        if group.get("next_action"):
            line += f" next: {markdown_text(group.get('next_action'))}"
        review_blocker_lines.append(line)
        commands = ordered_unique_strings(group.get("commands", []) or [])
        if commands:
            review_blocker_lines.append(f"- Command `{commands[0]}`")
    attack_strategy_status = (attack_strategy or {}).get("status", "unknown")
    attack_strategy_summary = (attack_strategy or {}).get("summary", {}) or {}
    attack_strategy_lines = [
        f"- Status `{attack_strategy_status}`",
        (
            f"- Clusters with specific strategy `{attack_strategy_summary.get('clusters_with_specific_strategy', 0)}`"
            f" / `{attack_strategy_summary.get('clusters', 0)}`"
        ),
        (
            "- Uncovered clusters "
            f"`{display_report_value(attack_strategy_summary.get('strategy_uncovered_clusters', []) or [])}`"
        ),
        f"- Waiting actions `{attack_strategy_summary.get('waiting_action_count', 0)}`",
        f"- Relevant next actions `{attack_strategy_summary.get('relevant_next_actions', 0)}`",
    ]
    command_safety_summary_doc = ((verification_queue or {}).get("summary", {}) or {}).get("command_safety", {}) or {}
    command_safety_counts = command_safety_summary_doc.get("classification_counts", {}) or {}
    burp_observation_coverage = load_optional_json(artifact_dir / "burp-observation-coverage.json") or {}
    burp_observation_summary = burp_observation_coverage.get("summary", {}) or {}
    burp_observation_coverage_status = burp_observation_coverage.get("status", "unknown")
    burp_observation_coverage_lines = [
        f"- Status `{burp_observation_coverage_status}`",
        f"- Clusters `{burp_observation_summary.get('clusters', 0)}`",
        f"- Status counts `{json.dumps(burp_observation_summary.get('status_counts', {}), sort_keys=True)}`",
        f"- Burp history clusters `{display_report_value(burp_observation_summary.get('burp_history_observed_clusters', []))}`",
        f"- Review candidate clusters `{display_report_value(burp_observation_summary.get('review_candidate_clusters', []))}`",
    ]
    for item in (burp_observation_coverage.get("clusters", []) or [])[:12]:
        burp_observation_coverage_lines.append(
            f"- `{item.get('cluster_id')}` `{item.get('status')}` next: {item.get('next_action')}"
        )
    response_delta_analysis = load_optional_json(artifact_dir / "response-delta-analysis.json") or {}
    response_delta_summary = response_delta_analysis.get("summary", {}) or {}
    response_delta_status = response_delta_analysis.get("status", "unknown")
    response_delta_lines = [
        f"- Status `{response_delta_status}`",
        f"- Probe rows `{response_delta_summary.get('probe_rows', 0)}`",
        f"- Endpoint groups `{response_delta_summary.get('endpoint_groups', 0)}`",
        f"- Review-needed groups `{response_delta_summary.get('review_needed_groups', 0)}`",
        f"- Interesting groups `{response_delta_summary.get('interesting_groups', 0)}`",
        f"- Expected-delta groups `{response_delta_summary.get('expected_delta_groups', 0)}`",
    ]
    for item in (response_delta_analysis.get("clusters", []) or [])[:12]:
        response_delta_lines.append(
            f"- `{item.get('cluster_id')}` `{item.get('status')}` probes `{item.get('probe_count')}` flags `{display_report_value(item.get('delta_flags', []))}`"
        )
    source_peek_requests = load_optional_json(artifact_dir / "source-peek-requests.json") or {}
    source_peek_request_summary = source_peek_requests.get("summary", {}) or {}
    source_peek_request_status = source_peek_requests.get("status", "unknown")
    source_peek_request_count = source_peek_request_summary.get("requests", 0)
    source_peek_request_lines = [
        f"- Status `{source_peek_request_status}`",
        f"- Requests `{source_peek_request_count}`",
        f"- Triggers `{json.dumps(source_peek_request_summary.get('trigger_counts', {}), sort_keys=True)}`",
        f"- Status counts `{json.dumps(source_peek_request_summary.get('status_counts', {}), sort_keys=True)}`",
    ]
    for item in (source_peek_requests.get("requests", []) or [])[:10]:
        source_peek_request_lines.append(
            f"- `{item.get('id')}` `{item.get('trigger')}` `{item.get('status')}` {display_report_value(item.get('entrypoint'))}"
        )
    profile_name = profile_display_name(profile)
    page_title = f"InferForge {profile_name} Greybox Run"
    artifact_links = "\n".join(
        f'      <li><a href="{e(name)}">{e(name)}</a></li>'
        for name in artifact_link_names(artifact_dir)
    )
    source_resolver_summary = build_source_resolver_report_summary(
        load_optional_json(artifact_dir / "source-peek-results.json")
    )

    def html_list(lines: list[str]) -> str:
        items = []
        for line in lines:
            item = line[2:] if line.startswith("- ") else line
            items.append(f"<li>{e(item)}</li>")
        return "\n".join(items)

    doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(page_title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --text: #15171a;
      --muted: #5d6673;
      --line: #d9dee7;
      --panel: #ffffff;
      --ok: #146c43;
      --warn: #9a3412;
      --accent: #0f5f6f;
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 15px;
      line-height: 1.5;
    }}
    main {{
      width: min(1180px, calc(100vw - 48px));
      margin: 32px auto 48px;
    }}
    h1, h2, h3 {{
	      margin: 0;
	      letter-spacing: 0;
	    }}
    h1 {{
      font-size: 32px;
      line-height: 1.15;
    }}
	    h2 {{
	      margin-top: 28px;
	      font-size: 20px;
	    }}
    h3 {{
      margin-top: 18px;
      font-size: 16px;
    }}
    .meta {{
      margin-top: 10px;
      color: var(--muted);
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 12px;
      margin-top: 24px;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px 16px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 13px;
    }}
    .metric strong {{
      display: block;
      margin-top: 5px;
      font-size: 18px;
    }}
    table {{
      width: 100%;
      margin-top: 12px;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      color: var(--muted);
      font-weight: 650;
      background: #eef2f5;
    }}
    tr:last-child td {{
      border-bottom: 0;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 13px;
    }}
    .ok {{
      color: var(--ok);
      font-weight: 700;
    }}
    .unexpected {{
      color: var(--warn);
      font-weight: 700;
    }}
    ul {{
      margin-top: 12px;
      padding-left: 22px;
    }}
    a {{
      color: var(--accent);
    }}
  </style>
</head>
<body>
  <main>
    <h1>{e(page_title)}</h1>
    <p class="meta">Generated {e(utc_now())} · Target <code>{e(target)}</code></p>

    <section class="summary" aria-label="Run summary">
      <div class="metric"><span>Target Profile</span><strong>{e(profile_name)}</strong></div>
      <div class="metric"><span>Target Health</span><strong>{e(capabilities['target']['health_status'])}</strong></div>
      <div class="metric"><span>Burp MCP Port</span><strong>{e(capabilities['burp']['mcp_port_open'])}</strong></div>
      <div class="metric"><span>Proxy 8080</span><strong>{e(capabilities['burp']['proxy_8080_open'])}</strong></div>
      <div class="metric"><span>Proxy 8081</span><strong>{e(capabilities['burp']['proxy_8081_open'])}</strong></div>
      <div class="metric"><span>Warmup Ready</span><strong>{e(warmup_ready)}</strong></div>
      <div class="metric"><span>Warmup Checks</span><strong>{warmup_count}</strong></div>
      <div class="metric"><span>Probes</span><strong>{len(results)}</strong></div>
      <div class="metric"><span>Suspicions</span><strong>{len(suspicions)}</strong></div>
      <div class="metric"><span>Findings</span><strong>{e(reportable_findings)}</strong></div>
      <div class="metric"><span>Hardening Notes</span><strong>{e(hardening_note_count)}</strong></div>
      <div class="metric"><span>Evidence Gaps</span><strong>{evidence_gap_count}</strong></div>
      <div class="metric"><span>Adjudication</span><strong>{e(adjudication_status)}</strong></div>
      <div class="metric"><span>RPC Policy</span><strong>{e(rpc_policy_posture)}</strong></div>
      <div class="metric"><span>Readiness</span><strong>{e(readiness_status)}</strong></div>
      <div class="metric"><span>Coverage Gate</span><strong>{e(blackbox_coverage_status)}</strong></div>
      <div class="metric"><span>Burp Observation</span><strong>{e(burp_observation_coverage_status)}</strong></div>
      <div class="metric"><span>Response Deltas</span><strong>{e(response_delta_status)}</strong></div>
      <div class="metric"><span>Evidence Chain</span><strong>{e(evidence_chain_status)}</strong></div>
      <div class="metric"><span>Source Peek Requests</span><strong>{e(source_peek_request_count)} · {e(source_peek_request_status)}</strong></div>
      <div class="metric"><span>Evidence Appendix</span><strong>{e(evidence_appendix_status)}</strong></div>
      <div class="metric"><span>Verification Queue</span><strong>{e(verification_queue_status)}</strong></div>
      <div class="metric"><span>Review Blockers</span><strong>{e(review_blocker_status)}</strong></div>
      <div class="metric"><span>Attack Strategy</span><strong>{e(attack_strategy_status)}</strong></div>
      <div class="metric"><span>Command Templates</span><strong>{e(command_safety_counts.get('manual-template', 0))} manual · {e(command_safety_summary_doc.get('unsafe_template_count', 0))} unsafe</strong></div>
      <div class="metric"><span>Tx Candidates</span><strong>{e(transaction_intent.get('candidates_seen', 0))}</strong></div>
      <div class="metric"><span>Decoded Tx</span><strong>{e(transaction_intent.get('decoded_transactions', 0))}</strong></div>
      <div class="metric"><span>Intent Policy</span><strong>{e(transaction_intent.get('intent_policy_checks', {}).get('status', 'unknown'))}</strong></div>
      <div class="metric"><span>Tx Self-Test</span><strong>{e(decoder_selftest_status)}</strong></div>
    </section>

	    <h2>Findings And Notes</h2>
	    <ul>{''.join(notes)}</ul>

    <h2>Review Blockers</h2>
    <ul>{html_list(review_blocker_lines)}</ul>

    <h2>Burp Observation Coverage</h2>
    <ul>{html_list(burp_observation_coverage_lines)}</ul>

    <h2>Response Delta Analysis</h2>
    <ul>{html_list(response_delta_lines)}</ul>

    <h2>Source Resolver And Route Policies</h2>
    <h3>Source Peek Requests</h3>
    <ul>{html_list(source_peek_request_lines)}</ul>
    <h3>Resolver Summary</h3>
    <ul>{html_list(source_resolver_summary['summary_lines'])}</ul>
    <h3>Runtime And Rewrite Entry Points</h3>
    <ul>{html_list(source_resolver_summary['entrypoint_lines'])}</ul>
    <h3>Redirect And Header Policies</h3>
    <ul>{html_list(source_resolver_summary['policy_lines'])}</ul>
    <h3>Server Actions</h3>
    <ul>{html_list(source_resolver_summary['server_action_lines'])}</ul>
    <h3>Observed Runtime And Condition Decisions</h3>
    <ul>{html_list(source_resolver_summary['observed_lines'])}</ul>

    <h2>Attack Strategy</h2>
    <ul>{html_list(attack_strategy_lines)}</ul>

	    <h2>Probe Results</h2>
    <table>
      <thead>
        <tr>
          <th>Probe</th>
          <th>Method</th>
          <th>Path</th>
          <th>Status</th>
          <th>State</th>
          <th>Expectation</th>
          <th>Response Sample</th>
        </tr>
      </thead>
      <tbody>{''.join(rows)}</tbody>
    </table>

    <h2>Artifacts</h2>
    <ul>
{artifact_links}
    </ul>
  </main>
</body>
</html>
"""
    (artifact_dir / "index.html").write_text(doc, encoding="utf-8")


def write_plan(
    artifact_dir: Path,
    probes: list[Probe],
    selection: dict[str, Any],
    *,
    ws_enabled: bool,
    ranking: dict[str, Any] | None = None,
) -> None:
    rank_by_id = {
        item["probe_id"]: item
        for item in (ranking or {}).get("ranked_probes", [])
    }
    write_json(
        artifact_dir / "probe-plan.json",
        {
            "generated_at": utc_now(),
            "selection": selection,
            "ranking": {
                "artifact": "probe-ranking.json" if ranking else None,
                "max_probes": (ranking or {}).get("max_probes"),
                "selected_probe_count": (ranking or {}).get("selected_probe_count", len(probes)),
                "total_probe_count": (ranking or {}).get("total_probe_count", len(probes)),
            },
            "safety": {
                "mode": "safe",
                "destructive_actions": False,
                "wallet_signing": False,
                "high_volume_fuzzing": False,
            },
            "websocket_probes_enabled": ws_enabled,
            "probes": [
                {
                    "id": probe.id,
                    "label": probe.label,
                    "cluster_id": probe.category,
                    "strategy_set": strategy_set_for_probe(probe),
                    "method": probe.method,
                    "path": probe.path,
                    "origin": probe.origin,
                    "referer": probe.referer,
                    "content_type": probe.content_type,
                    "expected_statuses": list(probe.expected_statuses),
                    "expectation": probe.expectation,
                    "external": probe.external,
                    "policy_field": probe.policy_field,
                    "risk": probe.risk,
                    "rank": rank_by_id.get(probe.id, {}).get("rank"),
                    "rank_score": rank_by_id.get(probe.id, {}).get("score"),
                    "rank_reasons": rank_by_id.get(probe.id, {}).get("reasons", []),
                }
                for probe in probes
            ],
        },
    )


def run_audit(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    ensure_burp_transaction_candidates_artifact(artifact_dir)
    ensure_initial_audit_artifacts(artifact_dir)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)

    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")
    clusters = build_clusters(profile, source_root)
    write_json(artifact_dir / "endpoint-clusters.json", clusters)
    pre_probe_traffic_index = build_traffic_index([], burp_history)
    selection = select_cluster_ids(
        pre_probe_traffic_index,
        clusters,
        source_assisted=not args.observed_only,
    )
    selected_clusters = set(selection["selected_cluster_ids"])
    candidate_probes = build_probe_plan(
        target,
        include_external=args.include_external,
        selected_clusters=selected_clusters,
        profile=profile,
    )
    ranking = build_probe_ranking(candidate_probes, selection, clusters, max_probes=args.max_probes)
    probes = apply_probe_ranking(candidate_probes, ranking)
    ws_enabled = (
        args.ws
        and "solana-rpc-ws" in selected_clusters
        and websocket_observation_config(profile) is not None
    )
    write_json(artifact_dir / "probe-ranking.json", ranking)
    write_plan(artifact_dir, probes, selection, ws_enabled=ws_enabled, ranking=ranking)
    try:
        with TargetProbeLock(target, purpose="audit"):
            warmup_results = run_audit_warmup(target, artifact_dir, profile, selected_clusters)
            results = run_http_probes(target, probes, phase="probe", timeout=20, max_attempts=2)
            if ws_enabled:
                results.extend(run_ws_probes(target, args.node, source_root, profile))
                if args.ws_resource_probes:
                    results.extend(run_ws_resource_probes(target, args.node, source_root, profile))
    except RuntimeError as error:
        write_json(
            artifact_dir / "target-probe-lock.json",
            {
                "generated_at": utc_now(),
                "status": "blocked",
                "target": target,
                "error": str(error),
                "safety": "Only one active probe run may target the same service at a time.",
            },
        )
        print(f"Target probe lock blocked audit: {error}")
        print(f"Wrote {artifact_dir / 'target-probe-lock.json'}")
        return 2

    append_jsonl(artifact_dir / "probe-results.jsonl", results)
    response_delta_analysis = build_response_delta_analysis(clusters, results)
    write_json(artifact_dir / "response-delta-analysis.json", response_delta_analysis)
    traffic_index = build_traffic_index(results, burp_history)
    write_json(artifact_dir / "traffic-index.json", traffic_index)
    source_peeks = build_source_peeks(source_root, profile, traffic_index.get("endpoints", []))
    write_json(artifact_dir / "source-peek-results.json", source_peeks)
    transaction_intent = build_transaction_intent(
        artifact_dir,
        results,
        args.node,
        source_root,
        policy_path=Path(args.intent_policy).resolve() if args.intent_policy else None,
        intent_direction=args.intent_direction,
        intent_wallet=args.intent_wallet,
        intent_amount_in=args.intent_amount_in,
        intent_allowed_programs=args.intent_allowed_program or None,
    )
    write_json(artifact_dir / "transaction-intent.json", transaction_intent)
    transaction_decoder_selftest = build_transaction_decoder_selftest(
        artifact_dir,
        source_root,
        args.node,
        direction=args.intent_direction or "buy",
        wallet=args.intent_wallet or DEFAULT_TEST_WALLET,
        amount_in=args.intent_amount_in or "1000000",
    )
    write_json(artifact_dir / "transaction-decoder-selftest.json", transaction_decoder_selftest)
    rpc_method_policy = build_rpc_method_policy(source_root, results)
    write_json(artifact_dir / "rpc-method-policy.json", rpc_method_policy)
    orca_baseline_path = artifact_dir / "orca-baseline.json"
    orca_baseline = json.loads(read_text(orca_baseline_path)) if orca_baseline_path.exists() else None
    quote_collection_path = artifact_dir / "quote-collection.json"
    quote_collection = json.loads(read_text(quote_collection_path)) if quote_collection_path.exists() else None
    suspicions = build_suspicions(results, clusters)
    write_json(artifact_dir / "suspicions.json", {"generated_at": utc_now(), "suspicions": suspicions})
    finding_gate = build_finding_gate(suspicions, burp_history)
    write_json(artifact_dir / "finding-gate.json", finding_gate)
    findings = build_findings(suspicions, finding_gate)
    hardening_notes = build_hardening_notes(suspicions, finding_gate)
    write_json(artifact_dir / "findings.json", {"generated_at": utc_now(), "findings": findings})
    write_json(
        artifact_dir / "hardening-notes.json",
        {"generated_at": utc_now(), "hardening_notes": hardening_notes},
    )
    attack_strategy = build_attack_strategy(clusters, suspicions, burp_history)
    write_json(artifact_dir / "attack-strategy.json", attack_strategy)
    capabilities = build_capabilities(target, artifact_dir, profile)
    quote_collection_for_readiness = quote_collection
    environment_readiness = build_environment_readiness(
        target,
        source_root,
        artifact_dir,
        capabilities=capabilities,
        quote_collection=quote_collection_for_readiness,
        transaction_intent=transaction_intent,
    )
    write_json(artifact_dir / "environment-readiness.json", environment_readiness)
    evidence_gaps = build_evidence_gaps(
        clusters,
        results,
        burp_history,
        transaction_intent,
        rpc_method_policy,
        orca_baseline,
        quote_collection,
        source_peeks,
    )
    write_json(artifact_dir / "evidence-gaps.json", evidence_gaps)
    burp_observation_run = load_optional_json(artifact_dir / "burp-observation-run.json")
    burp_observation_coverage = build_burp_observation_coverage(
        target,
        profile,
        clusters,
        burp_history,
        burp_observation_run,
        evidence_gaps,
    )
    write_json(artifact_dir / "burp-observation-coverage.json", burp_observation_coverage)
    source_peek_requests = build_source_peek_requests(
        clusters,
        traffic_index,
        source_peeks,
        suspicions,
        evidence_gaps,
    )
    write_json(artifact_dir / "source-peek-requests.json", source_peek_requests)
    blackbox_coverage = build_blackbox_coverage(
        clusters,
        results,
        burp_history,
        source_peeks,
        evidence_gaps,
        burp_observation_run,
        environment_readiness,
        transaction_decoder_selftest,
    )
    write_json(artifact_dir / "blackbox-coverage.json", blackbox_coverage)
    evidence_chain = build_evidence_chain(
        clusters,
        results,
        burp_history,
        source_peeks,
        finding_gate,
        evidence_gaps,
        blackbox_coverage,
        environment_readiness,
        transaction_intent,
        transaction_decoder_selftest,
    )
    write_json(artifact_dir / "evidence-chain.json", evidence_chain)
    adjudication = build_adjudication(
        suspicions,
        finding_gate,
        findings,
        hardening_notes,
        evidence_gaps,
        blackbox_coverage,
        environment_readiness,
        evidence_chain,
    )
    write_json(artifact_dir / "adjudication.json", adjudication)
    evidence_appendix = build_evidence_appendix(
        clusters,
        results,
        burp_history,
        burp_observation_run,
        blackbox_coverage,
        evidence_chain,
        adjudication,
        environment_readiness,
    )
    write_json(artifact_dir / "evidence-appendix.json", evidence_appendix)
    verification_queue = build_verification_queue(
        target,
        clusters,
        evidence_appendix,
        evidence_gaps,
        blackbox_coverage,
        adjudication,
        environment_readiness,
        artifact_dir,
        attack_strategy=attack_strategy,
    )
    verification_queue_path = artifact_dir / "verification-queue.json"
    reproduction_steps_path = artifact_dir / "reproduction-steps.md"
    review_blockers_path = artifact_dir / REVIEW_BLOCKERS_ARTIFACT
    review_blockers_markdown_path = artifact_dir / REVIEW_BLOCKERS_MARKDOWN_ARTIFACT
    write_json(verification_queue_path, verification_queue)
    write_reproduction_steps(artifact_dir, verification_queue)
    review_blockers = build_review_blockers(
        target=target,
        profile=profile,
        artifact_dir=artifact_dir,
        discovery_coverage=load_optional_json(artifact_dir / DISCOVERY_COVERAGE_ARTIFACT),
        burp_observation_coverage=burp_observation_coverage,
        verification_queue=verification_queue,
        source_peek_requests=source_peek_requests,
        environment_readiness=environment_readiness,
    )
    write_json(review_blockers_path, review_blockers)
    write_review_blockers_markdown(review_blockers_markdown_path, review_blockers)
    write_json(artifact_dir / "burp-capabilities.json", capabilities)
    write_json(
        artifact_dir / "config.json",
        {
            "generated_at": utc_now(),
            "tool": "InferForge local",
            "profile": profile_summary(profile),
            "target_profile": TARGET_PROFILE_ARTIFACT,
            "strategy_registry": STRATEGY_REGISTRY_ARTIFACT,
            "enabled_strategy_sets": sorted(enabled_strategy_set_ids(profile)),
            "target": target,
            "source_root": str(source_root),
            "artifact_dir": str(artifact_dir),
            "include_external": args.include_external,
            "max_probes": args.max_probes,
            "ws": ws_enabled,
            "ws_resource_probes": bool(args.ws_resource_probes),
            "selection_mode": selection["mode"],
            "warmup_ready": warmup_results["ready"],
            "http_probe_max_attempts": 2,
        },
    )
    generate_report(
        artifact_dir,
        target,
        results,
        suspicions,
        capabilities,
        attack_strategy,
        burp_history,
        finding_gate,
        transaction_intent,
        warmup_results,
        evidence_gaps,
        rpc_method_policy,
        environment_readiness,
        transaction_decoder_selftest,
        blackbox_coverage,
        evidence_chain,
        hardening_notes,
        adjudication,
        evidence_appendix,
        verification_queue,
        profile,
    )
    artifact_manifest = write_artifact_manifest(artifact_dir, target, command="audit")

    unexpected = [row for row in results if not row["expected"]]
    print(f"InferForge wrote artifacts to {artifact_dir}")
    print(f"Warmup: {'ready' if warmup_results['ready'] else 'unexpected warmup result'}")
    print(f"Probes: {len(results)} total, {len(unexpected)} unexpected, {len(suspicions)} suspicions")
    print(
        "Transactions: "
        f"{transaction_intent['candidates_seen']} candidates, "
        f"{transaction_intent['decoded_transactions']} decoded"
    )
    print(f"Evidence gaps: {len(evidence_gaps['gaps'])}")
    print(f"Evidence chain: {evidence_chain['status']}")
    print(f"Adjudication: {adjudication['status']}")
    print(f"Evidence appendix: {evidence_appendix['status']}")
    print(f"Verification queue: {verification_queue['status']}")
    print(
        "Command safety: "
        f"{format_command_safety_summary(verification_queue['summary'].get('command_safety', {}) or {})}"
    )
    print(f"Artifact manifest: {artifact_manifest['status']}")
    for row in unexpected:
        print(f"unexpected: {row['probe_id']} status={row['status']} expected={row['expected_statuses']}")
    return 0


def run_collect(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")
    clusters = build_clusters(profile, source_root)
    traffic_index = build_traffic_index([], burp_history)
    selection = select_cluster_ids(
        traffic_index,
        clusters,
        source_assisted=not args.observed_only,
    )

    write_json(artifact_dir / "endpoint-clusters.json", clusters)
    write_json(artifact_dir / "traffic-index.json", traffic_index)
    write_json(
        artifact_dir / "collection-summary.json",
        {
            "generated_at": utc_now(),
            "source": "burp-history-observations.jsonl",
            "profile": profile_summary(profile),
            "target": target,
            "burp_history_items": len(burp_history),
            "selection": selection,
        },
    )

    print(f"Collected {len(burp_history)} Burp history observations")
    print(f"Selected clusters: {', '.join(selection['selected_cluster_ids']) or '(none)'}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="collect",
            output_paths=[
                *target_profile_artifact_paths(artifact_dir),
                artifact_dir / "endpoint-clusters.json",
                artifact_dir / "traffic-index.json",
                artifact_dir / "collection-summary.json",
            ],
        )
    )
    return 0


def run_burp_observe(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)

    if not args.allow_nonlocal_target and not is_loopback_target(target):
        print("burp-observe refuses non-loopback targets unless --allow-nonlocal-target is set")
        return 2

    parsed_proxy = urllib.parse.urlparse(args.proxy)
    proxy_open = bool(
        parsed_proxy.hostname
        and socket_open(parsed_proxy.hostname, parsed_proxy.port or 8080)
    )
    requests = []
    try:
        observation_plan = build_burp_observation_plan(target, profile)
    except ValueError as error:
        output_path = artifact_dir / "burp-observation-run.json"
        write_json(
            output_path,
            {
                "generated_at": utc_now(),
                "status": "blocked-profile-validation",
                "profile": profile_summary(profile),
                "target": target,
                "error": str(error),
                "requests": [],
                "websocket_upgrade": None,
                "summary": {"total": 0, "unexpected": 0, "clusters": []},
                "safety": "No request was sent because the active Burp observation plan is not a reviewed concrete local path set.",
            },
        )
        print(f"Burp observation blocked by profile validation: {error}")
        print(f"Wrote {output_path}")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="burp-observe",
                output_paths=[
                    *target_profile_artifact_paths(artifact_dir),
                    output_path,
                ],
            )
        )
        return 2
    try:
        with TargetProbeLock(target, purpose="burp-observe"):
            for item in observation_plan:
                response = http_request_through_proxy(
                    target,
                    args.proxy,
                    item["method"],
                    item["path"],
                    body=item.get("body"),
                    headers=item.get("headers"),
                    timeout=20,
                )
                expected = response.get("status") in set(item["expected_statuses"])
                requests.append(
                    {
                        "id": item["id"],
                        "cluster": item["cluster"],
                        "method": item["method"],
                        "path": item["path"],
                        "expected_statuses": item["expected_statuses"],
                        "status": response.get("status"),
                        "expected": expected,
                        "duration_ms": response.get("duration_ms"),
                        "error": response.get("error"),
                        "body_sha256": response.get("body_sha256"),
                        "body_length": response.get("body_length"),
                        "body_sample": response.get("body_sample", "")[:240],
                    }
                )

            ws_observation = None
            if args.ws_upgrade:
                ws_observation = run_ws_upgrade_observation_through_proxy(
                    target,
                    args.proxy,
                    args.node,
                    source_root,
                    profile,
                )
                ws_observation["expected"] = (
                    True
                    if ws_observation.get("skipped")
                    else ws_observation.get("status") in set(ws_observation.get("expected_statuses", []))
                )
    except RuntimeError as error:
        output_path = artifact_dir / "target-probe-lock.json"
        write_json(
            output_path,
            {
                "generated_at": utc_now(),
                "status": "blocked",
                "target": target,
                "error": str(error),
                "safety": "Only one active observation/probe run may target the same service at a time.",
            },
        )
        print(f"Target probe lock blocked burp-observe: {error}")
        print(f"Wrote {output_path}")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="burp-observe",
                output_paths=[
                    *target_profile_artifact_paths(artifact_dir),
                    output_path,
                ],
            )
        )
        return 2

    all_items = requests + ([ws_observation] if ws_observation else [])
    unexpected = [item for item in all_items if not item.get("expected")]
    history_regex = build_burp_history_regex(
        target,
        observation_plan,
        include_ws_upgrade=bool(ws_observation),
    )
    artifact = {
        "generated_at": utc_now(),
        "profile": profile_summary(profile),
        "target": target,
        "proxy": args.proxy,
        "proxy_open": proxy_open,
        "safety": [
            "Generates a minimal, deterministic observation set through Burp Proxy.",
            "Does not sign wallets, submit Solana transactions, run Burp Scanner, or fuzz broadly.",
            "Non-loopback targets require --allow-nonlocal-target.",
        ],
        "requests": requests,
        "websocket_upgrade": ws_observation,
        "summary": {
            "total": len(all_items),
            "unexpected": len(unexpected),
            "clusters": sorted({str(item.get("cluster")) for item in all_items if item}),
        },
        "history_import": {
            "mcp_regex": history_regex,
            "next_step": (
                "Run burp-sync to read matching Burp Proxy HTTP history through MCP and import it."
            ),
            "import_command": "python3 scripts/inferforge.py burp-sync --replace",
        },
    }
    output_path = artifact_dir / "burp-observation-run.json"
    write_json(output_path, artifact)

    print(f"Burp proxy open: {proxy_open}")
    for item in all_items:
        print(
            f"{item.get('id')} {item.get('method')} {item.get('path')} -> "
            f"{item.get('status')} ({'ok' if item.get('expected') else 'unexpected'})"
        )
    print(f"Wrote {output_path}")
    print(f"History regex: {history_regex}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="burp-observe",
            output_paths=[
                *target_profile_artifact_paths(artifact_dir),
                output_path,
            ],
        )
    )
    return 0 if proxy_open and not unexpected else 1


def import_burp_history_inputs(
    *,
    inputs: list[tuple[str, str]],
    profile: dict[str, Any],
    artifact_dir: Path,
    target: str,
    source_root: Path,
    node: str,
    replace: bool,
    all_hosts: bool,
    source: str,
    observed_only: bool,
) -> dict[str, Any]:
    target_netloc = None if all_hosts else urllib.parse.urlparse(target).netloc
    quote_path = probe_target_path(profile, "quote", "path", "/api/quote")
    imported: list[dict[str, Any]] = []
    burp_transaction_candidate_docs: list[dict[str, Any]] = []
    input_summaries: list[dict[str, Any]] = []
    for label, text in inputs:
        items = parse_burp_mcp_history_items(text)
        observations = normalize_burp_history_items(
            items,
            target_netloc=target_netloc,
            source=source,
        )
        transaction_candidate_doc = extract_transaction_candidates_from_burp_items(
            items,
            target_netloc=target_netloc,
            source=source,
            quote_path=quote_path,
        )
        imported.extend(observations)
        burp_transaction_candidate_docs.append(transaction_candidate_doc)
        input_summaries.append(
            {
                "input": label,
                "mcp_items": len(items),
                "observations_after_filter": len(observations),
                "quote_responses": transaction_candidate_doc["quote_response_count"],
                "transaction_candidates": transaction_candidate_doc["candidate_count"],
            }
        )

    history_path = artifact_dir / "burp-history-observations.jsonl"
    existing = [] if replace else load_jsonl(history_path)
    merged = dedupe_observations(existing + imported)
    append_jsonl(history_path, merged)
    burp_transaction_candidates = merge_transaction_candidate_docs(
        burp_transaction_candidate_docs,
        source=source,
    )
    write_json(artifact_dir / "burp-transaction-candidates.json", burp_transaction_candidates)

    clusters = build_clusters(profile, source_root)
    traffic_index = build_traffic_index([], merged)
    selection = select_cluster_ids(
        traffic_index,
        clusters,
        source_assisted=not observed_only,
    )
    write_json(artifact_dir / "endpoint-clusters.json", clusters)
    write_json(artifact_dir / "traffic-index.json", traffic_index)
    transaction_intent = build_transaction_intent(
        artifact_dir,
        load_jsonl(artifact_dir / "probe-results.jsonl"),
        node,
        source_root,
    )
    write_json(artifact_dir / "transaction-intent.json", transaction_intent)
    summary = {
        "generated_at": utc_now(),
        "source": source,
        "profile": profile_summary(profile),
        "target_filter": target_netloc or "all-hosts",
        "replace": replace,
        "inputs": input_summaries,
        "imported_observations": len(imported),
        "burp_history_items": len(merged),
        "burp_transaction_candidates": burp_transaction_candidates["candidate_count"],
        "transaction_intent_candidates": transaction_intent["candidates_seen"],
        "decoded_transactions": transaction_intent["decoded_transactions"],
        "selection": selection,
        "history_path": str(history_path),
    }
    write_json(artifact_dir / "collection-summary.json", summary)
    return summary


def run_import_burp_history(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)

    inputs: list[tuple[str, str]] = []
    for item in args.input or []:
        if item == "-":
            inputs.append(("stdin", sys.stdin.read()))
            continue
        path = Path(item).resolve()
        inputs.append((str(path), read_text(path)))

    if not inputs and not sys.stdin.isatty():
        inputs.append(("stdin", sys.stdin.read()))

    if not inputs:
        print("No Burp MCP history input provided; pass --input PATH or pipe raw MCP output on stdin")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="import-burp-history",
                output_paths=target_profile_artifact_paths(artifact_dir),
            )
        )
        return 2

    summary = import_burp_history_inputs(
        inputs=inputs,
        profile=profile,
        artifact_dir=artifact_dir,
        target=target,
        source_root=source_root,
        node=args.node,
        replace=args.replace,
        all_hosts=args.all_hosts,
        source=args.source,
        observed_only=args.observed_only,
    )

    print(f"Imported {summary['imported_observations']} observations from Burp MCP history")
    print(f"Stored {summary['burp_history_items']} total observations in {summary['history_path']}")
    print(f"Extracted {summary['burp_transaction_candidates']} Burp transaction candidates")
    print(
        "Transactions: "
        f"{summary['transaction_intent_candidates']} candidates, "
        f"{summary['decoded_transactions']} decoded"
    )
    print(f"Selected clusters: {', '.join(summary['selection']['selected_cluster_ids']) or '(none)'}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="import-burp-history",
            output_paths=[
                *target_profile_artifact_paths(artifact_dir),
                artifact_dir / "burp-history-observations.jsonl",
                artifact_dir / "burp-transaction-candidates.json",
                artifact_dir / "endpoint-clusters.json",
                artifact_dir / "traffic-index.json",
                artifact_dir / "transaction-intent.json",
                artifact_dir / "collection-summary.json",
            ],
        )
    )
    return 0


def build_profile_routing_selftest_profile() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "name": "profile-routing-selftest",
        "display_name": "Profile Routing Self-Test",
        "description": "Synthetic profile proving built-in strategies honor profile-owned concrete paths.",
        "target_type": "self-test",
        "frameworks": ["Next.js App Router", "Solana"],
        "default_target": "http://127.0.0.1:9999",
        "default_source_root": ".",
        "strategy_sets": [
            "nextjs-api-routes",
            "solana-json-rpc-proxy",
            "quote-transaction-decoder",
            "fixed-upstream-proxy",
        ],
        "safety": {
            "no_wallet_signing": True,
            "no_transaction_submission": True,
            "no_burp_scanner": True,
            "no_broad_fuzzing": True,
            "prefer_loopback_targets": True,
        },
        "probe_targets": {
            "health": {"path": "/statusz"},
            "route-custom-api-widgets": {"path": "/custom/api/widgets"},
            "quote": {"path": "/bridge/quote"},
            "solana-rpc-http": {
                "path": "/chain/solana/devnet",
                "root_path": "/chain/rpc",
                "unknown_cluster_path": "/chain/solana/localnet",
                "cluster": "devnet",
                "unknown_cluster": "localnet",
            },
            "solana-rpc-ws": {"path": "/ws/solana/devnet"},
            "orca-pools": {
                "path_template": "/poolz/{address}",
                "invalid_address_path": "/poolz/not-an-address",
                "invalid_base58_path": "/poolz/0OIlnotbase58",
                "too_short_path": "/poolz/1111111111111111111111111111111",
                "too_long_path": "/poolz/111111111111111111111111111111111111111111111",
                "encoded_traversal_path": "/poolz/%2e%2e%2fstatusz",
                "extra_segment_path": "/poolz/not-an-address/extra",
                "query_injection_path": "/poolz/not-an-address?url=https://evil.example",
            },
        },
        "clusters": [
            {
                "id": "health",
                "method": "GET",
                "path": "/statusz",
                "kind": "health",
                "priority": "low",
                "strategy_set": "nextjs-api-routes",
                "match": {"methods": ["GET"], "paths": ["/statusz"]},
                "source_refs": [],
            },
            {
                "id": "quote",
                "method": "POST",
                "path": "/bridge/quote",
                "kind": "orchestration-proxy",
                "priority": "high",
                "strategy_set": "quote-transaction-decoder",
                "match": {"methods": ["POST"], "paths": ["/bridge/quote"]},
                "source_refs": [],
            },
            {
                "id": "route-custom-api-widgets",
                "method": "POST",
                "path": "/custom/api/widgets",
                "kind": "api-route",
                "priority": "medium",
                "strategy_set": "nextjs-api-routes",
                "match": {"methods": ["POST"], "paths": ["/custom/api/widgets"]},
                "source_refs": ["scripts/inferforge.py"],
            },
            {
                "id": "solana-rpc-http",
                "method": "POST",
                "path": "/chain/solana/{cluster}",
                "kind": "json-rpc-proxy",
                "priority": "high",
                "strategy_set": "solana-json-rpc-proxy",
                "match": {
                    "methods": ["OPTIONS", "POST"],
                    "paths": ["/chain/rpc"],
                    "path_prefixes": ["/chain/solana/"],
                },
                "source_refs": [],
            },
            {
                "id": "solana-rpc-ws",
                "method": "WS",
                "path": "/ws/solana/{cluster}",
                "kind": "websocket-json-rpc-proxy",
                "priority": "high",
                "strategy_set": "solana-json-rpc-proxy",
                "match": {"methods": ["WS"], "path_prefixes": ["/ws/solana/"]},
                "source_refs": [],
            },
            {
                "id": "orca-pools",
                "method": "GET",
                "path": "/poolz/{address}",
                "kind": "fixed-upstream-proxy",
                "priority": "medium",
                "strategy_set": "fixed-upstream-proxy",
                "match": {"methods": ["GET"], "path_prefixes": ["/poolz/"]},
                "source_refs": [],
            },
        ],
        "source_peeks": [],
        "burp_observation_plan": [
            {
                "id": "burp_observe_statusz",
                "method": "GET",
                "path": "/statusz",
                "headers": {"User-Agent": "InferForge-Burp-Observe/0.1"},
                "expected_statuses": [200],
                "cluster": "health",
            }
        ],
        "websocket_observation": {
            "id": "burp_observe_ws_upgrade",
            "path": "/ws/solana/devnet",
            "cluster": "solana-rpc-ws",
            "expected_statuses": [101],
            "subscribe_method": "slotSubscribe",
        },
        "_profile_path": "self-test",
        "_profile_loaded_from": "file",
        "_profile_defaulted_keys": [],
    }


def run_profile_routing_selftest(args: argparse.Namespace) -> int:
    profile, artifact_dir, current_target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    test_profile = build_profile_routing_selftest_profile()
    target = test_profile["default_target"]
    clusters = build_clusters(test_profile, ROOT)
    cluster_ids = {str(cluster["id"]) for cluster in clusters.get("clusters", [])}
    probes = build_probe_plan(target, include_external=True, selected_clusters=cluster_ids, profile=test_profile)
    warmups = build_warmup_probes(target, test_profile, cluster_ids)
    observation_plan = build_burp_observation_plan(target, test_profile)
    validation = build_profile_validation_artifact(test_profile, clusters, ROOT)
    unsafe_observation_profile = json_clone(test_profile)
    unsafe_observation_profile["burp_observation_plan"] = [
        {
            "id": "burp_observe_placeholder_path",
            "method": "GET",
            "path": PLACEHOLDER_APPROVED_CONCRETE_PATH,
            "headers": {"User-Agent": "InferForge-Burp-Observe/0.1"},
            "expected_statuses": [200],
            "cluster": "health",
        }
    ]
    unsafe_observation_validation = build_profile_validation_artifact(
        unsafe_observation_profile,
        build_clusters(unsafe_observation_profile, ROOT),
        ROOT,
    )
    unsafe_observation_build_blocked = False
    unsafe_observation_build_error = None
    try:
        build_burp_observation_plan(target, unsafe_observation_profile)
    except ValueError as error:
        unsafe_observation_build_blocked = True
        unsafe_observation_build_error = str(error)
    unsafe_observation_validation_passed = (
        unsafe_observation_validation.get("status") == "failed"
        and unsafe_observation_build_blocked
        and any(
            item.get("id") == "burp-observation-plan:burp_observe_placeholder_path:unsafe-path"
            for item in unsafe_observation_validation.get("issues", [])
        )
    )
    with tempfile.TemporaryDirectory(prefix="inferforge-discovery-selftest-") as temp_dir:
        rewrite_source_root = Path(temp_dir) / "rewrite-app"
        (rewrite_source_root / "src/app/health").mkdir(parents=True)
        (rewrite_source_root / "src/app/health/route.ts").write_text(
            "export async function GET() { return Response.json({ ok: true }) }\n",
            encoding="utf-8",
        )
        (rewrite_source_root / "app/api/root").mkdir(parents=True)
        (rewrite_source_root / "app/api/root/route.ts").write_text(
            "export async function POST() { return Response.json({ ok: true }) }\n",
            encoding="utf-8",
        )
        (rewrite_source_root / "src/app/actions.ts").write_text(
            textwrap.dedent(
                """
                'use server'

                export async function updateWidget(id: string) {
                  return { ok: Boolean(id) }
                }

                export const deleteWidget = async (id: string) => {
                  return { deleted: Boolean(id) }
                }
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (rewrite_source_root / "src/pages/api").mkdir(parents=True)
        (rewrite_source_root / "src/pages/api/widgets.ts").write_text(
            textwrap.dedent(
                """
                export default function handler(req, res) {
                  if (req.method === 'GET') {
                    res.status(200).json({ ok: true })
                    return
                  }
                  res.status(405).end()
                }
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (rewrite_source_root / "src/middleware.ts").write_text(
            textwrap.dedent(
                """
                import { NextResponse } from 'next/server'

                export function middleware() {
                  return NextResponse.next()
                }

                export const config = {
                  matcher: ['/api/:path*'],
                }
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (rewrite_source_root / "next.config.ts").write_text(
            textwrap.dedent(
                """
                const API_TARGET = process.env.API_TARGET ?? 'https://api.example.test'

                const nextConfig = {
                  async rewrites() {
                    return {
                      beforeFiles: [
                        {
                          source: '/api/proxy/:path*',
                          destination: `${API_TARGET}/v1/:path*`,
                          has: [
                            { type: 'header', key: 'x-approved-proxy', value: 'yes' },
                          ],
                        },
                      ],
                    }
                  },
                  async redirects() {
                    return [
                      {
                        source: '/old/:path*',
                        destination: '/api/proxy/:path*',
                        permanent: false,
                        missing: [
                          { type: 'cookie', key: 'new-ui' },
                        ],
                      },
                    ]
                  },
                  async headers() {
                    return [
                      {
                        source: '/api/:path*',
                        has: [
                          { type: 'query', key: 'debug', value: '1' },
                        ],
                        headers: [
                          { key: 'X-InferForge-Selftest', value: 'enabled' },
                        ],
                      },
                    ]
                  },
                }

                export default nextConfig
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (rewrite_source_root / "server.js").write_text(
            textwrap.dedent(
                """
                import http from 'node:http'
                import { WebSocketServer } from 'ws'

                const SOLANA_RPC_PATH_PREFIX = '/api/rpc/solana/'
                const wss = new WebSocketServer({ noServer: true })

                function getSolanaClusterFromPathname(pathname) {
                  if (!pathname.startsWith(SOLANA_RPC_PATH_PREFIX)) {
                    return null
                  }
                  return pathname.slice(SOLANA_RPC_PATH_PREFIX.length)
                }

                function isAllowedOrigin(req) {
                  return Boolean(req.headers.origin)
                }

                function handleSolanaWsProxy(cluster, req, socket, head) {
                  wss.handleUpgrade(req, socket, head, () => {})
                }

                const server = http.createServer()
                server.on('upgrade', (req, socket, head) => {
                  const cluster = getSolanaClusterFromPathname(new URL(req.url || '/', 'http://localhost').pathname)
                  if (cluster) {
                    handleSolanaWsProxy(cluster, req, socket, head)
                  }
                })
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        rewrite_inventory = discover_nextjs_routes(rewrite_source_root)
        rewrite_profile = build_discovered_profile(
            rewrite_inventory,
            name="rewrite-discovery-selftest",
            display_name="Rewrite Discovery Self-Test",
            target="http://127.0.0.1:9998",
            source_root=rewrite_source_root,
        )
        rewrite_observation_clusters = {
            str(item.get("cluster"))
            for item in rewrite_profile.get("burp_observation_plan", [])
        }
        rewrite_profile_candidates = [
            item
            for item in rewrite_profile.get("review_observation_candidates", [])
            if item.get("cluster") == "route-api-proxy-path"
        ]
        rewrite_normalized = normalize_target_profile(rewrite_profile)
        rewrite_clusters = build_clusters(rewrite_normalized, rewrite_source_root)
        rewrite_validation = build_profile_validation_artifact(
            rewrite_normalized,
            rewrite_clusters,
            rewrite_source_root,
        )
        rewrite_cluster = next(
            (
                cluster
                for cluster in rewrite_clusters.get("clusters", [])
                if cluster.get("id") == "route-api-proxy-path"
            ),
            None,
        )
        pages_api_cluster = next(
            (
                cluster
                for cluster in rewrite_clusters.get("clusters", [])
                if cluster.get("id") == "route-api-widgets"
            ),
            None,
        )
        root_app_cluster = next(
            (
                cluster
                for cluster in rewrite_clusters.get("clusters", [])
                if cluster.get("id") == "route-api-root"
            ),
            None,
        )
        server_action_entries = rewrite_inventory.get("server_actions", [])
        rewrite_cluster_candidates = (
            []
            if rewrite_cluster is None
            else rewrite_cluster.get("discovery", {}).get("review_observation_candidates", [])
        )
        rewrite_condition_context = build_request_context(
            "GET",
            "/api/proxy/users/42",
            {"x-approved-proxy": "yes", "host": "127.0.0.1:9998"},
            "127.0.0.1:9998",
        )
        rewrite_condition_missing_context = build_request_context(
            "GET",
            "/api/proxy/users/42",
            {"host": "127.0.0.1:9998"},
            "127.0.0.1:9998",
        )
        rewrite_resolution = resolve_endpoint_sources(
            rewrite_source_root,
            "GET",
            "/api/proxy/users/42",
            rewrite_inventory,
            rewrite_condition_context,
        )
        rewrite_condition_missing_resolution = resolve_endpoint_sources(
            rewrite_source_root,
            "GET",
            "/api/proxy/users/42",
            rewrite_inventory,
            rewrite_condition_missing_context,
        )
        rewrite_resolution_match = next(
            (
                match
                for match in rewrite_resolution.get("matches", [])
                if match.get("cluster_id") == "route-api-proxy-path"
            ),
            None,
        )
        rewrite_condition_missing_match = next(
            (
                match
                for match in rewrite_condition_missing_resolution.get("matches", [])
                if match.get("cluster_id") == "route-api-proxy-path"
            ),
            None,
        )
        ws_resolution = resolve_endpoint_sources(
            rewrite_source_root,
            "WS",
            "/api/rpc/solana/devnet",
            rewrite_inventory,
        )
        ws_resolution_match = next(
            (
                match
                for match in ws_resolution.get("matches", [])
                if match.get("cluster_id") == "solana-rpc-ws"
            ),
            None,
        )
        pages_api_debug_context = build_request_context(
            "GET",
            "/api/widgets?debug=1",
            {"host": "127.0.0.1:9998"},
            "127.0.0.1:9998",
        )
        pages_api_no_debug_context = build_request_context(
            "GET",
            "/api/widgets",
            {"host": "127.0.0.1:9998"},
            "127.0.0.1:9998",
        )
        pages_api_resolution = resolve_endpoint_sources(
            rewrite_source_root,
            "GET",
            "/api/widgets?debug=1",
            rewrite_inventory,
            pages_api_debug_context,
        )
        pages_api_no_debug_resolution = resolve_endpoint_sources(
            rewrite_source_root,
            "GET",
            "/api/widgets",
            rewrite_inventory,
            pages_api_no_debug_context,
        )
        pages_api_resolution_match = next(
            (
                match
                for match in pages_api_resolution.get("matches", [])
                if match.get("cluster_id") == "route-api-widgets"
            ),
            None,
        )
        root_app_resolution = resolve_endpoint_sources(
            rewrite_source_root,
            "POST",
            "/api/root",
            rewrite_inventory,
        )
        root_app_resolution_match = next(
            (
                match
                for match in root_app_resolution.get("matches", [])
                if match.get("cluster_id") == "route-api-root"
            ),
            None,
        )
        redirect_missing_cookie_context = build_request_context(
            "GET",
            "/old/users/42",
            {"host": "127.0.0.1:9998"},
            "127.0.0.1:9998",
        )
        redirect_cookie_present_context = build_request_context(
            "GET",
            "/old/users/42",
            {"host": "127.0.0.1:9998", "cookie": "new-ui=1"},
            "127.0.0.1:9998",
        )
        redirect_resolution = resolve_endpoint_sources(
            rewrite_source_root,
            "GET",
            "/old/users/42",
            rewrite_inventory,
            redirect_missing_cookie_context,
        )
        redirect_cookie_present_resolution = resolve_endpoint_sources(
            rewrite_source_root,
            "GET",
            "/old/users/42",
            rewrite_inventory,
            redirect_cookie_present_context,
        )
        rewrite_middleware_context = rewrite_resolution.get("middleware_context", [])
        pages_api_middleware_context = pages_api_resolution.get("middleware_context", [])
        pages_api_route_policy_context = pages_api_resolution.get("route_policy_context", [])
        pages_api_no_debug_route_policy_context = pages_api_no_debug_resolution.get("route_policy_context", [])
        rewrite_route_policy_context = rewrite_resolution.get("route_policy_context", [])
        redirect_route_policy_context = redirect_resolution.get("route_policy_context", [])
        redirect_cookie_present_route_policy_context = redirect_cookie_present_resolution.get("route_policy_context", [])
        promoted_rewrite_profile = None
        promoted_rewrite_observation = None
        promoted_rewrite_paths: set[str] = set()
        promotion_error = None
        try:
            promoted_rewrite_profile, promoted_rewrite_observation = promote_review_observation_candidate(
                rewrite_profile,
                candidate_id="review_observe_route_api_proxy_path_approved_path",
                approved_path="/api/proxy/users/42",
                note="self-test approved read-only path",
            )
            promoted_rewrite_plan = build_burp_observation_plan(
                "http://127.0.0.1:9998",
                normalize_target_profile(promoted_rewrite_profile),
            )
            promoted_rewrite_paths = {str(item.get("path")) for item in promoted_rewrite_plan}
        except ValueError as error:
            promotion_error = str(error)
        rejected_promotion_paths: dict[str, bool] = {}
        for invalid_path in [
            "/api/proxy/{path*}",
            "/api/proxy/<approved-read-only-path>",
            "https://api.example.test/v1/users/42",
            "/api/other/users/42",
        ]:
            try:
                promote_review_observation_candidate(
                    rewrite_profile,
                    candidate_id="review_observe_route_api_proxy_path_approved_path",
                    approved_path=invalid_path,
                )
                rejected_promotion_paths[invalid_path] = False
            except ValueError:
                rejected_promotion_paths[invalid_path] = True
        promotion_selftest_passed = (
            promoted_rewrite_observation is not None
            and promoted_rewrite_observation.get("path") == "/api/proxy/users/42"
            and promoted_rewrite_observation.get("cluster") == "route-api-proxy-path"
            and "/api/proxy/users/42" in promoted_rewrite_paths
            and all(rejected_promotion_paths.values())
        )
        queue_artifact_dir = Path(temp_dir) / "queue-artifacts"
        queue_artifact_dir.mkdir()
        rewrite_gap_id = "GAP-route-api-proxy-path-burp-observation"
        rewrite_queue = build_verification_queue(
            "http://127.0.0.1:9998",
            rewrite_clusters,
            {"clusters": []},
            {
                "gaps": [
                    {
                        "id": rewrite_gap_id,
                        "cluster_id": "route-api-proxy-path",
                        "title": "Browser-flow observation missing",
                        "priority": "low",
                        "reason": "Review-only rewrite observation candidate requires promotion.",
                        "safe_next_step": "Promote one approved concrete path.",
                        "safety_gate": "Review-only candidate; no automatic request.",
                        "review_candidates": rewrite_profile_candidates,
                    }
                ]
            },
            {"status": "covered-with-evidence-gaps"},
            {"status": "no-reportable-findings", "external_blockers": [], "decisions": []},
            {"status": "ready"},
            queue_artifact_dir,
        )
        rewrite_queue_item = next(
            (
                item
                for item in rewrite_queue.get("items", [])
                if item.get("id") == f"RESOLVE-{rewrite_gap_id}"
            ),
            None,
        )
        rewrite_queue_commands = [] if rewrite_queue_item is None else rewrite_queue_item.get("commands", [])
        rewrite_queue_command_safety = (
            {}
            if rewrite_queue_item is None
            else (rewrite_queue_item.get("command_safety", {}) or {}).get("summary", {})
        )
        rewrite_queue_command_counts = rewrite_queue_command_safety.get("classification_counts", {})
        rewrite_queue_global_command_safety = rewrite_queue.get("summary", {}).get("command_safety", {})
        unsafe_command_classification = classify_verification_command(
            "python3 scripts/inferforge.py promote-observation-candidate --path <approved-path>",
            source="self-test:unsafe-shell-placeholder",
        )
        queue_promotion_selftest_passed = (
            rewrite_queue_item is not None
            and len(rewrite_queue_commands) == 4
            and "promote-observation-candidate" in rewrite_queue_commands[0]
            and f"--path {PLACEHOLDER_APPROVED_CONCRETE_PATH}" in rewrite_queue_commands[0]
            and "reviewed-profile.json" in rewrite_queue_commands[0]
            and "--no-write" in rewrite_queue_commands[0]
            and "promote-observation-candidate" in rewrite_queue_commands[1]
            and f"--path {PLACEHOLDER_APPROVED_CONCRETE_PATH}" in rewrite_queue_commands[1]
            and "reviewed-profile.json" in rewrite_queue_commands[1]
            and "--no-write" not in rewrite_queue_commands[1]
            and "burp-sync --observe" in rewrite_queue_commands[2]
            and "audit --include-external --ws-resource-probes" in rewrite_queue_commands[3]
            and all(command.count("--profile") <= 1 for command in rewrite_queue_commands)
            and all(command.count("--artifact-dir") == 1 for command in rewrite_queue_commands)
            and rewrite_queue_command_counts.get("manual-template") == 2
            and rewrite_queue_command_counts.get("review-gated") == 2
            and rewrite_queue_command_safety.get("unsafe_template_count") == 0
            and rewrite_queue_global_command_safety.get("unsafe_template_count") == 0
            and unsafe_command_classification.get("classification") == "unsafe-template"
            and "shell-angle-placeholder-or-redirection" in unsafe_command_classification.get("issues", [])
        )
        rewrite_source_peeks = build_source_peeks(
            rewrite_source_root,
            rewrite_profile,
            [
                {
                    "method": "POST",
                    "path": "/api/root",
                    "request_context": build_request_context(
                        "POST",
                        "/api/root",
                        {"host": "127.0.0.1:9998"},
                        "127.0.0.1:9998",
                    ),
                }
            ],
        )
        rewrite_source_resolver_report = build_source_resolver_report_summary(rewrite_source_peeks)
        server_action_only_clusters = {
            "generated_at": utc_now(),
            "profile": rewrite_clusters.get("profile", {}),
            "clusters": [],
        }
        rewrite_server_action_gaps = build_evidence_gaps(
            server_action_only_clusters,
            [],
            [],
            {"candidates_seen": 1},
            source_peeks=rewrite_source_peeks,
        )
        rewrite_server_action_gap = next(
            (
                gap
                for gap in rewrite_server_action_gaps.get("gaps", [])
                if str(gap.get("id", "")).startswith("GAP-server-action-")
            ),
            None,
        )
        rewrite_server_action_queue = build_verification_queue(
            "http://127.0.0.1:9998",
            server_action_only_clusters,
            {"clusters": []},
            rewrite_server_action_gaps,
            {"status": "covered-with-evidence-gaps"},
            {"status": "no-reportable-findings", "external_blockers": [], "decisions": []},
            {"status": "ready"},
            queue_artifact_dir,
        )
        rewrite_server_action_queue_item = next(
            (
                item
                for item in rewrite_server_action_queue.get("items", [])
                if item.get("id") == f"RESOLVE-{rewrite_server_action_gap.get('id')}"
            ),
            None,
        ) if rewrite_server_action_gap else None
        rewrite_server_action_candidates = (
            []
            if rewrite_server_action_queue_item is None
            else rewrite_server_action_queue_item.get("review_candidates", [])
        )
        rewrite_server_action_gap_passed = (
            rewrite_server_action_gap is not None
            and rewrite_server_action_gap.get("cluster_id") == "server-actions"
            and rewrite_server_action_gap.get("priority") == "high"
            and "updateWidget" in rewrite_server_action_gap.get("reason", "")
            and "deleteWidget" in rewrite_server_action_gap.get("reason", "")
            and rewrite_server_action_queue_item is not None
            and rewrite_server_action_queue_item.get("status") == "manual-review"
            and rewrite_server_action_queue_item.get("commands") == []
            and "source-peek-results.json" in rewrite_server_action_queue_item.get("evidence_refs", [])
            and len(rewrite_server_action_candidates) == 1
            and rewrite_server_action_candidates[0].get("type") == "server-action-source-review"
            and rewrite_server_action_candidates[0].get("status") == "manual-review"
            and {"updateWidget", "deleteWidget"}.issubset(set(rewrite_server_action_candidates[0].get("action_names", [])))
            and rewrite_server_action_queue.get("summary", {}).get("command_safety", {}).get("unsafe_template_count") == 0
            and not any(str(cluster.get("id", "")).startswith("server_action") for cluster in rewrite_clusters.get("clusters", []))
        )
        rewrite_source_peek_requests = build_source_peek_requests(
            rewrite_clusters,
            {
                "generated_at": utc_now(),
                "endpoints": [
                    {
                        "method": "POST",
                        "path": "/api/root",
                        "statuses": [200],
                        "probe_ids": ["selftest-root-route"],
                        "observed_via": "safe-local-probe",
                    }
                ],
            },
            rewrite_source_peeks,
            [],
            rewrite_server_action_gaps,
        )
        rewrite_source_peek_request_ids = {
            str(item.get("id"))
            for item in rewrite_source_peek_requests.get("requests", [])
        }
        rewrite_source_peek_request_triggers = (
            rewrite_source_peek_requests.get("summary", {}).get("trigger_counts", {})
        )
        rewrite_source_peek_requests_passed = (
            rewrite_source_peek_requests.get("status") == "answered-with-manual-review"
            and any(request_id.startswith("PEEK-endpoint-") for request_id in rewrite_source_peek_request_ids)
            and any(request_id.startswith("PEEK-server-action-") for request_id in rewrite_source_peek_request_ids)
            and any(request_id.startswith("PEEK-gap-gap_server_action_") for request_id in rewrite_source_peek_request_ids)
            and rewrite_source_peek_request_triggers.get("observed-endpoint") == 1
            and rewrite_source_peek_request_triggers.get("source-only-server-action-discovery") == 1
            and rewrite_source_peek_request_triggers.get("evidence-gap") == 1
        )
        rewrite_burp_observation_coverage = build_burp_observation_coverage(
            "http://127.0.0.1:9998",
            rewrite_profile,
            rewrite_clusters,
            [],
            {
                "generated_at": utc_now(),
                "status": "observed",
                "summary": {
                    "total": 1,
                    "unexpected": 0,
                    "clusters": ["route-api-root"],
                },
                "requests": [
                    {
                        "id": "burp_observe_route_api_root",
                        "cluster": "route-api-root",
                        "method": "POST",
                        "path": "/api/root",
                        "expected": True,
                    }
                ],
            },
            {
                "gaps": [
                    {
                        "id": rewrite_gap_id,
                        "cluster_id": "route-api-proxy-path",
                    }
                ]
            },
        )
        rewrite_burp_rows = {
            item.get("cluster_id"): item
            for item in rewrite_burp_observation_coverage.get("clusters", [])
        }
        rewrite_burp_observation_coverage_passed = (
            rewrite_burp_observation_coverage.get("status") == "needs-human-review"
            and rewrite_burp_rows.get("route-api-root", {}).get("status") == "observe-run-generated-not-imported"
            and rewrite_burp_rows.get("route-api-proxy-path", {}).get("status") == "needs-reviewed-observation-promotion"
            and rewrite_burp_rows.get("route-api-proxy-path", {}).get("review_candidate_count") == 1
            and rewrite_gap_id in rewrite_burp_rows.get("route-api-proxy-path", {}).get("evidence_gaps", [])
        )
        rewrite_server_action_report_lines = rewrite_source_resolver_report.get("server_action_lines", [])
        rewrite_discovery_passed = (
            rewrite_inventory.get("summary", {}).get("rewrite_count") == 1
            and rewrite_inventory.get("summary", {}).get("app_router_route_count") == 2
            and rewrite_inventory.get("summary", {}).get("pages_router_api_route_count") == 1
            and rewrite_inventory.get("summary", {}).get("middleware_count") == 1
            and rewrite_inventory.get("summary", {}).get("server_action_file_count") == 1
            and rewrite_inventory.get("summary", {}).get("server_action_export_count") == 2
            and rewrite_inventory.get("summary", {}).get("redirect_count") == 1
            and rewrite_inventory.get("summary", {}).get("header_route_count") == 1
            and rewrite_inventory.get("summary", {}).get("custom_server_entrypoint_count") == 1
            and "health" in rewrite_observation_clusters
            and "route-api-widgets" in rewrite_observation_clusters
            and "route-api-root" in rewrite_observation_clusters
            and "route-api-proxy-path" not in rewrite_observation_clusters
            and "Next.js Server Actions" in rewrite_profile.get("frameworks", [])
            and (rewrite_profile.get("websocket_observation") or {}).get("cluster") == "solana-rpc-ws"
            and rewrite_validation.get("status") != "failed"
            and rewrite_cluster is not None
            and rewrite_cluster.get("kind") == "rewrite-proxy"
            and rewrite_cluster.get("strategy_set") == "fixed-upstream-proxy"
            and any(str(ref).endswith("next.config.ts") for ref in rewrite_cluster.get("source_refs", []))
            and "/api/proxy/" in (rewrite_cluster.get("match") or {}).get("path_prefixes", [])
            and "https://api.example.test" in rewrite_cluster.get("discovery", {}).get("fixed_upstreams", [])
            and any(
                item.get("phase") == "beforeFiles"
                and item.get("conditional") is True
                and (item.get("conditions") or {}).get("has")
                for item in rewrite_cluster.get("discovery", {}).get("rewrites", [])
            )
            and len(rewrite_profile_candidates) == 1
            and rewrite_profile_candidates[0].get("status") == "review-only"
            and rewrite_profile_candidates[0].get("example_path") == "/api/proxy/<approved-read-only-path>"
            and rewrite_cluster_candidates
            and rewrite_cluster_candidates[0].get("status") == "review-only"
            and "route-api-proxy-path" in classify_endpoint("GET", "/api/proxy/users/42", rewrite_clusters)
            and rewrite_resolution_match is not None
            and str(rewrite_resolution_match.get("source_ref", "")).endswith("next.config.ts")
            and "rewrite-phase:beforeFiles" in rewrite_resolution_match.get("match_reasons", [])
            and "conditional-route" in rewrite_resolution_match.get("match_reasons", [])
            and "condition-satisfied" in rewrite_resolution_match.get("match_reasons", [])
            and rewrite_resolution_match.get("condition_status") == "condition-satisfied"
            and rewrite_resolution_match.get("applicability") == "path-match-condition-satisfied"
            and not str((rewrite_resolution_match.get("line_refs") or {}).get("rewrite_source", "")).endswith(":not-found")
            and not str((rewrite_resolution_match.get("line_refs") or {}).get("rewrite_destination", "")).endswith(":not-found")
            and not str((rewrite_resolution_match.get("line_refs") or {}).get("has_conditions", "")).endswith(":not-found")
            and rewrite_condition_missing_match is not None
            and rewrite_condition_missing_match.get("condition_status") == "condition-not-satisfied"
            and rewrite_condition_missing_match.get("applicability") == "path-match-condition-not-satisfied"
            and ws_resolution_match is not None
            and str(ws_resolution_match.get("source_ref", "")).endswith("server.js")
            and not str((ws_resolution_match.get("line_refs") or {}).get("upgrade_handler", "")).endswith(":not-found")
            and not str((ws_resolution_match.get("line_refs") or {}).get("proxy_handler", "")).endswith(":not-found")
            and pages_api_cluster is not None
            and pages_api_cluster.get("strategy_set") == "nextjs-api-routes"
            and any(
                route.get("router") == "pages"
                for route in pages_api_cluster.get("discovery", {}).get("routes", [])
            )
            and pages_api_resolution_match is not None
            and str(pages_api_resolution_match.get("source_ref", "")).endswith("src/pages/api/widgets.ts")
            and root_app_cluster is not None
            and root_app_cluster.get("strategy_set") == "nextjs-api-routes"
            and any(
                route.get("router") == "app" and route.get("source_path") == "/api/root"
                for route in root_app_cluster.get("discovery", {}).get("routes", [])
            )
            and root_app_resolution_match is not None
            and str(root_app_resolution_match.get("source_ref", "")).endswith("app/api/root/route.ts")
            and len(server_action_entries) == 1
            and {"updateWidget", "deleteWidget"}.issubset(set(server_action_entries[0].get("action_names", [])))
            and not any(str(cluster.get("id", "")).startswith("server_action") for cluster in rewrite_clusters.get("clusters", []))
            and any("updateWidget" in line and "deleteWidget" in line for line in rewrite_server_action_report_lines)
            and rewrite_server_action_gap_passed
            and rewrite_source_peek_requests_passed
            and rewrite_burp_observation_coverage_passed
            and any(
                item.get("match_status") == "matched-static-matcher"
                and str(item.get("source_ref", "")).endswith("src/middleware.ts")
                for item in pages_api_middleware_context
            )
            and any(
                item.get("match_status") == "matched-static-matcher"
                and str(item.get("source_ref", "")).endswith("src/middleware.ts")
                for item in rewrite_middleware_context
            )
            and any(
                item.get("kind") == "next-config-headers"
                and item.get("match_status") == "matched-conditional-policy"
                and item.get("condition_status") == "condition-satisfied"
                and item.get("applicability") == "path-match-condition-satisfied"
                and "X-InferForge-Selftest" in (item.get("route_policy") or {}).get("header_keys", [])
                and (item.get("route_policy") or {}).get("conditional") is True
                and (item.get("route_policy") or {}).get("conditions", {}).get("has")
                for item in pages_api_route_policy_context
            )
            and any(
                item.get("kind") == "next-config-headers"
                and item.get("match_status") == "matched-conditional-policy"
                and item.get("condition_status") == "condition-not-satisfied"
                and item.get("applicability") == "path-match-condition-not-satisfied"
                for item in pages_api_no_debug_route_policy_context
            )
            and any(
                item.get("kind") == "next-config-headers"
                and item.get("match_status") == "matched-conditional-policy"
                and item.get("condition_status") == "condition-not-satisfied"
                for item in rewrite_route_policy_context
            )
            and any(
                item.get("kind") == "next-config-redirect"
                and item.get("match_status") == "matched-conditional-policy"
                and item.get("condition_status") == "condition-satisfied"
                and item.get("applicability") == "path-match-condition-satisfied"
                and (item.get("route_policy") or {}).get("status_code") == 307
                and (item.get("route_policy") or {}).get("conditions", {}).get("missing")
                for item in redirect_route_policy_context
            )
            and any(
                item.get("kind") == "next-config-redirect"
                and item.get("match_status") == "matched-conditional-policy"
                and item.get("condition_status") == "condition-not-satisfied"
                and item.get("applicability") == "path-match-condition-not-satisfied"
                for item in redirect_cookie_present_route_policy_context
            )
            and promotion_selftest_passed
            and queue_promotion_selftest_passed
        )
        initial_artifact_dir = Path(temp_dir) / "initial-artifacts"
        initial_artifact_dir.mkdir()
        ensure_initial_audit_artifacts(initial_artifact_dir)
        initial_observation = json.loads(read_text(initial_artifact_dir / "burp-observation-run.json"))
        initial_quote_collection = json.loads(read_text(initial_artifact_dir / "quote-collection.json"))
        initial_artifacts_passed = (
            (initial_artifact_dir / "burp-history-observations.jsonl").exists()
            and initial_observation.get("status") == "not-run"
            and initial_quote_collection.get("status") == "not-collected"
            and initial_quote_collection.get("diagnosis", {}).get("classification") == "quote-collection-not-run"
        )
        target_lock = TargetProbeLock("http://127.0.0.1:9997", purpose="self-test")
        nested_lock_blocked = False
        with target_lock:
            try:
                with TargetProbeLock("http://127.0.0.1:9997", purpose="self-test-nested"):
                    pass
            except RuntimeError:
                nested_lock_blocked = True
        target_lock_passed = nested_lock_blocked and not target_lock.path.exists()

        configured_source_root = Path(temp_dir) / "configured-app"
        (configured_source_root / "src/app/api/widgets").mkdir(parents=True)
        (configured_source_root / "src/app/api/widgets/route.ts").write_text(
            "export async function GET() { return Response.json({ ok: true }) }\n",
            encoding="utf-8",
        )
        (configured_source_root / "src/pages/api").mkdir(parents=True)
        (configured_source_root / "src/pages/api/legacy.ts").write_text(
            textwrap.dedent(
                """
                export default function handler(req, res) {
                  if (req.method === 'POST') {
                    res.status(200).json({ ok: true })
                    return
                  }
                  res.status(405).end()
                }
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        (configured_source_root / "next.config.ts").write_text(
            textwrap.dedent(
                """
                const nextConfig = {
                  async headers() {
                    return [
                      {
                        source: '/static/:path*',
                        basePath: false,
                        headers: [
                          { key: 'X-Selftest-Static', value: '1' },
                        ],
                      },
                    ]
                  },
                  basePath: '/console',
                  trailingSlash: true,
                  i18n: {
                    locales: ['en', 'fr'],
                    defaultLocale: 'en',
                  },
                  async rewrites() {
                    return [
                      {
                        source: '/api/proxy/:path*',
                        destination: 'https://api.example.test/:path*',
                        has: [
                          { type: 'header', key: 'x-approved-proxy', value: 'yes' },
                        ],
                      },
                    ]
                  },
                }

                export default nextConfig
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        configured_inventory = discover_nextjs_routes(configured_source_root)
        configured_profile = build_discovered_profile(
            configured_inventory,
            name="configured-nextjs-selftest",
            display_name="Configured Next.js Self-Test",
            target="http://127.0.0.1:9996",
            source_root=configured_source_root,
        )
        configured_clusters = build_clusters(normalize_target_profile(configured_profile), configured_source_root)
        configured_widget_route = next(
            (
                route
                for route in configured_inventory.get("routes", [])
                if route.get("source_path") == "/api/widgets"
            ),
            None,
        )
        configured_legacy_route = next(
            (
                route
                for route in configured_inventory.get("routes", [])
                if route.get("source_path") == "/api/legacy"
            ),
            None,
        )
        configured_rewrite = next(
            (
                rewrite
                for rewrite in configured_inventory.get("rewrites", [])
                if rewrite.get("source_path") == "/api/proxy/{path*}"
            ),
            None,
        )
        configured_widget_resolution = resolve_endpoint_sources(
            configured_source_root,
            "GET",
            "/console/fr/api/widgets/",
            configured_inventory,
            build_request_context("GET", "/console/fr/api/widgets/", {"host": "127.0.0.1:9996"}, "127.0.0.1:9996"),
        )
        configured_widget_match = next(
            (
                match
                for match in configured_widget_resolution.get("matches", [])
                if match.get("cluster_id") == "route-api-widgets"
            ),
            None,
        )
        configured_rewrite_resolution = resolve_endpoint_sources(
            configured_source_root,
            "GET",
            "/console/fr/api/proxy/users/42",
            configured_inventory,
            build_request_context(
                "GET",
                "/console/fr/api/proxy/users/42",
                {"host": "127.0.0.1:9996", "x-approved-proxy": "yes"},
                "127.0.0.1:9996",
            ),
        )
        configured_rewrite_match = next(
            (
                match
                for match in configured_rewrite_resolution.get("matches", [])
                if match.get("cluster_id") == "route-api-proxy-path"
            ),
            None,
        )
        configured_source_resolver_report = build_source_resolver_report_summary(
            build_source_peeks(
                configured_source_root,
                configured_profile,
                [
                    {
                        "method": "GET",
                        "path": "/console/fr/api/widgets/",
                        "request_context": build_request_context(
                            "GET",
                            "/console/fr/api/widgets/",
                            {"host": "127.0.0.1:9996"},
                            "127.0.0.1:9996",
                        ),
                    },
                    {
                        "method": "GET",
                        "path": "/console/fr/api/proxy/users/42",
                        "request_context": build_request_context(
                            "GET",
                            "/console/fr/api/proxy/users/42",
                            {"host": "127.0.0.1:9996", "x-approved-proxy": "yes"},
                            "127.0.0.1:9996",
                        ),
                    },
                ],
            )
        )
        configured_observation_paths = {
            str(item.get("path"))
            for item in configured_profile.get("burp_observation_plan", [])
        }
        configured_report_lines = [
            *configured_source_resolver_report.get("summary_lines", []),
            *configured_source_resolver_report.get("entrypoint_lines", []),
            *configured_source_resolver_report.get("policy_lines", []),
            *configured_source_resolver_report.get("observed_lines", []),
        ]
        configured_nextjs_runtime_passed = (
            configured_inventory.get("summary", {}).get("next_config_runtime", {}).get("base_path") == "/console"
            and configured_inventory.get("summary", {}).get("next_config_runtime", {}).get("trailing_slash") is True
            and configured_inventory.get("summary", {}).get("next_config_runtime", {}).get("i18n_configured") is True
            and configured_widget_route is not None
            and configured_widget_route.get("path") == "/console/api/widgets/"
            and configured_widget_route.get("cluster_id") == "route-api-widgets"
            and "/console/fr/api/widgets/" in (configured_widget_route.get("match") or {}).get("paths", [])
            and "/console/fr/api/widgets" in (configured_widget_route.get("match") or {}).get("paths", [])
            and configured_legacy_route is not None
            and configured_legacy_route.get("path") == "/console/api/legacy/"
            and configured_rewrite is not None
            and configured_rewrite.get("path") == "/console/api/proxy/{path*}"
            and "/console/fr/api/proxy/{path*}" in (configured_rewrite.get("match") or {}).get("path_patterns", [])
            and configured_widget_match is not None
            and str(configured_widget_match.get("source_ref", "")).endswith("src/app/api/widgets/route.ts")
            and "basePath:/console" in configured_widget_match.get("match_reasons", [])
            and "locale-prefix:fr" in configured_widget_match.get("match_reasons", [])
            and "trailingSlash:canonical" in configured_widget_match.get("match_reasons", [])
            and configured_rewrite_match is not None
            and configured_rewrite_match.get("condition_status") == "condition-satisfied"
            and "locale-prefix:fr" in configured_rewrite_match.get("match_reasons", [])
            and "condition-satisfied" in configured_rewrite_match.get("match_reasons", [])
            and any("basePath `/console`" in line for line in configured_report_lines)
            and any("/console/api/proxy/{path*}" in line for line in configured_report_lines)
            and any("condition `condition-satisfied`" in line for line in configured_report_lines)
            and any("basePath:/console" in line and "locale-prefix:fr" in line for line in configured_report_lines)
            and "route-api-widgets" in {cluster.get("id") for cluster in configured_clusters.get("clusters", [])}
            and "/console/api/widgets/" in configured_observation_paths
        )
    generic_unexpected_row = {
        "ts": utc_now(),
        "phase": "self-test",
        "probe_id": "nextjs_route_custom_api_widgets_get_method_confusion",
        "label": "Next.js route GET method confusion route-custom-api-widgets",
        "target": target,
        "method": "GET",
        "path": "/custom/api/widgets",
        "origin": None,
        "referer": None,
        "category": "route-custom-api-widgets",
        "external": False,
        "policy_field": "method",
        "risk": "safe-generic-route-method-probe",
        "expectation": "status",
        "expectation_result": "unexpected-status",
        "expected_statuses": [400, 403, 404, 405],
        "status": 200,
        "expected": False,
        "duration_ms": 1,
        "error": None,
        "body_sample": '{"ok":true}',
        "body_text": '{"ok":true}',
        "body_sha256": hashlib.sha256(b'{"ok":true}').hexdigest(),
        "body_truncated": False,
        "body_length": len('{"ok":true}'),
        "interesting": True,
        "attempt_count": 1,
    }
    generic_suspicions = build_suspicions([generic_unexpected_row], clusters)
    generic_gate = build_finding_gate(generic_suspicions, [])
    generic_hardening_notes = build_hardening_notes(generic_suspicions, generic_gate)
    generic_suspicion = next(
        (
            item
            for item in generic_suspicions
            if item.get("id") == "SUSP-nextjs-route-policy-route_custom_api_widgets"
        ),
        None,
    )
    generic_gate_item = next(
        (
            item
            for item in generic_gate.get("gates", [])
            if item.get("suspicion_id") == "SUSP-nextjs-route-policy-route_custom_api_widgets"
        ),
        None,
    )
    generic_attribution_passed = (
        generic_suspicion is not None
        and generic_gate_item is not None
        and generic_gate_item.get("gate_status") == "accepted-hardening-note"
        and "scripts/inferforge.py" in generic_suspicion.get("source_refs", [])
        and any(
            item.get("id") == "SUSP-nextjs-route-policy-route_custom_api_widgets"
            for item in generic_hardening_notes
        )
    )
    generic_expected_row = json_clone(generic_unexpected_row)
    generic_expected_row.update(
        {
            "probe_id": "nextjs_route_custom_api_widgets_head_expected",
            "label": "Next.js route HEAD expected route-custom-api-widgets",
            "method": "HEAD",
            "status": 405,
            "expected": True,
            "expected_statuses": [400, 403, 404, 405],
            "expectation_result": "status",
            "body_sample": '{"error":"method not allowed"}',
            "body_text": '{"error":"method not allowed"}',
            "body_sha256": hashlib.sha256(b'{"error":"method not allowed"}').hexdigest(),
            "body_length": len('{"error":"method not allowed"}'),
            "interesting": False,
        }
    )
    response_delta_selftest = build_response_delta_analysis(
        clusters,
        [generic_expected_row, generic_unexpected_row],
    )
    response_delta_cluster = next(
        (
            item
            for item in response_delta_selftest.get("clusters", [])
            if item.get("cluster_id") == "route-custom-api-widgets"
        ),
        None,
    )
    response_delta_endpoint = None
    if response_delta_cluster:
        response_delta_endpoint = next(
            (
                item
                for item in response_delta_cluster.get("endpoints", [])
                if item.get("endpoint") == "GET /custom/api/widgets"
            ),
            None,
        )
    response_delta_selftest_passed = (
        response_delta_selftest.get("status") == "review-needed"
        and response_delta_cluster is not None
        and response_delta_cluster.get("status") == "review-needed"
        and "status-variant" in response_delta_cluster.get("delta_flags", [])
        and "body-hash-variant" in response_delta_cluster.get("delta_flags", [])
        and "unexpected-response" in response_delta_cluster.get("delta_flags", [])
        and response_delta_endpoint is not None
        and response_delta_endpoint.get("status") == "review-needed"
        and response_delta_endpoint.get("unexpected_count") == 1
    )
    rewrite_attack_strategy = build_attack_strategy(
        rewrite_clusters,
        [],
        [
            {
                "method": "GET",
                "path": "/api/proxy/users/42",
                "status": 200,
                "source": "self-test",
            }
        ],
    )
    rewrite_strategy_route_coverage = next(
        (
            item
            for item in rewrite_attack_strategy.get("strategy_coverage", [])
            if item.get("cluster_id") == "route-api-proxy-path"
        ),
        {},
    )
    unknown_attack_strategy = build_attack_strategy(
        {
            "clusters": [
                {
                    "id": "opaque-service",
                    "kind": "opaque-proxy",
                    "strategy_set": "custom",
                }
            ]
        },
        [],
        [{"method": "GET", "path": "/opaque", "status": 200, "source": "self-test"}],
    )
    external_attack_strategy = build_attack_strategy(
        {
            "clusters": [
                {
                    "id": "quote",
                    "kind": "quote",
                    "strategy_set": "quote-transaction-decoder",
                }
            ]
        },
        [],
        [{"method": "POST", "path": "/bridge/quote", "status": 400, "source": "self-test"}],
    )
    unknown_waiting_actions = waiting_attack_strategy_actions(unknown_attack_strategy)
    external_waiting_summaries = [
        format_attack_strategy_waiting_action(action)
        for action in waiting_attack_strategy_actions(external_attack_strategy)
    ]
    strategy_review_queue = build_verification_queue(
        "http://127.0.0.1:9998",
        {"clusters": unknown_attack_strategy.get("strategy_coverage", [])},
        {"clusters": []},
        {"gaps": []},
        {"status": "covered"},
        {"status": "no-reportable-findings", "external_blockers": [], "decisions": []},
        {"status": "ready"},
        queue_artifact_dir,
        attack_strategy=unknown_attack_strategy,
    )
    strategy_review_item = next(
        (
            item
            for item in strategy_review_queue.get("items", [])
            if item.get("id") == "REVIEW-attack-strategy-coverage"
        ),
        None,
    )
    strategy_review_blockers = build_review_blockers(
        target="http://127.0.0.1:9998",
        profile=rewrite_profile,
        artifact_dir=queue_artifact_dir,
        verification_queue=strategy_review_queue,
    )
    strategy_external_queue = build_verification_queue(
        "http://127.0.0.1:9998",
        {"clusters": [{"id": "quote", "kind": "quote", "strategy_set": "quote-transaction-decoder"}]},
        {"clusters": []},
        {"gaps": []},
        {"status": "covered"},
        {"status": "no-reportable-findings", "external_blockers": [], "decisions": []},
        {"status": "ready"},
        queue_artifact_dir,
        attack_strategy=external_attack_strategy,
    )
    strategy_external_item = next(
        (
            item
            for item in strategy_external_queue.get("items", [])
            if item.get("id") == "RESOLVE-attack-strategy-external-evidence"
        ),
        None,
    )
    strategy_external_blockers = build_review_blockers(
        target="http://127.0.0.1:9998",
        profile=rewrite_profile,
        artifact_dir=queue_artifact_dir,
        verification_queue=strategy_external_queue,
    )
    attack_strategy_status_passed = (
        rewrite_attack_strategy.get("status") == "ready-for-regression"
        and "strategy-fixed-upstream-rewrite" in rewrite_strategy_route_coverage.get("strategy_ids", [])
        and unknown_attack_strategy.get("status") == "needs-strategy-review"
        and unknown_attack_strategy.get("summary", {}).get("strategy_uncovered_clusters") == ["opaque-service"]
        and unknown_waiting_actions == []
        and external_attack_strategy.get("status") == "needs-external-evidence"
        and any(
            action.get("id") == "NEXT-transaction-intent-corpus"
            for action in external_attack_strategy.get("relevant_next_development_actions", [])
        )
        and any(
            "NEXT-transaction-intent-corpus: waiting-for-real-quote-response - Feed real quote transaction payloads"
            in line
            for line in external_waiting_summaries
        )
        and strategy_review_item is not None
        and strategy_review_item.get("status") == "manual-review"
        and strategy_review_item.get("strategy_uncovered_clusters") == ["opaque-service"]
        and strategy_review_queue.get("status") == "needs-human-review"
        and strategy_review_queue.get("summary", {}).get("attack_strategy") == "needs-strategy-review"
        and strategy_review_blockers.get("status") == "needs-human-review"
        and any(
            blocker.get("id") == "QUEUE-REVIEW-attack-strategy-coverage"
            for blocker in strategy_review_blockers.get("blockers", [])
        )
        and strategy_external_item is not None
        and strategy_external_item.get("status") == "blocked-external"
        and "NEXT-transaction-intent-corpus" in strategy_external_item.get("waiting_action_ids", [])
        and any("collect-quote" in command for command in strategy_external_item.get("commands", []))
        and strategy_external_queue.get("status") == "ready-with-external-blockers"
        and strategy_external_queue.get("summary", {}).get("attack_strategy") == "needs-external-evidence"
        and strategy_external_blockers.get("status") == "ready-with-external-blockers"
        and any(
            blocker.get("id") == "QUEUE-RESOLVE-attack-strategy-external-evidence"
            for blocker in strategy_external_blockers.get("blockers", [])
        )
    )

    probe_paths = {probe.path for probe in probes}
    warmup_paths = {probe.path for probe in warmups}
    observation_paths = {str(item["path"]) for item in observation_plan}
    ws_config = websocket_observation_config(test_profile)
    ws_path = None if ws_config is None else str(ws_config.get("path"))
    all_paths = sorted(probe_paths | warmup_paths | observation_paths | ({ws_path} if ws_path else set()))
    forbidden_paths = {
        "/health",
        "/api/quote",
        "/api/rpc",
        "/api/rpc/solana/devnet",
        "/api/rpc/solana/localnet",
        "/api/orca/pools/not-an-address",
        "/api/orca/pools/0OIlnotbase58",
        "/api/orca/pools/1111111111111111111111111111111",
        "/api/orca/pools/111111111111111111111111111111111111111111111",
        "/api/orca/pools/%2e%2e%2fhealth",
        "/api/orca/pools/not-an-address/extra",
        "/api/orca/pools/not-an-address?url=https://evil.example",
    }
    required_paths = {
        "/statusz",
        "/bridge/quote",
        "/custom/api/widgets",
        "/chain/solana/devnet",
        "/chain/rpc",
        "/chain/solana/localnet",
        "/poolz/not-an-address",
        "/poolz/0OIlnotbase58",
        "/poolz/1111111111111111111111111111111",
        "/poolz/111111111111111111111111111111111111111111111",
        "/poolz/%2e%2e%2fstatusz",
        "/poolz/not-an-address/extra",
        "/poolz/not-an-address?url=https://evil.example",
        "/ws/solana/devnet",
    }
    leaked_paths = sorted(path for path in all_paths if path in forbidden_paths)
    missing_paths = sorted(path for path in required_paths if path not in all_paths)
    passed = (
        validation["status"] != "failed"
        and not leaked_paths
        and not missing_paths
        and generic_attribution_passed
        and response_delta_selftest_passed
        and unsafe_observation_validation_passed
        and rewrite_discovery_passed
        and configured_nextjs_runtime_passed
        and initial_artifacts_passed
        and target_lock_passed
        and attack_strategy_status_passed
    )

    artifact = {
        "generated_at": utc_now(),
        "status": "passed" if passed else "failed",
        "profile_under_test": profile_summary(test_profile),
        "current_profile_context": profile_summary(profile),
        "validation_status": validation["status"],
        "probe_count": len(probes),
        "warmup_count": len(warmups),
        "observation_count": len(observation_plan),
        "websocket_path": ws_path,
        "forbidden_default_paths": sorted(forbidden_paths),
        "leaked_default_paths": leaked_paths,
        "required_custom_paths": sorted(required_paths),
        "missing_custom_paths": missing_paths,
        "observed_paths": all_paths,
        "generic_route_attribution": {
            "status": "passed" if generic_attribution_passed else "failed",
            "suspicion_ids": [item.get("id") for item in generic_suspicions],
            "gate_status": None if generic_gate_item is None else generic_gate_item.get("gate_status"),
            "source_refs": [] if generic_suspicion is None else generic_suspicion.get("source_refs", []),
            "hardening_note_ids": [item.get("id") for item in generic_hardening_notes],
        },
        "response_delta_analysis": {
            "status": "passed" if response_delta_selftest_passed else "failed",
            "artifact_status": response_delta_selftest.get("status"),
            "summary": response_delta_selftest.get("summary", {}),
            "cluster": response_delta_cluster,
            "endpoint": response_delta_endpoint,
        },
        "attack_strategy_status": {
            "status": "passed" if attack_strategy_status_passed else "failed",
            "rewrite_status": rewrite_attack_strategy.get("status"),
            "rewrite_summary": rewrite_attack_strategy.get("summary", {}),
            "rewrite_route_coverage": rewrite_strategy_route_coverage,
            "unknown_status": unknown_attack_strategy.get("status"),
            "unknown_summary": unknown_attack_strategy.get("summary", {}),
            "external_status": external_attack_strategy.get("status"),
            "external_summary": external_attack_strategy.get("summary", {}),
            "external_waiting_summaries": external_waiting_summaries,
            "strategy_review_queue": {
                "status": strategy_review_queue.get("status"),
                "summary": strategy_review_queue.get("summary", {}),
                "item": strategy_review_item,
                "blockers_status": strategy_review_blockers.get("status"),
                "blocker_ids": [item.get("id") for item in strategy_review_blockers.get("blockers", [])],
            },
            "strategy_external_queue": {
                "status": strategy_external_queue.get("status"),
                "summary": strategy_external_queue.get("summary", {}),
                "item": strategy_external_item,
                "blockers_status": strategy_external_blockers.get("status"),
                "blocker_ids": [item.get("id") for item in strategy_external_blockers.get("blockers", [])],
            },
        },
        "active_observation_validation": {
            "status": "passed" if unsafe_observation_validation_passed else "failed",
            "validation_status": unsafe_observation_validation.get("status"),
            "issue_ids": [item.get("id") for item in unsafe_observation_validation.get("issues", [])],
            "build_blocked": unsafe_observation_build_blocked,
            "build_error": unsafe_observation_build_error,
        },
        "rewrite_discovery": {
            "status": "passed" if rewrite_discovery_passed else "failed",
            "inventory_summary": rewrite_inventory.get("summary", {}),
            "cluster_id": None if rewrite_cluster is None else rewrite_cluster.get("id"),
            "cluster_kind": None if rewrite_cluster is None else rewrite_cluster.get("kind"),
            "strategy_set": None if rewrite_cluster is None else rewrite_cluster.get("strategy_set"),
            "source_refs": [] if rewrite_cluster is None else rewrite_cluster.get("source_refs", []),
            "match": {} if rewrite_cluster is None else rewrite_cluster.get("match", {}),
            "fixed_upstreams": []
            if rewrite_cluster is None
            else rewrite_cluster.get("discovery", {}).get("fixed_upstreams", []),
            "classification_check_path": "/api/proxy/users/42",
            "endpoint_resolution": rewrite_resolution,
            "websocket_endpoint_resolution": ws_resolution,
            "pages_api_endpoint_resolution": pages_api_resolution,
            "middleware_context": {
                "rewrite": rewrite_middleware_context,
                "pages_api": pages_api_middleware_context,
            },
            "route_policy_context": {
                "rewrite": rewrite_route_policy_context,
                "pages_api": pages_api_route_policy_context,
                "pages_api_no_debug": pages_api_no_debug_route_policy_context,
                "redirect": redirect_route_policy_context,
                "redirect_cookie_present": redirect_cookie_present_route_policy_context,
            },
            "conditional_rewrite_without_required_header": rewrite_condition_missing_resolution,
            "pages_api_cluster": pages_api_cluster,
            "root_app_cluster": root_app_cluster,
            "root_app_endpoint_resolution": root_app_resolution,
            "server_actions": server_action_entries,
            "server_action_evidence_gap": {
                "status": "passed" if rewrite_server_action_gap_passed else "failed",
                "gap": rewrite_server_action_gap,
                "queue_item": rewrite_server_action_queue_item,
                "queue_status": rewrite_server_action_queue.get("status"),
                "queue_command_safety": rewrite_server_action_queue.get("summary", {}).get("command_safety", {}),
            },
            "source_peek_requests": {
                "status": "passed" if rewrite_source_peek_requests_passed else "failed",
                "artifact_status": rewrite_source_peek_requests.get("status"),
                "summary": rewrite_source_peek_requests.get("summary", {}),
                "request_ids": sorted(rewrite_source_peek_request_ids),
            },
            "burp_observation_coverage": {
                "status": "passed" if rewrite_burp_observation_coverage_passed else "failed",
                "artifact_status": rewrite_burp_observation_coverage.get("status"),
                "summary": rewrite_burp_observation_coverage.get("summary", {}),
                "clusters": rewrite_burp_observation_coverage.get("clusters", []),
            },
            "source_resolver_report_summary": rewrite_source_resolver_report,
            "observation_clusters": sorted(rewrite_observation_clusters),
            "review_observation_candidates": rewrite_profile_candidates,
            "promotion_selftest": {
                "status": "passed" if promotion_selftest_passed else "failed",
                "promoted_observation": promoted_rewrite_observation,
                "promoted_paths": sorted(promoted_rewrite_paths),
                "rejected_paths": rejected_promotion_paths,
                "queue_commands": rewrite_queue_commands,
                "queue_status": "passed" if queue_promotion_selftest_passed else "failed",
                "queue_command_safety": rewrite_queue_command_safety,
                "queue_global_command_safety": rewrite_queue_global_command_safety,
                "unsafe_command_classification": unsafe_command_classification,
                "error": promotion_error,
            },
        },
        "configured_nextjs_runtime": {
            "status": "passed" if configured_nextjs_runtime_passed else "failed",
            "inventory_summary": configured_inventory.get("summary", {}),
            "widget_route": configured_widget_route,
            "legacy_route": configured_legacy_route,
            "rewrite": configured_rewrite,
            "widget_resolution": configured_widget_resolution,
            "rewrite_resolution": configured_rewrite_resolution,
            "source_resolver_report_summary": configured_source_resolver_report,
            "observation_paths": sorted(configured_observation_paths),
        },
        "initial_audit_artifacts": {
            "status": "passed" if initial_artifacts_passed else "failed",
            "history_exists": (initial_artifact_dir / "burp-history-observations.jsonl").exists(),
            "observation_status": initial_observation.get("status"),
            "quote_collection_status": initial_quote_collection.get("status"),
            "quote_collection_classification": initial_quote_collection.get("diagnosis", {}).get("classification"),
        },
        "target_probe_lock": {
            "status": "passed" if target_lock_passed else "failed",
            "nested_lock_blocked": nested_lock_blocked,
            "lock_path_removed": not target_lock.path.exists(),
        },
        "safety": "Static self-test only. No HTTP requests, Burp calls, signing, or transaction submission are performed.",
    }
    write_json(artifact_dir / "profile-routing-selftest.json", artifact)
    print(f"Profile routing self-test: {artifact['status']}")
    print(f"Probes: {len(probes)}, warmups: {len(warmups)}, observations: {len(observation_plan)}")
    print(f"Wrote {artifact_dir / 'profile-routing-selftest.json'}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=current_target,
            command="self-test-profile-routing",
            output_paths=[artifact_dir / "profile-routing-selftest.json"],
        )
    )
    return 0 if passed else 1


def run_burp_sync(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)

    observe_result = None
    if args.observe:
        observe_result = run_burp_observe(args)
        if observe_result != 0:
            return observe_result

    try:
        observation_plan = build_burp_observation_plan(target, profile)
    except ValueError as error:
        sync_path = artifact_dir / "burp-mcp-sync.json"
        write_json(
            sync_path,
            {
                "generated_at": utc_now(),
                "status": "blocked-profile-validation",
                "profile": profile_summary(profile),
                "target": target,
                "mcp_url": args.mcp_url,
                "history_regex": None,
                "http_history": None,
                "websocket_history": None,
                "intercept": {
                    "requested_off": False,
                    "ok": None,
                    "error": None,
                },
                "observe_before_sync": bool(args.observe),
                "error": str(error),
                "safety": [
                    "No Burp MCP history was read because the active Burp observation plan is not a reviewed concrete local path set.",
                    "Does not run Burp Scanner, sign wallets, submit Solana transactions, or fuzz broadly.",
                ],
            },
        )
        print(f"Burp MCP sync blocked by profile validation: {error}")
        print(f"Wrote {sync_path}")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="burp-sync",
                output_paths=[
                    *target_profile_artifact_paths(artifact_dir),
                    sync_path,
                ],
            )
        )
        return 2
    observation_artifact_path = artifact_dir / "burp-observation-run.json"
    observed_ws_upgrade = False
    if observation_artifact_path.exists():
        observation_artifact = json.loads(read_text(observation_artifact_path))
        observed_ws_upgrade = bool(observation_artifact.get("websocket_upgrade"))

    history_regex = args.regex or build_burp_history_regex(
        target,
        observation_plan,
        include_ws_upgrade=args.ws_upgrade or observed_ws_upgrade,
    )
    raw_path = resolve_repo_path(args.raw_output) if args.raw_output else artifact_dir / "burp-mcp-history-latest.txt"
    ws_raw_path = (
        resolve_repo_path(args.websocket_raw_output)
        if args.websocket_raw_output
        else artifact_dir / "burp-mcp-websocket-history-latest.txt"
    )

    sync_artifact: dict[str, Any] = {
        "generated_at": utc_now(),
        "profile": profile_summary(profile),
        "target": target,
        "mcp_url": args.mcp_url,
        "history_regex": history_regex,
        "http_history": {
            "tool": "get_proxy_http_history_regex",
            "count": args.count,
            "offset": args.offset,
            "raw_output": str(raw_path),
        },
        "websocket_history": None,
        "intercept": {
            "requested_off": not args.keep_intercept_state,
            "ok": None,
            "error": None,
        },
        "observe_before_sync": bool(args.observe),
        "safety": [
            "Uses Burp MCP only for Proxy Intercept state and history retrieval.",
            "Does not run Burp Scanner, sign wallets, submit Solana transactions, or fuzz broadly.",
        ],
    }

    try:
        with McpSseClient(args.mcp_url, timeout=args.mcp_timeout) as client:
            if not args.keep_intercept_state:
                try:
                    client.call_tool("set_proxy_intercept_state", {"intercepting": False})
                    sync_artifact["intercept"]["ok"] = True
                except Exception as error:
                    sync_artifact["intercept"]["ok"] = False
                    sync_artifact["intercept"]["error"] = str(error)
                    raise

            http_result = client.call_tool(
                "get_proxy_http_history_regex",
                {"count": args.count, "offset": args.offset, "regex": history_regex},
            )
            if http_result.get("isError"):
                raise RuntimeError(mcp_tool_text(http_result))
            raw_text = mcp_tool_text(http_result)
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(raw_text, encoding="utf-8")

            if args.websocket_history:
                ws_result = client.call_tool(
                    "get_proxy_websocket_history_regex",
                    {"count": args.count, "offset": args.offset, "regex": history_regex},
                )
                if ws_result.get("isError"):
                    raise RuntimeError(mcp_tool_text(ws_result))
                ws_raw_text = mcp_tool_text(ws_result)
                ws_raw_path.parent.mkdir(parents=True, exist_ok=True)
                ws_raw_path.write_text(ws_raw_text, encoding="utf-8")
                sync_artifact["websocket_history"] = {
                    "tool": "get_proxy_websocket_history_regex",
                    "count": args.count,
                    "offset": args.offset,
                    "raw_output": str(ws_raw_path),
                    "bytes": len(ws_raw_text.encode("utf-8")),
                }

    except Exception as error:
        sync_artifact["status"] = "failed"
        sync_artifact["error"] = str(error)
        sync_path = artifact_dir / "burp-mcp-sync.json"
        write_json(sync_path, sync_artifact)
        print(f"Burp MCP sync failed: {error}")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="burp-sync",
                output_paths=[
                    *target_profile_artifact_paths(artifact_dir),
                    sync_path,
                ],
            )
        )
        return 1

    try:
        import_summary = import_burp_history_inputs(
            inputs=[(str(raw_path), raw_text)],
            profile=profile,
            artifact_dir=artifact_dir,
            target=target,
            source_root=source_root,
            node=args.node,
            replace=args.replace,
            all_hosts=args.all_hosts,
            source=args.source,
            observed_only=args.observed_only,
        )
    except Exception as error:
        sync_artifact["status"] = "failed-import"
        sync_artifact["error"] = str(error)
        sync_artifact["http_history"]["bytes"] = len(raw_text.encode("utf-8"))
        sync_path = artifact_dir / "burp-mcp-sync.json"
        write_json(sync_path, sync_artifact)
        print(f"Burp MCP history import failed: {error}")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="burp-sync",
                output_paths=[
                    *target_profile_artifact_paths(artifact_dir),
                    raw_path,
                    sync_path,
                ],
            )
        )
        return 1
    sync_artifact["status"] = "synced"
    sync_artifact["http_history"]["bytes"] = len(raw_text.encode("utf-8"))
    sync_artifact["import"] = import_summary
    sync_path = artifact_dir / "burp-mcp-sync.json"
    write_json(sync_path, sync_artifact)

    print(f"Burp MCP sync: synced via {args.mcp_url}")
    print(f"Raw HTTP history: {raw_path}")
    print(f"Imported {import_summary['imported_observations']} observations")
    print(f"Stored {import_summary['burp_history_items']} total observations in {import_summary['history_path']}")
    selection = import_summary["selection"]
    print(f"Observed clusters: {', '.join(selection['observed_cluster_ids']) or '(none)'}")
    print(f"Source-assisted selected clusters: {', '.join(selection['selected_cluster_ids']) or '(none)'}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="burp-sync",
            output_paths=[
                *target_profile_artifact_paths(artifact_dir),
                raw_path,
                ws_raw_path,
                artifact_dir / "burp-history-observations.jsonl",
                artifact_dir / "burp-transaction-candidates.json",
                artifact_dir / "endpoint-clusters.json",
                artifact_dir / "traffic-index.json",
                artifact_dir / "transaction-intent.json",
                artifact_dir / "collection-summary.json",
                sync_path,
            ],
        )
    )
    return 0


def run_plan(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    no_write = bool(args.no_write)
    if not no_write:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        write_target_profile_artifact(artifact_dir, profile, target, source_root)

    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")
    clusters = build_clusters(profile, source_root)
    traffic_path = artifact_dir / "traffic-index.json"
    traffic_index = json.loads(read_text(traffic_path)) if traffic_path.exists() else build_traffic_index([], burp_history)
    selection = select_cluster_ids(
        traffic_index,
        clusters,
        source_assisted=not args.observed_only,
    )
    selected_clusters = set(selection["selected_cluster_ids"])
    candidate_probes = build_probe_plan(
        target,
        include_external=args.include_external,
        selected_clusters=selected_clusters,
        profile=profile,
    )
    ranking = build_probe_ranking(candidate_probes, selection, clusters, max_probes=args.max_probes)
    probes = apply_probe_ranking(candidate_probes, ranking)
    ws_enabled = args.ws and "solana-rpc-ws" in selected_clusters

    if not no_write:
        write_json(artifact_dir / "endpoint-clusters.json", clusters)
        write_json(artifact_dir / "probe-ranking.json", ranking)
        write_plan(artifact_dir, probes, selection, ws_enabled=ws_enabled, ranking=ranking)
        write_json(artifact_dir / "attack-strategy.json", build_attack_strategy(clusters, [], burp_history))

    print(f"Planned {len(probes)} HTTP probes from {len(candidate_probes)} candidates")
    print(f"WebSocket probes: {'enabled' if ws_enabled else 'disabled'}")
    print(f"Selection mode: {selection['mode']}")
    print(f"Selected clusters: {', '.join(selection['selected_cluster_ids']) or '(none)'}")
    if no_write:
        probe_summaries = top_probe_plan_summaries(probes, ranking)
        if probe_summaries:
            print("Selected probes:")
            for probe_summary in probe_summaries:
                print(f"- {probe_summary}")
            if len(probes) > len(probe_summaries):
                print(f"- ... +{len(probes) - len(probe_summaries)} more selected probe(s)")
        print("No files written (--no-write).")
    else:
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="plan",
                output_paths=[
                    artifact_dir / TARGET_PROFILE_ARTIFACT,
                    artifact_dir / STRATEGY_REGISTRY_ARTIFACT,
                    artifact_dir / PROFILE_VALIDATION_ARTIFACT,
                    artifact_dir / "endpoint-clusters.json",
                    artifact_dir / "probe-ranking.json",
                    artifact_dir / "probe-plan.json",
                    artifact_dir / "attack-strategy.json",
                ],
            )
        )
    return 0


def run_attack_strategy(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    no_write = bool(args.no_write)
    if not no_write:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        write_target_profile_artifact(artifact_dir, profile, target, source_root)
    clusters_path = artifact_dir / "endpoint-clusters.json"
    clusters = json.loads(read_text(clusters_path)) if clusters_path.exists() else build_clusters(profile, source_root)
    suspicions_doc = load_optional_json(artifact_dir / "suspicions.json") or {}
    attack_strategy = build_attack_strategy(
        clusters,
        suspicions_doc.get("suspicions", []) or [],
        load_jsonl(artifact_dir / "burp-history-observations.jsonl"),
    )
    output_path = artifact_dir / "attack-strategy.json"
    if not no_write:
        write_json(output_path, attack_strategy)
    print(f"Attack strategy: {attack_strategy['status']}")
    print(
        "Coverage: "
        f"{attack_strategy['summary']['clusters_with_specific_strategy']} specific / "
        f"{attack_strategy['summary']['clusters']} clusters, "
        f"waiting_actions={attack_strategy['summary']['waiting_action_count']}"
    )
    uncovered = attack_strategy["summary"].get("strategy_uncovered_clusters", [])
    if uncovered:
        print(f"Uncovered clusters: {', '.join(str(item) for item in uncovered)}")
    waiting_actions = waiting_attack_strategy_actions(attack_strategy)
    waiting_action_preview_limit = 3
    for action in waiting_actions[:waiting_action_preview_limit]:
        print(f"Waiting action: {format_attack_strategy_waiting_action(action)}")
    overflow_line = format_attack_strategy_waiting_action_overflow(
        len(waiting_actions),
        waiting_action_preview_limit,
        no_write=no_write,
        output_path=output_path,
    )
    if overflow_line:
        print(overflow_line)
    if no_write:
        print("No files written (--no-write).")
    else:
        print(f"Wrote {output_path}")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="attack-strategy",
                output_paths=[
                    *target_profile_artifact_paths(artifact_dir),
                    output_path,
                ],
            )
        )
    if args.strict and attack_strategy["status"] != "ready-for-regression":
        return 1
    return 0


def run_gate(args: argparse.Namespace) -> int:
    artifact_dir = Path(args.artifact_dir).resolve()
    profile = load_target_profile(args.profile)
    target = resolve_target(args, profile)
    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")
    suspicions_path = artifact_dir / "suspicions.json"
    if not suspicions_path.exists():
        output_path = artifact_dir / "finding-gate.json"
        write_json(output_path, build_finding_gate([], burp_history))
        print("No suspicions.json found; wrote empty finding gate")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="gate",
                output_paths=[output_path],
            )
        )
        return 0

    suspicions_doc = json.loads(read_text(suspicions_path))
    suspicions = suspicions_doc.get("suspicions", [])
    gate = build_finding_gate(suspicions, burp_history)
    output_path = artifact_dir / "finding-gate.json"
    write_json(output_path, gate)
    print(f"Gated {len(gate['gates'])} suspicions")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="gate",
            output_paths=[output_path],
        )
    )
    return 0


def run_coverage(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    clusters_path = artifact_dir / "endpoint-clusters.json"
    clusters = json.loads(read_text(clusters_path)) if clusters_path.exists() else build_clusters(profile, source_root)
    results = load_jsonl(artifact_dir / "probe-results.jsonl")
    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")

    coverage = build_blackbox_coverage(
        clusters,
        results,
        burp_history,
        load_optional_json(artifact_dir / "source-peek-results.json"),
        load_optional_json(artifact_dir / "evidence-gaps.json"),
        load_optional_json(artifact_dir / "burp-observation-run.json"),
        load_optional_json(artifact_dir / "environment-readiness.json"),
        load_optional_json(artifact_dir / "transaction-decoder-selftest.json"),
    )
    output_path = artifact_dir / "blackbox-coverage.json"
    write_json(output_path, coverage)
    print(f"Coverage gate: {coverage['status']}")
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="coverage",
            output_paths=[output_path],
        )
    )
    return 0 if coverage["status"] in {"covered", "covered-with-external-blocker"} else 1


def run_burp_observation_coverage(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    clusters_path = artifact_dir / "endpoint-clusters.json"
    clusters = json.loads(read_text(clusters_path)) if clusters_path.exists() else build_clusters(profile, source_root)
    coverage = build_burp_observation_coverage(
        target,
        profile,
        clusters,
        load_jsonl(artifact_dir / "burp-history-observations.jsonl"),
        load_optional_json(artifact_dir / "burp-observation-run.json"),
        load_optional_json(artifact_dir / "evidence-gaps.json"),
    )
    output_path = artifact_dir / "burp-observation-coverage.json"
    write_json(output_path, coverage)
    print(f"Burp observation coverage: {coverage['status']}")
    print(
        "Clusters: "
        f"{coverage['summary']['clusters']} total, "
        f"status_counts={json.dumps(coverage['summary']['status_counts'], sort_keys=True)}"
    )
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="burp-observation-coverage",
            output_paths=[output_path],
        )
    )
    return 0 if coverage["status"] in {"covered", "needs-burp-sync"} else 1


def run_discovery_coverage(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)

    route_inventory_path = resolve_repo_path(args.route_inventory) if args.route_inventory else artifact_dir / ROUTE_INVENTORY_ARTIFACT
    if route_inventory_path.exists():
        route_inventory = json.loads(read_text(route_inventory_path))
    else:
        route_inventory = discover_nextjs_routes(source_root)
        route_inventory_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(route_inventory_path, route_inventory)

    clusters = build_clusters(profile, source_root)
    coverage = build_discovery_coverage(
        target,
        profile,
        source_root,
        route_inventory,
        clusters,
        route_inventory_path=route_inventory_path,
        burp_history=load_jsonl(artifact_dir / "burp-history-observations.jsonl"),
        probe_results=load_jsonl(artifact_dir / "probe-results.jsonl"),
    )
    output_path = resolve_repo_path(args.output) if args.output else artifact_dir / DISCOVERY_COVERAGE_ARTIFACT
    write_json(output_path, coverage)

    print(f"Discovery coverage: {coverage['status']}")
    print(
        "Surfaces: "
        f"{coverage['summary']['surfaces']} total, "
        f"status_counts={json.dumps(coverage['summary']['status_counts'], sort_keys=True)}"
    )
    print(f"Route inventory: {route_inventory_path}")
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="discovery-coverage",
            output_paths=[
                *target_profile_artifact_paths(artifact_dir),
                route_inventory_path,
                output_path,
            ],
        )
    )

    if coverage["status"] in {"uncovered", "profile-error", "missing-route-inventory", "failed", "no-surfaces"}:
        return 1
    if args.strict and coverage["status"] != "covered":
        return 1
    return 0


def run_discovery_coverage_selftest(args: argparse.Namespace) -> int:
    profile, artifact_dir, _target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result = build_discovery_coverage_selftest(source_root)
    result["current_profile_context"] = profile_summary(profile)
    output_path = artifact_dir / DISCOVERY_COVERAGE_SELFTEST_ARTIFACT
    write_json(output_path, result)
    failed = [item for item in result.get("assertions", []) if not item.get("passed")]
    print(f"Discovery coverage self-test: {result['status']}")
    print(
        "Cases: "
        f"full={result['cases']['full']['status']} "
        f"review_only={result['cases']['review_only']['status']} "
        f"covered={result['cases']['covered']['status']}"
    )
    if failed:
        print(f"Failed assertions: {', '.join(str(item.get('id')) for item in failed)}")
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=resolve_target(args, profile),
            command="self-test-discovery-coverage",
            output_paths=[output_path],
        )
    )
    return 0 if result["status"] == "passed" else 1


def run_response_deltas(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    clusters_path = artifact_dir / "endpoint-clusters.json"
    clusters = json.loads(read_text(clusters_path)) if clusters_path.exists() else build_clusters(profile, source_root)
    response_delta_analysis = build_response_delta_analysis(
        clusters,
        load_jsonl(artifact_dir / "probe-results.jsonl"),
    )
    output_path = artifact_dir / "response-delta-analysis.json"
    write_json(output_path, response_delta_analysis)
    print(f"Response delta analysis: {response_delta_analysis['status']}")
    print(
        "Deltas: "
        f"{response_delta_analysis['summary']['endpoint_groups']} endpoint groups, "
        f"review_needed={response_delta_analysis['summary']['review_needed_groups']}, "
        f"expected_deltas={response_delta_analysis['summary']['expected_delta_groups']}"
    )
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="response-deltas",
            output_paths=[output_path],
        )
    )
    return 0 if response_delta_analysis["status"] not in {"review-needed", "no-probe-results"} else 1


def run_evidence_chain(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    clusters_path = artifact_dir / "endpoint-clusters.json"
    clusters = json.loads(read_text(clusters_path)) if clusters_path.exists() else build_clusters(profile, source_root)
    results = load_jsonl(artifact_dir / "probe-results.jsonl")
    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")
    source_peeks = load_optional_json(artifact_dir / "source-peek-results.json")
    finding_gate = load_optional_json(artifact_dir / "finding-gate.json")
    evidence_gaps = load_optional_json(artifact_dir / "evidence-gaps.json")
    environment_readiness = load_optional_json(artifact_dir / "environment-readiness.json")
    transaction_intent = load_optional_json(artifact_dir / "transaction-intent.json")
    transaction_decoder_selftest = load_optional_json(artifact_dir / "transaction-decoder-selftest.json")
    blackbox_coverage = load_optional_json(artifact_dir / "blackbox-coverage.json")
    if blackbox_coverage is None:
        blackbox_coverage = build_blackbox_coverage(
            clusters,
            results,
            burp_history,
            source_peeks,
            evidence_gaps,
            load_optional_json(artifact_dir / "burp-observation-run.json"),
            environment_readiness,
            transaction_decoder_selftest,
        )

    evidence_chain = build_evidence_chain(
        clusters,
        results,
        burp_history,
        source_peeks,
        finding_gate,
        evidence_gaps,
        blackbox_coverage,
        environment_readiness,
        transaction_intent,
        transaction_decoder_selftest,
    )
    output_path = artifact_dir / "evidence-chain.json"
    write_json(output_path, evidence_chain)
    print(f"Evidence chain: {evidence_chain['status']}")
    print(
        "Indexed: "
        f"{evidence_chain['summary']['clusters']} clusters, "
        f"{evidence_chain['summary']['probes']} probes, "
        f"{evidence_chain['summary']['burp_observations']} Burp observations"
    )
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="evidence-chain",
            output_paths=[output_path],
        )
    )
    return 0 if evidence_chain["status"] in {"covered", "covered-with-external-blocker"} else 1


def run_source_peek_requests(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    clusters_path = artifact_dir / "endpoint-clusters.json"
    clusters = json.loads(read_text(clusters_path)) if clusters_path.exists() else build_clusters(profile, source_root)
    traffic_index = load_optional_json(artifact_dir / "traffic-index.json")
    output_paths = []
    if traffic_index is None:
        traffic_index = build_traffic_index(
            load_jsonl(artifact_dir / "probe-results.jsonl"),
            load_jsonl(artifact_dir / "burp-history-observations.jsonl"),
        )
        traffic_index_path = artifact_dir / "traffic-index.json"
        write_json(traffic_index_path, traffic_index)
        output_paths.append(traffic_index_path)
    source_peeks = load_optional_json(artifact_dir / "source-peek-results.json")
    suspicions_doc = load_optional_json(artifact_dir / "suspicions.json") or {}
    source_peek_requests = build_source_peek_requests(
        clusters,
        traffic_index,
        source_peeks,
        suspicions_doc.get("suspicions", []),
        load_optional_json(artifact_dir / "evidence-gaps.json"),
    )
    output_path = artifact_dir / "source-peek-requests.json"
    write_json(output_path, source_peek_requests)
    output_paths.append(output_path)
    print(f"Source-peek requests: {source_peek_requests['status']}")
    print(
        "Requests: "
        f"{source_peek_requests['summary']['requests']} total, "
        f"triggers={json.dumps(source_peek_requests['summary']['trigger_counts'], sort_keys=True)}"
    )
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="source-peek-requests",
            output_paths=output_paths,
        )
    )
    return 0


def run_evidence_appendix(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    clusters_path = artifact_dir / "endpoint-clusters.json"
    clusters = json.loads(read_text(clusters_path)) if clusters_path.exists() else build_clusters(profile, source_root)
    results = load_jsonl(artifact_dir / "probe-results.jsonl")
    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")
    evidence_appendix = build_evidence_appendix(
        clusters,
        results,
        burp_history,
        load_optional_json(artifact_dir / "burp-observation-run.json"),
        load_optional_json(artifact_dir / "blackbox-coverage.json"),
        load_optional_json(artifact_dir / "evidence-chain.json"),
        load_optional_json(artifact_dir / "adjudication.json"),
        load_optional_json(artifact_dir / "environment-readiness.json"),
    )
    output_path = artifact_dir / "evidence-appendix.json"
    write_json(output_path, evidence_appendix)
    print(f"Evidence appendix: {evidence_appendix['status']}")
    print(
        "Indexed: "
        f"{evidence_appendix['summary']['probe_rows']} probe rows, "
        f"{evidence_appendix['summary']['representative_probe_examples']} representative probe examples, "
        f"{evidence_appendix['summary']['burp_observations']} Burp observations"
    )
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="evidence-appendix",
            output_paths=[output_path],
        )
    )
    return 0 if evidence_appendix["status"] != "missing-evidence" else 1


def run_report(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    clusters_path = artifact_dir / "endpoint-clusters.json"
    clusters = json.loads(read_text(clusters_path)) if clusters_path.exists() else build_clusters(profile, source_root)
    results = load_jsonl(artifact_dir / "probe-results.jsonl")
    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")
    suspicions_doc = load_optional_json(artifact_dir / "suspicions.json") or {}
    suspicions = suspicions_doc.get("suspicions", []) or []
    attack_strategy = load_optional_json(artifact_dir / "attack-strategy.json") or build_attack_strategy(
        clusters,
        suspicions,
        burp_history,
    )
    finding_gate = load_optional_json(artifact_dir / "finding-gate.json") or build_finding_gate(
        suspicions,
        burp_history,
    )
    hardening_notes_doc = load_optional_json(artifact_dir / "hardening-notes.json") or {}
    hardening_notes = hardening_notes_doc.get("hardening_notes")
    if hardening_notes is None:
        hardening_notes = build_hardening_notes(suspicions, finding_gate)

    capabilities = load_optional_json(artifact_dir / "burp-capabilities.json") or build_report_capabilities_placeholder(
        target,
        artifact_dir,
    )
    transaction_intent = load_optional_json(artifact_dir / "transaction-intent.json") or build_report_transaction_intent_placeholder()
    report = generate_report(
        artifact_dir,
        target,
        results,
        suspicions,
        capabilities,
        attack_strategy,
        burp_history,
        finding_gate,
        transaction_intent,
        load_optional_json(artifact_dir / "warmup-results.json"),
        load_optional_json(artifact_dir / "evidence-gaps.json"),
        load_optional_json(artifact_dir / "rpc-method-policy.json"),
        load_optional_json(artifact_dir / "environment-readiness.json"),
        load_optional_json(artifact_dir / "transaction-decoder-selftest.json"),
        load_optional_json(artifact_dir / "blackbox-coverage.json"),
        load_optional_json(artifact_dir / "evidence-chain.json"),
        hardening_notes,
        load_optional_json(artifact_dir / "adjudication.json"),
        load_optional_json(artifact_dir / "evidence-appendix.json"),
        load_optional_json(artifact_dir / "verification-queue.json"),
        profile,
    )
    report_path = artifact_dir / "report.md"
    index_path = artifact_dir / "index.html"
    print("Report refresh: written")
    print(
        "Inputs: "
        f"{len(results)} probe rows, "
        f"{len(burp_history)} Burp observations, "
        f"{len(suspicions)} suspicions"
    )
    print(f"Report bytes: {len(report.encode('utf-8'))}")
    print(f"Wrote {report_path}")
    print(f"Wrote {index_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="report",
            output_paths=[
                *target_profile_artifact_paths(artifact_dir),
                report_path,
                index_path,
            ],
        )
    )
    return 0


def run_verification_queue(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    no_write = bool(args.no_write)
    if not no_write:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        write_target_profile_artifact(artifact_dir, profile, target, source_root)
    clusters_path = artifact_dir / "endpoint-clusters.json"
    clusters = json.loads(read_text(clusters_path)) if clusters_path.exists() else build_clusters(profile, source_root)
    verification_queue = build_verification_queue(
        target,
        clusters,
        load_optional_json(artifact_dir / "evidence-appendix.json"),
        load_optional_json(artifact_dir / "evidence-gaps.json"),
        load_optional_json(artifact_dir / "blackbox-coverage.json"),
        load_optional_json(artifact_dir / "adjudication.json"),
        load_optional_json(artifact_dir / "environment-readiness.json"),
        artifact_dir,
        attack_strategy=load_optional_json(artifact_dir / "attack-strategy.json"),
    )
    verification_queue_path = artifact_dir / "verification-queue.json"
    reproduction_steps_path = artifact_dir / "reproduction-steps.md"
    review_blockers_path = artifact_dir / REVIEW_BLOCKERS_ARTIFACT
    review_blockers_markdown_path = artifact_dir / REVIEW_BLOCKERS_MARKDOWN_ARTIFACT
    review_blockers = build_review_blockers(
        target=target,
        profile=profile,
        artifact_dir=artifact_dir,
        discovery_coverage=load_optional_json(artifact_dir / DISCOVERY_COVERAGE_ARTIFACT),
        burp_observation_coverage=load_optional_json(artifact_dir / "burp-observation-coverage.json"),
        verification_queue=verification_queue,
        source_peek_requests=load_optional_json(artifact_dir / "source-peek-requests.json"),
        environment_readiness=load_optional_json(artifact_dir / "environment-readiness.json"),
    )
    refreshed_manifests = []
    if not no_write:
        write_json(verification_queue_path, verification_queue)
        write_reproduction_steps(artifact_dir, verification_queue)
        write_json(review_blockers_path, review_blockers)
        write_review_blockers_markdown(review_blockers_markdown_path, review_blockers)
        refreshed_manifests = refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="verification-queue",
            output_paths=[
                verification_queue_path,
                reproduction_steps_path,
                review_blockers_path,
                review_blockers_markdown_path,
            ],
        )
    print(f"Verification queue: {verification_queue['status']}")
    print(
        "Items: "
        f"{verification_queue['summary']['items']} total, "
        f"status_counts={json.dumps(verification_queue['summary']['status_counts'], sort_keys=True)}"
    )
    print(
        "Command safety: "
        f"{format_command_safety_summary(verification_queue['summary'].get('command_safety', {}) or {})}"
    )
    item_summaries = top_verification_queue_item_summaries(verification_queue)
    if item_summaries:
        print("Queue items:")
        for item_summary in item_summaries:
            print(f"- {item_summary}")
        total_items = len(verification_queue.get("items", []) or [])
        if total_items > len(item_summaries):
            if no_write:
                print(f"- {total_items - len(item_summaries)} more item(s); rerun without --no-write to write reproduction steps")
            else:
                print(f"- {total_items - len(item_summaries)} more item(s) in {reproduction_steps_path}")
    if no_write:
        preview_items = [
            item
            for item in ranked_verification_queue_items(verification_queue)
            if verification_queue_command_preview_lines(item)
        ][:4]
        if preview_items:
            print("Command previews:")
            for item in preview_items:
                print(f"- {item.get('id') or 'ITEM-unknown'}:")
                for line in verification_queue_command_preview_lines(item):
                    print(line)
        followup_items = [
            item
            for item in ranked_verification_queue_items(verification_queue)
            if not verification_queue_command_preview_lines(item)
            and verification_queue_followup_preview_lines(item)
        ][:4]
        if followup_items:
            print("Manual/external previews:")
            for item in followup_items:
                print(f"- {item.get('id') or 'ITEM-unknown'}:")
                for line in verification_queue_followup_preview_lines(item):
                    print(line)
    if no_write:
        print("No files written (--no-write).")
    else:
        print(f"Wrote {verification_queue_path}")
        print(f"Wrote {reproduction_steps_path}")
        print(f"Wrote {review_blockers_path}")
        print(f"Wrote {review_blockers_markdown_path}")
        print_refreshed_manifests(refreshed_manifests)
    return verification_queue_exit_code(verification_queue)


def run_review_blockers(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    no_write = bool(args.no_write)
    if not no_write:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        write_target_profile_artifact(artifact_dir, profile, target, source_root)
    check_dirs: list[Path] = []
    for item in args.check_dir or []:
        check_dirs.append(resolve_repo_path(item))
    if args.discover_child_runs:
        check_dirs.extend(discover_review_blocker_dirs(artifact_dir))
    deduped_dirs = []
    seen_dirs: set[str] = set()
    for check_dir in check_dirs:
        resolved = check_dir.resolve()
        key = str(resolved)
        if key in seen_dirs:
            continue
        seen_dirs.add(key)
        deduped_dirs.append(resolved)

    if deduped_dirs:
        review_blockers = build_review_blockers_rollup(
            target=target,
            profile=profile,
            artifact_dir=artifact_dir,
            check_dirs=deduped_dirs,
            artifact_health=load_optional_json(artifact_dir / "artifact-health.json"),
        )
    else:
        review_blockers = build_review_blockers(
            target=target,
            profile=profile,
            artifact_dir=artifact_dir,
            discovery_coverage=load_optional_json(artifact_dir / DISCOVERY_COVERAGE_ARTIFACT),
            burp_observation_coverage=load_optional_json(artifact_dir / "burp-observation-coverage.json"),
            verification_queue=load_optional_json(artifact_dir / "verification-queue.json"),
            source_peek_requests=load_optional_json(artifact_dir / "source-peek-requests.json"),
            environment_readiness=load_optional_json(artifact_dir / "environment-readiness.json"),
            artifact_health=load_optional_json(artifact_dir / "artifact-health.json"),
        )
    output_path = resolve_repo_path(args.output) if args.output else artifact_dir / REVIEW_BLOCKERS_ARTIFACT
    markdown_path = (
        resolve_repo_path(args.markdown_output)
        if args.markdown_output
        else artifact_dir / REVIEW_BLOCKERS_MARKDOWN_ARTIFACT
    )
    refreshed_manifests = []
    if not no_write:
        write_json(output_path, review_blockers)
        write_review_blockers_markdown(markdown_path, review_blockers)
        refreshed_manifests = refresh_manifests_for_artifact_outputs(
            output_paths=[output_path, markdown_path],
            artifact_dir=artifact_dir,
            check_dirs=deduped_dirs,
            target=target,
            command="review-blockers",
        )
    print(f"Review blockers: {review_blockers['status']}")
    print(
        "Blockers: "
        f"{review_blockers['summary']['blockers']} total, "
        f"status_counts={json.dumps(review_blockers['summary']['status_counts'], sort_keys=True)}"
    )
    if review_blockers.get("mode") == "rollup":
        print(
            "Runs: "
            f"{review_blockers['summary']['runs']} checked, "
            f"run_status_counts={json.dumps(review_blockers['summary']['run_status_counts'], sort_keys=True)}"
        )
    groups = review_blockers.get("groups", []) or []
    if groups:
        print("Groups:")
        for group in groups[:8]:
            print(f"- {format_review_blocker_group_summary(group)}")
            if no_write:
                command_refs = review_blocker_group_command_refs(group)
                if command_refs:
                    command_safety = (group.get("command_safety", {}) or {}).get("summary", {}) or {}
                    if command_safety:
                        print(f"  command_safety={format_command_safety_summary(command_safety)}")
                    print("  command_templates:")
                    for ref in command_refs[:4]:
                        label = format_command_ref_label(ref)
                        command = inline_summary_text(ref.get("command"), max_chars=500)
                        print(f"    - {label} {command}")
                    if len(command_refs) > 4:
                        print(f"    - ... +{len(command_refs) - 4} more commands")
                else:
                    for line in review_blocker_group_followup_preview_lines(group):
                        print(line)
        if len(groups) > 8:
            if no_write:
                print(f"- {len(groups) - 8} more group(s); rerun without --no-write to write the full blocker artifact")
            else:
                print(f"- {len(groups) - 8} more group(s) in {output_path}")
    else:
        print("Blockers:")
        for blocker in review_blockers.get("blockers", [])[:8]:
            print(
                f"- {blocker.get('id')}: {blocker.get('status')} "
                f"source={blocker.get('source')} title={blocker.get('title')}"
            )
    if no_write:
        print("No files written (--no-write).")
    else:
        print(f"Wrote {output_path}")
        print(f"Wrote {markdown_path}")
        for item in refreshed_manifests:
            print(f"Refreshed {item['manifest']}: {item['status']}")
    if review_blockers["status"] == "failed":
        return 1
    if args.strict and review_blockers["status"] != "ready":
        return 1
    return 0


def run_review_blockers_selftest(args: argparse.Namespace) -> int:
    profile, artifact_dir, _target, _source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result = build_review_blockers_selftest()
    result["current_profile_context"] = profile_summary(profile)
    output_path = artifact_dir / REVIEW_BLOCKERS_SELFTEST_ARTIFACT
    write_json(output_path, result)
    print(f"Review blockers self-test: {result['status']}")
    print(
        "Cases: "
        f"default={result['cases']['default']['status']} "
        f"discovered={result['cases']['discovered']['status']} "
        f"rollup={result['cases']['rollup']['status']} "
        f"rollup_groups={result['summary']['rollup_groups']}"
    )
    failed = [item for item in result.get("assertions", []) if not item.get("passed")]
    if failed:
        print(f"Failed assertions: {', '.join(str(item.get('id')) for item in failed)}")
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=resolve_target(args, profile),
            command="self-test-review-blockers",
            output_paths=[output_path],
        )
    )
    return 0 if result["status"] == "passed" else 1


def run_command_safety_selftest(args: argparse.Namespace) -> int:
    profile, artifact_dir, _target, _source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result = build_command_safety_selftest()
    result["current_profile_context"] = profile_summary(profile)
    output_path = artifact_dir / COMMAND_SAFETY_SELFTEST_ARTIFACT
    write_json(output_path, result)
    print(f"Command safety self-test: {result['status']}")
    print(
        "Cases: "
        f"{result['summary']['cases']} cases, "
        f"assertions={result['summary']['assertions']}, "
        f"classifications={json.dumps(result['summary']['classification_counts'], sort_keys=True)}"
    )
    failed = [item for item in result.get("assertions", []) if not item.get("passed")]
    if failed:
        print(f"Failed assertions: {', '.join(str(item.get('id')) for item in failed)}")
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=resolve_target(args, profile),
            command="self-test-command-safety",
            output_paths=[output_path],
        )
    )
    return 0 if result["status"] == "passed" else 1


def run_artifact_health_selftest(args: argparse.Namespace) -> int:
    profile, artifact_dir, _target, _source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result = build_artifact_health_selftest()
    result["current_profile_context"] = profile_summary(profile)
    output_path = artifact_dir / ARTIFACT_HEALTH_SELFTEST_ARTIFACT
    write_json(output_path, result)
    print(f"Artifact health self-test: {result['status']}")
    print(
        "Cases: "
        f"assertions={result['summary']['assertions']}, "
        f"failed={result['summary']['failed']}, "
        f"stale_inputs={result['summary']['stale_input_count']}"
    )
    failed = [item for item in result.get("assertions", []) if not item.get("passed")]
    if failed:
        print(f"Failed assertions: {', '.join(str(item.get('id')) for item in failed)}")
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=resolve_target(args, profile),
            command="self-test-artifact-health",
            output_paths=[output_path],
        )
    )
    return 0 if result["status"] == "passed" else 1


def run_manifest_refresh_selftest(args: argparse.Namespace) -> int:
    profile, artifact_dir, _target, _source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result = build_manifest_refresh_selftest()
    result["current_profile_context"] = profile_summary(profile)
    output_path = artifact_dir / MANIFEST_REFRESH_SELFTEST_ARTIFACT
    write_json(output_path, result)
    print(f"Manifest refresh self-test: {result['status']}")
    print(
        "Cases: "
        f"commands={result['summary']['commands']}, "
        f"assertions={result['summary']['assertions']}, "
        f"failed={result['summary']['failed']}, "
        f"modes={json.dumps(result['summary']['mode_counts'], sort_keys=True)}"
    )
    failed = [item for item in result.get("assertions", []) if not item.get("passed")]
    if failed:
        print(f"Failed assertions: {', '.join(str(item.get('id')) for item in failed)}")
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=resolve_target(args, profile),
            command="self-test-manifest-refresh",
            output_paths=[output_path],
        )
    )
    return 0 if result["status"] == "passed" else 1


def run_no_write_selftest(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, _source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result = build_no_write_selftest()
    result["current_profile_context"] = profile_summary(profile)
    output_path = artifact_dir / NO_WRITE_SELFTEST_ARTIFACT
    write_json(output_path, result)
    print(f"No-write self-test: {result['status']}")
    print(
        "Cases: "
        f"assertions={result['summary']['assertions']}, "
        f"failed={result['summary']['failed']}"
    )
    failed = [item for item in result.get("assertions", []) if not item.get("passed")]
    if failed:
        print(f"Failed assertions: {', '.join(str(item.get('id')) for item in failed)}")
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="self-test-no-write",
            output_paths=[output_path],
        )
    )
    return 0 if result["status"] == "passed" else 1


def run_manifest(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    manifest = write_artifact_manifest(artifact_dir, target, command=args.command)
    print(f"Artifact manifest: {manifest['status']}")
    print(
        "Artifacts: "
        f"{manifest['summary']['artifact_count']} indexed, "
        f"missing_required={len(manifest['summary']['missing_required'])}"
    )
    print(f"Wrote {artifact_dir / MANIFEST_NAME}")
    return 0 if manifest["status"] != "incomplete" else 1


def run_artifact_health(args: argparse.Namespace) -> int:
    artifact_dir = Path(args.artifact_dir).resolve()
    profile = load_target_profile(args.profile)
    target = resolve_target(args, profile)
    check_dirs: list[Path] = []
    for item in args.check_dir or []:
        check_dirs.append(resolve_repo_path(item))
    if args.discover_child_runs:
        check_dirs.extend(discover_artifact_health_dirs(artifact_dir))
    if not check_dirs:
        check_dirs.append(artifact_dir)

    deduped_dirs = []
    seen = set()
    for path in check_dirs:
        resolved = path.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        deduped_dirs.append(resolved)

    health = build_artifact_health(deduped_dirs)
    output_path = resolve_repo_path(args.output) if args.output else artifact_dir / "artifact-health.json"
    refreshed_manifests = []
    if not args.no_write:
        health, refreshed_manifests = write_artifact_health_artifact(
            health=health,
            output_path=output_path,
            artifact_dir=artifact_dir,
            check_dirs=deduped_dirs,
            target=target,
        )

    print(f"Artifact health: {health['status']}")
    print(
        "Directories: "
        f"{health['summary']['artifact_dirs']} checked, "
        f"status_counts={json.dumps(health['summary']['status_counts'], sort_keys=True)}"
    )
    print(
        "Parse/required: "
        f"parse_errors={health['summary']['parse_error_count']}, "
        f"missing_required={health['summary']['missing_required_count']}, "
        f"stale_inputs={health['summary'].get('stale_input_count', 0)}"
    )
    for item in health["directories"]:
        statuses = item.get("statuses", {}) or {}
        print(
            f"- {item['artifact_dir']}: {item['status']} "
            f"manifest={statuses.get('manifest')} "
            f"coverage={statuses.get('coverage')} "
            f"discovery={statuses.get('discovery_coverage')} "
            f"review_blockers={statuses.get('review_blockers')} "
            f"verification={statuses.get('verification_queue')} "
            f"attack_strategy={statuses.get('attack_strategy')} "
            f"response_deltas={statuses.get('response_delta_analysis')} "
            f"source_peek_requests={statuses.get('source_peek_requests')} "
            f"burp_observation={statuses.get('burp_observation_coverage')}"
        )
        stale_inputs = item.get("stale_inputs", []) or []
        for stale_issue in stale_inputs[:3]:
            print(f"  stale: {format_artifact_health_stale_issue(stale_issue)}")
        if len(stale_inputs) > 3:
            print(f"  stale: {len(stale_inputs) - 3} more issue(s); inspect artifact-health.json")
    if not args.no_write:
        print(f"Wrote {output_path}")
        for item in refreshed_manifests:
            print(f"Refreshed {item['manifest']}: {item['status']}")

    if health["status"] in {"failed", "no-artifact-dirs"}:
        return 1
    if args.strict and health["status"] != "healthy":
        return 1
    return 0


def run_regression_suite(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    default_profile_path = resolve_repo_path(args.profile)
    default_artifact_dir = resolve_repo_path(args.default_artifact_dir)
    discovered_artifact_dir = resolve_repo_path(args.discovered_artifact_dir)
    discovered_profile_path = artifact_dir / DISCOVERED_PROFILE_ARTIFACT
    steps: list[dict[str, Any]] = []
    preparation: list[dict[str, Any]] = []
    suite_stopped = False

    def run_step(label: str, command: list[str]) -> bool:
        nonlocal suite_stopped
        print(f"[suite] {label}: {shlex.join(command)}")
        step = run_regression_step(label, command, timeout=args.step_timeout)
        steps.append(step)
        print(
            f"[suite] {label}: {step['status']} "
            f"returncode={step.get('returncode')} duration_ms={step.get('duration_ms')}"
        )
        if regression_step_failed(step) and args.stop_on_failure:
            suite_stopped = True
            return False
        return True

    if not args.keep_probe_results and not args.skip_audit:
        preparation.append(remove_stale_probe_results(default_artifact_dir))
        if not args.skip_discovered:
            preparation.append(remove_stale_probe_results(discovered_artifact_dir))

    if not args.skip_self_tests:
        for label, subcommand in [
            ("self-test-profile-routing", "self-test-profile-routing"),
            ("self-test-discovery-coverage", "self-test-discovery-coverage"),
            ("self-test-command-safety", "self-test-command-safety"),
            ("self-test-review-blockers", "self-test-review-blockers"),
            ("self-test-artifact-health", "self-test-artifact-health"),
            ("self-test-manifest-refresh", "self-test-manifest-refresh"),
            ("self-test-no-write", "self-test-no-write"),
            ("self-test-transactions", "self-test-transactions"),
        ]:
            command = inferforge_cli_command(
                args,
                profile_path=default_profile_path,
                artifact_dir=artifact_dir,
                subcommand=subcommand,
            )
            if not run_step(label, command):
                return_code_health = None
                suite = {
                    "generated_at": utc_now(),
                    "status": "failed",
                    "target": target,
                    "source_root": repo_relative_or_absolute(source_root),
                    "profile": profile_summary(profile),
                    "preparation": preparation,
                    "steps": steps,
                    "artifact_health": return_code_health,
                    "safety": "Regression suite stopped on failure. No wallet signing, transaction submission, Burp Scanner, or broad fuzzing is performed.",
                }
                write_json(artifact_dir / "regression-suite.json", suite)
                artifact_manifest = write_artifact_manifest(artifact_dir, target, command="regression-suite")
                print(f"Regression suite: {suite['status']}")
                print(f"Wrote {artifact_dir / 'regression-suite.json'}")
                print(f"Artifact manifest: {artifact_manifest['status']}")
                print(f"Wrote {artifact_dir / MANIFEST_NAME}")
                return 1

    if not args.skip_discover_profile and not args.skip_discovered:
        command = inferforge_cli_command(
            args,
            profile_path=default_profile_path,
            artifact_dir=artifact_dir,
            subcommand="discover-profile",
        )
        if not run_step("discover-profile", command):
            return_code_health = None
            suite = {
                "generated_at": utc_now(),
                "status": "failed",
                "target": target,
                "source_root": repo_relative_or_absolute(source_root),
                "profile": profile_summary(profile),
                "preparation": preparation,
                "steps": steps,
                "artifact_health": return_code_health,
                "safety": "Regression suite stopped on failure. No wallet signing, transaction submission, Burp Scanner, or broad fuzzing is performed.",
            }
            write_json(artifact_dir / "regression-suite.json", suite)
            artifact_manifest = write_artifact_manifest(artifact_dir, target, command="regression-suite")
            print(f"Regression suite: {suite['status']}")
            print(f"Wrote {artifact_dir / 'regression-suite.json'}")
            print(f"Artifact manifest: {artifact_manifest['status']}")
            print(f"Wrote {artifact_dir / MANIFEST_NAME}")
            return 1

    if not args.skip_burp_sync and not suite_stopped:
        burp_args = [
            "--mcp-url",
            args.mcp_url,
            "--proxy",
            args.proxy,
            "--observe",
            "--ws-upgrade",
            "--replace",
            "--count",
            str(args.burp_count),
        ]
        if args.allow_nonlocal_target:
            burp_args.append("--allow-nonlocal-target")
        command = inferforge_cli_command(
            args,
            profile_path=default_profile_path,
            artifact_dir=default_artifact_dir,
            subcommand="burp-sync",
            extra=burp_args,
        )
        run_step("default-burp-sync", command)

        if not args.skip_discovered and not suite_stopped:
            command = inferforge_cli_command(
                args,
                profile_path=discovered_profile_path,
                artifact_dir=discovered_artifact_dir,
                subcommand="burp-sync",
                extra=burp_args,
            )
            run_step("discovered-burp-sync", command)

    if not args.skip_discovery_coverage and not args.skip_discovered and not suite_stopped:
        coverage_args = [
            "--route-inventory",
            repo_relative_or_absolute(artifact_dir / ROUTE_INVENTORY_ARTIFACT),
        ]
        if args.strict:
            coverage_args.append("--strict")
        command = inferforge_cli_command(
            args,
            profile_path=discovered_profile_path,
            artifact_dir=discovered_artifact_dir,
            subcommand="discovery-coverage",
            extra=coverage_args,
        )
        run_step("discovered-discovery-coverage", command)

    if not args.skip_orca_baseline and not suite_stopped:
        command = inferforge_cli_command(
            args,
            profile_path=default_profile_path,
            artifact_dir=default_artifact_dir,
            subcommand="collect-orca-baseline",
        )
        run_step("default-orca-baseline", command)

        if not args.skip_discovered and not suite_stopped:
            command = inferforge_cli_command(
                args,
                profile_path=discovered_profile_path,
                artifact_dir=discovered_artifact_dir,
                subcommand="collect-orca-baseline",
            )
            run_step("discovered-orca-baseline", command)

    if not args.skip_audit and not suite_stopped:
        audit_args = []
        if args.include_external:
            audit_args.append("--include-external")
        if args.ws_resource_probes:
            audit_args.append("--ws-resource-probes")
        command = inferforge_cli_command(
            args,
            profile_path=default_profile_path,
            artifact_dir=default_artifact_dir,
            subcommand="audit",
            extra=audit_args,
        )
        run_step("default-audit", command)

        if not args.skip_discovered and not suite_stopped:
            command = inferforge_cli_command(
                args,
                profile_path=discovered_profile_path,
                artifact_dir=discovered_artifact_dir,
                subcommand="audit",
                extra=audit_args,
            )
            run_step("discovered-audit", command)

    if not args.skip_audit and not suite_stopped:
        command = inferforge_cli_command(
            args,
            profile_path=default_profile_path,
            artifact_dir=default_artifact_dir,
            subcommand="report",
        )
        run_step("default-report", command)

        if not args.skip_discovered and not suite_stopped:
            command = inferforge_cli_command(
                args,
                profile_path=discovered_profile_path,
                artifact_dir=discovered_artifact_dir,
                subcommand="report",
            )
            run_step("discovered-report", command)

    health_check_dirs = [default_artifact_dir]
    if not args.skip_discovered:
        health_check_dirs.append(discovered_artifact_dir)
    health_args = []
    for check_dir in health_check_dirs:
        health_args.extend(["--check-dir", repo_relative_or_absolute(check_dir)])
    if args.strict:
        health_args.append("--strict")
    command = inferforge_cli_command(
        args,
        profile_path=default_profile_path,
        artifact_dir=artifact_dir,
        subcommand="artifact-health",
        extra=health_args,
    )
    run_step("artifact-health", command)
    if not args.skip_review_blockers and not suite_stopped:
        review_blocker_args = []
        for check_dir in health_check_dirs:
            review_blocker_args.extend(["--check-dir", repo_relative_or_absolute(check_dir)])
        if args.strict:
            review_blocker_args.append("--strict")
        command = inferforge_cli_command(
            args,
            profile_path=default_profile_path,
            artifact_dir=artifact_dir,
            subcommand="review-blockers",
            extra=review_blocker_args,
        )
        run_step("review-blockers-rollup", command)
        if not suite_stopped:
            command = inferforge_cli_command(
                args,
                profile_path=default_profile_path,
                artifact_dir=artifact_dir,
                subcommand="report",
            )
            run_step("root-report", command)
    health = load_optional_json(artifact_dir / "artifact-health.json")
    review_blockers = None if args.skip_review_blockers else load_optional_json(artifact_dir / REVIEW_BLOCKERS_ARTIFACT)
    review_blocker_top_groups = top_review_blocker_group_summaries(review_blockers, limit=5)
    suite_status = regression_suite_status(steps, health, strict=args.strict)
    suite = {
        "generated_at": utc_now(),
        "status": suite_status,
        "target": target,
        "source_root": repo_relative_or_absolute(source_root),
        "profile": profile_summary(profile),
        "artifact_dirs": {
            "suite": repo_relative_or_absolute(artifact_dir),
            "default": repo_relative_or_absolute(default_artifact_dir),
            "discovered": None if args.skip_discovered else repo_relative_or_absolute(discovered_artifact_dir),
            "discovered_profile": None if args.skip_discovered else repo_relative_or_absolute(discovered_profile_path),
        },
        "options": {
            "include_external": bool(args.include_external),
            "ws_resource_probes": bool(args.ws_resource_probes),
            "burp_count": args.burp_count,
            "skip_discovered": bool(args.skip_discovered),
            "skip_burp_sync": bool(args.skip_burp_sync),
            "skip_orca_baseline": bool(args.skip_orca_baseline),
            "skip_audit": bool(args.skip_audit),
            "skip_discover_profile": bool(args.skip_discover_profile),
            "skip_discovery_coverage": bool(args.skip_discovery_coverage),
            "skip_self_tests": bool(args.skip_self_tests),
            "skip_review_blockers": bool(args.skip_review_blockers),
            "keep_probe_results": bool(args.keep_probe_results),
            "strict": bool(args.strict),
        },
        "preparation": preparation,
        "steps": steps,
        "artifact_health": {
            "status": None if not health else health.get("status"),
            "summary": None if not health else health.get("summary"),
            "artifact": "artifact-health.json",
        },
        "review_blockers": {
            "status": None if not review_blockers else review_blockers.get("status"),
            "summary": None if not review_blockers else review_blockers.get("summary"),
            "top_groups": review_blocker_top_groups,
            "artifact": REVIEW_BLOCKERS_ARTIFACT,
            "markdown": REVIEW_BLOCKERS_MARKDOWN_ARTIFACT,
        },
        "safety": [
            "Runs the existing deterministic low-volume InferForge regression commands.",
            "Does not run Burp Scanner, sign wallets, submit Solana transactions, invoke Server Actions, or fuzz broadly.",
            "Clears only generated probe-results.jsonl in the selected regression artifact directories unless --keep-probe-results is set.",
        ],
    }
    write_json(artifact_dir / "regression-suite.json", suite)
    artifact_manifest = write_artifact_manifest(artifact_dir, target, command="regression-suite")
    print(f"Regression suite: {suite_status}")
    if review_blocker_top_groups:
        print("Next blocker groups:")
        for group_summary in review_blocker_top_groups:
            print(f"- {group_summary}")
    print(f"Wrote {artifact_dir / 'regression-suite.json'}")
    print(f"Artifact manifest: {artifact_manifest['status']}")
    print(f"Wrote {artifact_dir / MANIFEST_NAME}")
    if suite_status == "failed":
        return 1
    if args.strict and suite_status != "healthy":
        return 1
    return 0


def run_profile(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    profile_doc = write_target_profile_artifact(artifact_dir, profile, target, source_root)
    clusters = build_clusters(profile, source_root)
    validation = load_optional_json(artifact_dir / PROFILE_VALIDATION_ARTIFACT) or {}
    write_json(artifact_dir / "endpoint-clusters.json", clusters)
    print(f"Target profile: {profile_doc.get('display_name') or profile_doc.get('name')}")
    print(f"Loaded from: {profile_doc.get('loaded_from')} ({profile_doc.get('profile_path')})")
    print(f"Effective target: {target}")
    print(f"Effective source root: {source_root}")
    print(f"Enabled strategy sets: {', '.join(sorted(enabled_strategy_set_ids(profile))) or '(none)'}")
    print(f"Clusters: {len(clusters['clusters'])}")
    print(f"Profile validation: {validation.get('status', 'unknown')}")
    print(f"Wrote {artifact_dir / TARGET_PROFILE_ARTIFACT}")
    print(f"Wrote {artifact_dir / STRATEGY_REGISTRY_ARTIFACT}")
    print(f"Wrote {artifact_dir / PROFILE_VALIDATION_ARTIFACT}")
    print(f"Wrote {artifact_dir / 'endpoint-clusters.json'}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="profile",
            output_paths=[
                artifact_dir / TARGET_PROFILE_ARTIFACT,
                artifact_dir / STRATEGY_REGISTRY_ARTIFACT,
                artifact_dir / PROFILE_VALIDATION_ARTIFACT,
                artifact_dir / "endpoint-clusters.json",
            ],
        )
    )
    return 0


def run_review_candidates(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    no_write = bool(args.no_write)
    if not no_write:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        write_target_profile_artifact(artifact_dir, profile, target, source_root)
    candidates = collect_review_observation_candidates(profile)
    artifact = {
        "generated_at": utc_now(),
        "status": "listed",
        "profile": profile_summary(profile),
        "target": target,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "safety": "Review candidates are inert templates. Listing them does not send HTTP traffic or modify the profile.",
    }
    output_path = artifact_dir / "review-observation-candidates.json"
    display_candidates = contextualize_review_candidates(candidates, build_clusters(profile, source_root), artifact_dir)
    print(f"Review observation candidates: {len(candidates)}")
    for candidate in display_candidates:
        for line in format_review_candidate_cli_lines(candidate):
            print(line)
    if no_write:
        print("No files written (--no-write).")
    else:
        write_json(output_path, artifact)
        print(f"Wrote {output_path}")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="review-candidates",
                output_paths=[
                    artifact_dir / TARGET_PROFILE_ARTIFACT,
                    artifact_dir / STRATEGY_REGISTRY_ARTIFACT,
                    artifact_dir / PROFILE_VALIDATION_ARTIFACT,
                    output_path,
                ],
            )
        )
    return 0


def run_promote_observation_candidate(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    no_write = bool(args.no_write)
    if not no_write:
        artifact_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(args.output).resolve() if args.output else artifact_dir / "reviewed-profile.json"
    if not no_write and output_path.exists() and not args.force:
        print(f"Refusing to overwrite existing profile without --force: {output_path}")
        return 2
    expected_statuses = [int(value) for value in args.expected_status] if args.expected_status else None
    try:
        promoted_profile, observation = promote_review_observation_candidate(
            profile,
            candidate_id=args.candidate_id,
            approved_path=args.path,
            observation_id=args.observation_id,
            method=args.method,
            expected_statuses=expected_statuses,
            note=args.note,
        )
    except ValueError as error:
        print(f"Could not promote candidate: {error}")
        return 2

    if not no_write:
        write_json(output_path, promoted_profile)
    normalized = normalize_target_profile(
        promoted_profile,
        profile_path=output_path if output_path.exists() else None,
    )
    clusters = build_clusters(normalized, source_root)
    validation = build_profile_validation_artifact(normalized, clusters, source_root)
    followup_commands = promoted_observation_followup_commands(output_path, artifact_dir)
    if no_write:
        print(f"Promotion preview: {args.candidate_id}")
        print(f"Observation: {observation['method']} {observation['path']} cluster={observation['cluster']}")
        print(f"Profile validation: {validation['status']}")
        validation_issues = validation.get("issues", []) or []
        if validation_issues:
            print("Validation issues:")
            for issue in validation_issues[:5]:
                issue_id = inline_summary_text(issue.get("id") or "unknown", max_chars=120)
                message = inline_summary_text(issue.get("message") or "", max_chars=240)
                print(f"- {issue_id}: {message}" if message else f"- {issue_id}")
            if len(validation_issues) > 5:
                print(f"- ... +{len(validation_issues) - 5} more issue(s)")
        print(f"Output profile: {output_path}")
        if output_path.exists() and not args.force:
            print("Output profile exists; rerun without --no-write requires --force to overwrite it.")
        if followup_commands:
            print("Next commands:")
            for command in followup_commands:
                print(f"- {command}")
        print("No files written (--no-write).")
        return 0 if validation["status"] != "failed" else 1

    write_json(artifact_dir / "reviewed-profile-validation.json", validation)
    write_json(
        artifact_dir / "reviewed-observation-promotion.json",
        {
            "generated_at": utc_now(),
            "status": "promoted",
            "profile": profile_summary(profile),
            "output_profile": repo_relative_or_absolute(output_path),
            "candidate_id": args.candidate_id,
            "observation": observation,
            "validation_status": validation["status"],
            "safety": "Profile edit only. No HTTP request was sent; use the output profile with burp-sync --observe after review.",
        },
    )
    print(f"Promoted candidate: {args.candidate_id}")
    print(f"Observation: {observation['method']} {observation['path']} cluster={observation['cluster']}")
    print(f"Profile validation: {validation['status']}")
    print(f"Wrote {output_path}")
    print(f"Wrote {artifact_dir / 'reviewed-profile-validation.json'}")
    print(f"Wrote {artifact_dir / 'reviewed-observation-promotion.json'}")
    if followup_commands:
        print("Next commands:")
        for command in followup_commands:
            print(f"- {command}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="promote-observation-candidate",
            output_paths=[
                output_path,
                artifact_dir / "reviewed-profile-validation.json",
                artifact_dir / "reviewed-observation-promotion.json",
            ],
        )
    )
    return 0 if validation["status"] != "failed" else 1


def run_discover_profile(args: argparse.Namespace) -> int:
    base_profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    route_inventory = discover_nextjs_routes(source_root)
    write_json(artifact_dir / ROUTE_INVENTORY_ARTIFACT, route_inventory)

    default_name = re.sub(r"[^A-Za-z0-9_-]+", "-", source_root.name.lower()).strip("-") or "discovered-target"
    name = args.name or default_name
    display_name = args.display_name or source_root.name
    discovered_profile = build_discovered_profile(
        route_inventory,
        name=name,
        display_name=display_name,
        target=target,
        source_root=source_root,
    )
    output_path = Path(args.output).resolve() if args.output else artifact_dir / DISCOVERED_PROFILE_ARTIFACT
    explicit_output = bool(args.output)
    if explicit_output and output_path.exists() and not args.force:
        print(f"Refusing to overwrite existing profile without --force: {output_path}")
        print(f"Wrote {artifact_dir / ROUTE_INVENTORY_ARTIFACT}")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="discover-profile",
                output_paths=[artifact_dir / ROUTE_INVENTORY_ARTIFACT],
            )
        )
        return 2

    write_json(output_path, discovered_profile)
    normalized = normalize_target_profile(discovered_profile, profile_path=output_path)
    clusters = build_clusters(normalized, source_root)
    validation = build_profile_validation_artifact(normalized, clusters, source_root)
    write_json(artifact_dir / "discovered-profile-validation.json", validation)

    print(f"Discovered routes: {route_inventory.get('summary', {}).get('route_count', 0)}")
    print(f"Discovered rewrites: {route_inventory.get('summary', {}).get('rewrite_count', 0)}")
    print(f"Discovered custom server entrypoints: {route_inventory.get('summary', {}).get('custom_server_entrypoint_count', 0)}")
    print(f"Discovered middleware: {route_inventory.get('summary', {}).get('middleware_count', 0)}")
    print(f"Discovered Server Action files: {route_inventory.get('summary', {}).get('server_action_file_count', 0)}")
    print(f"Discovered redirects: {route_inventory.get('summary', {}).get('redirect_count', 0)}")
    print(f"Discovered header routes: {route_inventory.get('summary', {}).get('header_route_count', 0)}")
    print(f"Suggested strategy sets: {', '.join(discovered_profile.get('strategy_sets', [])) or '(none)'}")
    print(f"Suggested clusters: {len(discovered_profile.get('clusters', []))}")
    print(f"Generated profile validation: {validation['status']}")
    print(f"Wrote {artifact_dir / ROUTE_INVENTORY_ARTIFACT}")
    print(f"Wrote {output_path}")
    print(f"Wrote {artifact_dir / 'discovered-profile-validation.json'}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="discover-profile",
            output_paths=[
                artifact_dir / ROUTE_INVENTORY_ARTIFACT,
                output_path,
                artifact_dir / "discovered-profile-validation.json",
            ],
        )
    )
    if route_inventory.get("status") != "discovered":
        return 1
    return 0 if validation["status"] != "failed" else 1


def run_adjudicate(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    suspicions_doc = load_optional_json(artifact_dir / "suspicions.json") or {}
    suspicions = suspicions_doc.get("suspicions", [])
    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")
    finding_gate = load_optional_json(artifact_dir / "finding-gate.json")
    wrote_finding_gate = False
    if finding_gate is None:
        finding_gate = build_finding_gate(suspicions, burp_history)
        write_json(artifact_dir / "finding-gate.json", finding_gate)
        wrote_finding_gate = True

    findings = build_findings(suspicions, finding_gate)
    hardening_notes = build_hardening_notes(suspicions, finding_gate)
    evidence_gaps = load_optional_json(artifact_dir / "evidence-gaps.json")
    blackbox_coverage = load_optional_json(artifact_dir / "blackbox-coverage.json")
    environment_readiness = load_optional_json(artifact_dir / "environment-readiness.json")
    evidence_chain = load_optional_json(artifact_dir / "evidence-chain.json")
    adjudication = build_adjudication(
        suspicions,
        finding_gate,
        findings,
        hardening_notes,
        evidence_gaps,
        blackbox_coverage,
        environment_readiness,
        evidence_chain,
    )
    findings_path = artifact_dir / "findings.json"
    hardening_notes_path = artifact_dir / "hardening-notes.json"
    adjudication_path = artifact_dir / "adjudication.json"
    output_paths = [findings_path, hardening_notes_path, adjudication_path]
    if wrote_finding_gate:
        output_paths.append(artifact_dir / "finding-gate.json")
    write_json(findings_path, {"generated_at": utc_now(), "findings": findings})
    write_json(
        hardening_notes_path,
        {"generated_at": utc_now(), "hardening_notes": hardening_notes},
    )
    write_json(adjudication_path, adjudication)
    print(f"Adjudication: {adjudication['status']}")
    print(
        "Decisions: "
        f"{len(findings)} findings, "
        f"{len(hardening_notes)} hardening notes, "
        f"{adjudication['summary']['manual_review']} manual review, "
        f"{adjudication['summary']['blocked']} blocked"
    )
    print(f"Wrote {adjudication_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="adjudicate",
            output_paths=output_paths,
        )
    )
    return 0 if adjudication["status"] not in {"manual-review", "blocked"} else 1


def run_capabilities(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    no_write = bool(args.no_write)
    if not no_write:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        write_target_profile_artifact(artifact_dir, profile, target, source_root)
    capabilities = build_capabilities(target, artifact_dir, profile)
    output_path = artifact_dir / "burp-capabilities.json"
    if not no_write:
        write_json(output_path, capabilities)
    print(json.dumps(capabilities, indent=2))
    target_info = capabilities.get("target", {}) or {}
    burp_info = capabilities.get("burp", {}) or {}
    target_ok = target_info.get("reachable") is True
    mcp_ok = burp_info.get("mcp_port_open") is True
    proxy_ok = burp_info.get("proxy_8080_open") is True
    script_ok = burp_info.get("check_script_ok") is True
    capability_status = "ready" if target_ok and mcp_ok and proxy_ok and script_ok else "limited"
    print(f"Capabilities: {capability_status}")
    print(
        "Target: "
        f"reachable={target_info.get('reachable')} "
        f"health_status={target_info.get('health_status')} "
        f"service={target_info.get('service') or 'unknown'}"
    )
    print(
        "Burp: "
        f"mcp_port_open={burp_info.get('mcp_port_open')} "
        f"proxy_8080_open={burp_info.get('proxy_8080_open')} "
        f"codex_mcp_get_burp_ok={burp_info.get('codex_mcp_get_burp_ok')} "
        f"check_script_ok={burp_info.get('check_script_ok')}"
    )
    approval_tools = burp_info.get("approval_sensitive_tools", {}) or {}
    if approval_tools:
        print(
            "Burp tools: "
            f"http_history={approval_tools.get('observed_get_proxy_http_history') or 'unknown'} "
            f"http_request={approval_tools.get('observed_send_http1_request') or 'unknown'} "
            f"repeater={approval_tools.get('observed_create_repeater_tab') or 'unknown'} "
            f"intercept={approval_tools.get('observed_set_proxy_intercept_state') or 'unknown'}"
        )
    if no_write:
        print("No files written (--no-write).")
    else:
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="capabilities",
                output_paths=[
                    *target_profile_artifact_paths(artifact_dir),
                    output_path,
                ],
            )
        )
    return 0 if capabilities["target"]["reachable"] and capabilities["burp"]["mcp_port_open"] else 1


def run_readiness(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    no_write = bool(args.no_write)
    if not no_write:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        write_target_profile_artifact(artifact_dir, profile, target, source_root)
    capabilities = build_capabilities(target, artifact_dir, profile)
    quote_path = artifact_dir / "quote-collection.json"
    quote_collection = json.loads(read_text(quote_path)) if quote_path.exists() else None
    transaction_path = artifact_dir / "transaction-intent.json"
    transaction_intent = json.loads(read_text(transaction_path)) if transaction_path.exists() else None
    readiness = build_environment_readiness(
        target,
        source_root,
        artifact_dir,
        capabilities=capabilities,
        quote_collection=quote_collection,
        transaction_intent=transaction_intent,
    )
    capabilities_path = artifact_dir / "burp-capabilities.json"
    readiness_path = artifact_dir / "environment-readiness.json"
    if not no_write:
        write_json(capabilities_path, capabilities)
        write_json(readiness_path, readiness)
    print(json.dumps(readiness, indent=2))
    check_status_counts: dict[str, int] = {}
    for check in readiness.get("checks", []) or []:
        increment_count(check_status_counts, str(check.get("status") or "unknown"))
    print(f"Readiness: {readiness['status']}")
    print(
        "Checks: "
        f"{len(readiness.get('checks', []) or [])} total, "
        f"status_counts={json.dumps(check_status_counts, sort_keys=True)}"
    )
    next_steps = readiness.get("next_steps", []) or []
    if next_steps:
        next_step_preview_limit = 3
        print("Next steps:")
        for step in next_steps[:next_step_preview_limit]:
            print(f"- {step}")
        overflow_line = format_readiness_next_step_overflow(
            len(next_steps),
            next_step_preview_limit,
            no_write=no_write,
            output_path=readiness_path,
        )
        if overflow_line:
            print(overflow_line)
    else:
        print("Next steps: none")
    if no_write:
        print("No files written (--no-write).")
    else:
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="readiness",
                output_paths=[
                    *target_profile_artifact_paths(artifact_dir),
                    capabilities_path,
                    readiness_path,
                ],
            )
        )
    return 0 if readiness["status"] == "ready" else 1


def run_decode_transactions(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    ensure_burp_transaction_candidates_artifact(artifact_dir)
    results = load_jsonl(artifact_dir / "probe-results.jsonl")
    extra_inputs = [Path(item).resolve() for item in args.input or []]
    transaction_intent = build_transaction_intent(
        artifact_dir,
        results,
        args.node,
        source_root,
        extra_inputs,
        policy_path=Path(args.intent_policy).resolve() if args.intent_policy else None,
        intent_direction=args.intent_direction,
        intent_wallet=args.intent_wallet,
        intent_amount_in=args.intent_amount_in,
        intent_allowed_programs=args.intent_allowed_program or None,
    )
    output_path = artifact_dir / "transaction-intent.json"
    write_json(output_path, transaction_intent)
    print(f"Wrote {output_path}")
    print(
        "Transactions: "
        f"{transaction_intent['candidates_seen']} candidates, "
        f"{transaction_intent['decoded_transactions']} decoded"
    )
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="decode-transactions",
            output_paths=[
                *target_profile_artifact_paths(artifact_dir),
                artifact_dir / "burp-transaction-candidates.json",
                output_path,
            ],
        )
    )
    return 0


def run_transaction_decoder_selftest(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    result = build_transaction_decoder_selftest(
        artifact_dir,
        source_root,
        args.node,
        direction=args.direction,
        wallet=args.wallet,
        amount_in=args.amount_in,
    )
    output_path = artifact_dir / "transaction-decoder-selftest.json"
    write_json(output_path, result)
    print(f"Transaction decoder self-test: {result['status']}")
    print(f"Wrote {output_path}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="self-test-transactions",
            output_paths=[
                artifact_dir / TARGET_PROFILE_ARTIFACT,
                artifact_dir / STRATEGY_REGISTRY_ARTIFACT,
                artifact_dir / PROFILE_VALIDATION_ARTIFACT,
                output_path,
            ],
        )
    )
    return 0 if result["status"] == "passed" else 1


def build_quote_collection_body(direction: str, wallet: str, amount_in: str) -> dict[str, Any]:
    expected = expected_mints_for_direction(direction)
    if expected is None:
        raise ValueError("direction must be buy or sell")
    source_mint, destination_mint = expected
    return {
        "route": {
            "source": {"chain": "Solana", "address": source_mint},
            "destination": {"chain": "Solana", "address": destination_mint},
        },
        "amountIn": amount_in,
        "sender": wallet,
        "recipient": wallet,
        "maxNumQuotes": 1,
    }


def diagnose_quote_collection_response(response: dict[str, Any], saved_payload: str | None) -> dict[str, Any]:
    status = response.get("status")
    body_sample = response.get("body_sample") or response.get("body_text") or ""

    if status == 200 and saved_payload:
        return {
            "classification": "quote-payload-collected",
            "summary": "A quote response was saved for transaction candidate extraction.",
            "next_step": "Decode the saved payload and compare transaction intent before any signing flow.",
        }

    if status is None:
        return {
            "classification": "local-transport-error",
            "summary": "The local quote collector could not reach the target quote endpoint.",
            "next_step": "Confirm the target server is running and rerun collect-quote.",
        }

    if status == 500 and "Quote service is not configured" in body_sample:
        return {
            "classification": "m0-config-missing-or-placeholder",
            "summary": "The target rejected quote collection before upstream forwarding because the M0 key is missing or still set to a template placeholder.",
            "next_step": "Configure a real M0_ORCHESTRATION_API_KEY, restart the target server, and rerun collect-quote.",
        }

    if status in {401, 403} and "M0 orchestration quote failed" in body_sample:
        return {
            "classification": "m0-upstream-auth-or-policy-rejected",
            "summary": "The target reached M0, but upstream rejected the quote request after local validation.",
            "next_step": "Verify the M0 key, account permissions, route, wallet, and amount, then rerun collect-quote.",
        }

    if status == 400 and "Invalid quote request body" in body_sample:
        return {
            "classification": "local-quote-policy-rejected",
            "summary": "The target rejected the quote body during local validation.",
            "next_step": "Review the generated quote request and local quote policy before rerunning collect-quote.",
        }

    if status == 502 and "Invalid response shape" in body_sample:
        return {
            "classification": "m0-response-shape-unexpected",
            "summary": "M0 returned a successful HTTP response, but the target did not recognize the quote response shape.",
            "next_step": "Capture the response shape in a controlled environment and update transaction extraction only after reviewing it.",
        }

    return {
        "classification": "quote-collection-no-payload",
        "summary": f"Quote collection returned HTTP {status} without a saved transaction payload.",
        "next_step": "Inspect quote-collection.json and rerun collect-quote after the upstream/configuration issue is resolved.",
    }


def run_collect_quote(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)
    ensure_burp_transaction_candidates_artifact(artifact_dir)

    body = build_quote_collection_body(args.direction, args.wallet, args.amount_in)
    quote_path = probe_target_path(profile, "quote", "path", "/api/quote")
    output_path = Path(args.output).resolve() if args.output else artifact_dir / "transaction-payloads.json"
    policy = {
        "direction": args.direction,
        "wallet": args.wallet,
        "amountIn": args.amount_in,
    }
    if args.intent_allowed_program:
        policy["allowedPrograms"] = args.intent_allowed_program
    write_json(artifact_dir / "transaction-intent-policy.json", policy)

    try:
        with TargetProbeLock(target, purpose="collect-quote"):
            response = http_request(
                target,
                "POST",
                quote_path,
                body=json.dumps(body),
                headers={
                    "Content-Type": "application/json",
                    "Origin": origin_for(target),
                    "User-Agent": "InferForge-Quote-Collector/0.1",
                },
                timeout=30,
            )
    except RuntimeError as error:
        lock_path = artifact_dir / "target-probe-lock.json"
        write_json(
            lock_path,
            {
                "generated_at": utc_now(),
                "status": "blocked",
                "target": target,
                "error": str(error),
                "safety": "Only one active collection/probe run may target the same service at a time.",
            },
        )
        print(f"Target probe lock blocked collect-quote: {error}")
        print(f"Wrote {lock_path}")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="collect-quote",
                output_paths=[
                    *target_profile_artifact_paths(artifact_dir),
                    artifact_dir / "burp-transaction-candidates.json",
                    artifact_dir / "transaction-intent-policy.json",
                    lock_path,
                ],
            )
        )
        return 2

    saved_payload = None
    if response["status"] == 200 and response["body_text"]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(response["body_text"], encoding="utf-8")
        saved_payload = str(output_path)

    diagnosis = diagnose_quote_collection_response(response, saved_payload)
    quote_collection = {
        "generated_at": utc_now(),
        "profile": profile_summary(profile),
        "target": target,
        "path": quote_path,
        "safety": "Quote collection only. No wallet signing or transaction submission is performed.",
        "request": {
            "direction": args.direction,
            "amountIn": args.amount_in,
            "wallet": args.wallet,
            "sourceMint": body["route"]["source"]["address"],
            "destinationMint": body["route"]["destination"]["address"],
        },
        "response": {
            "status": response["status"],
            "duration_ms": response["duration_ms"],
            "body_sha256": response["body_sha256"],
            "body_length": response["body_length"],
            "body_truncated": response["body_truncated"],
            "body_sample": response["body_sample"],
            "saved_payload": saved_payload,
        },
        "diagnosis": diagnosis,
    }
    write_json(artifact_dir / "quote-collection.json", quote_collection)

    extra_inputs = [output_path] if saved_payload else []
    transaction_intent = build_transaction_intent(
        artifact_dir,
        load_jsonl(artifact_dir / "probe-results.jsonl"),
        args.node,
        source_root,
        extra_inputs=extra_inputs,
        intent_direction=args.direction,
        intent_wallet=args.wallet,
        intent_amount_in=args.amount_in,
        intent_allowed_programs=args.intent_allowed_program or None,
    )
    write_json(artifact_dir / "transaction-intent.json", transaction_intent)
    results = load_jsonl(artifact_dir / "probe-results.jsonl")
    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")
    rpc_policy_path = artifact_dir / "rpc-method-policy.json"
    rpc_method_policy = (
        json.loads(read_text(rpc_policy_path))
        if rpc_policy_path.exists()
        else build_rpc_method_policy(source_root, results)
    )
    orca_baseline_path = artifact_dir / "orca-baseline.json"
    orca_baseline = json.loads(read_text(orca_baseline_path)) if orca_baseline_path.exists() else None
    source_peeks = load_optional_json(artifact_dir / "source-peek-results.json") or build_source_peeks(source_root, profile, [])
    evidence_gaps = build_evidence_gaps(
        build_clusters(profile, source_root),
        results,
        burp_history,
        transaction_intent,
        rpc_method_policy,
        orca_baseline,
        quote_collection,
        source_peeks,
    )
    write_json(artifact_dir / "evidence-gaps.json", evidence_gaps)
    transaction_decoder_selftest = build_transaction_decoder_selftest(
        artifact_dir,
        source_root,
        args.node,
        direction=args.direction,
        wallet=args.wallet,
        amount_in=args.amount_in,
    )
    write_json(artifact_dir / "transaction-decoder-selftest.json", transaction_decoder_selftest)
    capabilities = build_capabilities(target, artifact_dir, profile)
    write_json(artifact_dir / "burp-capabilities.json", capabilities)
    environment_readiness = build_environment_readiness(
        target,
        source_root,
        artifact_dir,
        capabilities=capabilities,
        quote_collection=quote_collection,
        transaction_intent=transaction_intent,
    )
    write_json(artifact_dir / "environment-readiness.json", environment_readiness)

    print(f"Quote status: {response['status']}")
    print(f"Diagnosis: {diagnosis['classification']}")
    print(f"Wrote {artifact_dir / 'quote-collection.json'}")
    if saved_payload:
        print(f"Saved quote payload to {saved_payload}")
    print(
        "Transactions: "
        f"{transaction_intent['candidates_seen']} candidates, "
        f"{transaction_intent['decoded_transactions']} decoded, "
        f"policy={transaction_intent['intent_policy_checks']['status']}"
    )
    print(f"Decoder self-test: {transaction_decoder_selftest['status']}")
    print(f"Readiness: {environment_readiness['status']}")
    print(f"Evidence gaps: {len(evidence_gaps['gaps'])}")
    output_paths = [
        *target_profile_artifact_paths(artifact_dir),
        artifact_dir / "burp-transaction-candidates.json",
        artifact_dir / "transaction-intent-policy.json",
        artifact_dir / "quote-collection.json",
        artifact_dir / "transaction-intent.json",
        artifact_dir / "evidence-gaps.json",
        artifact_dir / "transaction-decoder-selftest.json",
        artifact_dir / "burp-capabilities.json",
        artifact_dir / "environment-readiness.json",
    ]
    if saved_payload:
        output_paths.append(output_path)
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="collect-quote",
            output_paths=output_paths,
        )
    )
    return 0


def run_collect_orca_baseline(args: argparse.Namespace) -> int:
    profile, artifact_dir, target, source_root = resolve_run_context(args)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    write_target_profile_artifact(artifact_dir, profile, target, source_root)

    try:
        with TargetProbeLock(target, purpose="collect-orca-baseline"):
            baseline = build_orca_baseline(
                target,
                source_root,
                address=args.address,
                strategy_id=args.strategy_id,
                profile=profile,
            )
    except RuntimeError as error:
        lock_path = artifact_dir / "target-probe-lock.json"
        write_json(
            lock_path,
            {
                "generated_at": utc_now(),
                "status": "blocked",
                "target": target,
                "error": str(error),
                "safety": "Only one active collection/probe run may target the same service at a time.",
            },
        )
        print(f"Target probe lock blocked collect-orca-baseline: {error}")
        print(f"Wrote {lock_path}")
        print_refreshed_manifests(
            refresh_current_artifact_manifest(
                artifact_dir=artifact_dir,
                target=target,
                command="collect-orca-baseline",
                output_paths=[
                    *target_profile_artifact_paths(artifact_dir),
                    lock_path,
                ],
            )
        )
        return 2
    write_json(artifact_dir / "orca-baseline.json", baseline)

    results = load_jsonl(artifact_dir / "probe-results.jsonl")
    burp_history = load_jsonl(artifact_dir / "burp-history-observations.jsonl")
    transaction_intent_path = artifact_dir / "transaction-intent.json"
    transaction_intent = (
        json.loads(read_text(transaction_intent_path))
        if transaction_intent_path.exists()
        else build_transaction_intent(artifact_dir, results, args.node, source_root)
    )
    rpc_policy_path = artifact_dir / "rpc-method-policy.json"
    rpc_method_policy = (
        json.loads(read_text(rpc_policy_path))
        if rpc_policy_path.exists()
        else build_rpc_method_policy(source_root, results)
    )
    quote_collection_path = artifact_dir / "quote-collection.json"
    quote_collection = json.loads(read_text(quote_collection_path)) if quote_collection_path.exists() else None
    source_peeks = load_optional_json(artifact_dir / "source-peek-results.json") or build_source_peeks(source_root, profile, [])
    evidence_gaps = build_evidence_gaps(
        build_clusters(profile, source_root),
        results,
        burp_history,
        transaction_intent,
        rpc_method_policy,
        baseline,
        quote_collection,
        source_peeks,
    )
    write_json(artifact_dir / "evidence-gaps.json", evidence_gaps)

    response = baseline.get("response", {})
    request = baseline.get("request", {})
    print(f"Orca baseline status: {response.get('status')}")
    print(f"Success: {baseline.get('success')}")
    print(f"Address: {request.get('address')}")
    print(f"Wrote {artifact_dir / 'orca-baseline.json'}")
    print(f"Evidence gaps: {len(evidence_gaps['gaps'])}")
    print_refreshed_manifests(
        refresh_current_artifact_manifest(
            artifact_dir=artifact_dir,
            target=target,
            command="collect-orca-baseline",
            output_paths=[
                *target_profile_artifact_paths(artifact_dir),
                artifact_dir / "orca-baseline.json",
                artifact_dir / "evidence-gaps.json",
            ],
        )
    )
    return 0 if baseline.get("success") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="InferForge local greybox runner")
    parser.add_argument(
        "--profile",
        default=str(DEFAULT_PROFILE_PATH),
        help="Target profile JSON. Defaults to profiles/infrafi-web.json.",
    )
    parser.add_argument("--target", help="Base URL for the local target. Defaults to the target profile.")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR), help="Artifact directory")
    parser.add_argument("--source-root", help="Target source root. Defaults to the target profile.")
    parser.add_argument("--node", default=DEFAULT_NODE, help="Node binary for WebSocket probes")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_intent_policy_args(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--intent-policy",
            help="JSON file describing expected transaction intent for transaction-intent checks",
        )
        command.add_argument(
            "--intent-direction",
            choices=["buy", "sell"],
            help="Expected swap direction for transaction-intent checks",
        )
        command.add_argument(
            "--intent-wallet",
            help="Expected Solana wallet/sender for transaction-intent checks",
        )
        command.add_argument(
            "--intent-amount-in",
            help="Expected raw positive integer amountIn for transaction-intent checks",
        )
        command.add_argument(
            "--intent-allowed-program",
            action="append",
            help="Allowed compiled instruction program ID for transaction-intent checks. Repeat as needed.",
        )

    profile = sub.add_parser("profile", help="Write the effective target profile and endpoint clusters")
    profile.set_defaults(func=run_profile)

    review_candidates = sub.add_parser(
        "review-candidates",
        help="List inert review-only observation candidates from the current profile",
    )
    review_candidates.add_argument(
        "--no-write",
        action="store_true",
        help="Print candidates only; do not write review-observation-candidates.json or refreshed manifests.",
    )
    review_candidates.set_defaults(func=run_review_candidates)

    promote_candidate = sub.add_parser(
        "promote-observation-candidate",
        help="Promote one reviewed observation candidate into a new profile without sending traffic",
    )
    promote_candidate.add_argument("--candidate-id", required=True, help="review_observation_candidates id to promote")
    promote_candidate.add_argument("--path", required=True, help="Approved concrete local path, for example /api/proxy/status")
    promote_candidate.add_argument("--output", help="Where to write the promoted profile. Defaults to .greybox/reviewed-profile.json")
    promote_candidate.add_argument("--force", action="store_true", help="Allow overwriting the output profile")
    promote_candidate.add_argument("--observation-id", help="Override the generated burp_observation_plan id")
    promote_candidate.add_argument("--method", choices=sorted(HTTP_METHODS), help="Override the observation HTTP method")
    promote_candidate.add_argument(
        "--expected-status",
        action="append",
        type=int,
        help="Allowed response status for the promoted observation. Repeat as needed.",
    )
    promote_candidate.add_argument("--note", help="Short review note to store with the promoted observation")
    promote_candidate.add_argument(
        "--no-write",
        action="store_true",
        help="Validate and preview the promoted observation without writing reviewed profile artifacts or refreshed manifests.",
    )
    promote_candidate.set_defaults(func=run_promote_observation_candidate)

    discover_profile = sub.add_parser(
        "discover-profile",
        help="Statically discover Next.js route handlers and write a starter target profile",
    )
    discover_profile.add_argument(
        "--output",
        help="Where to write the generated starter profile. Defaults to .greybox/discovered-profile.json",
    )
    discover_profile.add_argument("--name", help="Profile machine name. Defaults to the source-root directory name")
    discover_profile.add_argument("--display-name", help="Profile display name. Defaults to the source-root directory name")
    discover_profile.add_argument(
        "--force",
        action="store_true",
        help="Allow overwriting an explicit --output profile path",
    )
    discover_profile.set_defaults(func=run_discover_profile)

    collect = sub.add_parser("collect", help="Normalize available Burp history observations into traffic artifacts")
    collect.add_argument(
        "--observed-only",
        action="store_true",
        help="Select only endpoint kinds seen in Burp/history observations",
    )
    collect.set_defaults(func=run_collect)

    burp_observe = sub.add_parser(
        "burp-observe",
        help="Generate a minimal safe observation flow through Burp Proxy",
    )
    burp_observe.add_argument(
        "--proxy",
        default="http://127.0.0.1:8080",
        help="Burp Proxy URL for observation traffic",
    )
    burp_observe.add_argument(
        "--ws-upgrade",
        action="store_true",
        help="Also open one low-volume Solana RPC WebSocket upgrade through Burp Proxy",
    )
    burp_observe.add_argument(
        "--allow-nonlocal-target",
        action="store_true",
        help="Allow observation traffic to non-loopback targets",
    )
    burp_observe.set_defaults(func=run_burp_observe)

    burp_sync = sub.add_parser(
        "burp-sync",
        help="Read Burp MCP history directly and import normalized observations",
    )
    burp_sync.add_argument(
        "--mcp-url",
        default="http://127.0.0.1:9876",
        help="Burp MCP SSE URL. Defaults to http://127.0.0.1:9876",
    )
    burp_sync.add_argument(
        "--mcp-timeout",
        type=positive_int,
        default=10,
        help="Timeout in seconds for each Burp MCP HTTP/SSE operation",
    )
    burp_sync.add_argument(
        "--proxy",
        default="http://127.0.0.1:8080",
        help="Burp Proxy URL used when --observe is enabled",
    )
    burp_sync.add_argument(
        "--observe",
        action="store_true",
        help="First generate the profile's deterministic observation flow through Burp Proxy",
    )
    burp_sync.add_argument(
        "--ws-upgrade",
        action="store_true",
        help="When --observe is enabled, also open one low-volume WebSocket upgrade through Burp Proxy",
    )
    burp_sync.add_argument(
        "--allow-nonlocal-target",
        action="store_true",
        help="Allow --observe traffic to non-loopback targets",
    )
    burp_sync.add_argument(
        "--keep-intercept-state",
        action="store_true",
        help="Do not force Burp Proxy Intercept off before syncing history",
    )
    burp_sync.add_argument(
        "--regex",
        help="Override the generated Burp history regex",
    )
    burp_sync.add_argument(
        "--count",
        type=positive_int,
        default=200,
        help="Maximum Burp history items to request from MCP",
    )
    burp_sync.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Burp history offset to request from MCP",
    )
    burp_sync.add_argument(
        "--raw-output",
        help="Where to save raw MCP HTTP history text. Defaults to .greybox/burp-mcp-history-latest.txt",
    )
    burp_sync.add_argument(
        "--websocket-history",
        action="store_true",
        help="Also save raw Burp MCP WebSocket history text when the tool is available",
    )
    burp_sync.add_argument(
        "--websocket-raw-output",
        help="Where to save raw MCP WebSocket history text. Defaults to .greybox/burp-mcp-websocket-history-latest.txt",
    )
    burp_sync.add_argument(
        "--replace",
        action="store_true",
        help="Replace burp-history-observations.jsonl instead of merging and deduplicating",
    )
    burp_sync.add_argument(
        "--all-hosts",
        action="store_true",
        help="Do not filter imported history to the current --target host",
    )
    burp_sync.add_argument(
        "--source",
        default="burp-proxy-http-history",
        help="Source label to write into imported observations",
    )
    burp_sync.add_argument(
        "--observed-only",
        action="store_true",
        help="Select only endpoint kinds seen in imported Burp observations",
    )
    burp_sync.set_defaults(func=run_burp_sync)

    import_history = sub.add_parser(
        "import-burp-history",
        help="Import raw Burp MCP HTTP history output into normalized observations",
    )
    import_history.add_argument(
        "--input",
        action="append",
        help="Raw Burp MCP history text/JSON file. Use '-' to read stdin.",
    )
    import_history.add_argument(
        "--replace",
        action="store_true",
        help="Replace burp-history-observations.jsonl instead of merging and deduplicating",
    )
    import_history.add_argument(
        "--all-hosts",
        action="store_true",
        help="Do not filter imported history to the current --target host",
    )
    import_history.add_argument(
        "--source",
        default="burp-proxy-http-history",
        help="Source label to write into imported observations",
    )
    import_history.add_argument(
        "--observed-only",
        action="store_true",
        help="Select only endpoint kinds seen in imported Burp observations",
    )
    import_history.set_defaults(func=run_import_burp_history)

    plan = sub.add_parser("plan", help="Generate endpoint-aware safe probe plan without running probes")
    plan.add_argument("--include-external", action="store_true", help="Plan bounded M0 quote validation probes")
    plan.add_argument("--max-probes", type=positive_int, help="Limit planned HTTP probes to the top-ranked N")
    plan.add_argument("--no-ws", dest="ws", action="store_false", help="Skip WebSocket probes")
    plan.add_argument(
        "--observed-only",
        action="store_true",
        help="Plan only for endpoint kinds seen in traffic-index.json",
    )
    plan.add_argument(
        "--no-write",
        action="store_true",
        help="Print probe plan summary only; do not write probe-plan artifacts or refreshed manifests.",
    )
    plan.set_defaults(func=run_plan, ws=True)

    attack_strategy = sub.add_parser(
        "attack-strategy",
        help="Recompute attack strategy coverage and next-action status from current artifacts",
    )
    attack_strategy.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero unless attack strategy status is ready-for-regression.",
    )
    attack_strategy.add_argument(
        "--no-write",
        action="store_true",
        help="Print strategy coverage only; do not write attack-strategy.json or refreshed manifests.",
    )
    attack_strategy.set_defaults(func=run_attack_strategy)

    audit = sub.add_parser("audit", help="Run safe probes, source peeks, clustering, and report generation")
    audit.add_argument("--include-external", action="store_true", help="Allow bounded M0 quote validation probes")
    audit.add_argument("--max-probes", type=positive_int, help="Limit executed HTTP probes to the top-ranked N")
    audit.add_argument("--no-ws", dest="ws", action="store_false", help="Skip WebSocket probes")
    audit.add_argument(
        "--ws-resource-probes",
        action="store_true",
        help="Run approval-gated low-volume WebSocket connection-limit probes",
    )
    audit.add_argument(
        "--observed-only",
        action="store_true",
        help="Run only probes selected from observed traffic, without source-assisted expansion",
    )
    add_intent_policy_args(audit)
    audit.set_defaults(func=run_audit, ws=True, ws_resource_probes=False)

    gate = sub.add_parser("gate", help="Recompute finding gate decisions from suspicions and evidence")
    gate.set_defaults(func=run_gate)

    coverage = sub.add_parser("coverage", help="Recompute black-box coverage gate from current artifacts")
    coverage.set_defaults(func=run_coverage)

    burp_observation_coverage = sub.add_parser(
        "burp-observation-coverage",
        help="Recompute Burp browser observation coverage from current artifacts",
    )
    burp_observation_coverage.set_defaults(func=run_burp_observation_coverage)

    discovery_coverage = sub.add_parser(
        "discovery-coverage",
        help="Compare static route discovery against the current profile, observations, and review gates",
    )
    discovery_coverage.add_argument(
        "--route-inventory",
        help="Route inventory JSON to check. Defaults to --artifact-dir/route-inventory.json, discovering from source if missing.",
    )
    discovery_coverage.add_argument(
        "--output",
        help="Where to write discovery-coverage.json. Defaults to --artifact-dir/discovery-coverage.json.",
    )
    discovery_coverage.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero unless every discovered surface is fully covered with no human-review gates.",
    )
    discovery_coverage.set_defaults(func=run_discovery_coverage)

    response_deltas = sub.add_parser(
        "response-deltas",
        help="Recompute response delta analysis from current probe results",
    )
    response_deltas.set_defaults(func=run_response_deltas)

    evidence_chain = sub.add_parser(
        "evidence-chain",
        help="Recompute machine-readable evidence chain from current artifacts",
    )
    evidence_chain.set_defaults(func=run_evidence_chain)

    source_peek_requests = sub.add_parser(
        "source-peek-requests",
        help="Recompute source-peek request rationale from current artifacts",
    )
    source_peek_requests.set_defaults(func=run_source_peek_requests)

    evidence_appendix = sub.add_parser(
        "evidence-appendix",
        help="Recompute compact request/response evidence appendix from current artifacts",
    )
    evidence_appendix.set_defaults(func=run_evidence_appendix)

    report = sub.add_parser(
        "report",
        help="Refresh report.md and index.html from current artifacts without probing",
    )
    report.set_defaults(func=run_report)

    verification_queue = sub.add_parser(
        "verification-queue",
        help="Recompute verification queue and reproduction steps from current artifacts",
    )
    verification_queue.add_argument(
        "--no-write",
        action="store_true",
        help="Print queue summary only; do not write verification-queue.json, reproduction steps, review blockers, or refreshed manifests.",
    )
    verification_queue.set_defaults(func=run_verification_queue)

    review_blockers = sub.add_parser(
        "review-blockers",
        help="Summarize human-review, profile-update, and external blockers from current artifacts",
    )
    review_blockers.add_argument(
        "--output",
        help="Where to write review-blockers.json. Defaults to --artifact-dir/review-blockers.json.",
    )
    review_blockers.add_argument(
        "--check-dir",
        action="append",
        help="Child artifact directory to include in a rollup. Repeat as needed.",
    )
    review_blockers.add_argument(
        "--discover-child-runs",
        action="store_true",
        help="Build a rollup from child directories under --artifact-dir that contain review-blockers.json.",
    )
    review_blockers.add_argument(
        "--markdown-output",
        help="Where to write review-blockers.md. Defaults to --artifact-dir/review-blockers.md.",
    )
    review_blockers.add_argument(
        "--no-write",
        action="store_true",
        help="Print blocker summary only; do not write review-blockers.json, review-blockers.md, or refreshed manifests.",
    )
    review_blockers.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero unless no review, profile-update, or external blockers remain.",
    )
    review_blockers.set_defaults(func=run_review_blockers)

    manifest = sub.add_parser(
        "manifest",
        help="Hash and summarize generated artifacts for integrity/reproducibility checks",
    )
    manifest.add_argument(
        "--command",
        default="manifest",
        help="Command label to store in artifact-manifest.json",
    )
    manifest.set_defaults(func=run_manifest)

    artifact_health = sub.add_parser(
        "artifact-health",
        help="Validate artifact manifests plus JSON/JSONL parse health across one or more artifact directories",
    )
    artifact_health.add_argument(
        "--check-dir",
        action="append",
        help="Artifact directory to check. Repeat as needed. Defaults to --artifact-dir.",
    )
    artifact_health.add_argument(
        "--discover-child-runs",
        action="store_true",
        help="Also check regression-suite managed child artifact dirs, falling back to child dirs with artifact-manifest.json.",
    )
    artifact_health.add_argument(
        "--output",
        help="Where to write artifact-health.json. Defaults to --artifact-dir/artifact-health.json.",
    )
    artifact_health.add_argument(
        "--no-write",
        action="store_true",
        help="Print health only; do not write artifact-health.json.",
    )
    artifact_health.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero unless every checked artifact directory is healthy with no human review or external blockers.",
    )
    artifact_health.set_defaults(func=run_artifact_health)

    regression_suite = sub.add_parser(
        "regression-suite",
        help="Run the default and discovered-profile regression workflow and summarize artifact health",
    )
    regression_suite.add_argument(
        "--default-artifact-dir",
        default=str(DEFAULT_ARTIFACT_DIR / "regression-default"),
        help="Artifact directory for the checked-in default profile regression.",
    )
    regression_suite.add_argument(
        "--discovered-artifact-dir",
        default=str(DEFAULT_ARTIFACT_DIR / "regression-discovered"),
        help="Artifact directory for the statically discovered profile regression.",
    )
    regression_suite.add_argument(
        "--mcp-url",
        default="http://127.0.0.1:9876",
        help="Burp MCP SSE URL used by burp-sync steps.",
    )
    regression_suite.add_argument(
        "--proxy",
        default="http://127.0.0.1:8080",
        help="Burp Proxy URL used by burp-sync --observe steps.",
    )
    regression_suite.add_argument(
        "--burp-count",
        type=positive_int,
        default=80,
        help="Maximum Burp history items to request for each burp-sync step.",
    )
    regression_suite.add_argument(
        "--include-external",
        action="store_true",
        help="Pass --include-external to audit steps for bounded external validation probes.",
    )
    regression_suite.add_argument(
        "--ws-resource-probes",
        action="store_true",
        help="Pass --ws-resource-probes to audit steps for bounded WebSocket connection-limit validation.",
    )
    regression_suite.add_argument(
        "--allow-nonlocal-target",
        action="store_true",
        help="Allow burp-sync --observe traffic to non-loopback targets.",
    )
    regression_suite.add_argument(
        "--skip-discovered",
        action="store_true",
        help="Only run the checked-in default profile regression.",
    )
    regression_suite.add_argument(
        "--skip-discover-profile",
        action="store_true",
        help="Reuse the existing discovered profile instead of refreshing it first.",
    )
    regression_suite.add_argument(
        "--skip-discovery-coverage",
        action="store_true",
        help="Skip static discovery coverage checking for the discovered profile.",
    )
    regression_suite.add_argument(
        "--skip-review-blockers",
        action="store_true",
        help="Skip root-level review-blockers rollup after artifact health.",
    )
    regression_suite.add_argument(
        "--skip-self-tests",
        action="store_true",
        help="Skip static self-tests that normally run before fixture regression steps.",
    )
    regression_suite.add_argument(
        "--skip-burp-sync",
        action="store_true",
        help="Skip Burp observe/sync steps and rely on existing Burp history artifacts.",
    )
    regression_suite.add_argument(
        "--skip-orca-baseline",
        action="store_true",
        help="Skip single-address Orca baseline collection.",
    )
    regression_suite.add_argument(
        "--skip-audit",
        action="store_true",
        help="Skip active audit probe steps and only refresh discovery/Burp/history health as requested.",
    )
    regression_suite.add_argument(
        "--keep-probe-results",
        action="store_true",
        help="Do not remove existing probe-results.jsonl before audit steps.",
    )
    regression_suite.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop scheduling subsequent active regression steps after the first failed step.",
    )
    regression_suite.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero unless artifact health is fully healthy with no human-review or external blockers.",
    )
    regression_suite.add_argument(
        "--step-timeout",
        type=positive_int,
        default=300,
        help="Timeout in seconds for each scheduled regression subcommand.",
    )
    regression_suite.set_defaults(func=run_regression_suite)

    adjudicate = sub.add_parser(
        "adjudicate",
        help="Recompute reportability decisions from finding gate and current artifacts",
    )
    adjudicate.set_defaults(func=run_adjudicate)

    capabilities = sub.add_parser("capabilities", help="Check target and Burp MCP readiness")
    capabilities.add_argument(
        "--no-write",
        action="store_true",
        help="Print capability checks only; do not write burp-capabilities.json or refreshed manifests.",
    )
    capabilities.set_defaults(func=run_capabilities)

    readiness = sub.add_parser(
        "readiness",
        help="Check external dependency readiness without printing secret values",
    )
    readiness.add_argument(
        "--no-write",
        action="store_true",
        help="Print readiness checks only; do not write capability/readiness artifacts or refreshed manifests.",
    )
    readiness.set_defaults(func=run_readiness)

    decode = sub.add_parser(
        "decode-transactions",
        help="Decode Solana transaction payload candidates from quote responses or sidecar files",
    )
    decode.add_argument(
        "--input",
        action="append",
        help="Additional JSON, JSONL, or text file containing base64 transaction payloads",
    )
    add_intent_policy_args(decode)
    decode.set_defaults(func=run_decode_transactions)

    selftest = sub.add_parser(
        "self-test-transactions",
        help="Run a local synthetic transaction decoder self-test without signing or submitting",
    )
    selftest.add_argument("--direction", choices=["buy", "sell"], default="buy", help="Synthetic swap direction")
    selftest.add_argument("--wallet", default=DEFAULT_TEST_WALLET, help="Synthetic wallet/sender")
    selftest.add_argument("--amount-in", default="1000000", help="Synthetic raw positive integer amountIn")
    selftest.set_defaults(func=run_transaction_decoder_selftest)

    profile_selftest = sub.add_parser(
        "self-test-profile-routing",
        help="Run a static self-test proving profile-owned probe paths do not leak regression target paths",
    )
    profile_selftest.set_defaults(func=run_profile_routing_selftest)

    discovery_coverage_selftest = sub.add_parser(
        "self-test-discovery-coverage",
        help="Run a static self-test for discovery-coverage classification and gates",
    )
    discovery_coverage_selftest.set_defaults(func=run_discovery_coverage_selftest)

    command_safety_selftest = sub.add_parser(
        "self-test-command-safety",
        help="Run a static self-test for verification command safety classification",
    )
    command_safety_selftest.set_defaults(func=run_command_safety_selftest)

    review_blockers_selftest = sub.add_parser(
        "self-test-review-blockers",
        help="Run a static self-test for review-blocker grouping and rollups",
    )
    review_blockers_selftest.set_defaults(func=run_review_blockers_selftest)
    artifact_health_selftest = sub.add_parser(
        "self-test-artifact-health",
        help="Run a static self-test for artifact-health manifest integrity checks",
    )
    artifact_health_selftest.set_defaults(func=run_artifact_health_selftest)
    manifest_refresh_selftest = sub.add_parser(
        "self-test-manifest-refresh",
        help="Run a static self-test for artifact writer manifest refresh coverage",
    )
    manifest_refresh_selftest.set_defaults(func=run_manifest_refresh_selftest)

    no_write_selftest = sub.add_parser(
        "self-test-no-write",
        help="Run a synthetic self-test for --no-write command behavior",
    )
    no_write_selftest.set_defaults(func=run_no_write_selftest)

    collect_quote = sub.add_parser(
        "collect-quote",
        help="Safely request /api/quote and save returned transaction payloads without signing or submitting",
    )
    collect_quote.add_argument("--direction", choices=["buy", "sell"], required=True, help="Swap direction to quote")
    collect_quote.add_argument("--wallet", required=True, help="Solana wallet/sender for the quote request")
    collect_quote.add_argument("--amount-in", required=True, help="Raw positive integer amountIn for the quote request")
    collect_quote.add_argument(
        "--output",
        help="Where to save a successful quote response. Defaults to .greybox/transaction-payloads.json",
    )
    collect_quote.add_argument(
        "--intent-allowed-program",
        action="append",
        help="Allowed compiled instruction program ID for immediate transaction-intent checks. Repeat as needed.",
    )
    collect_quote.set_defaults(func=run_collect_quote)

    collect_orca = sub.add_parser(
        "collect-orca-baseline",
        help="Collect one source-known or explicitly supplied Orca pool baseline without enumeration",
    )
    collect_orca.add_argument(
        "--strategy-id",
        help="Source ORCA_WHIRLPOOLS key to baseline. Defaults to the first source-known pool.",
    )
    collect_orca.add_argument(
        "--address",
        help="Explicit single Orca pool address to baseline instead of reading ORCA_WHIRLPOOLS.",
    )
    collect_orca.set_defaults(func=run_collect_orca_baseline)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
