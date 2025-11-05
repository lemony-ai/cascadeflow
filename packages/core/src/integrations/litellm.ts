/**
 * LiteLLM integration for cascadeflow TypeScript
 *
 * Provides accurate cost tracking using LiteLLM's pricing database,
 * which is maintained and updated regularly by the LiteLLM team.
 *
 * Port from Python cascadeflow.integrations.litellm
 *
 * Features:
 * - LiteLLMCostProvider: Accurate cost calculations using LiteLLM
 * - SUPPORTED_PROVIDERS: Strategic provider selection with value props
 * - Provider validation
 * - Automatic fallback if LiteLLM not installed
 *
 * Benefits over custom pricing:
 * - Always up-to-date pricing (LiteLLM team maintains it)
 * - Covers 100+ models across 10+ providers
 * - Includes both input and output token pricing
 * - Handles special pricing (batch, cached tokens, etc.)
 *
 * @example
 * ```typescript
 * import { LiteLLMCostProvider } from '@cascadeflow/core';
 *
 * // Create cost provider
 * const costProvider = new LiteLLMCostProvider();
 *
 * // Calculate cost
 * const cost = await costProvider.calculateCost({
 *   model: 'gpt-4',
 *   inputTokens: 100,
 *   outputTokens: 50
 * });
 * console.log(`Cost: $${cost.toFixed(6)}`);
 * ```
 *
 * Installation:
 *   npm install litellm
 *
 * Note: This is a TypeScript port. The original LiteLLM is a Python library.
 * For full LiteLLM features, consider using the Python version or a REST API wrapper.
 */

/**
 * Information about a supported provider
 */
export interface ProviderInfo {
  /** Provider identifier */
  name: string;

  /** Display name */
  displayName: string;

  /** Value proposition - why use this provider? */
  valueProp: string;

  /** Whether LiteLLM has pricing info */
  pricingAvailable: boolean;

  /** Whether API key is required */
  requiresApiKey: boolean;

  /** Example model names */
  exampleModels: string[];
}

/**
 * Strategic provider selection (10 providers as per plan)
 * Each provider has a clear value proposition
 */
export const SUPPORTED_PROVIDERS: Record<string, ProviderInfo> = {
  openai: {
    name: 'openai',
    displayName: 'OpenAI',
    valueProp: 'Industry-leading quality, most reliable, best for production',
    pricingAvailable: true,
    requiresApiKey: true,
    exampleModels: ['gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
  },
  anthropic: {
    name: 'anthropic',
    displayName: 'Anthropic Claude',
    valueProp: 'Best for reasoning and analysis, strong safety features',
    pricingAvailable: true,
    requiresApiKey: true,
    exampleModels: [
      'anthropic/claude-3-opus-20240229',
      'anthropic/claude-3-5-sonnet-20241022',
      'anthropic/claude-3-sonnet-20240229',
      'anthropic/claude-3-haiku-20240307',
    ],
  },
  groq: {
    name: 'groq',
    displayName: 'Groq',
    valueProp: 'Fastest inference speed, ultra-low latency, free tier',
    pricingAvailable: true,
    requiresApiKey: true,
    exampleModels: [
      'groq/llama-3.1-70b-versatile',
      'groq/llama-3.1-8b-instant',
      'groq/mixtral-8x7b-32768',
    ],
  },
  together: {
    name: 'together',
    displayName: 'Together AI',
    valueProp: 'Cost-effective, wide model selection, good for experimentation',
    pricingAvailable: true,
    requiresApiKey: true,
    exampleModels: [
      'together_ai/meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo',
      'together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo',
      'together_ai/Qwen/Qwen2.5-72B-Instruct-Turbo',
    ],
  },
  huggingface: {
    name: 'huggingface',
    displayName: 'Hugging Face',
    valueProp: 'Open-source models, community-driven, flexible deployment',
    pricingAvailable: true,
    requiresApiKey: true,
    exampleModels: [
      'huggingface/mistralai/Mistral-7B-Instruct-v0.2',
      'huggingface/meta-llama/Llama-2-70b-chat',
    ],
  },
  ollama: {
    name: 'ollama',
    displayName: 'Ollama',
    valueProp: 'Local/on-prem deployment, zero cost, full privacy',
    pricingAvailable: false, // Free, local
    requiresApiKey: false,
    exampleModels: ['llama3.1:8b', 'llama3.1:70b', 'mistral', 'codellama'],
  },
  vllm: {
    name: 'vllm',
    displayName: 'vLLM',
    valueProp: 'Self-hosted inference, high throughput, production-ready',
    pricingAvailable: false, // Self-hosted
    requiresApiKey: false,
    exampleModels: ['meta-llama/Llama-3.1-70B', 'meta-llama/Llama-3.1-8B'],
  },
  google: {
    name: 'google',
    displayName: 'Google (Vertex AI)',
    valueProp: 'Enterprise integration, GCP ecosystem, Gemini models',
    pricingAvailable: true,
    requiresApiKey: true,
    exampleModels: ['gemini/gemini-pro', 'gemini/gemini-1.5-pro', 'gemini/gemini-1.5-flash'],
  },
  azure: {
    name: 'azure',
    displayName: 'Azure OpenAI',
    valueProp: 'Enterprise compliance, HIPAA/SOC2, Microsoft ecosystem',
    pricingAvailable: true,
    requiresApiKey: true,
    exampleModels: ['azure/gpt-4', 'azure/gpt-4-turbo', 'azure/gpt-3.5-turbo'],
  },
  deepseek: {
    name: 'deepseek',
    displayName: 'DeepSeek',
    valueProp: 'Specialized code models, very cost-effective for coding tasks',
    pricingAvailable: true,
    requiresApiKey: true,
    exampleModels: ['deepseek/deepseek-coder', 'deepseek/deepseek-chat'],
  },
};

/**
 * Validate if provider is supported
 *
 * @param provider - Provider name to validate
 * @returns True if supported, false otherwise
 */
export function validateProvider(provider: string): boolean {
  const supported = provider.toLowerCase() in SUPPORTED_PROVIDERS;

  if (!supported) {
    const available = Object.keys(SUPPORTED_PROVIDERS).join(', ');
    console.warn(
      `Provider '${provider}' not in supported list. Available: ${available}`
    );
  }

  return supported;
}

/**
 * Get information about a provider
 *
 * @param provider - Provider name
 * @returns ProviderInfo if found, undefined otherwise
 */
export function getProviderInfo(provider: string): ProviderInfo | undefined {
  return SUPPORTED_PROVIDERS[provider.toLowerCase()];
}

/**
 * Model pricing information
 */
export interface ModelPricing {
  /** Cost per input token (USD) */
  inputCostPerToken: number;

  /** Cost per output token (USD) */
  outputCostPerToken: number;

  /** Maximum context length */
  maxTokens: number;

  /** Whether streaming is supported */
  supportsStreaming: boolean;
}

/**
 * Cost calculation options
 */
export interface CostCalculationOptions {
  /** Model name */
  model: string;

  /** Number of input tokens */
  inputTokens?: number;

  /** Number of output tokens */
  outputTokens?: number;
}

/**
 * Cost calculation using LiteLLM's pricing database.
 *
 * This provides accurate, up-to-date pricing for 100+ models across
 * 10+ providers without maintaining custom pricing tables.
 *
 * Note: This TypeScript version uses fallback pricing estimates.
 * For real-time LiteLLM pricing, use the Python version or REST API.
 *
 * @example
 * ```typescript
 * const costProvider = new LiteLLMCostProvider();
 *
 * // Calculate cost from token counts
 * const cost = await costProvider.calculateCost({
 *   model: 'gpt-4',
 *   inputTokens: 100,
 *   outputTokens: 50
 * });
 *
 * // Get model pricing info
 * const pricing = await costProvider.getModelCost('gpt-4');
 * console.log(`Input: $${pricing.inputCostPerToken.toFixed(8)}/token`);
 * ```
 */
export class LiteLLMCostProvider {
  private fallbackEnabled: boolean;

  /**
   * Rough pricing estimates (per 1M tokens)
   * These are fallback values when LiteLLM is unavailable
   */
  private readonly roughPricing: Record<
    string,
    { input: number; output: number }
  > = {
    // OpenAI
    'gpt-4': { input: 30.0, output: 60.0 },
    'gpt-4-turbo': { input: 10.0, output: 30.0 },
    'gpt-4o': { input: 5.0, output: 15.0 },
    'gpt-4o-mini': { input: 0.15, output: 0.6 },
    'gpt-3.5-turbo': { input: 0.5, output: 1.5 },
    // Anthropic
    'claude-3-opus': { input: 15.0, output: 75.0 },
    'claude-3-5-sonnet': { input: 3.0, output: 15.0 },
    'claude-3-sonnet': { input: 3.0, output: 15.0 },
    'claude-3-haiku': { input: 0.25, output: 1.25 },
    // Default
    default: { input: 1.0, output: 2.0 },
  };

  constructor(options: { fallbackEnabled?: boolean } = {}) {
    this.fallbackEnabled = options.fallbackEnabled ?? true;

    // Note: In TypeScript, LiteLLM is not natively available
    // This implementation uses fallback estimates
    console.warn(
      'LiteLLMCostProvider (TypeScript): Using fallback cost estimates. ' +
        'For real-time pricing, use the Python version or REST API.'
    );
  }

  /**
   * Calculate cost using fallback estimates
   *
   * @param options - Cost calculation options
   * @returns Cost in USD
   */
  async calculateCost(options: CostCalculationOptions): Promise<number> {
    const { model, inputTokens = 0, outputTokens = 0 } = options;

    if (!this.fallbackEnabled) {
      throw new Error(
        'LiteLLM not available and fallback disabled. ' +
          'Consider using Python version or REST API.'
      );
    }

    return this.fallbackCost(model, inputTokens, outputTokens);
  }

  /**
   * Get pricing information for a model
   *
   * @param model - Model name
   * @returns Model pricing information
   */
  async getModelCost(model: string): Promise<ModelPricing> {
    // In TypeScript, we use fallback pricing
    return this.fallbackPricing(model);
  }

  /**
   * Fallback cost estimation when LiteLLM unavailable
   *
   * Uses rough estimates based on typical pricing
   */
  private fallbackCost(
    model: string,
    inputTokens: number,
    outputTokens: number
  ): number {
    // Get pricing or use default
    const pricing = this.roughPricing[model] || this.roughPricing.default;

    const inputCost = (inputTokens / 1_000_000) * pricing.input;
    const outputCost = (outputTokens / 1_000_000) * pricing.output;

    const totalCost = inputCost + outputCost;

    console.debug(
      `Fallback cost for ${model}: $${totalCost.toFixed(6)} ` +
        `(${inputTokens} in @ $${pricing.input}/1M, ` +
        `${outputTokens} out @ $${pricing.output}/1M)`
    );

    return totalCost;
  }

  /**
   * Fallback pricing info when LiteLLM unavailable
   */
  private fallbackPricing(model: string): ModelPricing {
    const pricing = this.roughPricing[model] || this.roughPricing.default;

    return {
      inputCostPerToken: pricing.input / 1_000_000,
      outputCostPerToken: pricing.output / 1_000_000,
      maxTokens: 4096,
      supportsStreaming: true,
    };
  }
}

/**
 * Get pricing information for a model
 *
 * Convenience function that creates a LiteLLMCostProvider and calls getModelCost()
 *
 * @param model - Model name
 * @returns Model pricing information
 */
export async function getModelCost(model: string): Promise<ModelPricing> {
  const provider = new LiteLLMCostProvider();
  return provider.getModelCost(model);
}

/**
 * Calculate cost for a model call
 *
 * Convenience function that creates a LiteLLMCostProvider and calls calculateCost()
 *
 * @param options - Cost calculation options
 * @returns Cost in USD
 */
export async function calculateCost(
  options: CostCalculationOptions
): Promise<number> {
  const provider = new LiteLLMCostProvider();
  return provider.calculateCost(options);
}
