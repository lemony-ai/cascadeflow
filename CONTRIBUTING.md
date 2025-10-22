# Contributing to CascadeFlow

Thank you for your interest in contributing to CascadeFlow! 🌊

We welcome contributions of all kinds: bug reports, documentation improvements, feature requests, and code contributions.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Code Formatting](#code-formatting)
- [Testing](#testing)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

---

## Code of Conduct

This project follows a Code of Conduct to ensure a welcoming environment for everyone. By participating, you agree to:

- Be respectful and considerate
- Welcome newcomers and help them get started
- Focus on constructive feedback
- Accept gracefully when your contribution is not accepted

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- Virtual environment tool (venv, virtualenv, or conda)

### Quick Start

```bash
# Fork the repository on GitHub
# Clone your fork
git clone https://github.com/YOUR-USERNAME/cascadeflow.git
cd cascadeflow

# Add upstream remote
git remote add upstream https://github.com/lemony-ai/cascadeflow.git
```

---

## Development Setup

### 1. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows
```

### 2. Install Development Dependencies

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Or use requirements file
pip install -r requirements-dev.txt
```

### 3. Set Up Pre-commit Hooks

```bash
pre-commit install
```

### 4. Create Environment File

```bash
cp .env.example .env
# Add your API keys to .env
```

### 5. Verify Setup

```bash
# Run tests
pytest

# Check formatting
black --check cascadeflow/
ruff check cascadeflow/

# Run type checker
mypy cascadeflow/
```

---

## Making Changes

### 1. Create a Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Your Changes

- Write clear, concise code
- Add docstrings to functions and classes
- Update documentation if needed
- Add tests for new functionality

### 3. Commit Your Changes

Follow conventional commit format:

```bash
git add .
git commit -m "type: description"
```

**Commit Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, no logic change)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

**Examples:**
```bash
git commit -m "feat: add support for custom quality thresholds"
git commit -m "fix: resolve token counting edge case"
git commit -m "docs: update installation guide"
```

---

## Code Formatting

**⚠️ IMPORTANT: Always format your code before committing!**

We use automated formatting tools to maintain consistent code style across the project.

### Quick Format (Recommended)

Run the formatting script before every commit:

```bash
# Make script executable (first time only)
chmod +x scripts/format_code.sh

# Run formatting
./scripts/format_code.sh  # macOS/Linux
# or
scripts\format_code.bat   # Windows
```

This script automatically runs:
1. **Black** - Code formatter
2. **isort** - Import sorter
3. **Ruff** - Linter with auto-fix
4. **mypy** - Type checker

### Manual Formatting

If you prefer to run tools individually:

```bash
# Format code with Black
black cascadeflow/ tests/ examples/ --line-length 100

# Sort imports with isort
isort cascadeflow/ tests/ examples/ --profile black --line-length 100

# Fix linting issues with Ruff
ruff check cascadeflow/ tests/ examples/ --fix

# Check types with mypy
mypy cascadeflow/ --ignore-missing-imports
```

### What Each Tool Does

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **Black** | Formats Python code to PEP 8 | Line length: 100 chars |
| **isort** | Sorts and organizes imports | Black-compatible profile |
| **Ruff** | Fast linter with auto-fix | Catches common issues |
| **mypy** | Static type checking | Validates type hints |

### Before Committing Checklist

- [ ] Run `./scripts/format_code.sh` (or `.bat` on Windows)
- [ ] Check `git diff` to review formatting changes
- [ ] Ensure all tests still pass: `pytest`
- [ ] Verify no new linting errors: `ruff check cascadeflow/`

### Formatting Standards

Our formatting follows these standards:
- **Line length:** 100 characters maximum
- **Import order:** stdlib → third-party → local (sorted alphabetically)
- **Spacing:** Consistent spacing around operators and after commas
- **Quotes:** Double quotes preferred by Black
- **Type hints:** Required for all public functions and methods

### Example: Before and After

**Before formatting:**
```python
from cascadeflow.quality import QualityValidator
import os
from typing import Optional,List
import asyncio

def process_query(query:str,model:str,temperature:float=0.7)->dict:
    result=model.generate(query,temp=temperature)
    return result
```

**After formatting:**
```python
import asyncio
import os
from typing import List, Optional

from cascadeflow.quality import QualityValidator


def process_query(query: str, model: str, temperature: float = 0.7) -> dict:
    result = model.generate(query, temp=temperature)
    return result
```

### Continuous Integration

Our CI pipeline automatically checks code formatting:
- Pull requests must pass all formatting checks
- Black, isort, Ruff, and mypy run on every PR
- Failed checks will block merging

**Pro Tip:** Set up pre-commit hooks to auto-format on commit:
```bash
pre-commit install
```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agent.py

# Run with coverage
pytest --cov=cascadeflow --cov-report=html

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_agent.py::test_smart_default
```

### Writing Tests

- Add tests for all new features
- Test edge cases and error conditions
- Use descriptive test names
- Mock external API calls

**Example:**

```python
import pytest
from cascadeflow import CascadeAgent, ModelConfig

def test_agent_initialization():
    """Test that agent initializes correctly."""
    models = [
        ModelConfig(name="gpt-4", provider="openai", cost=0.03)
    ]
    agent = CascadeAgent(models=models)
    assert agent is not None
    assert len(agent.models) == 1

@pytest.mark.asyncio
async def test_agent_run():
    """Test agent.run() with mock provider."""
    # Your test here
    pass
```

### Test Requirements

- All tests must pass before PR is merged
- Maintain or improve code coverage
- Include both unit and integration tests

---

## Code Style

### Formatting

We use automated tools to maintain consistent code style. **Always run the formatting script before committing:**

```bash
./scripts/format_code.sh  # macOS/Linux
# or
scripts\format_code.bat   # Windows
```

See the [Code Formatting](#code-formatting) section for details.

### Style Guidelines

**General:**
- Line length: 100 characters
- Use type hints for function parameters and return values
- Write docstrings for all public functions and classes

**Docstrings:**
```python
def example_function(param1: str, param2: int) -> bool:
    """
    Short description of what the function does.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Description of return value
        
    Raises:
        ValueError: When something goes wrong
    """
    pass
```

**Naming:**
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

---

## Pull Request Process

### Before Submitting

1. **Format your code**
   ```bash
   ./scripts/format_code.sh  # or format_code.bat on Windows
   ```

2. **Update your branch**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

3. **Run all checks**
   ```bash
   pytest
   black --check cascadeflow/
   ruff check cascadeflow/
   mypy cascadeflow/
   ```

4. **Update documentation**
    - Update README.md if needed
    - Update docstrings
    - Add examples if applicable

### Submitting PR

1. **Push your branch**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request on GitHub**
    - Use a clear, descriptive title
    - Reference related issues: "Fixes #123"
    - Describe what changed and why
    - Add screenshots if UI changes

3. **PR Template**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Documentation update
   - [ ] Performance improvement
   
   ## Testing
   - [ ] Tests pass locally
   - [ ] Added new tests
   - [ ] Updated documentation
   - [ ] Ran formatting script
   
   ## Related Issues
   Fixes #123
   ```

### Review Process

- Maintainers will review your PR
- Address any requested changes
- Once approved, your PR will be merged
- Your contribution will be credited in release notes

---

## Reporting Bugs

### Before Reporting

1. Check existing issues for duplicates
2. Try to reproduce with latest version
3. Gather relevant information

### Creating Bug Report

Use the bug report template:

```markdown
**Describe the bug**
Clear description of the bug

**To Reproduce**
Steps to reproduce:
1. Step one
2. Step two
3. See error

**Expected behavior**
What should happen

**Actual behavior**
What actually happens

**Environment**
- OS: Ubuntu 22.04
- Python: 3.11.5
- CascadeFlow: 0.1.0
- Provider: OpenAI

**Additional context**
Any other relevant information
```

---

## Suggesting Features

### Before Suggesting

1. Check if feature already exists or is planned
2. Check existing feature requests
3. Consider if it fits project scope

### Creating Feature Request

```markdown
**Feature Description**
What feature would you like to see?

**Use Case**
Why is this feature important?
What problem does it solve?

**Proposed Solution**
How should this work?

**Alternatives Considered**
What alternatives have you considered?

**Additional Context**
Any mockups, examples, or related features?
```

---

## Development Guidelines

### Adding a New Provider

1. Create `cascadeflow/providers/your_provider.py`
2. Inherit from `BaseProvider`
3. Implement required methods
4. Add to `PROVIDER_REGISTRY`
5. Write tests in `tests/test_your_provider.py`
6. Update documentation
7. **Format code:** `./scripts/format_code.sh`

### Adding a New Feature

1. Discuss in an issue first (for major features)
2. Write tests before implementation (TDD)
3. Update relevant documentation
4. Add examples if applicable
5. Update CHANGELOG.md
6. **Format code before committing**

### Performance Considerations

- Profile code for performance-critical sections
- Avoid blocking operations in async code
- Cache expensive computations when possible
- Consider memory usage for large-scale deployments

---

## Quick Reference

### Common Commands

```bash
# Setup
pip install -e ".[dev]"

# Format code (DO THIS BEFORE EVERY COMMIT!)
./scripts/format_code.sh       # macOS/Linux
scripts\format_code.bat        # Windows

# Test
pytest                         # Run all tests
pytest -v                      # Verbose output
pytest --cov=cascadeflow       # With coverage

# Check code
black --check cascadeflow/     # Check formatting
ruff check cascadeflow/        # Check linting
mypy cascadeflow/              # Check types

# Git workflow
git checkout -b feature/name   # Create branch
git add .                      # Stage changes
git commit -m "feat: message"  # Commit with conventional format
git push origin feature/name   # Push to your fork
```

---

## Questions?

- Open an issue for questions
- Join our discussions
- Check existing documentation

Thank you for contributing to CascadeFlow! 🚀