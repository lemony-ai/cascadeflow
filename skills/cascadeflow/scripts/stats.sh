#!/bin/bash
# Query CascadeFlow stats endpoint (raw JSON)
# Usage: stats.sh [host] [port]

HOST="${1:-192.168.0.147}"
PORT="${2:-8084}"

curl -s "http://${HOST}:${PORT}/stats" | jq '.'
