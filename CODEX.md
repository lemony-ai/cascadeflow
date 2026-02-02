# CODEX.md - cascadeflow Agent Reference

> Central reference for AI agents (Codex, Claude Code, etc.) working on cascadeflow.
> Read this first. Keep it updated.

## Project Overview

**cascadeflow** reduces LLM API costs by 40-85% through speculative execution:

> ⚠️ **BRANDING: Always use lowercase "cascadeflow"** — not CascadeFlow, Cascadeflow, or CASCADEFLOW.
1. Try cheap model first (drafter)
2. Validate quality (alignment + confidence)
3. Escalate to expensive model only if needed (verifier)

**Result:** 60-80% of queries accept the draft → massive cost savings.

| Metric | Value |
|--------|-------|
| Version | 0.6.5 (Beta) |
| Languages | Python + TypeScript |
| Maintainer | Sascha Bührle |
| License | MIT |
| Repo | https://github.com/lemony-ai/cascadeflow |

---

## Architecture Quick Reference

```
┌─────────────────────────────────────────────────────────────────┐
│                      CascadeAgent                                │
│                   (Main Orchestrator)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐   │
│  │ Pre-Router  │ → │   Drafter   │ → │  Quality Validator  │   │
│  │ (Complexity)│   │ (Cheap LLM) │   │  (Alignment+Conf)   │   │
│  └─────────────┘   └─────────────┘   └──────────┬──────────┘   │
│                                                  │              │
│                    ┌─────────────────────────────┴───┐          │
│                    │         Quality Check           │          │
│                    │  Pass → Return Draft (save $$)  │          │
│                    │  Fail → Escalate to Verifier    │          │
│                    └─────────────────────────────────┘          │
│                                     │                           │
│                          ┌──────────▼──────────┐                │
│                          │     Verifier        │                │
│                          │  (Expensive LLM)    │                │
│                          └─────────────────────┘                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
cascadeflow/
├── cascadeflow/              # Python package
│   ├── agent.py              # Main CascadeAgent orchestrator
│   ├── core/                 # Cascade execution logic
│   │   └── cascade.py        # Speculative cascade
│   ├── routing/              # Domain + complexity routing
│   │   ├── pre_router.py     # Complexity-based routing
│   │   ├── domain.py         # Domain detection (16 domains)
│   │   └── tool_router.py    # Tool capability routing
│   ├── quality/              # Quality validation ⭐ CRITICAL
│   │   ├── alignment_scorer.py  # Query-response alignment (v14)
│   │   ├── confidence.py     # Multi-signal confidence
│   │   └── quality.py        # QualityValidator
│   ├── providers/            # LLM providers (9 supported)
│   ├── telemetry/            # Cost tracking
│   └── tools/                # Tool calling support
│
├── packages/
│   └── core/                 # TypeScript @cascadeflow/core
│       └── src/
│           ├── agent.ts      # CascadeAgent (TS)
│           ├── alignment.ts  # Alignment scorer (v10 ⚠️ OUTDATED)
│           ├── quality.ts    # Quality validation
│           └── providers/    # TS providers
│
├── packages/integrations/
│   └── n8n/                  # n8n community node
│
├── tests/                    # Python tests
├── examples/                 # Usage examples
└── docs/                     # Documentation
```

---

## Critical Files (Know These)

| File | Purpose | Sync Status |
|------|---------|-------------|
| `cascadeflow/quality/alignment_scorer.py` | Query-response alignment | **v14** (latest) |
| `packages/core/src/alignment.ts` | TS alignment scorer | **v10** ⚠️ needs v11-v14 |
| `cascadeflow/quality/confidence.py` | Confidence estimation | Python only |
| `cascadeflow/agent.py` | Main orchestrator | Reference implementation |
| `cascadeflow/routing/domain.py` | Domain detection (16) | Contains FINANCIAL fix |

---

## Quality System (Most Important)

### Alignment Scorer
Measures how well response answers the query (0.0-1.0).

**Key features:**
- Keyword extraction + overlap
- Trivial query detection
- MCQ format detection (v10)
- Classification detection (v11)
- Long context QA detection (v12)
- Function call detection (v13)
- Roleplay/extraction detection (v14)

**Alignment floor:** 0.15-0.20 (prevents off-topic acceptance)

### Confidence Estimation
Multi-signal approach:
- Model logprobs (when available)
- Response structure analysis
- Alignment score integration
- Complexity-adjusted thresholds

### Quality Check Flow
```
confidence = estimate_confidence(response)
alignment = score_alignment(query, response)

if alignment < FLOOR:
    confidence = cap_confidence(confidence)  # Safety floor

threshold = get_threshold(complexity)  # 0.5-0.85 based on complexity

passed = confidence >= threshold
```

---

## Supported Domains (16)

| Domain | Keywords | Threshold |
|--------|----------|-----------|
| CODE | function, debug, code | 0.70 |
| FINANCIAL | bond, equity, interest rate, risk-return | 0.85 |
| MEDICAL | diagnosis, treatment, clinical | 0.90 |
| LEGAL | contract, liability, compliance | 0.85 |
| MATH | equation, calculate, proof | 0.90 |
| ... | See `routing/domain.py` | ... |

---

## TypeScript/Python Parity

**Goal:** Both SDKs should behave identically.

| Component | Python | TypeScript | Status |
|-----------|--------|------------|--------|
| Alignment Scorer | v14 | v10 | ⚠️ TS behind |
| Confidence | Full | Full | ✅ |
| Domain Detection | 16 domains | 16 domains | ✅ |
| Providers | 9 | 3 | TS needs more |
| Streaming | Full | Full | ✅ |
| Tool Calling | Full | Full | ✅ |

**Priority:** Keep alignment scorer in sync!

---

## Testing

### Python
```bash
cd cascadeflow
source .venv/bin/activate
pytest tests/ -v
```

### TypeScript
```bash
cd packages/core
npm test
```

### Examples
```bash
# Python
python examples/basic_usage.py

# TypeScript
cd packages/core/examples/nodejs
npx tsx basic-usage.ts
```

---

## Common Tasks

### Add new domain detection keyword
1. Edit `cascadeflow/routing/domain.py`
2. Edit `packages/core/src/routing/domain.ts`
3. Add tests
4. Update docs/domains.md

### Fix alignment scorer
1. Edit Python: `cascadeflow/quality/alignment_scorer.py`
2. Port to TS: `packages/core/src/alignment.ts`
3. Run both test suites
4. Compare basic_usage.py vs basic-usage.ts results

### Add new provider
1. Python: Create `cascadeflow/providers/newprovider.py`
2. TypeScript: Create `packages/core/src/providers/newprovider.ts`
3. Export in `__init__.py` / `index.ts`
4. Add example

---

## Git Workflow

1. **Never push to main** - Sascha releases
2. **Never merge PRs** - Sascha approves
3. **Branch naming:** `feat/[name]` or `fix/[name]`
4. **Commit often** - traceable progress
5. **Push often** - visible on GitHub

---

## Current Priorities

1. ⚠️ **Port alignment v11-v14 to TypeScript**
2. 🔧 Proxy feature integration (OpenAI + Anthropic compatible)
3. 📊 Benchmark improvements

---

## Links

- [Architecture Details](docs/ARCHITECTURE.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Examples](examples/)
- [n8n Integration](packages/integrations/n8n/)
