# CascadeFlow Architecture & Code Structure

This document explains the architecture and organization of CascadeFlow to help contributors quickly understand and navigate the codebase.

---

## Table of Contents

1. [Quick Overview](#quick-overview)
2. [Directory Structure](#directory-structure)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Key Design Patterns](#key-design-patterns)
6. [Module Guide](#module-guide)
7. [Common Tasks](#common-tasks)

---

## Quick Overview

**CascadeFlow** reduces LLM API costs by 40-85% through **speculative execution**:

1. Try cheap model first (draft)
2. Validate quality
3. Escalate to expensive model only if needed (verifier)

**Result:** 70-80% of queries accept the draft, avoiding expensive model calls entirely.

---

## Directory Structure

```
cascadeflow/
│
├── 📄 Root-Level Files (Main Entry Point)
│   ├── agent.py              Main CascadeAgent orchestrator (1,565 lines)
│   └── __init__.py           Public API exports + backward compatibility
│
├── 📁 schema/                Data Structures & Configuration
│   ├── __init__.py           Schema module exports
│   ├── config.py             ModelConfig, CascadeConfig, UserTier, etc.
│   ├── result.py             CascadeResult dataclass
│   └── exceptions.py         Custom exception hierarchy
│
├── 📁 core/                  Core Execution Engine
│   ├── __init__.py           Core module exports
│   ├── cascade.py            Speculative cascade implementation (was speculative.py)
│   └── execution.py          Domain detection & execution planning
│
├── 📁 providers/             LLM Provider Implementations
│   ├── base.py               BaseProvider interface
│   ├── openai.py             OpenAI provider (GPT-4, GPT-3.5)
│   ├── anthropic.py          Anthropic provider (Claude)
│   ├── groq.py               Groq provider (Llama, Mixtral)
│   ├── ollama.py             Ollama provider (local models)
│   ├── vllm.py               vLLM provider (self-hosted)
│   ├── huggingface.py        HuggingFace Inference API
│   └── together.py           Together AI provider
│
├── 📁 quality/               Quality Validation System
│   ├── quality.py            QualityValidator, QualityConfig
│   ├── confidence.py         Confidence scoring
│   ├── alignment_scorer.py   Query-response alignment
│   ├── complexity.py         ComplexityDetector (5-level analysis)
│   ├── query_difficulty.py   Query difficulty estimation
│   └── tool_validator.py     Tool call validation
│
├── 📁 routing/               Routing & Decision Logic
│   ├── base.py               Base router interface
│   ├── router.py             Main router implementation
│   ├── pre_router.py         Complexity-based routing (text queries)
│   ├── tool_router.py        Capability filtering (tools)
│   ├── complexity_router.py  Tool-specific complexity routing
│   └── tool_complexity.py    Tool complexity analysis
│
├── 📁 streaming/             Streaming Response Handling
│   ├── base.py               StreamManager (text-only streaming)
│   ├── tools.py              ToolStreamManager (tool call streaming)
│   └── utils.py              Streaming utilities
│
├── 📁 telemetry/             Metrics, Cost Tracking & Monitoring
│   ├── cost_calculator.py    CostCalculator (v2.5+ single source of truth)
│   ├── collector.py          MetricsCollector (statistics aggregation)
│   ├── cost_tracker.py       CostTracker (historical tracking)
│   └── callbacks.py          CallbackManager (event-based monitoring)
│
├── 📁 tools/                 Tool Calling Framework
│   ├── call.py               Tool call handling
│   ├── config.py             Tool configuration
│   ├── executor.py           Tool execution
│   ├── formats.py            Tool format conversion
│   ├── result.py             Tool result dataclass
│   └── examples.py           Example tool definitions
│
├── 📁 utils/                 Helper Utilities
│   ├── helpers.py            Logging, formatting, token estimation
│   ├── caching.py            Response caching (ResponseCache)
│   └── presets.py            Smart presets (CascadePresets)
│
└── 📁 interface/             Visual Feedback & UI
    └── visual_consumer.py    Terminal visual indicators (pulsing dots)
```

---

## Core Components

### 1. CascadeAgent (`agent.py`)

**Purpose:** Main orchestrator - entry point for all queries

**Key Methods:**
- `run(query)` - Execute query with cascading
- `run_streaming(query)` - Execute with streaming
- `stream_events(query)` - Low-level streaming API

**Responsibilities:**
- Coordinate all components
- Route to appropriate execution strategy
- Calculate final costs via CostCalculator
- Manage metrics collection
- Handle callbacks

**When to modify:** Adding new top-level features, changing orchestration logic

**Location:** `cascadeflow/agent.py`

---

### 2. WholeResponseCascade (`core/cascade.py`)

**Purpose:** Core cascade execution engine (the innovation!)

**Key Method:**
- `execute(query, drafter, verifier)` - Run speculative cascade

**How it works:**
```python
# 1. Generate draft response (cheap model)
draft_response = await drafter.complete(query)

# 2. Validate quality
validation = quality_validator.validate(draft_response, query)

# 3. Decide: accept draft or escalate
if validation.passed:
    return draft_response  # ✅ 70% of queries stop here!
else:
    return await verifier.complete(query)  # ❌ Escalate to expensive model
```

**When to modify:** Changing cascade logic, quality validation integration, cost calculation

**Location:** `cascadeflow/core/cascade.py` (was `speculative.py`)

---

### 3. ComplexityDetector (`quality/complexity.py`)

**Purpose:** Analyze query complexity (5 levels: trivial, simple, moderate, hard, expert)

**Key Method:**
- `detect(query)` → QueryComplexity

**Used by:** PreRouter to decide direct vs cascade routing

**When to modify:** Improving complexity detection heuristics

**Location:** `cascadeflow/quality/complexity.py`

---

### 4. QualityValidator (`quality/quality.py`)

**Purpose:** Multi-dimensional response quality validation

**Checks:**
- Confidence score (via logprobs)
- Query-response alignment
- Response coherence
- Query difficulty vs model capability

**Key Method:**
- `validate(response, query, model)` → ValidationResult

**When to modify:** Adding new quality dimensions, tuning thresholds

**Location:** `cascadeflow/quality/quality.py`

---

### 5. ModelConfig (`schema/config.py`)

**Purpose:** Configuration dataclass for individual models

**Key Fields:**
```python
@dataclass
class ModelConfig:
    name: str                    # Model name (e.g., "gpt-4o")
    provider: str                # Provider (e.g., "openai")
    cost: float                  # Cost per 1K tokens
    speed_ms: Optional[int]      # Expected latency
    quality_score: float         # Quality rating (0.0-1.0)
    domains: List[str]           # Specialized domains
    supports_tools: bool         # Tool calling support
```

**When to modify:** Adding new configuration options for models

**Location:** `cascadeflow/schema/config.py`

---

### 6. CascadeResult (`schema/result.py`)

**Purpose:** Comprehensive result object with 30+ diagnostic fields

**Key Fields:**
```python
@dataclass
class CascadeResult:
    # Core (9 fields)
    content: str
    model_used: str
    total_cost: float
    latency_ms: float
    complexity: str
    cascaded: bool
    draft_accepted: bool
    routing_strategy: str
    reason: str

    # Quality diagnostics (4 fields)
    # Timing breakdown (5 fields)
    # Cost breakdown (3 fields)
    # Tool calling (2 fields)
    # ... 30+ total fields
```

**When to modify:** Adding new diagnostic fields for results

**Location:** `cascadeflow/schema/result.py`

---

### 7. BaseProvider (`providers/base.py`)

**Purpose:** Abstract interface for all LLM providers

**Key Methods:**
- `complete(messages, max_tokens, temperature)` → ModelResponse
- `stream(messages)` → AsyncIterator[str]
- `complete_with_tools(messages, tools)` → ModelResponse

**When to modify:** Adding new provider, changing provider contract

**Location:** `cascadeflow/providers/base.py`

---

### 8. PreRouter (`routing/pre_router.py`)

**Purpose:** Decide whether to cascade or route directly based on complexity

**Decision Logic:**
```
Trivial/Simple query    → Direct to cheap model (no cascade)
Moderate query          → Cascade (draft → quality check → maybe verifier)
Hard/Expert query       → Direct to best model (skip draft)
```

**When to modify:** Changing routing heuristics, adding new routing strategies

**Location:** `cascadeflow/routing/pre_router.py`

---

### 9. CostCalculator (`telemetry/cost_calculator.py`)

**Purpose:** Single source of truth for cost calculations (v2.5+)

**Key Method:**
- `calculate(spec_result)` → CostBreakdown

**Calculates:**
- `draft_cost` - Cost of draft model
- `verifier_cost` - Cost of verifier model (if called)
- `total_cost` - Properly aggregated total
- `cost_saved` - Savings vs using best model only

**When to modify:** Changing cost calculation logic, adding new cost metrics

**Location:** `cascadeflow/telemetry/cost_calculator.py`

---

## Data Flow

### High-Level Flow

```
User Query (str)
    ↓
CascadeAgent.run()
    ↓
PreRouter (decide: cascade vs direct?)
    ↓
WholeResponseCascade.execute()
    ↓
Drafter.complete() → ModelResponse
    ↓
QualityValidator.validate() → ValidationResult
    ↓
    ├─ PASSED → Return draft (cost: draft only) ✅
    └─ FAILED → Verifier.complete() → ModelResponse (cost: draft + verifier) ❌
    ↓
CostCalculator.calculate() → CostBreakdown
    ↓
CascadeResult (final result with 30+ diagnostic fields)
```

### Detailed Data Structures

```python
# Input
query: str = "What is Python?"

# From Provider
ModelResponse = {
    content: str,
    tokens_used: int,
    cost: float,
    logprobs: list[float],
    ...
}

# From Cascade
SpeculativeResult = {
    content: str,
    draft_response: ModelResponse,
    verifier_response: Optional[ModelResponse],
    quality_check_passed: bool,
    ...
}

# Final Output
CascadeResult = {
    content: str,                 # Final response
    model_used: str,              # Which model produced final response
    total_cost: float,            # Total cost
    draft_accepted: bool,         # Was draft accepted?
    complexity: str,              # Query complexity level
    quality_score: float,         # Quality validation score
    latency_ms: float,            # Total execution time
    # ... 23+ more diagnostic fields
}
```

---

## Key Design Patterns

### 1. Deferral/Escalation Pattern ⭐ (Core Innovation)

**What:** Try cheap approach first, escalate only if needed

**Where:** `core/cascade.py` - WholeResponseCascade

**Why:** This is how we save 40-85% on costs!

```python
# Traditional: Always use best model
response = await expensive_model.complete(query)  # $$$$

# CascadeFlow: Try cheap first
draft = await cheap_model.complete(query)  # $
if quality_check_passes(draft):
    return draft  # ✅ Save money!
else:
    return await expensive_model.complete(query)  # $$$$ (only when needed)
```

---

### 2. Strategy Pattern

**What:** Multiple routers, each decides one aspect

**Where:** `routing/` - PreRouter, ToolRouter, ComplexityRouter

**Why:** Separation of concerns, composable decision-making

---

### 3. Adapter Pattern

**What:** BaseProvider abstracts all LLM APIs

**Where:** `providers/` - Each provider implements BaseProvider interface

**Why:** Easy to add new providers, consistent interface

---

### 4. Observer Pattern

**What:** Telemetry observes all results without coupling

**Where:** `telemetry/callbacks.py` - CallbackManager

**Why:** Monitoring without modifying core logic

---

### 5. Composite Pattern

**What:** Multiple validators combine for final quality decision

**Where:** `quality/` - Multiple validators combine scores

**Why:** Multi-dimensional quality assessment

---

## Module Guide

### When to modify each module:

| Module | Modify when you want to... | Location |
|--------|----------------------------|----------|
| `agent.py` | Add new top-level features, change orchestration | `cascadeflow/agent.py` |
| `core/cascade.py` | Change cascade logic, quality integration | `cascadeflow/core/cascade.py` |
| `core/execution.py` | Improve domain detection, model scoring | `cascadeflow/core/execution.py` |
| `schema/config.py` | Add new configuration options | `cascadeflow/schema/config.py` |
| `schema/result.py` | Add new diagnostic fields to results | `cascadeflow/schema/result.py` |
| `schema/exceptions.py` | Add new exception types | `cascadeflow/schema/exceptions.py` |
| `providers/*.py` | Add new LLM provider, fix provider bugs | `cascadeflow/providers/` |
| `quality/*.py` | Improve quality validation, add new checks | `cascadeflow/quality/` |
| `routing/*.py` | Change routing logic, add new routing strategies | `cascadeflow/routing/` |
| `streaming/*.py` | Improve streaming, add streaming features | `cascadeflow/streaming/` |
| `telemetry/*.py` | Add metrics, improve cost tracking | `cascadeflow/telemetry/` |
| `tools/*.py` | Improve tool calling, add tool features | `cascadeflow/tools/` |
| `utils/*.py` | Add utility functions, improve helpers | `cascadeflow/utils/` |
| `interface/*.py` | Improve terminal UI, add visual feedback | `cascadeflow/interface/` |

---

## Common Tasks

### Adding a New LLM Provider

**Files to modify:**
1. Create `cascadeflow/providers/newprovider.py`
2. Implement `BaseProvider` interface
3. Register in `cascadeflow/providers/__init__.py`
4. Add tests in `tests/test_newprovider.py`

**Example:**
```python
# cascadeflow/providers/newprovider.py
from .base import BaseProvider, ModelResponse

class NewProvider(BaseProvider):
    async def complete(self, messages, max_tokens, temperature):
        # Implementation here
        return ModelResponse(...)
```

---

### Updating Provider Pricing & Adding New Models

**Overview:**
Provider pricing is defined in each provider's `calculate_cost()` method using Python dictionaries. This approach is type-safe, fast, and requires no external file dependencies.

**Files to modify:**
1. `cascadeflow/providers/{provider}.py` - Update pricing dictionary in `calculate_cost()` method
2. Update documentation if model capabilities changed

**Example: Adding GPT-5 to OpenAI**
```python
# cascadeflow/providers/openai.py - calculate_cost() method

# OpenAI pricing per 1K tokens (as of December 2024)
# Source: https://openai.com/api/pricing/
pricing = {
    # GPT-5 series (NEW!)
    "gpt-5": {"input": 0.010, "output": 0.030},
    "gpt-5-turbo": {"input": 0.005, "output": 0.015},
    "gpt-5-mini": {"input": 0.0003, "output": 0.0012},

    # Existing models...
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
}
```

**Why Python dict over YAML/JSON:**
- ✅ Type-safe (IDE autocomplete and validation)
- ✅ No file I/O overhead (faster)
- ✅ No external dependencies
- ✅ Works in all environments (containers, serverless, etc.)
- ✅ Can be dynamically overridden in code
- ✅ Version controlled with code

**Provider Pricing Locations:**
- OpenAI: `cascadeflow/providers/openai.py` (line ~800)
- Anthropic: `cascadeflow/providers/anthropic.py` (`calculate_cost()`)
- Groq: `cascadeflow/providers/groq.py` (`calculate_cost()`)
- Together: `cascadeflow/providers/together.py` (`calculate_cost()`)
- HuggingFace: `cascadeflow/providers/huggingface.py` (`calculate_cost()`)
- Ollama: Free (always $0)
- vLLM: Self-hosted (user-defined cost in ModelConfig)

**Auto-Discovery for Local Providers:**

Both Ollama and vLLM support automatic model discovery:

```python
# Ollama - List installed models
from cascadeflow.providers.ollama import OllamaProvider
provider = OllamaProvider()
models = await provider.list_models()
# Returns: ['llama3.2:1b', 'mistral:7b', ...]

# vLLM - List served models
from cascadeflow.providers.vllm import VLLMProvider
provider = VLLMProvider(base_url="http://localhost:8000/v1")
models = await provider.list_models()
# Returns: ['meta-llama/Llama-3.2-3B-Instruct', ...]
```

**When to update pricing:**
1. Provider announces new pricing (check official pricing pages)
2. New model released with different pricing tier
3. User reports cost calculation mismatch

**Testing after pricing update:**
```bash
# Verify pricing calculation
python -c "
from cascadeflow.providers.openai import OpenAIProvider
provider = OpenAIProvider(api_key='test')
cost = provider.calculate_cost(tokens=1000, model='gpt-5')
print(f'Cost for 1K tokens: \${cost:.6f}')
"
```

---

### Adding a New Quality Check

**Files to modify:**
1. Create validator in `cascadeflow/quality/new_validator.py`
2. Integrate in `cascadeflow/quality/quality.py` (QualityValidator)
3. Update `QualityConfig` if needed
4. Add tests

**Example:**
```python
# cascadeflow/quality/new_validator.py
class NewValidator:
    def validate(self, response: str, query: str) -> float:
        # Return score 0.0-1.0
        return score
```

---

### Adding a New Routing Strategy

**Files to modify:**
1. Create router in `cascadeflow/routing/new_router.py`
2. Inherit from `BaseRouter` (if exists) or create standalone
3. Integrate in `CascadeAgent.run()`
4. Add tests

---

### Adding New Diagnostic Fields to CascadeResult

**Files to modify:**
1. `cascadeflow/schema/result.py` - Add field to dataclass
2. `cascadeflow/agent.py` - Populate field when creating result
3. `cascadeflow/__init__.py` - Update exports if needed (already exported)
4. Update documentation

---

### Improving Cost Calculation

**Files to modify:**
1. `cascadeflow/telemetry/cost_calculator.py` - Update calculation logic
2. Tests to verify accuracy
3. Documentation

**Note:** CostCalculator is the single source of truth (v2.5+). Do NOT add cost logic elsewhere!

---

## Architecture Principles

1. **Single Responsibility:** Each module has one clear purpose
2. **Separation of Concerns:** Routing, execution, validation are separate
3. **Dependency Injection:** Agent receives models/config, doesn't create them
4. **Async-First:** All I/O operations are async
5. **Observable:** Telemetry can observe without coupling
6. **Testable:** Core logic separated from I/O
7. **Extensible:** Easy to add providers, routers, validators

---

## Performance Characteristics

**Cascade Performance:**
- Draft acceptance rate: 70-80% (typical)
- Cost savings: 40-85% vs always using best model
- Latency: 2-10x faster (when draft accepted)
- Quality: Equal or better (validation ensures threshold)

**When to skip cascade:**
- Very simple queries → Direct to cheap model (PreRouter decides)
- Very complex queries → Direct to best model (PreRouter decides)
- User forces direct → `force_direct=True` parameter

---

## Import Patterns

### Recommended (Top-Level)

```python
from cascadeflow import (
    CascadeAgent,
    ModelConfig,
    CascadeResult,
    WholeResponseCascade,
    QualityConfig,
)
```

### Backward Compatible (Old Paths)

```python
# Still works! (for backward compatibility)
from cascadeflow.config import ModelConfig
from cascadeflow.exceptions import CascadeFlowError
from cascadeflow.speculative import WholeResponseCascade
```

### New Organized Paths

```python
# Clearer structure
from cascadeflow.schema.config import ModelConfig
from cascadeflow.schema.exceptions import CascadeFlowError
from cascadeflow.core.cascade import WholeResponseCascade
```

**All three patterns work!** Use top-level imports for simplicity.

---

## Testing Strategy

**Test locations:**
- `tests/test_agent.py` - CascadeAgent integration tests
- `tests/test_mvp_cascade_direct.py` - Cascade logic tests
- `tests/test_quality_*.py` - Quality validation tests
- `tests/test_providers/` - Provider-specific tests (if organized)
- `tests/test_routing.py` - Routing logic tests

**Run tests:**
```bash
pytest                          # All tests
pytest tests/test_agent.py      # Specific file
pytest -v                       # Verbose
pytest --cov=cascadeflow        # With coverage
```

---

## Backward Compatibility

**100% backward compatible!** All old import paths still work via `sys.modules` aliasing in `__init__.py`:

```python
# In cascadeflow/__init__.py
sys.modules['cascadeflow.exceptions'] = schema.exceptions
sys.modules['cascadeflow.result'] = schema.result
sys.modules['cascadeflow.config'] = schema.config
sys.modules['cascadeflow.execution'] = core.execution
sys.modules['cascadeflow.speculative'] = core.cascade
```

This means existing code continues to work without changes.

---

## Recent Changes

### v0.2.0 (December 2024) - Production Readiness

**Code Quality:**
- Removed 85 changelog-style comments from codebase (cleaner, more maintainable)
- Professional production-ready code without bloat
- Verified no inline test suites (proper test separation already exists)

**Examples & Documentation:**
- Fixed `edge_device.py` example (imports, indentation, syntax)
- Created `docs/guides/edge_device.md` (600-line comprehensive guide)
- Updated `examples/README.md` (now documents all 11 examples)
- Moved `test_cascadeflow.py` to proper `tests/` directory
- Total documentation: 10 guides, ~10,280 lines

**Provider Updates:**
- Added GPT-5 family to OpenAI provider (gpt-5, gpt-5-turbo, gpt-5-mini)
- Updated pricing with proper documentation and source references
- Organized pricing by model generation (GPT-5 → GPT-4o → GPT-4 → GPT-3.5)
- Verified auto-discovery already implemented for Ollama and vLLM

**Developer Experience:**
- Easy to get started (all examples validated and working)
- Scales to production (clean code, documented patterns)
- State-of-the-art Python approach (Pydantic, type-safe, no external config files)

---

### v0.1.0 (October 2024) - Major Restructuring

**Structure Changes:**
- Created `schema/` directory for data structures (config, result, exceptions)
- Created `core/` directory for execution engine (cascade, execution)
- Renamed `speculative.py` → `cascade.py` for clarity
- Moved `utils.py`, `caching.py`, `presets.py` → `utils/` directory
- Root level now only contains `agent.py` and `__init__.py`

**Benefits:**
- Clearer separation of concerns
- Easier navigation for contributors
- Follows industry best practices (FastAPI, Django patterns)
- 100% backward compatible (all old imports still work)

---

## Next Steps

- **New Contributors:** Start with [CONTRIBUTING.md](CONTRIBUTING.md) (coming soon)
- **Adding Features:** Review this document + [CLAUDE.md](CLAUDE.md)
- **Architecture Deep Dive:** See [CLAUDE.md](CLAUDE.md) for detailed component descriptions
- **Questions:** Open an issue on GitHub

---

**Last Updated:** October 2024
**Version:** v0.1.0 (with restructuring)
**Commit:** `6165e54` - Major directory reorganization
