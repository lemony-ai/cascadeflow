# CascadeFlow Skill

Cost-optimized LLM routing using drafter/verifier cascade pattern. Save 50-80% on LLM costs while maintaining quality.

## Prerequisites

1. **CascadeFlow server** running (see [CascadeFlow GitHub](https://github.com/lemony-ai/cascadeflow))
2. **API keys** for your LLM providers (Anthropic, OpenAI, etc.)

## Quick Setup

### 1. Deploy CascadeFlow Server

```bash
# Clone and setup
git clone https://github.com/lemony-ai/cascadeflow.git
cd cascadeflow
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Configure API keys
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
echo "OPENAI_API_KEY=sk-proj-..." >> .env

# Start server
export $(grep -v "^#" .env | xargs)
python -m cascadeflow.integrations.openclaw.openai_server \
  --config anthropic-only.yaml --host 0.0.0.0 --port 8084
```

### 2. Configure OpenClaw

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
          "cost": {"input": 0, "output": 0},
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

### 3. Set Environment (for scripts)

```bash
export CASCADEFLOW_HOST="your-server-ip"
export CASCADEFLOW_PORT="8084"
```

Or add to your workspace's TOOLS.md:
```markdown
## CascadeFlow
- **Host:** your-server-ip
- **Port:** 8084
```

## Commands

| Command | Description |
|---------|-------------|
| `/model cascade` | Switch to CascadeFlow |
| `/cascade` | Stats summary (queries, acceptance, savings) |
| `/cascade savings` | Detailed cost breakdown by complexity |
| `/cascade health` | Server health check |

## Example Output

**`/cascade`:**
```
📊 CascadeFlow Stats
━━━━━━━━━━━━━━━━━━━━━━━
📈 Queries: 150 total
✅ Draft Accepted: 127/142 (89%)
🔀 Cascade Used: 142 (94%)
💰 Total Saved: $0.089
📉 Savings: 72%
🎯 Quality Mean: 0.98
```

**`/cascade savings`:**
```
💰 CascadeFlow Savings Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Queries: 150
Draft Acceptance: 89%

💵 Cost Comparison:
  Baseline (verifier-only): $0.124
  With Cascade:             $0.035
  ━━━━━━━━━━━━━━━━━━━━━━━
  Savings:                  $0.089 (72%)

📊 By Complexity:
  Trivial:  45 queries
  Simple:   52 queries
  Moderate: 38 queries
  Hard:     15 queries
```

## Available Configs

Pre-built configs in `configs/` directory:

| Config | Drafter | Verifier | Best For |
|--------|---------|----------|----------|
| `anthropic-only.yaml` | Haiku 3.5 | Sonnet 4 | Anthropic users |
| `openai-only.yaml` | GPT-4o-mini | GPT-4o | OpenAI users |
| `mixed.yaml` | GPT-4o-mini | Claude Opus | Best quality/cost |

## How It Works

1. **Query arrives** → CascadeFlow analyzes complexity
2. **Drafter responds** → Fast, cheap model (e.g., Haiku)
3. **Quality check** → Verify response meets threshold
4. **Accept or escalate** → Good enough? Done! Otherwise → Verifier

**Result:** Simple queries use cheap model, complex queries get premium model. You only pay for what you need.

## Metrics Explained

| Metric | Description |
|--------|-------------|
| **Draft Acceptance** | % where drafter was good enough |
| **Cascade Used** | % that went through cascade |
| **Savings** | Cost saved vs verifier-only |
| **Quality Mean** | Average quality score (1.0 = perfect) |

## Troubleshooting

**Server not responding:**
```bash
./scripts/health.sh your-host 8084
```

**Check server logs:**
```bash
tail -f /tmp/cascadeflow.log
```

**Restart server:**
```bash
pkill -f cascadeflow
# Then start again with the command above
```

## Links

- [CascadeFlow GitHub](https://github.com/lemony-ai/cascadeflow)
- [OpenClaw Docs](https://docs.openclaw.ai)
- [ClaWHub](https://clawhub.com)
