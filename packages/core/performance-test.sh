#!/bin/bash
# Performance Testing Script
# Runs basic-usage.ts multiple times and collects metrics

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RUNS=${1:-10}
OUTPUT_DIR="/tmp/cascadeflow-perf-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   cascadeflow Performance Testing                             ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Running $RUNS iterations of basic-usage.ts..."
echo "Output directory: $OUTPUT_DIR"
echo ""

# Check for API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}❌ OPENAI_API_KEY not set${NC}"
    echo "Load from .env or set manually:"
    echo "  export OPENAI_API_KEY='sk-...'"
    exit 1
fi

# Load environment if .env exists
if [ -f "../../.env" ]; then
    echo -e "${GREEN}📋 Loading environment from ../../.env${NC}"
    set -a
    source ../../.env
    set +a
fi

# Arrays to store metrics
declare -a savings_array
declare -a total_cost_array
declare -a cascade_rate_array
declare -a direct_rate_array
declare -a cheap_model_rate_array

echo -e "\n${YELLOW}Starting test runs...${NC}\n"

# Run tests
for i in $(seq 1 $RUNS); do
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Run $i/$RUNS${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Run the example and capture output
    OUTPUT_FILE="$OUTPUT_DIR/run-$i.log"

    if npx tsx examples/nodejs/basic-usage.ts > "$OUTPUT_FILE" 2>&1; then
        echo -e "${GREEN}✓ Run $i completed${NC}"

        # Extract metrics using grep and awk
        savings=$(grep "💰 SAVINGS:" "$OUTPUT_FILE" | awk '{print $3}' | sed 's/[($%)]//g' || echo "0")
        total_cost=$(grep "Total Cost:" "$OUTPUT_FILE" | awk '{print $3}' | sed 's/\$//g' || echo "0")

        # Extract model usage percentages
        cheap_pct=$(grep "GPT-4o-mini:" "$OUTPUT_FILE" | head -1 | awk '{print $2}' | sed 's/[(%)]//g' || echo "0")

        # Count routing types from the output
        direct_count=$(grep -c "Direct Route:" "$OUTPUT_FILE" || echo "0")
        total_queries=8  # We know basic-usage.ts has 8 queries
        direct_pct=$(echo "scale=1; $direct_count * 100 / $total_queries" | bc)

        # Store metrics
        savings_array+=("$savings")
        total_cost_array+=("$total_cost")
        cheap_model_rate_array+=("$cheap_pct")
        direct_rate_array+=("$direct_pct")

        echo "  Savings: ${savings}%"
        echo "  Cost: \$${total_cost}"
        echo "  Cheap model: ${cheap_pct}%"
        echo "  Direct route: ${direct_pct}%"
    else
        echo -e "${RED}✗ Run $i failed${NC}"
        echo "  See: $OUTPUT_FILE"
    fi

    echo ""

    # Small delay to avoid rate limiting
    if [ $i -lt $RUNS ]; then
        sleep 2
    fi
done

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}All runs completed!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# Calculate statistics
echo -e "${YELLOW}📊 PERFORMANCE STATISTICS${NC}\n"

# Function to calculate average
calc_avg() {
    local arr=("$@")
    local sum=0
    local count=0

    for val in "${arr[@]}"; do
        if [ -n "$val" ] && [ "$val" != "0" ]; then
            sum=$(echo "$sum + $val" | bc)
            count=$((count + 1))
        fi
    done

    if [ $count -gt 0 ]; then
        echo "scale=2; $sum / $count" | bc
    else
        echo "0"
    fi
}

# Calculate averages
avg_savings=$(calc_avg "${savings_array[@]}")
avg_cost=$(calc_avg "${total_cost_array[@]}")
avg_cheap=$(calc_avg "${cheap_model_rate_array[@]}")
avg_direct=$(calc_avg "${direct_rate_array[@]}")

echo "Cost Savings:"
echo "  Average: ${avg_savings}%"
echo "  Target: 40-60%"
if (( $(echo "$avg_savings >= 40" | bc -l) )); then
    echo -e "  Status: ${GREEN}✓ Target achieved!${NC}"
elif (( $(echo "$avg_savings >= 20" | bc -l) )); then
    echo -e "  Status: ${YELLOW}⚠ Below target but improving${NC}"
else
    echo -e "  Status: ${RED}✗ Needs improvement${NC}"
fi

echo ""
echo "Average Cost per Run: \$${avg_cost}"
echo ""
echo "Routing Efficiency:"
echo "  Cheap model (GPT-4o-mini): ${avg_cheap}%"
echo "  Direct routing rate: ${avg_direct}%"
echo "  Target direct routing: 30-40%"

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "Detailed logs: $OUTPUT_DIR"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# Generate summary report
SUMMARY_FILE="$OUTPUT_DIR/summary.txt"
cat > "$SUMMARY_FILE" << EOF
cascadeflow Performance Test Summary
=====================================
Date: $(date)
Runs: $RUNS

METRICS
-------
Average Savings: ${avg_savings}%
Average Cost: \$${avg_cost}
Cheap Model Usage: ${avg_cheap}%
Direct Routing: ${avg_direct}%

TARGET COMPARISON
-----------------
Savings Target: 40-60%
Actual: ${avg_savings}%

INDIVIDUAL RUNS
---------------
EOF

for i in $(seq 1 $RUNS); do
    if [ -n "${savings_array[$i-1]}" ]; then
        echo "Run $i: ${savings_array[$i-1]}% savings, \$${total_cost_array[$i-1]} cost" >> "$SUMMARY_FILE"
    fi
done

echo ""
echo "Summary saved to: $SUMMARY_FILE"
echo ""
