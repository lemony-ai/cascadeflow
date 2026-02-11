#!/bin/bash
# Query CascadeFlow stats endpoint (raw JSON)
# Usage: stats.sh [host] [port]
# Environment: CASCADEFLOW_HOST, CASCADEFLOW_PORT

HOST="${1:-${CASCADEFLOW_HOST:-localhost}}"
PORT="${2:-${CASCADEFLOW_PORT:-8084}}"

curl -s "http://${HOST}:${PORT}/stats" | jq '.'
