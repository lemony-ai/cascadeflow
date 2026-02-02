import type { ProviderAdapter, VercelAIProviderId } from './types';
import { anthropicAdapter } from './providers/anthropic';
import { azureAdapter } from './providers/azure';
import { bedrockAdapter } from './providers/bedrock';
import { cohereAdapter } from './providers/cohere';
import { deepseekAdapter } from './providers/deepseek';
import { fireworksAdapter } from './providers/fireworks';
import { googleAdapter } from './providers/google';
import { groqAdapter } from './providers/groq';
import { liteLLMAdapter } from './providers/litellm';
import { localAdapter } from './providers/local';
import { mistralAdapter } from './providers/mistral';
import { openAIAdapter } from './providers/openai';
import { openRouterAdapter } from './providers/openrouter';
import { perplexityAdapter } from './providers/perplexity';
import { togetherAdapter } from './providers/together';
import { vertexAdapter } from './providers/vertex';
import { xaiAdapter } from './providers/xai';

export class VercelAIProviderRegistry {
  private providers = new Map<VercelAIProviderId, ProviderAdapter>();

  register(provider: ProviderAdapter): void {
    this.providers.set(provider.id, provider);
  }

  get(providerId: VercelAIProviderId): ProviderAdapter {
    const provider = this.providers.get(providerId);
    if (!provider) {
      throw new Error(`Provider '${providerId}' is not registered.`);
    }
    return provider;
  }

  list(): VercelAIProviderId[] {
    return Array.from(this.providers.keys());
  }

  values(): ProviderAdapter[] {
    return Array.from(this.providers.values());
  }
}

export const vercelAIProviderRegistry = new VercelAIProviderRegistry();

[
  openAIAdapter,
  anthropicAdapter,
  googleAdapter,
  localAdapter,
  liteLLMAdapter,
  openRouterAdapter,
  togetherAdapter,
  groqAdapter,
  mistralAdapter,
  cohereAdapter,
  fireworksAdapter,
  perplexityAdapter,
  deepseekAdapter,
  xaiAdapter,
  azureAdapter,
  bedrockAdapter,
  vertexAdapter,
].forEach((adapter) => vercelAIProviderRegistry.register(adapter));
