"""
Custom Validation Example
==========================

Build custom quality validators beyond cascadeflow's built-in validation.

What it demonstrates:
- Custom validation rules for specific domains
- Keyword-based validation (must contain/avoid certain terms)
- Length-based validation (min/max words)
- Format validation (JSON, XML, markdown)
- Domain-specific quality checks (medical, legal, code)
- Combining multiple validators
- Integration with cascadeflow quality system

Requirements:
    - cascadeflow[all]
    - OpenAI API key

Setup:
    pip install cascadeflow[all]
    export OPENAI_API_KEY="sk-..."
    python examples/custom_validation.py

Use Cases:
    1. Medical/Legal: Verify disclaimers present
    2. Code: Validate syntax, ensure runnable
    3. JSON: Validate format, required fields
    4. Content moderation: Block unwanted content
    5. Brand compliance: Enforce tone/terminology

Documentation:
    📖 Validation Guide: docs/guides/custom_validation.md
    📖 Quality System: docs/guides/quality.md
    📚 Examples README: examples/README.md
"""

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Optional

from cascadeflow import CascadeAgent, ModelConfig

# ═══════════════════════════════════════════════════════════════════════════
# CUSTOM VALIDATOR BASE CLASS
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class CustomValidationResult:
    """Result from custom validation."""

    passed: bool
    score: float  # 0.0 to 1.0
    reason: str
    checks: dict[str, bool]
    violations: list[str]


class CustomValidator:
    """Base class for custom validators."""

    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        """Validate response. Override in subclasses."""
        raise NotImplementedError


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR 1: Keyword-Based Validation
# ═══════════════════════════════════════════════════════════════════════════


class KeywordValidator(CustomValidator):
    """Validate response contains/avoids specific keywords."""

    def __init__(
        self,
        required_keywords: Optional[list[str]] = None,
        forbidden_keywords: Optional[list[str]] = None,
        case_sensitive: bool = False,
    ):
        self.required = required_keywords or []
        self.forbidden = forbidden_keywords or []
        self.case_sensitive = case_sensitive

    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        """Check keyword requirements."""
        text = response if self.case_sensitive else response.lower()

        checks = {}
        violations = []

        # Check required keywords
        for keyword in self.required:
            check_kw = keyword if self.case_sensitive else keyword.lower()
            present = check_kw in text
            checks[f"contains_{keyword}"] = present
            if not present:
                violations.append(f"Missing required keyword: {keyword}")

        # Check forbidden keywords
        for keyword in self.forbidden:
            check_kw = keyword if self.case_sensitive else keyword.lower()
            present = check_kw in text
            checks[f"avoids_{keyword}"] = not present
            if present:
                violations.append(f"Contains forbidden keyword: {keyword}")

        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks) if checks else 1.0
        reason = "All keyword checks passed" if passed else f"{len(violations)} violations"

        return CustomValidationResult(
            passed=passed, score=score, reason=reason, checks=checks, violations=violations
        )


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR 2: Length-Based Validation
# ═══════════════════════════════════════════════════════════════════════════


class LengthValidator(CustomValidator):
    """Validate response length (words, sentences, etc.)."""

    def __init__(
        self,
        min_words: Optional[int] = None,
        max_words: Optional[int] = None,
        min_sentences: Optional[int] = None,
        max_sentences: Optional[int] = None,
    ):
        self.min_words = min_words
        self.max_words = max_words
        self.min_sentences = min_sentences
        self.max_sentences = max_sentences

    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        """Check length requirements."""
        word_count = len(response.split())
        sentence_count = len([s for s in response.split(".") if s.strip()])

        checks = {}
        violations = []

        # Word count checks
        if self.min_words is not None:
            passed = word_count >= self.min_words
            checks["min_words"] = passed
            if not passed:
                violations.append(f"Too short: {word_count} words (min: {self.min_words})")

        if self.max_words is not None:
            passed = word_count <= self.max_words
            checks["max_words"] = passed
            if not passed:
                violations.append(f"Too long: {word_count} words (max: {self.max_words})")

        # Sentence count checks
        if self.min_sentences is not None:
            passed = sentence_count >= self.min_sentences
            checks["min_sentences"] = passed
            if not passed:
                violations.append(
                    f"Too few sentences: {sentence_count} (min: {self.min_sentences})"
                )

        if self.max_sentences is not None:
            passed = sentence_count <= self.max_sentences
            checks["max_sentences"] = passed
            if not passed:
                violations.append(
                    f"Too many sentences: {sentence_count} (max: {self.max_sentences})"
                )

        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks) if checks else 1.0
        reason = "Length requirements met" if passed else f"{len(violations)} violations"

        return CustomValidationResult(
            passed=passed, score=score, reason=reason, checks=checks, violations=violations
        )


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR 3: Format Validation (JSON, Code, etc.)
# ═══════════════════════════════════════════════════════════════════════════


class FormatValidator(CustomValidator):
    """Validate response format (JSON, code blocks, etc.)."""

    def __init__(self, format_type: str = "json"):
        self.format_type = format_type.lower()

    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        """Check format requirements."""
        checks = {}
        violations = []

        if self.format_type == "json":
            # Check if response contains valid JSON
            try:
                # Try to find JSON in response
                json_match = re.search(r"\{.*\}|\[.*\]", response, re.DOTALL)
                if json_match:
                    json.loads(json_match.group())
                    checks["valid_json"] = True
                else:
                    checks["valid_json"] = False
                    violations.append("No JSON found in response")
            except json.JSONDecodeError as e:
                checks["valid_json"] = False
                violations.append(f"Invalid JSON: {str(e)}")

        elif self.format_type == "code":
            # Check if response contains code block
            has_code_block = "```" in response
            checks["has_code_block"] = has_code_block
            if not has_code_block:
                violations.append("No code block found (expected ```)")

        elif self.format_type == "markdown":
            # Check basic markdown elements
            has_headers = bool(re.search(r"^#+\s", response, re.MULTILINE))
            checks["has_headers"] = has_headers
            if not has_headers:
                violations.append("No markdown headers found")

        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks) if checks else 1.0
        reason = "Format valid" if passed else f"{len(violations)} format issues"

        return CustomValidationResult(
            passed=passed, score=score, reason=reason, checks=checks, violations=violations
        )


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR 4: Domain-Specific Validators
# ═══════════════════════════════════════════════════════════════════════════


class MedicalValidator(CustomValidator):
    """Validate medical content compliance."""

    REQUIRED_DISCLAIMER = "consult a healthcare professional"
    FORBIDDEN_TERMS = ["guaranteed cure", "miracle treatment", "100% effective"]

    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        """Validate medical response."""
        response_lower = response.lower()
        checks = {}
        violations = []

        # Must contain disclaimer
        has_disclaimer = self.REQUIRED_DISCLAIMER.lower() in response_lower
        checks["has_disclaimer"] = has_disclaimer
        if not has_disclaimer:
            violations.append(f"Missing required disclaimer: '{self.REQUIRED_DISCLAIMER}'")

        # Must not contain forbidden marketing terms
        for term in self.FORBIDDEN_TERMS:
            contains_term = term.lower() in response_lower
            checks[f"avoids_{term}"] = not contains_term
            if contains_term:
                violations.append(f"Contains forbidden term: '{term}'")

        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks)
        reason = "Medical compliance passed" if passed else f"{len(violations)} compliance issues"

        return CustomValidationResult(
            passed=passed, score=score, reason=reason, checks=checks, violations=violations
        )


class CodeValidator(CustomValidator):
    """Validate code responses."""

    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        """Validate code quality."""
        checks = {}
        violations = []

        # Check for code block
        has_code = "```" in response
        checks["has_code_block"] = has_code
        if not has_code:
            violations.append("No code block found")

        # Check for common Python keywords (if Python code)
        if "python" in query.lower() or "def " in response:
            has_def = "def " in response
            checks["has_function"] = has_def

            # Check for basic structure
            has_docstring = '"""' in response or "'''" in response
            checks["has_docstring"] = has_docstring
            if not has_docstring:
                violations.append("Missing docstring")

        # Check for syntax errors (basic check)
        common_errors = ["SyntaxError", "IndentationError", "NameError"]
        has_errors = any(err in response for err in common_errors)
        checks["no_error_messages"] = not has_errors
        if has_errors:
            violations.append("Response contains error messages")

        passed = len(violations) == 0
        score = sum(1 for v in checks.values() if v) / len(checks) if checks else 1.0
        reason = "Code validation passed" if passed else f"{len(violations)} issues"

        return CustomValidationResult(
            passed=passed, score=score, reason=reason, checks=checks, violations=violations
        )


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR 5: Composite Validator (Combine Multiple)
# ═══════════════════════════════════════════════════════════════════════════


class CompositeValidator(CustomValidator):
    """Combine multiple validators."""

    def __init__(self, validators: list[CustomValidator], require_all: bool = True):
        self.validators = validators
        self.require_all = require_all

    def validate(self, response: str, query: str = "") -> CustomValidationResult:
        """Run all validators and combine results."""
        results = [v.validate(response, query) for v in self.validators]

        # Combine checks
        all_checks = {}
        all_violations = []
        for i, result in enumerate(results):
            for key, value in result.checks.items():
                all_checks[f"validator_{i}_{key}"] = value
            all_violations.extend(result.violations)

        # Determine pass/fail
        if self.require_all:
            passed = all(r.passed for r in results)
            reason = (
                "All validators passed" if passed else f"{len(all_violations)} total violations"
            )
        else:
            passed = any(r.passed for r in results)
            reason = "At least one validator passed" if passed else "All validators failed"

        avg_score = sum(r.score for r in results) / len(results)

        return CustomValidationResult(
            passed=passed,
            score=avg_score,
            reason=reason,
            checks=all_checks,
            violations=all_violations,
        )


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════


async def demo_keyword_validator():
    """Demo keyword-based validation."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Keyword Validator")
    print("=" * 70)
    print("\nValidate response contains required terms and avoids forbidden ones\n")

    # Create validator
    validator = KeywordValidator(
        required_keywords=["Python", "programming"], forbidden_keywords=["difficult", "impossible"]
    )

    # Test responses
    test_cases = [
        ("Python is a great programming language for beginners.", "✅ Should pass"),
        ("JavaScript is difficult to learn.", "❌ Missing Python, has 'difficult'"),
        ("Python is powerful.", "❌ Missing 'programming'"),
    ]

    for response, expected in test_cases:
        result = validator.validate(response)
        print(f"Response: {response[:60]}...")
        print(f"Expected: {expected}")
        print(f"Result: {'✅ PASS' if result.passed else '❌ FAIL'} (score: {result.score:.2f})")
        if result.violations:
            print(f"Violations: {', '.join(result.violations)}")
        print()


async def demo_medical_validator():
    """Demo medical content validation."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Medical Validator")
    print("=" * 70)
    print("\nEnsure medical responses include disclaimers and avoid marketing claims\n")

    validator = MedicalValidator()

    # Generate response with AI
    agent = CascadeAgent(
        models=[
            ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
        ]
    )

    query = "What helps with headaches?"
    print(f"Query: {query}\n")

    result = await agent.run(query, max_tokens=150, temperature=0.7)
    print(f"AI Response:\n{result.content}\n")

    # Validate
    validation = validator.validate(result.content, query)
    print(f"Validation: {'✅ PASS' if validation.passed else '❌ FAIL'}")
    print(f"Score: {validation.score:.2f}")
    print(f"Reason: {validation.reason}")
    if validation.violations:
        print("\nViolations:")
        for v in validation.violations:
            print(f"  • {v}")


async def demo_composite_validator():
    """Demo composite validator combining multiple rules."""
    print("\n\n" + "=" * 70)
    print("EXAMPLE 3: Composite Validator")
    print("=" * 70)
    print("\nCombine multiple validators for comprehensive quality checks\n")

    # Create composite validator
    composite = CompositeValidator(
        [
            LengthValidator(min_words=20, max_words=100),
            KeywordValidator(required_keywords=["function", "return"]),
            CodeValidator(),
        ],
        require_all=True,
    )

    # Generate code response
    agent = CascadeAgent(
        models=[
            ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
        ]
    )

    query = "Write a Python function to calculate factorial"
    print(f"Query: {query}\n")

    result = await agent.run(query, max_tokens=200, temperature=0.7)
    print(f"AI Response:\n{result.content}\n")

    # Validate
    validation = composite.validate(result.content, query)
    print(f"Validation: {'✅ PASS' if validation.passed else '❌ FAIL'}")
    print(f"Score: {validation.score:.2f}")
    print(f"Total checks: {len(validation.checks)}")
    print(f"Passed: {sum(1 for v in validation.checks.values() if v)}/{len(validation.checks)}")

    if validation.violations:
        print("\nViolations:")
        for v in validation.violations:
            print(f"  • {v}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════


async def main():
    """Run custom validation examples."""

    print("🌊 cascadeflow Custom Validation Examples")
    print("=" * 70)

    if not os.getenv("OPENAI_API_KEY"):
        print("\n❌ OPENAI_API_KEY required")
        return

    # Run examples
    await demo_keyword_validator()
    await demo_medical_validator()
    await demo_composite_validator()

    # Summary
    print("\n\n" + "=" * 70)
    print("🎓 KEY TAKEAWAYS")
    print("=" * 70)

    print("\n1. Validator Types:")
    print("   ├─ Keyword: Required/forbidden terms")
    print("   ├─ Length: Min/max words/sentences")
    print("   ├─ Format: JSON, code blocks, markdown")
    print("   ├─ Domain: Medical, legal, code-specific")
    print("   └─ Composite: Combine multiple validators")

    print("\n2. Use Cases:")
    print("   ├─ Compliance: Ensure disclaimers, avoid claims")
    print("   ├─ Quality: Check format, length, structure")
    print("   ├─ Safety: Block inappropriate content")
    print("   ├─ Branding: Enforce tone, terminology")
    print("   └─ Technical: Validate code, JSON, markup")

    print("\n3. Integration:")
    print("   ├─ Run validators after AI generation")
    print("   ├─ Reject/regenerate if validation fails")
    print("   ├─ Log violations for analysis")
    print("   ├─ Adjust prompts based on failures")
    print("   └─ Combine with cascadeflow quality system")

    print("\n📚 Learn more:")
    print("   • docs/guides/custom_validation.md")
    print("   • docs/guides/quality.md")
    print("   • examples/production_patterns.py\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
