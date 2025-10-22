#!/usr/bin/env python3
"""
Validate that requirements.txt and requirements-dev.txt match actual imports.

Run this to check if dependencies are correct:
    python validate_dependencies.py
"""

import re
from pathlib import Path

# Map import names to package names
IMPORT_TO_PACKAGE = {
    "pydantic": "pydantic",
    "httpx": "httpx",
    "tiktoken": "tiktoken",
    "openai": "openai",
    "anthropic": "anthropic",
    "groq": "groq",
    "huggingface_hub": "huggingface-hub",
    "together": "together",
    "vllm": "vllm",
    "pytest": "pytest",
    "rich": "rich",
    "sentence_transformers": "sentence-transformers",
}


def find_imports(file_path: Path) -> set[str]:
    """Extract all imports from a Python file."""
    imports = set()

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Find "import X" statements
        imports.update(re.findall(r"^\s*import\s+(\w+)", content, re.MULTILINE))

        # Find "from X import" statements
        imports.update(re.findall(r"^\s*from\s+(\w+)", content, re.MULTILINE))

    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")

    return imports


def scan_directory(directory: Path) -> dict[str, set[str]]:
    """Scan directory for all Python imports."""
    all_imports = {}

    for py_file in directory.rglob("*.py"):
        # Skip __pycache__ and .venv
        if "__pycache__" in str(py_file) or ".venv" in str(py_file):
            continue

        imports = find_imports(py_file)
        if imports:
            # Convert to relative path for display
            rel_path = py_file.relative_to(directory.parent)
            all_imports[str(rel_path)] = imports

    return all_imports


def parse_requirements(req_file: Path) -> set[str]:
    """Parse requirements.txt and extract package names."""
    packages = set()

    if not req_file.exists():
        return packages

    with open(req_file) as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Skip -r includes
            if line.startswith("-r"):
                continue

            # Extract package name (before >=, ==, etc.)
            package = re.split(r"[><=!]", line)[0].strip()
            packages.add(package)

    return packages


def main():
    """Validate dependencies."""
    print("=" * 80)
    print("CASCADEFLOW DEPENDENCY VALIDATION")
    print("=" * 80)
    print()

    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir if (script_dir / "cascadeflow").exists() else script_dir.parent

    # Scan for imports
    print("📦 Scanning cascadeflow/ for imports...")
    cascadeflow_dir = project_root / "cascadeflow"
    imports_by_file = scan_directory(cascadeflow_dir)

    # Collect all unique imports
    all_imports = set()
    for imports in imports_by_file.values():
        all_imports.update(imports)

    # Filter to known packages
    used_packages = set()
    for imp in all_imports:
        if imp in IMPORT_TO_PACKAGE:
            used_packages.add(IMPORT_TO_PACKAGE[imp])

    print(f"✅ Found {len(used_packages)} package imports in code")
    print()

    # Parse requirements files
    req_file = project_root / "requirements.txt"
    req_dev_file = project_root / "requirements-dev.txt"

    req_packages = parse_requirements(req_file)
    req_dev_packages = parse_requirements(req_dev_file)

    print(f"📄 requirements.txt: {len(req_packages)} packages")
    print(f"📄 requirements-dev.txt: {len(req_dev_packages)} packages (excluding -r)")
    print()

    # Categorize packages
    core_packages = {"pydantic", "httpx", "tiktoken"}
    provider_packages = {"openai", "anthropic", "groq", "huggingface-hub", "together", "vllm"}
    dev_packages = {"pytest", "black", "ruff", "mypy", "isort", "pre-commit", "rich"}
    future_packages = {"sentence-transformers"}  # Not yet implemented

    # Validate core
    print("🔍 VALIDATION RESULTS")
    print("=" * 80)
    print()

    print("1. Core Dependencies (must be in requirements.txt):")
    for pkg in sorted(core_packages):
        in_code = pkg in used_packages
        in_req = pkg in req_packages
        status = "✅" if (in_code and in_req) else "⚠️"
        print(f"   {status} {pkg:20} - In code: {in_code:5}, In requirements.txt: {in_req}")
    print()

    print("2. Provider SDKs (should be optional, in pyproject.toml extras):")
    for pkg in sorted(provider_packages):
        in_code = pkg in used_packages
        in_req = pkg in req_packages
        in_dev = pkg in req_dev_packages

        # Providers should be in requirements-dev.txt for testing, but NOT in requirements.txt
        if in_code:
            status = "✅" if (not in_req and in_dev) else "⚠️"
            location = "requirements-dev.txt only" if not in_req else "WRONG: in requirements.txt"
            print(f"   {status} {pkg:20} - Used in code, {location}")
    print()

    print("3. Development Tools (should be in requirements-dev.txt only):")
    for pkg in sorted(dev_packages):
        in_code = pkg in used_packages
        in_dev = pkg in req_dev_packages
        in_req = pkg in req_packages

        if pkg == "rich":  # Rich might be used in code
            status = "✅" if in_dev else "⚠️"
        else:  # Other dev tools shouldn't be in production code
            status = "✅" if (not in_code and in_dev and not in_req) else "⚠️"

        print(f"   {status} {pkg:20} - In dev requirements: {in_dev}")
    print()

    print("4. Future Features (not yet implemented - should NOT be in requirements):")
    for pkg in sorted(future_packages):
        in_code = pkg in used_packages
        in_req = pkg in req_packages or pkg in req_dev_packages
        status = "✅" if not in_code and not in_req else "⚠️"
        note = "Correctly excluded" if status == "✅" else "WARNING: Present but not used!"
        print(f"   {status} {pkg:20} - {note}")
    print()

    # Summary
    print("=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print()
    print(
        f"Core dependencies:  {len(core_packages & used_packages)}/{len(core_packages)} used in code"
    )
    print(
        f"Provider SDKs:      {len(provider_packages & used_packages)}/{len(provider_packages)} used in code"
    )
    print(
        f"Development tools:  {len(dev_packages & req_dev_packages)}/{len(dev_packages)} in requirements-dev.txt"
    )
    print()

    # Architecture validation
    print("🏗️  ARCHITECTURE VALIDATION")
    print("=" * 80)
    print()

    core_in_req = core_packages.issubset(req_packages)
    providers_not_in_req = not bool(provider_packages & req_packages)
    providers_in_dev = provider_packages.issubset(req_dev_packages)

    print(f"✅ Core in requirements.txt:      {core_in_req}")
    print(f"✅ Providers NOT in requirements.txt: {providers_not_in_req} (correct!)")
    print(f"✅ Providers in requirements-dev.txt: {providers_in_dev}")
    print()

    if core_in_req and providers_not_in_req and providers_in_dev:
        print("🎉 VALIDATION PASSED!")
        print("   Your requirements structure is correct:")
        print("   - Core dependencies in requirements.txt")
        print("   - Providers as optional extras (pyproject.toml)")
        print("   - All providers in requirements-dev.txt for testing")
        return 0
    else:
        print("⚠️  VALIDATION FAILED!")
        print("   Please review the warnings above.")
        return 1


if __name__ == "__main__":
    exit(main())
