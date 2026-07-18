#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
workspace="$(mktemp -d)"
trap 'rm -rf "$workspace"' EXIT

cd "$repo_root"

python3 -m compileall -q src scripts/inferforge.py tests
if command -v ruff >/dev/null 2>&1; then
  ruff format --check src tests scripts/inferforge.py
  ruff check src tests scripts/inferforge.py
fi
if command -v pyright >/dev/null 2>&1; then
  pyright
fi
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 scripts/inferforge.py \
  scan \
  --source-root tests/fixtures/vulnerable_web \
  --workspace "$workspace/scan" \
  --sarif tests/fixtures/vulnerable_web/sample.sarif \
  --json
python3 scripts/inferforge.py \
  verify-artifacts \
  --source-root tests/fixtures/vulnerable_web \
  --workspace "$workspace/scan"
