# Production Deployment Guide

Complete guide to deploying cascadeflow in production environments.

---

## 📋 Table of Contents

### **Basic (Essential Patterns)**
1. [Getting Started](#getting-started)
2. [Error Handling](#error-handling-basic)
3. [Basic Monitoring](#basic-monitoring)
4. [Deployment](#basic-deployment)

### **Advanced (Enterprise Features)**
5. [Rate Limiting](#rate-limiting)
6. [Advanced Budget Management](#advanced-budget-management)
7. [Circuit Breakers](#circuit-breakers)
8. [Caching Strategies](#caching-strategies)
9. [Advanced Monitoring](#advanced-monitoring)
10. [Kubernetes Deployment](#kubernetes-deployment)
11. [Best Practices](#best-practices)

---

# Basic Usage

Essential patterns for getting cascadeflow running in production.

---

## Getting Started

Production deployments require robust patterns for reliability, performance, and cost control.

### Production Checklist (Basic)

- ✅ **Error Handling** - Retry logic, graceful degradation
- ✅ **Basic Logging** - Request/response logging
- ✅ **Health Monitoring** - Simple health checks
- ✅ **Deployment** - Docker/container deployment
- ✅ **Security** - API key management

### Production Checklist (Advanced)

- ✅ **Rate Limiting** - Prevent abuse, manage load
- ✅ **Budget Management** - Cost controls, alerts
- ✅ **Circuit Breakers** - Fault tolerance
- ✅ **Caching** - Performance optimization
- ✅ **Advanced Monitoring** - Metrics, distributed tracing

---

<a name="error-handling-basic"></a>

## Error Handling

### Retry with Exponential Backoff

```python
import asyncio
from dataclasses import dataclass

@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0

async def execute_with_retry(
    agent: CascadeAgent,
    query: str,
    config: RetryConfig = RetryConfig(),
    **kwargs
):
    """Execute with exponential backoff retry."""
    last_error = None
    
    for attempt in range(config.max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{config.max_retries}")
            result = await agent.run(query, **kwargs)
            return result
        
        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            
            if attempt < config.max_retries - 1:
                delay = min(
                    config.base_delay * (config.exponential_base ** attempt),
                    config.max_delay
                )
                logger.info(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
    
    raise last_error

# Usage
try:
    result = await execute_with_retry(agent, query)
except Exception as e:
    logger.error(f"All retries failed: {e}")
    # Fallback or error response
```

### Error Classification

```python
class ErrorClassifier:
    """Classify errors for appropriate handling."""
    
    RETRIABLE_ERRORS = [
        "timeout",
        "rate_limit",
        "service_unavailable",
        "connection_error"
    ]
    
    PERMANENT_ERRORS = [
        "invalid_api_key",
        "unauthorized",
        "invalid_request"
    ]
    
    @staticmethod
    def is_retriable(error: Exception) -> bool:
        """Check if error should be retried."""
        error_str = str(error).lower()
        return any(err in error_str for err in ErrorClassifier.RETRIABLE_ERRORS)
    
    @staticmethod
    def should_alert(error: Exception) -> bool:
        """Check if error requires immediate attention."""
        error_str = str(error).lower()
        return any(err in error_str for err in ErrorClassifier.PERMANENT_ERRORS)
```

### Graceful Degradation

```python
async def query_with_fallback(
    agent: CascadeAgent,
    query: str,
    fallback_response: str = "I'm experiencing technical difficulties."
):
    """Execute with fallback response."""
    try:
        result = await execute_with_retry(agent, query)
        return result.content
    
    except Exception as e:
        logger.error(f"Query failed: {e}")
        
        # Return fallback
        return fallback_response
```

---

<a name="basic-monitoring"></a>

## Basic Monitoring

Simple health checks for production deployments.

```python
from typing import Dict
import asyncio

async def health_check(agent: CascadeAgent) -> Dict[str, any]:
    """Simple health check for production."""
    try:
        # Quick test query
        start = time.time()
        result = await agent.run("test", options={"max_tokens": 5})
        latency = (time.time() - start) * 1000

        return {
            "status": "healthy",
            "latency_ms": latency,
            "model": result.model_used
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
```

<a name="basic-deployment"></a>

## Basic Deployment

### Docker

Simple Docker deployment:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run
CMD ["python", "main.py"]
```

---

# Advanced Usage

Enterprise-grade features for scale, reliability, and performance.

---

## Rate Limiting

### Token Bucket Algorithm

```python
import time

class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, rate: int, per: float = 60.0):
        """
        Args:
            rate: Requests allowed per time window
            per: Time window in seconds (default: 60s)
        """
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.time()
    
    async def acquire(self) -> bool:
        """Try to acquire permission for request."""
        current = time.time()
        time_passed = current - self.last_check
        self.last_check = current
        
        # Add tokens based on time passed
        self.allowance += time_passed * (self.rate / self.per)
        if self.allowance > self.rate:
            self.allowance = self.rate
        
        if self.allowance < 1.0:
            return False  # Rate limited
        
        self.allowance -= 1.0
        return True
    
    async def wait_if_needed(self):
        """Wait until request slot available."""
        while not await self.acquire():
            await asyncio.sleep(0.1)

# Usage
limiter = RateLimiter(rate=60, per=60.0)  # 60 req/min

async def rate_limited_query(query: str):
    await limiter.wait_if_needed()
    return await agent.run(query)
```

### Per-User Rate Limiting

```python
from collections import defaultdict

class MultiUserRateLimiter:
    """Rate limiting per user."""
    
    def __init__(self, rate: int, per: float = 60.0):
        self.rate = rate
        self.per = per
        self.limiters = defaultdict(lambda: RateLimiter(rate, per))
    
    async def acquire(self, user_id: str) -> bool:
        """Acquire for specific user."""
        return await self.limiters[user_id].acquire()
    
    def get_stats(self, user_id: str) -> dict:
        """Get user's rate limit stats."""
        limiter = self.limiters[user_id]
        return {
            "allowance": limiter.allowance,
            "rate": limiter.rate,
            "utilization": 1 - (limiter.allowance / limiter.rate)
        }

# Usage
limiter = MultiUserRateLimiter(rate=100, per=3600)  # 100/hour

if not await limiter.acquire(user_id):
    raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

### Adaptive Rate Limiting

```python
class AdaptiveRateLimiter:
    """Adjust rate limits based on system load."""
    
    def __init__(self, base_rate: int, min_rate: int, max_rate: int):
        self.base_rate = base_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.current_rate = base_rate
        self.error_count = 0
        self.success_count = 0
    
    def adjust_rate(self):
        """Adjust rate based on success/error ratio."""
        total = self.success_count + self.error_count
        if total < 100:
            return  # Need more data
        
        error_rate = self.error_count / total
        
        if error_rate > 0.1:  # > 10% errors
            # Reduce rate
            self.current_rate = max(
                self.min_rate,
                int(self.current_rate * 0.8)
            )
        elif error_rate < 0.01:  # < 1% errors
            # Increase rate
            self.current_rate = min(
                self.max_rate,
                int(self.current_rate * 1.2)
            )
        
        # Reset counters
        self.error_count = 0
        self.success_count = 0
```

---

## Budget Management

### Multi-Tier Budgets

```python
from datetime import datetime, timedelta

class BudgetManager:
    """Manage daily/hourly/monthly budgets."""
    
    def __init__(
        self,
        hourly_budget: float,
        daily_budget: float,
        monthly_budget: float,
        alert_threshold: float = 0.8
    ):
        self.budgets = {
            "hourly": hourly_budget,
            "daily": daily_budget,
            "monthly": monthly_budget
        }
        self.spent = {
            "hourly": 0.0,
            "daily": 0.0,
            "monthly": 0.0
        }
        self.alert_threshold = alert_threshold
        self.reset_times = {
            "hourly": datetime.now(),
            "daily": datetime.now(),
            "monthly": datetime.now()
        }
        
        self.total_queries = 0
        self.blocked_queries = 0
    
    def reset_if_needed(self):
        """Reset budgets when time windows expire."""
        now = datetime.now()
        
        # Hourly reset
        if (now - self.reset_times["hourly"]).seconds >= 3600:
            self.spent["hourly"] = 0.0
            self.reset_times["hourly"] = now
            logger.info("Hourly budget reset")
        
        # Daily reset
        if now.date() > self.reset_times["daily"].date():
            self.spent["daily"] = 0.0
            self.reset_times["daily"] = now
            logger.info("Daily budget reset")
        
        # Monthly reset
        if now.month != self.reset_times["monthly"].month:
            self.spent["monthly"] = 0.0
            self.reset_times["monthly"] = now
            logger.info("Monthly budget reset")
    
    def can_afford(self, estimated_cost: float) -> tuple[bool, str]:
        """Check if within all budgets."""
        self.reset_if_needed()
        
        for period, budget in self.budgets.items():
            if self.spent[period] + estimated_cost > budget:
                return False, f"{period.capitalize()} budget exceeded"
        
        return True, "OK"
    
    def record_cost(self, cost: float):
        """Record cost across all periods."""
        for period in self.spent:
            self.spent[period] += cost
        
        self.total_queries += 1
        
        # Alert if approaching limits
        for period, budget in self.budgets.items():
            if self.spent[period] >= budget * self.alert_threshold:
                logger.warning(
                    f"Approaching {period} budget: "
                    f"${self.spent[period]:.2f}/${budget:.2f} "
                    f"({self.spent[period]/budget*100:.1f}%)"
                )
    
    def get_stats(self) -> dict:
        """Get budget statistics."""
        return {
            "hourly": {
                "spent": self.spent["hourly"],
                "budget": self.budgets["hourly"],
                "remaining": self.budgets["hourly"] - self.spent["hourly"],
                "utilization": self.spent["hourly"] / self.budgets["hourly"]
            },
            "daily": {
                "spent": self.spent["daily"],
                "budget": self.budgets["daily"],
                "remaining": self.budgets["daily"] - self.spent["daily"],
                "utilization": self.spent["daily"] / self.budgets["daily"]
            },
            "total_queries": self.total_queries,
            "blocked_queries": self.blocked_queries,
            "avg_cost": self.spent["daily"] / self.total_queries 
                if self.total_queries > 0 else 0
        }

# Usage
budget_mgr = BudgetManager(
    hourly_budget=1.0,
    daily_budget=10.0,
    monthly_budget=250.0
)

can_afford, reason = budget_mgr.can_afford(estimated_cost=0.01)
if not can_afford:
    raise Exception(f"Budget exceeded: {reason}")

result = await agent.run(query)
budget_mgr.record_cost(result.total_cost)
```

---

## Circuit Breakers

### Basic Circuit Breaker

```python
class CircuitBreaker:
    """Circuit breaker for fault tolerance."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
    
    def is_open(self) -> bool:
        """Check if circuit is open (blocking)."""
        if self.state == "open":
            # Check recovery timeout
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "half_open"
                logger.info("Circuit breaker: HALF_OPEN")
                return False
            return True
        return False
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker."""
        if self.is_open():
            raise Exception("Circuit breaker OPEN - request blocked")
        
        try:
            result = await func(*args, **kwargs)
            
            # Success in half-open state closes circuit
            if self.state == "half_open":
                self.state = "closed"
                self.failure_count = 0
                logger.info("Circuit breaker: CLOSED (recovered)")
            
            return result
        
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.error(
                    f"Circuit breaker: OPEN after {self.failure_count} failures"
                )
            
            raise e

# Usage
circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

try:
    result = await circuit_breaker.call(agent.run, query)
except Exception as e:
    logger.error(f"Request blocked or failed: {e}")
```

---

## Caching Strategies

### In-Memory Cache

```python
import hashlib

class QueryCache:
    """Simple in-memory LRU cache."""
    
    def __init__(self, ttl: int = 3600, max_size: int = 1000):
        self.ttl = ttl
        self.max_size = max_size
        self.cache = {}  # key -> (result, timestamp)
        self.hits = 0
        self.misses = 0
    
    def _make_key(self, query: str, **kwargs) -> str:
        """Generate cache key."""
        content = f"{query}:{sorted(kwargs.items())}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, query: str, **kwargs):
        """Get cached result."""
        key = self._make_key(query, **kwargs)
        
        if key in self.cache:
            result, timestamp = self.cache[key]
            
            # Check expiration
            if time.time() - timestamp < self.ttl:
                self.hits += 1
                return result
            else:
                del self.cache[key]
        
        self.misses += 1
        return None
    
    def set(self, query: str, result, **kwargs):
        """Cache result."""
        key = self._make_key(query, **kwargs)
        
        # Evict oldest if full
        if len(self.cache) >= self.max_size:
            oldest = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest]
        
        self.cache[key] = (result, time.time())
    
    def get_stats(self) -> dict:
        """Cache statistics."""
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total * 100 if total > 0 else 0,
            "size": len(self.cache)
        }

# Usage
cache = QueryCache(ttl=3600, max_size=1000)

async def cached_query(query: str, **kwargs):
    # Try cache
    cached = cache.get(query, **kwargs)
    if cached:
        return cached
    
    # Execute
    result = await agent.run(query, **kwargs)
    
    # Cache
    cache.set(query, result, **kwargs)
    return result
```

### Redis Cache (Distributed)

```python
import redis
import json

class RedisCache:
    """Distributed Redis cache."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", ttl: int = 3600):
        self.redis = redis.from_url(redis_url)
        self.ttl = ttl
    
    def _make_key(self, query: str, **kwargs) -> str:
        content = f"{query}:{sorted(kwargs.items())}"
        return f"cascadeflow:{hashlib.md5(content.encode()).hexdigest()}"
    
    def get(self, query: str, **kwargs):
        key = self._make_key(query, **kwargs)
        cached = self.redis.get(key)
        
        if cached:
            return json.loads(cached)
        return None
    
    def set(self, query: str, result, **kwargs):
        key = self._make_key(query, **kwargs)
        self.redis.setex(
            key,
            self.ttl,
            json.dumps(result, default=str)
        )
```

---

## Health Monitoring

### Health Monitor

```python
from collections import deque

class HealthMonitor:
    """Track system health metrics."""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.latencies = deque(maxlen=window_size)
        self.errors = deque(maxlen=window_size)
        self.costs = deque(maxlen=window_size)
        self.start_time = time.time()
    
    def record_request(
        self,
        latency_ms: float,
        cost: float,
        error: bool = False
    ):
        """Record request metrics."""
        self.latencies.append(latency_ms)
        self.costs.append(cost)
        self.errors.append(1 if error else 0)
    
    def get_health(self) -> dict:
        """Get health status."""
        if not self.latencies:
            return {"status": "unknown"}
        
        avg_latency = sum(self.latencies) / len(self.latencies)
        error_rate = sum(self.errors) / len(self.errors) * 100
        avg_cost = sum(self.costs) / len(self.costs)
        uptime = time.time() - self.start_time
        
        # Determine status
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
                "p95_latency_ms": round(sorted(self.latencies)[int(len(self.latencies) * 0.95)], 2) if self.latencies else 0,
                "error_rate_pct": round(error_rate, 2),
                "avg_cost": round(avg_cost, 6),
                "uptime_seconds": round(uptime, 2)
            }
        }
```

---

## Deployment

### Docker

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1

# Run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Kubernetes

**deployment.yaml:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cascadeflow
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cascadeflow
  template:
    metadata:
      labels:
        app: cascadeflow
    spec:
      containers:
      - name: api
        image: cascadeflow:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: openai
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          periodSeconds: 10
```

---

## Best Practices

### 1. Comprehensive Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Log all important events
logger.info(f"Query received: {query[:50]}")
logger.info(f"Model used: {result.model_used}, Cost: ${result.total_cost:.6f}")
logger.error(f"Query failed: {e}", exc_info=True)
```

### 2. Metrics Collection

```python
# Track key metrics
metrics = {
    "total_queries": 0,
    "total_cost": 0.0,
    "avg_latency": 0.0,
    "error_count": 0
}

# Update on each request
metrics["total_queries"] += 1
metrics["total_cost"] += result.total_cost
```

### 3. Graceful Shutdown

```python
import signal

shutdown_event = asyncio.Event()

def handle_shutdown(sig, frame):
    logger.info("Shutdown signal received")
    shutdown_event.set()

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

# In main loop
await shutdown_event.wait()
```

---

## Examples

See [`examples/production_patterns.py`](../../examples/production_patterns.py) for complete implementation.

---

**Questions?** Check the [FastAPI Guide](fastapi.md) for API deployment or open an issue on [GitHub](https://github.com/lemony-ai/cascadeflow/issues).