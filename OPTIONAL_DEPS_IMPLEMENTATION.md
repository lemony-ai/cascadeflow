# Optional Dependencies Implementation Guide

## Overview

CascadeFlow v0.2.0 uses optional dependencies to keep the core package lightweight while providing advanced ML-based features for users who need them.

## Installation Options

### Basic Installation (Core Features)

```bash
pip install cascadeflow
```

**Includes:**
- ✅ Cost tracking and cascading (core value)
- ✅ User tier management
- ✅ Domain routing (rule-based only)
- ✅ Rule-based quality validation
- ✅ Budget enforcement
- ✅ All provider integrations
- **Size:** ~5MB
- **Dependencies:** httpx, pydantic, tiktoken

**Use Cases:**
- Production deployments on edge devices
- Lambda functions (size constraints)
- Quick prototyping
- Users who don't need ML validation

### Semantic Features (ML-Based Quality)

```bash
pip install cascadeflow[semantic]
```

**Adds:**
- ✅ Semantic similarity validation (FastEmbed)
- ✅ Toxicity detection (transformers)
- ✅ Domain detection (semantic routing)
- ✅ Hallucination detection (optional)
- **Additional size:** ~300-500MB (models)
- **Additional dependencies:** fastembed, transformers, sentence-transformers

**Use Cases:**
- Production API servers (quality-critical)
- Applications requiring content safety
- High-stakes domains (medical, legal)

### Full Installation (All Features)

```bash
pip install cascadeflow[all]
```

**Includes:**
- Everything from `[semantic]`
- Plus: Development tools, testing utilities
- **Use case:** Development, testing, full feature exploration

## Implementation in Code

### pyproject.toml Configuration

```toml
[project]
name = "cascadeflow"
version = "0.2.0"
dependencies = [
    "httpx>=0.24.0",
    "pydantic>=2.0.0",
    "tiktoken>=0.5.0",
    "numpy>=1.24.0",  # Lightweight, widely used
]

[project.optional-dependencies]
semantic = [
    "fastembed>=0.2.0",           # Fast embeddings (ONNX)
    "transformers>=4.30.0",       # HuggingFace models
    "sentence-transformers>=2.2.0", # Semantic similarity
    "torch>=2.0.0",               # Required by transformers
]

hallucination = [
    "selfcheckgpt>=0.1.0",        # Hallucination detection
]

all = [
    "cascadeflow[semantic]",
    "cascadeflow[hallucination]",
]

dev = [
    "cascadeflow[all]",
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]
```

### Graceful Degradation Pattern

```python
# cascadeflow/quality/semantic.py

from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    from fastembed import TextEmbedding
    from transformers import pipeline
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    TextEmbedding = None
    pipeline = None


class SemanticValidator:
    """
    Semantic quality validator with graceful degradation.

    If semantic dependencies not installed, falls back to rule-based validation
    with clear warnings.
    """

    def __init__(
        self,
        enable_semantic: bool = True,
        enable_toxicity: bool = True,
        fallback_to_rules: bool = True,
    ):
        self.enable_semantic = enable_semantic
        self.enable_toxicity = enable_toxicity
        self.fallback_to_rules = fallback_to_rules

        # Check if ML features are requested but not available
        if (enable_semantic or enable_toxicity) and not SEMANTIC_AVAILABLE:
            self._handle_missing_dependencies()

    def _handle_missing_dependencies(self):
        """Handle case where semantic features requested but not installed."""

        if self.fallback_to_rules:
            # Graceful degradation
            logger.warning(
                "Semantic validation requested but dependencies not installed. "
                "Falling back to rule-based validation. "
                "Install semantic features with: pip install cascadeflow[semantic]"
            )
            self.enable_semantic = False
            self.enable_toxicity = False
        else:
            # Strict mode: raise error
            raise ImportError(
                "Semantic validation requires additional dependencies. "
                "Install with: pip install cascadeflow[semantic]\n\n"
                "Or disable semantic validation:\n"
                "  agent = CascadeAgent(models=[...], quality_mode='fast')"
            )

    def validate(self, query: str, response: str) -> dict:
        """Validate response with available validators."""

        results = {}

        # Rule-based validation (always available)
        results['rule_based'] = self._rule_based_validation(response)

        # Semantic validation (if available and enabled)
        if self.enable_semantic and SEMANTIC_AVAILABLE:
            results['semantic_similarity'] = self._semantic_validation(query, response)

        # Toxicity check (if available and enabled)
        if self.enable_toxicity and SEMANTIC_AVAILABLE:
            results['toxicity'] = self._toxicity_check(response)

        return results

    def _rule_based_validation(self, response: str) -> dict:
        """Rule-based validation (always available)."""
        # Existing logic from v0.1.1
        return {
            'hedging_score': self._check_hedging(response),
            'coherence_score': self._check_coherence(response),
            'completeness_score': self._check_completeness(response),
        }

    def _semantic_validation(self, query: str, response: str) -> float:
        """Semantic similarity (requires fastembed)."""
        if not SEMANTIC_AVAILABLE:
            return None

        # Lazy load model
        if not hasattr(self, '_embedding_model'):
            self._embedding_model = TextEmbedding(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )

        # Calculate similarity
        embeddings = self._embedding_model.embed([query, response])
        similarity = self._cosine_similarity(embeddings[0], embeddings[1])
        return float(similarity)

    def _toxicity_check(self, response: str) -> float:
        """Toxicity detection (requires transformers)."""
        if not SEMANTIC_AVAILABLE:
            return None

        # Lazy load classifier
        if not hasattr(self, '_toxicity_classifier'):
            self._toxicity_classifier = pipeline(
                "text-classification",
                model="sileod/deberta-v3-base-tasksource-toxicity",
                device=-1  # CPU
            )

        result = self._toxicity_classifier(response)[0]
        toxicity_score = result['score'] if result['label'] == 'toxic' else 1.0 - result['score']
        return toxicity_score
```

### User-Friendly Configuration

```python
# cascadeflow/config.py

class QualityConfig:
    """
    Quality validation configuration with automatic dependency detection.
    """

    @classmethod
    def for_production(cls):
        """
        Production preset with automatic feature detection.

        Uses semantic validation if available, otherwise falls back to rules.
        """
        from cascadeflow.quality.semantic import SEMANTIC_AVAILABLE

        if SEMANTIC_AVAILABLE:
            return cls(
                enable_semantic_validation=True,
                enable_toxicity_check=True,
                fallback_to_rules=True,
            )
        else:
            # Automatically use rules-only if semantic not installed
            return cls(
                enable_semantic_validation=False,
                enable_toxicity_check=False,
            )

    @classmethod
    def balanced(cls):
        """
        Balanced preset (requires semantic dependencies).

        Raises clear error if dependencies not installed.
        """
        from cascadeflow.quality.semantic import SEMANTIC_AVAILABLE

        if not SEMANTIC_AVAILABLE:
            raise ImportError(
                "Balanced quality mode requires semantic dependencies.\n\n"
                "Install with:\n"
                "  pip install cascadeflow[semantic]\n\n"
                "Or use 'fast' mode (rule-based only):\n"
                "  QualityConfig.for_production()"
            )

        return cls(
            enable_semantic_validation=True,
            enable_toxicity_check=True,
            fallback_to_rules=False,  # Strict: fail if ML not available
        )

    @classmethod
    def fast(cls):
        """
        Fast preset using only rule-based validation.

        Always works, no dependencies required.
        """
        return cls(
            enable_semantic_validation=False,
            enable_toxicity_check=False,
        )
```

### Clear Error Messages

```python
# Example: User tries to enable semantic without dependencies

>>> agent = CascadeAgent(models=[...], quality_mode='balanced')

ImportError: Balanced quality mode requires semantic dependencies.

Install with:
  pip install cascadeflow[semantic]

Or use 'fast' mode (rule-based only):
  agent = CascadeAgent(models=[...], quality_mode='fast')
  # or
  agent = CascadeAgent(models=[...])  # fast is default
```

### Automatic Feature Detection

```python
# cascadeflow/__init__.py

from cascadeflow.quality.semantic import SEMANTIC_AVAILABLE

# Export capability flags
__features__ = {
    'semantic_validation': SEMANTIC_AVAILABLE,
    'toxicity_detection': SEMANTIC_AVAILABLE,
    'hallucination_detection': False,  # Requires additional install
}

def print_features():
    """Print available features."""
    print("CascadeFlow v0.2.0 Features:")
    print(f"  Core: ✅ (always available)")
    print(f"  Semantic Validation: {'✅' if SEMANTIC_AVAILABLE else '❌ (install with: pip install cascadeflow[semantic])'}")
    print(f"  Toxicity Detection: {'✅' if SEMANTIC_AVAILABLE else '❌ (install with: pip install cascadeflow[semantic])'}")
```

## Documentation Strategy

### Quick Start (Keep Simple)

```markdown
## Installation

### Basic (Recommended for Getting Started)
```bash
pip install cascadeflow
```

### With Semantic Quality (Recommended for Production)
```bash
pip install cascadeflow[semantic]
```

This adds ML-based quality validation (semantic similarity, toxicity detection).
About 300-500MB additional download.
```

### Feature Guide

```markdown
## Quality Validation Modes

CascadeFlow offers three quality modes:

### Fast (Default)
- **Install:** `pip install cascadeflow`
- **Features:** Rule-based validation only
- **Overhead:** ~3-5ms
- **Use case:** Edge devices, Lambda functions, quick prototyping

### Balanced (Recommended for Production)
- **Install:** `pip install cascadeflow[semantic]`
- **Features:** Rules + semantic similarity + toxicity detection
- **Overhead:** ~70ms
- **Use case:** Production APIs, content-sensitive applications

### Strict (High-Stakes)
- **Install:** `pip install cascadeflow[semantic]`
- **Features:** All above + hallucination detection
- **Overhead:** ~500-1000ms
- **Use case:** Medical, legal, financial applications
```

### Migration Guide

```markdown
## Upgrading from v0.1.1 to v0.2.0

### No Changes Required

All v0.1.1 code works unchanged:

```python
# v0.1.1 code (still works)
agent = CascadeAgent(models=[...])
result = await agent.run(query="...")
```

### Adding Semantic Quality (Optional)

If you want ML-based quality validation:

1. Install semantic dependencies:
   ```bash
   pip install --upgrade cascadeflow[semantic]
   ```

2. Enable in config:
   ```python
   agent = CascadeAgent(models=[...], quality_mode='balanced')
   ```

That's it! If dependencies aren't installed, CascadeFlow automatically falls back to rule-based validation with a warning.
```

## Testing Strategy

### Unit Tests (Mock Optional Dependencies)

```python
# tests/test_optional_deps.py

import pytest
from unittest.mock import patch

def test_semantic_validator_without_dependencies():
    """Test graceful degradation when semantic deps not installed."""

    # Mock missing imports
    with patch('cascadeflow.quality.semantic.SEMANTIC_AVAILABLE', False):
        from cascadeflow import QualityConfig

        # Should fall back to rule-based
        config = QualityConfig.for_production()
        assert config.enable_semantic_validation == False
        assert config.enable_toxicity_check == False

def test_semantic_validator_strict_mode_without_deps():
    """Test strict mode raises clear error when deps missing."""

    with patch('cascadeflow.quality.semantic.SEMANTIC_AVAILABLE', False):
        from cascadeflow import QualityConfig

        with pytest.raises(ImportError, match="pip install cascadeflow\\[semantic\\]"):
            config = QualityConfig.balanced()

def test_semantic_validator_with_dependencies():
    """Test ML features work when dependencies installed."""

    # Only run if semantic actually available
    pytest.importorskip('fastembed')

    from cascadeflow import QualityConfig, SemanticValidator

    config = QualityConfig.balanced()
    validator = SemanticValidator()

    result = validator.validate(
        query="What is 2+2?",
        response="2+2 equals 4."
    )

    assert 'semantic_similarity' in result
    assert result['semantic_similarity'] > 0.7
```

### Integration Tests (Conditional)

```python
# tests/integration/test_semantic_integration.py

import pytest

@pytest.mark.skipif(
    not pytest.importorskip('fastembed'),
    reason="Semantic dependencies not installed"
)
def test_full_cascade_with_semantic():
    """Test complete cascade with semantic validation."""

    from cascadeflow import CascadeAgent, QualityConfig

    agent = CascadeAgent(
        models=[...],
        quality_mode='balanced'
    )

    result = await agent.run(query="Test query")

    # Validate semantic scores are present
    assert 'semantic_similarity' in result.metadata
    assert 'toxicity_score' in result.metadata
```

## CI/CD Strategy

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml

name: Tests

on: [push, pull_request]

jobs:
  test-core:
    name: Test Core (No Optional Deps)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      # Install ONLY core dependencies
      - name: Install core
        run: pip install -e .

      - name: Run core tests
        run: pytest tests/ -k "not semantic"

  test-semantic:
    name: Test Semantic Features
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      # Install with semantic dependencies
      - name: Install semantic
        run: pip install -e .[semantic,dev]

      - name: Run all tests
        run: pytest tests/

  test-matrix:
    name: Test Python ${{ matrix.python-version }}
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11', '3.12']
        include:
          - deps: core
          - deps: semantic
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          if [ "${{ matrix.deps }}" == "semantic" ]; then
            pip install -e .[semantic,dev]
          else
            pip install -e .[dev]
          fi

      - name: Run tests
        run: pytest
```

## Package Size Analysis

### Core Package

```
cascadeflow/
├── core/           # 500KB
├── providers/      # 300KB
├── telemetry/      # 200KB
├── quality/        # 400KB (rules only)
├── utils/          # 100KB
└── __init__.py     # 10KB

Total: ~1.5MB (compressed: ~500KB)
```

### Semantic Add-On

```
Dependencies:
├── fastembed       # ~150MB (includes ONNX models)
├── transformers    # ~100MB
├── sentence-transformers  # ~50MB
├── torch           # ~200MB (CPU version)

Total additional: ~500MB
```

### Comparison

```
| Package | Core Only | With Semantic | With All |
|---------|-----------|---------------|----------|
| Size    | 500KB     | ~500MB        | ~800MB   |
| Install | 5s        | 60s           | 90s      |
| Use Case| Edge/Lambda | Production API | Development |
```

## Rollout Strategy

### Phase 1: v0.2.0-alpha (Week 1-2)

- Release with optional dependencies
- Core features + semantic optional
- Internal testing only
- Gather feedback on install experience

### Phase 2: v0.2.0-beta (Week 3-4)

- Public beta with clear "experimental" labels
- Documentation emphasizing optional nature
- Monitor adoption of `[semantic]` install
- Fix any packaging issues

### Phase 3: v0.2.0 (Week 5-6)

- Stable release
- Full documentation
- Clear guidance on which install to choose
- Blog post explaining optional deps strategy

## User Education

### Landing Page

```markdown
## CascadeFlow: Smart LLM Routing

### Quick Start

Choose your installation:

┌─────────────────────────────────────────────────────┐
│ 🚀 Fast Start (Core Features)                      │
│                                                     │
│ pip install cascadeflow                            │
│                                                     │
│ ✅ Cost optimization (60-85% savings)              │
│ ✅ User tier management                            │
│ ✅ Rule-based quality validation                   │
│ 📦 Package size: 500KB                             │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ ⭐ Recommended (Production Quality)                │
│                                                     │
│ pip install cascadeflow[semantic]                  │
│                                                     │
│ ✅ Everything above +                              │
│ ✅ Semantic similarity validation (10x better)     │
│ ✅ Toxicity detection (94.87% accuracy)            │
│ ✅ Domain-aware routing                            │
│ 📦 Additional size: ~500MB                         │
└─────────────────────────────────────────────────────┘

Not sure? Start with core and upgrade later!
```

### FAQ Section

```markdown
## FAQ: Optional Dependencies

**Q: Why are some features optional?**
A: To keep the core package lightweight (500KB vs 500MB). Edge devices and Lambda functions benefit from the smaller package.

**Q: Can I start with core and add semantic later?**
A: Yes! Just run `pip install --upgrade cascadeflow[semantic]`. Your existing code continues to work.

**Q: What happens if I try to use semantic features without installing them?**
A: CascadeFlow automatically falls back to rule-based validation with a helpful warning message.

**Q: Which should I choose?**
A:
- Edge/Lambda/Quick prototype: Core
- Production API/Content-sensitive: Semantic
- Not sure: Start with core, upgrade when needed

**Q: Do semantic features work offline?**
A: Yes, once installed. Models are bundled and don't require internet after initial install.
```

## Summary

### Key Benefits of Optional Dependency Approach

1. **Accessibility** - Core features available in 5-second install
2. **Flexibility** - Users choose performance vs quality tradeoff
3. **Compatibility** - Works on edge devices without ML overhead
4. **Progressive** - Can upgrade from core → semantic → all
5. **Clear** - Explicit about tradeoffs, not hidden complexity

### Implementation Checklist

- [ ] Configure pyproject.toml with optional deps
- [ ] Add SEMANTIC_AVAILABLE flag with try/except
- [ ] Implement graceful degradation in SemanticValidator
- [ ] Add clear error messages with install instructions
- [ ] Update QualityConfig presets with auto-detection
- [ ] Write unit tests for both scenarios (with/without deps)
- [ ] Add CI/CD jobs for core-only and semantic testing
- [ ] Create clear documentation with install guides
- [ ] Add feature detection function (print_features)
- [ ] Test package size for both installations

### Success Metrics

**Adoption:**
- Core installs: Target 60% (quick start, edge cases)
- Semantic installs: Target 35% (production APIs)
- All installs: Target 5% (development)

**Support:**
- "How do I install semantic features?" - Should be <5% of issues
- Install-related bugs - Target <1% of bug reports

**Performance:**
- Core install time: <10 seconds
- Semantic install time: <90 seconds
- No install failures due to dependency conflicts

---

This approach gives us the best of both worlds: fast, lightweight core for getting started and edge deployment, plus powerful ML features for production when needed.
