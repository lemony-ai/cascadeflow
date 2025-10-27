#!/bin/bash
# Test TypeScript examples

cd packages/core/examples || exit 1

# Load env vars
set -a
source ../../../.env 2>/dev/null || true
set +a

PASSED=0
FAILED=0

for example in nodejs/*.ts streaming.ts; do
    [ -f "$example" ] || continue
    echo "Testing: $example"
    if npx tsx "$example" > /dev/null 2>&1; then
        echo "✅ PASSED"
        ((PASSED++))
    else
        echo "❌ FAILED"
        ((FAILED++))
    fi
done

echo ""
echo "Passed: $PASSED, Failed: $FAILED"
exit $FAILED
