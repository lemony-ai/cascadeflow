import { describe, expect, it } from 'vitest';
import {
  anthropicAdapter,
  azureAdapter,
  bedrockAdapter,
  cohereAdapter,
  deepseekAdapter,
  fireworksAdapter,
  googleAdapter,
  groqAdapter,
  liteLLMAdapter,
  localAdapter,
  mistralAdapter,
  openAIAdapter,
  openRouterAdapter,
  perplexityAdapter,
  togetherAdapter,
  vertexAdapter,
  xaiAdapter,
  vercelAIProviderRegistry,
} from '../index';

const adapters = [
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
];

describe('Vercel AI provider adapters', () => {
  it('registers all providers in the registry', () => {
    const registryProviders = vercelAIProviderRegistry.list();
    const adapterIds = adapters.map((adapter) => adapter.id);
    expect(new Set(registryProviders)).toEqual(new Set(adapterIds));
  });

  it('creates model configs for each provider', () => {
    adapters.forEach((adapter) => {
      const modelId = adapter.models[0]?.id;
      expect(modelId).toBeTruthy();
      const config = adapter.toModelConfig(modelId);
      expect(config.provider).toBe(adapter.id);
      expect(config.cost).toBeGreaterThanOrEqual(0);
    });
  });
});
