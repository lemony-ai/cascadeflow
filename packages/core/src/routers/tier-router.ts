/**
 * Tier-aware routing for user tier management
 *
 * This module provides tier-based model filtering and budget enforcement.
 * It's OPTIONAL - only activated when users provide 'tiers' parameter.
 *
 * Port from Python cascadeflow/routing/tier_routing.py
 *
 * @example
 * ```typescript
 * import { TierRouter, createTierRouter } from '@cascadeflow/core';
 *
 * const router = createTierRouter({
 *   tiers: {
 *     free: {
 *       name: 'Free',
 *       allowedModels: ['gpt-3.5-turbo', 'claude-haiku'],
 *       maxBudget: 0.01
 *     },
 *     pro: {
 *       name: 'Pro',
 *       allowedModels: ['*'], // All models
 *       maxBudget: 0.10
 *     }
 *   },
 *   models: allModels,
 *   verbose: true
 * });
 *
 * // Filter models for free tier
 * const freeModels = router.filterModels('free', allModels);
 * ```
 */

import type { ModelConfig } from '../types';

/**
 * Enhanced tier configuration for routing
 *
 * Extends basic TierConfig with model access controls
 */
export interface TierRouterConfig {
  /** Tier name */
  name: string;

  /** List of allowed model names (supports '*' wildcard for all models) */
  allowedModels?: string[];

  /** List of excluded model names */
  excludeModels?: string[];

  /** Maximum budget per query (USD) */
  maxBudget?: number;

  /** Minimum quality threshold (0-1) */
  qualityThreshold?: number;

  /** Maximum latency in milliseconds */
  maxLatencyMs?: number;

  /** Additional tier metadata */
  metadata?: Record<string, any>;
}

/**
 * Tier constraints for display/logging
 */
export interface TierConstraints {
  maxBudget?: number;
  qualityThreshold?: number;
  maxLatencyMs?: number;
  allowedModels?: string[];
  excludeModels?: string[];
}

/**
 * TierRouter statistics
 */
export interface TierRouterStats {
  /** Total number of filter operations */
  totalFilters: number;

  /** Filters by tier name */
  byTier: Record<string, number>;

  /** Total models filtered out */
  modelsFilteredOut: number;

  /** Average models filtered per query */
  avgFilteredPerQuery: number;
}

/**
 * Configuration for TierRouter
 */
export interface TierAwareRouterConfig {
  /** Dictionary of tier name → TierRouterConfig */
  tiers: Record<string, TierRouterConfig>;

  /** All available models in the agent */
  models: ModelConfig[];

  /** Enable verbose logging */
  verbose?: boolean;
}

/**
 * Options for filterModels
 */
export interface FilterModelsOptions {
  /** Name of the user tier (e.g., 'free', 'pro') */
  tierName: string;

  /** Models to filter (defaults to all models) */
  availableModels?: ModelConfig[];
}

/**
 * Tier-aware router for user tier management
 *
 * Routes model selection based on user tiers. This router is OPTIONAL and only
 * used when:
 * 1. User provides 'tiers' parameter to CascadeAgent
 * 2. User specifies 'user_tier' parameter in agent.run()
 *
 * Features:
 * - Model filtering based on tier's allowed_models
 * - Budget constraint awareness
 * - Quality threshold enforcement
 * - Fallback to cheapest model if all filtered out
 *
 * @example
 * ```typescript
 * const router = new TierRouter({
 *   tiers: {
 *     free: {
 *       name: 'Free',
 *       allowedModels: ['gpt-3.5-turbo'],
 *       maxBudget: 0.01
 *     },
 *     pro: {
 *       name: 'Pro',
 *       allowedModels: ['*'],
 *       maxBudget: 0.10
 *     }
 *   },
 *   models: allModels,
 *   verbose: true
 * });
 *
 * // Filter models for free tier
 * const freeModels = router.filterModels({ tierName: 'free' });
 * ```
 */
export class TierRouter {
  private tiers: Record<string, TierRouterConfig>;
  private allModels: ModelConfig[];
  private verbose: boolean;
  private stats: {
    totalFilters: number;
    byTier: Record<string, number>;
    modelsFilteredOut: number;
  };

  constructor(config: TierAwareRouterConfig) {
    this.tiers = config.tiers;
    this.allModels = config.models;
    this.verbose = config.verbose ?? false;

    // Initialize statistics
    this.stats = {
      totalFilters: 0,
      byTier: Object.fromEntries(
        Object.keys(config.tiers).map((tier) => [tier, 0])
      ),
      modelsFilteredOut: 0,
    };

    if (this.verbose) {
      console.log('TierRouter initialized:');
      console.log(`  Tiers: ${Object.keys(this.tiers).join(', ')}`);
      console.log(`  Total models: ${this.allModels.length}`);
      console.log(`  Model names: ${this.allModels.map((m) => m.name).join(', ')}`);
    }
  }

  /**
   * Filter models based on user tier constraints
   *
   * This is the core tier routing function. It:
   * 1. Checks if tier exists
   * 2. Filters models based on tier's allowed_models
   * 3. Excludes models in tier's exclude_models
   * 4. Returns filtered list (or cheapest model as fallback)
   *
   * @param options - Filter options
   * @returns Filtered list of models allowed for this tier
   *
   * @example
   * ```typescript
   * const freeModels = router.filterModels({ tierName: 'free' });
   * // Returns only cheap models allowed for free tier
   *
   * const proModels = router.filterModels({
   *   tierName: 'pro',
   *   availableModels: customModelList
   * });
   * ```
   */
  filterModels(options: FilterModelsOptions): ModelConfig[] {
    const { tierName, availableModels = this.allModels } = options;

    // Update stats
    this.stats.totalFilters++;

    // Check if tier exists
    if (!(tierName in this.tiers)) {
      console.warn(
        `Tier '${tierName}' not found. Available tiers: ${Object.keys(this.tiers).join(', ')}. ` +
          `Returning all models.`
      );
      return availableModels;
    }

    const tier = this.tiers[tierName];
    this.stats.byTier[tierName]++;

    // Filter models based on tier's allowed_models
    const filtered: ModelConfig[] = [];

    for (const model of availableModels) {
      if (this.allowsModel(tier, model.name)) {
        filtered.push(model);
      } else {
        this.stats.modelsFilteredOut++;
        if (this.verbose) {
          console.log(`Model '${model.name}' filtered out by tier '${tierName}'`);
        }
      }
    }

    if (this.verbose) {
      console.log(
        `Tier '${tierName}' filtering: ${availableModels.length} → ${filtered.length} models`
      );
      console.log(`  Allowed: ${filtered.map((m) => m.name).join(', ')}`);
      console.log(`  Filtered out: ${availableModels.length - filtered.length}`);
    }

    // Fallback: If no models remain, return cheapest model
    if (filtered.length === 0) {
      // Check if we have any models at all
      if (availableModels.length === 0) {
        return [];
      }

      console.warn(
        `Tier '${tierName}' filtered out ALL models. ` +
          `Returning cheapest model as fallback.`
      );
      // Sort by cost and return cheapest
      const cheapest = [...availableModels].sort((a, b) => a.cost - b.cost)[0];
      return [cheapest];
    }

    return filtered;
  }

  /**
   * Check if a model is allowed for a tier
   *
   * @param tier - Tier configuration
   * @param modelName - Model name to check
   * @returns True if model is allowed
   */
  private allowsModel(tier: TierRouterConfig, modelName: string): boolean {
    const allowedModels = tier.allowedModels ?? ['*'];
    const excludeModels = tier.excludeModels ?? [];

    // Check exclusions first
    if (excludeModels.includes(modelName)) {
      return false;
    }

    // Check if wildcard or specific model
    if (allowedModels.includes('*')) {
      return true;
    }

    return allowedModels.includes(modelName);
  }

  /**
   * Get tier configuration by name
   *
   * @param tierName - Name of the tier
   * @returns TierRouterConfig or undefined if not found
   *
   * @example
   * ```typescript
   * const freeTier = router.getTier('free');
   * if (freeTier) {
   *   console.log(`Max budget: $${freeTier.maxBudget}`);
   * }
   * ```
   */
  getTier(tierName: string): TierRouterConfig | undefined {
    return this.tiers[tierName];
  }

  /**
   * Get tier constraints for display/logging
   *
   * @param tierName - Name of the tier
   * @returns Dictionary of tier constraints
   *
   * @example
   * ```typescript
   * const constraints = router.getTierConstraints('free');
   * console.log(`Max budget: $${constraints.maxBudget}`);
   * console.log(`Allowed models: ${constraints.allowedModels?.join(', ')}`);
   * ```
   */
  getTierConstraints(tierName: string): TierConstraints {
    const tier = this.getTier(tierName);
    if (!tier) {
      return {};
    }

    return {
      maxBudget: tier.maxBudget,
      qualityThreshold: tier.qualityThreshold,
      maxLatencyMs: tier.maxLatencyMs,
      allowedModels: tier.allowedModels,
      excludeModels: tier.excludeModels,
    };
  }

  /**
   * Get routing statistics
   *
   * @returns TierRouterStats with filtering statistics
   *
   * @example
   * ```typescript
   * const stats = router.getStats();
   * console.log(`Total filters: ${stats.totalFilters}`);
   * console.log(`Free tier: ${stats.byTier['free']} queries`);
   * console.log(`Avg filtered: ${stats.avgFilteredPerQuery}`);
   * ```
   */
  getStats(): TierRouterStats {
    const avgFiltered =
      this.stats.totalFilters > 0
        ? this.stats.modelsFilteredOut / this.stats.totalFilters
        : 0;

    return {
      totalFilters: this.stats.totalFilters,
      byTier: { ...this.stats.byTier },
      modelsFilteredOut: this.stats.modelsFilteredOut,
      avgFilteredPerQuery: Math.round(avgFiltered * 100) / 100,
    };
  }

  /**
   * Reset statistics tracking
   *
   * @example
   * ```typescript
   * router.resetStats();
   * console.log(router.getStats().totalFilters); // 0
   * ```
   */
  resetStats(): void {
    this.stats = {
      totalFilters: 0,
      byTier: Object.fromEntries(
        Object.keys(this.tiers).map((tier) => [tier, 0])
      ),
      modelsFilteredOut: 0,
    };

    if (this.verbose) {
      console.log('TierRouter stats reset');
    }
  }

  /**
   * Get list of all tier names
   *
   * @returns Array of tier names
   *
   * @example
   * ```typescript
   * const tiers = router.getTierNames();
   * console.log(`Available tiers: ${tiers.join(', ')}`);
   * ```
   */
  getTierNames(): string[] {
    return Object.keys(this.tiers);
  }

  /**
   * Check if a tier exists
   *
   * @param tierName - Name of the tier
   * @returns True if tier exists
   *
   * @example
   * ```typescript
   * if (router.hasTier('premium')) {
   *   console.log('Premium tier is available');
   * }
   * ```
   */
  hasTier(tierName: string): boolean {
    return tierName in this.tiers;
  }
}

/**
 * Create a TierRouter with configuration
 *
 * @param config - TierRouter configuration
 * @returns Configured TierRouter instance
 *
 * @example
 * ```typescript
 * import { createTierRouter } from '@cascadeflow/core';
 *
 * const router = createTierRouter({
 *   tiers: {
 *     free: { name: 'Free', allowedModels: ['gpt-3.5'], maxBudget: 0.01 },
 *     pro: { name: 'Pro', allowedModels: ['*'], maxBudget: 0.10 }
 *   },
 *   models: allModels,
 *   verbose: true
 * });
 * ```
 */
export function createTierRouter(
  config: TierAwareRouterConfig
): TierRouter {
  return new TierRouter(config);
}
