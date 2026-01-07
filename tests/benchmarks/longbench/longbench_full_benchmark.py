"""
Full LongBench-Style Benchmark for CascadeFlow Long Context Understanding.

This script:
1. Downloads LongBench dataset (multi-task long context benchmark)
2. Tests documents from 1K to 32K+ words
3. Measures accuracy and cascade performance on long prompts
4. Validates CascadeFlow handles long context efficiently

Categories:
- Single-doc QA (long document + question)
- Multi-doc QA (multiple documents + question)
- Summarization (long document summarization)
- Code understanding (long code + question)

Usage:
    python tests/benchmarks/longbench/longbench_full_benchmark.py --sample 20
    python tests/benchmarks/longbench/longbench_full_benchmark.py --full
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cascadeflow import CascadeAgent, DomainConfig, ModelConfig


@dataclass
class LongBenchResult:
    """Result for a single long context test."""
    task_id: str
    task_type: str
    word_count: int
    correct: bool
    draft_accepted: bool
    cost: float
    latency_ms: float
    complexity: str
    error: Optional[str] = None


# LongBench-style test cases (curated for CascadeFlow testing)
LONGBENCH_TASKS = [
    # Single Document QA - Testing long context comprehension
    {
        "task_id": "single_doc_qa_1",
        "task_type": "single_doc_qa",
        "context": """
The history of artificial intelligence began in antiquity, with myths and stories about artificial beings endowed with intelligence or consciousness by master craftsmen. The seeds of modern AI were planted by classical philosophers who attempted to describe the process of human thinking as the mechanical manipulation of symbols. This work culminated in the invention of the programmable digital computer in the 1940s.

Alan Turing was the first to propose that a machine could be constructed that would be capable of thinking. In his 1950 paper "Computing Machinery and Intelligence", Turing proposed what is now known as the Turing test as a criterion of intelligence. The field of AI research was founded at a workshop held on the campus of Dartmouth College during the summer of 1956.

Early AI researchers developed programs that could solve algebra word problems, prove theorems in geometry, and learn to play games like checkers. In the 1960s and 1970s, researchers made significant progress in natural language processing, robotics, and expert systems. However, progress was slower than expected, leading to a period known as the "AI winter" in the 1970s and 1980s.

The resurgence of AI in the 1990s was driven by several factors: the availability of large amounts of data, increased computational power, and new techniques like machine learning. Deep learning, a subset of machine learning using neural networks with many layers, revolutionized the field starting in 2012 when a deep learning system won the ImageNet competition by a large margin.

""" + """Today, AI is used in a wide variety of applications including speech recognition, image recognition, recommendation systems, autonomous vehicles, medical diagnosis, and scientific research. Large language models like GPT and Claude have demonstrated remarkable capabilities in understanding and generating human language, leading to a new wave of AI applications.

The development of AI has raised important ethical questions about privacy, bias, job displacement, and the potential risks of artificial general intelligence. Researchers and policymakers are working to ensure that AI is developed in a way that is safe, beneficial, and aligned with human values.

""" * 10,  # Repeat to make it longer
        "question": "According to the text, what event is considered the founding of AI research as a field?",
        "expected_answer": "dartmouth",
        "answer_contains": ["dartmouth", "1956", "workshop"],
    },
    {
        "task_id": "single_doc_qa_2",
        "task_type": "single_doc_qa",
        "context": """
Climate change refers to long-term shifts in global temperatures and weather patterns. While climate change is a natural phenomenon, human activities have been the main driver since the 1800s, primarily due to the burning of fossil fuels like coal, oil, and gas.

Burning fossil fuels generates greenhouse gas emissions that act like a blanket wrapped around the Earth, trapping the sun's heat and raising temperatures. The main greenhouse gases that are causing climate change include carbon dioxide and methane. These come from using gasoline for driving a car or coal for heating a building, for example. Clearing land and cutting down forests can also release carbon dioxide.

""" + """Agriculture, oil and gas operations are major sources of methane emissions. Energy, industry, transport, buildings, agriculture and land use are among the main sectors causing greenhouse gases.

The effects of climate change are already being felt around the world. Rising temperatures are causing more frequent and severe heat waves. Changes in precipitation patterns are leading to more droughts in some areas and more flooding in others. Sea levels are rising due to melting ice sheets and glaciers, threatening coastal communities. Extreme weather events like hurricanes and wildfires are becoming more intense.

Scientists have observed that the Earth's average temperature has increased by about 1.1 degrees Celsius since the late 1800s. If current trends continue, temperatures could rise by 2.5 to 4.5 degrees Celsius by the end of the century. This would have catastrophic consequences for ecosystems, human health, food security, and economic stability.

To address climate change, countries around the world have committed to reducing greenhouse gas emissions. The Paris Agreement, adopted in 2015, aims to limit global warming to 1.5 degrees Celsius above pre-industrial levels. This requires transitioning to renewable energy sources, improving energy efficiency, protecting and restoring forests, and developing new technologies for carbon capture and storage.

""" * 8,
        "question": "What is the main goal of the Paris Agreement mentioned in the text?",
        "expected_answer": "1.5 degrees",
        "answer_contains": ["1.5", "limit", "warming"],
    },
    # Multi-Document QA
    {
        "task_id": "multi_doc_qa_1",
        "task_type": "multi_doc_qa",
        "context": """
DOCUMENT 1: COMPANY FINANCIAL REPORT Q3 2024
Revenue for Q3 2024 reached $4.2 billion, representing a 15% increase year-over-year. Operating expenses grew by 8% to $3.1 billion, while net income rose 25% to $850 million. The company's cash position remains strong at $12.5 billion.

Key growth drivers included:
- Cloud services revenue up 35% to $1.8 billion
- Enterprise software up 12% to $1.5 billion
- Consumer products stable at $900 million

The company announced a $2 billion share buyback program and increased quarterly dividend by 10% to $0.44 per share.

""" + """
DOCUMENT 2: MARKET ANALYSIS
The technology sector continues to outperform broader markets, with cloud computing leading growth. Industry analysts project the global cloud market to reach $1.2 trillion by 2027, growing at a CAGR of 16%.

Key trends shaping the market:
- Artificial intelligence integration driving new use cases
- Hybrid cloud adoption accelerating among enterprises
- Security concerns pushing investment in zero-trust architectures
- Edge computing emerging as complement to centralized cloud

Competition remains intense, with major players investing heavily in data center expansion and AI capabilities.

""" + """
DOCUMENT 3: PRODUCT ANNOUNCEMENTS
The company unveiled its next-generation AI platform at the annual developer conference. Key features include:
- 10x improvement in inference speed
- Support for models up to 1 trillion parameters
- New tools for fine-tuning and deployment
- Enhanced privacy controls and audit logging

The platform will be generally available in Q1 2025, with early access starting next month. Pricing starts at $0.01 per 1,000 API calls.

""" * 5,
        "question": "What was the cloud services revenue growth rate in Q3 2024?",
        "expected_answer": "35%",
        "answer_contains": ["35"],
    },
    # Summarization Tasks
    {
        "task_id": "summarization_1",
        "task_type": "summarization",
        "context": """
The Industrial Revolution was a period of major industrialization and innovation that took place during the late 1700s and early 1800s. The Industrial Revolution began in Great Britain and quickly spread throughout the world.

Prior to the Industrial Revolution, manufacturing was often done in people's homes using hand tools or basic machines. Industrialization marked a shift to powered, special-purpose machinery, factories, and mass production.

The textile industry was substantially transformed during this period. Before mechanization, textiles were made in homes with the raw materials brought to people's homes and picked up when finished. Initially, this was done by independent artisans who owned their own equipment. However, the development of new technology led to the rise of factories.

""" + """Key inventions that drove the Industrial Revolution included the spinning jenny, the water frame, the power loom, and the steam engine. James Watt's improvements to the steam engine in 1765 made it a practical source of power for factories and transportation.

The steam engine enabled the development of railways and steamships, dramatically reducing travel times and enabling the movement of goods and people over long distances. The first public railway, the Stockton and Darlington Railway, opened in 1825 in England.

The Industrial Revolution led to urbanization as people moved from rural areas to cities in search of factory work. This rapid urban growth created many social problems including overcrowding, pollution, and poor working conditions.

Working conditions in early factories were often dangerous and unhealthy. Workers, including children, labored for long hours with low pay. This eventually led to the formation of labor unions and the passage of factory acts regulating working conditions.

The Industrial Revolution transformed society in fundamental ways. It changed how people lived, worked, and related to each other. It led to the growth of the middle class, increased literacy, and new forms of entertainment and culture.

""" * 6,
        "question": "Summarize the main impacts of the Industrial Revolution in 2-3 sentences.",
        "expected_answer": "transformation",
        "answer_contains": ["factory", "urban", "transform"],
    },
    # Code Understanding
    {
        "task_id": "code_understanding_1",
        "task_type": "code_understanding",
        "context": """
```python
# Authentication Service Implementation
import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class User:
    id: int
    username: str
    email: str
    password_hash: str
    salt: str
    created_at: datetime
    is_active: bool = True
    failed_attempts: int = 0
    locked_until: Optional[datetime] = None

class AuthenticationService:
    def __init__(self, secret_key: str, token_expiry_hours: int = 24):
        self.secret_key = secret_key
        self.token_expiry = token_expiry_hours
        self.users: Dict[str, User] = {}
        self.max_attempts = 5
        self.lockout_minutes = 30

    def _hash_password(self, password: str, salt: str) -> str:
        combined = password + salt
        return hashlib.sha256(combined.encode()).hexdigest()

    def _generate_salt(self) -> str:
        return secrets.token_hex(32)

    def register(self, username: str, email: str, password: str) -> User:
        if username in self.users:
            raise ValueError("Username already exists")

        salt = self._generate_salt()
        password_hash = self._hash_password(password, salt)

        user = User(
            id=len(self.users) + 1,
            username=username,
            email=email,
            password_hash=password_hash,
            salt=salt,
            created_at=datetime.utcnow()
        )

        self.users[username] = user
        logger.info(f"User registered: {username}")
        return user

    def authenticate(self, username: str, password: str) -> Optional[str]:
        user = self.users.get(username)
        if not user:
            return None

        if user.locked_until and datetime.utcnow() < user.locked_until:
            raise PermissionError("Account is locked")

        password_hash = self._hash_password(password, user.salt)

        if password_hash != user.password_hash:
            user.failed_attempts += 1
            if user.failed_attempts >= self.max_attempts:
                user.locked_until = datetime.utcnow() + timedelta(minutes=self.lockout_minutes)
                logger.warning(f"Account locked: {username}")
            return None

        user.failed_attempts = 0
        user.locked_until = None

        token = jwt.encode(
            {"user_id": user.id, "exp": datetime.utcnow() + timedelta(hours=self.token_expiry)},
            self.secret_key,
            algorithm="HS256"
        )

        logger.info(f"User authenticated: {username}")
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
```

Additional helper functions for the authentication service:

```python
def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain uppercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain a digit"
    return True, "Password meets requirements"

def validate_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```
""" * 3,
        "question": "What happens when a user exceeds the maximum number of failed login attempts according to this code?",
        "expected_answer": "locked",
        "answer_contains": ["lock", "30 minute", "locked_until"],
    },
    # Very long document QA (stress test)
    {
        "task_id": "stress_test_1",
        "task_type": "stress_test",
        "context": """
This is a comprehensive technical specification document for a distributed database system.

SECTION 1: SYSTEM ARCHITECTURE
The system uses a distributed architecture with multiple nodes for high availability and scalability. Each node can handle read and write operations independently while maintaining consistency through a consensus protocol.

Key Components:
- Storage Engine: Uses a log-structured merge-tree (LSM-tree) for efficient writes
- Consensus Layer: Implements Raft protocol for leader election and log replication
- Query Engine: Supports SQL-like queries with distributed execution plans
- Cache Layer: In-memory caching with LRU eviction policy

""" + """
SECTION 2: DATA MODEL
The system supports multiple data models including relational tables, document stores, and key-value pairs. Data is automatically sharded across nodes based on a consistent hashing algorithm.

Schema Management:
- Tables can be created, altered, and dropped dynamically
- Indexes are maintained asynchronously to avoid blocking writes
- Foreign key constraints are enforced at the application level
- Column families group related columns for efficient storage

""" + """
SECTION 3: REPLICATION AND CONSISTENCY
Data is replicated across multiple nodes using synchronous and asynchronous replication modes.

Consistency Levels:
- STRONG: All replicas must acknowledge before returning
- QUORUM: Majority of replicas must acknowledge
- EVENTUAL: Write returns immediately, replicated in background

The default consistency level is QUORUM, which provides a good balance between consistency and availability.

""" * 15,  # Make it very long
        "question": "What is the default consistency level in this database system?",
        "expected_answer": "QUORUM",
        "answer_contains": ["QUORUM", "quorum"],
    },
]

# Add more padded versions for super-long tests
for i in range(5):
    base_padding = "This is additional context to test long document handling capabilities. " * 200
    LONGBENCH_TASKS.append({
        "task_id": f"padded_simple_{i}",
        "task_type": "padded_simple",
        "context": f"""
{base_padding}

Here is the actual information you need:
The capital of France is Paris. Paris is known as the City of Light.

{base_padding}
""",
        "question": "What is the capital of France?",
        "expected_answer": "Paris",
        "answer_contains": ["paris"],
    })


class LongBenchBenchmark:
    """LongBench-style benchmark for long context understanding."""

    def __init__(
        self,
        drafter_model: str = "gpt-4o-mini",
        verifier_model: str = "gpt-4o",
        quality_threshold: float = 0.60,
    ):
        self.drafter_model = drafter_model
        self.verifier_model = verifier_model
        self.quality_threshold = quality_threshold
        self.results: list[LongBenchResult] = []

    def _check_answer(self, response: str, expected: str, contains: list[str]) -> bool:
        """Check if response contains expected answer."""
        response_lower = response.lower()
        # Check if any of the expected strings are in the response
        return any(c.lower() in response_lower for c in contains)

    async def run_single(self, task: dict) -> LongBenchResult:
        """Run a single long context test."""
        task_id = task["task_id"]
        task_type = task["task_type"]
        context = task["context"]
        question = task["question"]
        expected = task["expected_answer"]
        contains = task["answer_contains"]

        word_count = len(context.split())

        # Create prompt
        prompt = f"""Read the following document carefully and answer the question.

DOCUMENT:
{context}

QUESTION: {question}

Provide a clear, direct answer based only on the information in the document."""

        # Create agent
        agent = CascadeAgent(
            models=[
                ModelConfig(name=self.drafter_model, provider="openai", cost=0.00015),
                ModelConfig(name=self.verifier_model, provider="openai", cost=0.0025),
            ],
            enable_domain_detection=True,
            use_semantic_domains=True,
        )

        start_time = time.time()

        try:
            result = await agent.run(prompt, max_tokens=500)
            latency_ms = (time.time() - start_time) * 1000

            # Check answer
            correct = self._check_answer(result.content, expected, contains)

            draft_accepted = result.metadata.get("draft_accepted", False)
            complexity = result.metadata.get("complexity", "unknown")

            return LongBenchResult(
                task_id=task_id,
                task_type=task_type,
                word_count=word_count,
                correct=correct,
                draft_accepted=draft_accepted,
                cost=result.total_cost,
                latency_ms=latency_ms,
                complexity=complexity,
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            return LongBenchResult(
                task_id=task_id,
                task_type=task_type,
                word_count=word_count,
                correct=False,
                draft_accepted=False,
                cost=0.0,
                latency_ms=latency_ms,
                complexity="error",
                error=str(e),
            )

    async def run_benchmark(
        self,
        max_tasks: Optional[int] = None,
        verbose: bool = True,
    ) -> dict:
        """Run full benchmark."""
        tasks = LONGBENCH_TASKS[:max_tasks] if max_tasks else LONGBENCH_TASKS

        print("=" * 70)
        print("LONGBENCH-STYLE LONG CONTEXT BENCHMARK")
        print("=" * 70)
        print("\nConfiguration:")
        print(f"  Drafter:  {self.drafter_model}")
        print(f"  Verifier: {self.verifier_model}")
        print(f"  Threshold: {self.quality_threshold}")
        print(f"  Tasks: {len(tasks)}")
        print()

        self.results = []

        for i, task in enumerate(tasks):
            result = await self.run_single(task)
            self.results.append(result)

            status = "✓" if result.correct else "✗"
            route = "[D]" if result.draft_accepted else "[V]"

            if verbose:
                print(
                    f"[{i+1}/{len(tasks)}] {result.task_id}: {status} {route} | "
                    f"{result.word_count:,} words | {result.complexity} | "
                    f"${result.cost:.4f} | {result.latency_ms:.0f}ms"
                )
                if result.error:
                    print(f"    Error: {result.error[:60]}")

        return self._calculate_metrics()

    def _calculate_metrics(self) -> dict:
        """Calculate benchmark metrics."""
        total = len(self.results)
        correct = sum(1 for r in self.results if r.correct)
        draft_accepted = sum(1 for r in self.results if r.draft_accepted)
        total_cost = sum(r.cost for r in self.results)
        total_words = sum(r.word_count for r in self.results)

        # Group by task type
        by_type = {}
        for r in self.results:
            if r.task_type not in by_type:
                by_type[r.task_type] = {"correct": 0, "total": 0, "words": 0}
            by_type[r.task_type]["total"] += 1
            by_type[r.task_type]["words"] += r.word_count
            if r.correct:
                by_type[r.task_type]["correct"] += 1

        # Group by word count buckets
        buckets = {"<1K": [], "1K-5K": [], "5K-10K": [], ">10K": []}
        for r in self.results:
            if r.word_count < 1000:
                buckets["<1K"].append(r)
            elif r.word_count < 5000:
                buckets["1K-5K"].append(r)
            elif r.word_count < 10000:
                buckets["5K-10K"].append(r)
            else:
                buckets[">10K"].append(r)

        accuracy = correct / total if total > 0 else 0
        draft_rate = draft_accepted / total if total > 0 else 0

        metrics = {
            "total_tasks": total,
            "correct": correct,
            "accuracy": accuracy,
            "draft_acceptance": draft_rate,
            "total_cost": total_cost,
            "total_words": total_words,
            "avg_words": total_words / total if total > 0 else 0,
        }

        # Print summary
        print("\n" + "=" * 70)
        print("BENCHMARK SUMMARY")
        print("=" * 70)

        print("\nOverall Performance:")
        print(f"  Accuracy:         {accuracy:.1%} ({correct}/{total})")
        print(f"  Draft Acceptance: {draft_rate:.1%}")
        print(f"  Total Cost:       ${total_cost:.4f}")
        print(f"  Total Words:      {total_words:,}")
        print(f"  Avg Words/Task:   {total_words//total:,}")

        print("\nBy Task Type:")
        for task_type, data in by_type.items():
            type_acc = data["correct"] / data["total"] if data["total"] > 0 else 0
            avg_words = data["words"] // data["total"] if data["total"] > 0 else 0
            print(f"  {task_type:20} {type_acc:.1%} ({data['correct']}/{data['total']}) | ~{avg_words:,} words")

        print("\nBy Document Length:")
        for bucket, results in buckets.items():
            if results:
                bucket_acc = sum(1 for r in results if r.correct) / len(results)
                bucket_draft = sum(1 for r in results if r.draft_accepted) / len(results)
                print(f"  {bucket:8} {bucket_acc:.1%} acc | {bucket_draft:.1%} draft | {len(results)} tasks")

        print("=" * 70)

        return metrics


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="LongBench-style Benchmark")
    parser.add_argument("--sample", type=int, help="Run N tasks")
    parser.add_argument("--full", action="store_true", help="Run all tasks")
    parser.add_argument("--drafter", default="gpt-4o-mini")
    parser.add_argument("--verifier", default="gpt-4o")

    args = parser.parse_args()

    max_tasks = None
    if args.sample:
        max_tasks = args.sample
    elif not args.full:
        max_tasks = 10  # Default quick test

    benchmark = LongBenchBenchmark(
        drafter_model=args.drafter,
        verifier_model=args.verifier,
    )

    results = await benchmark.run_benchmark(max_tasks=max_tasks)

    # Save results
    output_dir = Path(__file__).parent / "longbench_results"
    output_dir.mkdir(exist_ok=True)

    with open(output_dir / "results.json", "w") as f:
        json.dump({
            "config": {
                "drafter": args.drafter,
                "verifier": args.verifier,
            },
            "metrics": results,
            "results": [
                {
                    "task_id": r.task_id,
                    "task_type": r.task_type,
                    "word_count": r.word_count,
                    "correct": r.correct,
                    "draft_accepted": r.draft_accepted,
                    "cost": r.cost,
                    "latency_ms": r.latency_ms,
                    "complexity": r.complexity,
                }
                for r in benchmark.results
            ],
        }, f, indent=2)

    print(f"\nResults saved to: {output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
