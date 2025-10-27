#!/bin/bash
# Helper script to run TypeScript examples with proper module resolution
#
# Usage: ./run-example.sh nodejs/basic-usage.ts

set -e

# Ensure we're in the core package directory
cd "$(dirname "$0")/.."

# Build if needed
if [ ! -d "dist" ]; then
    echo "📦 Building @cascadeflow/core..."
    pnpm build
fi

# Load environment variables
if [ -f "../../../.env" ]; then
    set -a
    source ../../../.env
    set +a
fi

# Run with tsx and use node_modules resolution
npx tsx --conditions=import "examples/$1"
