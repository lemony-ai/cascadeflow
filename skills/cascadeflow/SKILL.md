# CascadeFlow Skill

Cost-optimized LLM routing using drafter/verifier cascade pattern.

## Quick Start

```bash
# Check health
/cascade health

# View stats summary
/cascade

# Detailed savings report
/cascade savings
```

## Commands

| Command | Description |
|---------|-------------|
| `/cascade` | Stats summary (queries, acceptance, savings) |
| `/cascade savings` | Detailed cost breakdown by complexity |
| `/cascade health` | Server health check |
| `/cascade config` | Show current config (drafter/verifier models) |

## OpenClaw Provider Setup

Add to your `openclaw.json`:

```json
{
  "models": {
    "providers": {
      "cascadeflow": {
        "baseUrl": "http://YOUR_HOST:8084/v1",
        "apiKey": "local",
        "api": "openai-completions",
        "models": [{
          "id": "cascadeflow",
          "name": "CascadeFlow",
          "reasoning": false,
          "input": ["text"],
          "cost": {"input": 0.0008, "output": 0.0024},
          "contextWindow": 200000,
          "maxTokens": 8192
        }]
      }
    }
  },
  "agents": {
    "defaults": {
      "models": {
        "cascadeflow/cascadeflow": {"alias": "cascade"}
      }
    }
  }
}
```

Then use: `/model cascade`

## Scripts

Scripts are in `scripts/` directory. Default host: `192.168.0.147:8084`

```bash
# Raw JSON stats
./scripts/stats.sh [host] [port]

# Formatted summary (for /cascade command)
./scripts/summary.sh [host] [port]

# Detailed savings (for /cascade savings)
./scripts/savings.sh [host] [port]

# Health check (for /cascade health)
./scripts/health.sh [host] [port]
```

## Metrics Explained

| Metric | Description |
|--------|-------------|
| **Draft Acceptance** | % of queries where drafter response was good enough |
| **Cascade Used** | % of queries that went through cascade (vs direct routing) |
| **Savings** | Cost saved vs using verifier for everything |
| **Quality Mean** | Average quality score (1.0 = perfect) |

## Response Format

**`/cascade`:**
```
📊 CascadeFlow Stats
━━━━━━━━━━━━━━━━━━━━━━━
📈 Queries: 38 total
✅ Draft Accepted: 33/34 (86%)
🔀 Cascade Used: 34 (89%)
💰 Total Saved: $0.023
📉 Savings: 70%
🎯 Quality Mean: 0.99
```

**`/cascade savings`:**
```
💰 CascadeFlow Savings Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Queries: 38
Draft Acceptance: 86%

💵 Cost Comparison:
  Baseline (verifier-only): $0.0337
  With Cascade:             $0.0099
  ━━━━━━━━━━━━━━━━━━━━━━━
  Savings:                  $0.0237 (70%)

📊 By Complexity:
  Trivial:  8 queries
  Simple:   9 queries
  Moderate: 10 queries
  Hard:     7 queries
```

## Presets

CascadeFlow supports multiple model configurations:

### Anthropic-only
- Drafter: `claude-3-5-haiku-20241022`
- Verifier: `claude-sonnet-4-20250514` or `claude-opus-4-20250514`

### OpenAI-only
- Drafter: `gpt-4o-mini`
- Verifier: `gpt-4o`

### Mixed (recommended)
- Drafter: `gpt-4o-mini` (fast, cheap)
- Verifier: `claude-opus-4-20250514` (quality)

## Environment

CascadeFlow server needs API keys in `.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
```

## Troubleshooting

**CascadeFlow offline:**
```bash
./scripts/health.sh
# Check if server is running on mgmt02
ssh cluster@192.168.0.147 'pgrep -a cascadeflow'
```

**Start server:**
```bash
ssh cluster@192.168.0.147 'cd ~/Projects/cascadeflow && export $(grep -v "^#" .env | xargs) && source .venv/bin/activate && nohup python -m cascadeflow.integrations.openclaw.openai_server --config anthropic-only.yaml --host 0.0.0.0 --port 8084 > /tmp/cascadeflow.log 2>&1 &'
```

## Links

- [CascadeFlow GitHub](https://github.com/lemony-ai/cascadeflow)
- [OpenClaw Docs](https://docs.openclaw.ai)
