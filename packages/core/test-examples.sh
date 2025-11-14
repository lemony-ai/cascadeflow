#!/bin/bash
# Comprehensive example test runner
# Tests TypeScript examples with proper environment setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables from root .env
if [ -f "../../.env" ]; then
    echo "📋 Loading environment from ../../.env"
    set -a
    source ../../.env
    set +a
else
    echo "⚠️  Warning: ../../.env not found"
fi

# Track results
PASSED=0
FAILED=0
SKIPPED=0
declare -a FAILED_EXAMPLES

# Function to test an example
test_example() {
    local example=$1
    local timeout=${2:-60}

    echo ""
    echo "=========================================="
    echo "Testing: $example"
    echo "=========================================="

    if [ ! -f "examples/nodejs/$example" ]; then
        echo -e "${YELLOW}⏭️  SKIPPED${NC}: File not found"
        ((SKIPPED++))
        return
    fi

    # Run example (no timeout on macOS)
    if npx tsx "examples/nodejs/$example" > "/tmp/test-$example.log" 2>&1; then
        echo -e "${GREEN}✅ PASSED${NC}"
        ((PASSED++))
        # Show last 20 lines of output
        echo "--- Last 20 lines of output ---"
        tail -20 "/tmp/test-$example.log"
    else
        EXIT_CODE=$?
        echo -e "${RED}❌ FAILED${NC} (exit code: $EXIT_CODE)"
        ((FAILED++))
        FAILED_EXAMPLES+=("$example")
        # Show last 50 lines for debugging
        echo "--- Last 50 lines of output ---"
        tail -50 "/tmp/test-$example.log"
    fi
}

# Phase 1: Test remaining untested examples
echo "🚀 PHASE 1: Testing Remaining Examples"
echo "========================================"

test_example "cost-tracking.ts" 60
test_example "free-models-cascade.ts" 60
test_example "multi-instance-ollama.ts" 120
test_example "multi-instance-vllm.ts" 120
test_example "production-patterns.ts" 90
test_example "reasoning-models.ts" 120
test_example "semantic-quality.ts" 90
test_example "user-profiles-workflows.ts" 60
test_example "factory-methods.ts" 60

# Summary
echo ""
echo "=========================================="
echo "📊 TEST SUMMARY"
echo "=========================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo -e "${YELLOW}Skipped: $SKIPPED${NC}"
echo ""

if [ $FAILED -gt 0 ]; then
    echo "Failed examples:"
    for example in "${FAILED_EXAMPLES[@]}"; do
        echo "  ❌ $example"
    done
    echo ""
    echo "Logs available in /tmp/test-*.log"
    exit 1
else
    echo "✅ All tests passed!"
    exit 0
fi
