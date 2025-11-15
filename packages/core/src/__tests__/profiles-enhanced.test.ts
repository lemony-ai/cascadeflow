/**
 * Tests for Enhanced UserProfile System
 *
 * Tests latency awareness, optimization weights, and cost sensitivity
 *
 * Run: pnpm test profiles-enhanced.test.ts
 */

import { describe, it, expect } from 'vitest';
import {
  validateOptimizationWeights,
  createOptimizationWeights,
  createLatencyProfile,
  OPTIMIZATION_PRESETS,
  LATENCY_PRESETS,
  getDailyBudget,
  getRequestsPerHour,
  getRequestsPerDay,
  getOptimizationWeights,
  getLatencyProfile,
  createUserProfile,
  TIER_PRESETS,
} from '../profiles';
import type {
  OptimizationWeights,
  LatencyProfile,
  UserProfile,
} from '../types';

describe('OptimizationWeights', () => {
  describe('validateOptimizationWeights', () => {
    it('should accept valid weights that sum to 1.0', () => {
      const weights: OptimizationWeights = { cost: 0.3, speed: 0.4, quality: 0.3 };
      expect(() => validateOptimizationWeights(weights)).not.toThrow();
    });

    it('should reject weights that sum to less than 1.0', () => {
      const weights: OptimizationWeights = { cost: 0.3, speed: 0.3, quality: 0.3 };
      expect(() => validateOptimizationWeights(weights)).toThrow('must sum to 1.0');
    });

    it('should reject weights that sum to more than 1.0', () => {
      const weights: OptimizationWeights = { cost: 0.4, speed: 0.4, quality: 0.4 };
      expect(() => validateOptimizationWeights(weights)).toThrow('must sum to 1.0');
    });

    it('should accept weights within floating point tolerance', () => {
      const weights: OptimizationWeights = { cost: 0.333, speed: 0.333, quality: 0.334 };
      expect(() => validateOptimizationWeights(weights)).not.toThrow();
    });

    it('should reject negative cost weight', () => {
      const weights: OptimizationWeights = { cost: -0.1, speed: 0.6, quality: 0.5 };
      expect(() => validateOptimizationWeights(weights)).toThrow('Cost weight');
    });

    it('should reject cost weight greater than 1', () => {
      const weights: OptimizationWeights = { cost: 1.5, speed: 0.0, quality: -0.5 };
      expect(() => validateOptimizationWeights(weights)).toThrow('Cost weight');
    });

    it('should reject negative speed weight', () => {
      const weights: OptimizationWeights = { cost: 0.6, speed: -0.1, quality: 0.5 };
      expect(() => validateOptimizationWeights(weights)).toThrow('Speed weight');
    });

    it('should reject negative quality weight', () => {
      const weights: OptimizationWeights = { cost: 0.6, speed: 0.5, quality: -0.1 };
      expect(() => validateOptimizationWeights(weights)).toThrow('Quality weight');
    });
  });

  describe('createOptimizationWeights', () => {
    it('should create valid weights', () => {
      const weights = createOptimizationWeights(0.2, 0.5, 0.3);
      expect(weights).toEqual({ cost: 0.2, speed: 0.5, quality: 0.3 });
    });

    it('should throw for invalid weights', () => {
      expect(() => createOptimizationWeights(0.5, 0.5, 0.5)).toThrow();
    });
  });

  describe('OPTIMIZATION_PRESETS', () => {
    it('should have aggressive preset with high cost weight', () => {
      const aggressive = OPTIMIZATION_PRESETS.aggressive;
      expect(aggressive.cost).toBe(0.7);
      expect(aggressive.speed).toBe(0.15);
      expect(aggressive.quality).toBe(0.15);
      expect(() => validateOptimizationWeights(aggressive)).not.toThrow();
    });

    it('should have balanced preset with equal distribution', () => {
      const balanced = OPTIMIZATION_PRESETS.balanced;
      expect(balanced.cost).toBe(0.4);
      expect(balanced.speed).toBe(0.3);
      expect(balanced.quality).toBe(0.3);
      expect(() => validateOptimizationWeights(balanced)).not.toThrow();
    });

    it('should have quality_first preset with high quality weight', () => {
      const qualityFirst = OPTIMIZATION_PRESETS.quality_first;
      expect(qualityFirst.cost).toBe(0.1);
      expect(qualityFirst.speed).toBe(0.3);
      expect(qualityFirst.quality).toBe(0.6);
      expect(() => validateOptimizationWeights(qualityFirst)).not.toThrow();
    });

    it('should have all presets sum to 1.0', () => {
      for (const [name, weights] of Object.entries(OPTIMIZATION_PRESETS)) {
        expect(() => validateOptimizationWeights(weights)).not.toThrow();
      }
    });
  });
});

describe('LatencyProfile', () => {
  describe('createLatencyProfile', () => {
    it('should create profile with defaults', () => {
      const profile = createLatencyProfile();
      expect(profile).toEqual({
        maxTotalMs: 5000,
        maxPerModelMs: 3000,
        preferParallel: false,
        skipCascadeThreshold: 0,
      });
    });

    it('should override specific fields', () => {
      const profile = createLatencyProfile({
        maxTotalMs: 2000,
        preferParallel: true,
      });
      expect(profile.maxTotalMs).toBe(2000);
      expect(profile.maxPerModelMs).toBe(3000); // default
      expect(profile.preferParallel).toBe(true);
      expect(profile.skipCascadeThreshold).toBe(0); // default
    });

    it('should allow zero values', () => {
      const profile = createLatencyProfile({
        maxTotalMs: 0,
        maxPerModelMs: 0,
        skipCascadeThreshold: 0,
      });
      expect(profile.maxTotalMs).toBe(0);
      expect(profile.maxPerModelMs).toBe(0);
    });
  });

  describe('LATENCY_PRESETS', () => {
    it('should have realtime preset with low latency', () => {
      const realtime = LATENCY_PRESETS.realtime;
      expect(realtime.maxTotalMs).toBe(1000);
      expect(realtime.maxPerModelMs).toBe(800);
      expect(realtime.preferParallel).toBe(true);
      expect(realtime.skipCascadeThreshold).toBe(800);
    });

    it('should have interactive preset with moderate latency', () => {
      const interactive = LATENCY_PRESETS.interactive;
      expect(interactive.maxTotalMs).toBe(3000);
      expect(interactive.maxPerModelMs).toBe(2000);
      expect(interactive.preferParallel).toBe(true);
      expect(interactive.skipCascadeThreshold).toBe(1500);
    });

    it('should have standard preset', () => {
      const standard = LATENCY_PRESETS.standard;
      expect(standard.maxTotalMs).toBe(8000);
      expect(standard.maxPerModelMs).toBe(5000);
      expect(standard.preferParallel).toBe(false);
      expect(standard.skipCascadeThreshold).toBe(2000);
    });

    it('should have batch preset with high latency tolerance', () => {
      const batch = LATENCY_PRESETS.batch;
      expect(batch.maxTotalMs).toBe(30000);
      expect(batch.maxPerModelMs).toBe(20000);
      expect(batch.preferParallel).toBe(false);
      expect(batch.skipCascadeThreshold).toBe(0);
    });

    it('should have increasing latency tolerance', () => {
      expect(LATENCY_PRESETS.realtime.maxTotalMs).toBeLessThan(
        LATENCY_PRESETS.interactive.maxTotalMs
      );
      expect(LATENCY_PRESETS.interactive.maxTotalMs).toBeLessThan(
        LATENCY_PRESETS.standard.maxTotalMs
      );
      expect(LATENCY_PRESETS.standard.maxTotalMs).toBeLessThan(
        LATENCY_PRESETS.batch.maxTotalMs
      );
    });
  });
});

describe('UserProfile Helper Functions', () => {
  describe('getDailyBudget', () => {
    it('should return custom budget when set', () => {
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.FREE,
        customDailyBudget: 5.0,
      };
      expect(getDailyBudget(profile)).toBe(5.0);
    });

    it('should return tier budget when custom not set', () => {
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.PRO,
      };
      expect(getDailyBudget(profile)).toBe(TIER_PRESETS.PRO.dailyBudget);
    });

    it('should handle zero custom budget', () => {
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.PRO,
        customDailyBudget: 0,
      };
      expect(getDailyBudget(profile)).toBe(0);
    });
  });

  describe('getRequestsPerHour', () => {
    it('should return custom limit when set', () => {
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.FREE,
        customRequestsPerHour: 1000,
      };
      expect(getRequestsPerHour(profile)).toBe(1000);
    });

    it('should return tier limit when custom not set', () => {
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.STARTER,
      };
      expect(getRequestsPerHour(profile)).toBe(TIER_PRESETS.STARTER.requestsPerHour);
    });
  });

  describe('getRequestsPerDay', () => {
    it('should return custom limit when set', () => {
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.FREE,
        customRequestsPerDay: 5000,
      };
      expect(getRequestsPerDay(profile)).toBe(5000);
    });

    it('should return tier limit when custom not set', () => {
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.BUSINESS,
      };
      expect(getRequestsPerDay(profile)).toBe(TIER_PRESETS.BUSINESS.requestsPerDay);
    });
  });

  describe('getOptimizationWeights', () => {
    it('should return explicit weights when set', () => {
      const customWeights = createOptimizationWeights(0.2, 0.3, 0.5);
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.PRO,
        optimization: customWeights,
      };
      expect(getOptimizationWeights(profile)).toEqual(customWeights);
    });

    it('should derive from cost sensitivity when weights not set', () => {
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.PRO,
        costSensitivity: 'aggressive',
      };
      expect(getOptimizationWeights(profile)).toEqual(OPTIMIZATION_PRESETS.aggressive);
    });

    it('should default to balanced when neither set', () => {
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.PRO,
      };
      expect(getOptimizationWeights(profile)).toEqual(OPTIMIZATION_PRESETS.balanced);
    });

    it('should prefer explicit weights over cost sensitivity', () => {
      const customWeights = createOptimizationWeights(0.1, 0.1, 0.8);
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.PRO,
        costSensitivity: 'aggressive',
        optimization: customWeights,
      };
      expect(getOptimizationWeights(profile)).toEqual(customWeights);
      expect(getOptimizationWeights(profile)).not.toEqual(OPTIMIZATION_PRESETS.aggressive);
    });
  });

  describe('getLatencyProfile', () => {
    it('should return explicit latency profile when set', () => {
      const customLatency = createLatencyProfile({
        maxTotalMs: 1500,
        preferParallel: true,
      });
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.PRO,
        latency: customLatency,
      };
      expect(getLatencyProfile(profile)).toEqual(customLatency);
    });

    it('should default to standard preset when not set', () => {
      const profile: UserProfile = {
        userId: 'test-user',
        tier: TIER_PRESETS.PRO,
      };
      expect(getLatencyProfile(profile)).toEqual(LATENCY_PRESETS.standard);
    });
  });
});

describe('Enhanced UserProfile Integration', () => {
  it('should create profile with all new fields', () => {
    const profile = createUserProfile('PRO', 'user-123', {
      costSensitivity: 'quality_first',
      latency: LATENCY_PRESETS.interactive,
      optimization: OPTIMIZATION_PRESETS.balanced,
    });

    expect(profile.userId).toBe('user-123');
    expect(profile.tier).toEqual(TIER_PRESETS.PRO);
    expect(profile.costSensitivity).toBe('quality_first');
    expect(profile.latency).toEqual(LATENCY_PRESETS.interactive);
    expect(profile.optimization).toEqual(OPTIMIZATION_PRESETS.balanced);
  });

  it('should handle profile with only cost sensitivity', () => {
    const profile = createUserProfile('STARTER', 'user-456', {
      costSensitivity: 'aggressive',
    });

    expect(getOptimizationWeights(profile)).toEqual(OPTIMIZATION_PRESETS.aggressive);
    expect(getLatencyProfile(profile)).toEqual(LATENCY_PRESETS.standard);
  });

  it('should handle profile with createdAt timestamp', () => {
    const now = new Date();
    const profile = createUserProfile('FREE', 'user-789', {
      createdAt: now,
    });

    expect(profile.createdAt).toEqual(now);
  });

  it('should combine tier defaults with custom overrides', () => {
    const profile = createUserProfile('BUSINESS', 'user-999', {
      customDailyBudget: 100.0,
      customRequestsPerHour: 10000,
      costSensitivity: 'quality_first',
    });

    expect(getDailyBudget(profile)).toBe(100.0); // Custom override
    expect(getRequestsPerHour(profile)).toBe(10000); // Custom override
    expect(getRequestsPerDay(profile)).toBe(TIER_PRESETS.BUSINESS.requestsPerDay); // Tier default
    expect(getOptimizationWeights(profile)).toEqual(OPTIMIZATION_PRESETS.quality_first);
  });
});

describe('Cost Sensitivity Modes', () => {
  it('should have aggressive mode prioritize cost', () => {
    const weights = OPTIMIZATION_PRESETS.aggressive;
    expect(weights.cost).toBeGreaterThan(weights.speed);
    expect(weights.cost).toBeGreaterThan(weights.quality);
  });

  it('should have quality_first mode prioritize quality', () => {
    const weights = OPTIMIZATION_PRESETS.quality_first;
    expect(weights.quality).toBeGreaterThan(weights.cost);
    expect(weights.quality).toBeGreaterThan(weights.speed);
  });

  it('should have balanced mode distribute evenly', () => {
    const weights = OPTIMIZATION_PRESETS.balanced;
    expect(weights.cost).toBeGreaterThanOrEqual(0.3);
    expect(weights.speed).toBeGreaterThanOrEqual(0.3);
    expect(weights.quality).toBeGreaterThanOrEqual(0.3);
  });
});

describe('Latency Awareness', () => {
  it('should have faster presets prefer parallel execution', () => {
    expect(LATENCY_PRESETS.realtime.preferParallel).toBe(true);
    expect(LATENCY_PRESETS.interactive.preferParallel).toBe(true);
    expect(LATENCY_PRESETS.standard.preferParallel).toBe(false);
    expect(LATENCY_PRESETS.batch.preferParallel).toBe(false);
  });

  it('should have faster presets with higher skip thresholds', () => {
    expect(LATENCY_PRESETS.realtime.skipCascadeThreshold).toBeGreaterThan(
      LATENCY_PRESETS.batch.skipCascadeThreshold
    );
    expect(LATENCY_PRESETS.interactive.skipCascadeThreshold).toBeGreaterThan(
      LATENCY_PRESETS.batch.skipCascadeThreshold
    );
  });

  it('should have maxPerModelMs less than maxTotalMs', () => {
    for (const [name, profile] of Object.entries(LATENCY_PRESETS)) {
      expect(profile.maxPerModelMs).toBeLessThanOrEqual(profile.maxTotalMs);
    }
  });
});
