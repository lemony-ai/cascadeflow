"""Test execution planning with domain and semantic integration."""

import pytest
from cascadeflow.schema.config import ModelConfig, OptimizationWeights
from cascadeflow.core.execution import (
    DomainDetector,
    ExecutionStrategy,
    LatencyAwareExecutionPlanner,
    ModelScorer,
)

from cascadeflow.quality.complexity import QueryComplexity


class TestDomainDetector:

    def setup_method(self):
        self.detector = DomainDetector()

    def test_code_detection(self):
        """Test code domain detection."""
        queries = [
            "Fix this Python bug",
            "Implement a React component",
            "Debug this JavaScript function",
        ]
        for query in queries:
            domains = self.detector.detect(query)
            assert "code" in domains

    def test_math_detection(self):
        """Test math domain detection."""
        queries = [
            "Solve this equation",
            "Calculate the derivative",
            "What is the probability",
        ]
        for query in queries:
            domains = self.detector.detect(query)
            assert "math" in domains

    def test_multiple_domains(self):
        """Test multiple domain detection."""
        query = "Write Python code to calculate statistical analysis"
        domains = self.detector.detect(query)
        assert "code" in domains
        assert "math" in domains or "data" in domains

    def test_general_fallback(self):
        """Test general domain fallback."""
        query = "Tell me about cats"
        domains = self.detector.detect(query)
        assert domains == ["general"]


class TestModelScorer:

    def setup_method(self):
        self.scorer = ModelScorer()
        self.models = [
            ModelConfig(
                name="llama3:8b",
                provider="ollama",
                cost=0.0,
                speed_ms=500,
                quality_score=0.6,
                domains=["general"],
            ),
            ModelConfig(
                name="codellama",
                provider="ollama",
                cost=0.0,
                speed_ms=600,
                quality_score=0.7,
                domains=["code"],
            ),
            ModelConfig(
                name="gpt-4",
                provider="openai",
                cost=0.03,
                speed_ms=1500,
                quality_score=0.95,
                domains=["general"],
            ),
        ]

    def test_domain_boost(self):
        """Test 2.0x domain boost for specialists."""
        optimization = OptimizationWeights(cost=0.33, speed=0.33, quality=0.34)

        scored = self.scorer.score_models(
            models=self.models,
            query="Fix this Python bug",
            complexity=QueryComplexity.MODERATE,
            optimization=optimization,
            query_domains=["code"],
        )

        # Find codellama in results
        codellama_score = next(
            (meta for model, score, meta in scored if model.name == "codellama"), None
        )

        assert codellama_score is not None
        assert codellama_score["domain_boost"] == 2.0
        print(f"\nCodeLlama score: {codellama_score}")

    def test_size_boost(self):
        """Test 1.5x size boost for small models on simple queries."""
        optimization = OptimizationWeights(cost=0.7, speed=0.15, quality=0.15)

        scored = self.scorer.score_models(
            models=self.models,
            query="What is Python?",
            complexity=QueryComplexity.SIMPLE,
            optimization=optimization,
            query_domains=["general"],
        )

        # Small model (llama3:8b, quality<0.7) should get boost
        llama_result = next(
            (meta for model, score, meta in scored if model.name == "llama3:8b"), None
        )

        assert llama_result is not None
        assert llama_result["size_boost"] == 1.5
        print(f"\nLlama3 score: {llama_result}")

    def test_semantic_boost(self):
        """Test semantic boost integration."""
        optimization = OptimizationWeights(cost=0.33, speed=0.33, quality=0.34)

        semantic_hints = {
            "codellama": 0.85,  # High similarity
            "gpt-4": 0.45,  # Medium similarity
        }

        scored = self.scorer.score_models(
            models=self.models,
            query="Debug Python code",
            complexity=QueryComplexity.MODERATE,
            optimization=optimization,
            query_domains=["code"],
            semantic_hints=semantic_hints,
        )

        codellama_result = next(
            (meta for model, score, meta in scored if model.name == "codellama"), None
        )

        assert codellama_result is not None
        assert codellama_result["semantic_boost"] > 1.0
        print(f"\nCodeLlama with semantic: {codellama_result}")

    def test_combined_boosts(self):
        """Test that multiple boosts multiply together."""
        optimization = OptimizationWeights(cost=0.33, speed=0.33, quality=0.34)

        semantic_hints = {"codellama": 0.75}

        scored = self.scorer.score_models(
            models=self.models,
            query="Fix Python bug",
            complexity=QueryComplexity.MODERATE,
            optimization=optimization,
            query_domains=["code"],
            semantic_hints=semantic_hints,
        )

        codellama_result = next(
            (meta for model, score, meta in scored if model.name == "codellama"), None
        )

        # Should have domain_boost (2.0) * semantic_boost (1.5+)
        combined = codellama_result["combined_boost"]
        assert combined >= 3.0  # 2.0 * 1.5
        print(f"\nCombined boost: {combined:.2f}x")


class TestExecutionPlanner:

    def setup_method(self):
        self.planner = LatencyAwareExecutionPlanner()
        self.models = [
            ModelConfig(
                name="llama3:8b",
                provider="ollama",
                cost=0.0,
                speed_ms=500,
                quality_score=0.6,
                domains=["general"],
            ),
            ModelConfig(
                name="codellama",
                provider="ollama",
                cost=0.0,
                speed_ms=600,
                quality_score=0.7,
                domains=["code"],
            ),
            ModelConfig(
                name="gpt-4",
                provider="openai",
                cost=0.03,
                speed_ms=1500,
                quality_score=0.95,
                domains=["general"],
            ),
        ]

    @pytest.mark.asyncio
    async def test_trivial_query_uses_cheapest(self):
        """Test that trivial queries use cheapest model."""
        plan = await self.planner.create_plan(
            query="What is 2+2?", complexity=QueryComplexity.TRIVIAL, available_models=self.models
        )

        assert plan.strategy == ExecutionStrategy.DIRECT_CHEAP
        assert plan.primary_model.cost == 0.0
        print(f"\nTrivial query plan: {plan.reasoning}")

    @pytest.mark.asyncio
    async def test_code_query_prefers_specialist(self):
        """Test that code queries prefer code specialists."""
        plan = await self.planner.create_plan(
            query="Fix this Python bug",
            complexity=QueryComplexity.MODERATE,
            available_models=self.models,
            query_domains=["code"],
        )

        # Should prefer codellama due to domain boost
        print(f"\nCode query plan: {plan.reasoning}")
        print(f"Top 3 models: {plan.metadata['top_3_models']}")

        top_model = plan.metadata["top_3_models"][0]
        assert top_model["domain_boost"] == 2.0

    @pytest.mark.asyncio
    async def test_semantic_hints_influence(self):
        """Test that semantic hints influence selection."""
        semantic_hints = {
            "codellama": 0.9,  # Very high similarity
            "gpt-4": 0.3,
        }

        plan = await self.planner.create_plan(
            query="Debug Python code",
            complexity=QueryComplexity.MODERATE,
            available_models=self.models,
            query_domains=["code"],
            semantic_hints=semantic_hints,
        )

        assert plan.metadata["semantic_routing_used"] is True
        print(f"\nWith semantic hints: {plan.reasoning}")

        top_model = plan.metadata["top_3_models"][0]
        assert top_model["semantic_boost"] > 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
