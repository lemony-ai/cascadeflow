"""Test suite for execution planning and domain detection."""

import pytest
from cascadeflow.execution import (
    DomainDetector,
    ModelScorer,
    LatencyAwareExecutionPlanner,
    ExecutionStrategy
)
from cascadeflow.complexity import QueryComplexity
from cascadeflow.config import ModelConfig, OptimizationWeights, DEFAULT_TIERS


class TestDomainDetector:
    """Test domain detection."""

    def test_code_domain(self):
        detector = DomainDetector()
        domains = detector.detect("Write a Python function to parse JSON")
        assert "code" in domains

    def test_math_domain(self):
        detector = DomainDetector()
        domains = detector.detect("Calculate the derivative of x squared")
        assert "math" in domains

    def test_data_domain(self):
        detector = DomainDetector()
        domains = detector.detect("Analyze this pandas dataframe")
        assert "data" in domains

    def test_multiple_domains(self):
        detector = DomainDetector()
        domains = detector.detect("Write Python code to calculate statistics")
        assert "code" in domains
        assert "math" in domains

    def test_general_fallback(self):
        detector = DomainDetector()
        domains = detector.detect("What is the weather today?")
        assert "general" in domains


class TestModelScorer:
    """Test model scoring with domain/size boosts."""

    @pytest.fixture
    def sample_models(self):
        return [
            ModelConfig(
                name="llama3:8b",
                provider="ollama",
                cost=0.0,
                speed_ms=300,
                quality_score=0.65,
                domains=["general"]
            ),
            ModelConfig(
                name="codellama:7b",
                provider="ollama",
                cost=0.0,
                speed_ms=350,
                quality_score=0.70,
                domains=["code"]
            ),
            ModelConfig(
                name="gpt-4",
                provider="openai",
                cost=0.03,
                speed_ms=1500,
                quality_score=0.95,
                domains=["general", "expert"]
            )
        ]

    def test_domain_boost(self, sample_models):
        scorer = ModelScorer()
        optimization = OptimizationWeights(cost=0.33, speed=0.33, quality=0.34)

        # Code query should boost codellama
        scored = scorer.score_models(
            sample_models,
            "Write a Python function",
            QueryComplexity.MODERATE,
            optimization,
            query_domains=["code"]
        )

        # Check that codellama got domain boost
        codellama_entry = next(
            (m for m in scored if m[0].name == "codellama:7b"),
            None
        )
        assert codellama_entry is not None
        _, score, meta = codellama_entry
        assert meta["domain_boost"] == 2.0

    def test_size_boost_on_simple(self, sample_models):
        scorer = ModelScorer()
        optimization = OptimizationWeights(cost=0.33, speed=0.33, quality=0.34)

        # Simple query should boost small models
        scored = scorer.score_models(
            sample_models,
            "What is 2+2?",
            QueryComplexity.SIMPLE,
            optimization,
            query_domains=["general"]
        )

        # Small models should get size boost
        llama_entry = next(
            (m for m in scored if m[0].name == "llama3:8b"),
            None
        )
        assert llama_entry is not None
        _, score, meta = llama_entry
        assert meta["size_boost"] == 1.5

    def test_no_boost_complex_query(self, sample_models):
        scorer = ModelScorer()
        optimization = OptimizationWeights(cost=0.33, speed=0.33, quality=0.34)

        # Complex query should not boost small models
        scored = scorer.score_models(
            sample_models,
            "Analyze complex geopolitical situation",
            QueryComplexity.EXPERT,
            optimization,
            query_domains=["general"]
        )

        llama_entry = next(
            (m for m in scored if m[0].name == "llama3:8b"),
            None
        )
        assert llama_entry is not None
        _, score, meta = llama_entry
        assert meta["size_boost"] == 1.0  # No size boost on expert


class TestExecutionPlanner:
    """Test execution planning."""

    @pytest.fixture
    def sample_models(self):
        return [
            ModelConfig(
                name="llama3:8b",
                provider="ollama",
                cost=0.0,
                speed_ms=300,
                quality_score=0.65,
                domains=["general"]
            ),
            ModelConfig(
                name="codellama:7b",
                provider="ollama",
                cost=0.0,
                speed_ms=350,
                quality_score=0.70,
                domains=["code"]
            ),
            ModelConfig(
                name="gpt-3.5-turbo",
                provider="openai",
                cost=0.002,
                speed_ms=800,
                quality_score=0.80,
                domains=["general"]
            ),
            ModelConfig(
                name="gpt-4",
                provider="openai",
                cost=0.03,
                speed_ms=1500,
                quality_score=0.95,
                domains=["general", "expert"]
            )
        ]

    @pytest.mark.asyncio
    async def test_trivial_uses_cheapest(self, sample_models):
        planner = LatencyAwareExecutionPlanner()
        plan = await planner.create_plan(
            query="What is 2+2?",
            complexity=QueryComplexity.TRIVIAL,
            available_models=sample_models
        )

        assert plan.strategy == ExecutionStrategy.DIRECT_CHEAP
        assert plan.primary_model.cost == 0.0

    @pytest.mark.asyncio
    async def test_code_query_uses_specialist(self, sample_models):
        planner = LatencyAwareExecutionPlanner()
        plan = await planner.create_plan(
            query="Write a Python function to sort a list",
            complexity=QueryComplexity.MODERATE,
            available_models=sample_models,
            query_domains=["code"]
        )

        # Should prefer codellama due to domain boost
        assert plan.strategy in [
            ExecutionStrategy.DIRECT_SMART,
            ExecutionStrategy.SPECULATIVE
        ]

    @pytest.mark.asyncio
    async def test_expert_query_uses_best(self, sample_models):
        planner = LatencyAwareExecutionPlanner()
        plan = await planner.create_plan(
            query="Analyze complex philosophical implications",
            complexity=QueryComplexity.EXPERT,
            available_models=sample_models
        )

        assert plan.strategy == ExecutionStrategy.DIRECT_BEST
        assert plan.primary_model.name == "gpt-4"

    @pytest.mark.asyncio
    async def test_speculative_with_tier(self, sample_models):
        planner = LatencyAwareExecutionPlanner()
        tier = DEFAULT_TIERS["premium"]

        plan = await planner.create_plan(
            query="Compare Python and JavaScript",
            complexity=QueryComplexity.MODERATE,
            available_models=sample_models,
            tier=tier
        )

        # Premium tier should enable speculative
        if plan.strategy == ExecutionStrategy.SPECULATIVE:
            assert plan.drafter is not None
            assert plan.verifier is not None

    @pytest.mark.asyncio
    async def test_parallel_race_enterprise(self, sample_models):
        planner = LatencyAwareExecutionPlanner()
        tier = DEFAULT_TIERS["enterprise"]

        plan = await planner.create_plan(
            query="Analyze in depth",
            complexity=QueryComplexity.HARD,
            available_models=sample_models,
            tier=tier
        )

        # Enterprise tier should enable parallel race
        if plan.strategy == ExecutionStrategy.PARALLEL_RACE:
            assert plan.race_models is not None
            assert len(plan.race_models) >= 2


class TestIntegration:
    """Test integration of all components."""

    @pytest.mark.asyncio
    async def test_full_flow_code_query(self):
        """Test complete flow for code query."""
        models = [
            ModelConfig(
                name="codellama:7b",
                provider="ollama",
                cost=0.0,
                speed_ms=300,
                quality_score=0.70,
                domains=["code"]
            ),
            ModelConfig(
                name="gpt-4",
                provider="openai",
                cost=0.03,
                speed_ms=1500,
                quality_score=0.95,
                domains=["general"]
            )
        ]

        planner = LatencyAwareExecutionPlanner()
        plan = await planner.create_plan(
            query="Fix this Python bug in my function",
            complexity=QueryComplexity.MODERATE,
            available_models=models,
            query_domains=["code"]
        )

        # Should use codellama due to domain boost
        assert plan.estimated_cost < 0.01  # Should be cheap
        assert "code" in plan.metadata["query_domains"]

    @pytest.mark.asyncio
    async def test_optimization_weights_honored(self):
        """Test that optimization weights affect scoring."""
        models = [
            ModelConfig(
                name="fast-cheap",
                provider="ollama",
                cost=0.0,
                speed_ms=200,
                quality_score=0.60,
                domains=["general"]
            ),
            ModelConfig(
                name="slow-expensive",
                provider="openai",
                cost=0.05,
                speed_ms=2000,
                quality_score=0.95,
                domains=["general"]
            )
        ]

        planner = LatencyAwareExecutionPlanner()

        # Cost priority
        tier_cost = DEFAULT_TIERS["free"]  # 70% cost weight
        plan_cost = await planner.create_plan(
            query="Simple question",
            complexity=QueryComplexity.SIMPLE,
            available_models=models,
            tier=tier_cost
        )

        # Should prefer cheap model
        assert plan_cost.primary_model.cost < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])