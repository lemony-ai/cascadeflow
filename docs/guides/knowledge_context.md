# Versioned knowledge across model switches

Cascadeflow can attach one immutable knowledge snapshot to a request and pass the
same snapshot to every model selected during direct, draft, verifier, tool, and
streaming execution. Knowledge selection is request-scoped: the agent never keeps
an implicit "active" knowledge set that a concurrent or later request could inherit.

## Python

```python
from cascadeflow import CascadeAgent, KnowledgeSnapshot

knowledge = KnowledgeSnapshot(
    key="support-manual",
    version="2026-08-06",
    content=retrieved_text,
    cache_ttl="1h",  # "5m" is the default
)

result = await agent.run("How do I reset the device?", knowledge=knowledge)
print(result.metadata["knowledge"])
```

Pass a different snapshot on the next request to switch knowledge. Reusing the
same `key` and explicit `version` with different content is rejected while that
version is resident locally. Provider cache keys also include the content digest,
so old provider-side content cannot be selected after an LRU eviction or restart.

## TypeScript

```ts
const result = await agent.run('How do I reset the device?', {
  knowledge: {
    key: 'support-manual',
    version: '2026-08-06',
    content: retrievedText,
    cacheTtl: '1h',
  },
});
```

The same option works with `runStream`.

## Cost model

The local LRU stores only the stable rendered prefix and metadata. It does **not**
pretend to remove provider input tokens. Correctness always comes from sending the
selected snapshot to each model that handles the request.

To reduce billed work without risking stale state:

1. Retrieve only the passages needed for the current request before constructing
   the snapshot. Do not attach an entire knowledge base by default.
2. Keep knowledge and stable instructions first, and the current conversation turn
   last. Provider prompt caches require a stable prefix.
3. Reuse the same key/version/content while the knowledge is unchanged. Change the
   version when it changes.
4. Send conversation history only when the query depends on it. Prefer a concise,
   application-owned handoff over blindly replaying a full transcript.
5. Measure `cached_input_tokens` and `cache_write_input_tokens` in provider metadata
   before claiming savings. CascadeFlow uses those reported categories in OpenAI
   and Anthropic result-cost calculations instead of assuming every request hit.

OpenAI receives a content-bound `prompt_cache_key`. For GPT-5.6 and later model
families, cascadeflow also places an explicit breakpoint immediately after the
stable knowledge prefix and disables the implicit latest-message breakpoint. This
prevents each changing query from creating a separate billable cache write.
Anthropic receives top-level `cache_control` with a five-minute or one-hour TTL.
Other providers—including local Ollama and vLLM endpoints—receive the same
knowledge prefix without unsupported cache arguments. Provider caching is therefore
an optimization, never a dependency.

Provider caches have minimum prefix sizes and charge for the initial write on some
models. A short or one-off snapshot may not save money. Disable provider caching
with `enable_provider_cache=False` (Python) or `enableProviderCache: false`
(TypeScript) when a snapshot is not expected to be reused. The local immutable
snapshot and switch-safety behavior remain enabled.

Cache-aware dollar estimates use standard API rates. Provider service tiers,
regional processing, cloud resellers, negotiated pricing, and future price changes
can differ, so provider invoices remain authoritative.

See the official [OpenAI prompt caching guide](https://developers.openai.com/api/docs/guides/prompt-caching)
and [Anthropic prompt caching guide](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
for provider-specific cache thresholds, billing, and retention behavior.

## Concurrency and security

- The snapshot is immutable and selected per call, so concurrent tenants cannot
  race through shared "current knowledge" state.
- The provider cache key hashes the logical identity and content digest; it does not
  expose tenant or document names.
- Knowledge text is still sent to the selected provider models. Apply the same data
  classification and provider policy used for normal prompts.
- A `key` and `version` are identifiers, not authorization. Resolve tenant access
  before constructing a snapshot.
