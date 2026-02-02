import type { ModelConfig } from '../../config';
import type {
  ProviderAdapter,
  ProviderAdapterConfig,
  ProviderCost,
  ProviderModelSpec,
} from '../types';

export function calculateBlendedCost(cost: ProviderCost): number {
  return (cost.input + cost.output) / 2;
}

function formatModelList(models: ProviderModelSpec[]): string {
  return models.map((model) => model.id).join(', ');
}

export function createProviderAdapter(config: ProviderAdapterConfig): ProviderAdapter {
  const modelLookup = new Map<string, ProviderModelSpec>(
    config.models.map((model) => [model.id, model])
  );

  return {
    ...config,
    getModel(modelId: string): ProviderModelSpec {
      const model = modelLookup.get(modelId);
      if (!model) {
        throw new Error(
          `Model '${modelId}' not found for provider '${config.id}'. Available models: ${formatModelList(
            config.models
          )}`
        );
      }
      return model;
    },
    toModelConfig(modelId: string, overrides?: Partial<ModelConfig>): ModelConfig {
      const model = modelLookup.get(modelId);
      if (!model) {
        throw new Error(
          `Model '${modelId}' not found for provider '${config.id}'. Available models: ${formatModelList(
            config.models
          )}`
        );
      }

      const baseCost = calculateBlendedCost(model.cost);

      return {
        name: model.id,
        provider: config.id,
        cost: overrides?.cost ?? baseCost,
        maxTokens: overrides?.maxTokens ?? model.contextWindow,
        supportsTools: overrides?.supportsTools ?? model.supportsTools,
        speedMs: overrides?.speedMs ?? model.speedMs,
        apiKey: overrides?.apiKey,
        baseUrl: overrides?.baseUrl ?? config.defaultBaseUrl,
        extra: {
          costBreakdown: model.cost,
          rateLimit: config.rateLimit,
          providerLabel: config.label,
          ...overrides?.extra,
        },
      };
    },
  };
}
