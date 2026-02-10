# CascadeFlow for OpenClaw

Cost-saving AI inference via drafter/verifier cascade. Route requests through a cheap fast model first, only escalate to expensive models when needed.

## Features

- **70-90% cost savings** on typical workloads
- **OpenAI-compatible API** - drop-in replacement
- **Tool calling support** - works with OpenClaw tools
- **Agent loops** - multi-turn conversations preserved
- **Domain routing** - code, creative, general, tool domains
- **Quality verification** - semantic similarity scoring

## Quick Start

```bash
# Install
pip install cascadeflow

# Start with a preset
cascadeflow serve --config configs/openai-only.yaml

# Configure OpenClaw
# Add to providers in openclaw.yaml:
providers:
  cascadeflow:
    baseUrl: "http://localhost:8084/v1"
    model: "cascadeflow"
```

## Provider Presets

| Preset | Drafter | Verifier | Best For |
|--------|---------|----------|----------|
| `openai-only` | gpt-4o-mini | gpt-4o | Parallel tools, balanced |
| `anthropic-only` | claude-haiku | claude-sonnet | Speed (2.94 QPS), quality |
| `mixed` | gpt-4o-mini | claude-sonnet | Cheap + quality |

## Commands

Once integrated with OpenClaw, use these commands:

| Command | Description |
|---------|-------------|
| `/cascade` | Show stats summary |
| `/cascade savings` | Cost breakdown |
| `/cascade health` | Acceptance rates |
| `/cascade config` | Current preset |

## Benchmark Results

Tested with 200 diverse queries:

| Metric | OpenAI | Anthropic | Mixed |
|--------|--------|-----------|-------|
| Acceptance | 74.9% | 41.7% | 70.9% |
| Quality | 0.914 | 0.987 | 0.908 |
| Cost | $0.038 | $0.017 | $0.042 |
| Latency | 4991ms | 1754ms | 5190ms |

## Architecture

```
User Request
     ↓
[Complexity Detection] → trivial/simple/moderate/hard
     ↓
[Domain Detection] → general/code/creative/tool
     ↓
[Drafter Model] → Fast, cheap response
     ↓
[Quality Check] → Semantic similarity scoring
     ↓
  Accept? ──Yes──→ Return draft (💰 saved!)
     │
    No
     ↓
[Verifier Model] → High-quality response
     ↓
Return verified response
```

## Stats API

```bash
# Health check
curl http://localhost:8084/health

# Full stats
curl http://localhost:8084/stats

# Per-request stats in response
{
  "cascadeflow": {
    "model_used": "gpt-4o-mini",
    "metadata": {
      "draft_accepted": true,
      "quality_score": 1.0,
      "complexity": "simple",
      "cascade_overhead_ms": 52
    }
  }
}
```

## Files

```
configs/
├── openai-only.yaml      # GPT-4o-mini → GPT-4o
├── anthropic-only.yaml   # Haiku → Sonnet
└── mixed.yaml            # GPT-4o-mini → Sonnet
```

## Requirements

- Python 3.10+
- OpenAI API key (for OpenAI models)
- Anthropic API key (for Anthropic models)
- ~40MB disk for embedding model (auto-downloaded)

## License

MIT
