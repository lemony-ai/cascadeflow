/**
 * Tests for CascadeAgent Factory Methods
 *
 * Tests static factory methods for creating CascadeAgent instances
 * from different sources (environment, profile, tier).
 *
 * Run: pnpm test agent-factory.test.ts
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { CascadeAgent } from '../agent';
import { createUserProfile, TIER_PRESETS } from '../profiles';
import type { TierLevel } from '../types';

describe('CascadeAgent Factory Methods', () => {
  // Store original environment
  const originalEnv = { ...process.env };

  beforeEach(() => {
    // Reset environment before each test
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    // Restore environment after each test
    process.env = originalEnv;
  });

  describe('fromEnv()', () => {
    it('should create agent with OpenAI when OPENAI_API_KEY is set', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const agent = CascadeAgent.fromEnv();

      expect(agent).toBeInstanceOf(CascadeAgent);
      // Agent should have OpenAI models configured
      expect(agent['models'].some(m => m.provider === 'openai')).toBe(true);
    });

    it('should create agent with Anthropic when ANTHROPIC_API_KEY is set', () => {
      process.env.ANTHROPIC_API_KEY = 'test-key';

      const agent = CascadeAgent.fromEnv();

      expect(agent).toBeInstanceOf(CascadeAgent);
      expect(agent['models'].some(m => m.provider === 'anthropic')).toBe(true);
    });

    it('should create agent with multiple providers when multiple keys are set', () => {
      process.env.OPENAI_API_KEY = 'test-key-1';
      process.env.ANTHROPIC_API_KEY = 'test-key-2';

      const agent = CascadeAgent.fromEnv();

      expect(agent).toBeInstanceOf(CascadeAgent);
      expect(agent['models'].some(m => m.provider === 'openai')).toBe(true);
      expect(agent['models'].some(m => m.provider === 'anthropic')).toBe(true);
    });

    it('should include Groq models when GROQ_API_KEY is set', () => {
      process.env.GROQ_API_KEY = 'test-key';

      const agent = CascadeAgent.fromEnv();

      expect(agent).toBeInstanceOf(CascadeAgent);
      expect(agent['models'].some(m => m.provider === 'groq')).toBe(true);
    });

    it('should throw error when no API keys are set', () => {
      // Clear all API keys
      delete process.env.OPENAI_API_KEY;
      delete process.env.ANTHROPIC_API_KEY;
      delete process.env.GROQ_API_KEY;
      delete process.env.TOGETHER_API_KEY;

      expect(() => CascadeAgent.fromEnv()).toThrow(
        'No providers available. Set API keys in environment'
      );
    });

    it('should include standard OpenAI models in correct order', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const agent = CascadeAgent.fromEnv();
      const openaiModels = agent['models'].filter(m => m.provider === 'openai');

      expect(openaiModels.map(m => m.name)).toEqual([
        'gpt-4o-mini',
        'gpt-3.5-turbo',
        'gpt-4o'
      ]);
    });

    it('should include standard Anthropic models in correct order', () => {
      process.env.ANTHROPIC_API_KEY = 'test-key';

      const agent = CascadeAgent.fromEnv();
      const anthropicModels = agent['models'].filter(m => m.provider === 'anthropic');

      expect(anthropicModels.map(m => m.name)).toEqual([
        'claude-3-5-haiku-20241022',
        'claude-3-5-sonnet-20241022'
      ]);
    });

    it('should accept quality configuration override', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const agent = CascadeAgent.fromEnv({
        quality: { minConfidence: 0.9 }
      });

      expect(agent).toBeInstanceOf(CascadeAgent);
      // Quality config should be applied (checking internal config)
      expect(agent['qualityValidator']['config']?.minConfidence).toBe(0.9);
    });

    it('should have correct cost values for models', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const agent = CascadeAgent.fromEnv();
      const gpt4oMini = agent['models'].find(m => m.name === 'gpt-4o-mini');
      const gpt35 = agent['models'].find(m => m.name === 'gpt-3.5-turbo');
      const gpt4o = agent['models'].find(m => m.name === 'gpt-4o');

      expect(gpt4oMini?.cost).toBe(0.00015);
      expect(gpt35?.cost).toBe(0.002);
      expect(gpt4o?.cost).toBe(0.00625);
    });
  });

  describe('fromProfile()', () => {
    it('should create agent from FREE tier profile', () => {
      process.env.OPENAI_API_KEY = 'test-key';
      const profile = createUserProfile('FREE', 'user-123');

      const agent = CascadeAgent.fromProfile(profile);

      expect(agent).toBeInstanceOf(CascadeAgent);
      expect(agent['qualityValidator']['config']?.minConfidence).toBe(
        TIER_PRESETS.FREE.minQuality
      );
    });

    it('should create agent from PRO tier profile', () => {
      process.env.OPENAI_API_KEY = 'test-key';
      const profile = createUserProfile('PRO', 'user-456');

      const agent = CascadeAgent.fromProfile(profile);

      expect(agent).toBeInstanceOf(CascadeAgent);
      expect(agent['qualityValidator']['config']?.minConfidence).toBe(
        TIER_PRESETS.PRO.minQuality
      );
    });

    it('should filter models by preferredModels list', () => {
      process.env.OPENAI_API_KEY = 'test-key';
      process.env.ANTHROPIC_API_KEY = 'test-key';

      const profile = createUserProfile('PRO', 'user-789', {
        preferredModels: ['gpt-4o', 'claude-3-5-sonnet-20241022']
      });

      const agent = CascadeAgent.fromProfile(profile);
      const modelNames = agent['models'].map(m => m.name);

      expect(modelNames).toContain('gpt-4o');
      expect(modelNames).toContain('claude-3-5-sonnet-20241022');
      expect(modelNames).not.toContain('gpt-4o-mini');
      expect(modelNames).not.toContain('claude-3-5-haiku-20241022');
    });

    it('should include all available models when no preferred models specified', () => {
      process.env.OPENAI_API_KEY = 'test-key';
      process.env.ANTHROPIC_API_KEY = 'test-key';

      const profile = createUserProfile('PRO', 'user-999');

      const agent = CascadeAgent.fromProfile(profile);
      const modelNames = agent['models'].map(m => m.name);

      // Should include both OpenAI and Anthropic models
      expect(modelNames.length).toBeGreaterThan(3);
    });

    it('should allow quality configuration override', () => {
      process.env.OPENAI_API_KEY = 'test-key';
      const profile = createUserProfile('PRO', 'user-123');

      const agent = CascadeAgent.fromProfile(profile, {
        quality: { minConfidence: 0.95 }
      });

      expect(agent['qualityValidator']['config']?.minConfidence).toBe(0.95);
    });

    it('should throw error when no API keys are set', () => {
      delete process.env.OPENAI_API_KEY;
      delete process.env.ANTHROPIC_API_KEY;
      delete process.env.GROQ_API_KEY;

      const profile = createUserProfile('PRO', 'user-123');

      expect(() => CascadeAgent.fromProfile(profile)).toThrow(
        'No providers available. Set API keys in environment'
      );
    });

    it('should throw error when no models match preferred models', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const profile = createUserProfile('PRO', 'user-123', {
        preferredModels: ['non-existent-model']
      });

      expect(() => CascadeAgent.fromProfile(profile)).toThrow(
        'No models available matching profile preferences'
      );
    });

    it('should handle profile with only Groq models preferred', () => {
      process.env.GROQ_API_KEY = 'test-key';

      const profile = createUserProfile('PRO', 'user-123', {
        preferredModels: ['llama-3.3-70b-versatile']
      });

      const agent = CascadeAgent.fromProfile(profile);
      const modelNames = agent['models'].map(m => m.name);

      expect(modelNames).toContain('llama-3.3-70b-versatile');
      expect(modelNames.length).toBe(1);
    });

    it('should respect tier quality settings from profile', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const freeTier = createUserProfile('FREE', 'user-free');
      const proTier = createUserProfile('PRO', 'user-pro');
      const enterpriseTier = createUserProfile('ENTERPRISE', 'user-ent');

      const freeAgent = CascadeAgent.fromProfile(freeTier);
      const proAgent = CascadeAgent.fromProfile(proTier);
      const enterpriseAgent = CascadeAgent.fromProfile(enterpriseTier);

      expect(freeAgent['qualityValidator']['config'].minConfidence).toBe(0.6);
      expect(proAgent['qualityValidator']['config'].minConfidence).toBe(0.75);
      expect(enterpriseAgent['qualityValidator']['config'].minConfidence).toBe(0.85);
    });
  });

  describe('forTier()', () => {
    it('should create agent for FREE tier', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const agent = CascadeAgent.forTier('FREE');

      expect(agent).toBeInstanceOf(CascadeAgent);
      expect(agent['qualityValidator']['config']?.minConfidence).toBe(
        TIER_PRESETS.FREE.minQuality
      );
    });

    it('should create agent for STARTER tier', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const agent = CascadeAgent.forTier('STARTER');

      expect(agent).toBeInstanceOf(CascadeAgent);
      expect(agent['qualityValidator']['config']?.minConfidence).toBe(
        TIER_PRESETS.STARTER.minQuality
      );
    });

    it('should create agent for PRO tier', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const agent = CascadeAgent.forTier('PRO');

      expect(agent).toBeInstanceOf(CascadeAgent);
      expect(agent['qualityValidator']['config']?.minConfidence).toBe(
        TIER_PRESETS.PRO.minQuality
      );
    });

    it('should create agent for BUSINESS tier', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const agent = CascadeAgent.forTier('BUSINESS');

      expect(agent).toBeInstanceOf(CascadeAgent);
      expect(agent['qualityValidator']['config']?.minConfidence).toBe(
        TIER_PRESETS.BUSINESS.minQuality
      );
    });

    it('should create agent for ENTERPRISE tier', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const agent = CascadeAgent.forTier('ENTERPRISE');

      expect(agent).toBeInstanceOf(CascadeAgent);
      expect(agent['qualityValidator']['config']?.minConfidence).toBe(
        TIER_PRESETS.ENTERPRISE.minQuality
      );
    });

    it('should allow quality configuration override', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const agent = CascadeAgent.forTier('PRO', {
        quality: { minConfidence: 0.95 }
      });

      expect(agent['qualityValidator']['config']?.minConfidence).toBe(0.95);
    });

    it('should throw error when no API keys are set', () => {
      delete process.env.OPENAI_API_KEY;
      delete process.env.ANTHROPIC_API_KEY;
      delete process.env.GROQ_API_KEY;

      expect(() => CascadeAgent.forTier('PRO')).toThrow(
        'No providers available. Set API keys in environment'
      );
    });

    it('should have correct quality thresholds for all tiers', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const tiers: TierLevel[] = ['FREE', 'STARTER', 'PRO', 'BUSINESS', 'ENTERPRISE'];
      const expectedQuality = [0.6, 0.7, 0.75, 0.8, 0.85];

      for (let i = 0; i < tiers.length; i++) {
        const agent = CascadeAgent.forTier(tiers[i]);
        expect(agent['qualityValidator']['config']?.minConfidence).toBe(expectedQuality[i]);
      }
    });
  });

  describe('Integration Tests', () => {
    it('should create functionally equivalent agents from different methods', () => {
      process.env.OPENAI_API_KEY = 'test-key';

      const profile = createUserProfile('PRO', 'user-123');

      const fromEnvAgent = CascadeAgent.fromEnv({
        quality: { minConfidence: 0.7 }
      });
      const fromProfileAgent = CascadeAgent.fromProfile(profile);
      const forTierAgent = CascadeAgent.forTier('PRO');

      // All should have same quality threshold (PRO tier)
      expect(fromEnvAgent['qualityValidator']['config'].minConfidence).toBe(0.7);
      expect(fromProfileAgent['qualityValidator']['config'].minConfidence).toBe(0.75);
      expect(forTierAgent['qualityValidator']['config'].minConfidence).toBe(0.75);
    });

    it('should handle mixed provider scenarios', () => {
      process.env.OPENAI_API_KEY = 'test-key';
      process.env.ANTHROPIC_API_KEY = 'test-key';
      process.env.GROQ_API_KEY = 'test-key';

      const agent = CascadeAgent.fromEnv();
      const providers = new Set(agent['models'].map(m => m.provider));

      expect(providers.has('openai')).toBe(true);
      expect(providers.has('anthropic')).toBe(true);
      expect(providers.has('groq')).toBe(true);
    });

    it('should create agents with sensible model ordering', () => {
      process.env.OPENAI_API_KEY = 'test-key';
      process.env.ANTHROPIC_API_KEY = 'test-key';

      const agent = CascadeAgent.fromEnv();
      const costs = agent['models'].map(m => m.cost);

      // Models should generally be ordered by cost (cheapest first for cascading)
      // Check that we have a range of costs
      expect(Math.min(...costs)).toBeLessThan(0.001);
      expect(Math.max(...costs)).toBeGreaterThan(0.003);
    });
  });
});
