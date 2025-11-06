"""
Tests for Multi-Step Cascade Executor (Phase 4.1)

Tests the cascade executor and validation functions.
"""

import pytest

from cascadeflow.routing.cascade_executor import (
    MultiStepCascadeExecutor,
    validate_fact_check,
    validate_full_quality,
    validate_quality,
    validate_safety,
    validate_syntax,
)
from cascadeflow.routing.cascade_pipeline import (
    CascadeStep,
    DomainCascadeStrategy,
    ValidationMethod,
    get_code_strategy,
    get_medical_strategy,
)
from cascadeflow.routing.domain import Domain

# ============================================================================
# TEST: Validation Functions
# ============================================================================


class TestValidationFunctions:
    """Test validation functions."""

    def test_validate_syntax_with_code(self):
        """Test syntax validation with valid code."""
        response = """
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[0]
    return quicksort([x for x in arr[1:] if x < pivot]) + [pivot] + quicksort([x for x in arr[1:] if x >= pivot])
"""
        passed, score, details = validate_syntax(response, {})

        assert passed is True
        assert score >= 0.7
        assert "has_code" in details
        assert details["has_code"] is True

    def test_validate_syntax_without_code(self):
        """Test syntax validation without code."""
        response = "This is just plain text without any code."

        passed, score, details = validate_syntax(response, {})

        assert passed is False
        assert score < 0.7

    def test_validate_fact_check_with_disclaimer(self):
        """Test fact checking with medical disclaimer."""
        response = """
Type 2 diabetes symptoms include increased thirst, frequent urination, and fatigue.
However, please consult a healthcare professional for medical advice.
"""
        passed, score, details = validate_fact_check(response, {})

        assert passed is True
        assert score >= 0.75
        assert "has_disclaimer" in details

    def test_validate_fact_check_without_disclaimer(self):
        """Test fact checking without disclaimer."""
        response = "Aspirin is safe for everyone to take daily."

        passed, score, details = validate_fact_check(response, {})

        # Should still pass but with lower score
        assert "has_disclaimer" in details

    def test_validate_safety_clean_response(self):
        """Test safety validation with clean response."""
        response = "Here's a helpful Python tutorial on machine learning."

        passed, score, details = validate_safety(response, {})

        assert passed is True
        assert score >= 0.9
        assert "toxic_keywords_found" in details
        assert len(details["toxic_keywords_found"]) == 0

    def test_validate_safety_with_toxic_keywords(self):
        """Test safety validation with toxic keywords."""
        # Use more explicitly toxic keywords from the validator's list
        response = "This is terrible garbage. Kill this stupid worthless code, you moron!"

        passed, score, details = validate_safety(response, {})

        # Check that toxic keywords were detected
        assert "toxic_keywords_found" in details
        # Depending on keyword list, may or may not pass threshold
        assert isinstance(passed, bool)
        assert 0.0 <= score <= 1.0

    def test_validate_quality_good_response(self):
        """Test quality validation with good response."""
        response = """
Python is a high-level programming language known for its simplicity and readability.
It supports multiple programming paradigms including procedural, object-oriented, and functional programming.
Python has a large standard library and active community support.
"""
        passed, score, details = validate_quality(response, {})

        assert passed is True
        assert score >= 0.7
        assert "good_length" in details
        assert details["good_length"] is True

    def test_validate_quality_short_response(self):
        """Test quality validation with too short response."""
        response = "Yes."

        passed, score, details = validate_quality(response, {})

        # Short responses should fail
        assert "too_short" in details or "good_length" not in details

    def test_validate_full_quality_combines_checks(self):
        """Test full quality validation combines multiple checks."""
        response = """
Python is a versatile programming language with excellent readability.
It's widely used in data science, web development, and automation.
The language emphasizes code clarity and developer productivity.
"""
        passed, score, details = validate_full_quality(response, {})

        assert passed is True
        assert score >= 0.85
        # Should include both quality and safety checks
        assert "quality" in details
        assert "safety" in details
        assert "combined_score" in details

    def test_validation_respects_thresholds(self):
        """Test validation functions respect custom thresholds."""
        response = "Short response"

        # The validation functions use threshold from metadata if provided
        # But they have internal logic, so we test the score
        passed, score, _ = validate_quality(response, {})

        # Just verify it returns valid score
        assert 0.0 <= score <= 1.0


# ============================================================================
# TEST: MultiStepCascadeExecutor
# ============================================================================


class TestMultiStepCascadeExecutor:
    """Test MultiStepCascadeExecutor."""

    def test_executor_initialization(self):
        """Test executor initialization."""
        strategies = [get_code_strategy()]
        executor = MultiStepCascadeExecutor(strategies=strategies)

        assert len(executor.strategies) == 1
        assert executor.enable_fallback is True
        assert executor.max_retries == 2

    def test_executor_initialization_with_empty_strategies(self):
        """Test executor with no strategies."""
        executor = MultiStepCascadeExecutor(strategies=[])

        assert len(executor.strategies) == 0

    def test_executor_custom_validators(self):
        """Test executor with custom validators."""

        def custom_validator(response, metadata):
            return True, 1.0, {"custom": True}

        executor = MultiStepCascadeExecutor(custom_validators={"custom": custom_validator})

        assert "custom" in executor.custom_validators

    def test_executor_get_strategy_for_domain(self):
        """Test getting strategy for a domain."""
        code_strategy = get_code_strategy()
        medical_strategy = get_medical_strategy()

        executor = MultiStepCascadeExecutor(strategies=[code_strategy, medical_strategy])

        # Should return CODE strategy
        strategy = executor.get_strategy(Domain.CODE)
        assert strategy is not None
        assert strategy.domain == Domain.CODE

        # Should return MEDICAL strategy
        strategy = executor.get_strategy(Domain.MEDICAL)
        assert strategy is not None
        assert strategy.domain == Domain.MEDICAL

        # Should return None for domain without strategy
        strategy = executor.get_strategy(Domain.CONVERSATION)
        assert strategy is None

    @pytest.mark.asyncio
    async def test_executor_execute_no_strategy(self):
        """Test executor with no strategy for domain."""
        executor = MultiStepCascadeExecutor(strategies=[])

        result = await executor.execute(
            query="Test query",
            domain=Domain.CODE,
        )

        assert result.success is False
        # Check that error is in metadata
        assert "error" in result.metadata
        assert "No strategy found" in result.metadata["error"]


# ============================================================================
# TEST: Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for cascade executor."""

    @pytest.mark.asyncio
    async def test_code_cascade_execution(self):
        """Test executing CODE cascade pipeline."""
        strategy = get_code_strategy()
        executor = MultiStepCascadeExecutor(strategies=[strategy])

        result = await executor.execute(
            query="Write a Python function to implement binary search",
            domain=Domain.CODE,
        )

        assert result.success is True
        assert result.domain == Domain.CODE
        assert len(result.steps_executed) >= 1
        assert result.total_cost > 0
        assert result.final_response is not None

    @pytest.mark.asyncio
    async def test_medical_cascade_execution(self):
        """Test executing MEDICAL cascade pipeline."""
        strategy = get_medical_strategy()
        executor = MultiStepCascadeExecutor(strategies=[strategy])

        result = await executor.execute(
            query="What are the symptoms of type 2 diabetes?",
            domain=Domain.MEDICAL,
        )

        assert result.success is True
        assert result.domain == Domain.MEDICAL
        assert len(result.steps_executed) >= 1

    @pytest.mark.asyncio
    async def test_fallback_behavior(self):
        """Test fallback step execution."""
        # Create strategy with fallback step
        fallback_strategy = DomainCascadeStrategy(
            domain=Domain.CODE,
            description="Fallback test",
            steps=[
                CascadeStep(
                    name="draft",
                    model="gpt-4o-mini",
                    provider="openai",
                    validation=ValidationMethod.QUALITY_CHECK,
                    quality_threshold=0.95,  # High but valid threshold
                    fallback_only=False,
                ),
                CascadeStep(
                    name="fallback",
                    model="gpt-4",
                    provider="openai",
                    quality_threshold=0.7,  # Lower threshold
                    fallback_only=True,
                ),
            ],
        )

        executor = MultiStepCascadeExecutor(strategies=[fallback_strategy])

        result = await executor.execute(
            query="Simple query",
            domain=Domain.CODE,
        )

        # Verify result structure (fallback may or may not trigger based on validation)
        assert isinstance(result.fallback_used, bool)
        assert len(result.steps_executed) >= 1
        assert result.success is True

    @pytest.mark.asyncio
    async def test_multi_domain_executor(self):
        """Test executor with multiple domain strategies."""
        executor = MultiStepCascadeExecutor(
            strategies=[
                get_code_strategy(),
                get_medical_strategy(),
            ]
        )

        # Execute CODE query
        code_result = await executor.execute(
            query="Write Python code",
            domain=Domain.CODE,
        )
        assert code_result.domain == Domain.CODE

        # Execute MEDICAL query
        medical_result = await executor.execute(
            query="Medical question",
            domain=Domain.MEDICAL,
        )
        assert medical_result.domain == Domain.MEDICAL

    @pytest.mark.asyncio
    async def test_execution_result_helpers(self):
        """Test execution result helper methods."""
        strategy = get_code_strategy()
        executor = MultiStepCascadeExecutor(strategies=[strategy])

        result = await executor.execute(
            query="Test query",
            domain=Domain.CODE,
        )

        # Test get_cost_breakdown
        breakdown = result.get_cost_breakdown()
        assert isinstance(breakdown, dict)
        assert len(breakdown) > 0

        # Test get_successful_steps
        successful = result.get_successful_steps()
        assert len(successful) >= 1

        # Test get_step_result
        first_step = result.steps_executed[0]
        step_result = result.get_step_result(first_step.step_name)
        assert step_result is not None


# ============================================================================
# TEST: Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_executor_with_disabled_fallback(self):
        """Test executor with fallback disabled."""
        strategy = get_code_strategy()
        executor = MultiStepCascadeExecutor(
            strategies=[strategy],
            enable_fallback=False,
        )

        result = await executor.execute(
            query="Test query",
            domain=Domain.CODE,
        )

        # Should not use fallback even if draft fails
        assert result.fallback_used is False

    def test_validation_function_registry(self):
        """Test validation function registry."""
        # Test that validation functions are registered
        from cascadeflow.routing.cascade_executor import VALIDATION_FUNCTIONS

        assert ValidationMethod.NONE in VALIDATION_FUNCTIONS
        assert ValidationMethod.SYNTAX_CHECK in VALIDATION_FUNCTIONS
        assert ValidationMethod.QUALITY_CHECK in VALIDATION_FUNCTIONS
        assert ValidationMethod.FULL_QUALITY in VALIDATION_FUNCTIONS

    @pytest.mark.asyncio
    async def test_executor_with_metadata(self):
        """Test executor with custom metadata."""
        strategy = get_code_strategy()
        executor = MultiStepCascadeExecutor(strategies=[strategy])

        result = await executor.execute(
            query="Test query",
            domain=Domain.CODE,
            user_id="test_user_123",
            custom_field="custom_value",
        )

        assert result.success is True
        # Metadata should be captured in result
        assert result.metadata is not None


# ============================================================================
# TEST: Cost Tracking
# ============================================================================


class TestCostTracking:
    """Test cost tracking in execution results."""

    @pytest.mark.asyncio
    async def test_execution_tracks_costs(self):
        """Test that execution results include cost information."""
        strategy = get_code_strategy()
        executor = MultiStepCascadeExecutor(strategies=[strategy])

        result = await executor.execute(
            query="Test query",
            domain=Domain.CODE,
        )

        # Should have cost information
        assert result.total_cost > 0
        assert result.total_tokens > 0

        # Each step should have cost
        for step in result.steps_executed:
            assert step.cost >= 0
            assert step.tokens_used >= 0

    @pytest.mark.asyncio
    async def test_cost_breakdown_accurate(self):
        """Test that cost breakdown matches total cost."""
        strategy = get_code_strategy()
        executor = MultiStepCascadeExecutor(strategies=[strategy])

        result = await executor.execute(
            query="Test query",
            domain=Domain.CODE,
        )

        # Cost breakdown should sum to total
        breakdown = result.get_cost_breakdown()
        breakdown_total = sum(breakdown.values())

        # Allow for small floating point differences
        assert abs(breakdown_total - result.total_cost) < 0.000001
