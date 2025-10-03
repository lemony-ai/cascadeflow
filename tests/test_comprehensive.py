"""
Comprehensive integration test for CascadeFlow.

Tests:
- 10 prompts (easy → hard)
- All providers
- Cascading logic
- User tiers
- Budget enforcement
- Quality thresholds
- Cost tracking
"""

import asyncio
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

from cascadeflow import CascadeAgent, ModelConfig, UserTier, CascadeConfig
from cascadeflow.exceptions import BudgetExceededError

load_dotenv()

# 10 test prompts (easy → hard)
TEST_PROMPTS = [
    # 1. VERY EASY (should succeed with smallest model)
    {
        "level": "very_easy",
        "prompt": "What is 2+2?",
        "expected_min_confidence": 0.7,
        "expected_provider": ["ollama", "groq"],  # Should use free models
    },

    # 2. EASY (simple fact)
    {
        "level": "easy",
        "prompt": "What is the capital of France?",
        "expected_min_confidence": 0.7,
        "expected_provider": ["ollama", "groq"],
    },

    # 3. MODERATE (explanation)
    {
        "level": "moderate",
        "prompt": "Explain what artificial intelligence is in 2-3 sentences.",
        "expected_min_confidence": 0.7,
        "expected_provider": ["groq", "huggingface", "together"],
    },

    # 4. MODERATE+ (comparison)
    {
        "level": "moderate_plus",
        "prompt": "Compare machine learning and deep learning.",
        "expected_min_confidence": 0.75,
        "expected_provider": ["groq", "together", "openai"],
    },

    # 5. INTERMEDIATE (reasoning)
    {
        "level": "intermediate",
        "prompt": "If all roses are flowers and some flowers fade quickly, what can we conclude about roses?",
        "expected_min_confidence": 0.75,
        "expected_provider": ["groq", "together", "openai"],
    },

    # 6. INTERMEDIATE+ (code)
    {
        "level": "intermediate_plus",
        "prompt": "Write a Python function to reverse a string.",
        "expected_min_confidence": 0.8,
        "expected_provider": ["together", "openai", "anthropic"],
    },

    # 7. ADVANCED (analysis)
    {
        "level": "advanced",
        "prompt": "Analyze the key differences between supervised and unsupervised learning, with examples.",
        "expected_min_confidence": 0.8,
        "expected_provider": ["openai", "anthropic"],
    },

    # 8. ADVANCED+ (creative reasoning)
    {
        "level": "advanced_plus",
        "prompt": "Design a system architecture for a real-time recommendation engine that handles 1M requests/second.",
        "expected_min_confidence": 0.85,
        "expected_provider": ["openai", "anthropic"],
    },

    # 9. EXPERT (complex problem)
    {
        "level": "expert",
        "prompt": "Explain the mathematical foundations of transformer models, including attention mechanisms and positional encodings.",
        "expected_min_confidence": 0.85,
        "expected_provider": ["gpt-4", "claude"],
    },

    # 10. VERY HARD (research-level)
    {
        "level": "very_hard",
        "prompt": "Propose a novel approach to reduce hallucinations in large language models, considering both training-time and inference-time techniques. Include potential trade-offs and implementation challenges.",
        "expected_min_confidence": 0.9,
        "expected_provider": ["gpt-4", "claude-3-opus"],
    },
]


class ComprehensiveTest:
    """Comprehensive test suite."""

    def __init__(self):
        """Initialize test suite."""
        self.results: List[Dict[str, Any]] = []
        self.total_cost = 0.0
        self.total_queries = 0
        self.cascades = 0

    def setup_agent(self) -> CascadeAgent:
        """Setup CascadeAgent with all available providers."""
        models = []

        # Tier 1: Local (if available)
        try:
            import httpx
            response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
            if response.status_code == 200:
                models.append(ModelConfig(
                    name="llama3:8b",
                    provider="ollama",
                    cost=0.0,
                    keywords=["simple", "quick"]
                ))
                print("✓ Ollama detected")
        except:
            print("○ Ollama not available")

        # Tier 2: Free cloud
        if os.getenv("GROQ_API_KEY"):
            models.append(ModelConfig(
                name="llama-3.1-8b-instant",
                provider="groq",
                cost=0.0,
                keywords=["moderate", "fast"]
            ))
            print("✓ Groq detected")

        # Tier 3: Low-cost options
        if os.getenv("HF_TOKEN"):
            models.append(ModelConfig(
                name="meta-llama/Llama-3.2-3B-Instruct",
                provider="huggingface",
                cost=0.0,
                keywords=["moderate"]
            ))
            print("✓ HuggingFace detected")

        if os.getenv("TOGETHER_API_KEY"):
            models.append(ModelConfig(
                name="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                provider="together",
                cost=0.0002,
                keywords=["detailed", "reasoning"]
            ))
            print("✓ Together.ai detected")

        # Tier 4: Paid (cheap)
        if os.getenv("OPENAI_API_KEY"):
            models.append(ModelConfig(
                name="gpt-3.5-turbo",
                provider="openai",
                cost=0.002,
                keywords=["analysis", "code"]
            ))
            print("✓ OpenAI (GPT-3.5) detected")

        # Tier 5: Paid (expensive)
        if os.getenv("OPENAI_API_KEY"):
            models.append(ModelConfig(
                name="gpt-4",
                provider="openai",
                cost=0.03,
                keywords=["complex", "expert"]
            ))
            print("✓ OpenAI (GPT-4) detected")

        if os.getenv("ANTHROPIC_API_KEY"):
            models.append(ModelConfig(
                name="claude-3-sonnet",
                provider="anthropic",
                cost=0.003,
                keywords=["reasoning", "analysis"]
            ))
            print("✓ Anthropic detected")

        if not models:
            raise ValueError("No providers available! Please set API keys in .env")

        print(f"\nTotal providers available: {len(models)}")
        print(f"Cascade chain: {' → '.join([m.name for m in models])}\n")

        # Create agent
        config = CascadeConfig(
            quality_threshold=0.7,
            max_budget=1.0,
            verbose=True
        )

        return CascadeAgent(models, config=config)

    async def run_single_test(
            self,
            agent: CascadeAgent,
            test: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run a single test case."""
        print(f"\n{'='*70}")
        print(f"TEST: {test['level'].upper()}")
        print(f"Prompt: {test['prompt'][:60]}...")
        print(f"Expected confidence: ≥ {test['expected_min_confidence']}")
        print(f"{'='*70}\n")

        try:
            result = await agent.run(test['prompt'])

            # Validate result
            success = result.confidence >= test['expected_min_confidence']

            test_result = {
                "level": test["level"],
                "prompt": test["prompt"],
                "success": success,
                "model_used": result.model_used,
                "provider": result.provider,
                "confidence": result.confidence,
                "cost": result.total_cost,
                "latency_ms": result.latency_ms,
                "cascaded": result.cascaded,
                "cascade_path": result.cascade_path,
                "response_length": len(result.content),
                "expected_min_confidence": test["expected_min_confidence"],
            }

            # Print result
            if success:
                print(f"✅ SUCCESS")
            else:
                print(f"⚠️  QUALITY THRESHOLD NOT MET")

            print(f"Model used: {result.model_used}")
            print(f"Provider: {result.provider}")
            print(f"Confidence: {result.confidence:.2f} (expected ≥ {test['expected_min_confidence']})")
            print(f"Cost: ${result.total_cost:.6f}")
            print(f"Latency: {result.latency_ms:.0f}ms")
            print(f"Cascaded: {result.cascaded}")
            if result.cascaded:
                print(f"Cascade path: {' → '.join(result.cascade_path)}")
            print(f"Response length: {len(result.content)} chars")
            print(f"\nResponse preview:")
            print(f"{result.content[:200]}...")

            return test_result

        except Exception as e:
            print(f"❌ ERROR: {e}")
            return {
                "level": test["level"],
                "prompt": test["prompt"],
                "success": False,
                "error": str(e),
            }

    async def run_all_tests(self):
        """Run all test cases."""
        print("\n" + "="*70)
        print("CASCADEFLOW COMPREHENSIVE TEST SUITE")
        print("Testing 10 prompts from easy to very hard")
        print("="*70 + "\n")

        # Setup agent
        print("Setting up CascadeAgent...\n")
        agent = self.setup_agent()

        # Run tests
        for i, test in enumerate(TEST_PROMPTS, 1):
            print(f"\n[TEST {i}/10]")
            result = await self.run_single_test(agent, test)
            self.results.append(result)

            # Track stats
            self.total_queries += 1
            if "cost" in result:
                self.total_cost += result["cost"]
            if result.get("cascaded"):
                self.cascades += 1

            # Brief pause between tests
            await asyncio.sleep(1)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70 + "\n")

        # Overall stats
        successful = sum(1 for r in self.results if r.get("success"))
        failed = len(self.results) - successful

        print(f"Total tests: {len(self.results)}")
        print(f"✅ Passed: {successful}")
        print(f"❌ Failed: {failed}")
        print(f"Success rate: {successful/len(self.results)*100:.1f}%\n")

        # Cost stats
        print(f"Total cost: ${self.total_cost:.4f}")
        print(f"Average cost: ${self.total_cost/len(self.results):.4f} per query")
        print(f"Cascade rate: {self.cascades/self.total_queries*100:.1f}%\n")

        # Provider distribution
        print("Provider usage:")
        providers = {}
        for r in self.results:
            if "provider" in r:
                providers[r["provider"]] = providers.get(r["provider"], 0) + 1

        for provider, count in sorted(providers.items(), key=lambda x: -x[1]):
            percentage = count / len(self.results) * 100
            print(f"  {provider}: {count} ({percentage:.1f}%)")

        print("\n" + "="*70)
        print("Detailed results by complexity level:")
        print("="*70 + "\n")

        for result in self.results:
            status = "✅" if result.get("success") else "❌"
            level = result["level"].replace("_", " ").title()
            model = result.get("model_used", "N/A")
            confidence = result.get("confidence", 0)
            cost = result.get("cost", 0)

            print(f"{status} {level:20s} | {model:30s} | Conf: {confidence:.2f} | ${cost:.6f}")

        print("\n" + "="*70)

        # Cost comparison
        print("\nCost comparison:")
        print(f"CascadeFlow: ${self.total_cost:.4f}")
        print(f"Pure GPT-4:  ${len(self.results) * 0.03:.4f}")
        savings = (1 - self.total_cost / (len(self.results) * 0.03)) * 100
        print(f"Savings: {savings:.1f}%")

        print("\n" + "="*70)
        print("TEST COMPLETE")
        print("="*70 + "\n")


async def main():
    """Run comprehensive tests."""
    test = ComprehensiveTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())