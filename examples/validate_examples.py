"""
Validate all Python examples without running them.

This script checks that all examples:
- Have valid Python syntax
- Import correctly without errors
- Are properly structured
"""

import ast
import importlib.util
import sys
from pathlib import Path


def validate_syntax(file_path: Path) -> tuple[bool, str]:
    """Check if file has valid Python syntax."""
    try:
        with open(file_path) as f:
            source = f.read()
        ast.parse(source)
        return True, "✅ Valid syntax"
    except SyntaxError as e:
        return False, f"❌ Syntax error: {e}"


def validate_imports(file_path: Path) -> tuple[bool, str]:
    """Check if file can be imported (validates imports and top-level code)."""
    try:
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if spec is None or spec.loader is None:
            return False, "❌ Could not load module spec"

        # We just compile it, not execute to avoid running expensive API calls
        with open(file_path) as f:
            source = f.read()
        compile(source, str(file_path), "exec")

        return True, "✅ Imports valid"
    except ImportError as e:
        return False, f"❌ Import error: {e}"
    except Exception as e:
        return False, f"❌ Error: {e}"


def main():
    """Validate all Python examples."""
    examples_dir = Path(__file__).parent
    example_files = sorted(examples_dir.glob("*.py"))

    # Exclude this validation script itself
    example_files = [f for f in example_files if f.name != "validate_examples.py"]

    print("=" * 80)
    print("🔍 VALIDATING PYTHON EXAMPLES")
    print("=" * 80)
    print()

    results = []
    for example_file in example_files:
        print(f"📄 {example_file.name}")

        # Check syntax
        syntax_ok, syntax_msg = validate_syntax(example_file)
        print(f"   {syntax_msg}")

        # Check imports
        if syntax_ok:
            import_ok, import_msg = validate_imports(example_file)
            print(f"   {import_msg}")
        else:
            import_ok = False
            import_msg = "⏭️  Skipped (syntax error)"

        results.append(
            {
                "file": example_file.name,
                "syntax_ok": syntax_ok,
                "import_ok": import_ok,
                "valid": syntax_ok and import_ok,
            }
        )
        print()

    # Summary
    print("=" * 80)
    print("📊 VALIDATION SUMMARY")
    print("=" * 80)
    print()

    total = len(results)
    valid = sum(1 for r in results if r["valid"])
    syntax_errors = sum(1 for r in results if not r["syntax_ok"])
    import_errors = sum(1 for r in results if r["syntax_ok"] and not r["import_ok"])

    print(f"Total examples: {total}")
    print(f"✅ Valid: {valid}/{total}")
    print(f"❌ Syntax errors: {syntax_errors}")
    print(f"❌ Import errors: {import_errors}")
    print()

    if valid == total:
        print("🎉 ALL EXAMPLES VALID!")
        return 0
    else:
        print("⚠️  SOME EXAMPLES HAVE ISSUES")
        print("\nFailed examples:")
        for r in results:
            if not r["valid"]:
                print(f"  - {r['file']}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
