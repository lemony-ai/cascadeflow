# CascadeFlow OpenTelemetry Integration Examples

This directory contains examples for integrating CascadeFlow with OpenTelemetry for production observability.

## What's Included

1. **`opentelemetry_grafana.py`** - Complete example showing metrics export to Grafana
2. **`docker-compose.yml`** - Docker stack with OpenTelemetry Collector + Prometheus + Grafana
3. **Configuration files** - Ready-to-use configs for OpenTelemetry, Prometheus, and Grafana

## Quick Start

### 1. Install Dependencies

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

### 2. Start Observability Stack

```bash
cd examples/integrations
docker-compose up -d
```

This starts:
- **OpenTelemetry Collector** on `localhost:4318` (OTLP HTTP)
- **Prometheus** on `localhost:9090`
- **Grafana** on `localhost:3000` (username: `admin`, password: `admin`)

### 3. Run Example

```bash
python3 opentelemetry_grafana.py
```

### 4. View Metrics in Grafana

1. Open http://localhost:3000
2. Login with `admin/admin`
3. Go to **Explore** → Select **Prometheus**
4. Query metrics:
   - `cascadeflow_cost_total` - Total cost by user/model/provider
   - `cascadeflow_tokens_input` - Input tokens by model
   - `cascadeflow_tokens_output` - Output tokens by model
   - `cascadeflow_latency` - Latency histogram by provider

## Metrics Exported

### Cost Metrics
- **`cascadeflow.cost.total`** (Counter) - Total cost in USD
- Dimensions: `user.id`, `user.tier`, `model.name`, `provider.name`, `query.domain`

### Token Metrics
- **`cascadeflow.tokens.input`** (Counter) - Input tokens consumed
- **`cascadeflow.tokens.output`** (Counter) - Output tokens generated
- Dimensions: `user.id`, `user.tier`, `model.name`, `provider.name`

### Latency Metrics
- **`cascadeflow.latency`** (Histogram) - Request latency in milliseconds
- Dimensions: `user.id`, `model.name`, `provider.name`

## Example Grafana Queries

### Cost by User Tier
```promql
sum by (user_tier) (rate(cascadeflow_cost_total[5m]))
```

### Tokens by Model
```promql
sum by (model_name) (rate(cascadeflow_tokens_input[5m]))
+ sum by (model_name) (rate(cascadeflow_tokens_output[5m]))
```

### Latency P95 by Provider
```promql
histogram_quantile(0.95,
  sum by (provider_name, le) (rate(cascadeflow_latency_bucket[5m]))
)
```

### Cost per User (Top 10)
```promql
topk(10, sum by (user_id) (rate(cascadeflow_cost_total[5m])))
```

## Integration with Your App

```python
from cascadeflow.integrations.otel import OpenTelemetryExporter, CascadeFlowMetrics, MetricDimensions

# Initialize exporter
exporter = OpenTelemetryExporter(
    endpoint="http://localhost:4318",
    service_name="my-app",
    environment="production"
)

# Record metrics after each CascadeFlow query
metrics = CascadeFlowMetrics(
    cost=response.cost,
    tokens_input=response.metadata["prompt_tokens"],
    tokens_output=response.metadata["completion_tokens"],
    latency_ms=response.latency_ms,
    dimensions=MetricDimensions(
        user_id=user.id,
        user_tier=user.tier,
        model=response.model,
        provider=response.provider,
        domain="code"  # Optional
    )
)

exporter.record(metrics)
```

## Environment Variables

```bash
# OpenTelemetry Configuration
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_SERVICE_NAME="cascadeflow-prod"
export ENVIRONMENT="production"
export OTEL_ENABLED="true"

# Then use:
from cascadeflow.integrations.otel import create_exporter_from_env
exporter = create_exporter_from_env()
```

## Production Deployment

### AWS CloudWatch

```python
exporter = OpenTelemetryExporter(
    endpoint="https://your-otel-collector.amazonaws.com:4318",
    service_name="cascadeflow-prod",
    environment="production"
)
```

### Datadog

```python
# Configure OpenTelemetry Collector to export to Datadog
# Then use the same exporter
exporter = OpenTelemetryExporter(
    endpoint="http://localhost:4318",
    service_name="cascadeflow-prod"
)
```

### Grafana Cloud

```python
exporter = OpenTelemetryExporter(
    endpoint="https://otlp-gateway-prod-us-central-0.grafana.net/otlp",
    service_name="cascadeflow-prod",
    environment="production"
)
```

## Cleanup

```bash
docker-compose down
```

## Troubleshooting

### Metrics not appearing in Grafana

1. Check OpenTelemetry Collector logs:
   ```bash
   docker-compose logs otel-collector
   ```

2. Verify metrics are being received:
   ```bash
   curl http://localhost:8889/metrics
   ```

3. Check Prometheus is scraping:
   - Open http://localhost:9090
   - Go to **Status** → **Targets**
   - Verify `otel-collector` is UP

### OpenTelemetry not installed

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
```

## Learn More

- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/instrumentation/python/)
- [Grafana Dashboards](https://grafana.com/docs/grafana/latest/dashboards/)
- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
