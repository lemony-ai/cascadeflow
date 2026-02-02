# OpenClaw Integration Strategy (Planning)

## Scope & Assumptions
- This document is a **planning-only** proposal. It does not implement code changes.
- OpenClaw internals are not yet available in this repo; the plan below includes discovery steps and placeholders to be validated once OpenClaw docs/source are provided.
- The integration should preserve OpenClaw’s existing UX while enabling cascadeflow’s cost-optimized routing.

## OpenClaw Architecture Understanding (Hypothesis + Discovery)
Because OpenClaw documentation isn’t present in this repository, treat the following as a working model and confirm during discovery:

1. **Skill model**
   - Skills are likely organized as a directory with a `SKILL.md` manifest plus supporting code and assets.
   - Skills are probably loaded dynamically and expose a standardized entrypoint that OpenClaw can invoke (similar to a plugin/extension model).

2. **LLM invocation pipeline**
   - OpenClaw likely supports multiple providers and exposes a provider registry plus model-selection configuration.
   - LLM calls probably flow through a centralized client where routing logic and telemetry (usage/cost) can be added.

3. **Configuration patterns**
   - Expect config to include provider credentials, default model, and per-skill overrides.
   - A centralized config file or environment-variable-based system is likely used.

**Discovery checklist** (to perform when OpenClaw repo/docs are available):
- Locate OpenClaw skill spec and example skills.
- Identify model/provider configuration files and how overrides work.
- Find the LLM client abstraction and any telemetry/usage tracking hooks.

## Integration Approaches (Comparison)

### A) OpenClaw Skill that wraps cascadeflow
**Concept:** Build an OpenClaw skill that exposes cascadeflow as a callable tool. The skill invokes cascadeflow to decide the best model/provider per request.

**Pros**
- Minimal changes to OpenClaw core.
- Optional/opt-in per skill or per workflow.

**Cons**
- Only affects calls that explicitly use the skill.
- Harder to enforce global cost optimization.

**Best for:** Trial rollouts, targeted use cases, manual invocation.

### B) cascadeflow as a proxy for OpenClaw LLM calls
**Concept:** Configure OpenClaw’s LLM client to route all model calls through cascadeflow (as a service or local library). cascadeflow handles provider selection and cost logic globally.

**Pros**
- Maximum coverage: all LLM usage benefits from optimization.
- Centralized telemetry and savings reporting.

**Cons**
- Requires deeper integration in OpenClaw’s core LLM layer.
- Higher operational complexity (service availability, latency).

**Best for:** Organization-wide cost control, consistent performance.

### C) Hybrid: Skill + Proxy
**Concept:** Default to proxy routing for most calls, but also ship a skill for manual overrides and A/B testing.

**Pros**
- Flexible rollout; allows fast experimentation.
- Provides fallback for workflows that need explicit control.

**Cons**
- More moving parts and documentation burden.

**Recommended:** Start with **B** for global savings, add **A** for manual control and experimentation.

## What the Skill Should Provide
If implementing the skill (A or C), recommended capabilities:

1. **Manual cascade triggering**
   - Let users explicitly send a prompt through cascadeflow.

2. **Cost optimization toggle**
   - Enable/disable cascade routing per request or per skill.

3. **Telemetry + dashboard hooks**
   - Emit metrics (model chosen, cost estimate, latency) to OpenClaw’s telemetry system.

4. **Policy helpers**
   - Accept quality thresholds or “safety bars” that cascadeflow uses when selecting models.

## Configuration Schema Proposal
**Goal:** Let OpenClaw users specify cascadeflow policies globally and per use case.

```yaml
openclaw:
  llm:
    provider: cascadeflow
    cascadeflow:
      endpoint: "http://localhost:8080"
      api_key: "${CASCADEFLOW_API_KEY}"
      default_policy: "balanced"
      policies:
        high_accuracy:
          quality_threshold: 0.9
          max_cost_per_1k_tokens_usd: 0.15
          fallback_models: ["gpt-4.1", "claude-3.5"]
        low_cost:
          quality_threshold: 0.7
          max_cost_per_1k_tokens_usd: 0.02
          fallback_models: ["gpt-4o-mini", "claude-3-haiku"]

skills:
  summarize:
    cascadeflow_policy: "low_cost"
  code_review:
    cascadeflow_policy: "high_accuracy"
```

**Notes:**
- The schema should align with OpenClaw’s existing config conventions once known.
- Policies should be reusable and override-able per skill or workflow.

## Usage Examples

### 1) Global proxy
- All OpenClaw LLM calls are routed through cascadeflow.
- Default policy is `balanced`, with opt-in overrides per skill.

### 2) Manual skill invocation
- A user calls the “cascadeflow” skill explicitly.
- The skill returns the model decision and cost estimate along with the response.

### 3) A/B testing
- Use a feature flag to route a percentage of calls through cascadeflow.
- Compare cost and quality metrics vs. baseline.

## Implementation Roadmap

### Phase 0 — Discovery (1–2 days)
- Read OpenClaw skill and LLM client docs/source.
- Identify config entry points and telemetry hooks.
- Confirm how provider selection is currently done.

### Phase 1 — Minimal proxy (3–5 days)
- Implement a cascadeflow provider adapter in OpenClaw’s LLM layer.
- Route all calls through cascadeflow with a default policy.
- Emit basic metrics (model chosen, cost estimate, latency).

### Phase 2 — Skill + policy controls (3–5 days)
- Build optional OpenClaw skill for manual control.
- Add policy overrides per skill/workflow.
- Provide structured usage logs for dashboards.

### Phase 3 — Production hardening (1–2 weeks)
- Add retries, fallbacks, and circuit breakers.
- Implement SLA monitoring and alerting.
- Provide migration guides and onboarding templates.

## Value Proposition for OpenClaw Users

1. **Estimated savings**
   - If cascadeflow can route 30–70% of calls to cheaper models while maintaining quality, organizations could realize material cost savings.
   - Exact savings depend on traffic mix and target quality thresholds.

2. **Ease of setup**
   - Proxy mode requires only a config change and endpoint credentials.
   - Optional skill provides manual control without altering existing workflows.

## Open Questions / Validation Needed
- Exact OpenClaw skill spec and entrypoint contract.
- Configuration format and precedence rules.
- Telemetry/cost accounting APIs for usage reporting.
- Any OpenClaw security constraints for external routing.
