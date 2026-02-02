import type { ModelConfig } from '../config';

export type VercelAIProviderId =
  | 'openai'
  | 'anthropic'
  | 'google'
  | 'local'
  | 'litellm'
  | 'openrouter'
  | 'together'
  | 'groq'
  | 'mistral'
  | 'cohere'
  | 'fireworks'
  | 'perplexity'
  | 'deepseek'
  | 'xai'
  | 'azure'
  | 'bedrock'
  | 'vertex';

export type ProviderRole = 'drafter' | 'verifier';

export interface ProviderCost {
  input: number;
  output: number;
}

export interface ProviderModelSpec {
  id: string;
  label: string;
  cost: ProviderCost;
  contextWindow?: number;
  supportsTools?: boolean;
  speedMs?: number;
}

export interface ProviderEndpoint {
  name: string;
  baseUrl: string;
  description?: string;
}

export interface ProviderRateLimitPolicy {
  requestsPerMinute?: number;
  tokensPerMinute?: number;
  concurrency?: number;
}

export interface ProviderCapabilities {
  streaming: boolean;
  tools: boolean;
}

export interface ProviderAdapterConfig {
  id: VercelAIProviderId;
  label: string;
  envKeys: string[];
  defaultBaseUrl?: string;
  endpoints?: ProviderEndpoint[];
  rateLimit: ProviderRateLimitPolicy;
  capabilities: ProviderCapabilities;
  models: ProviderModelSpec[];
}

export interface ProviderAdapter extends ProviderAdapterConfig {
  getModel(modelId: string): ProviderModelSpec;
  toModelConfig(modelId: string, overrides?: Partial<ModelConfig>): ModelConfig;
}

export interface CascadeStageConfig {
  providerId: VercelAIProviderId;
  model: string;
  role?: ProviderRole;
  overrides?: Partial<ModelConfig>;
}

export interface CascadePlan {
  models: ModelConfig[];
  roles: ProviderRole[];
  fallbackOrder: string[];
  estimatedCostPer1k: number;
}
