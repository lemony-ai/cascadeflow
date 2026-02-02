# Vercel AI SDK all-provider validation report

## Scope
- Reviewed the provider adapter definitions in `packages/core/src/vercel-ai/providers/`.
- Validated type safety, error handling, and rate-limit policy representation.
- Added E2E tests with real API calls for OpenAI, Groq, and Anthropic using SDK clients.
- Added SDK-like generate/stream tests for mixed-provider cascades and cost tracking.

## Provider adapter review (17 adapters)
- **Coverage:** OpenAI, Anthropic, Google, Local, LiteLLM, OpenRouter, Together, Groq, Mistral, Cohere, Fireworks, Perplexity, DeepSeek, xAI, Azure, Bedrock, Vertex.
- **Type safety:** Adapters rely on `ProviderAdapterConfig` and `createProviderAdapter`, which enforce model lookup and error messaging for unknown model IDs.
- **Error handling:** `createProviderAdapter.getModel` and `toModelConfig` raise explicit errors when an unknown model ID is requested.
- **Rate limiting:** Each adapter defines a `rateLimit` policy that flows through `ProviderRateLimiter` for request, token, and concurrency checks.

## Test additions
- `e2e.test.ts` validates real API calls for OpenAI, Groq, and Anthropic when API keys are present.
- Tests cover:
  - Draft/verifier cascade behavior across providers.
  - Error handling and fallback to another provider.
  - Streaming output.
  - Cost tracking derived from usage metadata.

## Issues / follow-ups
- **Vercel AI SDK packages** could not be installed in this environment due to registry authentication restrictions (403). E2E tests use provider SDKs to mimic Vercel AI SDK `generateText`/`streamText` patterns and validate response shape instead.
- **No adapter defects** were found during the config review. If any provider returns missing usage metadata, cost tracking tests will surface it.
