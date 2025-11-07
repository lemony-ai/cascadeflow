/**
 * Configuration types for cascadeflow
 */

import type { Provider, RoutingStrategy } from './types';
import type { QualityConfig as QualityValidatorConfig } from './quality';

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

  /** Per-model quality threshold for cascade acceptance (0-1, overrides global threshold) */
  qualityThreshold?: number;
}

/**
 * Quality configuration for validation
 *
 * Controls how strictly the cascade validates draft responses before accepting them.
 * Higher thresholds mean more responses will be escalated to better models.
 *
 * @example Basic quality config
 * ```typescript
 * const config: QualityConfig = {
 *   threshold: 0.8,  // Higher = stricter (more escalations)
 *   requireMinimumTokens: 10  // Reject very short responses
 * };
 * ```
 *
 * @example Adaptive thresholds by complexity
 * ```typescript
 * const config: QualityConfig = {
 *   confidenceThresholds: {
 *     trivial: 0.5,   // Very low bar for trivial queries
 *     simple: 0.6,    // Lower bar for simple queries
 *     moderate: 0.7,  // Medium bar
 *     hard: 0.8,      // High bar for hard queries
 *     expert: 0.9     // Very high bar for expert-level
 *   }
 * };
 * ```
 */
type QualityValidatorParams = Partial<QualityValidatorConfig>;

export interface QualityConfig extends QualityValidatorParams {
  /** Minimum confidence threshold to accept result (0-1, default: 0.7) */
  threshold?: number;

  /** Confidence thresholds by complexity level (overrides global threshold) */
  confidenceThresholds?: {
    trivial?: number;
    simple?: number;
    moderate?: number;
    hard?: number;
    expert?: number;
  };

  /** Require minimum response length in tokens (default: 10) */
  requireMinimumTokens?: number;

  /** Enable quality validation (default: true) */
  requireValidation?: boolean;

  /** Enable adaptive thresholds based on query complexity (default: false) */
  enableAdaptive?: boolean;
}

/**
 * Cascade configuration
 *
 * Advanced settings for controlling cascade behavior, cost limits, retries, and logging.
 * Most users should use presets instead of manually configuring these settings.
 *
 * @example Basic cascade config
 * ```typescript
 * const config: CascadeConfig = {
 *   maxBudget: 0.10,  // Max $0.10 per query
 *   maxRetries: 3,    // Retry failed requests 3 times
 *   trackCosts: true  // Track detailed cost metrics
 * };
 * ```
 *
 * @example Production config with quality settings
 * ```typescript
 * const config: CascadeConfig = {
 *   quality: {
 *     threshold: 0.8,
 *     requireMinimumTokens: 20
 *   },
 *   maxBudget: 0.25,
 *   timeout: 60,
 *   trackMetrics: true,
 *   verbose: false
 * };
 * ```
 */
export interface CascadeConfig {
  /** Quality validation configuration */
  quality?: QualityConfig;

  /** Maximum budget per query in USD (default: no limit) */
  maxBudget?: number;

  /** Enable detailed cost tracking (default: true) */
  trackCosts?: boolean;

  /** Maximum retries per model on failure (default: 0) */
  maxRetries?: number;

  /** Timeout per model call in seconds (default: 60) */
  timeout?: number;

  /** Routing strategy: 'cost', 'quality', 'speed' (default: 'cost') */
  routingStrategy?: RoutingStrategy;

  /** Enable speculative cascade execution (default: false, experimental) */
  useSpeculative?: boolean;

  /** Enable verbose logging for debugging (default: false) */
  verbose?: boolean;

  /** Track detailed performance metrics (default: true) */
  trackMetrics?: boolean;
}

/**
 * Agent configuration combining models and cascade settings
 *
 * This is the main configuration interface for creating a CascadeAgent.
 * You can either configure manually or use presets (recommended).
 *
 * @example Using presets (recommended)
 * ```typescript
 * import { CascadeAgent, PRESET_BEST_OVERALL } from '@cascadeflow/core';
 *
 * const agent = new CascadeAgent(PRESET_BEST_OVERALL);
 * ```
 *
 * @example Manual configuration
 * ```typescript
 * import { CascadeAgent, ModelConfig, AgentConfig } from '@cascadeflow/core';
 *
 * const config: AgentConfig = {
 *   models: [
 *     { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
 *     { name: 'gpt-4o', provider: 'openai', cost: 0.00625 }
 *   ]
 * };
 *
 * const agent = new CascadeAgent(config);
 * ```
 *
 * @example With quality settings
 * ```typescript
 * const config: AgentConfig = {
 *   models: [...],
 *   quality: {
 *     threshold: 0.8,
 *     requireMinimumTokens: 20
 *   }
 * };
 * ```
 *
 * @example With full cascade config
 * ```typescript
 * const config: AgentConfig = {
 *   models: [...],
 *   cascade: {
 *     maxBudget: 0.10,
 *     timeout: 30,
 *     trackMetrics: true,
 *     quality: { threshold: 0.75 }
 *   }
 * };
 * ```
 *
 * @see {ModelConfig} for model configuration options
 * @see {QualityConfig} for quality validation settings
 * @see {CascadeConfig} for advanced cascade settings
 */
export interface AgentConfig {
  /** Array of model configurations (will be automatically sorted by cost) */
  models: ModelConfig[];

  /** Optional cascade configuration (advanced settings) */
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
  if (config.qualityThreshold !== undefined && (config.qualityThreshold < 0 || config.qualityThreshold > 1)) {
    throw new Error('qualityThreshold must be between 0 and 1');
  }
}

/**
 * Default quality configuration
 */
export const DEFAULT_QUALITY_CONFIG: QualityConfig = {
  threshold: 0.7,
  confidenceThresholds: {
    trivial: 0.5,
    simple: 0.6,
    moderate: 0.7,
    hard: 0.8,
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
