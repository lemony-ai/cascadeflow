#!/bin/bash
# Generate formatted summary from CascadeFlow stats
# Usage: summary.sh [host] [port]
# Environment: CASCADEFLOW_HOST, CASCADEFLOW_PORT

HOST="${1:-${CASCADEFLOW_HOST:-localhost}}"
PORT="${2:-${CASCADEFLOW_PORT:-8084}}"

STATS=$(curl -s "http://${HOST}:${PORT}/stats")

echo "$STATS" | jq -r '
.summary |
"📊 CascadeFlow Stats\n" +
"━━━━━━━━━━━━━━━━━━━━━━━\n" +
"📈 Queries: \(.total_queries // 0) total\n" +
"✅ Draft Accepted: \(.draft_accepted // 0)/\(.cascade_used // 0) (\(.acceptance_rate // 0 | floor)%)\n" +
"🔀 Cascade Used: \(.cascade_used // 0) (\(.cascade_rate // 0 | floor)%)\n" +
"💰 Total Saved: $\(.total_saved // 0 | . * 1000 | floor / 1000)\n" +
"📉 Savings: \(.savings_percent // 0 | floor)%\n" +
"🎯 Quality Mean: \(.quality_stats.mean // 0 | . * 100 | floor / 100)"
'
