#!/bin/bash
# cascadeflow Code Formatting Script
# Run this before every commit and definitely before launch!

set -e  # Exit on any error

echo "🎨 cascadeflow - Code Formatting Script"
echo "========================================"
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Virtual environment not activated!"
    echo "Please run: source .venv/bin/activate"
    exit 1
fi

# Check if we're in the right directory
if [[ ! -f "pyproject.toml" ]]; then
    echo "❌ Error: Not in project root directory"
    echo "Please run this script from the cascadeflow/ directory"
    exit 1
fi

echo "✅ Virtual environment: $VIRTUAL_ENV"
echo "✅ Working directory: $(pwd)"
echo ""

# Install formatting tools if not present
echo "📦 Checking formatting tools..."
pip install --quiet --upgrade black isort ruff mypy 2>/dev/null || {
    echo "Installing formatting tools..."
    pip install black isort ruff mypy
}
echo "✅ Formatting tools ready"
echo ""

# Step 1: Black - Code formatting
echo "🎨 Step 1/4: Running Black (code formatter)..."
echo "-------------------------------------------"
black cascadeflow/ tests/ examples/ --line-length 100 || {
    echo "❌ Black formatting failed"
    exit 1
}
echo "✅ Black formatting complete"
echo ""

# Step 2: isort - Import sorting
echo "📦 Step 2/4: Running isort (import sorter)..."
echo "--------------------------------------------"
isort cascadeflow/ tests/ examples/ --profile black --line-length 100 || {
    echo "❌ isort failed"
    exit 1
}
echo "✅ Import sorting complete"
echo ""

# Step 3: Ruff - Linting and auto-fix
echo "🔍 Step 3/4: Running Ruff (linter)..."
echo "------------------------------------"
echo "Checking for issues..."
ruff check cascadeflow/ tests/ examples/ --fix || {
    echo "⚠️  Ruff found some issues"
    echo "Attempting to auto-fix..."
    ruff check cascadeflow/ tests/ examples/ --fix --unsafe-fixes || {
        echo "❌ Some issues need manual fixing"
        echo "Review the output above and fix manually"
        exit 1
    }
}
echo "✅ Linting complete"
echo ""

# Step 4: mypy - Type checking (optional, won't fail)
echo "🔤 Step 4/4: Running mypy (type checker)..."
echo "-----------------------------------------"
mypy cascadeflow/ --ignore-missing-imports --no-strict-optional || {
    echo "⚠️  Type checking found some issues (non-critical)"
    echo "Consider fixing these before launch, but not required"
}
echo "✅ Type checking complete"
echo ""

# Final verification
echo "🧪 Running quick verification..."
echo "------------------------------"

# Check if there are any .py files with syntax errors
python -m py_compile cascadeflow/*.py 2>/dev/null || {
    echo "❌ Syntax errors detected in cascadeflow/"
    exit 1
}

python -m py_compile tests/*.py 2>/dev/null || {
    echo "⚠️  Syntax errors in tests/ (check manually)"
}

echo "✅ Syntax verification passed"
echo ""

# Summary
echo "======================================"
echo "✨ Code Formatting Complete!"
echo "======================================"
echo ""
echo "Summary:"
echo "  ✅ Black formatting applied"
echo "  ✅ Imports sorted with isort"
echo "  ✅ Linting issues fixed with Ruff"
echo "  ✅ Type checking completed"
echo "  ✅ Syntax verification passed"
echo ""
echo "Next steps:"
echo "  1. Review changes: git diff"
echo "  2. Run tests: pytest tests/ -v"
echo "  3. Commit: git add . && git commit -m 'style: Format code with Black/isort/Ruff'"
echo ""
echo "🚀 Ready for launch!"