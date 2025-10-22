@echo off
REM CascadeFlow Code Formatting Script (Windows)
REM Run this before every commit and definitely before launch!

echo.
echo 🎨 CascadeFlow - Code Formatting Script
echo ========================================
echo.

REM Check if virtual environment is activated
if not defined VIRTUAL_ENV (
    echo ⚠️  Virtual environment not activated!
    echo Please run: .venv\Scripts\activate
    exit /b 1
)

REM Check if we're in the right directory
if not exist pyproject.toml (
    echo ❌ Error: Not in project root directory
    echo Please run this script from the cascadeflow\ directory
    exit /b 1
)

echo ✅ Virtual environment: %VIRTUAL_ENV%
echo ✅ Working directory: %CD%
echo.

REM Install formatting tools if not present
echo 📦 Checking formatting tools...
pip install --quiet --upgrade black isort ruff mypy 2>nul || (
    echo Installing formatting tools...
    pip install black isort ruff mypy
)
echo ✅ Formatting tools ready
echo.

REM Step 1: Black - Code formatting
echo 🎨 Step 1/4: Running Black (code formatter)...
echo -------------------------------------------
black cascadeflow\ tests\ examples\ --line-length 100
if errorlevel 1 (
    echo ❌ Black formatting failed
    exit /b 1
)
echo ✅ Black formatting complete
echo.

REM Step 2: isort - Import sorting
echo 📦 Step 2/4: Running isort (import sorter)...
echo --------------------------------------------
isort cascadeflow\ tests\ examples\ --profile black --line-length 100
if errorlevel 1 (
    echo ❌ isort failed
    exit /b 1
)
echo ✅ Import sorting complete
echo.

REM Step 3: Ruff - Linting and auto-fix
echo 🔍 Step 3/4: Running Ruff (linter)...
echo ------------------------------------
echo Checking for issues...
ruff check cascadeflow\ tests\ examples\ --fix
if errorlevel 1 (
    echo ⚠️  Ruff found some issues
    echo Attempting to auto-fix...
    ruff check cascadeflow\ tests\ examples\ --fix --unsafe-fixes
    if errorlevel 1 (
        echo ❌ Some issues need manual fixing
        echo Review the output above and fix manually
        exit /b 1
    )
)
echo ✅ Linting complete
echo.

REM Step 4: mypy - Type checking (optional, won't fail)
echo 🔤 Step 4/4: Running mypy (type checker)...
echo -----------------------------------------
mypy cascadeflow\ --ignore-missing-imports --no-strict-optional
if errorlevel 1 (
    echo ⚠️  Type checking found some issues (non-critical)
    echo Consider fixing these before launch, but not required
)
echo ✅ Type checking complete
echo.

REM Final verification
echo 🧪 Running quick verification...
echo ------------------------------
python -m py_compile cascadeflow\*.py 2>nul
if errorlevel 1 (
    echo ❌ Syntax errors detected in cascadeflow\
    exit /b 1
)
echo ✅ Syntax verification passed
echo.

REM Summary
echo ======================================
echo ✨ Code Formatting Complete!
echo ======================================
echo.
echo Summary:
echo   ✅ Black formatting applied
echo   ✅ Imports sorted with isort
echo   ✅ Linting issues fixed with Ruff
echo   ✅ Type checking completed
echo   ✅ Syntax verification passed
echo.
echo Next steps:
echo   1. Review changes: git diff
echo   2. Run tests: pytest tests\ -v
echo   3. Commit: git add . ^&^& git commit -m "style: Format code with Black/isort/Ruff"
echo.
echo 🚀 Ready for launch!
pause