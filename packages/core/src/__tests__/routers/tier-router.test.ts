/**
 * TierRouter Tests
 *
 * Comprehensive test suite for TierRouter class.
 * Tests tier-based model filtering, constraints, and statistics.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  TierRouter,
  createTierRouter,
  type TierAwareRouterConfig,
  type TierRouterConfig,
} from '../../routers/tier-router';
import type { ModelConfig } from '../../types';

describe('TierRouter', () => {
  // Test models
  const cheapModel: ModelConfig = {
    name: 'gpt-3.5-turbo',
    provider: 'openai',
    cost: 0.002,
  };

  const midModel: ModelConfig = {
    name: 'gpt-4o-mini',
    provider: 'openai',
    cost: 0.01,
  };

  const expensiveModel: ModelConfig = {
    name: 'gpt-4',
    provider: 'openai',
    cost: 0.03,
  };

  const premiumModel: ModelConfig = {
    name: 'claude-3-opus',
    provider: 'anthropic',
    cost: 0.05,
  };

  const allModels = [cheapModel, midModel, expensiveModel, premiumModel];

  // Test tier configurations
  const freeTier: TierRouterConfig = {
    name: 'Free',
    allowedModels: ['gpt-3.5-turbo'],
    maxBudget: 0.01,
    qualityThreshold: 0.6,
  };

  const proTier: TierRouterConfig = {
    name: 'Pro',
    allowedModels: ['gpt-3.5-turbo', 'gpt-4o-mini', 'gpt-4'],
    excludeModels: ['claude-3-opus'],
    maxBudget: 0.05,
    qualityThreshold: 0.8,
  };

  const premiumTier: TierRouterConfig = {
    name: 'Premium',
    allowedModels: ['*'], // All models
    maxBudget: 0.10,
    qualityThreshold: 0.9,
  };

  const tiers = {
    free: freeTier,
    pro: proTier,
    premium: premiumTier,
  };

  let router: TierRouter;

  beforeEach(() => {
    router = new TierRouter({
      tiers,
      models: allModels,
    });
  });

  describe('constructor and configuration', () => {
    it('should initialize with tiers and models', () => {
      expect(router).toBeInstanceOf(TierRouter);
    });

    it('should initialize statistics', () => {
      const stats = router.getStats();
      expect(stats.totalFilters).toBe(0);
      expect(stats.byTier).toHaveProperty('free');
      expect(stats.byTier).toHaveProperty('pro');
      expect(stats.byTier).toHaveProperty('premium');
    });

    it('should support verbose mode', () => {
      const verboseRouter = new TierRouter({
        tiers,
        models: allModels,
        verbose: true,
      });
      expect(verboseRouter).toBeInstanceOf(TierRouter);
    });

    it('should handle empty tiers', () => {
      const emptyRouter = new TierRouter({
        tiers: {},
        models: allModels,
      });
      expect(emptyRouter).toBeInstanceOf(TierRouter);
    });
  });

  describe('filterModels', () => {
    it('should filter models for free tier', () => {
      const filtered = router.filterModels({ tierName: 'free' });

      expect(filtered).toHaveLength(1);
      expect(filtered[0].name).toBe('gpt-3.5-turbo');
    });

    it('should filter models for pro tier', () => {
      const filtered = router.filterModels({ tierName: 'pro' });

      expect(filtered).toHaveLength(3);
      expect(filtered.map((m) => m.name)).toContain('gpt-3.5-turbo');
      expect(filtered.map((m) => m.name)).toContain('gpt-4o-mini');
      expect(filtered.map((m) => m.name)).toContain('gpt-4');
      expect(filtered.map((m) => m.name)).not.toContain('claude-3-opus');
    });

    it('should allow all models for premium tier (wildcard)', () => {
      const filtered = router.filterModels({ tierName: 'premium' });

      expect(filtered).toHaveLength(4);
      expect(filtered).toEqual(allModels);
    });

    it('should return all models for unknown tier with warning', () => {
      const filtered = router.filterModels({ tierName: 'unknown' });

      expect(filtered).toEqual(allModels);
    });

    it('should handle custom available models', () => {
      const customModels = [cheapModel, midModel];
      const filtered = router.filterModels({
        tierName: 'free',
        availableModels: customModels,
      });

      expect(filtered).toHaveLength(1);
      expect(filtered[0].name).toBe('gpt-3.5-turbo');
    });

    it('should respect exclude_models', () => {
      const filtered = router.filterModels({ tierName: 'pro' });

      expect(filtered.map((m) => m.name)).not.toContain('claude-3-opus');
    });

    it('should fallback to cheapest model if all filtered out', () => {
      const restrictiveTier: TierRouterConfig = {
        name: 'Restrictive',
        allowedModels: ['non-existent-model'],
      };

      const restrictiveRouter = new TierRouter({
        tiers: { restrictive: restrictiveTier },
        models: allModels,
      });

      const filtered = restrictiveRouter.filterModels({ tierName: 'restrictive' });

      expect(filtered).toHaveLength(1);
      expect(filtered[0].name).toBe('gpt-3.5-turbo'); // Cheapest
    });

    it('should handle tiers with no allowed_models (defaults to wildcard)', () => {
      const openTier: TierRouterConfig = {
        name: 'Open',
        // No allowedModels specified
      };

      const openRouter = new TierRouter({
        tiers: { open: openTier },
        models: allModels,
      });

      const filtered = openRouter.filterModels({ tierName: 'open' });

      expect(filtered).toHaveLength(4);
      expect(filtered).toEqual(allModels);
    });
  });

  describe('getTier', () => {
    it('should get tier configuration by name', () => {
      const tier = router.getTier('free');

      expect(tier).toBeDefined();
      expect(tier?.name).toBe('Free');
      expect(tier?.maxBudget).toBe(0.01);
    });

    it('should return undefined for unknown tier', () => {
      const tier = router.getTier('unknown');

      expect(tier).toBeUndefined();
    });
  });

  describe('getTierConstraints', () => {
    it('should get tier constraints', () => {
      const constraints = router.getTierConstraints('free');

      expect(constraints.maxBudget).toBe(0.01);
      expect(constraints.qualityThreshold).toBe(0.6);
      expect(constraints.allowedModels).toEqual(['gpt-3.5-turbo']);
    });

    it('should return empty object for unknown tier', () => {
      const constraints = router.getTierConstraints('unknown');

      expect(constraints).toEqual({});
    });

    it('should include all constraint fields', () => {
      const constraints = router.getTierConstraints('pro');

      expect(constraints).toHaveProperty('maxBudget');
      expect(constraints).toHaveProperty('qualityThreshold');
      expect(constraints).toHaveProperty('allowedModels');
      expect(constraints).toHaveProperty('excludeModels');
    });
  });

  describe('statistics tracking', () => {
    it('should track total filters', () => {
      router.filterModels({ tierName: 'free' });
      router.filterModels({ tierName: 'pro' });
      router.filterModels({ tierName: 'premium' });

      const stats = router.getStats();
      expect(stats.totalFilters).toBe(3);
    });

    it('should track filters by tier', () => {
      router.filterModels({ tierName: 'free' });
      router.filterModels({ tierName: 'free' });
      router.filterModels({ tierName: 'pro' });

      const stats = router.getStats();
      expect(stats.byTier['free']).toBe(2);
      expect(stats.byTier['pro']).toBe(1);
      expect(stats.byTier['premium']).toBe(0);
    });

    it('should track models filtered out', () => {
      router.filterModels({ tierName: 'free' }); // Filters out 3 models

      const stats = router.getStats();
      expect(stats.modelsFilteredOut).toBe(3);
    });

    it('should calculate average filtered per query', () => {
      router.filterModels({ tierName: 'free' }); // Filters out 3
      router.filterModels({ tierName: 'pro' }); // Filters out 1
      router.filterModels({ tierName: 'premium' }); // Filters out 0

      const stats = router.getStats();
      expect(stats.avgFilteredPerQuery).toBeCloseTo(1.33, 2); // (3+1+0)/3
    });

    it('should reset statistics', () => {
      router.filterModels({ tierName: 'free' });
      router.filterModels({ tierName: 'pro' });

      router.resetStats();

      const stats = router.getStats();
      expect(stats.totalFilters).toBe(0);
      expect(stats.byTier['free']).toBe(0);
      expect(stats.byTier['pro']).toBe(0);
      expect(stats.modelsFilteredOut).toBe(0);
    });

    it('should handle zero stats gracefully', () => {
      const stats = router.getStats();
      expect(stats.avgFilteredPerQuery).toBe(0);
    });
  });

  describe('getTierNames', () => {
    it('should return list of tier names', () => {
      const names = router.getTierNames();

      expect(names).toHaveLength(3);
      expect(names).toContain('free');
      expect(names).toContain('pro');
      expect(names).toContain('premium');
    });

    it('should return empty array for router with no tiers', () => {
      const emptyRouter = new TierRouter({
        tiers: {},
        models: allModels,
      });

      const names = emptyRouter.getTierNames();
      expect(names).toHaveLength(0);
    });
  });

  describe('hasTier', () => {
    it('should return true for existing tier', () => {
      expect(router.hasTier('free')).toBe(true);
      expect(router.hasTier('pro')).toBe(true);
      expect(router.hasTier('premium')).toBe(true);
    });

    it('should return false for non-existent tier', () => {
      expect(router.hasTier('unknown')).toBe(false);
      expect(router.hasTier('enterprise')).toBe(false);
    });
  });

  describe('createTierRouter factory', () => {
    it('should create router with factory', () => {
      const router = createTierRouter({
        tiers,
        models: allModels,
      });

      expect(router).toBeInstanceOf(TierRouter);
    });

    it('should pass config to constructor', () => {
      const router = createTierRouter({
        tiers,
        models: allModels,
        verbose: true,
      });

      expect(router).toBeInstanceOf(TierRouter);
    });
  });

  describe('edge cases', () => {
    it('should handle empty models array', () => {
      const emptyRouter = new TierRouter({
        tiers,
        models: [],
      });

      const filtered = emptyRouter.filterModels({ tierName: 'free' });
      expect(filtered).toHaveLength(0);
    });

    it('should handle tier with empty allowed_models array', () => {
      const emptyAllowedTier: TierRouterConfig = {
        name: 'Empty',
        allowedModels: [],
      };

      const router = new TierRouter({
        tiers: { empty: emptyAllowedTier },
        models: allModels,
      });

      const filtered = router.filterModels({ tierName: 'empty' });

      // Should fallback to cheapest
      expect(filtered).toHaveLength(1);
      expect(filtered[0].name).toBe('gpt-3.5-turbo');
    });

    it('should handle tier with only exclude_models', () => {
      const excludeOnlyTier: TierRouterConfig = {
        name: 'ExcludeOnly',
        excludeModels: ['gpt-4', 'claude-3-opus'],
      };

      const router = new TierRouter({
        tiers: { excludeOnly: excludeOnlyTier },
        models: allModels,
      });

      const filtered = router.filterModels({ tierName: 'excludeOnly' });

      expect(filtered).toHaveLength(2);
      expect(filtered.map((m) => m.name)).toContain('gpt-3.5-turbo');
      expect(filtered.map((m) => m.name)).toContain('gpt-4o-mini');
    });

    it('should handle model in both allowed and excluded (exclude wins)', () => {
      const conflictTier: TierRouterConfig = {
        name: 'Conflict',
        allowedModels: ['gpt-4'],
        excludeModels: ['gpt-4'], // Excluded
      };

      const router = new TierRouter({
        tiers: { conflict: conflictTier },
        models: allModels,
      });

      const filtered = router.filterModels({ tierName: 'conflict' });

      // Should fallback to cheapest
      expect(filtered).toHaveLength(1);
      expect(filtered[0].name).toBe('gpt-3.5-turbo');
    });

    it('should handle very large model arrays', () => {
      const manyModels: ModelConfig[] = Array.from({ length: 1000 }, (_, i) => ({
        name: `model-${i}`,
        provider: 'test',
        cost: 0.01 + i * 0.001,
      }));

      const largeTier: TierRouterConfig = {
        name: 'Large',
        allowedModels: ['model-0', 'model-1', 'model-2'],
      };

      const largeRouter = new TierRouter({
        tiers: { large: largeTier },
        models: manyModels,
      });

      const filtered = largeRouter.filterModels({ tierName: 'large' });

      expect(filtered).toHaveLength(3);
    });

    it('should handle multiple calls with same tier', () => {
      const filtered1 = router.filterModels({ tierName: 'free' });
      const filtered2 = router.filterModels({ tierName: 'free' });
      const filtered3 = router.filterModels({ tierName: 'free' });

      expect(filtered1).toEqual(filtered2);
      expect(filtered2).toEqual(filtered3);

      const stats = router.getStats();
      expect(stats.byTier['free']).toBe(3);
    });

    it('should handle tier with undefined maxBudget', () => {
      const noLimitTier: TierRouterConfig = {
        name: 'NoLimit',
        allowedModels: ['*'],
        // No maxBudget
      };

      const router = new TierRouter({
        tiers: { noLimit: noLimitTier },
        models: allModels,
      });

      const constraints = router.getTierConstraints('noLimit');
      expect(constraints.maxBudget).toBeUndefined();
    });
  });

  describe('wildcard behavior', () => {
    it('should allow all models with wildcard', () => {
      const wildcardTier: TierRouterConfig = {
        name: 'Wildcard',
        allowedModels: ['*'],
      };

      const router = new TierRouter({
        tiers: { wildcard: wildcardTier },
        models: allModels,
      });

      const filtered = router.filterModels({ tierName: 'wildcard' });

      expect(filtered).toHaveLength(4);
      expect(filtered).toEqual(allModels);
    });

    it('should respect exclude with wildcard', () => {
      const wildcardExcludeTier: TierRouterConfig = {
        name: 'WildcardExclude',
        allowedModels: ['*'],
        excludeModels: ['gpt-4', 'claude-3-opus'],
      };

      const router = new TierRouter({
        tiers: { wildcardExclude: wildcardExcludeTier },
        models: allModels,
      });

      const filtered = router.filterModels({ tierName: 'wildcardExclude' });

      expect(filtered).toHaveLength(2);
      expect(filtered.map((m) => m.name)).toContain('gpt-3.5-turbo');
      expect(filtered.map((m) => m.name)).toContain('gpt-4o-mini');
    });
  });
});
