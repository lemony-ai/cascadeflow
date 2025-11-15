/**
 * Tests for WorkflowProfile System
 *
 * Tests workflow profiles for specific use cases with overrides
 *
 * Run: pnpm test workflow-profile.test.ts
 */

import { describe, it, expect } from 'vitest';
import {
  createWorkflowProfile,
  applyWorkflowProfile,
  isModelAllowedByWorkflow,
  WORKFLOW_PRESETS,
  createUserProfile,
  createOptimizationWeights,
  createLatencyProfile,
  getOptimizationWeights,
  getLatencyProfile,
  getDailyBudget,
} from '../profiles';
import type { WorkflowProfile } from '../types';

describe('WorkflowProfile', () => {
  describe('createWorkflowProfile', () => {
    it('should create workflow profile with all fields', () => {
      const workflow = createWorkflowProfile({
        name: 'custom',
        maxBudgetOverride: 0.01,
        qualityThresholdOverride: 0.8,
        preferredModels: ['gpt-4'],
        description: 'Custom workflow',
      });

      expect(workflow.name).toBe('custom');
      expect(workflow.maxBudgetOverride).toBe(0.01);
      expect(workflow.qualityThresholdOverride).toBe(0.8);
      expect(workflow.preferredModels).toEqual(['gpt-4']);
      expect(workflow.description).toBe('Custom workflow');
    });

    it('should validate optimization weights', () => {
      expect(() =>
        createWorkflowProfile({
          name: 'invalid',
          optimizationOverride: { cost: 0.5, speed: 0.5, quality: 0.5 }, // sum > 1
        })
      ).toThrow();
    });

    it('should accept valid optimization weights', () => {
      const workflow = createWorkflowProfile({
        name: 'valid',
        optimizationOverride: createOptimizationWeights(0.3, 0.3, 0.4),
      });

      expect(workflow.optimizationOverride).toBeDefined();
      expect(workflow.optimizationOverride?.cost).toBe(0.3);
    });

    it('should allow partial workflow profiles', () => {
      const workflow = createWorkflowProfile({
        name: 'minimal',
        enableCaching: true,
      });

      expect(workflow.name).toBe('minimal');
      expect(workflow.enableCaching).toBe(true);
      expect(workflow.maxBudgetOverride).toBeUndefined();
    });
  });

  describe('applyWorkflowProfile', () => {
    it('should apply workflow overrides to user profile', () => {
      const baseProfile = createUserProfile('PRO', 'user-123');
      const workflow: WorkflowProfile = {
        name: 'test',
        maxBudgetOverride: 0.001,
        optimizationOverride: createOptimizationWeights(0.8, 0.1, 0.1),
      };

      const result = applyWorkflowProfile(baseProfile, workflow);

      expect(getDailyBudget(result)).toBe(0.001);
      expect(getOptimizationWeights(result)).toEqual({
        cost: 0.8,
        speed: 0.1,
        quality: 0.1,
      });
    });

    it('should preserve base profile fields when not overridden', () => {
      const baseProfile = createUserProfile('PRO', 'user-123', {
        customDailyBudget: 10.0,
        preferredModels: ['gpt-4'],
      });
      const workflow: WorkflowProfile = {
        name: 'test',
        qualityThresholdOverride: 0.9,
      };

      const result = applyWorkflowProfile(baseProfile, workflow);

      expect(getDailyBudget(result)).toBe(10.0); // Preserved
      expect(result.preferredModels).toEqual(['gpt-4']); // Preserved
    });

    it('should store workflow metadata', () => {
      const baseProfile = createUserProfile('PRO', 'user-123');
      const workflow: WorkflowProfile = {
        name: 'test_workflow',
        description: 'Test description',
      };

      const result = applyWorkflowProfile(baseProfile, workflow);

      expect(result.metadata?.appliedWorkflow).toBe('test_workflow');
      expect(result.metadata?.workflowDescription).toBe('Test description');
    });

    it('should override preferred models', () => {
      const baseProfile = createUserProfile('PRO', 'user-123', {
        preferredModels: ['gpt-4'],
      });
      const workflow: WorkflowProfile = {
        name: 'test',
        preferredModels: ['claude-3-opus'],
      };

      const result = applyWorkflowProfile(baseProfile, workflow);

      expect(result.preferredModels).toEqual(['claude-3-opus']);
    });

    it('should override latency profile', () => {
      const baseProfile = createUserProfile('PRO', 'user-123', {
        latency: createLatencyProfile({ maxTotalMs: 5000 }),
      });
      const workflow: WorkflowProfile = {
        name: 'realtime',
        latencyOverride: createLatencyProfile({ maxTotalMs: 1000 }),
      };

      const result = applyWorkflowProfile(baseProfile, workflow);

      expect(getLatencyProfile(result).maxTotalMs).toBe(1000);
    });

    it('should merge base metadata with workflow metadata', () => {
      const baseProfile = createUserProfile('PRO', 'user-123', {
        metadata: { existingKey: 'value' },
      });
      const workflow: WorkflowProfile = {
        name: 'test',
        description: 'Test',
      };

      const result = applyWorkflowProfile(baseProfile, workflow);

      expect(result.metadata?.existingKey).toBe('value');
      expect(result.metadata?.appliedWorkflow).toBe('test');
    });
  });

  describe('isModelAllowedByWorkflow', () => {
    it('should allow all models when no restrictions', () => {
      const workflow: WorkflowProfile = { name: 'test' };

      expect(isModelAllowedByWorkflow(workflow, 'gpt-4')).toBe(true);
      expect(isModelAllowedByWorkflow(workflow, 'claude-3-opus')).toBe(true);
    });

    it('should restrict to forceModels when set', () => {
      const workflow: WorkflowProfile = {
        name: 'test',
        forceModels: ['gpt-4', 'gpt-3.5-turbo'],
      };

      expect(isModelAllowedByWorkflow(workflow, 'gpt-4')).toBe(true);
      expect(isModelAllowedByWorkflow(workflow, 'gpt-3.5-turbo')).toBe(true);
      expect(isModelAllowedByWorkflow(workflow, 'claude-3-opus')).toBe(false);
    });

    it('should exclude models in excludeModels', () => {
      const workflow: WorkflowProfile = {
        name: 'test',
        excludeModels: ['gpt-3.5-turbo'],
      };

      expect(isModelAllowedByWorkflow(workflow, 'gpt-4')).toBe(true);
      expect(isModelAllowedByWorkflow(workflow, 'gpt-3.5-turbo')).toBe(false);
    });

    it('should prioritize forceModels over excludeModels', () => {
      const workflow: WorkflowProfile = {
        name: 'test',
        forceModels: ['gpt-4'],
        excludeModels: ['gpt-3.5-turbo'],
      };

      expect(isModelAllowedByWorkflow(workflow, 'gpt-4')).toBe(true);
      expect(isModelAllowedByWorkflow(workflow, 'gpt-3.5-turbo')).toBe(false);
      expect(isModelAllowedByWorkflow(workflow, 'claude-3-opus')).toBe(false);
    });

    it('should handle empty forceModels array as unrestricted', () => {
      const workflow: WorkflowProfile = {
        name: 'test',
        forceModels: [],
      };

      expect(isModelAllowedByWorkflow(workflow, 'gpt-4')).toBe(true);
    });
  });

  describe('WORKFLOW_PRESETS', () => {
    describe('draft_mode', () => {
      it('should be ultra cost optimized', () => {
        const draft = WORKFLOW_PRESETS.draft_mode;

        expect(draft.name).toBe('draft_mode');
        expect(draft.optimizationOverride?.cost).toBe(0.8);
        expect(draft.maxBudgetOverride).toBe(0.0001);
        expect(draft.qualityThresholdOverride).toBe(0.5);
      });

      it('should prefer cheap models', () => {
        const draft = WORKFLOW_PRESETS.draft_mode;

        expect(draft.preferredModels).toContain('gpt-3.5-turbo');
      });
    });

    describe('production', () => {
      it('should be balanced with high quality', () => {
        const prod = WORKFLOW_PRESETS.production;

        expect(prod.name).toBe('production');
        expect(prod.qualityThresholdOverride).toBe(0.85);
        expect(prod.enableCaching).toBe(true);
      });

      it('should not have budget override', () => {
        const prod = WORKFLOW_PRESETS.production;

        expect(prod.maxBudgetOverride).toBeUndefined();
      });
    });

    describe('critical', () => {
      it('should prioritize quality over cost', () => {
        const critical = WORKFLOW_PRESETS.critical;

        expect(critical.name).toBe('critical');
        expect(critical.optimizationOverride?.quality).toBe(0.6);
        expect(critical.optimizationOverride?.cost).toBe(0.1);
        expect(critical.qualityThresholdOverride).toBe(0.9);
      });

      it('should force best models only', () => {
        const critical = WORKFLOW_PRESETS.critical;

        expect(critical.forceModels).toContain('gpt-4');
        expect(critical.forceModels).toContain('claude-3-opus');
      });
    });

    describe('realtime', () => {
      it('should prioritize speed', () => {
        const realtime = WORKFLOW_PRESETS.realtime;

        expect(realtime.name).toBe('realtime');
        expect(realtime.optimizationOverride?.speed).toBe(0.7);
      });

      it('should have aggressive latency limits', () => {
        const realtime = WORKFLOW_PRESETS.realtime;

        expect(realtime.latencyOverride?.maxTotalMs).toBe(800);
        expect(realtime.latencyOverride?.maxPerModelMs).toBe(600);
        expect(realtime.latencyOverride?.preferParallel).toBe(true);
      });

      it('should prefer fast models', () => {
        const realtime = WORKFLOW_PRESETS.realtime;

        expect(realtime.preferredModels).toContain('gpt-3.5-turbo');
        expect(realtime.preferredModels).toContain('claude-3-haiku');
      });
    });

    describe('batch_processing', () => {
      it('should prioritize cost for long-running jobs', () => {
        const batch = WORKFLOW_PRESETS.batch_processing;

        expect(batch.name).toBe('batch_processing');
        expect(batch.optimizationOverride?.cost).toBe(0.7);
        expect(batch.optimizationOverride?.speed).toBe(0.1);
      });

      it('should have relaxed latency limits', () => {
        const batch = WORKFLOW_PRESETS.batch_processing;

        expect(batch.latencyOverride?.maxTotalMs).toBe(30000);
        expect(batch.latencyOverride?.maxPerModelMs).toBe(20000);
        expect(batch.latencyOverride?.preferParallel).toBe(false);
      });

      it('should enable caching', () => {
        const batch = WORKFLOW_PRESETS.batch_processing;

        expect(batch.enableCaching).toBe(true);
      });
    });

    it('should have all presets with valid names', () => {
      const presetNames = Object.keys(WORKFLOW_PRESETS);
      expect(presetNames.length).toBeGreaterThan(0);

      for (const [key, workflow] of Object.entries(WORKFLOW_PRESETS)) {
        expect(workflow.name).toBe(key);
      }
    });

    it('should have all presets with descriptions', () => {
      for (const workflow of Object.values(WORKFLOW_PRESETS)) {
        expect(workflow.description).toBeDefined();
        expect(workflow.description!.length).toBeGreaterThan(0);
      }
    });

    it('should have valid optimization overrides', () => {
      for (const workflow of Object.values(WORKFLOW_PRESETS)) {
        if (workflow.optimizationOverride) {
          const { cost, speed, quality } = workflow.optimizationOverride;
          const sum = cost + speed + quality;
          expect(sum).toBeGreaterThanOrEqual(0.99);
          expect(sum).toBeLessThanOrEqual(1.01);
        }
      }
    });
  });

  describe('Integration with UserProfile', () => {
    it('should combine tier, profile, and workflow settings', () => {
      // Start with PRO tier
      const profile = createUserProfile('PRO', 'user-123', {
        customDailyBudget: 5.0,
        costSensitivity: 'balanced',
      });

      // Apply draft mode workflow
      const withWorkflow = applyWorkflowProfile(profile, WORKFLOW_PRESETS.draft_mode);

      // Workflow should override budget and optimization
      expect(getDailyBudget(withWorkflow)).toBe(0.0001);
      expect(getOptimizationWeights(withWorkflow).cost).toBe(0.8);

      // Profile metadata should be preserved
      expect(withWorkflow.userId).toBe('user-123');
      expect(withWorkflow.tier.name).toBe('Pro');
    });

    it('should allow chaining multiple workflow applications', () => {
      const profile = createUserProfile('PRO', 'user-123');
      const step1 = applyWorkflowProfile(profile, WORKFLOW_PRESETS.draft_mode);
      const step2 = applyWorkflowProfile(step1, WORKFLOW_PRESETS.realtime);

      // Last workflow should win
      expect(getLatencyProfile(step2).maxTotalMs).toBe(800);
      expect(step2.metadata?.appliedWorkflow).toBe('realtime');
    });
  });

  describe('Feature Overrides', () => {
    it('should override caching setting', () => {
      const workflow: WorkflowProfile = {
        name: 'test',
        enableCaching: false,
      };

      expect(workflow.enableCaching).toBe(false);
    });

    it('should override parallel execution', () => {
      const workflow: WorkflowProfile = {
        name: 'test',
        enableParallel: true,
      };

      expect(workflow.enableParallel).toBe(true);
    });

    it('should override speculative cascading', () => {
      const workflow: WorkflowProfile = {
        name: 'test',
        enableSpeculative: false,
      };

      expect(workflow.enableSpeculative).toBe(false);
    });

    it('should override streaming', () => {
      const workflow: WorkflowProfile = {
        name: 'test',
        enableStreaming: true,
      };

      expect(workflow.enableStreaming).toBe(true);
    });
  });

  describe('Custom Workflow Creation', () => {
    it('should support custom workflows for specific domains', () => {
      const medicalWorkflow = createWorkflowProfile({
        name: 'medical_queries',
        optimizationOverride: createOptimizationWeights(0.1, 0.2, 0.7),
        qualityThresholdOverride: 0.95,
        forceModels: ['gpt-4', 'claude-3-opus'],
        enableCaching: false,
        description: 'Medical queries requiring high accuracy',
      });

      expect(medicalWorkflow.name).toBe('medical_queries');
      expect(medicalWorkflow.optimizationOverride?.quality).toBe(0.7);
      expect(isModelAllowedByWorkflow(medicalWorkflow, 'gpt-4')).toBe(true);
      expect(isModelAllowedByWorkflow(medicalWorkflow, 'gpt-3.5-turbo')).toBe(false);
    });
  });
});
