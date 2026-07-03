#!/usr/bin/env bash
set -u

BURP_HOST="${BURP_MCP_HOST:-127.0.0.1}"
BURP_PORT="${BURP_MCP_PORT:-9876}"
BURP_MCP_URL="http://${BURP_HOST}:${BURP_PORT}"
BURP_JAR="${BURP_MCP_EXTENSION_JAR:-/home/ret2basic/.local/share/burp/extensions/burp-mcp-all.jar}"
PROXY_JAR="${BURP_MCP_PROXY_JAR:-/home/ret2basic/.local/share/burp/extensions/mcp-proxy-all.jar}"
BURP_JAVA="${BURP_JAVA:-/home/ret2basic/.local/opt/BurpSuite/jre/bin/java}"

status=0

section() {
  printf '\n== %s ==\n' "$1"
}

ok() {
  printf '[ok] %s\n' "$1"
}

warn() {
  printf '[warn] %s\n' "$1"
  status=1
}

section "Files"
for path in "$BURP_JAR" "$PROXY_JAR" "$BURP_JAVA"; do
  if [ -e "$path" ]; then
    ok "$path"
  else
    warn "missing: $path"
  fi
done

section "Codex MCP"
if command -v codex >/dev/null 2>&1; then
  codex mcp get burp || warn "codex MCP server 'burp' is not registered"
else
  warn "codex command not found"
fi

section "Ports"
if command -v ss >/dev/null 2>&1; then
  if ss -ltnp | grep -E "[:.]${BURP_PORT}[[:space:]]" >/dev/null 2>&1; then
    ss -ltnp | grep -E "[:.]${BURP_PORT}[[:space:]]"
    ok "Burp MCP appears to be listening on ${BURP_MCP_URL}"
  else
    warn "nothing is listening on ${BURP_MCP_URL}"
  fi

  if ss -ltnp | grep -E '[:.]8080[[:space:]]' >/dev/null 2>&1; then
    printf '\nPort 8080 is currently in use:\n'
    ss -ltnp | grep -E '[:.]8080[[:space:]]'
    printf 'If Burp Proxy cannot bind 8080, use 127.0.0.1:8081 for Burp Proxy.\n'
  fi
else
  warn "ss command not found"
fi

section "HTTP Probe"
if command -v curl >/dev/null 2>&1; then
  curl_output="$(curl -i --max-time 3 "$BURP_MCP_URL/sse" 2>&1)"
  curl_status=$?
  printf '%s\n' "$curl_output" | sed -n '1,20p'

  case "$curl_status" in
    0|28)
      if printf '%s\n' "$curl_output" | grep -Eiq 'HTTP/|text/event-stream|event:'; then
        ok "SSE endpoint responded"
      else
        warn "SSE endpoint did not return recognizable MCP/SSE output"
      fi
      ;;
    *)
      warn "curl failed for ${BURP_MCP_URL}/sse"
      ;;
  esac
else
  warn "curl command not found"
fi

section "Result"
if [ "$status" -eq 0 ]; then
  ok "Burp MCP basic checks passed"
else
  warn "Burp MCP is not fully ready yet"
fi

exit "$status"
