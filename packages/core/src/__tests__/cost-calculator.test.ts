/**
 * Cost Calculator Tests
 *
 * Comprehensive test suite for CostCalculator class.
 * Validates cost calculations, token estimation, and breakdown accuracy.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { CostCalculator, calculateCascadeCost } from '../telemetry/cost-calculator';
import type { CascadeResult } from '../result';

describe('CostCalculator', () => {
  let calculator: CostCalculator;

  beforeEach(() => {
    calculator = new CostCalculator();
  });

  describe('estimateTokens', () => {
    it('should estimate tokens from text', () => {
      const text = 'What is TypeScript?';
      const tokens = CostCalculator.estimateTokens(text);

      // "What is TypeScript?" = 3 words
      // 3 words * 1.3 = 3.9 ≈ 4 tokens
      expect(tokens).toBe(4);
    });

    it('should handle empty text', () => {
      expect(CostCalculator.estimateTokens('')).toBe(0);
      expect(CostCalculator.estimateTokens('   ')).toBe(0);
    });

    it('should handle single word', () => {
      const tokens = CostCalculator.estimateTokens('Hello');
      // 1 word * 1.3 = 1.3 ≈ 1 token
      expect(tokens).toBe(1);
    });

    it('should handle multiple words', () => {
      const text = 'Explain quantum computing in simple terms';
      const tokens = CostCalculator.estimateTokens(text);

      // 6 words * 1.3 = 7.8 ≈ 8 tokens
      expect(tokens).toBe(8);
    });

    it('should handle text with multiple spaces', () => {
      const text = 'Hello    world    test';
      const tokens = CostCalculator.estimateTokens(text);

      // 3 words * 1.3 = 3.9 ≈ 4 tokens
      expect(tokens).toBe(4);
    });

    it('should return at least 1 token for non-empty text', () => {
      const tokens = CostCalculator.estimateTokens('a');
      expect(tokens).toBeGreaterThanOrEqual(1);
    });
  });

  describe('calculate - draft accepted', () => {
    it('should calculate costs for accepted draft', () => {
      const result: CascadeResult = {
        content: 'TypeScript is a superset of JavaScript...',
        modelUsed: 'gpt-4o-mini',
        totalCost: 0.0001,
        latencyMs: 250,
        complexity: 'simple',
        cascaded: true,
        draftAccepted: true,
        routingStrategy: 'cascade',
        reason: 'Quality check passed',
        hasToolCalls: false,
        draftCost: 0.0001,
        verifierCost: 0,
        costSaved: 0.0009,
        savingsPercentage: 90,
        draftModel: 'gpt-4o-mini',
        verifierModel: 'gpt-4o',
        responseLength: 150,
      };

      const breakdown = calculator.calculate(result, 'What is TypeScript?');

      expect(breakdown.draftCost).toBe(0.0001);
      expect(breakdown.verifierCost).toBe(0);
      expect(breakdown.totalCost).toBe(0.0001);
      expect(breakdown.draftAccepted).toBe(true);
      expect(breakdown.wasCascaded).toBe(true);
      expect(breakdown.costSaved).toBeGreaterThan(0);
      expect(breakdown.savingsPercentage).toBeGreaterThan(0);
      expect(breakdown.metadata).toHaveProperty('draftModel', 'gpt-4o-mini');
      expect(breakdown.metadata).toHaveProperty('verifierModel', 'gpt-4o');
      expect(breakdown.metadata).toHaveProperty('complexity', 'simple');
    });

    it('should estimate tokens when draft accepted', () => {
      const result: CascadeResult = {
        content: 'Response',
        modelUsed: 'gpt-4o-mini',
        totalCost: 0.0001,
        latencyMs: 250,
        complexity: 'simple',
        cascaded: true,
        draftAccepted: true,
        routingStrategy: 'cascade',
        reason: 'Quality check passed',
        hasToolCalls: false,
        draftCost: 0.0001,
        responseLength: 100,
      };

      const queryText = 'What is TypeScript?';
      const breakdown = calculator.calculate(result, queryText);

      // Should include query tokens + estimated response tokens
      expect(breakdown.draftTokens).toBeGreaterThan(0);
      expect(breakdown.verifierTokens).toBe(0);
      expect(breakdown.totalTokens).toBe(breakdown.draftTokens);
      expect(breakdown.metadata).toHaveProperty('queryInputTokens');
    });
  });

  describe('calculate - draft rejected', () => {
    it('should calculate costs for rejected draft', () => {
      const result: CascadeResult = {
        content: 'Detailed quantum computing explanation...',
        modelUsed: 'gpt-4o',
        totalCost: 0.0015,
        latencyMs: 500,
        complexity: 'hard',
        cascaded: true,
        draftAccepted: false,
        routingStrategy: 'cascade',
        reason: 'Quality check failed - escalated',
        hasToolCalls: false,
        draftCost: 0.0001,
        verifierCost: 0.0014,
        costSaved: -0.0001, // Negative = wasted draft cost
        savingsPercentage: -7.14,
        draftModel: 'gpt-4o-mini',
        verifierModel: 'gpt-4o',
        draftResponse: 'Brief response',
        verifierResponse: 'Detailed quantum explanation...',
        rejectionReason: 'Quality score 0.5 below threshold 0.64',
      };

      const breakdown = calculator.calculate(result, 'Explain quantum computing');

      expect(breakdown.draftCost).toBe(0.0001);
      expect(breakdown.verifierCost).toBe(0.0014);
      expect(breakdown.totalCost).toBe(0.0015);
      expect(breakdown.draftAccepted).toBe(false);
      expect(breakdown.wasCascaded).toBe(true);
      expect(breakdown.costSaved).toBeLessThan(0); // Negative savings
      expect(breakdown.metadata).toHaveProperty('rejectionReason');
    });

    it('should track both draft and verifier tokens when rejected', () => {
      const result: CascadeResult = {
        content: 'Verifier response',
        modelUsed: 'gpt-4o',
        totalCost: 0.0015,
        latencyMs: 500,
        complexity: 'hard',
        cascaded: true,
        draftAccepted: false,
        routingStrategy: 'cascade',
        reason: 'Escalated',
        hasToolCalls: false,
        draftCost: 0.0001,
        verifierCost: 0.0014,
        draftResponse: 'Draft response text',
        verifierResponse: 'Verifier response text',
      };

      const breakdown = calculator.calculate(result, 'Complex query');

      expect(breakdown.draftTokens).toBeGreaterThan(0);
      expect(breakdown.verifierTokens).toBeGreaterThan(0);
      expect(breakdown.totalTokens).toBe(
        breakdown.draftTokens + breakdown.verifierTokens
      );
    });
  });

  describe('calculateFromTokens', () => {
    it('should calculate costs from token counts - draft accepted', async () => {
      const breakdown = await calculator.calculateFromTokens({
        draftOutputTokens: 150,
        verifierOutputTokens: 0,
        queryInputTokens: 20,
        draftAccepted: true,
        draftModel: 'gpt-4o-mini',
        verifierModel: 'gpt-4o',
        draftProvider: 'openai',
        verifierProvider: 'openai',
      });

      expect(breakdown.draftCost).toBeGreaterThan(0);
      expect(breakdown.verifierCost).toBe(0);
      expect(breakdown.totalCost).toBe(breakdown.draftCost);
      expect(breakdown.draftAccepted).toBe(true);
      expect(breakdown.wasCascaded).toBe(true);
      expect(breakdown.draftTokens).toBe(170); // 20 input + 150 output
      expect(breakdown.verifierTokens).toBe(0);
      expect(breakdown.totalTokens).toBe(170);
      expect(breakdown.costSaved).toBeGreaterThan(0); // Should save money
      expect(breakdown.savingsPercentage).toBeGreaterThan(0);
    });

    it('should calculate costs from token counts - draft rejected', async () => {
      const breakdown = await calculator.calculateFromTokens({
        draftOutputTokens: 150,
        verifierOutputTokens: 200,
        queryInputTokens: 20,
        draftAccepted: false,
        draftModel: 'gpt-4o-mini',
        verifierModel: 'gpt-4o',
        draftProvider: 'openai',
        verifierProvider: 'openai',
      });

      expect(breakdown.draftCost).toBeGreaterThan(0);
      expect(breakdown.verifierCost).toBeGreaterThan(0);
      expect(breakdown.totalCost).toBe(breakdown.draftCost + breakdown.verifierCost);
      expect(breakdown.draftAccepted).toBe(false);
      expect(breakdown.wasCascaded).toBe(true);
      expect(breakdown.draftTokens).toBe(170); // 20 input + 150 output
      expect(breakdown.verifierTokens).toBeGreaterThan(0); // Includes context + output
      expect(breakdown.costSaved).toBeLessThan(0); // Wasted draft cost
      expect(breakdown.savingsPercentage).toBeLessThan(0);
    });

    it('should handle zero input tokens', async () => {
      const breakdown = await calculator.calculateFromTokens({
        draftOutputTokens: 100,
        verifierOutputTokens: 0,
        queryInputTokens: 0,
        draftAccepted: true,
        draftModel: 'gpt-4o-mini',
        verifierModel: 'gpt-4o',
      });

      expect(breakdown.draftTokens).toBe(100);
      expect(breakdown.totalCost).toBeGreaterThan(0);
      expect(breakdown.metadata).toHaveProperty('queryInputTokens', 0);
    });

    it('should include metadata', async () => {
      const breakdown = await calculator.calculateFromTokens({
        draftOutputTokens: 150,
        verifierOutputTokens: 0,
        queryInputTokens: 20,
        draftAccepted: true,
        draftModel: 'gpt-4o-mini',
        verifierModel: 'gpt-4o',
        draftProvider: 'openai',
        verifierProvider: 'openai',
      });

      expect(breakdown.metadata).toHaveProperty('draftModel', 'gpt-4o-mini');
      expect(breakdown.metadata).toHaveProperty('verifierModel', 'gpt-4o');
      expect(breakdown.metadata).toHaveProperty('draftProvider', 'openai');
      expect(breakdown.metadata).toHaveProperty('verifierProvider', 'openai');
      expect(breakdown.metadata).toHaveProperty('queryInputTokens', 20);
      expect(breakdown.metadata).toHaveProperty('draftOutputTokens', 150);
      expect(breakdown.metadata).toHaveProperty('verifierOutputTokens', 0);
      expect(breakdown.metadata).toHaveProperty('timestamp');
    });

    it('should handle provider prefixes correctly', async () => {
      const breakdown = await calculator.calculateFromTokens({
        draftOutputTokens: 100,
        verifierOutputTokens: 0,
        queryInputTokens: 10,
        draftAccepted: true,
        draftModel: 'claude-3-5-haiku-20241022',
        verifierModel: 'claude-3-5-sonnet-20241022',
        draftProvider: 'anthropic',
        verifierProvider: 'anthropic',
      });

      // Should calculate costs successfully with provider prefixes
      expect(breakdown.totalCost).toBeGreaterThan(0);
      expect(breakdown.metadata).toHaveProperty('draftProvider', 'anthropic');
    });
  });

  describe('calculateCascadeCost - convenience function', () => {
    it('should work as convenience wrapper', () => {
      const result: CascadeResult = {
        content: 'Response',
        modelUsed: 'gpt-4o-mini',
        totalCost: 0.0001,
        latencyMs: 250,
        complexity: 'simple',
        cascaded: true,
        draftAccepted: true,
        routingStrategy: 'cascade',
        reason: 'Quality passed',
        hasToolCalls: false,
        draftCost: 0.0001,
        responseLength: 100,
      };

      const breakdown = calculateCascadeCost(result, 'Test query');

      expect(breakdown).toBeDefined();
      expect(breakdown.totalCost).toBe(0.0001);
      expect(breakdown.wasCascaded).toBe(true);
    });
  });

  describe('edge cases', () => {
    it('should handle missing optional fields', () => {
      const result: CascadeResult = {
        content: 'Response',
        modelUsed: 'gpt-4o-mini',
        totalCost: 0.0001,
        latencyMs: 250,
        complexity: 'simple',
        cascaded: true,
        draftAccepted: true,
        routingStrategy: 'cascade',
        reason: 'Test',
        hasToolCalls: false,
        // Missing many optional fields
      };

      const breakdown = calculator.calculate(result);

      expect(breakdown).toBeDefined();
      expect(breakdown.totalCost).toBeGreaterThanOrEqual(0);
    });

    it('should handle zero costs', () => {
      const result: CascadeResult = {
        content: 'Response',
        modelUsed: 'ollama',
        totalCost: 0,
        latencyMs: 250,
        complexity: 'simple',
        cascaded: false,
        draftAccepted: true,
        routingStrategy: 'direct',
        reason: 'Local model',
        hasToolCalls: false,
        draftCost: 0,
        verifierCost: 0,
      };

      const breakdown = calculator.calculate(result);

      expect(breakdown.totalCost).toBe(0);
      expect(breakdown.costSaved).toBe(0);
      expect(breakdown.savingsPercentage).toBe(0);
    });

    it('should handle very long responses', () => {
      const longText = 'word '.repeat(1000); // 1000 words
      const tokens = CostCalculator.estimateTokens(longText);

      // 1000 words * 1.3 = 1300 tokens
      expect(tokens).toBe(1300);
    });
  });

  describe('cost breakdown structure', () => {
    it('should have all required fields', async () => {
      const breakdown = await calculator.calculateFromTokens({
        draftOutputTokens: 100,
        verifierOutputTokens: 0,
        queryInputTokens: 10,
        draftAccepted: true,
        draftModel: 'gpt-4o-mini',
        verifierModel: 'gpt-4o',
      });

      // Verify all required fields present
      expect(breakdown).toHaveProperty('draftCost');
      expect(breakdown).toHaveProperty('verifierCost');
      expect(breakdown).toHaveProperty('totalCost');
      expect(breakdown).toHaveProperty('costSaved');
      expect(breakdown).toHaveProperty('bigonlyCost');
      expect(breakdown).toHaveProperty('savingsPercentage');
      expect(breakdown).toHaveProperty('draftTokens');
      expect(breakdown).toHaveProperty('verifierTokens');
      expect(breakdown).toHaveProperty('totalTokens');
      expect(breakdown).toHaveProperty('wasCascaded');
      expect(breakdown).toHaveProperty('draftAccepted');
      expect(breakdown).toHaveProperty('metadata');
    });

    it('should calculate savings percentage correctly', async () => {
      const breakdown = await calculator.calculateFromTokens({
        draftOutputTokens: 150,
        verifierOutputTokens: 0,
        queryInputTokens: 20,
        draftAccepted: true,
        draftModel: 'gpt-4o-mini',
        verifierModel: 'gpt-4o',
      });

      // Savings % = (costSaved / bigonlyCost) * 100
      const expectedSavings = (breakdown.costSaved / breakdown.bigonlyCost) * 100;
      expect(breakdown.savingsPercentage).toBeCloseTo(expectedSavings, 1);
      expect(breakdown.savingsPercentage).toBeGreaterThan(50); // Should save significant money
    });

    it('should show negative savings when draft rejected', async () => {
      const breakdown = await calculator.calculateFromTokens({
        draftOutputTokens: 100,
        verifierOutputTokens: 150,
        queryInputTokens: 10,
        draftAccepted: false,
        draftModel: 'gpt-4o-mini',
        verifierModel: 'gpt-4o',
      });

      expect(breakdown.costSaved).toBeLessThan(0);
      expect(breakdown.savingsPercentage).toBeLessThan(0);
      expect(breakdown.bigonlyCost).toBe(breakdown.verifierCost);
    });
  });
});
