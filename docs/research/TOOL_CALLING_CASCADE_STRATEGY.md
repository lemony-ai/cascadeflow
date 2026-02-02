# Tool Calling Cascade Strategy Investigation (Planning Only)

## 1. Current Tool Calling Architecture

### High-level flow (tool path)
* **Tool queries are detected by the presence of `tools` in the request**, which routes execution to the tool path in `Cascade._execute_tool_path`. The tool path is responsible for tool complexity analysis, drafting with tools, tool-quality validation, and escalation to the verifier if validation fails.【F:cascadeflow/core/cascade.py†L560-L883】
* **Tool complexity analysis** is performed by `ToolComplexityAnalyzer`, which scores a request using eight indicators and maps it to one of five complexity levels (TRIVIAL → EXPERT). This analysis is used both for routing and for adaptive tool validation thresholds.【F:cascadeflow/routing/tool_complexity.py†L1-L229】【F:cascadeflow/routing/tool_complexity.py†L240-L456】
* **Tool routing** (complexity-based) is implemented in `ComplexityRouter`, which maps TRIVIAL/SIMPLE/MODERATE to tool cascade and HARD/EXPERT to direct large-model routing, with expected cost savings documented in the router itself.【F:cascadeflow/routing/complexity_router.py†L1-L204】
* **Tool capability filtering** lives in `ToolRouter`, which ensures models that lack tool support are filtered out when tools are provided.【F:cascadeflow/routing/tool_router.py†L1-L129】

### Tool call quality validation
* **Tool drafts are accepted/rejected in `_should_accept_tool_draft`**, which rejects drafts with no tool calls and otherwise delegates to `ToolQualityValidator` for a weighted, 5-level validation result and adaptive thresholds based on tool complexity.【F:cascadeflow/core/cascade.py†L910-L963】【F:cascadeflow/quality/tool_validator.py†L1-L214】
* **ToolQualityValidator uses five validation levels** (JSON validity, schema match, tool existence, required fields, parameter sanity) with weights and adaptive thresholds (TRIVIAL: 0.70, SIMPLE: 0.75, MODERATE: 0.85; default 0.80). It also documents expected acceptance rates of 92%/76%/47% for TRIVIAL/SIMPLE/MODERATE respectively.【F:cascadeflow/quality/tool_validator.py†L1-L134】【F:cascadeflow/quality/tool_validator.py†L169-L231】
* **Streaming tool cascades** include a separate validation path in `ToolStreamManager`, which validates tool calls and optionally reuses `ToolQualityValidator` with its own thresholding behavior (default 0.75 when a float score is returned).【F:cascadeflow/streaming/tools.py†L430-L569】

### Tool call vs text path
* If **no tools are supplied**, the cascade uses the **text path**, which relies on `QualityValidator` and alignment scoring rather than `ToolQualityValidator`. This matters for BFCL since that benchmark uses prompt-based tool descriptions instead of actual tool schemas.【F:cascadeflow/core/cascade.py†L560-L605】【F:cascadeflow/quality/quality.py†L560-L740】
* The **alignment scorer explicitly detects function/tool call prompts** and can assign a fixed 0.72 alignment “boost” when the response looks like a valid tool call, which influences the acceptance logic for text-path tool prompts.【F:cascadeflow/quality/alignment_scorer.py†L640-L860】【F:cascadeflow/quality/alignment_scorer.py†L1120-L1190】

### BFCL benchmark harness
* The BFCL benchmark defines tool descriptions in the prompt and **calls `CascadeAgent.run()` without passing `tools`**. That means the “tool calling” evaluation is handled by the **text path**, not the tool path or tool validator logic.【F:tests/benchmarks/bfcl/bfcl_full_benchmark.py†L342-L472】
* The benchmark expects “Tool: <tool_name> / Parameters: <JSON>” formatted responses or a “no tool needed” explanation, which is aligned with the alignment scorer’s function-call response detection but does not trigger tool-mode validation.【F:tests/benchmarks/bfcl/bfcl_full_benchmark.py†L366-L426】【F:cascadeflow/quality/alignment_scorer.py†L769-L860】

---

## 2. Root Cause Analysis: Why Are Tool Call Drafts Rejected?

### Primary root cause (bench harness mismatch)
* **BFCL uses prompt-level tool descriptions and never passes `tools` into the cascade**, so tool drafts are never evaluated via `ToolQualityValidator`. This means the tool-specific acceptance logic (including the expected TRIVIAL/SIMPLE/MODERATE acceptance rates) is not exercised at all in the current BFCL harness.【F:tests/benchmarks/bfcl/bfcl_full_benchmark.py†L342-L472】【F:cascadeflow/quality/tool_validator.py†L1-L36】

### Likely rejection reasons in text path for BFCL prompts
* The text path uses **standard quality checks** (confidence, length, specificity, alignment, etc.), and **tool-format responses only get lenient handling if the alignment scorer detects a valid function-call response**. If the draft response doesn’t match the expected “Tool/Parameters” format or JSON markers, the alignment boost is not applied, leading to low effective confidence and rejections.【F:cascadeflow/quality/quality.py†L560-L740】【F:cascadeflow/quality/alignment_scorer.py†L769-L860】【F:cascadeflow/quality/alignment_scorer.py†L1120-L1190】
* **Drafts with no tool calls are hard-rejected in the tool path**, but in the BFCL harness the model is never actually calling tools, it is writing formatted text. This further underscores that BFCL results are currently measuring **text validation behavior**, not true tool calling behavior.【F:cascadeflow/core/cascade.py†L910-L932】【F:tests/benchmarks/bfcl/bfcl_full_benchmark.py†L366-L426】

### Secondary root causes to investigate (once tool path is exercised)
* **Tool schema mismatch**: `ToolQualityValidator` expects available tools in the universal `{"name", "description", "parameters"}` format. If BFCL or other tool-call tests are using provider-native formats (e.g., OpenAI’s `{"type": "function", "function": {...}}`), tool existence and required-field checks will fail, driving rejections.【F:cascadeflow/quality/tool_validator.py†L278-L344】
* **Strict schema/parameter validation**: `ToolQualityValidator` requires arguments to parse cleanly into dicts and required fields to be present; any partial JSON or omitted required values triggers rejection.【F:cascadeflow/quality/tool_validator.py†L316-L365】

---

## 3. Tool Call Classification Taxonomy (Draft)

This taxonomy is intended to **mirror the existing tool complexity signals** while adding routing-specific categories.

| Category | Description | Likely Complexity Signals | Examples |
| --- | --- | --- | --- |
| **Simple Lookup** | Single tool, explicit params | Low ambiguity, low parameter count | Weather lookup, single search |
| **Single Tool + Inference** | Single tool but implicit/ambiguous params | Ambiguity signals | “Find relevant docs” |
| **Parallel Calls** | Multiple calls that can run concurrently | Iterative operations or multi-step but no dependency | “Get weather in London and Berlin” |
| **Sequential Multi-Step** | Multi-call with dependency | Multi-step signal, conditional logic | “Search then summarize” |
| **Conditional / Branching** | Call depends on condition | Conditional logic | “If approved, send email” |
| **High-Structure / Nested** | Tools with nested object/array params | Nested structures, high parameter count | “Create project with team members” |
| **Tool Selection / Ambiguity** | Many tools, unclear best choice | Tool selection difficulty | “Send a message” w/ email, SMS, Slack |

Mapping to existing indicators:
* `ToolComplexityAnalyzer` already covers multi-step, ambiguous params, nested structures, tool selection, conditional logic, iterative operations, and high parameter count, so this taxonomy can be derived directly from those indicators and scores.【F:cascadeflow/routing/tool_complexity.py†L78-L214】【F:cascadeflow/routing/tool_complexity.py†L240-L456】

---

## 4. Architecture Options (Pros/Cons/Effort)

### Option A — Adapted Cascade Logic (Tool-specific thresholds)
**Idea:** Adjust acceptance thresholds and validation logic for tool calls rather than reusing text-path quality.

**Pros**
* Leverages existing `ToolQualityValidator` and adaptive thresholds already defined for tool calls.【F:cascadeflow/quality/tool_validator.py†L1-L134】
* Keeps cost savings structure intact (tool cascade stays primary path).【F:cascadeflow/routing/complexity_router.py†L66-L104】

**Cons**
* Requires **fixing BFCL harness to exercise the tool path**; otherwise changes won’t move BFCL acceptance rates.【F:tests/benchmarks/bfcl/bfcl_full_benchmark.py†L342-L472】
* Tool schema format mismatches can still cause rejections unless normalized (needs validation).

**Effort:** Medium (threshold tuning + schema normalization + benchmark harness updates).

---

### Option B — Parallel Draft + Verifier for Tool Calls
**Idea:** Run small and large models concurrently for tool calls, accept the first valid tool call result.

**Pros**
* Mitigates failures from weak tool-calling in small models.
* Simplifies acceptance: first valid schema wins (tool validator can arbitrate).

**Cons**
* Higher cost and latency overhead; needs careful cost modeling to prevent negating cascade savings.
* Requires concurrency orchestration (not present today in tool path).【F:cascadeflow/core/cascade.py†L560-L883】

**Effort:** Medium/High (introduce parallel calls + cancellation mechanics).

---

### Option C — Hybrid: Cascade for Simple Tools, Parallel for Complex
**Idea:** Use `ToolComplexityAnalyzer` to pick cascade vs parallel (or direct) based on tool complexity.

**Pros**
* Uses existing complexity analysis infrastructure and cluster mapping.【F:cascadeflow/routing/tool_complexity.py†L34-L70】【F:cascadeflow/routing/complexity_router.py†L156-L204】
* Limits parallel execution to hard cases, protecting cost savings.

**Cons**
* Requires calibrating complexity thresholds for tool calls with real data.
* Adds operational complexity in routing and telemetry.

**Effort:** Medium (build on complexity router + add parallel execution branch).

---

### Option D — Tool-Specific Routing
**Idea:** Route by tool type (e.g., “critical tools” always use verifier) rather than by complexity alone.

**Pros**
* Simple policy for high-risk or high-cost tools.
* Can be implemented as a rule-based overlay on existing routing logic.【F:cascadeflow/routing/complexity_router.py†L156-L204】

**Cons**
* Requires maintaining per-tool policies and risk tags.
* Risk of inconsistent routing behavior unless clearly specified.

**Effort:** Low/Medium (policy config + integration).

---

## 5. Recommendation (Planning)

**Primary recommendation:** **Fix the benchmark harness to drive the tool path**, then pursue **Option C (Hybrid)** with targeted threshold tuning.

**Reasoning:**
1. **BFCL currently measures text-path behavior**, so tool acceptance cannot improve until the benchmark uses actual tool schemas and tool calls.【F:tests/benchmarks/bfcl/bfcl_full_benchmark.py†L342-L472】
2. The codebase already has **tool-specific validation and adaptive thresholds** designed to produce acceptance rates for TRIVIAL/SIMPLE/MODERATE tool calls.【F:cascadeflow/quality/tool_validator.py†L1-L36】
3. The **complexity router is designed for tool call routing**, which can be extended to choose cascade vs parallel strategies in a hybrid mode while preserving cost savings for simple tool calls.【F:cascadeflow/routing/complexity_router.py†L66-L104】【F:cascadeflow/routing/tool_complexity.py†L34-L70】

---

## 6. Implementation Roadmap (Planning)

1. **Benchmark alignment**
   * Update BFCL harness to pass `tools` into `CascadeAgent.run()` and validate actual tool call responses.
   * Ensure tool schema format is universal (`name/description/parameters`) to satisfy `ToolQualityValidator`.
   * Add logging for tool path acceptance vs text path acceptance.

2. **Tool validation tuning**
   * Calibrate `ToolQualityValidator` thresholds for TRIVIAL/SIMPLE/MODERATE using actual BFCL tool-call runs.
   * Expand validator to accept common provider-specific tool schema variations (if required).

3. **Routing strategy**
   * Use `ToolComplexityAnalyzer` to split simple vs complex tool calls.
   * Route TRIVIAL/SIMPLE to cascade-only; MODERATE to cascade+parallel; HARD/EXPERT to direct verifier.

4. **Telemetry**
   * Add metrics for tool-call draft acceptance by complexity and tool type.
   * Track rejection reasons (e.g., schema mismatch, missing required fields).

---

## 7. Expected Acceptance Rate Improvement

Based on existing tool validation thresholds and documented expectations:
* **TRIVIAL:** 0% → **~90%+** (validator expectation ~92%).【F:cascadeflow/quality/tool_validator.py†L16-L36】
* **SIMPLE:** 0% → **~70–80%** (validator expectation ~76%).【F:cascadeflow/quality/tool_validator.py†L16-L36】
* **MODERATE:** 0% → **~40–50%** (validator expectation ~47%).【F:cascadeflow/quality/tool_validator.py†L16-L36】

These improvements **only become possible after BFCL is driven through the tool path** rather than the text path, because `ToolQualityValidator` and tool complexity analysis are otherwise bypassed.【F:tests/benchmarks/bfcl/bfcl_full_benchmark.py†L342-L472】【F:cascadeflow/core/cascade.py†L560-L883】
