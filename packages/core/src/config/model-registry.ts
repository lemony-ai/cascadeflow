/**
 * Model Registry - Maps model names to configurations
 *
 * The ModelRegistry provides a centralized way to resolve model names
 * (like "gpt-4o" or "deepseek-coder") to full ModelConfig objects with
 * provider, cost, and capability information.
 *
 * @example
 * ```typescript
 * import { ModelRegistry } from '@cascadeflow/core';
 *
 * const registry = new ModelRegistry();
 *
 * // Get a built-in model
 * const gpt4o = registry.get('gpt-4o');
 * console.log(gpt4o.provider); // 'openai'
 * console.log(gpt4o.cost); // 0.0025
 *
 * // Register a custom model
 * registry.register('my-model', {
 *   name: 'my-fine-tuned-model',
 *   provider: 'openai',
 *   cost: 0.005,
 * });
 * ```
 */

import type { ModelConfig } from '../config';

/**
 * Extended model configuration with additional metadata.
 */
export interface ModelRegistryEntry extends ModelConfig {
  /** Aliases for this model (e.g., 'gpt4' -> 'gpt-4o') */
  aliases?: string[];
  /** Domains this model excels at */
  domains?: string[];
  /** Context window size in tokens */
  contextWindow?: number;
  /** Whether the model supports tool/function calling */
  supportsTools?: boolean;
  /** Whether the model supports streaming */
  supportsStreaming?: boolean;
  /** Whether the model supports vision/images */
  supportsVision?: boolean;
  /** Model release date (for versioning) */
  releaseDate?: string;
  /** Deprecation notice if model is being sunset */
  deprecated?: string;
}

/**
 * Built-in model definitions with current pricing (as of Nov 2024).
 *
 * Pricing is in USD per 1K tokens (input cost).
 * Note: Output costs are typically higher - this is input cost for simplicity.
 */
const BUILTIN_MODELS: Record<string, ModelRegistryEntry> = {
  // ========================================================================
  // OpenAI Models
  // ========================================================================
  'gpt-4o': {
    name: 'gpt-4o',
    provider: 'openai',
    cost: 0.0025, // $2.50/1M input
    aliases: ['gpt4o', 'gpt-4-omni'],
    contextWindow: 128000,
    supportsTools: true,
    supportsStreaming: true,
    supportsVision: true,
  },
  'gpt-4o-mini': {
    name: 'gpt-4o-mini',
    provider: 'openai',
    cost: 0.00015, // $0.15/1M input
    aliases: ['gpt4o-mini', 'gpt-4-mini'],
    contextWindow: 128000,
    supportsTools: true,
    supportsStreaming: true,
    supportsVision: true,
  },
  'gpt-4': {
    name: 'gpt-4',
    provider: 'openai',
    cost: 0.03, // $30/1M input
    aliases: ['gpt4'],
    contextWindow: 8192,
    supportsTools: true,
    supportsStreaming: true,
  },
  'gpt-4-turbo': {
    name: 'gpt-4-turbo',
    provider: 'openai',
    cost: 0.01, // $10/1M input
    aliases: ['gpt4-turbo'],
    contextWindow: 128000,
    supportsTools: true,
    supportsStreaming: true,
    supportsVision: true,
  },
  'gpt-3.5-turbo': {
    name: 'gpt-3.5-turbo',
    provider: 'openai',
    cost: 0.0005, // $0.50/1M input
    aliases: ['gpt35', 'gpt-35-turbo'],
    contextWindow: 16385,
    supportsTools: true,
    supportsStreaming: true,
  },
  'o1': {
    name: 'o1',
    provider: 'openai',
    cost: 0.015, // $15/1M input
    aliases: ['openai-o1'],
    contextWindow: 128000,
    supportsTools: false,
    supportsStreaming: false,
  },
  'o1-mini': {
    name: 'o1-mini',
    provider: 'openai',
    cost: 0.003, // $3/1M input
    aliases: ['openai-o1-mini'],
    contextWindow: 128000,
    supportsTools: false,
    supportsStreaming: false,
  },

  // ========================================================================
  // Anthropic Models
  // ========================================================================
  'claude-3-opus': {
    name: 'claude-3-opus-20240229',
    provider: 'anthropic',
    cost: 0.015, // $15/1M input
    aliases: ['claude-opus', 'claude-3-opus-20240229'],
    contextWindow: 200000,
    supportsTools: true,
    supportsStreaming: true,
    supportsVision: true,
  },
  'claude-3-sonnet': {
    name: 'claude-3-sonnet-20240229',
    provider: 'anthropic',
    cost: 0.003, // $3/1M input
    aliases: ['claude-sonnet', 'claude-3-sonnet-20240229'],
    contextWindow: 200000,
    supportsTools: true,
    supportsStreaming: true,
    supportsVision: true,
  },
  'claude-3.5-sonnet': {
    name: 'claude-3-5-sonnet-20241022',
    provider: 'anthropic',
    cost: 0.003, // $3/1M input
    aliases: ['claude-35-sonnet', 'claude-3-5-sonnet'],
    contextWindow: 200000,
    supportsTools: true,
    supportsStreaming: true,
    supportsVision: true,
  },
  'claude-3-haiku': {
    name: 'claude-3-haiku-20240307',
    provider: 'anthropic',
    cost: 0.00025, // $0.25/1M input
    aliases: ['claude-haiku', 'claude-3-haiku-20240307'],
    contextWindow: 200000,
    supportsTools: true,
    supportsStreaming: true,
    supportsVision: true,
  },

  // ========================================================================
  // Groq Models (Fast inference)
  // ========================================================================
  'groq/llama-3.1-70b': {
    name: 'llama-3.1-70b-versatile',
    provider: 'groq',
    cost: 0.00059, // $0.59/1M input
    aliases: ['llama-3.1-70b', 'llama-70b'],
    contextWindow: 131072,
    supportsTools: true,
    supportsStreaming: true,
  },
  'groq/llama-3.1-8b': {
    name: 'llama-3.1-8b-instant',
    provider: 'groq',
    cost: 0.00005, // $0.05/1M input
    aliases: ['llama-3.1-8b', 'llama-8b'],
    contextWindow: 131072,
    supportsTools: true,
    supportsStreaming: true,
  },
  'groq/mixtral-8x7b': {
    name: 'mixtral-8x7b-32768',
    provider: 'groq',
    cost: 0.00024, // $0.24/1M input
    aliases: ['mixtral-8x7b', 'mixtral'],
    contextWindow: 32768,
    supportsTools: true,
    supportsStreaming: true,
  },

  // ========================================================================
  // DeepSeek Models (Code-optimized)
  // ========================================================================
  'deepseek-coder': {
    name: 'deepseek-coder',
    provider: 'deepseek',
    cost: 0.00014, // $0.14/1M input
    aliases: ['deepseek-coder-v2'],
    domains: ['code'],
    contextWindow: 128000,
    supportsTools: true,
    supportsStreaming: true,
  },
  'deepseek-chat': {
    name: 'deepseek-chat',
    provider: 'deepseek',
    cost: 0.00014, // $0.14/1M input
    aliases: ['deepseek'],
    contextWindow: 128000,
    supportsTools: true,
    supportsStreaming: true,
  },

  // ========================================================================
  // Together AI Models
  // ========================================================================
  'together/llama-3.1-405b': {
    name: 'meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo',
    provider: 'together',
    cost: 0.005, // $5/1M input
    aliases: ['llama-405b', 'llama-3.1-405b'],
    contextWindow: 130000,
    supportsTools: true,
    supportsStreaming: true,
  },
  'together/llama-3.1-70b': {
    name: 'meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo',
    provider: 'together',
    cost: 0.00088, // $0.88/1M input
    aliases: ['together-llama-70b'],
    contextWindow: 130000,
    supportsTools: true,
    supportsStreaming: true,
  },
  'together/qwen-72b': {
    name: 'Qwen/Qwen2.5-72B-Instruct-Turbo',
    provider: 'together',
    cost: 0.0012, // $1.20/1M input
    aliases: ['qwen-72b', 'qwen2.5-72b'],
    contextWindow: 32768,
    supportsTools: true,
    supportsStreaming: true,
  },

  // ========================================================================
  // Ollama Models (Local)
  // ========================================================================
  'ollama/llama3': {
    name: 'llama3',
    provider: 'ollama',
    cost: 0, // Free (local)
    aliases: ['llama3-local', 'ollama-llama3'],
    contextWindow: 8192,
    supportsTools: false,
    supportsStreaming: true,
  },
  'ollama/mistral': {
    name: 'mistral',
    provider: 'ollama',
    cost: 0, // Free (local)
    aliases: ['mistral-local', 'ollama-mistral'],
    contextWindow: 8192,
    supportsTools: false,
    supportsStreaming: true,
  },
  'ollama/codellama': {
    name: 'codellama',
    provider: 'ollama',
    cost: 0, // Free (local)
    aliases: ['codellama-local'],
    domains: ['code'],
    contextWindow: 16384,
    supportsTools: false,
    supportsStreaming: true,
  },

  // ========================================================================
  // OpenRouter (Multi-provider)
  // ========================================================================
  'openrouter/auto': {
    name: 'openrouter/auto',
    provider: 'openrouter',
    cost: 0.001, // Variable
    aliases: ['openrouter-auto'],
    contextWindow: 128000,
    supportsTools: true,
    supportsStreaming: true,
  },
};

/**
 * Model Registry for resolving model names to configurations.
 *
 * Provides:
 * - Built-in models with current pricing
 * - Custom model registration
 * - Alias resolution
 * - YAML/JSON config loading
 */
export class ModelRegistry {
  private models: Map<string, ModelRegistryEntry>;
  private aliases: Map<string, string>;

  constructor() {
    this.models = new Map();
    this.aliases = new Map();

    // Load built-in models
    for (const [name, config] of Object.entries(BUILTIN_MODELS)) {
      this.registerInternal(name, config);
    }
  }

  /**
   * Register a model internally (with alias handling).
   */
  private registerInternal(name: string, config: ModelRegistryEntry): void {
    this.models.set(name.toLowerCase(), config);

    // Register aliases
    if (config.aliases) {
      for (const alias of config.aliases) {
        this.aliases.set(alias.toLowerCase(), name.toLowerCase());
      }
    }
  }

  /**
   * Register a custom model.
   *
   * @param name - Model identifier
   * @param config - Model configuration
   */
  register(name: string, config: ModelRegistryEntry): void {
    this.registerInternal(name, config);
  }

  /**
   * Get a model by name or alias.
   *
   * @param name - Model name or alias
   * @returns ModelRegistryEntry
   * @throws Error if model not found
   */
  get(name: string): ModelRegistryEntry {
    const normalizedName = name.toLowerCase();

    // Check direct match
    if (this.models.has(normalizedName)) {
      return this.models.get(normalizedName)!;
    }

    // Check aliases
    if (this.aliases.has(normalizedName)) {
      const canonicalName = this.aliases.get(normalizedName)!;
      return this.models.get(canonicalName)!;
    }

    throw new Error(
      `Unknown model: "${name}". ` +
        `Use registry.register("${name}", {...}) to add it, ` +
        `or use one of: ${this.listModels().slice(0, 5).join(', ')}...`
    );
  }

  /**
   * Check if a model exists in the registry.
   */
  has(name: string): boolean {
    const normalizedName = name.toLowerCase();
    return this.models.has(normalizedName) || this.aliases.has(normalizedName);
  }

  /**
   * Get a model if it exists, otherwise return undefined.
   */
  getOrUndefined(name: string): ModelRegistryEntry | undefined {
    try {
      return this.get(name);
    } catch {
      return undefined;
    }
  }

  /**
   * List all registered model names.
   */
  listModels(): string[] {
    return Array.from(this.models.keys());
  }

  /**
   * List models by provider.
   */
  listByProvider(provider: string): string[] {
    return Array.from(this.models.entries())
      .filter(([_, config]) => config.provider === provider)
      .map(([name]) => name);
  }

  /**
   * List models that support a specific domain.
   */
  listByDomain(domain: string): string[] {
    return Array.from(this.models.entries())
      .filter(([_, config]) => config.domains?.includes(domain))
      .map(([name]) => name);
  }

  /**
   * List models that support tools/function calling.
   */
  listWithToolSupport(): string[] {
    return Array.from(this.models.entries())
      .filter(([_, config]) => config.supportsTools)
      .map(([name]) => name);
  }

  /**
   * Get the cheapest model that meets certain criteria.
   */
  getCheapest(options?: {
    maxCost?: number;
    supportsTools?: boolean;
    supportsStreaming?: boolean;
    provider?: string;
  }): ModelRegistryEntry | undefined {
    let candidates = Array.from(this.models.values());

    if (options?.maxCost !== undefined) {
      candidates = candidates.filter((m) => m.cost <= options.maxCost!);
    }
    if (options?.supportsTools) {
      candidates = candidates.filter((m) => m.supportsTools);
    }
    if (options?.supportsStreaming) {
      candidates = candidates.filter((m) => m.supportsStreaming);
    }
    if (options?.provider) {
      candidates = candidates.filter((m) => m.provider === options.provider);
    }

    if (candidates.length === 0) return undefined;

    return candidates.sort((a, b) => a.cost - b.cost)[0];
  }

  /**
   * Convert a model name to a full ModelConfig.
   * If already a ModelConfig, returns as-is.
   */
  resolve(nameOrConfig: string | ModelRegistryEntry): ModelRegistryEntry {
    if (typeof nameOrConfig === 'string') {
      return this.get(nameOrConfig);
    }
    return nameOrConfig;
  }

  /**
   * Create a registry from a plain object.
   */
  static fromObject(models: Record<string, ModelRegistryEntry>): ModelRegistry {
    const registry = new ModelRegistry();
    for (const [name, config] of Object.entries(models)) {
      registry.register(name, config);
    }
    return registry;
  }

  /**
   * Export registry to a plain object.
   */
  toObject(): Record<string, ModelRegistryEntry> {
    const obj: Record<string, ModelRegistryEntry> = {};
    for (const [name, config] of this.models) {
      obj[name] = config;
    }
    return obj;
  }
}

/**
 * Global default model registry instance.
 */
export const defaultModelRegistry = new ModelRegistry();

/**
 * Convenience function to get a model from the default registry.
 */
export function getModel(name: string): ModelRegistryEntry {
  return defaultModelRegistry.get(name);
}

/**
 * Convenience function to check if a model exists in the default registry.
 */
export function hasModel(name: string): boolean {
  return defaultModelRegistry.has(name);
}
