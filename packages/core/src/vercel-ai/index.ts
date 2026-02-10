export type {
  VercelAIProviderId,
  ProviderRole,
  ProviderCost,
  ProviderModelSpec,
  ProviderEndpoint,
  ProviderRateLimitPolicy,
  ProviderCapabilities,
  ProviderAdapter,
  ProviderAdapterConfig,
  CascadeStageConfig,
  CascadePlan,
} from './types';

export { vercelAIProviderRegistry, VercelAIProviderRegistry } from './provider-registry';
export { buildCascadePlan, buildFallbackCascade, createDraftVerifierCascade } from './cascade';
export { ProviderRateLimiter } from './rate-limiter';

export { openAIAdapter } from './providers/openai';
export { anthropicAdapter } from './providers/anthropic';
export { googleAdapter } from './providers/google';
export { localAdapter } from './providers/local';
export { liteLLMAdapter } from './providers/litellm';
export { openRouterAdapter } from './providers/openrouter';
export { togetherAdapter } from './providers/together';
export { groqAdapter } from './providers/groq';
export { mistralAdapter } from './providers/mistral';
export { cohereAdapter } from './providers/cohere';
export { fireworksAdapter } from './providers/fireworks';
export { perplexityAdapter } from './providers/perplexity';
export { deepseekAdapter } from './providers/deepseek';
export { xaiAdapter } from './providers/xai';
export { azureAdapter } from './providers/azure';
export { bedrockAdapter } from './providers/bedrock';
export { vertexAdapter } from './providers/vertex';

// Vercel AI SDK UI helpers (e.g. `useChat`)
export { createChatHandler, createCompletionHandler } from './ui';
export type { VercelAIChatHandlerOptions, VercelAIStreamProtocol } from './ui';
