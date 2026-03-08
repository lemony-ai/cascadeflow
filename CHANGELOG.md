# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-07

### Added

- **Harness API** — `init()`, `run()`, `@agent()` for zero-change observability, scoped budget runs, and decorated agent policy. Three modes: `off`, `observe`, `enforce`.
- **SDK auto-instrumentation** — Patches OpenAI and Anthropic Python SDKs to intercept every LLM call for cost tracking, budget enforcement, compliance gating, and decision tracing.
- **Six-dimension optimization** — Cost, latency, quality, budget, compliance, and energy tracked across every model call.
- **KPI-weighted routing** — Inject business priorities (`quality`, `cost`, `latency`, `energy`) as weights into model selection decisions.
- **Compliance gating** — GDPR, HIPAA, PCI, and strict model allowlists; block non-compliant models before execution.
- **Energy tracking** — Deterministic compute-intensity coefficients for carbon-aware AI operations.
- **Decision traces** — Full per-step audit trail: action, reason, model, cost, budget state, enforcement status.
- **Budget enforcement** — Per-run and per-user budget caps with automatic stop actions when limits are exceeded.
- **Framework integrations** — LangChain (Python + TypeScript), OpenAI Agents SDK, CrewAI, Google ADK, n8n, Vercel AI SDK.
- **TypeScript SDK** — `@cascadeflow/core`, `@cascadeflow/langchain`, `@cascadeflow/vercel-ai`, `@cascadeflow/ml`, `@cascadeflow/n8n-nodes-cascadeflow` published on npm.
- **Proxy Gateway** — Drop-in OpenAI/Anthropic-compatible HTTP server with mock and agent modes, streaming, tool calling, and embeddings support.
- **OpenClaw Server** — Standalone OpenAI-compatible server for OpenClaw deployments with semantic routing.
- **Paygentic integration** — Usage reporting and billing proxy for Paygentic platform.
- **Tool risk classification** — `ToolRiskClassifier` for per-tool-call routing based on risk level.
- **Circuit breaker** — Per-provider circuit breaker with configurable thresholds and recovery.
- **Dynamic configuration** — Runtime config updates via file watcher with change events.
- **Rule engine** — `RuleEngine` for declarative routing and policy rules.
- **Agent loops** — Multi-turn tool execution with automatic tool call, result, re-prompt cycles.
- **Semantic quality validation** — Optional ML-based quality scoring via FastEmbed embeddings.
- **15-domain auto-detection** — Code, math, medical, legal, finance, data, and more with per-domain routing pipelines.
- **Complexity detection** — 500+ technical terms, mathematical notation detection, density-aware scoring for long documents.

### Changed

- **Lazy imports** — `import cascadeflow` no longer eagerly loads all providers, numpy, or heavyweight submodules. Import time reduced from ~1900ms to <200ms.
- **`__all__` reduced** — From 127 to ~20 essential public symbols. Non-essential exports remain accessible but are not star-exported.
- **`rich` moved to optional** — No longer a core dependency; falls back to stdlib logging when not installed. Install with `pip install cascadeflow[rich]`.
- **Integration import errors** — Failed optional integration imports now return proxy objects that raise `ImportError` with install hints on use, instead of silently returning `None`.
- **Proxy CORS default** — `cors_allow_origin` changed from `"*"` to `None` (opt-in) for secure-by-default deployments.

### Removed

- **Deprecated `CascadeAgent` parameters** — `config`, `tiers`, `workflows`, `enable_caching`, `cache_size`, `enable_callbacks` removed from constructor. Use `HarnessConfig` or dedicated APIs instead.
- **Submodule `__version__` strings** — Removed from `quality`, `streaming`, `telemetry`, `ml`, `tools`, `routing`, `interface` subpackages. Use `cascadeflow.__version__` instead.
- **Benchmark infrastructure** — `tests/benchmarks/`, `benchmark_results/`, and related docs removed (moved to separate benchmark repo).

### Fixed

- **Thread safety** — Added `threading.Lock` around SDK patch/unpatch state. `HarnessRunContext` counters guarded with lock for multi-threaded use.
- **Trace buffer** — `_trace` changed from `list` with manual slicing to `collections.deque(maxlen=1000)` for bounded memory.
- **Regex pre-compilation** — `ComplexityDetector` now pre-compiles all regex patterns in `__init__()` instead of per-`detect()` call.
- **Proxy body limit** — Added `max_body_bytes` (default 10MB) to `ProxyConfig`; returns 413 for oversized requests.
- **Proxy auth** — Added optional `auth_token` to `ProxyConfig`; returns 401 for unauthenticated requests when set.

### Security

- Proxy gateway CORS tightened to opt-in (`None` default).
- Request body size limit prevents memory exhaustion attacks.
- Bearer token authentication for proxy gateway endpoints.
- Updated `SECURITY.md` supported version to 1.0.x.

[1.0.0]: https://github.com/lemony-ai/cascadeflow/releases/tag/v1.0.0
