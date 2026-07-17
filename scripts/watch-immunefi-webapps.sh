#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
artifact_dir="${IMMUNEFI_WATCH_ARTIFACT_DIR:-${repo_root}/.greybox/immunefi-webapps-catalog}"

exec python3 "${repo_root}/scripts/inferforge.py" \
  --artifact-dir "${artifact_dir}" \
  immunefi-webapps-catalog \
  --top "${IMMUNEFI_WATCH_TOP:-20}" \
  --show-changes \
  --strict \
  --exit-on-change \
  "$@"
