#!/bin/bash
# Detailed cost savings breakdown from CascadeFlow
# Usage: savings.sh [host] [port]

HOST="${1:-192.168.0.147}"
PORT="${2:-8084}"

STATS=$(curl -s "http://${HOST}:${PORT}/stats")

echo "$STATS" | jq -r '
.summary |
"💰 CascadeFlow Savings Report\n" +
"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n" +
"Total Queries: \(.total_queries // 0)\n" +
"Draft Acceptance: \(.acceptance_rate // 0 | floor)%\n\n" +
"💵 Cost Comparison:\n" +
"  Baseline (verifier-only): $\(.baseline_cost // 0 | . * 10000 | floor / 10000)\n" +
"  With Cascade:             $\(.total_cost // 0 | . * 10000 | floor / 10000)\n" +
"  ━━━━━━━━━━━━━━━━━━━━━━━\n" +
"  Savings:                  $\(.total_saved // 0 | . * 10000 | floor / 10000) (\(.savings_percent // 0 | floor)%)\n\n" +
"📊 By Complexity:\n" +
"  Trivial:  \(.by_complexity.trivial // 0) queries\n" +
"  Simple:   \(.by_complexity.simple // 0) queries\n" +
"  Moderate: \(.by_complexity.moderate // 0) queries\n" +
"  Hard:     \(.by_complexity.hard // 0) queries\n\n" +
"⏱️ Timing (avg):\n" +
"  Draft generation:    \(.timing_stats.avg_draft_generation_ms // 0 | floor)ms\n" +
"  Quality verification: \(.timing_stats.avg_quality_verification_ms // 0 | floor)ms\n" +
"  Verifier generation: \(.timing_stats.avg_verifier_generation_ms // 0 | floor)ms"
'
