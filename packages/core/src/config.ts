/**
 * Configuration types for CascadeFlow
 */

import type { Provider, RoutingStrategy } from './types';

/**
 * Configuration for a single model in the cascade
 *
 * @example
 * ```typescript
 * const model: ModelConfig = {
 *   name: 'gpt-4o-mini',
 *   provider: 'openai',
 *   cost: 0.00015
 * };
 * ```
 */
export interface ModelConfig {
  /** Model name (e.g., 'gpt-4o-mini', 'claude-3-5-sonnet') */
  name: string;

  /** Provider name */
  provider: Provider;

  /** Cost per 1K tokens in USD */
  cost: number;

  // Optional settings
  /** Keywords for routing (optional) */
  keywords?: string[];

  /** Domains this model is good at (e.g., 'code', 'math') */
  domains?: string[];

  /** Maximum tokens for generation */
  maxTokens?: number;

  /** System prompt override */
  systemPrompt?: string;

  /** Temperature for generation (0-2) */
  temperature?: number;

  /** API key (or use environment variable) */
  apiKey?: string;

  /** Custom base URL (for vLLM, Ollama, etc.) */
  baseUrl?: string;

  /** Provider-specific options */
  extra?: Record<string, any>;

  /** Expected latency in milliseconds */
  speedMs?: number;

  /** Base quality score (0-1) */
  qualityScore?: number;

  /** Whether model supports tool/function calling */
  supportsTools?: boolean;
}

/**
 * Quality configuration for validation
 */
export interface QualityConfig {
  /** Minimum confidence threshold to accept result (0-1) */
  threshold?: number;

  /** Confidence thresholds by complexity level */
  confidenceThresholds?: {
    simple?: number;
    moderate?: number;
    complex?: number;
    expert?: number;
  };

  /** Require minimum response length in tokens */
  requireMinimumTokens?: number;

  /** Enable validation */
  requireValidation?: boolean;

  /** Enable adaptive thresholds */
  enableAdaptive?: boolean;
}

/**
 * Cascade configuration
 */
export interface CascadeConfig {
  /** Quality configuration */
  quality?: QualityConfig;

  /** Maximum budget per query in USD */
  maxBudget?: number;

  /** Enable cost tracking */
  trackCosts?: boolean;

  /** Maximum retries per model */
  maxRetries?: number;

  /** Timeout per model call in seconds */
  timeout?: number;

  /** Routing strategy */
  routingStrategy?: RoutingStrategy;

  /** Use speculative cascades */
  useSpeculative?: boolean;

  /** Verbose logging */
  verbose?: boolean;

  /** Track metrics */
  trackMetrics?: boolean;
}

/**
 * Agent configuration combining models and cascade settings
 */
export interface AgentConfig {
  /** Array of model configurations (ordered by cost: cheap → expensive) */
  models: ModelConfig[];

  /** Optional cascade configuration */
  cascade?: CascadeConfig;

  /** Optional quality configuration (shorthand for cascade.quality) */
  quality?: QualityConfig;
}

/**
 * Validate ModelConfig
 */
export function validateModelConfig(config: ModelConfig): void {
  if (!config.name) {
    throw new Error('Model name is required');
  }
  if (!config.provider) {
    throw new Error('Provider is required');
  }
  if (config.cost < 0) {
    throw new Error('Cost must be non-negative');
  }
  if (config.temperature !== undefined && (config.temperature < 0 || config.temperature > 2)) {
    throw new Error('Temperature must be between 0 and 2');
  }
  if (config.maxTokens !== undefined && config.maxTokens <= 0) {
    throw new Error('maxTokens must be positive');
  }
}

/**
 * Default quality configuration
 */
export const DEFAULT_QUALITY_CONFIG: Required<QualityConfig> = {
  threshold: 0.7,
  confidenceThresholds: {
    simple: 0.6,
    moderate: 0.7,
    complex: 0.8,
    expert: 0.85,
  },
  requireMinimumTokens: 10,
  requireValidation: true,
  enableAdaptive: true,
};

/**
 * Default cascade configuration
 */
export const DEFAULT_CASCADE_CONFIG: Required<Omit<CascadeConfig, 'quality'>> = {
  maxBudget: 1.0,
  trackCosts: true,
  maxRetries: 2,
  timeout: 30,
  routingStrategy: 'adaptive',
  useSpeculative: true,
  verbose: false,
  trackMetrics: true,
};
