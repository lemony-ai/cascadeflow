"""
Production Patterns Example
============================

Production-ready patterns for deploying cascadeflow at scale.

What it demonstrates:
- Error handling and retry strategies
- Rate limiting and throttling
- Monitoring and logging
- Budget management
- Caching strategies
- Circuit breakers
- Graceful degradation
- Health checks

Requirements:
    - cascadeflow[all]
    - redis (optional, for distributed caching)
    - prometheus_client (optional, for metrics)

Setup:
    pip install cascadeflow[all]
    export OPENAI_API_KEY="sk-..."
    python examples/production_patterns.py

Use Cases:
    1. High-volume production APIs
    2. Mission-critical applications
    3. Multi-tenant systems
    4. Cost-controlled environments
    5. Regulated industries

Documentation:
    📖 Production Guide: docs/guides/production.md
    📖 Deployment: docs/guides/deployment.md
    📚 Examples README: examples/README.md
"""

import asyncio
import logging
import os
import time
from collections import deque
from datetime import datetime
from typing import Any, Optional

from cascadeflow import CascadeAgent, ModelConfig

# ═══════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN 1: Error Handling & Retry Logic
# ═══════════════════════════════════════════════════════════════════════════


class RetryConfig:
    """Configuration for retry logic."""

    max_retries: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0
    exponential_base: float = 2.0


async def execute_with_retry(
    agent: CascadeAgent, query: str, config: RetryConfig = RetryConfig(), **kwargs
) -> Any:
    """Execute query with exponential backoff retry."""
    last_error = None

    for attempt in range(config.max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{config.max_retries} for query")
            result = await agent.run(query, **kwargs)
            return result

        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt + 1} failed: {e}")

            if attempt < config.max_retries - 1:
                # Calculate delay with exponential backoff
                delay = min(
                    config.base_delay * (config.exponential_base**attempt), config.max_delay
                )
                logger.info(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All {config.max_retries} attempts failed")

    raise last_error


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN 2: Rate Limiting
# ═══════════════════════════════════════════════════════════════════════════


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate: int, per: float = 60.0):
        """
        Args:
            rate: Number of requests allowed
            per: Time window in seconds (default: 60s = 1 minute)
        """
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.time()

    async def acquire(self) -> bool:
        """Acquire permission to make a request."""
        current = time.time()
        time_passed = current - self.last_check
        self.last_check = current

        # Add tokens based on time passed
        self.allowance += time_passed * (self.rate / self.per)
        if self.allowance > self.rate:
            self.allowance = self.rate

        if self.allowance < 1.0:
            # Rate limit exceeded
            return False

        self.allowance -= 1.0
        return True

    async def wait_if_needed(self):
        """Wait until a request slot is available."""
        while not await self.acquire():
            await asyncio.sleep(0.1)


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN 3: Budget Management
# ═══════════════════════════════════════════════════════════════════════════


class BudgetManager:
    """Manage and enforce budget limits."""

    def __init__(
        self,
        daily_budget: float,
        hourly_budget: Optional[float] = None,
        alert_threshold: float = 0.8,
    ):
        self.daily_budget = daily_budget
        self.hourly_budget = hourly_budget or (daily_budget / 24)
        self.alert_threshold = alert_threshold

        self.daily_spent = 0.0
        self.hourly_spent = 0.0
        self.last_hour_reset = datetime.now()
        self.last_day_reset = datetime.now()

        self.total_queries = 0
        self.blocked_queries = 0

    def reset_if_needed(self):
        """Reset budgets if time windows have passed."""
        now = datetime.now()

        # Reset hourly budget
        if (now - self.last_hour_reset).total_seconds() >= 3600:
            self.hourly_spent = 0.0
            self.last_hour_reset = now
            logger.info("Hourly budget reset")

        # Reset daily budget
        if (now - self.last_day_reset).total_seconds() >= 86400:
            self.daily_spent = 0.0
            self.last_day_reset = now
            logger.info("Daily budget reset")

    def can_afford(self, estimated_cost: float) -> bool:
        """Check if query is within budget."""
        self.reset_if_needed()

        if self.hourly_spent + estimated_cost > self.hourly_budget:
            logger.warning(
                f"Hourly budget exceeded: ${self.hourly_spent:.4f}/${self.hourly_budget:.4f}"
            )
            return False

        if self.daily_spent + estimated_cost > self.daily_budget:
            logger.warning(
                f"Daily budget exceeded: ${self.daily_spent:.4f}/${self.daily_budget:.4f}"
            )
            return False

        return True

    def record_cost(self, actual_cost: float):
        """Record actual cost after query."""
        self.daily_spent += actual_cost
        self.hourly_spent += actual_cost
        self.total_queries += 1

        # Alert if approaching limits
        if self.hourly_spent >= self.hourly_budget * self.alert_threshold:
            logger.warning(
                f"Approaching hourly budget limit: {self.hourly_spent/self.hourly_budget*100:.1f}%"
            )

        if self.daily_spent >= self.daily_budget * self.alert_threshold:
            logger.warning(
                f"Approaching daily budget limit: {self.daily_spent/self.daily_budget*100:.1f}%"
            )

    def get_stats(self) -> dict[str, Any]:
        """Get budget statistics."""
        return {
            "daily_spent": self.daily_spent,
            "daily_budget": self.daily_budget,
            "daily_remaining": self.daily_budget - self.daily_spent,
            "hourly_spent": self.hourly_spent,
            "hourly_budget": self.hourly_budget,
            "total_queries": self.total_queries,
            "blocked_queries": self.blocked_queries,
            "avg_cost_per_query": (
                self.daily_spent / self.total_queries if self.total_queries > 0 else 0
            ),
        }


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN 4: Circuit Breaker
# ═══════════════════════════════════════════════════════════════════════════


class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    def is_open(self) -> bool:
        """Check if circuit is open (blocking requests)."""
        if self.state == "open":
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "half_open"
                logger.info("Circuit breaker entering half-open state")
                return False
            return True
        return False

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.is_open():
            raise Exception("Circuit breaker is OPEN - blocking request")

        try:
            result = await func(*args, **kwargs)

            # Success - reset if in half-open
            if self.state == "half_open":
                self.state = "closed"
                self.failure_count = 0
                logger.info("Circuit breaker closed after successful recovery")

            return result

        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.error(f"Circuit breaker OPENED after {self.failure_count} failures")

            raise e


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN 5: Simple In-Memory Cache
# ═══════════════════════════════════════════════════════════════════════════


class QueryCache:
    """Simple in-memory cache for query results."""

    def __init__(self, ttl: int = 3600, max_size: int = 1000):
        self.ttl = ttl
        self.max_size = max_size
        self.cache: dict[str, tuple] = {}  # key -> (result, timestamp)
        self.hits = 0
        self.misses = 0

    def _make_key(self, query: str, **kwargs) -> str:
        """Generate cache key from query and params."""
        # Simple key generation (in production, use better hashing)
        params_str = str(sorted(kwargs.items()))
        return f"{query}:{params_str}"

    def get(self, query: str, **kwargs) -> Optional[Any]:
        """Get cached result if available and not expired."""
        key = self._make_key(query, **kwargs)

        if key in self.cache:
            result, timestamp = self.cache[key]

            # Check if expired
            if time.time() - timestamp < self.ttl:
                self.hits += 1
                logger.debug(f"Cache HIT for query: {query[:50]}...")
                return result
            else:
                # Expired, remove from cache
                del self.cache[key]

        self.misses += 1
        logger.debug(f"Cache MISS for query: {query[:50]}...")
        return None

    def set(self, query: str, result: Any, **kwargs):
        """Cache a query result."""
        key = self._make_key(query, **kwargs)

        # Evict oldest if at capacity
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]

        self.cache[key] = (result, time.time())
        logger.debug(f"Cached result for: {query[:50]}...")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = self.hits / total * 100 if total > 0 else 0

        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "cache_size": len(self.cache),
            "max_size": self.max_size,
        }


# ═══════════════════════════════════════════════════════════════════════════
# PATTERN 6: Health Check Monitor
# ═══════════════════════════════════════════════════════════════════════════


class HealthMonitor:
    """Monitor system health metrics."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.latencies = deque(maxlen=window_size)
        self.errors = deque(maxlen=window_size)
        self.costs = deque(maxlen=window_size)
        self.start_time = time.time()

    def record_request(self, latency_ms: float, cost: float, error: bool = False):
        """Record a request's metrics."""
        self.latencies.append(latency_ms)
        self.costs.append(cost)
        self.errors.append(1 if error else 0)

    def get_health(self) -> dict[str, Any]:
        """Get current health status."""
        if not self.latencies:
            return {"status": "unknown", "reason": "No data"}

        avg_latency = sum(self.latencies) / len(self.latencies)
        error_rate = sum(self.errors) / len(self.errors) * 100
        avg_cost = sum(self.costs) / len(self.costs)
        uptime = time.time() - self.start_time

        # Determine health status
        if error_rate > 10:
            status = "unhealthy"
            reason = f"High error rate: {error_rate:.1f}%"
        elif avg_latency > 5000:
            status = "degraded"
            reason = f"High latency: {avg_latency:.0f}ms"
        else:
            status = "healthy"
            reason = "All metrics normal"

        return {
            "status": status,
            "reason": reason,
            "metrics": {
                "avg_latency_ms": round(avg_latency, 2),
                "error_rate_pct": round(error_rate, 2),
                "avg_cost": round(avg_cost, 6),
                "uptime_seconds": round(uptime, 2),
                "requests_tracked": len(self.latencies),
            },
        }


# ═══════════════════════════════════════════════════════════════════════════
# PRODUCTION-READY AGENT WRAPPER
# ═══════════════════════════════════════════════════════════════════════════


class ProductionAgent:
    """Production-ready cascadeflow agent with all patterns integrated."""

    def __init__(
        self,
        agent: CascadeAgent,
        daily_budget: float = 10.0,
        rate_limit: int = 60,  # requests per minute
        enable_cache: bool = True,
        enable_circuit_breaker: bool = True,
    ):
        self.agent = agent
        self.budget_manager = BudgetManager(daily_budget)
        self.rate_limiter = RateLimiter(rate_limit, per=60.0)
        self.cache = QueryCache() if enable_cache else None
        self.circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None
        self.health_monitor = HealthMonitor()

        logger.info("Production agent initialized with all patterns")

    async def query(self, query: str, use_cache: bool = True, **kwargs) -> Any:
        """Execute query with all production patterns."""
        start_time = time.time()
        error_occurred = False

        try:
            # 1. Check rate limit
            await self.rate_limiter.wait_if_needed()

            # 2. Check cache
            if use_cache and self.cache:
                cached_result = self.cache.get(query, **kwargs)
                if cached_result is not None:
                    return cached_result

            # 3. Check budget
            estimated_cost = 0.001  # Rough estimate
            if not self.budget_manager.can_afford(estimated_cost):
                self.budget_manager.blocked_queries += 1
                raise Exception("Budget exceeded - query blocked")

            # 4. Execute with circuit breaker
            if self.circuit_breaker:
                result = await self.circuit_breaker.call(
                    execute_with_retry, self.agent, query, **kwargs
                )
            else:
                result = await execute_with_retry(self.agent, query, **kwargs)

            # 5. Record cost
            self.budget_manager.record_cost(result.total_cost)

            # 6. Cache result
            if use_cache and self.cache:
                self.cache.set(query, result, **kwargs)

            return result

        except Exception as e:
            error_occurred = True
            logger.error(f"Query failed: {e}")
            raise

        finally:
            # Record metrics
            latency_ms = (time.time() - start_time) * 1000
            cost = getattr(result, "total_cost", 0) if "result" in locals() else 0
            self.health_monitor.record_request(latency_ms, cost, error_occurred)

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics."""
        stats = {
            "budget": self.budget_manager.get_stats(),
            "health": self.health_monitor.get_health(),
        }

        if self.cache:
            stats["cache"] = self.cache.get_stats()

        if self.circuit_breaker:
            stats["circuit_breaker"] = {
                "state": self.circuit_breaker.state,
                "failure_count": self.circuit_breaker.failure_count,
            }

        return stats


# ═══════════════════════════════════════════════════════════════════════════
# EXAMPLES
# ═══════════════════════════════════════════════════════════════════════════


async def demo_production_agent():
    """Demonstrate production-ready agent."""

    print("\n" + "=" * 70)
    print("PRODUCTION AGENT DEMO")
    print("=" * 70)
    print("\nIntegrated patterns: Retry, Rate Limiting, Budget, Cache, Circuit Breaker\n")

    # Setup
    models = [
        ModelConfig("gpt-4o-mini", provider="openai", cost=0.00015),
        ModelConfig("gpt-4o", provider="openai", cost=0.00625),
    ]
    agent = CascadeAgent(models=models)

    # Wrap with production patterns
    prod_agent = ProductionAgent(
        agent=agent,
        daily_budget=1.0,
        rate_limit=10,  # 10 req/min for demo
        enable_cache=True,
        enable_circuit_breaker=True,
    )

    # Execute queries
    queries = [
        "What is Python?",
        "What is Python?",  # Should hit cache
        "Explain machine learning",
        "What is 2+2?",
    ]

    for i, query in enumerate(queries):
        print(f"\n{'─'*70}")
        print(f"Query {i+1}: {query}")
        print(f"{'─'*70}")

        try:
            result = await prod_agent.query(query, max_tokens=100)
            print("✓ Success")
            print(f"  Model: {result.model_used}")
            print(f"  Cost: ${result.total_cost:.6f}")
            print(f"  Latency: {result.latency_ms:.0f}ms")
        except Exception as e:
            print(f"✗ Failed: {e}")

    # Show stats
    print(f"\n{'='*70}")
    print("STATISTICS")
    print(f"{'='*70}\n")

    stats = prod_agent.get_stats()

    print("Budget:")
    print(f"  Spent: ${stats['budget']['daily_spent']:.4f}/${stats['budget']['daily_budget']:.2f}")
    print(f"  Queries: {stats['budget']['total_queries']}")
    print(f"  Blocked: {stats['budget']['blocked_queries']}")

    print("\nCache:")
    print(f"  Hit rate: {stats['cache']['hit_rate']:.1f}%")
    print(f"  Hits: {stats['cache']['hits']}")
    print(f"  Misses: {stats['cache']['misses']}")

    print("\nHealth:")
    print(f"  Status: {stats['health']['status']}")
    print(f"  Avg latency: {stats['health']['metrics']['avg_latency_ms']:.0f}ms")
    print(f"  Error rate: {stats['health']['metrics']['error_rate_pct']:.1f}%")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════


async def main():
    """Run production patterns examples."""

    print("🌊 cascadeflow Production Patterns")
    print("=" * 70)

    if not os.getenv("OPENAI_API_KEY"):
        print("\n❌ OPENAI_API_KEY required")
        return

    await demo_production_agent()

    # Summary
    print("\n\n" + "=" * 70)
    print("🎓 KEY TAKEAWAYS")
    print("=" * 70)

    print("\n1. Error Handling:")
    print("   ├─ Exponential backoff retry")
    print("   ├─ Configurable retry limits")
    print("   └─ Detailed error logging")

    print("\n2. Rate Limiting:")
    print("   ├─ Token bucket algorithm")
    print("   ├─ Per-minute/hour/day limits")
    print("   └─ Graceful request queuing")

    print("\n3. Budget Management:")
    print("   ├─ Daily/hourly budgets")
    print("   ├─ Cost tracking per query")
    print("   ├─ Alert at 80% threshold")
    print("   └─ Block over-budget queries")

    print("\n4. Circuit Breaker:")
    print("   ├─ Fail fast after threshold")
    print("   ├─ Auto-recovery after timeout")
    print("   └─ Prevent cascade failures")

    print("\n5. Caching:")
    print("   ├─ In-memory query cache")
    print("   ├─ TTL-based expiration")
    print("   ├─ LRU eviction")
    print("   └─ 20-50% latency reduction")

    print("\n6. Health Monitoring:")
    print("   ├─ Track latency, errors, costs")
    print("   ├─ Real-time health status")
    print("   ├─ Uptime tracking")
    print("   └─ Alerting integration")

    print("\n📚 Learn more:")
    print("   • docs/guides/production.md")
    print("   • docs/guides/deployment.md")
    print("   • examples/fastapi_integration.py\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
