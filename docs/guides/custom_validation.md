# Custom Validation Guide

Build custom quality validators for domain-specific requirements and compliance.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Validator Types](#validator-types)
3. [Building Custom Validators](#building-custom-validators)
4. [Composite Validators](#composite-validators)
5. [Integration Patterns](#integration-patterns)
6. [Compliance & Regulation](#compliance--regulation)
7. [Best Practices](#best-practices)
8. [Examples](#examples)

---

## Overview

While cascadeflow includes built-in quality validation, you can create custom validators for specific requirements.

### When to Use Custom Validation

- **Compliance** - Medical, legal, financial disclaimers
- **Format Requirements** - JSON, XML, code structure
- **Content Moderation** - Block unwanted content
- **Brand Guidelines** - Enforce tone, terminology
- **Technical Validation** - Code syntax, data formats

### Validation Architecture

```
Query → AI Generation → Custom Validators → Accept/Reject
                              ↓
                        Regenerate if Failed
```

---

## Validator Types

### 1. Keyword Validator

Check for required/forbidden keywords.

```python
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class CustomValidationResult:
    passed: bool
    score: float  # 0.0 to 1.0
    reason: str
    checks: Dict[str, bool]
    violations: List[str]

class KeywordValidator:
    """Validate presence/absence of keywords."""
    
    def __init__(
        self,
        required: Optional[List[str]] = None,
        forbidden: Optional[List[str]] = None,
        case_sensitive: bool = False
    ):
        self.required = required or []
        self.forbidden = forbidden or []
        self.case_sensitive = case_sensitive
    
    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        """Check keyword requirements."""
        text = response if self.case_sensitive else response.lower()
        
        checks = {}
        violations = []
        
        # Required keywords
        for keyword in self.required:
            check_kw = keyword if self.case_sensitive else keyword.lower()
            present = check_kw in text
            checks[f"contains_{keyword}"] = present
            if not present:
                violations.append(f"Missing: {keyword}")
        
        # Forbidden keywords
        for keyword in self.forbidden:
            check_kw = keyword if self.case_sensitive else keyword.lower()
            present = check_kw in text
            checks[f"avoids_{keyword}"] = not present
            if present:
                violations.append(f"Contains forbidden: {keyword}")
        
        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks) if checks else 1.0
        
        return CustomValidationResult(
            passed=passed,
            score=score,
            reason=f"{'Pass' if passed else f'{len(violations)} violations'}",
            checks=checks,
            violations=violations
        )

# Usage
validator = KeywordValidator(
    required=["disclaimer", "consult"],
    forbidden=["guaranteed", "miracle"]
)
result = validator.validate(response)
if not result.passed:
    print(f"Violations: {result.violations}")
```

**Use Cases:**
- Medical: Require "consult a healthcare professional"
- Legal: Require "not legal advice"
- Brand: Avoid competitor names

---

### 2. Length Validator

Enforce minimum/maximum length constraints.

```python
class LengthValidator:
    """Validate response length."""
    
    def __init__(
        self,
        min_words: Optional[int] = None,
        max_words: Optional[int] = None,
        min_sentences: Optional[int] = None,
        max_sentences: Optional[int] = None
    ):
        self.min_words = min_words
        self.max_words = max_words
        self.min_sentences = min_sentences
        self.max_sentences = max_sentences
    
    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        word_count = len(response.split())
        sentence_count = len([s for s in response.split('.') if s.strip()])
        
        checks = {}
        violations = []
        
        if self.min_words and word_count < self.min_words:
            checks["min_words"] = False
            violations.append(f"Too short: {word_count} < {self.min_words} words")
        else:
            checks["min_words"] = True
        
        if self.max_words and word_count > self.max_words:
            checks["max_words"] = False
            violations.append(f"Too long: {word_count} > {self.max_words} words")
        else:
            checks["max_words"] = True
        
        # Similar for sentences...
        
        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks) if checks else 1.0
        
        return CustomValidationResult(
            passed=passed,
            score=score,
            reason="Length OK" if passed else f"{len(violations)} issues",
            checks=checks,
            violations=violations
        )

# Usage
validator = LengthValidator(min_words=50, max_words=200)
result = validator.validate(response)
```

**Use Cases:**
- API responses: Enforce token limits
- Summaries: 50-100 words
- Descriptions: 20-50 words

---

### 3. Format Validator

Validate structural requirements (JSON, code, markdown).

```python
import json
import re

class FormatValidator:
    """Validate response format."""
    
    def __init__(self, format_type: str = "json"):
        self.format_type = format_type.lower()
    
    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        checks = {}
        violations = []
        
        if self.format_type == "json":
            # Extract and validate JSON
            try:
                json_match = re.search(r'\{.*\}|\[.*\]', response, re.DOTALL)
                if json_match:
                    json.loads(json_match.group())
                    checks["valid_json"] = True
                else:
                    checks["valid_json"] = False
                    violations.append("No JSON found")
            except json.JSONDecodeError as e:
                checks["valid_json"] = False
                violations.append(f"Invalid JSON: {e}")
        
        elif self.format_type == "code":
            # Check for code block
            has_code_block = "```" in response
            checks["has_code_block"] = has_code_block
            if not has_code_block:
                violations.append("No code block (```)")
        
        elif self.format_type == "markdown":
            # Check markdown structure
            has_headers = bool(re.search(r'^#+\s', response, re.MULTILINE))
            checks["has_headers"] = has_headers
            if not has_headers:
                violations.append("No markdown headers")
        
        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks) if checks else 1.0
        
        return CustomValidationResult(
            passed=passed,
            score=score,
            reason="Format valid" if passed else "Format issues",
            checks=checks,
            violations=violations
        )

# Usage
validator = FormatValidator(format_type="json")
result = validator.validate(response)
```

**Use Cases:**
- API responses: Valid JSON required
- Code generation: Must include code blocks
- Documentation: Markdown structure

---

### 4. Domain-Specific Validators

Specialized validators for regulated industries.

#### Medical Validator

```python
class MedicalValidator:
    """Validate medical content compliance."""
    
    REQUIRED_DISCLAIMER = "consult a healthcare professional"
    FORBIDDEN_TERMS = [
        "guaranteed cure",
        "miracle treatment",
        "100% effective",
        "FDA approved" # Unless actually true
    ]
    
    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        response_lower = response.lower()
        checks = {}
        violations = []
        
        # Must include disclaimer
        has_disclaimer = self.REQUIRED_DISCLAIMER in response_lower
        checks["has_disclaimer"] = has_disclaimer
        if not has_disclaimer:
            violations.append(f"Missing disclaimer: '{self.REQUIRED_DISCLAIMER}'")
        
        # Must not contain forbidden claims
        for term in self.FORBIDDEN_TERMS:
            if term in response_lower:
                checks[f"avoids_{term}"] = False
                violations.append(f"Forbidden claim: '{term}'")
            else:
                checks[f"avoids_{term}"] = True
        
        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks)
        
        return CustomValidationResult(
            passed=passed,
            score=score,
            reason="Medical compliance OK" if passed else f"{len(violations)} issues",
            checks=checks,
            violations=violations
        )
```

#### Legal Validator

```python
class LegalValidator:
    """Validate legal content compliance."""
    
    REQUIRED_DISCLAIMER = "not legal advice"
    REQUIRE_JURISDICTION = True
    
    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        violations = []
        checks = {}
        
        # Must include "not legal advice"
        has_disclaimer = self.REQUIRED_DISCLAIMER in response.lower()
        checks["has_disclaimer"] = has_disclaimer
        if not has_disclaimer:
            violations.append("Missing: 'not legal advice'")
        
        # Should mention consulting a lawyer
        has_lawyer_mention = any(
            word in response.lower() 
            for word in ["lawyer", "attorney", "legal professional"]
        )
        checks["mentions_professional"] = has_lawyer_mention
        if not has_lawyer_mention:
            violations.append("Should mention consulting a lawyer")
        
        # Check for absolute statements (red flag)
        absolutes = ["always", "never", "definitely", "guaranteed"]
        has_absolutes = any(word in response.lower() for word in absolutes)
        checks["avoids_absolutes"] = not has_absolutes
        if has_absolutes:
            violations.append("Contains absolute statements")
        
        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks)
        
        return CustomValidationResult(
            passed=passed,
            score=score,
            reason="Legal compliance OK" if passed else f"{len(violations)} issues",
            checks=checks,
            violations=violations
        )
```

#### Code Validator

```python
class CodeValidator:
    """Validate code responses."""
    
    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        checks = {}
        violations = []
        
        # Must have code block
        has_code = "```" in response
        checks["has_code_block"] = has_code
        if not has_code:
            violations.append("No code block")
        
        # Check for Python-specific (if applicable)
        if "python" in query.lower():
            has_def = "def " in response
            checks["has_function"] = has_def
            
            has_docstring = '"""' in response or "'''" in response
            checks["has_docstring"] = has_docstring
            if not has_docstring:
                violations.append("Missing docstring")
        
        # No error messages in output
        error_keywords = ["Error", "Exception", "Traceback"]
        has_errors = any(err in response for err in error_keywords)
        checks["no_errors"] = not has_errors
        if has_errors:
            violations.append("Contains error messages")
        
        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks) if checks else 1.0
        
        return CustomValidationResult(
            passed=passed,
            score=score,
            reason="Code valid" if passed else f"{len(violations)} issues",
            checks=checks,
            violations=violations
        )
```

---

## Building Custom Validators

### Base Class Pattern

```python
from abc import ABC, abstractmethod

class BaseValidator(ABC):
    """Abstract base class for validators."""
    
    @abstractmethod
    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        """Validate response. Must be implemented by subclasses."""
        pass
    
    def __call__(self, response: str, query: str = "") -> CustomValidationResult:
        """Allow validator to be called directly."""
        return self.validate(response, query)
```

### Custom Validator Example

```python
class BrandGuidelineValidator(BaseValidator):
    """Enforce brand-specific guidelines."""
    
    def __init__(self, brand_config: dict):
        self.required_tone = brand_config.get("tone", "professional")
        self.forbidden_words = brand_config.get("forbidden", [])
        self.preferred_terms = brand_config.get("preferred", {})
    
    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        checks = {}
        violations = []
        
        # Check tone (simplified)
        if self.required_tone == "professional":
            casual_words = ["gonna", "wanna", "yeah", "nope"]
            has_casual = any(word in response.lower() for word in casual_words)
            checks["professional_tone"] = not has_casual
            if has_casual:
                violations.append("Uses casual language")
        
        # Check forbidden words
        for word in self.forbidden_words:
            if word.lower() in response.lower():
                checks[f"avoids_{word}"] = False
                violations.append(f"Uses forbidden term: {word}")
            else:
                checks[f"avoids_{word}"] = True
        
        # Check preferred terms
        for old, new in self.preferred_terms.items():
            if old.lower() in response.lower():
                violations.append(f"Should use '{new}' instead of '{old}'")
                checks[f"uses_{new}"] = False
            else:
                checks[f"uses_{new}"] = True
        
        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks) if checks else 1.0
        
        return CustomValidationResult(
            passed=passed,
            score=score,
            reason="Brand guidelines met" if passed else f"{len(violations)} issues",
            checks=checks,
            violations=violations
        )

# Usage
brand_config = {
    "tone": "professional",
    "forbidden": ["competitor-name", "cheap"],
    "preferred": {
        "AI": "artificial intelligence",
        "app": "application"
    }
}
validator = BrandGuidelineValidator(brand_config)
result = validator.validate(response)
```

---

## Composite Validators

Combine multiple validators for comprehensive validation.

```python
class CompositeValidator(BaseValidator):
    """Combine multiple validators."""
    
    def __init__(
        self,
        validators: List[BaseValidator],
        require_all: bool = True,
        weights: Optional[List[float]] = None
    ):
        self.validators = validators
        self.require_all = require_all
        self.weights = weights or [1.0] * len(validators)
    
    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        """Run all validators and combine results."""
        results = [v.validate(response, query) for v in self.validators]
        
        # Combine checks
        all_checks = {}
        all_violations = []
        for i, result in enumerate(results):
            for key, value in result.checks.items():
                all_checks[f"v{i}_{key}"] = value
            all_violations.extend(result.violations)
        
        # Determine pass/fail
        if self.require_all:
            passed = all(r.passed for r in results)
        else:
            passed = any(r.passed for r in results)
        
        # Weighted average score
        weighted_score = sum(
            r.score * w for r, w in zip(results, self.weights)
        ) / sum(self.weights)
        
        return CustomValidationResult(
            passed=passed,
            score=weighted_score,
            reason=f"{'All passed' if passed else f'{len(all_violations)} total violations'}",
            checks=all_checks,
            violations=all_violations
        )

# Usage
composite = CompositeValidator([
    KeywordValidator(required=["disclaimer"]),
    LengthValidator(min_words=50, max_words=200),
    FormatValidator("markdown")
], require_all=True)

result = composite.validate(response)
```

### Weighted Validators

```python
# Different validators have different importance
validator = CompositeValidator(
    validators=[
        MedicalValidator(),      # Critical
        LengthValidator(),       # Important
        FormatValidator()        # Nice-to-have
    ],
    weights=[3.0, 2.0, 1.0],
    require_all=False  # Pass if weighted score > threshold
)
```

---

## Integration Patterns

### Pattern 1: Post-Generation Validation

```python
async def generate_with_validation(
    agent: CascadeAgent,
    query: str,
    validators: List[BaseValidator],
    max_retries: int = 3
):
    """Generate with validation and retry."""
    
    for attempt in range(max_retries):
        # Generate
        result = await agent.run(query)
        
        # Validate
        validation = CompositeValidator(validators).validate(
            result.content,
            query
        )
        
        if validation.passed:
            return result
        
        logger.warning(
            f"Validation failed (attempt {attempt + 1}): "
            f"{validation.violations}"
        )
        
        # Modify prompt to address violations
        query = f"{query}\n\nIMPORTANT: {', '.join(validation.violations)}"
    
    raise ValueError(f"Failed validation after {max_retries} attempts")
```

### Pattern 2: Pre-Filter Validation

```python
def validate_query(query: str) -> bool:
    """Validate query before processing."""
    # Check length
    if len(query) > 1000:
        raise ValueError("Query too long")
    
    # Check for prohibited content
    prohibited = ["hack", "exploit", "illegal"]
    if any(word in query.lower() for word in prohibited):
        raise ValueError("Prohibited content in query")
    
    return True

@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    # Validate query first
    validate_query(request.query)
    
    # Then process
    result = await agent.run(request.query)
    return result
```

### Pattern 3: Pipeline Validation

```python
class ValidationPipeline:
    """Multi-stage validation pipeline."""
    
    def __init__(self, stages: List[tuple[str, BaseValidator]]):
        self.stages = stages
    
    def validate(self, response: str, query: str = ""):
        """Run through validation stages."""
        results = {}
        
        for stage_name, validator in self.stages:
            result = validator.validate(response, query)
            results[stage_name] = result
            
            # Stop at first failure
            if not result.passed:
                return {
                    "passed": False,
                    "failed_stage": stage_name,
                    "result": result,
                    "all_results": results
                }
        
        return {
            "passed": True,
            "all_results": results
        }

# Usage
pipeline = ValidationPipeline([
    ("format", FormatValidator("json")),
    ("length", LengthValidator(min_words=10)),
    ("keywords", KeywordValidator(required=["summary"])),
    ("domain", MedicalValidator())
])

validation = pipeline.validate(response)
if not validation["passed"]:
    print(f"Failed at: {validation['failed_stage']}")
```

---

## Compliance & Regulation

### GDPR Compliance

```python
class GDPRValidator(BaseValidator):
    """Validate GDPR compliance."""
    
    PII_PATTERNS = [
        r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
        r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',  # Email
        r'\b\d{16}\b',  # Credit card
    ]
    
    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        violations = []
        checks = {}
        
        # Check for PII
        for pattern in self.PII_PATTERNS:
            if re.search(pattern, response, re.IGNORECASE):
                violations.append(f"Contains PII: {pattern}")
                checks[f"no_pii_{pattern}"] = False
            else:
                checks[f"no_pii_{pattern}"] = True
        
        # Check for data retention notice
        has_notice = "data retention" in response.lower() or \
                    "privacy policy" in response.lower()
        checks["has_privacy_notice"] = has_notice
        
        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks)
        
        return CustomValidationResult(
            passed=passed,
            score=score,
            reason="GDPR compliant" if passed else "GDPR issues",
            checks=checks,
            violations=violations
        )
```

### HIPAA Compliance

```python
class HIPAAValidator(BaseValidator):
    """Validate HIPAA compliance for healthcare."""
    
    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        violations = []
        checks = {}
        
        # No PHI (Protected Health Information)
        phi_indicators = ["patient name", "medical record number", "ssn"]
        has_phi = any(indicator in response.lower() for indicator in phi_indicators)
        checks["no_phi"] = not has_phi
        if has_phi:
            violations.append("Contains PHI")
        
        # Must have disclaimer
        required_disclaimer = "consult with a healthcare provider"
        has_disclaimer = required_disclaimer in response.lower()
        checks["has_disclaimer"] = has_disclaimer
        if not has_disclaimer:
            violations.append(f"Missing: '{required_disclaimer}'")
        
        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks)
        
        return CustomValidationResult(
            passed=passed,
            score=score,
            reason="HIPAA compliant" if passed else "HIPAA violations",
            checks=checks,
            violations=violations
        )
```

---

## Best Practices

### 1. Start with Simple Validators

```python
# Good: Simple, clear
validator = KeywordValidator(required=["disclaimer"])

# Avoid: Over-complex initially
validator = MLBasedSemanticContentQualityValidator(
    model="bert-large",
    threshold=0.95,
    ensemble_count=5
)
```

### 2. Provide Clear Error Messages

```python
# Good
if not has_disclaimer:
    violations.append(
        "Missing required disclaimer: 'consult a healthcare professional'. "
        "Please add this to ensure compliance."
    )

# Bad
if not has_disclaimer:
    violations.append("Missing disclaimer")
```

### 3. Log Validation Decisions

```python
def validate_with_logging(response: str, validator: BaseValidator):
    result = validator.validate(response)
    
    logger.info(
        f"Validation: {result.passed}, "
        f"Score: {result.score:.2f}, "
        f"Checks: {sum(1 for v in result.checks.values() if v)}/{len(result.checks)}"
    )
    
    if not result.passed:
        logger.warning(f"Violations: {result.violations}")
    
    return result
```

### 4. Make Validators Configurable

```python
# Load from config file
validator_config = {
    "medical": {
        "required_disclaimer": "consult a healthcare professional",
        "forbidden_terms": ["guaranteed cure", "miracle"]
    },
    "legal": {
        "required_disclaimer": "not legal advice"
    }
}

validator = MedicalValidator(
    required_disclaimer=validator_config["medical"]["required_disclaimer"],
    forbidden_terms=validator_config["medical"]["forbidden_terms"]
)
```

### 5. Test Validators Thoroughly

```python
def test_medical_validator():
    validator = MedicalValidator()
    
    # Should pass
    good_response = "Aspirin may help. Please consult a healthcare professional."
    result = validator.validate(good_response)
    assert result.passed
    
    # Should fail - missing disclaimer
    bad_response1 = "Take aspirin."
    result = validator.validate(bad_response1)
    assert not result.passed
    assert "disclaimer" in result.reason.lower()
    
    # Should fail - forbidden claim
    bad_response2 = "This guaranteed cure works. Consult a healthcare professional."
    result = validator.validate(bad_response2)
    assert not result.passed
    assert "forbidden" in ' '.join(result.violations).lower()
```

---

## TypeScript Implementation

cascadeflow TypeScript also supports custom quality validation with ML-based semantic similarity checking.

### Semantic Quality Validation

Use embeddings to validate query-response alignment:

```typescript
import { CascadeAgent, SemanticQualityChecker } from '@cascadeflow/core';

// Enable semantic validation in cascade
const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.000375 },
    { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
  ],
  quality: {
    threshold: 0.40,                    // Traditional confidence threshold
    requireMinimumTokens: 5,            // Minimum response length
    useSemanticValidation: true,        // Enable ML validation
    semanticThreshold: 0.5,             // 50% minimum similarity
  },
});

// Responses are now validated for semantic alignment
const result = await agent.run('Explain quantum computing');
```

### Direct Semantic Checking

Use the semantic checker directly for custom validation:

```typescript
import { SemanticQualityChecker } from '@cascadeflow/core';

const checker = new SemanticQualityChecker();

if (await checker.isAvailable()) {
  const result = await checker.checkSimilarity(
    'What is machine learning?',
    'Machine learning is a subset of AI that enables systems to learn.'
  );

  console.log(`Similarity: ${(result.similarity * 100).toFixed(1)}%`);
  console.log(`Passed: ${result.passed}`);

  if (!result.passed) {
    console.log(`Reason: ${result.reason}`);
  }
}
```

**Features:**
- BGE-small-en-v1.5 embeddings (~40MB, auto-downloads)
- CPU-based inference (~50-100ms with caching)
- Request-scoped caching (50% latency reduction)
- Graceful degradation if ML dependencies not installed

**Installation:**
```bash
npm install @cascadeflow/ml @xenova/transformers
```

---

## Examples

**Python:** See [`examples/custom_validation.py`](../../examples/custom_validation.py) for complete working examples.

**TypeScript:** See [`packages/core/examples/nodejs/semantic-quality.ts`](../../packages/core/examples/nodejs/semantic-quality.ts) for ML-based semantic validation.

---

**Next Steps:**
- **Production Guide**: See [production.md](production.md) for deployment
- **FastAPI Integration**: See [fastapi.md](fastapi.md) for API validation
- **Custom Cascades**: See [custom_cascade.md](custom_cascade.md) for routing

---

**Questions?** Open an issue on [GitHub](https://github.com/lemony-ai/cascadeflow/issues).