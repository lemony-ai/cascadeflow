#!/bin/bash
# Comprehensive Example Test Runner
# Tests ALL TypeScript examples including Phase 2

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment
if [ -f "../../.env" ]; then
    echo "📋 Loading environment from ../../.env"
    set -a
    source ../../.env
    set +a
fi

# Track results
PASSED=0
FAILED=0
SKIPPED=0
declare -a FAILED_EXAMPLES
declare -a PASSED_EXAMPLES

# Test function
test_example() {
    local example=$1
    local desc=$2

    echo ""
    echo "=========================================="
    echo "Testing: $example"
    echo "Description: $desc"
    echo "=========================================="

    if [ ! -f "examples/nodejs/$example" ]; then
        echo -e "${YELLOW}⏭️  SKIPPED${NC}: File not found"
        ((SKIPPED++))
        return
    fi

    if npx tsx "examples/nodejs/$example" > "/tmp/test-$example.log" 2>&1; then
        echo -e "${GREEN}✅ PASSED${NC}"
        ((PASSED++))
        PASSED_EXAMPLES+=("$example")
        tail -10 "/tmp/test-$example.log"
    else
        EXIT_CODE=$?
        echo -e "${RED}❌ FAILED${NC} (exit code: $EXIT_CODE)"
        ((FAILED++))
        FAILED_EXAMPLES+=("$example")
        tail -30 "/tmp/test-$example.log"
    fi
}

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         cascadeflow - All Examples Test Suite                ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Phase 1 examples (existing)
echo -e "${BLUE}━━━ PHASE 1: Existing Examples ━━━${NC}"

test_example "basic-usage.ts" "Basic cascade usage"
test_example "cost-tracking.ts" "Cost tracking & analytics"
test_example "production-patterns.ts" "Production deployment patterns"
test_example "semantic-quality.ts" "Semantic quality validation"
test_example "user-profiles-workflows.ts" "User profiles & workflows"
test_example "factory-methods.ts" "Factory method patterns"
test_example "multi-provider.ts" "Multi-provider setup"
test_example "quality-profiles.ts" "Quality profiles"
test_example "tool-calling.ts" "Tool calling support"
test_example "reasoning-models.ts" "Reasoning models (o3, Claude)"

# Phase 2 examples (newly created)
echo ""
echo -e "${BLUE}━━━ PHASE 2: Newly Created Examples ━━━${NC}"

test_example "rate-limiting-usage.ts" "Rate limiting by tier"
test_example "custom-validation.ts" "Custom validators"
test_example "streaming-text.ts" "Text streaming (SSE)"

# Express integration (special case - just test startup)
echo ""
echo "=========================================="
echo "Testing: express-integration.ts"
echo "Description: Express REST API"
echo "=========================================="

if npx tsx examples/nodejs/express-integration.ts > /tmp/test-express.log 2>&1 &
SERVER_PID=$!
sleep 5
kill $SERVER_PID 2>/dev/null || true
if grep -q "Server running" /tmp/test-express.log; then
    echo -e "${GREEN}✅ PASSED${NC}: Server started successfully"
    ((PASSED++))
    PASSED_EXAMPLES+=("express-integration.ts")
else
    echo -e "${RED}❌ FAILED${NC}: Server did not start"
    ((FAILED++))
    FAILED_EXAMPLES+=("express-integration.ts")
fi
cat /tmp/test-express.log
fi

# Summary
echo ""
echo "=========================================="
echo "📊 TEST SUMMARY"
echo "=========================================="
echo -e "${GREEN}Passed:  $PASSED${NC}"
echo -e "${RED}Failed:  $FAILED${NC}"
echo -e "${YELLOW}Skipped: $SKIPPED${NC}"
echo ""

if [ ${#PASSED_EXAMPLES[@]} -gt 0 ]; then
    echo "Passed examples:"
    for example in "${PASSED_EXAMPLES[@]}"; do
        echo -e "  ${GREEN}✓${NC} $example"
    done
    echo ""
fi

if [ ${#FAILED_EXAMPLES[@]} -gt 0 ]; then
    echo "Failed examples:"
    for example in "${FAILED_EXAMPLES[@]}"; do
        echo -e "  ${RED}✗${NC} $example"
    done
    echo ""
    echo "Logs available in /tmp/test-*.log"
    exit 1
else
    echo "✅ All testable examples passed!"
    exit 0
fi
