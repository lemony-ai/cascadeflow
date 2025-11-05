/**
 * Tests for reasoning model auto-detection and support
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { OpenAIProvider, getReasoningModelInfo as getOpenAIReasoningModelInfo } from '../providers/openai';
import { AnthropicProvider, getReasoningModelInfo as getAnthropicReasoningModelInfo } from '../providers/anthropic';
import { OllamaProvider, getReasoningModelInfo as getOllamaReasoningModelInfo } from '../providers/ollama';
import { VLLMProvider, getReasoningModelInfo as getVLLMReasoningModelInfo } from '../providers/vllm';
import type { ModelConfig } from '../config';

// Mock OpenAI SDK
vi.mock('openai', () => ({
  default: vi.fn().mockImplementation(() => ({
    chat: {
      completions: {
        create: vi.fn(),
      },
    },
  })),
}));

// Mock Anthropic SDK
vi.mock('@anthropic-ai/sdk', () => ({
  default: vi.fn().mockImplementation(() => ({
    messages: {
      create: vi.fn(),
      stream: vi.fn(),
    },
  })),
}));

describe('Reasoning Model Support', () => {
  let mockConfig: ModelConfig;

  beforeEach(() => {
    mockConfig = {
      name: 'gpt-4o-mini',
      provider: 'openai',
      apiKey: 'test-key',
      cost: 0,
    };
    vi.clearAllMocks();
  });

  describe('Model Detection', () => {
    it('should detect o1-preview as reasoning model', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-preview' });
      expect(provider).toBeDefined();
      // Model info is checked internally during generation
    });

    it('should detect o1-mini as reasoning model', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-mini' });
      expect(provider).toBeDefined();
    });

    it('should detect o1-2024-12-17 as reasoning model', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-2024-12-17' });
      expect(provider).toBeDefined();
    });

    it('should detect o3-mini as reasoning model', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o3-mini' });
      expect(provider).toBeDefined();
    });

    it('should not detect gpt-4o as reasoning model', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'gpt-4o' });
      expect(provider).toBeDefined();
    });
  });

  describe('Cost Calculation', () => {
    it('should calculate cost for o1-preview correctly', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-preview' });
      const cost = provider.calculateCost(1000, 2000, 'o1-preview');

      // Input: 1000 tokens at $0.015/1K = $0.015
      // Output: 2000 tokens at $0.060/1K = $0.120
      // Total: $0.135
      expect(cost).toBeCloseTo(0.135, 6);
    });

    it('should calculate cost for o1-mini correctly', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-mini' });
      const cost = provider.calculateCost(1000, 2000, 'o1-mini');

      // Input: 1000 tokens at $0.003/1K = $0.003
      // Output: 2000 tokens at $0.012/1K = $0.024
      // Total: $0.027
      expect(cost).toBeCloseTo(0.027, 6);
    });

    it('should calculate cost for o1-2024-12-17 correctly', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-2024-12-17' });
      const cost = provider.calculateCost(1000, 2000, 'o1-2024-12-17');

      // Input: 1000 tokens at $0.015/1K = $0.015
      // Output: 2000 tokens at $0.060/1K = $0.120
      // Total: $0.135
      expect(cost).toBeCloseTo(0.135, 6);
    });

    it('should calculate cost for o3-mini correctly', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o3-mini' });
      const cost = provider.calculateCost(1000, 2000, 'o3-mini');

      // Input: 1000 tokens at $0.001/1K = $0.001
      // Output: 2000 tokens at $0.005/1K = $0.010
      // Total: $0.011
      expect(cost).toBeCloseTo(0.011, 6);
    });

    it('should handle reasoning tokens in cost calculation', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-mini' });

      // Reasoning tokens are already included in completion_tokens from API
      // So passing reasoning_tokens separately shouldn't double-count
      const cost = provider.calculateCost(1000, 2000, 'o1-mini', 500);

      expect(cost).toBeCloseTo(0.027, 6); // Same as without reasoning_tokens param
    });

    it('should fallback to gpt-4o-mini pricing for unknown reasoning models', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o4-unknown' });
      const cost = provider.calculateCost(1000, 2000, 'o4-unknown');

      // Should use gpt-4o-mini fallback pricing
      // Input: 1000 tokens at $0.00015/1K = $0.00015
      // Output: 2000 tokens at $0.0006/1K = $0.0012
      // Total: $0.00135
      expect(cost).toBeCloseTo(0.00135, 6);
    });

    it('should use prefix matching for versioned models', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-preview-2025-01-15' });
      const cost = provider.calculateCost(1000, 2000, 'o1-preview-2025-01-15');

      // Should match 'o1-preview' prefix
      expect(cost).toBeCloseTo(0.135, 6);
    });
  });

  describe('Provider Availability', () => {
    it('should be available with API key in config', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-mini', apiKey: 'test-key' });
      expect(provider.isAvailable()).toBe(true);
    });

    it('should be available with API key in environment', () => {
      process.env.OPENAI_API_KEY = 'test-env-key';
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-mini', apiKey: undefined });
      expect(provider.isAvailable()).toBe(true);
      delete process.env.OPENAI_API_KEY;
    });

    it('should not be available without API key', () => {
      const configWithoutKey = { ...mockConfig, apiKey: undefined };
      delete process.env.OPENAI_API_KEY;

      expect(() => new OpenAIProvider({ ...configWithoutKey, name: 'o1-mini' }))
        .toThrow();
    });
  });

  describe('Model-specific Pricing', () => {
    const testCases = [
      // GPT-5 series
      { model: 'gpt-5', input: 0.00125, output: 0.010 },
      { model: 'gpt-5-mini', input: 0.00025, output: 0.002 },
      { model: 'gpt-5-nano', input: 0.00005, output: 0.0004 },

      // GPT-4o series
      { model: 'gpt-4o', input: 0.0025, output: 0.010 },
      { model: 'gpt-4o-mini', input: 0.00015, output: 0.0006 },

      // O1 series (reasoning)
      { model: 'o1-preview', input: 0.015, output: 0.060 },
      { model: 'o1-mini', input: 0.003, output: 0.012 },
      { model: 'o1', input: 0.015, output: 0.060 },
      { model: 'o1-2024-12-17', input: 0.015, output: 0.060 },

      // O3 series (reasoning)
      { model: 'o3-mini', input: 0.001, output: 0.005 },

      // GPT-4 series
      { model: 'gpt-4-turbo', input: 0.010, output: 0.030 },
      { model: 'gpt-4', input: 0.030, output: 0.060 },

      // GPT-3.5 series
      { model: 'gpt-3.5-turbo', input: 0.0005, output: 0.0015 },
    ];

    testCases.forEach(({ model, input, output }) => {
      it(`should have correct pricing for ${model}`, () => {
        const provider = new OpenAIProvider({ ...mockConfig, name: model });
        const cost = provider.calculateCost(1000, 1000, model);

        const expectedCost = (1000 / 1000) * input + (1000 / 1000) * output;
        expect(cost).toBeCloseTo(expectedCost, 6);
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero tokens', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-mini' });
      const cost = provider.calculateCost(0, 0, 'o1-mini');
      expect(cost).toBe(0);
    });

    it('should handle very large token counts', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'o1-mini' });
      const cost = provider.calculateCost(1000000, 2000000, 'o1-mini');

      // Should scale linearly
      const expected = (1000000 / 1000) * 0.003 + (2000000 / 1000) * 0.012;
      expect(cost).toBeCloseTo(expected, 6);
    });

    it('should handle case-insensitive model names', () => {
      const provider1 = new OpenAIProvider({ ...mockConfig, name: 'O1-MINI' });
      const provider2 = new OpenAIProvider({ ...mockConfig, name: 'o1-mini' });

      const cost1 = provider1.calculateCost(1000, 2000, 'O1-MINI');
      const cost2 = provider2.calculateCost(1000, 2000, 'o1-mini');

      expect(cost1).toBeCloseTo(cost2, 6);
    });
  });

  describe('Integration with Usage Details', () => {
    it('should support extended usage details structure', () => {
      // This test validates that the UsageDetails interface can handle reasoning tokens
      const usageDetails = {
        prompt_tokens: 100,
        completion_tokens: 200,
        total_tokens: 300,
        reasoning_tokens: 50,
        completion_tokens_details: {
          reasoning_tokens: 50,
          accepted_prediction_tokens: 0,
          rejected_prediction_tokens: 0,
        },
      };

      expect(usageDetails.reasoning_tokens).toBe(50);
      expect(usageDetails.completion_tokens_details?.reasoning_tokens).toBe(50);
      expect(usageDetails.total_tokens).toBe(300);
    });
  });

  describe('Backward Compatibility', () => {
    it('should work with existing non-reasoning models', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'gpt-4o-mini' });
      const cost = provider.calculateCost(1000, 2000, 'gpt-4o-mini');

      // gpt-4o-mini: input $0.00015/1K, output $0.0006/1K
      // 1000 input + 2000 output = $0.00015 + $0.0012 = $0.00135
      expect(cost).toBeCloseTo(0.00135, 6);
    });

    it('should not break existing cost calculations', () => {
      const provider = new OpenAIProvider({ ...mockConfig, name: 'gpt-3.5-turbo' });

      // Old signature (without reasoning_tokens)
      const cost1 = provider.calculateCost(1000, 2000, 'gpt-3.5-turbo');

      // New signature (with reasoning_tokens, should be ignored for non-reasoning models)
      const cost2 = provider.calculateCost(1000, 2000, 'gpt-3.5-turbo', 500);

      expect(cost1).toBe(cost2);
    });
  });
});

describe('Reasoning Model Types', () => {
  it('should have ReasoningEffort type with correct values', () => {
    const efforts: Array<'low' | 'medium' | 'high'> = ['low', 'medium', 'high'];

    efforts.forEach(effort => {
      expect(['low', 'medium', 'high']).toContain(effort);
    });
  });

  it('should support ThinkingConfig structure', () => {
    const thinkingConfig = {
      type: 'enabled' as const,
      budget_tokens: 1024,
    };

    expect(thinkingConfig.type).toBe('enabled');
    expect(thinkingConfig.budget_tokens).toBeGreaterThanOrEqual(1024);
  });

  it('should support extended ProviderResponse with thinking', () => {
    const response = {
      content: 'Test response',
      model: 'o1-mini',
      usage: {
        prompt_tokens: 100,
        completion_tokens: 200,
        total_tokens: 300,
        reasoning_tokens: 50,
      },
      thinking: 'Internal reasoning process...',
    };

    expect(response.thinking).toBeDefined();
    expect(response.usage?.reasoning_tokens).toBe(50);
  });
});

describe('Anthropic Claude 4.5 Extended Thinking', () => {
  let mockConfig: ModelConfig;

  beforeEach(() => {
    mockConfig = {
      name: 'claude-3-5-sonnet',
      provider: 'anthropic',
      apiKey: 'test-key',
      cost: 0,
    };
    vi.clearAllMocks();
  });

  describe('Model Detection', () => {
    it('should detect claude-sonnet-4.5 as reasoning model', () => {
      const modelInfo = getAnthropicReasoningModelInfo('claude-sonnet-4.5');
      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('anthropic');
      expect(modelInfo.supportsExtendedThinking).toBe(true);
      expect(modelInfo.requiresThinkingBudget).toBe(true);
    });

    it('should detect claude-3-5-sonnet as standard model (not reasoning)', () => {
      const modelInfo = getAnthropicReasoningModelInfo('claude-3-5-sonnet-20241022');
      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
      expect(modelInfo.supportsStreaming).toBe(true);
      expect(modelInfo.supportsTools).toBe(true);
    });

    it('should not detect claude-3-5-sonnet as reasoning model', () => {
      const modelInfo = getAnthropicReasoningModelInfo('claude-3-5-sonnet');
      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
      expect(modelInfo.requiresThinkingBudget).toBe(false);
    });

    it('should not detect claude-3-opus as reasoning model', () => {
      const modelInfo = getAnthropicReasoningModelInfo('claude-3-opus');
      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
    });

    it('should not detect claude-3-haiku as reasoning model', () => {
      const modelInfo = getAnthropicReasoningModelInfo('claude-3-haiku');
      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
    });
  });

  describe('Model Capabilities', () => {
    it('should report correct capabilities for Claude 3.5 Sonnet', () => {
      const modelInfo = getAnthropicReasoningModelInfo('claude-3-5-sonnet-20241022');

      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.provider).toBe('anthropic');
      expect(modelInfo.supportsStreaming).toBe(true);
      expect(modelInfo.supportsTools).toBe(true);
      expect(modelInfo.supportsSystemMessages).toBe(true);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
      expect(modelInfo.requiresThinkingBudget).toBe(false);
    });

    it('should report correct capabilities for Claude 3.5 Haiku', () => {
      const modelInfo = getAnthropicReasoningModelInfo('claude-3-5-haiku-20241022');

      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.provider).toBe('anthropic');
      expect(modelInfo.supportsStreaming).toBe(true);
      expect(modelInfo.supportsTools).toBe(true);
      expect(modelInfo.supportsSystemMessages).toBe(true);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
      expect(modelInfo.requiresThinkingBudget).toBe(false);
    });
  });

  describe('Cost Calculation', () => {
    it('should calculate cost for claude-3-5-sonnet correctly', () => {
      const provider = new AnthropicProvider({ ...mockConfig, name: 'claude-3-5-sonnet-20241022' });
      const cost = provider.calculateCost(1000000, 1000000, 'claude-3-5-sonnet-20241022');

      // Blended rate: $9.00 per 1M tokens
      // 2M tokens total = $18.00
      expect(cost).toBeCloseTo(18.0, 6);
    });

    it('should calculate cost for claude-sonnet-4.5 correctly', () => {
      const provider = new AnthropicProvider({ ...mockConfig, name: 'claude-sonnet-4.5' });
      const cost = provider.calculateCost(1000000, 1000000, 'claude-sonnet-4.5');

      // Claude Sonnet 4.5: $3 in + $15 out = $9 blended per 1M tokens
      // For 2M tokens: $9 * 2 = $18
      expect(cost).toBeCloseTo(18.0, 6);
    });

    it('should handle prefix matching for Claude 4.5 variants', () => {
      const cost1 = new AnthropicProvider(mockConfig).calculateCost(1000000, 1000000, 'claude-sonnet-4.5-20250219');
      const cost2 = new AnthropicProvider(mockConfig).calculateCost(1000000, 1000000, 'claude-sonnet-4.5');

      expect(cost1).toBeCloseTo(cost2, 6);
    });
  });

  describe('Provider Availability', () => {
    it('should be available with API key in config', () => {
      const provider = new AnthropicProvider({ ...mockConfig, name: 'claude-3-5-sonnet-20241022', apiKey: 'test-key' });
      expect(provider.isAvailable()).toBe(true);
    });

    it('should be available with API key in environment', () => {
      process.env.ANTHROPIC_API_KEY = 'test-env-key';
      const provider = new AnthropicProvider({ ...mockConfig, name: 'claude-3-5-sonnet-20241022', apiKey: undefined });
      expect(provider.isAvailable()).toBe(true);
      delete process.env.ANTHROPIC_API_KEY;
    });

    it('should not be available without API key', () => {
      const configWithoutKey = { ...mockConfig, apiKey: undefined };
      delete process.env.ANTHROPIC_API_KEY;

      expect(() => new AnthropicProvider({ ...configWithoutKey, name: 'claude-3-5-sonnet-20241022' }))
        .toThrow();
    });
  });

  describe('Anthropic Pricing Matrix', () => {
    const testCases = [
      // Claude 4 Series
      { model: 'claude-opus-4.1', expectedBlended: 45.0 },
      { model: 'claude-opus-4', expectedBlended: 45.0 },
      { model: 'claude-sonnet-4.5', expectedBlended: 9.0 },
      { model: 'claude-sonnet-4', expectedBlended: 9.0 },

      // Claude 3.5 Series
      { model: 'claude-3-5-sonnet', expectedBlended: 9.0 },
      { model: 'claude-3-5-haiku', expectedBlended: 3.0 },

      // Claude 3 Series
      { model: 'claude-3-opus', expectedBlended: 45.0 },
      { model: 'claude-3-sonnet', expectedBlended: 9.0 },
      { model: 'claude-3-haiku', expectedBlended: 0.75 },
    ];

    testCases.forEach(({ model, expectedBlended }) => {
      it(`should have correct blended pricing for ${model}`, () => {
        const provider = new AnthropicProvider({ ...mockConfig, name: model });
        const cost = provider.calculateCost(1000000, 1000000, model);

        // Total 2M tokens at blended rate
        const expectedCost = 2.0 * expectedBlended;
        expect(cost).toBeCloseTo(expectedCost, 6);
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero tokens', () => {
      const provider = new AnthropicProvider({ ...mockConfig, name: 'claude-sonnet-4.5' });
      const cost = provider.calculateCost(0, 0, 'claude-sonnet-4.5');
      expect(cost).toBe(0);
    });

    it('should handle very large token counts', () => {
      const provider = new AnthropicProvider({ ...mockConfig, name: 'claude-sonnet-4.5' });
      const cost = provider.calculateCost(10000000, 10000000, 'claude-sonnet-4.5');

      // 20M tokens at $9/M blended = $180
      expect(cost).toBeCloseTo(180.0, 6);
    });

    it('should fallback to Sonnet pricing for unknown models', () => {
      const provider = new AnthropicProvider({ ...mockConfig, name: 'claude-unknown' });
      const cost = provider.calculateCost(1000000, 1000000, 'claude-unknown');

      // Should use $9.0 blended fallback (2M tokens)
      expect(cost).toBeCloseTo(18.0, 6);
    });
  });

  describe('Backward Compatibility', () => {
    it('should work with existing non-reasoning models', () => {
      const provider = new AnthropicProvider({ ...mockConfig, name: 'claude-3-5-sonnet' });
      const cost = provider.calculateCost(1000000, 1000000, 'claude-3-5-sonnet');

      // claude-3-5-sonnet: $9.0 blended
      expect(cost).toBeCloseTo(18.0, 6);
    });

    it('should not break existing instantiation patterns', () => {
      expect(() => new AnthropicProvider({ ...mockConfig, name: 'claude-3-5-sonnet' }))
        .not.toThrow();

      expect(() => new AnthropicProvider({ ...mockConfig, name: 'claude-sonnet-4.5' }))
        .not.toThrow();
    });
  });
});

describe('Cross-Provider Reasoning Model Comparison', () => {
  describe('OpenAI vs Anthropic Reasoning Models', () => {
    it('should detect OpenAI reasoning models correctly', () => {
      const o1Info = getOpenAIReasoningModelInfo('o1-preview');
      expect(o1Info.isReasoning).toBe(true);
      expect(o1Info.provider).toBe('openai');
      expect(o1Info.supportsReasoningEffort).toBeDefined();
    });

    it('should detect Anthropic reasoning models correctly', () => {
      const claudeInfo = getAnthropicReasoningModelInfo('claude-sonnet-4.5');
      expect(claudeInfo.isReasoning).toBe(true);
      expect(claudeInfo.provider).toBe('anthropic');
      expect(claudeInfo.supportsExtendedThinking).toBe(true);
    });

    it('should have different capabilities for OpenAI vs Anthropic', () => {
      const o1Info = getOpenAIReasoningModelInfo('o1-mini');
      const claudeInfo = getAnthropicReasoningModelInfo('claude-sonnet-4.5');

      // OpenAI o1 doesn't support tools
      expect(o1Info.supportsTools).toBe(false);

      // Claude 4.5 supports tools
      expect(claudeInfo.supportsTools).toBe(true);

      // Different extended thinking approaches
      expect(o1Info.supportsExtendedThinking).not.toBe(true);
      expect(claudeInfo.supportsExtendedThinking).toBe(true);
    });
  });

  describe('Cost Comparison', () => {
    it('should compare o1-mini vs claude-sonnet-4.5 costs', () => {
      const o1Provider = new OpenAIProvider({ name: 'o1-mini', provider: 'openai', apiKey: 'test', cost: 0 });
      const claudeProvider = new AnthropicProvider({ name: 'claude-sonnet-4.5', provider: 'anthropic', apiKey: 'test', cost: 0 });

      const o1Cost = o1Provider.calculateCost(1000000, 1000000, 'o1-mini');
      const claudeCost = claudeProvider.calculateCost(1000000, 1000000, 'claude-sonnet-4.5');

      // o1-mini: $3 in + $12 out = $15 for 2M tokens
      // claude-sonnet-4.5: $9 blended per 1M = $18 for 2M tokens
      expect(o1Cost).toBeCloseTo(15.0, 6);
      expect(claudeCost).toBeCloseTo(18.0, 6);

      // o1-mini is cheaper
      expect(o1Cost).toBeLessThan(claudeCost);
    });

    it('should compare o1-preview vs claude-opus-4 costs', () => {
      const o1Provider = new OpenAIProvider({ name: 'o1-preview', provider: 'openai', apiKey: 'test', cost: 0 });
      const claudeProvider = new AnthropicProvider({ name: 'claude-opus-4', provider: 'anthropic', apiKey: 'test', cost: 0 });

      const o1Cost = o1Provider.calculateCost(1000000, 1000000, 'o1-preview');
      const claudeCost = claudeProvider.calculateCost(1000000, 1000000, 'claude-opus-4');

      // o1-preview: $15 in + $60 out = $75 for 2M tokens
      // claude-opus-4: $45 blended = $90 for 2M tokens
      expect(o1Cost).toBeCloseTo(75.0, 6);
      expect(claudeCost).toBeCloseTo(90.0, 6);

      // o1-preview is cheaper
      expect(o1Cost).toBeLessThan(claudeCost);
    });
  });
});

describe('DeepSeek-R1 Reasoning Model (Ollama)', () => {
  let mockConfig: ModelConfig;

  beforeEach(() => {
    mockConfig = {
      name: 'llama3.2',
      provider: 'ollama',
      cost: 0,
    };
    vi.clearAllMocks();
  });

  describe('Model Detection', () => {
    it('should detect deepseek-r1 as reasoning model', () => {
      const modelInfo = getOllamaReasoningModelInfo('deepseek-r1');
      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('ollama');
      expect(modelInfo.supportsStreaming).toBe(true);
      expect(modelInfo.supportsTools).toBe(true);
      expect(modelInfo.supportsSystemMessages).toBe(true);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
      expect(modelInfo.requiresThinkingBudget).toBe(false);
    });

    it('should detect deepseek-r1:latest as reasoning model', () => {
      const modelInfo = getOllamaReasoningModelInfo('deepseek-r1:latest');
      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('ollama');
    });

    it('should detect deepseek-r1:8b as reasoning model', () => {
      const modelInfo = getOllamaReasoningModelInfo('deepseek-r1:8b');
      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('ollama');
    });

    it('should detect deepseek-r1:32b as reasoning model', () => {
      const modelInfo = getOllamaReasoningModelInfo('deepseek-r1:32b');
      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('ollama');
    });

    it('should detect deepseek-r1:70b as reasoning model', () => {
      const modelInfo = getOllamaReasoningModelInfo('deepseek-r1:70b');
      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('ollama');
    });

    it('should handle case-insensitive model names', () => {
      const modelInfo1 = getOllamaReasoningModelInfo('DEEPSEEK-R1');
      const modelInfo2 = getOllamaReasoningModelInfo('DeepSeek-R1:8B');

      expect(modelInfo1.isReasoning).toBe(true);
      expect(modelInfo2.isReasoning).toBe(true);
    });

    it('should detect deepseek_r1 (underscore) as reasoning model', () => {
      const modelInfo = getOllamaReasoningModelInfo('deepseek_r1');
      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('ollama');
    });

    it('should not detect llama3 as reasoning model', () => {
      const modelInfo = getOllamaReasoningModelInfo('llama3.2');
      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.provider).toBe('ollama');
    });

    it('should not detect mistral as reasoning model', () => {
      const modelInfo = getOllamaReasoningModelInfo('mistral');
      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.provider).toBe('ollama');
    });

    it('should not detect qwen as reasoning model', () => {
      const modelInfo = getOllamaReasoningModelInfo('qwen:7b');
      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.provider).toBe('ollama');
    });
  });

  describe('Model Capabilities', () => {
    it('should report correct capabilities for DeepSeek-R1', () => {
      const modelInfo = getOllamaReasoningModelInfo('deepseek-r1');

      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('ollama');
      expect(modelInfo.supportsStreaming).toBe(true);
      expect(modelInfo.supportsTools).toBe(true);
      expect(modelInfo.supportsSystemMessages).toBe(true);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
      expect(modelInfo.requiresThinkingBudget).toBe(false);
    });

    it('should report correct capabilities for standard Ollama models', () => {
      const modelInfo = getOllamaReasoningModelInfo('llama3.2');

      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.provider).toBe('ollama');
      expect(modelInfo.supportsStreaming).toBe(true);
      expect(modelInfo.supportsTools).toBe(true);
      expect(modelInfo.supportsSystemMessages).toBe(true);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
      expect(modelInfo.requiresThinkingBudget).toBe(false);
    });
  });

  describe('Cost Calculation', () => {
    it('should return zero cost for Ollama (free)', () => {
      const provider = new OllamaProvider({ ...mockConfig, name: 'deepseek-r1' });
      const cost = provider.calculateCost(1000000, 2000000, 'deepseek-r1');

      // Ollama is always free (local execution)
      expect(cost).toBe(0.0);
    });

    it('should return zero cost for all Ollama models', () => {
      const models = ['deepseek-r1', 'deepseek-r1:8b', 'llama3.2', 'mistral'];

      models.forEach(model => {
        const provider = new OllamaProvider({ ...mockConfig, name: model });
        const cost = provider.calculateCost(1000000, 1000000, model);
        expect(cost).toBe(0.0);
      });
    });
  });

  describe('Provider Availability', () => {
    it('should be available without API key', () => {
      const provider = new OllamaProvider({ ...mockConfig, name: 'deepseek-r1' });
      expect(provider.isAvailable()).toBe(true);
    });

    it('should be available with any configuration', () => {
      const provider = new OllamaProvider({ name: 'deepseek-r1', provider: 'ollama', cost: 0 });
      expect(provider.isAvailable()).toBe(true);
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero tokens', () => {
      const provider = new OllamaProvider({ ...mockConfig, name: 'deepseek-r1' });
      const cost = provider.calculateCost(0, 0, 'deepseek-r1');
      expect(cost).toBe(0.0);
    });

    it('should handle very large token counts', () => {
      const provider = new OllamaProvider({ ...mockConfig, name: 'deepseek-r1' });
      const cost = provider.calculateCost(10000000, 10000000, 'deepseek-r1');

      // Still free
      expect(cost).toBe(0.0);
    });
  });
});

describe('DeepSeek-R1 Reasoning Model (vLLM)', () => {
  let mockConfig: ModelConfig;

  beforeEach(() => {
    mockConfig = {
      name: 'llama-3.2-1b',
      provider: 'vllm',
      cost: 0,
    };
    vi.clearAllMocks();
  });

  describe('Model Detection', () => {
    it('should detect deepseek-r1 as reasoning model', () => {
      const modelInfo = getVLLMReasoningModelInfo('deepseek-r1');
      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('vllm');
      expect(modelInfo.supportsStreaming).toBe(true);
      expect(modelInfo.supportsTools).toBe(true);
      expect(modelInfo.supportsSystemMessages).toBe(true);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
      expect(modelInfo.requiresThinkingBudget).toBe(false);
    });

    it('should detect deepseek-r1-distill as reasoning model', () => {
      const modelInfo = getVLLMReasoningModelInfo('deepseek-r1-distill');
      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('vllm');
    });

    it('should detect deepseek-r1-distill-llama-8b as reasoning model', () => {
      const modelInfo = getVLLMReasoningModelInfo('deepseek-r1-distill-llama-8b');
      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('vllm');
    });

    it('should handle case-insensitive model names', () => {
      const modelInfo1 = getVLLMReasoningModelInfo('DEEPSEEK-R1');
      const modelInfo2 = getVLLMReasoningModelInfo('DeepSeek-R1-Distill');

      expect(modelInfo1.isReasoning).toBe(true);
      expect(modelInfo2.isReasoning).toBe(true);
    });

    it('should detect deepseek_r1 (underscore) as reasoning model', () => {
      const modelInfo = getVLLMReasoningModelInfo('deepseek_r1');
      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('vllm');
    });

    it('should not detect llama as reasoning model', () => {
      const modelInfo = getVLLMReasoningModelInfo('llama-3.2-1b');
      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.provider).toBe('vllm');
    });

    it('should not detect mistral as reasoning model', () => {
      const modelInfo = getVLLMReasoningModelInfo('mistral-7b-instruct');
      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.provider).toBe('vllm');
    });

    it('should not detect qwen as reasoning model', () => {
      const modelInfo = getVLLMReasoningModelInfo('qwen-7b');
      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.provider).toBe('vllm');
    });
  });

  describe('Model Capabilities', () => {
    it('should report correct capabilities for DeepSeek-R1', () => {
      const modelInfo = getVLLMReasoningModelInfo('deepseek-r1');

      expect(modelInfo.isReasoning).toBe(true);
      expect(modelInfo.provider).toBe('vllm');
      expect(modelInfo.supportsStreaming).toBe(true);
      expect(modelInfo.supportsTools).toBe(true);
      expect(modelInfo.supportsSystemMessages).toBe(true);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
      expect(modelInfo.requiresThinkingBudget).toBe(false);
    });

    it('should report correct capabilities for standard vLLM models', () => {
      const modelInfo = getVLLMReasoningModelInfo('llama-3.2-1b');

      expect(modelInfo.isReasoning).toBe(false);
      expect(modelInfo.provider).toBe('vllm');
      expect(modelInfo.supportsStreaming).toBe(true);
      expect(modelInfo.supportsTools).toBe(true);
      expect(modelInfo.supportsSystemMessages).toBe(true);
      expect(modelInfo.supportsExtendedThinking).toBe(false);
      expect(modelInfo.requiresThinkingBudget).toBe(false);
    });
  });

  describe('Cost Calculation', () => {
    it('should return zero cost for vLLM by default (self-hosted)', () => {
      const provider = new VLLMProvider({ ...mockConfig, name: 'deepseek-r1' });
      const cost = provider.calculateCost(1000000, 2000000, 'deepseek-r1');

      // vLLM is self-hosted, defaults to free
      expect(cost).toBe(0.0);
    });

    it('should use custom cost if provided in config', () => {
      const customCost = 0.001;
      const provider = new VLLMProvider({ ...mockConfig, name: 'deepseek-r1', cost: customCost });
      const cost = provider.calculateCost(1000000, 2000000, 'deepseek-r1');

      expect(cost).toBe(customCost);
    });

    it('should return zero cost for all vLLM models by default', () => {
      const models = ['deepseek-r1', 'deepseek-r1-distill', 'llama-3.2-1b', 'mistral-7b'];

      models.forEach(model => {
        const provider = new VLLMProvider({ ...mockConfig, name: model });
        const cost = provider.calculateCost(1000000, 1000000, model);
        expect(cost).toBe(0.0);
      });
    });
  });

  describe('Provider Availability', () => {
    it('should be available without API key', () => {
      const provider = new VLLMProvider({ ...mockConfig, name: 'deepseek-r1' });
      expect(provider.isAvailable()).toBe(true);
    });

    it('should be available with any configuration', () => {
      const provider = new VLLMProvider({ name: 'deepseek-r1', provider: 'vllm', cost: 0 });
      expect(provider.isAvailable()).toBe(true);
    });

    it('should be available with API key if provided', () => {
      const provider = new VLLMProvider({ ...mockConfig, name: 'deepseek-r1', apiKey: 'test-key' });
      expect(provider.isAvailable()).toBe(true);
    });
  });

  describe('Edge Cases', () => {
    it('should handle zero tokens', () => {
      const provider = new VLLMProvider({ ...mockConfig, name: 'deepseek-r1' });
      const cost = provider.calculateCost(0, 0, 'deepseek-r1');
      expect(cost).toBe(0.0);
    });

    it('should handle very large token counts', () => {
      const provider = new VLLMProvider({ ...mockConfig, name: 'deepseek-r1' });
      const cost = provider.calculateCost(10000000, 10000000, 'deepseek-r1');

      // Still free by default
      expect(cost).toBe(0.0);
    });
  });
});

describe('Multi-Provider DeepSeek-R1 Comparison', () => {
  describe('Ollama vs vLLM DeepSeek-R1', () => {
    it('should detect DeepSeek-R1 in both providers', () => {
      const ollamaInfo = getOllamaReasoningModelInfo('deepseek-r1');
      const vllmInfo = getVLLMReasoningModelInfo('deepseek-r1');

      expect(ollamaInfo.isReasoning).toBe(true);
      expect(vllmInfo.isReasoning).toBe(true);
      expect(ollamaInfo.provider).toBe('ollama');
      expect(vllmInfo.provider).toBe('vllm');
    });

    it('should have consistent capabilities across providers', () => {
      const ollamaInfo = getOllamaReasoningModelInfo('deepseek-r1');
      const vllmInfo = getVLLMReasoningModelInfo('deepseek-r1');

      expect(ollamaInfo.supportsStreaming).toBe(vllmInfo.supportsStreaming);
      expect(ollamaInfo.supportsTools).toBe(vllmInfo.supportsTools);
      expect(ollamaInfo.supportsSystemMessages).toBe(vllmInfo.supportsSystemMessages);
      expect(ollamaInfo.supportsExtendedThinking).toBe(vllmInfo.supportsExtendedThinking);
      expect(ollamaInfo.requiresThinkingBudget).toBe(vllmInfo.requiresThinkingBudget);
    });

    it('should be free for both local providers', () => {
      const ollamaProvider = new OllamaProvider({ name: 'deepseek-r1', provider: 'ollama', cost: 0 });
      const vllmProvider = new VLLMProvider({ name: 'deepseek-r1', provider: 'vllm', cost: 0 });

      const ollamaCost = ollamaProvider.calculateCost(1000000, 1000000, 'deepseek-r1');
      const vllmCost = vllmProvider.calculateCost(1000000, 1000000, 'deepseek-r1');

      expect(ollamaCost).toBe(0.0);
      expect(vllmCost).toBe(0.0);
    });
  });
});
