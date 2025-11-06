"""
Tests for Multi-Step Cascade Pipelines (Phase 4.1)

Tests the cascade pipeline data structures and built-in strategies.
"""

import pytest

from cascadeflow.routing.cascade_pipeline import (
    CascadeExecutionResult,
    CascadeStep,
    DomainCascadeStrategy,
    StepResult,
    StepStatus,
    ValidationMethod,
    get_code_strategy,
    get_data_strategy,
    get_general_strategy,
    get_medical_strategy,
    get_strategy_for_domain,
    list_available_strategies,
)
from cascadeflow.routing.domain import Domain

# ============================================================================
# TEST: CascadeStep
# ============================================================================


class TestCascadeStep:
    """Test CascadeStep dataclass."""

    def test_cascade_step_creation(self):
        """Test creating a cascade step."""
        step = CascadeStep(
            name="draft",
            model="gpt-4o-mini",
            provider="openai",
            validation=ValidationMethod.QUALITY_CHECK,
            quality_threshold=0.7,
            fallback_only=False,
        )

        assert step.name == "draft"
        assert step.model == "gpt-4o-mini"
        assert step.provider == "openai"
        assert step.validation == ValidationMethod.QUALITY_CHECK
        assert step.quality_threshold == 0.7
        assert step.fallback_only is False
        assert step.max_tokens == 1000  # Default
        assert step.temperature == 0.7  # Default

    def test_cascade_step_with_metadata(self):
        """Test cascade step with custom metadata."""
        step = CascadeStep(
            name="verify",
            model="gpt-4",
            provider="openai",
            metadata={"step_type": "verify", "expensive": True},
        )

        assert step.metadata["step_type"] == "verify"
        assert step.metadata["expensive"] is True

    def test_cascade_step_validation_threshold_range(self):
        """Test quality_threshold must be between 0 and 1."""
        # Valid thresholds
        step = CascadeStep(name="test", model="gpt-4", provider="openai", quality_threshold=0.0)
        assert step.quality_threshold == 0.0

        step = CascadeStep(name="test", model="gpt-4", provider="openai", quality_threshold=1.0)
        assert step.quality_threshold == 1.0

        # Invalid thresholds
        with pytest.raises(ValueError, match="quality_threshold must be between 0 and 1"):
            CascadeStep(name="test", model="gpt-4", provider="openai", quality_threshold=-0.1)

        with pytest.raises(ValueError, match="quality_threshold must be between 0 and 1"):
            CascadeStep(name="test", model="gpt-4", provider="openai", quality_threshold=1.5)

    def test_cascade_step_max_tokens_validation(self):
        """Test max_tokens must be positive."""
        # Valid
        step = CascadeStep(name="test", model="gpt-4", provider="openai", max_tokens=1)
        assert step.max_tokens == 1

        # Invalid
        with pytest.raises(ValueError, match="max_tokens must be positive"):
            CascadeStep(name="test", model="gpt-4", provider="openai", max_tokens=0)

        with pytest.raises(ValueError, match="max_tokens must be positive"):
            CascadeStep(name="test", model="gpt-4", provider="openai", max_tokens=-100)

    def test_cascade_step_temperature_validation(self):
        """Test temperature must be between 0 and 2."""
        # Valid
        step = CascadeStep(name="test", model="gpt-4", provider="openai", temperature=0.0)
        assert step.temperature == 0.0

        step = CascadeStep(name="test", model="gpt-4", provider="openai", temperature=2.0)
        assert step.temperature == 2.0

        # Invalid
        with pytest.raises(ValueError, match="temperature must be between 0 and 2"):
            CascadeStep(name="test", model="gpt-4", provider="openai", temperature=-0.1)

        with pytest.raises(ValueError, match="temperature must be between 0 and 2"):
            CascadeStep(name="test", model="gpt-4", provider="openai", temperature=2.5)


# ============================================================================
# TEST: StepResult
# ============================================================================


class TestStepResult:
    """Test StepResult dataclass."""

    def test_step_result_creation(self):
        """Test creating a step result."""
        result = StepResult(
            step_name="draft",
            status=StepStatus.SUCCESS,
            response="Generated code here",
            quality_score=0.85,
            cost=0.0014,
            latency_ms=250.0,
            tokens_used=150,
        )

        assert result.step_name == "draft"
        assert result.status == StepStatus.SUCCESS
        assert result.response == "Generated code here"
        assert result.quality_score == 0.85
        assert result.cost == 0.0014
        assert result.latency_ms == 250.0
        assert result.tokens_used == 150

    def test_step_result_with_error(self):
        """Test step result with error."""
        result = StepResult(
            step_name="draft",
            status=StepStatus.FAILED_ERROR,
            error="API timeout",
        )

        assert result.status == StepStatus.FAILED_ERROR
        assert result.error == "API timeout"
        assert result.response is None

    def test_step_result_with_validation_details(self):
        """Test step result with validation details."""
        result = StepResult(
            step_name="draft",
            status=StepStatus.FAILED_QUALITY,
            quality_score=0.45,
            validation_details={
                "passed_checks": ["length", "diversity"],
                "failed_checks": ["completeness"],
                "threshold": 0.7,
            },
        )

        assert result.validation_details["threshold"] == 0.7
        assert "completeness" in result.validation_details["failed_checks"]


# ============================================================================
# TEST: DomainCascadeStrategy
# ============================================================================


class TestDomainCascadeStrategy:
    """Test DomainCascadeStrategy dataclass."""

    def test_strategy_creation(self):
        """Test creating a domain cascade strategy."""
        steps = [
            CascadeStep(name="draft", model="gpt-4o-mini", provider="openai"),
            CascadeStep(name="verify", model="gpt-4", provider="openai", fallback_only=True),
        ]

        strategy = DomainCascadeStrategy(
            domain=Domain.CODE,
            steps=steps,
            description="Test strategy",
        )

        assert strategy.domain == Domain.CODE
        assert len(strategy.steps) == 2
        assert strategy.description == "Test strategy"
        assert strategy.enabled is True

    def test_strategy_requires_steps(self):
        """Test strategy must have at least one step."""
        with pytest.raises(ValueError, match="must have at least one step"):
            DomainCascadeStrategy(domain=Domain.CODE, steps=[])

    def test_strategy_first_step_cannot_be_fallback_only(self):
        """Test first step cannot be fallback-only."""
        steps = [
            CascadeStep(name="fallback", model="gpt-4", provider="openai", fallback_only=True),
        ]

        with pytest.raises(ValueError, match="First step cannot be fallback-only"):
            DomainCascadeStrategy(domain=Domain.CODE, steps=steps)

    def test_strategy_get_step(self):
        """Test getting step by name."""
        steps = [
            CascadeStep(name="draft", model="gpt-4o-mini", provider="openai"),
            CascadeStep(name="verify", model="gpt-4", provider="openai"),
        ]
        strategy = DomainCascadeStrategy(domain=Domain.CODE, steps=steps)

        draft_step = strategy.get_step("draft")
        assert draft_step is not None
        assert draft_step.name == "draft"
        assert draft_step.model == "gpt-4o-mini"

        nonexistent = strategy.get_step("nonexistent")
        assert nonexistent is None

    def test_strategy_get_fallback_steps(self):
        """Test getting fallback-only steps."""
        steps = [
            CascadeStep(name="draft", model="gpt-4o-mini", provider="openai", fallback_only=False),
            CascadeStep(name="verify", model="gpt-4", provider="openai", fallback_only=True),
            CascadeStep(name="safety", model="gpt-4", provider="openai", fallback_only=True),
        ]
        strategy = DomainCascadeStrategy(domain=Domain.CODE, steps=steps)

        fallback_steps = strategy.get_fallback_steps()
        assert len(fallback_steps) == 2
        assert all(step.fallback_only for step in fallback_steps)
        assert fallback_steps[0].name == "verify"
        assert fallback_steps[1].name == "safety"


# ============================================================================
# TEST: CascadeExecutionResult
# ============================================================================


class TestCascadeExecutionResult:
    """Test CascadeExecutionResult dataclass."""

    def test_execution_result_creation(self):
        """Test creating an execution result."""
        steps_executed = [
            StepResult(
                step_name="draft",
                status=StepStatus.SUCCESS,
                response="Code here",
                cost=0.0014,
                latency_ms=250.0,
                tokens_used=150,
                quality_score=0.85,
            )
        ]

        result = CascadeExecutionResult(
            success=True,
            domain=Domain.CODE,
            strategy_used="code_strategy",
            final_response="Code here",
            steps_executed=steps_executed,
            total_cost=0.0014,
            total_latency_ms=250.0,
            total_tokens=150,
            quality_score=0.85,
            fallback_used=False,
        )

        assert result.success is True
        assert result.domain == Domain.CODE
        assert result.total_cost == 0.0014
        assert result.fallback_used is False
        assert len(result.steps_executed) == 1

    def test_execution_result_get_step_result(self):
        """Test getting specific step result."""
        steps_executed = [
            StepResult(step_name="draft", status=StepStatus.SUCCESS, cost=0.001),
            StepResult(step_name="verify", status=StepStatus.SUCCESS, cost=0.030),
        ]

        result = CascadeExecutionResult(
            success=True,
            domain=Domain.CODE,
            strategy_used="test",
            final_response="test",
            steps_executed=steps_executed,
            total_cost=0.031,
            total_latency_ms=500.0,
            total_tokens=200,
            quality_score=0.9,
            fallback_used=True,
        )

        draft_result = result.get_step_result("draft")
        assert draft_result is not None
        assert draft_result.step_name == "draft"
        assert draft_result.cost == 0.001

        nonexistent = result.get_step_result("nonexistent")
        assert nonexistent is None

    def test_execution_result_get_cost_breakdown(self):
        """Test getting cost breakdown by step."""
        steps_executed = [
            StepResult(step_name="draft", status=StepStatus.SUCCESS, cost=0.001),
            StepResult(step_name="verify", status=StepStatus.SUCCESS, cost=0.030),
        ]

        result = CascadeExecutionResult(
            success=True,
            domain=Domain.CODE,
            strategy_used="test",
            final_response="test",
            steps_executed=steps_executed,
            total_cost=0.031,
            total_latency_ms=500.0,
            total_tokens=200,
            quality_score=0.9,
            fallback_used=True,
        )

        breakdown = result.get_cost_breakdown()
        assert breakdown["draft"] == 0.001
        assert breakdown["verify"] == 0.030

    def test_execution_result_get_successful_steps(self):
        """Test getting only successful steps."""
        steps_executed = [
            StepResult(step_name="draft", status=StepStatus.FAILED_QUALITY, cost=0.001),
            StepResult(step_name="verify", status=StepStatus.SUCCESS, cost=0.030),
        ]

        result = CascadeExecutionResult(
            success=True,
            domain=Domain.CODE,
            strategy_used="test",
            final_response="test",
            steps_executed=steps_executed,
            total_cost=0.031,
            total_latency_ms=500.0,
            total_tokens=200,
            quality_score=0.9,
            fallback_used=True,
        )

        successful = result.get_successful_steps()
        assert len(successful) == 1
        assert successful[0].step_name == "verify"


# ============================================================================
# TEST: Built-in Strategies
# ============================================================================


class TestBuiltInStrategies:
    """Test built-in cascade strategies."""

    def test_get_code_strategy(self):
        """Test CODE domain strategy."""
        strategy = get_code_strategy()

        assert strategy.domain == Domain.CODE
        assert len(strategy.steps) == 2
        assert strategy.steps[0].name == "draft"
        assert strategy.steps[0].model == "deepseek-coder"
        assert strategy.steps[0].validation == ValidationMethod.SYNTAX_CHECK
        assert strategy.steps[0].fallback_only is False
        assert strategy.steps[1].name == "verify"
        assert strategy.steps[1].model == "gpt-4o"
        assert strategy.steps[1].fallback_only is True

    def test_get_medical_strategy(self):
        """Test MEDICAL domain strategy."""
        strategy = get_medical_strategy()

        assert strategy.domain == Domain.MEDICAL
        assert len(strategy.steps) == 2
        assert strategy.steps[0].name == "draft"
        assert strategy.steps[0].model == "gpt-4o-mini"
        assert strategy.steps[0].validation == ValidationMethod.FACT_CHECK
        assert strategy.steps[0].temperature == 0.2  # Low for medical
        assert strategy.steps[1].name == "verify"
        assert strategy.steps[1].validation == ValidationMethod.SAFETY_CHECK
        assert strategy.steps[1].quality_threshold == 0.9  # High for medical

    def test_get_general_strategy(self):
        """Test GENERAL domain strategy."""
        strategy = get_general_strategy()

        assert strategy.domain == Domain.GENERAL
        assert len(strategy.steps) == 2
        assert strategy.steps[0].model == "llama-3.1-70b-versatile"
        assert strategy.steps[0].provider == "groq"
        assert strategy.steps[1].model == "gpt-4o"

    def test_get_data_strategy(self):
        """Test DATA domain strategy."""
        strategy = get_data_strategy()

        assert strategy.domain == Domain.DATA
        assert len(strategy.steps) == 2
        assert strategy.steps[0].temperature == 0.3  # Low for data
        assert strategy.steps[1].quality_threshold == 0.85

    def test_get_strategy_for_domain(self):
        """Test getting strategy for a domain."""
        code_strategy = get_strategy_for_domain(Domain.CODE)
        assert code_strategy is not None
        assert code_strategy.domain == Domain.CODE

        medical_strategy = get_strategy_for_domain(Domain.MEDICAL)
        assert medical_strategy is not None
        assert medical_strategy.domain == Domain.MEDICAL

        # Domain without built-in strategy
        conversation_strategy = get_strategy_for_domain(Domain.CONVERSATION)
        assert conversation_strategy is None

    def test_list_available_strategies(self):
        """Test listing available strategies."""
        available = list_available_strategies()

        assert Domain.CODE in available
        assert Domain.MEDICAL in available
        assert Domain.GENERAL in available
        assert Domain.DATA in available
        assert Domain.MATH in available
        assert Domain.STRUCTURED in available
        assert len(available) == 6


# ============================================================================
# TEST: ValidationMethod Enum
# ============================================================================


class TestValidationMethod:
    """Test ValidationMethod enum."""

    def test_validation_methods_exist(self):
        """Test all validation methods are defined."""
        assert ValidationMethod.NONE == "none"
        assert ValidationMethod.SYNTAX_CHECK == "syntax_check"
        assert ValidationMethod.FACT_CHECK == "fact_check"
        assert ValidationMethod.SAFETY_CHECK == "safety_check"
        assert ValidationMethod.QUALITY_CHECK == "quality_check"
        assert ValidationMethod.FULL_QUALITY == "full_quality"
        assert ValidationMethod.CUSTOM == "custom"


# ============================================================================
# TEST: StepStatus Enum
# ============================================================================


class TestStepStatus:
    """Test StepStatus enum."""

    def test_step_statuses_exist(self):
        """Test all step statuses are defined."""
        assert StepStatus.PENDING == "pending"
        assert StepStatus.RUNNING == "running"
        assert StepStatus.SUCCESS == "success"
        assert StepStatus.FAILED_QUALITY == "failed_quality"
        assert StepStatus.FAILED_ERROR == "failed_error"
        assert StepStatus.SKIPPED == "skipped"


# ============================================================================
# TEST: Strategy Configuration
# ============================================================================


class TestStrategyConfiguration:
    """Test strategy configuration patterns."""

    def test_all_strategies_have_draft_and_verify(self):
        """Test all built-in strategies follow draft→verify pattern."""
        strategies = [
            get_code_strategy(),
            get_medical_strategy(),
            get_general_strategy(),
            get_data_strategy(),
        ]

        for strategy in strategies:
            assert len(strategy.steps) >= 2
            assert strategy.steps[0].name == "draft"
            assert strategy.steps[0].fallback_only is False
            # At least one fallback step
            fallback_steps = [s for s in strategy.steps if s.fallback_only]
            assert len(fallback_steps) >= 1

    def test_strategies_use_appropriate_temperatures(self):
        """Test strategies use domain-appropriate temperatures."""
        # CODE and DATA should use low temperature (0.3)
        code_strategy = get_code_strategy()
        assert code_strategy.steps[0].temperature == 0.3

        data_strategy = get_data_strategy()
        assert data_strategy.steps[0].temperature == 0.3

        # MEDICAL should use very low temperature (0.2)
        medical_strategy = get_medical_strategy()
        assert medical_strategy.steps[0].temperature == 0.2

        # GENERAL should use moderate temperature (0.7)
        general_strategy = get_general_strategy()
        assert general_strategy.steps[0].temperature == 0.7

    def test_strategies_use_appropriate_validation(self):
        """Test strategies use domain-appropriate validation."""
        code_strategy = get_code_strategy()
        assert code_strategy.steps[0].validation == ValidationMethod.SYNTAX_CHECK

        medical_strategy = get_medical_strategy()
        assert medical_strategy.steps[0].validation == ValidationMethod.FACT_CHECK
        assert medical_strategy.steps[1].validation == ValidationMethod.SAFETY_CHECK

        general_strategy = get_general_strategy()
        assert general_strategy.steps[0].validation == ValidationMethod.QUALITY_CHECK

    def test_fallback_steps_use_expensive_models(self):
        """Test fallback steps use more capable/expensive models."""
        strategies = [
            get_code_strategy(),
            get_medical_strategy(),
            get_general_strategy(),
            get_data_strategy(),
        ]

        for strategy in strategies:
            fallback_steps = [s for s in strategy.steps if s.fallback_only]
            # Fallback steps should use GPT-4 or GPT-4o
            for step in fallback_steps:
                assert "gpt-4" in step.model.lower()
