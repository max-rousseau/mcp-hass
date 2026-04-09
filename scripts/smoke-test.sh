#!/usr/bin/env bash
#
# MCP-HASS Smoke Test
#
# Validates a running mcp-hass instance using MCP Inspector CLI.
# Requires: npx (Node.js), jq, curl
#
# Usage: ./scripts/smoke-test.sh [URL]
#   URL defaults to http://localhost:3000/mcp

set -euo pipefail

URL="${1:-http://localhost:3000/mcp}"
PASS=0
FAIL=0
EXPECTED_TOOLS=10
EXPECTED_RESOURCES=2
EXPECTED_PROMPTS=2

red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
bold()  { printf "\033[1m%s\033[0m\n" "$*"; }

check() {
    local name="$1"
    shift
    if "$@" >/dev/null 2>&1; then
        green "  PASS  $name"
        PASS=$((PASS + 1))
    else
        red "  FAIL  $name"
        FAIL=$((FAIL + 1))
    fi
}

bold "MCP-HASS Smoke Test"
bold "Target: $URL"
echo ""

# --- Prerequisites ---
for cmd in npx jq curl; do
    if ! command -v "$cmd" &>/dev/null; then
        red "Required command not found: $cmd"
        exit 1
    fi
done

# --- Readiness ---
bold "[1/4] Readiness check"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null || echo "000")
if [ "$STATUS" = "406" ] || [ "$STATUS" = "405" ] || [ "$STATUS" = "200" ]; then
    green "  PASS  Server responding (HTTP $STATUS)"
    PASS=$((PASS + 1))
else
    red "  FAIL  Server not responding (HTTP $STATUS)"
    red "  Is the container running? Try: docker compose up -d"
    exit 1
fi

# --- Tool discovery ---
bold "[2/4] Tool discovery"
TOOLS_RESULT=$(npx -y @modelcontextprotocol/inspector --cli "$URL" --method tools/list --transport http 2>/dev/null)
TOOL_COUNT=$(echo "$TOOLS_RESULT" | jq '.tools | length')
check "tools/list returns $EXPECTED_TOOLS tools" [ "$TOOL_COUNT" -eq "$EXPECTED_TOOLS" ]

if [ "$TOOL_COUNT" -ne "$EXPECTED_TOOLS" ]; then
    echo "  Got $TOOL_COUNT tools:"
    echo "$TOOLS_RESULT" | jq -r '.tools[].name' | sed 's/^/    /'
fi

# --- Resource discovery ---
bold "[3/4] Resource discovery"
RESOURCES_RESULT=$(npx -y @modelcontextprotocol/inspector --cli "$URL" --method resources/list --transport http 2>/dev/null)
RESOURCE_COUNT=$(echo "$RESOURCES_RESULT" | jq '.resources | length')
check "resources/list returns $EXPECTED_RESOURCES resources" [ "$RESOURCE_COUNT" -eq "$EXPECTED_RESOURCES" ]

# --- Read-only tool call (list_areas) ---
bold "[4/4] Live tool call (list_areas)"
AREAS_RESULT=$(npx -y @modelcontextprotocol/inspector --cli "$URL" --method tools/call --tool-name list_areas --transport http 2>/dev/null)
IS_ERROR=$(echo "$AREAS_RESULT" | jq '.isError')
check "list_areas executes without error" [ "$IS_ERROR" != "true" ]

CONTENT=$(echo "$AREAS_RESULT" | jq -r '.content[0].text // empty')
if [ -n "$CONTENT" ]; then
    AREA_COUNT=$(echo "$CONTENT" | jq 'length' 2>/dev/null || echo "0")
    check "list_areas returns areas (got $AREA_COUNT)" [ "$AREA_COUNT" -gt 0 ]
else
    red "  FAIL  list_areas returned empty content"
    FAIL=$((FAIL + 1))
fi

# --- Summary ---
echo ""
bold "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && green "All checks passed." || red "Some checks failed."
exit "$FAIL"
