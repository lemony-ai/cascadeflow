# CascadeResult (Python)

Result object returned from cascade agent execution with comprehensive diagnostics.

## Class: `CascadeResult`

```python
from cascadeflow import CascadeResult
```

## Fields

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | Generated response text |
| `model_used` | `str` | Model that produced final response |
| `total_cost` | `float` | Total cost in USD (properly aggregated) |
| `latency_ms` | `int` | Total latency in milliseconds |
| `complexity` | `str` | Detected complexity level ("simple", "moderate", "complex", "expert") |
| `cascaded` | `bool` | Whether cascade was used |
| `draft_accepted` | `bool` | If cascaded, whether draft was accepted |
| `routing_strategy` | `str` | How query was routed ("direct" or "cascade") |
| `reason` | `str` | Explanation for routing decision |

### Tool Calling

| Field | Type | Description |
|-------|------|-------------|
| `tool_calls` | `List[Dict]` | Tool calls made by model (if any) |
| `has_tool_calls` | `bool` | Whether response includes tool calls |

### Quality Diagnostics

| Field | Type | Description |
|-------|------|-------------|
| `quality_score` | `float` | Quality score from validator (0-1) |
| `quality_threshold` | `float` | Threshold used for validation |
| `quality_check_passed` | `bool` | Whether quality check passed |
| `rejection_reason` | `Optional[str]` | Why draft was rejected (if applicable) |

### Response Tracking

| Field | Type | Description |
|-------|------|-------------|
| `draft_response` | `Optional[str]` | Full draft response text |
| `verifier_response` | `Optional[str]` | Full verifier response (if cascaded) |
| `response_length` | `int` | Length of final response |
| `response_word_count` | `int` | Word count of final response |

### Timing Breakdown

| Field | Type | Description |
|-------|------|-------------|
| `complexity_detection_ms` | `int` | Time to detect complexity |
| `draft_generation_ms` | `int` | Time to generate draft |
| `quality_verification_ms` | `int` | Time for quality validation |
| `verifier_generation_ms` | `int` | Time to generate verifier response |
| `cascade_overhead_ms` | `int` | Additional overhead from cascade system |

### Cost Breakdown

| Field | Type | Description |
|-------|------|-------------|
| `draft_cost` | `float` | Cost of draft generation |
| `verifier_cost` | `float` | Cost of verifier generation |
| `cost_saved` | `float` | Cost saved vs always using best model |
| `cost_saved_percentage` | `float` | Savings as percentage (0-100) |

---

## Examples

### Basic Usage

```python
result = await agent.run("What is Python?")

print(f"Answer: {result.content}")
print(f"Model: {result.model_used}")
print(f"Cost: ${result.total_cost:.6f}")
print(f"Latency: {result.latency_ms}ms")
```

### Analyzing Cascade Behavior

```python
result = await agent.run("Explain quantum computing")

if result.cascaded:
    if result.draft_accepted:
        print(f"✅ Draft accepted from {result.model_used}")
        print(f"Saved ${result.cost_saved:.6f} ({result.cost_saved_percentage:.1f}%)")
    else:
        print(f"❌ Draft rejected: {result.rejection_reason}")
        print(f"Escalated to {result.model_used}")
else:
    print(f"Direct execution: {result.reason}")
```

### Quality Metrics

```python
result = await agent.run("Write production-ready code")

print(f"Quality score: {result.quality_score:.2f}")
print(f"Threshold: {result.quality_threshold:.2f}")
print(f"Passed: {result.quality_check_passed}")

if result.quality_score < 0.7:
    print("⚠️ Low quality detected")
```

### Performance Analysis

```python
result = await agent.run("Generate a report")

print(f"Total time: {result.latency_ms}ms")
print(f"  Complexity detection: {result.complexity_detection_ms}ms")
print(f"  Draft generation: {result.draft_generation_ms}ms")
print(f"  Quality verification: {result.quality_verification_ms}ms")

if result.verifier_generation_ms:
    print(f"  Verifier generation: {result.verifier_generation_ms}ms")

print(f"Cascade overhead: {result.cascade_overhead_ms}ms")
```

### Cost Analysis

```python
result = await agent.run("Summarize this document")

print(f"Draft cost: ${result.draft_cost:.6f}")
if result.verifier_cost:
    print(f"Verifier cost: ${result.verifier_cost:.6f}")
print(f"Total cost: ${result.total_cost:.6f}")
print(f"Saved: ${result.cost_saved:.6f} ({result.cost_saved_percentage:.1f}%)")
```

### Tool Call Inspection

```python
tools = [{"name": "get_weather", "description": "Get weather", "parameters": {...}}]
result = await agent.run("What's the weather?", tools=tools)

if result.has_tool_calls:
    for call in result.tool_calls:
        print(f"Tool: {call['name']}")
        print(f"Arguments: {call['arguments']}")
        print(f"ID: {call['id']}")
```

---

## Response Types

### Successful Cascade (Draft Accepted)

```python
CascadeResult(
    content="Python is a high-level programming language...",
    model_used="gpt-4o-mini",
    total_cost=0.000042,
    cascaded=True,
    draft_accepted=True,
    quality_score=0.85,
    cost_saved=0.006208,
    cost_saved_percentage=99.3
)
```

### Escalation (Draft Rejected)

```python
CascadeResult(
    content="Quantum computing is a revolutionary paradigm...",
    model_used="gpt-4o",
    total_cost=0.006250,
    cascaded=True,
    draft_accepted=False,
    rejection_reason="Insufficient detail (quality: 0.62 < 0.70)",
    quality_score=0.92,
    cost_saved=0.0,
    cost_saved_percentage=0.0
)
```

### Direct Execution (Complex Query)

```python
CascadeResult(
    content="Advanced machine learning explanation...",
    model_used="gpt-4o",
    total_cost=0.006250,
    cascaded=False,
    draft_accepted=None,
    routing_strategy="direct",
    reason="Query complexity: expert-level",
    quality_score=0.95
)
```

---

## See Also

- [CascadeAgent](./agent.md) - Agent class that returns results
- [ModelConfig](./config.md) - Model and quality configuration (includes QualityConfig)
- [Cost Tracking Guide](../../guides/cost_tracking.md) - Analyzing costs and metrics
