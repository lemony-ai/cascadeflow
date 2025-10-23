#!/bin/bash
# Initial Release Cleanup Script for CascadeFlow v0.1.2
# Removes temporary test files and organizes test directory

set -e

echo "🧹 CascadeFlow Initial Release Cleanup"
echo "======================================="
echo ""

# Safety check
read -p "This will archive dev tests and remove temp test files. Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Starting cleanup..."
echo ""

# =============================================================================
# 1. Remove TypeScript development test files
# =============================================================================
echo "📁 Removing TypeScript development test files..."
find packages/core -maxdepth 1 -name "test-*.ts" -type f -delete 2>/dev/null || true
find packages/core -maxdepth 1 -name "test-*.js" -type f -delete 2>/dev/null || true
echo "   ✅ TypeScript test files removed"

# =============================================================================
# 2. Remove root-level Python test files
# =============================================================================
echo "📁 Removing root-level Python test files..."
rm -f test_*.py
echo "   ✅ Root test files removed"

# =============================================================================
# 3. Archive development tests in tests/ directory
# =============================================================================
echo "📁 Archiving development tests in tests/ directory..."

# Create archive subdirectories
mkdir -p tests/_archive_development_tests/_comprehensive_validation
mkdir -p tests/_archive_development_tests/_logprobs_validation
mkdir -p tests/_archive_development_tests/_version_specific
mkdir -p tests/_archive_development_tests/_mvp_tests
mkdir -p tests/_archive_development_tests/_feature_validation
mkdir -p tests/_archive_development_tests/_experimental

# Move comprehensive validation tests
mv tests/test_agent_comprehensive.py tests/_archive_development_tests/_comprehensive_validation/ 2>/dev/null || true
mv tests/test_comprehensive.py tests/_archive_development_tests/_comprehensive_validation/ 2>/dev/null || true
mv tests/test_quality_system_full.py tests/_archive_development_tests/_comprehensive_validation/ 2>/dev/null || true
mv tests/test_full_cascade_integration.py tests/_archive_development_tests/_comprehensive_validation/ 2>/dev/null || true
mv tests/test_tool_calling_comprehensive.py tests/_archive_development_tests/_comprehensive_validation/ 2>/dev/null || true
mv tests/test_tools_system.py tests/_archive_development_tests/_comprehensive_validation/ 2>/dev/null || true

# Move logprobs validation tests
mv tests/test_anthropic_logprobs.py tests/_archive_development_tests/_logprobs_validation/ 2>/dev/null || true
mv tests/test_groq_logprobs.py tests/_archive_development_tests/_logprobs_validation/ 2>/dev/null || true
mv tests/test_huggingface_logprobs.py tests/_archive_development_tests/_logprobs_validation/ 2>/dev/null || true
mv tests/test_ollama_logprobs.py tests/_archive_development_tests/_logprobs_validation/ 2>/dev/null || true
mv tests/test_openai_logprobs.py tests/_archive_development_tests/_logprobs_validation/ 2>/dev/null || true
mv tests/test_together_logprobs.py tests/_archive_development_tests/_logprobs_validation/ 2>/dev/null || true
mv tests/test_cascade_logprobs_integration.py tests/_archive_development_tests/_logprobs_validation/ 2>/dev/null || true

# Move version-specific tests
mv tests/test_agent_v2_extended.py tests/_archive_development_tests/_version_specific/ 2>/dev/null || true
mv tests/test_agent_v2_streaming.py tests/_archive_development_tests/_version_specific/ 2>/dev/null || true

# Move MVP tests
mv tests/test_mvp_cascade_direct.py tests/_archive_development_tests/_mvp_tests/ 2>/dev/null || true
mv tests/test_cascadeflow.py tests/_archive_development_tests/_mvp_tests/ 2>/dev/null || true

# Move feature validation tests
mv tests/test_confidence_integration.py tests/_archive_development_tests/_feature_validation/ 2>/dev/null || true
mv tests/test_provider_confidence_raw.py tests/_archive_development_tests/_feature_validation/ 2>/dev/null || true
mv tests/test_text_cascade_only.py tests/_archive_development_tests/_feature_validation/ 2>/dev/null || true
mv tests/test_merged_config.py tests/_archive_development_tests/_feature_validation/ 2>/dev/null || true

# Move experimental tests
mv tests/test_specualtives_full_impl.py tests/_archive_development_tests/_experimental/ 2>/dev/null || true
mv tests/test_retry_logic.py tests/_archive_development_tests/_experimental/ 2>/dev/null || true

echo "   ✅ Development tests archived"

# =============================================================================
# 4. Clean build artifacts
# =============================================================================
echo "📁 Cleaning build artifacts..."
rm -rf build/
rm -rf dist/
rm -rf *.egg-info/
rm -rf cascadeflow.egg-info/
rm -rf packages/*/dist/
echo "   ✅ Build artifacts cleaned"

# =============================================================================
# 5. Clean pytest cache
# =============================================================================
echo "📁 Cleaning pytest cache..."
rm -rf .pytest_cache/
rm -f .coverage
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo "   ✅ Pytest cache cleaned"

# =============================================================================
# 6. Clean macOS files
# =============================================================================
echo "📁 Cleaning macOS files..."
find . -name ".DS_Store" -delete 2>/dev/null || true
echo "   ✅ macOS files cleaned"

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Summary of changes:"
echo "  ✅ TypeScript test files removed (test-*.ts)"
echo "  ✅ Root Python test files removed (test_*.py)"
echo "  ✅ Development tests archived to tests/_archive_development_tests/"
echo "  ✅ Build artifacts cleaned"
echo "  ✅ Cache files cleaned"
echo ""
echo "Files kept (but will be gitignored):"
echo "  📝 CLAUDE.md - Assistant conversation notes"
echo "  📝 *_ARCHITECTURE.md - Architecture documentation"
echo "  📝 *_ROADMAP.md - Planning documents"
echo "  📂 .analysis/ - Analysis reports"
echo ""
echo "Active tests remaining in tests/:"
echo "  • Core: test_agent.py, test_config.py, test_execution.py, etc."
echo "  • Providers: test_openai.py, test_anthropic.py, etc."
echo "  • Features: test_streaming.py, test_tool_calling.py, etc."
echo ""
echo "Next steps:"
echo "  1. Review changes: git status"
echo "  2. Test remaining suite: pytest tests/ -v"
echo "  3. Build packages: pnpm build && python -m build"
echo "  4. Commit: git add -A && git commit -m 'chore: cleanup for v0.1.2 release'"
echo "  5. Publish!"
echo ""
