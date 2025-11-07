#!/bin/bash

# Script to deprecate incorrect 5.0.3 versions of @cascadeflow TypeScript packages
# Run this AFTER publishing v0.5.0 to npm

echo "Deprecating @cascadeflow/core and @cascadeflow/ml version 5.0.3..."
echo ""
echo "⚠️  Make sure you are authenticated to npm with the correct account"
echo "⚠️  Run: npm whoami"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Deprecate @cascadeflow/core
echo ""
echo "Deprecating @cascadeflow/core@5.0.3..."
npm deprecate @cascadeflow/core@5.0.3 "Version numbering error. Please upgrade to v0.5.0 or later: npm install @cascadeflow/core@latest"

# Deprecate @cascadeflow/ml
echo ""
echo "Deprecating @cascadeflow/ml@5.0.3..."
npm deprecate @cascadeflow/ml@5.0.3 "Version numbering error. Please upgrade to v0.5.0 or later: npm install @cascadeflow/ml@latest"

echo ""
echo "✅ All 5.0.3 versions deprecated successfully!"
echo ""
echo "Users will see deprecation warnings when installing these versions."
echo "npm will recommend v0.5.0 as the latest stable version."
