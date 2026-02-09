#!/bin/bash
# CascadeFlow health check
# Usage: health.sh [host] [port]

HOST="${1:-192.168.0.147}"
PORT="${2:-8084}"

HEALTH=$(curl -s --connect-timeout 3 "http://${HOST}:${PORT}/health" 2>/dev/null)

if [ -z "$HEALTH" ]; then
  echo "❌ CascadeFlow OFFLINE (http://${HOST}:${PORT})"
  exit 1
fi

STATUS=$(echo "$HEALTH" | jq -r '.status // "unknown"')

if [ "$STATUS" = "ok" ]; then
  echo "✅ CascadeFlow OK (http://${HOST}:${PORT})"
  exit 0
else
  echo "⚠️ CascadeFlow status: $STATUS"
  exit 1
fi
