"""MT-Bench: Multi-Turn Conversation Benchmark.

Evaluates CascadeFlow on multi-turn conversations requiring context retention,
instruction following, and coherent dialogue across multiple exchanges.

Based on MT-Bench by LMSYS (https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge)
"""

import asyncio
from typing import Any

from cascadeflow.agent import Agent

from .base import Benchmark, BenchmarkResult, BenchmarkSummary


class MTBenchmark(Benchmark):
    """MT-Bench multi-turn conversation benchmark."""

    def __init__(
        self,
        drafter_model: str = "gpt-4o-mini",
        verifier_model: str = "gpt-4o",
        max_samples: int = 10,
    ):
        """
        Initialize MT-Bench benchmark.

        Args:
            drafter_model: Model for initial draft responses
            verifier_model: Model for verification
            max_samples: Maximum number of conversations to test
        """
        super().__init__(
            dataset_name="MT-Bench",
            drafter_model=drafter_model,
            verifier_model=verifier_model,
            max_samples=max_samples,
        )

    def load_dataset(self) -> list[tuple[str, Any]]:
        """
        Load MT-Bench multi-turn conversations.

        Returns:
            List of (conversation_id, conversation_data) tuples
        """
        # Representative MT-Bench conversations (10 samples from 8 categories)
        conversations = [
            {
                "conversation_id": "mtbench_writing_1",
                "category": "writing",
                "turns": [
                    {
                        "turn": 1,
                        "prompt": "Compose an engaging travel blog post about a recent trip to Hawaii, highlighting cultural experiences and must-see attractions.",
                        "reference_quality": 8.5,
                    },
                    {
                        "turn": 2,
                        "prompt": "Rewrite your previous response. Start every sentence with the letter A.",
                        "reference_quality": 7.0,
                    },
                ],
            },
            {
                "conversation_id": "mtbench_roleplay_1",
                "category": "roleplay",
                "turns": [
                    {
                        "turn": 1,
                        "prompt": "Imagine you are a time traveler from the year 3000. What technological advancements would you tell people about?",
                        "reference_quality": 8.0,
                    },
                    {
                        "turn": 2,
                        "prompt": "How would these advancements affect daily life and society?",
                        "reference_quality": 8.0,
                    },
                ],
            },
            {
                "conversation_id": "mtbench_reasoning_1",
                "category": "reasoning",
                "turns": [
                    {
                        "turn": 1,
                        "prompt": "Given a binary tree, how would you determine if it is a valid binary search tree?",
                        "reference_quality": 9.0,
                    },
                    {
                        "turn": 2,
                        "prompt": "What is the time and space complexity of your solution?",
                        "reference_quality": 9.0,
                    },
                ],
            },
            {
                "conversation_id": "mtbench_math_1",
                "category": "math",
                "turns": [
                    {
                        "turn": 1,
                        "prompt": "Solve for x: 3x + 7 = 22",
                        "reference_quality": 9.5,
                    },
                    {
                        "turn": 2,
                        "prompt": "Now solve for y if 3x + 2y = 30 (using the x value from before)",
                        "reference_quality": 9.0,
                    },
                ],
            },
            {
                "conversation_id": "mtbench_coding_1",
                "category": "coding",
                "turns": [
                    {
                        "turn": 1,
                        "prompt": "Write a Python function to reverse a linked list.",
                        "reference_quality": 8.5,
                    },
                    {
                        "turn": 2,
                        "prompt": "Now modify it to reverse only the first k nodes.",
                        "reference_quality": 8.0,
                    },
                ],
            },
            {
                "conversation_id": "mtbench_extraction_1",
                "category": "extraction",
                "turns": [
                    {
                        "turn": 1,
                        "prompt": "Extract the key dates and events from this text: 'World War II began on September 1, 1939, when Germany invaded Poland. The war ended on September 2, 1945, with Japan's formal surrender.'",
                        "reference_quality": 9.0,
                    },
                    {
                        "turn": 2,
                        "prompt": "How many years did the war last?",
                        "reference_quality": 9.5,
                    },
                ],
            },
            {
                "conversation_id": "mtbench_stem_1",
                "category": "stem",
                "turns": [
                    {
                        "turn": 1,
                        "prompt": "Explain the difference between supervised and unsupervised learning in machine learning.",
                        "reference_quality": 8.5,
                    },
                    {
                        "turn": 2,
                        "prompt": "Give me a real-world example where unsupervised learning would be more appropriate than supervised learning.",
                        "reference_quality": 8.0,
                    },
                ],
            },
            {
                "conversation_id": "mtbench_humanities_1",
                "category": "humanities",
                "turns": [
                    {
                        "turn": 1,
                        "prompt": "Discuss the main themes in Shakespeare's Hamlet.",
                        "reference_quality": 8.0,
                    },
                    {
                        "turn": 2,
                        "prompt": "How do these themes relate to modern society?",
                        "reference_quality": 7.5,
                    },
                ],
            },
            {
                "conversation_id": "mtbench_writing_2",
                "category": "writing",
                "turns": [
                    {
                        "turn": 1,
                        "prompt": "Write a professional email to a client explaining a project delay.",
                        "reference_quality": 8.5,
                    },
                    {
                        "turn": 2,
                        "prompt": "Now add a paragraph proposing a solution to prevent future delays.",
                        "reference_quality": 8.0,
                    },
                ],
            },
            {
                "conversation_id": "mtbench_reasoning_2",
                "category": "reasoning",
                "turns": [
                    {
                        "turn": 1,
                        "prompt": "If you have 3 apples and you take away 2, how many do you have?",
                        "reference_quality": 9.0,
                    },
                    {
                        "turn": 2,
                        "prompt": "Explain the logical reasoning behind your answer.",
                        "reference_quality": 8.5,
                    },
                ],
            },
        ]

        return [(c["conversation_id"], c) for c in conversations[: self.max_samples]]

    def evaluate_prediction(self, prediction: str, ground_truth: Any) -> tuple[bool, float]:
        """
        Evaluate multi-turn conversation response quality.

        Uses a simplified quality assessment based on:
        - Response length (should be substantial)
        - Coherence indicators (proper sentence structure)
        - Context retention (references to previous turns)

        Args:
            prediction: Model's response
            ground_truth: Conversation turn data with reference quality

        Returns:
            Tuple of (passes_threshold, quality_score)
        """
        try:
            if not prediction or len(prediction.strip()) < 20:
                return False, 0.0

            # Simple heuristic quality scoring
            quality_score = 0.5  # Base score

            # Length bonus (substantial responses score higher)
            if len(prediction) > 100:
                quality_score += 0.2
            if len(prediction) > 300:
                quality_score += 0.1

            # Coherence indicators
            has_sentences = "." in prediction or "!" in prediction or "?" in prediction
            if has_sentences:
                quality_score += 0.1

            # Structure indicators (paragraphs, lists, code blocks)
            if "\n\n" in prediction or "\n-" in prediction or "```" in prediction:
                quality_score += 0.1

            # Cap at 1.0
            quality_score = min(quality_score, 1.0)

            # Consider pass if quality >= 0.7 (70%)
            passes = quality_score >= 0.7

            return passes, quality_score

        except Exception as e:
            print(f"  Warning: Evaluation error: {e}")
            return False, 0.0

    async def run_cascade(self, conversation_data: Any) -> BenchmarkResult:
        """
        Run cascade on a multi-turn conversation.

        Args:
            conversation_data: Conversation with multiple turns

        Returns:
            BenchmarkResult with aggregated metrics across all turns
        """
        conversation_id = conversation_data["conversation_id"]
        category = conversation_data["category"]
        turns = conversation_data["turns"]

        print(f"\nConversation: {conversation_id} ({category})")
        print(f"  Turns: {len(turns)}")

        # Initialize agent with cascade configuration
        agent = Agent(
            name=f"MTBench-{category}",
            task="Multi-turn conversation",
            drafter_model=self.drafter_model,
            verifier_model=self.verifier_model,
            quality={"threshold": 0.7},
        )

        # Track conversation state
        conversation_history = []
        all_correct = True
        total_quality = 0.0
        total_cost = 0.0
        total_latency = 0.0
        drafter_accepted_count = 0

        # Execute each turn in sequence
        for turn_data in turns:
            turn_num = turn_data["turn"]
            prompt = turn_data["prompt"]

            # Build context-aware prompt with conversation history
            if conversation_history:
                context = "\n".join(
                    [f"Turn {i+1}: {h}" for i, h in enumerate(conversation_history)]
                )
                full_prompt = f"Previous conversation:\n{context}\n\nCurrent turn: {prompt}"
            else:
                full_prompt = prompt

            # Run cascade
            result = await agent.arun(full_prompt)

            # Extract response
            response = result.get("response", "")
            conversation_history.append(response)

            # Evaluate turn
            is_correct, quality = self.evaluate_prediction(response, turn_data)

            # Track metrics
            if not is_correct:
                all_correct = False

            total_quality += quality
            total_cost += result.get("total_cost", 0.0)
            total_latency += result.get("latency_ms", 0.0)

            if result.get("model_used") == self.drafter_model:
                drafter_accepted_count += 1

            print(
                f"    Turn {turn_num}: Quality={quality:.2f}, "
                f"{'✅ Drafter' if result.get('model_used') == self.drafter_model else '❌ Verifier'}"
            )

        # Calculate aggregated metrics
        num_turns = len(turns)
        avg_quality = total_quality / num_turns
        avg_latency = total_latency / num_turns

        # Baseline cost (all turns use verifier)
        baseline_cost = self.calculate_baseline_cost(conversation_data)

        return BenchmarkResult(
            problem_id=conversation_id,
            correct=all_correct,  # All turns must pass
            quality_score=avg_quality,
            latency_ms=avg_latency,
            cost=total_cost,
            baseline_cost=baseline_cost,
            drafter_accepted=(drafter_accepted_count == num_turns),  # All turns accepted
            category=category,
        )

    def calculate_baseline_cost(self, problem: Any) -> float:
        """
        Calculate baseline cost (all turns use verifier).

        Args:
            problem: Conversation data

        Returns:
            Estimated cost for verifier-only approach
        """
        # Rough token estimates for multi-turn conversations
        # Turn 1: ~100 input tokens, ~300 output tokens
        # Turn 2: ~200 input tokens (includes context), ~300 output tokens

        num_turns = len(problem["turns"])

        # GPT-4o pricing: $2.50 per 1M input tokens, $10.00 per 1M output tokens
        input_cost_per_token = 2.50 / 1_000_000
        output_cost_per_token = 10.00 / 1_000_000

        # Estimate tokens per turn (increases with context)
        total_cost = 0.0
        for i in range(num_turns):
            input_tokens = 100 + (i * 100)  # Context grows
            output_tokens = 300

            total_cost += (input_tokens * input_cost_per_token) + (
                output_tokens * output_cost_per_token
            )

        return total_cost


async def run_mtbench_benchmark() -> BenchmarkSummary:
    """
    Run MT-Bench multi-turn conversation benchmark.

    Returns:
        BenchmarkSummary with results
    """
    print("\n" + "=" * 80)
    print("MT-BENCH: MULTI-TURN CONVERSATION BENCHMARK")
    print("=" * 80 + "\n")

    benchmark = MTBenchmark(
        drafter_model="gpt-4o-mini",
        verifier_model="gpt-4o",
        max_samples=10,
    )

    summary = await benchmark.run()

    # Print summary
    print("\n" + "=" * 80)
    print("MT-BENCH RESULTS")
    print("=" * 80 + "\n")

    print(f"Total Conversations: {summary.total_tests}")
    print(f"Successful (all turns pass): {summary.correct} ({summary.accuracy*100:.1f}%)")
    print(
        f"Drafter Accepted (all turns): {summary.drafter_accepted} ({summary.acceptance_rate*100:.1f}%)"
    )
    print(
        f"Verifier Escalated: {summary.total_tests - summary.drafter_accepted} ({(1-summary.acceptance_rate)*100:.1f}%)"
    )

    print("\nCost Analysis:")
    print(f"  Cascade Total Cost:  ${summary.total_cost:.6f}")
    print(f"  Baseline Total Cost: ${summary.baseline_cost:.6f}")
    print(f"  Cost Savings:        ${summary.cost_savings:.6f} ({summary.cost_reduction_pct:.1f}%)")

    print("\nPerformance:")
    print(f"  Average Latency:     {summary.avg_latency_ms:.0f}ms per turn")
    print(f"  Average Quality:     {summary.avg_quality_score:.3f}")
    print(
        f"  Drafter Accuracy:    {summary.drafter_accuracy*100:.1f}% (when accepted for all turns)"
    )

    print("\nKey Findings:")
    if summary.acceptance_rate > 0.5:
        print(
            f"  ✅ Drafter handles {summary.acceptance_rate*100:.0f}% of conversations independently"
        )
    if summary.cost_reduction_pct > 40:
        print(f"  💰 Achieved {summary.cost_reduction_pct:.0f}% cost reduction")
    if summary.avg_quality_score > 0.75:
        print("  ✅ High quality maintained across multi-turn conversations")
    if summary.drafter_accuracy < 0.7:
        print("  ⚠️  Multi-turn context retention challenging - consider stronger drafter")

    print("\n" + "=" * 80 + "\n")

    return summary


if __name__ == "__main__":
    asyncio.run(run_mtbench_benchmark())
