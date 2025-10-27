#!/bin/bash
# Test all Python examples systematically

set -a
source .env
set +a

echo "=================================="
echo "Testing Python Examples"
echo "=================================="

# Examples to test (excluding validate_examples.py, vllm, fastapi, edge_device)
EXAMPLES=(
    "basic_usage.py"
    "preset_usage.py"
    "multi_provider.py"
    "cost_tracking.py"
    "tool_execution.py"
    "production_patterns.py"
    "custom_cascade.py"
    "custom_validation.py"
)

PASSED=0
FAILED=0
SKIPPED=0

for example in "${EXAMPLES[@]}"; do
    echo ""
    echo "Testing: $example"
    echo "----------------------------------"

    if python3 "examples/$example" > /dev/null 2>&1; then
        echo "✅ PASSED: $example"
        ((PASSED++))
    else
        EXIT_CODE=$?
        echo "❌ FAILED: $example (exit code: $EXIT_CODE)"
        # Show last 20 lines of error
        python3 "examples/$example" 2>&1 | tail -20
        ((FAILED++))
    fi
done

echo ""
echo "=================================="
echo "Summary:"
echo "  ✅ Passed: $PASSED"
echo "  ❌ Failed: $FAILED"
echo "  ⏭️  Skipped: $SKIPPED"
echo "=================================="
