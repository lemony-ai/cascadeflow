#!/bin/bash
# Quick Performance Test - 3 runs for cost efficiency
# Simplified version for faster analysis

set -e

RUNS=3
OUTPUT_DIR="/tmp/cascadeflow-quickperf-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║   cascadeflow Quick Performance Test (3 runs)                ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Load environment
if [ -f "../../.env" ]; then
    set -a
    source ../../.env
    set +a
fi

declare -a savings_array
declare -a cost_array

for i in {1..3}; do
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Run $i/3"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    OUTPUT_FILE="$OUTPUT_DIR/run-$i.log"

    if npx tsx examples/nodejs/basic-usage.ts > "$OUTPUT_FILE" 2>&1; then
        echo "✓ Run $i completed"

        # Extract savings percentage
        savings=$(grep "💰 SAVINGS:" "$OUTPUT_FILE" | awk '{print $3}' | sed 's/[($%)]//g' || echo "0")
        cost=$(grep "Total Cost:" "$OUTPUT_FILE" | awk '{print $3}' | sed 's/\$//g' || echo "0")

        savings_array+=("$savings")
        cost_array+=("$cost")

        echo "  Savings: ${savings}%"
        echo "  Cost: \$${cost}"
    else
        echo "✗ Run $i failed"
    fi

    # Delay between runs
    if [ $i -lt 3 ]; then
        sleep 3
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 RESULTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Calculate average
sum=0
count=0
for val in "${savings_array[@]}"; do
    if [ -n "$val" ]; then
        sum=$(echo "$sum + $val" | bc)
        count=$((count + 1))
    fi
done

if [ $count -gt 0 ]; then
    avg=$(echo "scale=2; $sum / $count" | bc)
else
    avg="0"
fi

echo ""
echo "Average Savings: ${avg}%"
echo "Target: 40-60%"
if (( $(echo "$avg >= 40" | bc -l) )); then
    echo "Status: ✓ Target achieved!"
else
    echo "Status: ⚠ Below target"
fi

echo ""
echo "Individual runs:"
for i in {1..3}; do
    if [ -n "${savings_array[$i-1]}" ]; then
        echo "  Run $i: ${savings_array[$i-1]}% (Cost: \$${cost_array[$i-1]})"
    fi
done

echo ""
echo "Logs: $OUTPUT_DIR"
echo ""
