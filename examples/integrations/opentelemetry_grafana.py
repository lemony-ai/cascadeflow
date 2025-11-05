"""
OpenTelemetry Integration Example with Grafana

This example shows how to export cascadeflow metrics to Grafana using OpenTelemetry.
Metrics include cost, tokens, and latency with user/model/provider dimensions.

Setup:
    1. Install OpenTelemetry:
       pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http

    2. Start Grafana + OpenTelemetry Collector (Docker):
       docker-compose up -d

    3. Access Grafana:
       http://localhost:3000
       (username: admin, password: admin)

    4. Run this example:
       python3 opentelemetry_grafana.py

Metrics Exported:
    - cascadeflow.cost.total: Total cost in USD
    - cascadeflow.tokens.input: Input tokens
    - cascadeflow.tokens.output: Output tokens
    - cascadeflow.latency: Request latency in ms

Dimensions (tags):
    - user.id: User ID
    - user.tier: User tier (free/pro/enterprise)
    - model.name: Model name
    - provider.name: Provider name
    - query.domain: Query domain
"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from cascadeflow.integrations.otel import (
    OpenTelemetryExporter,
    cascadeflowMetrics,
    MetricDimensions,
)


async def simulate_queries():
    """Simulate cascadeflow queries with different users/models/costs."""
    print("=" * 80)
    print("CASCADEFLOW - OPENTELEMETRY + GRAFANA EXAMPLE")
    print("=" * 80)
    print("\nThis example simulates cascadeflow queries and exports metrics to Grafana.")
    print("\nSetup Required:")
    print("  1. OpenTelemetry Collector running on localhost:4318")
    print("  2. Grafana dashboard at http://localhost:3000")
    print("\nMetrics will be exported every 60 seconds.")
    print("\n" + "=" * 80)

    # Initialize OpenTelemetry exporter
    exporter = OpenTelemetryExporter(
        endpoint="http://localhost:4318",
        service_name="cascadeflow-demo",
        environment="development",
    )

    if not exporter.enabled:
        print("\n⚠️  OpenTelemetry not available!")
        print("   Install with:")
        print("   pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http")
        print("\n   Or set OTEL_EXPORTER_OTLP_ENDPOINT to disable this warning.")
        return

    print("\n✅ OpenTelemetry exporter initialized!")
    print(f"   Endpoint: {exporter.endpoint}")
    print(f"   Service: {exporter.service_name}")
    print(f"   Environment: {exporter.environment}")

    # Simulate queries
    queries = [
        # Free tier user - cheap models
        {
            "user_id": "user_free_001",
            "user_tier": "free",
            "model": "gpt-3.5-turbo",
            "provider": "openai",
            "cost": 0.0005,
            "tokens_input": 50,
            "tokens_output": 100,
            "latency_ms": 800,
            "domain": "general",
        },
        # Pro tier user - GPT-4o-mini
        {
            "user_id": "user_pro_001",
            "user_tier": "pro",
            "model": "gpt-4o-mini",
            "provider": "openai",
            "cost": 0.0015,
            "tokens_input": 100,
            "tokens_output": 200,
            "latency_ms": 1200,
            "domain": "code",
        },
        # Enterprise user - GPT-4
        {
            "user_id": "user_enterprise_001",
            "user_tier": "enterprise",
            "model": "gpt-4",
            "provider": "openai",
            "cost": 0.03,
            "tokens_input": 200,
            "tokens_output": 300,
            "latency_ms": 3500,
            "domain": "expert",
        },
        # Pro user - Anthropic Claude
        {
            "user_id": "user_pro_002",
            "user_tier": "pro",
            "model": "claude-3-haiku-20240307",
            "provider": "anthropic",
            "cost": 0.0008,
            "tokens_input": 80,
            "tokens_output": 150,
            "latency_ms": 600,
            "domain": "general",
        },
        # Free user - Groq (ultra-fast)
        {
            "user_id": "user_free_002",
            "user_tier": "free",
            "model": "llama-3.1-8b-instant",
            "provider": "groq",
            "cost": 0.0001,
            "tokens_input": 60,
            "tokens_output": 120,
            "latency_ms": 200,
            "domain": "general",
        },
    ]

    print("\n" + "=" * 80)
    print("SIMULATING QUERIES (5 queries)")
    print("=" * 80)

    for i, query in enumerate(queries, 1):
        print(f"\n[{i}/5] Simulating query...")
        print(f"  User: {query['user_id']} ({query['user_tier']} tier)")
        print(f"  Model: {query['model']} ({query['provider']})")
        print(f"  Cost: ${query['cost']:.4f}")
        print(f"  Tokens: {query['tokens_input']} input + {query['tokens_output']} output")
        print(f"  Latency: {query['latency_ms']}ms")
        print(f"  Domain: {query['domain']}")

        # Record metrics
        metrics = cascadeflowMetrics(
            cost=query["cost"],
            tokens_input=query["tokens_input"],
            tokens_output=query["tokens_output"],
            latency_ms=query["latency_ms"],
            dimensions=MetricDimensions(
                user_id=query["user_id"],
                user_tier=query["user_tier"],
                model=query["model"],
                provider=query["provider"],
                domain=query["domain"],
            ),
        )

        exporter.record(metrics)

        # Simulate delay between queries
        await asyncio.sleep(1)

    print("\n" + "=" * 80)
    print("✅ ALL METRICS RECORDED")
    print("=" * 80)
    print("\n📊 Metrics exported to OpenTelemetry!")
    print("   Metrics are batched and sent every 60 seconds.")
    print("   Force flushing now...")

    # Force flush to send immediately
    exporter.flush()

    print("\n✅ Metrics flushed to Grafana!")
    print("\n🎯 Next Steps:")
    print("   1. Open Grafana: http://localhost:3000")
    print("   2. Create dashboard with these metrics:")
    print("      • cascadeflow.cost.total (by user.tier, provider.name)")
    print("      • cascadeflow.tokens.input/output (by model.name)")
    print("      • cascadeflow.latency (histogram by provider.name)")
    print("   3. Try filtering by dimensions:")
    print("      • user.tier='pro'")
    print("      • provider.name='openai'")
    print("      • query.domain='code'")

    # Shutdown exporter
    exporter.shutdown()

    print("\n" + "=" * 80)
    print("EXAMPLE COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(simulate_queries())
