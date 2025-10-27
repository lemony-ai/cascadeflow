# Zero-Dependency Developer Experience

## Core Philosophy: Integrate, Don't Replace

**CascadeFlow should fit into existing workflows, not require new tools.**

Users already have:
- ✅ Logging systems (Python logging, Winston, Pino)
- ✅ Monitoring (Datadog, New Relic, CloudWatch)
- ✅ Dashboards (Grafana, Kibana, custom)
- ✅ Alerting (PagerDuty, Slack, email)

**Our job: Export data in standard formats they can use.**

---

## Design Principle: Standard Outputs, Not Custom Tools

### Anti-Pattern (What NOT to Do)

```python
# ❌ Forces users into our ecosystem
agent = CascadeAgent(models=[...])
agent.start_dashboard(port=8080)  # Forces custom dashboard
agent.use_cascadeflow_monitoring()  # Forces our monitoring

# Now user has:
# - Their existing Grafana
# - Their existing Datadog
# - CascadeFlow dashboard (yet another tool)
# Result: Tool sprawl, fragmentation
```

### Good Pattern (What TO Do)

```python
# ✅ Fits into existing tools
agent = CascadeAgent(models=[...])

# Works with user's existing logging
import logging
logging.basicConfig(level=logging.INFO)
# CascadeFlow automatically logs to standard Python logging

# Works with user's existing monitoring
result = await agent.run(query="...")
print(f"Cost: ${result.metadata['total_cost']}")  # Just metadata
# User can send to their Datadog, Grafana, etc.

# Works with user's existing alerts
if result.metadata['user_budget_remaining'] < 1.00:
    # User's existing alert system
    send_slack_alert("Budget low!")
```

---

## Observability: Standard Structured Logging

### Rich Metadata, Zero Dependencies

```python
result = await agent.run(
    query="What is 2+2?",
    user_id='user_123',
    user_tier='pro'
)

# Every result has complete metadata
print(result.metadata)
# {
#   # Cost tracking
#   'total_cost': 0.00045,
#   'draft_cost': 0.00015,
#   'verifier_cost': 0.0003,
#   'cost_saved': 0.00255,
#   'savings_percent': 85.0,
#   'bigonly_cost': 0.003,
#
#   # Quality metrics
#   'confidence': 0.88,
#   'quality_score': 0.92,
#   'validation_passed': True,
#
#   # Routing
#   'domain': 'general',
#   'draft_model': 'gpt-4o-mini',
#   'verifier_model': 'gpt-4o',
#   'draft_accepted': False,
#
#   # User context
#   'user_id': 'user_123',
#   'user_tier': 'pro',
#   'user_budget_remaining_daily': 4.25,
#   'user_budget_remaining_monthly': 92.50,
#
#   # Performance
#   'latency_ms': 245,
#   'draft_latency_ms': 120,
#   'verifier_latency_ms': 95,
#   'validation_latency_ms': 30,
#
#   # Timestamps
#   'timestamp': '2025-10-27T14:30:00Z',
#   'draft_timestamp': '2025-10-27T14:29:59Z',
#   'verifier_timestamp': '2025-10-27T14:30:00Z',
# }

# User decides what to do with this data
# - Log to their system
# - Send to their monitoring
# - Store in their database
# - Display in their UI
```

### Integration with Standard Logging

```python
import logging

# CascadeFlow uses standard Python logging
logger = logging.getLogger('cascadeflow')

# User's existing logging config works automatically
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),  # User's log file
        logging.StreamHandler(),         # User's console
    ]
)

agent = CascadeAgent(models=[...])
result = await agent.run(query="...")

# CascadeFlow automatically logs to user's configured handlers:
# 2025-10-27 14:30:00 - cascadeflow - INFO - Draft model: gpt-4o-mini
# 2025-10-27 14:30:00 - cascadeflow - INFO - Draft cost: $0.00015
# 2025-10-27 14:30:00 - cascadeflow - INFO - Confidence: 0.88
# 2025-10-27 14:30:00 - cascadeflow - INFO - Cascade to verifier: gpt-4o
# 2025-10-27 14:30:00 - cascadeflow - INFO - Total cost: $0.00045 (saved $0.00255, 85%)
```

### Structured Logging (JSON)

```python
import logging
import json

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'timestamp': record.created,
            'level': record.levelname,
            'message': record.getMessage(),
            'extra': record.__dict__.get('extra', {})
        })

# User's existing JSON logging setup
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger = logging.getLogger('cascadeflow')
logger.addHandler(handler)

agent = CascadeAgent(models=[...])
result = await agent.run(query="...")

# CascadeFlow logs as JSON (works with ELK, Datadog, etc.):
# {"timestamp": 1698765432, "level": "INFO", "message": "Cascade decision", "extra": {"confidence": 0.88, "cost": 0.00045}}
```

---

## Cost Tracking: Export, Don't Host

### Simple Export Functions

```python
from cascadeflow import CostTracker

tracker = CostTracker()

# Track costs (no dependencies)
for _ in range(100):
    result = await agent.run(query="...", user_id='user_123')
    # Automatically tracked

# Export to CSV (standard format)
tracker.export_csv('costs.csv')
# costs.csv can be opened in Excel, imported to any tool

# Export to JSON (for APIs)
data = tracker.export_json()
# {
#   'total_cost': 10.50,
#   'by_user': {'user_123': 5.25, 'user_456': 5.25},
#   'by_model': {'gpt-4o': 7.00, 'gpt-4o-mini': 3.50},
#   'by_domain': {'code': 6.00, 'general': 4.50}
# }

# Export to Prometheus format
metrics = tracker.export_prometheus()
# # TYPE cascadeflow_cost_total counter
# cascadeflow_cost_total{user_id="user_123"} 5.25
# cascadeflow_cost_total{user_id="user_456"} 5.25
```

### Integration with Existing Monitoring

```python
# Example: Send to Datadog
from datadog import statsd

agent = CascadeAgent(models=[...])
result = await agent.run(query="...")

# Use user's existing Datadog client
statsd.gauge('cascadeflow.cost', result.metadata['total_cost'])
statsd.gauge('cascadeflow.savings_percent', result.metadata['savings_percent'])
statsd.increment('cascadeflow.requests', tags=[f"user:{result.metadata['user_id']}"])

# Example: Send to CloudWatch
import boto3
cloudwatch = boto3.client('cloudwatch')

cloudwatch.put_metric_data(
    Namespace='CascadeFlow',
    MetricData=[{
        'MetricName': 'Cost',
        'Value': result.metadata['total_cost'],
        'Unit': 'None',
        'Dimensions': [{'Name': 'UserID', 'Value': result.metadata['user_id']}]
    }]
)

# Example: Send to Grafana (via Prometheus)
from prometheus_client import Gauge

cost_gauge = Gauge('cascadeflow_cost', 'Total cost per query', ['user_id'])
savings_gauge = Gauge('cascadeflow_savings', 'Savings percent', ['user_id'])

cost_gauge.labels(user_id=result.metadata['user_id']).set(result.metadata['total_cost'])
savings_gauge.labels(user_id=result.metadata['user_id']).set(result.metadata['savings_percent'])
```

---

## Alerting: Callbacks, Not Custom System

### Webhook Callbacks (Standard HTTP)

```python
from cascadeflow import CostTracker, WebhookAlert

tracker = CostTracker(
    budget_limit=10.00,
    alert_channels=[
        # Standard webhook - works with ANY system
        WebhookAlert(
            url='https://api.example.com/alerts',
            events=['budget_90', 'budget_100'],
            headers={'Authorization': 'Bearer abc123'}
        )
    ]
)

# When budget hit, CascadeFlow POSTs standard JSON:
# POST https://api.example.com/alerts
# {
#   "event": "budget_threshold",
#   "threshold": 0.90,
#   "current_spend": 9.00,
#   "budget_limit": 10.00,
#   "timestamp": "2025-10-27T14:30:00Z"
# }

# User's existing system handles it (PagerDuty, custom, etc.)
```

### Callback Functions (In-Process)

```python
def on_budget_threshold(event_data):
    """User's custom alert logic."""
    if event_data['threshold'] >= 0.90:
        # User's existing Slack client
        slack.send_message(f"Budget at {event_data['threshold']*100}%!")

    # User's existing database
    db.log_alert(event_data)

tracker = CostTracker(
    budget_limit=10.00,
    on_threshold=on_budget_threshold  # User's function
)

# CascadeFlow calls user's function, user handles rest
```

### Slack Integration (Optional Helper)

```python
# Optional helper for common case, but user can use their own
from cascadeflow.alerts import SlackAlert

tracker = CostTracker(
    budget_limit=10.00,
    alert_channels=[
        SlackAlert(
            webhook='https://hooks.slack.com/services/...',  # User's webhook
            events=['budget_90'],
            message_template="Budget alert: {threshold}% used"
        )
    ]
)

# Under the hood, just posts to user's Slack webhook
# User could do same thing with WebhookAlert
```

---

## Storage: User's Choice, Not Ours

### In-Memory (Default - Zero Dependencies)

```python
# Default: In-memory tracking (no database, no setup)
tracker = CostTracker()

# Tracks in memory during session
for _ in range(100):
    result = await agent.run(query="...")

# Export when needed
tracker.export_csv('costs.csv')
```

### SQLite (Simple Persistence - Still Zero Dependencies)

```python
# Optional: SQLite for persistence (stdlib, no dependencies)
tracker = CostTracker(
    storage='sqlite:///costs.db'  # Standard SQLite
)

# Automatically persists to SQLite
# User can query with standard SQL tools
```

### User's Database (BYO Storage)

```python
# Advanced: Use user's existing database
import psycopg2

conn = psycopg2.connect(...)  # User's existing connection

def store_cost(result_metadata):
    """User's custom storage logic."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO llm_costs (user_id, cost, model, timestamp) VALUES (%s, %s, %s, %s)",
        (
            result_metadata['user_id'],
            result_metadata['total_cost'],
            result_metadata['model_used'],
            result_metadata['timestamp']
        )
    )
    conn.commit()

# User hooks into CascadeFlow
agent = CascadeAgent(
    models=[...],
    on_query_complete=store_cost  # User's function
)

# CascadeFlow calls user's function, user decides where to store
```

---

## Configuration: Simple Files, Not UI

### Environment Variables (Standard)

```python
# User's existing .env file
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# CASCADEFLOW_BUDGET_DAILY=10.00
# CASCADEFLOW_BUDGET_MONTHLY=200.00

from cascadeflow import CascadeAgent

# Automatically reads from environment
agent = CascadeAgent.from_env()

# Or explicit
agent = CascadeAgent(
    models=[...],
    budget_daily=os.getenv('CASCADEFLOW_BUDGET_DAILY', 10.00),
    budget_monthly=os.getenv('CASCADEFLOW_BUDGET_MONTHLY', 200.00),
)
```

### YAML/JSON Config (Standard Formats)

```yaml
# cascadeflow.yaml (user's config file)
models:
  - name: gpt-4o-mini
    provider: openai
    cost: 0.00015
  - name: gpt-4o
    provider: openai
    cost: 0.003

tiers:
  free:
    daily_budget: 0.10
    allowed_models: [gpt-4o-mini]
  pro:
    daily_budget: 5.00
    allowed_models: [gpt-4o-mini, gpt-4o]

quality:
  mode: fast  # rule-based only, no ML

domain_routing:
  enabled: true
  mode: fast  # rule-based only, no ML
```

```python
# Load from user's config file
agent = CascadeAgent.from_yaml('cascadeflow.yaml')

# Or from JSON
agent = CascadeAgent.from_json('cascadeflow.json')
```

---

## Developer Experience: Examples

### Example 1: FastAPI Integration (Minimal)

```python
from fastapi import FastAPI, Header
from cascadeflow import CascadeAgent
import logging

app = FastAPI()

# Use user's existing logging
logging.basicConfig(level=logging.INFO)

# Initialize agent (no custom dashboard, no custom monitoring)
agent = CascadeAgent(
    models=[...],
    tier_config={
        'free': TierConfig(daily_budget=0.10),
        'pro': TierConfig(daily_budget=5.00),
    }
)

@app.post("/query")
async def query(
    query: str,
    user_id: str = Header(...),
    user_tier: str = Header(..., default='free')
):
    # Run query
    result = await agent.run(query=query, user_id=user_id, user_tier=user_tier)

    # Use user's existing logging (automatically logged by CascadeFlow)
    # Use user's existing monitoring
    # Use user's existing error handling

    return {
        'content': result.content,
        'cost': result.metadata['total_cost'],
        'savings': result.metadata['savings_percent'],
    }

# That's it! No custom dashboard, no new monitoring tools
```

### Example 2: With User's Existing Datadog

```python
from cascadeflow import CascadeAgent
from datadog import initialize, statsd
import os

# User's existing Datadog setup
initialize(api_key=os.getenv('DATADOG_API_KEY'))

agent = CascadeAgent(models=[...])

async def run_query(query: str, user_id: str):
    result = await agent.run(query=query, user_id=user_id)

    # Send to user's existing Datadog
    statsd.increment('cascadeflow.requests', tags=[f'user:{user_id}'])
    statsd.gauge('cascadeflow.cost', result.metadata['total_cost'])
    statsd.gauge('cascadeflow.savings', result.metadata['savings_percent'])
    statsd.histogram('cascadeflow.latency', result.metadata['latency_ms'])

    return result

# User sees CascadeFlow metrics in their existing Datadog dashboard
# No new tool, no new dashboard, fits right in
```

### Example 3: With User's Existing Slack Alerts

```python
from cascadeflow import CascadeAgent, CostTracker
from slack_sdk import WebClient

# User's existing Slack client
slack = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))

def send_budget_alert(event_data):
    """User's custom alert logic using their Slack client."""
    slack.chat_postMessage(
        channel='#ops',
        text=f"CascadeFlow budget alert: {event_data['threshold']*100}% used"
    )

tracker = CostTracker(
    budget_limit=10.00,
    on_threshold=send_budget_alert  # User's existing Slack
)

agent = CascadeAgent(models=[...], cost_tracker=tracker)

# Alerts go to user's existing Slack workspace
# No custom CascadeFlow alerting system
```

### Example 4: With User's Existing Prometheus/Grafana

```python
from cascadeflow import CascadeAgent
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# User's existing Prometheus metrics
requests_counter = Counter('llm_requests_total', 'Total LLM requests', ['user_id', 'tier'])
cost_gauge = Gauge('llm_cost_current', 'Current cost', ['user_id'])
latency_histogram = Histogram('llm_latency_seconds', 'Query latency', ['model'])

agent = CascadeAgent(models=[...])

async def run_query(query: str, user_id: str, user_tier: str):
    result = await agent.run(query=query, user_id=user_id, user_tier=user_tier)

    # Update user's existing Prometheus metrics
    requests_counter.labels(user_id=user_id, tier=user_tier).inc()
    cost_gauge.labels(user_id=user_id).set(result.metadata['total_cost'])
    latency_histogram.labels(model=result.metadata['model_used']).observe(
        result.metadata['latency_ms'] / 1000
    )

    return result

# User sees metrics in their existing Grafana dashboards
# No custom CascadeFlow dashboard needed
```

---

## Export Formats (Standard)

### CSV Export

```python
tracker.export_csv('costs.csv')
```

```csv
timestamp,user_id,user_tier,query,model_used,cost,savings_percent
2025-10-27T14:30:00Z,user_123,pro,"What is 2+2?",gpt-4o-mini,0.00015,85.0
2025-10-27T14:31:00Z,user_456,free,"Explain AI",gpt-4o-mini,0.00020,80.0
```

### JSON Export

```python
data = tracker.export_json()
```

```json
{
  "total_cost": 10.50,
  "total_requests": 1000,
  "average_cost": 0.0105,
  "total_saved": 42.00,
  "average_savings_percent": 80.0,
  "by_user": {
    "user_123": {"cost": 5.25, "requests": 500, "savings": 21.00},
    "user_456": {"cost": 5.25, "requests": 500, "savings": 21.00}
  },
  "by_model": {
    "gpt-4o": {"cost": 7.00, "requests": 200},
    "gpt-4o-mini": {"cost": 3.50, "requests": 800}
  },
  "by_tier": {
    "free": {"cost": 2.10, "requests": 400},
    "pro": {"cost": 8.40, "requests": 600}
  }
}
```

### Prometheus Export

```python
metrics = tracker.export_prometheus()
```

```prometheus
# TYPE cascadeflow_cost_total counter
cascadeflow_cost_total{user_id="user_123"} 5.25
cascadeflow_cost_total{user_id="user_456"} 5.25

# TYPE cascadeflow_requests_total counter
cascadeflow_requests_total{user_id="user_123"} 500
cascadeflow_requests_total{user_id="user_456"} 500

# TYPE cascadeflow_savings_total counter
cascadeflow_savings_total{user_id="user_123"} 21.00
cascadeflow_savings_total{user_id="user_456"} 21.00
```

### SQL Export (for import into user's DB)

```python
sql = tracker.export_sql()
```

```sql
INSERT INTO llm_costs (timestamp, user_id, user_tier, query, model_used, cost, savings_percent)
VALUES
  ('2025-10-27T14:30:00Z', 'user_123', 'pro', 'What is 2+2?', 'gpt-4o-mini', 0.00015, 85.0),
  ('2025-10-27T14:31:00Z', 'user_456', 'free', 'Explain AI', 'gpt-4o-mini', 0.00020, 80.0);
```

---

## Documentation Focus

### Emphasize Integration, Not Isolation

```markdown
## Observability

CascadeFlow integrates with your existing tools:

### Logging
- Uses standard Python `logging` module
- Works with your existing log handlers
- No custom logging system

### Monitoring
- Export to Prometheus, Datadog, CloudWatch, etc.
- Rich metadata in every response
- Use your existing dashboards

### Alerting
- Webhooks (standard HTTP POST)
- Callback functions (in-process)
- Slack helper (optional)
- Use your existing alert system

### Storage
- In-memory (default, no setup)
- SQLite (stdlib, no dependencies)
- Export to CSV/JSON/SQL
- BYO database (callback functions)

**You decide where data goes. CascadeFlow just provides it.**
```

---

## Summary: Zero-Dependency DX Principles

### 1. Standard Outputs
- ✅ Structured metadata (not custom format)
- ✅ Standard logging (Python logging, not custom)
- ✅ Standard exports (CSV, JSON, Prometheus, SQL)
- ❌ No custom dashboard
- ❌ No custom monitoring system
- ❌ No custom database

### 2. User's Tools
- ✅ Works with existing logging (Winston, Pino, Python logging)
- ✅ Works with existing monitoring (Datadog, New Relic, CloudWatch)
- ✅ Works with existing dashboards (Grafana, Kibana, custom)
- ✅ Works with existing alerts (PagerDuty, Slack, email)
- ✅ Works with existing storage (PostgreSQL, MongoDB, Redis)

### 3. Callbacks, Not Services
- ✅ Webhook callbacks (standard HTTP)
- ✅ Function callbacks (in-process)
- ✅ Optional helpers (Slack, Datadog)
- ❌ No background services
- ❌ No hosted platform
- ❌ No vendor lock-in

### 4. Configuration Files, Not UI
- ✅ Environment variables (.env)
- ✅ YAML/JSON config files
- ✅ Python code
- ❌ No web UI for config
- ❌ No admin dashboard
- ❌ No hosted configuration

### 5. Export, Don't Host
- ✅ Export to CSV (user opens in Excel)
- ✅ Export to JSON (user sends to their API)
- ✅ Export to Prometheus (user's Grafana)
- ✅ Export to SQL (user's database)
- ❌ No hosted analytics
- ❌ No CascadeFlow dashboard
- ❌ No CascadeFlow visualization

---

## Benefits of This Approach

### For Developers
1. **Familiar** - Uses tools they already know
2. **Simple** - No new systems to learn
3. **Flexible** - Fits any existing stack
4. **Lightweight** - No additional services to run
5. **Portable** - Not locked into CascadeFlow ecosystem

### For Operations
1. **Consolidated** - All monitoring in one place (existing tools)
2. **Consistent** - Same alerting system for everything
3. **Proven** - Uses battle-tested monitoring tools
4. **Scalable** - User's existing infrastructure handles it
5. **Maintainable** - No additional tools to maintain

### For CascadeFlow Development
1. **Focused** - Build core features, not infrastructure
2. **Faster** - No dashboard/monitoring to build
3. **Cheaper** - No hosting costs
4. **Better** - Integrate with best-in-class tools vs building our own
5. **Adopted** - Easier adoption (no new tools required)

---

## Roadmap Updates

### v0.2.0 (Current Plan)
- ✅ Rich metadata in all responses
- ✅ Standard Python logging
- ✅ Export functions (CSV, JSON, Prometheus, SQL)
- ✅ Webhook callbacks
- ✅ Function callbacks
- ✅ Optional helpers (Slack, Datadog)
- ❌ NO custom dashboard
- ❌ NO custom monitoring
- ❌ NO hosted platform

### v0.3.0 (Future - Only If Needed)
- Optional simple dashboard (Streamlit/Gradio)
- Only if users explicitly request it
- Only if integration isn't sufficient
- Still prioritize integration over custom tools

---

This approach keeps CascadeFlow focused, lightweight, and easy to integrate into any existing stack.
