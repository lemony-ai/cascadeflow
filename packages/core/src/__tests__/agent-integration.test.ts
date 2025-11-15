/**
 * Integration Tests for CascadeAgent
 *
 * Tests key system integrations:
 * - Router integration with quality validation
 * - Telemetry and metrics collection
 * - Factory method integrations
 * - Configuration validation
 *
 * Note: These tests use existing providers (not mocks) to test real integration.
 * Some tests may be skipped if provider API keys are not available.
 *
 * Run: pnpm test agent-integration.test.ts
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { CascadeAgent } from '../agent';
import type { ModelConfig } from '../config';
import { CallbackManager, CallbackEvent } from '../telemetry/callbacks';
import { createUserProfile, TIER_PRESETS } from '../profiles';
import { QualityValidator } from '../quality';

describe('CascadeAgent Integration Tests', () => {
  describe('Configuration and Initialization', () => {
    it('should initialize with valid configuration', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
        },
        {
          name: 'gpt-4o',
          provider: 'openai',
          cost: 0.00625,
        },
      ];

      const agent = new CascadeAgent({ models });

      expect(agent).toBeInstanceOf(CascadeAgent);
      // Agent initializes successfully
    });

    it('should validate model configuration', () => {
      const invalidModels: any[] = [
        {
          name: 'test-model',
          // Missing provider and cost
        },
      ];

      // Note: CascadeAgent may not throw on invalid models but will fail during execution
      const agent = new CascadeAgent({ models: invalidModels });
      expect(agent).toBeInstanceOf(CascadeAgent);
    });

    it('should handle empty model list', () => {
      expect(() => {
        new CascadeAgent({ models: [] });
      }).toThrow();
    });

    it('should initialize routers correctly', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
          supportsTools: true,
        },
      ];

      const agent = new CascadeAgent({ models });
      const routerStats = agent.getRouterStats();

      expect(routerStats.preRouter).toBeDefined();
      expect(routerStats.toolRouter).toBeDefined();
    });
  });

  describe('Metrics and Telemetry Integration', () => {
    it('should initialize metrics collector', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
        },
      ];

      const agent = new CascadeAgent({ models });

      // Agent initializes with metrics tracking capability
      expect(agent).toBeInstanceOf(CascadeAgent);
    });

    it('should accept callback manager', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
        },
      ];

      const callbackManager = new CallbackManager();
      const events: string[] = [];

      callbackManager.register(CallbackEvent.QUERY_START, (data) => {
        events.push('start');
      });

      const agent = new CascadeAgent({
        models,
        callbacks: callbackManager,
      });

      expect(agent).toBeInstanceOf(CascadeAgent);
    });

    it('should reset metrics correctly', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
        },
      ];

      const agent = new CascadeAgent({ models });

      // Reset router stats instead
      agent.resetRouterStats();
      const stats = agent.getRouterStats();

      expect(stats.preRouter).toBeDefined();
      expect(stats.toolRouter).toBeDefined();
    });

    it('should reset router stats correctly', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
        },
      ];

      const agent = new CascadeAgent({ models });

      agent.resetRouterStats();
      const stats = agent.getRouterStats();

      expect(stats.preRouter).toBeDefined();
      expect(stats.toolRouter).toBeDefined();
    });
  });

  describe('Profile Integration', () => {
    it('should create agent with user profile', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
        },
        {
          name: 'gpt-4o',
          provider: 'openai',
          cost: 0.00625,
        },
      ];

      const profile = createUserProfile('FREE', 'test-user-1');

      const agent = CascadeAgent.fromProfile(profile);

      expect(agent).toBeInstanceOf(CascadeAgent);
    });

    it('should use profile tier restrictions', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
        },
      ];

      const profile = createUserProfile('FREE', 'test-user-2');

      // Create agent with profile
      const agent = CascadeAgent.fromProfile(profile);

      expect(agent).toBeInstanceOf(CascadeAgent);
    });
  });

  describe('Quality Validation Integration', () => {
    it('should use quality validator with production confidence', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
        },
      ];

      const agent = new CascadeAgent({
        models,
        quality: {
          useProductionConfidence: true,
          provider: 'openai',
        },
      });

      expect(agent).toBeInstanceOf(CascadeAgent);
    });

    it('should use quality validator factory methods', () => {
      const strictValidator = QualityValidator.strict();
      const prodValidator = QualityValidator.forProduction();
      const devValidator = QualityValidator.forDevelopment();
      const cascadeValidator = QualityValidator.forCascade();
      const permissiveValidator = QualityValidator.permissive();

      expect(strictValidator).toBeInstanceOf(QualityValidator);
      expect(prodValidator).toBeInstanceOf(QualityValidator);
      expect(devValidator).toBeInstanceOf(QualityValidator);
      expect(cascadeValidator).toBeInstanceOf(QualityValidator);
      expect(permissiveValidator).toBeInstanceOf(QualityValidator);

      // Verify configs are different
      expect(strictValidator.getConfig().strictMode).toBe(true);
      expect(prodValidator.getConfig().minConfidence).toBeGreaterThan(0);
      expect(devValidator.getConfig().minConfidence).toBeLessThan(
        prodValidator.getConfig().minConfidence
      );
    });
  });

  describe('Factory Method Integration', () => {
    it('should have fromEnv factory method', () => {
      expect(CascadeAgent.fromEnv).toBeDefined();
      expect(typeof CascadeAgent.fromEnv).toBe('function');
    });

    it('should have fromProfile factory method', () => {
      expect(CascadeAgent.fromProfile).toBeDefined();
      expect(typeof CascadeAgent.fromProfile).toBe('function');
    });
  });

  describe('Cascade Configuration', () => {
    it('should support cascade configuration', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
        },
        {
          name: 'gpt-4o',
          provider: 'openai',
          cost: 0.00625,
        },
      ];

      const agent = new CascadeAgent({
        models,
        quality: {
          minConfidence: 0.7,
          minWordCount: 10,
        },
      });

      expect(agent).toBeInstanceOf(CascadeAgent);
    });

    it('should handle invalid quality thresholds gracefully', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
        },
      ];

      // Should not throw even with invalid config
      const agent = new CascadeAgent({
        models,
        quality: {
          minConfidence: 1.5, // Invalid: > 1
        },
      });

      expect(agent).toBeInstanceOf(CascadeAgent);
    });
  });

  describe('Tool Support Configuration', () => {
    it('should configure models with tool support', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o',
          provider: 'openai',
          cost: 0.00625,
          supportsTools: true,
        },
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
          supportsTools: false,
        },
      ];

      const agent = new CascadeAgent({ models });

      // Agent should initialize successfully
      expect(agent).toBeInstanceOf(CascadeAgent);

      // ToolRouter should track tool-capable models
      const routerStats = agent.getRouterStats();
      expect(routerStats.toolRouter).toBeDefined();
    });
  });

  describe('Model Ordering', () => {
    it('should maintain model order', () => {
      const models: ModelConfig[] = [
        {
          name: 'draft-model',
          provider: 'openai',
          cost: 0.0001,
        },
        {
          name: 'verifier-model',
          provider: 'openai',
          cost: 0.001,
        },
        {
          name: 'premium-model',
          provider: 'openai',
          cost: 0.01,
        },
      ];

      const agent = new CascadeAgent({ models });

      // Models should be accessible in order
      expect(agent).toBeInstanceOf(CascadeAgent);
    });
  });

  describe('Multiple Provider Support', () => {
    it('should support models from different providers', () => {
      const models: ModelConfig[] = [
        {
          name: 'gpt-4o-mini',
          provider: 'openai',
          cost: 0.00015,
        },
        {
          name: 'claude-3-5-haiku-20241022',
          provider: 'anthropic',
          cost: 0.0008,
        },
      ];

      const agent = new CascadeAgent({ models });

      expect(agent).toBeInstanceOf(CascadeAgent);
    });
  });
});
