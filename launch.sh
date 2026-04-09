#!/usr/bin/env bash
#
# MCP-HASS Launch & Smoke Test
#
# Builds the Docker image (no cache), starts the container via compose,
# waits for readiness, then runs the smoke test suite.
#
# Usage: ./launch.sh
#
# Prerequisites:
#   - .env file configured (cp .env.example .env && edit)
#   - Docker running
#   - Node.js (for npx), jq, curl installed

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Read host port from .env if set, otherwise default to 3000
PORT=$(grep -s '^MCP_HOST_PORT=' "$PROJECT_DIR/.env" | cut -d= -f2 | tr -d ' "'"'" || echo "3000")
PORT="${PORT:-3000}"
URL="http://localhost:${PORT}/mcp"
CONTAINER="mcp-hass-local"

red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
bold()  { printf "\033[1m%s\033[0m\n" "$*"; }

cd "$PROJECT_DIR"

# --- Pre-flight ---
if [ ! -f .env ]; then
    red "No .env file found. Run: cp .env.example .env && edit"
    exit 1
fi

# --- Build ---
bold "[1/4] Building Docker image (no cache)..."
docker compose build --no-cache

# --- Start ---
bold "[2/4] Starting container..."
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d

# --- Readiness ---
bold "[3/4] Waiting for server readiness..."
for i in $(seq 1 30); do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null || echo "000")
    if [ "$STATUS" = "406" ] || [ "$STATUS" = "405" ] || [ "$STATUS" = "200" ]; then
        green "Server ready (HTTP $STATUS) after ${i}s"
        break
    fi
    if [ "$i" -eq 30 ]; then
        red "Server failed to start after 30s"
        bold "Container logs:"
        docker logs "$CONTAINER" 2>&1 | tail -20
        exit 1
    fi
    sleep 1
done

# --- Smoke test ---
bold "[4/4] Running smoke tests..."
echo ""
"$PROJECT_DIR/scripts/smoke-test.sh" "$URL"
