import { describe, it, expect } from 'vitest';
import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { AIMessage, BaseMessage } from '@langchain/core/messages';
import { ChatResult } from '@langchain/core/outputs';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import { analyzeCascadePair, suggestCascadePairs } from './helpers.js';

// Mock chat model for testing
class MockChatModel extends BaseChatModel {
  modelName: string;

  constructor(modelName: string) {
    super({});
    this.modelName = modelName;
  }

  _llmType(): string {
    return 'mock';
  }

  async _generate(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): Promise<ChatResult> {
    return {
      generations: [
        {
          text: 'test',
          message: new AIMessage('test'),
        },
      ],
      llmOutput: {},
    };
  }

  get model() {
    return this.modelName;
  }
}

describe('analyzeCascadePair', () => {
  it('should analyze valid OpenAI cascade pair', () => {
    const drafter = new MockChatModel('gpt-4o-mini');
    const verifier = new MockChatModel('gpt-4o');

    const analysis = analyzeCascadePair(drafter, verifier);

    expect(analysis.drafterModel).toBe('gpt-4o-mini');
    expect(analysis.verifierModel).toBe('gpt-4o');
    expect(analysis.valid).toBe(true);
    expect(analysis.warnings).toHaveLength(0);
    expect(analysis.estimatedSavings).toBeGreaterThan(50);
    expect(analysis.drafterCost.input).toBe(0.150);
    expect(analysis.drafterCost.output).toBe(0.600);
    expect(analysis.verifierCost.input).toBe(2.50);
    expect(analysis.verifierCost.output).toBe(10.00);
  });

  it('should analyze valid Anthropic cascade pair', () => {
    const drafter = new MockChatModel('claude-3-5-haiku-20241022');
    const verifier = new MockChatModel('claude-3-5-sonnet-20241022');

    const analysis = analyzeCascadePair(drafter, verifier);

    expect(analysis.drafterModel).toBe('claude-3-5-haiku-20241022');
    expect(analysis.verifierModel).toBe('claude-3-5-sonnet-20241022');
    expect(analysis.valid).toBe(true);
    expect(analysis.warnings).toHaveLength(0);
    expect(analysis.estimatedSavings).toBeGreaterThan(40);
    expect(analysis.drafterCost.input).toBe(0.80);
    expect(analysis.drafterCost.output).toBe(4.00);
    expect(analysis.verifierCost.input).toBe(3.00);
    expect(analysis.verifierCost.output).toBe(15.00);
  });

  it('should detect when drafter is more expensive than verifier', () => {
    const drafter = new MockChatModel('gpt-4o');
    const verifier = new MockChatModel('gpt-4o-mini');

    const analysis = analyzeCascadePair(drafter, verifier);

    expect(analysis.valid).toBe(false);
    expect(analysis.warnings.length).toBeGreaterThan(0);
    expect(analysis.warnings[0]).toContain('more expensive');
  });

  it('should detect when models are the same', () => {
    const drafter = new MockChatModel('gpt-4o');
    const verifier = new MockChatModel('gpt-4o');

    const analysis = analyzeCascadePair(drafter, verifier);

    expect(analysis.valid).toBe(false);
    expect(analysis.warnings.length).toBeGreaterThan(0);
    expect(analysis.warnings.some(w => w.includes('same model'))).toBe(true);
  });

  it('should handle unknown model pricing', () => {
    const drafter = new MockChatModel('unknown-model-1');
    const verifier = new MockChatModel('unknown-model-2');

    const analysis = analyzeCascadePair(drafter, verifier);

    expect(analysis.drafterModel).toBe('unknown-model-1');
    expect(analysis.verifierModel).toBe('unknown-model-2');
    expect(analysis.drafterCost.input).toBe(0);
    expect(analysis.drafterCost.output).toBe(0);
    expect(analysis.verifierCost.input).toBe(0);
    expect(analysis.verifierCost.output).toBe(0);
    expect(analysis.estimatedSavings).toBe(0);
    expect(analysis.warnings.length).toBeGreaterThan(0);
    expect(analysis.warnings.some(w => w.includes('Unknown pricing'))).toBe(true);
  });

  it('should generate correct recommendations', () => {
    const excellentDrafter = new MockChatModel('gpt-4o-mini');
    const excellentVerifier = new MockChatModel('gpt-4o');
    const excellentAnalysis = analyzeCascadePair(excellentDrafter, excellentVerifier);
    expect(excellentAnalysis.recommendation).toContain('Excellent');

    const invalidDrafter = new MockChatModel('gpt-4o');
    const invalidVerifier = new MockChatModel('gpt-4o-mini');
    const invalidAnalysis = analyzeCascadePair(invalidDrafter, invalidVerifier);
    expect(invalidAnalysis.recommendation).toContain('needs attention');
  });

  it('should extract model name from different property names', () => {
    // Test with model property
    const model1 = new MockChatModel('test-model-1');
    const model2 = new MockChatModel('test-model-2');

    const analysis = analyzeCascadePair(model1, model2);
    expect(analysis.drafterModel).toBe('test-model-1');
    expect(analysis.verifierModel).toBe('test-model-2');
  });
});

describe('suggestCascadePairs', () => {
  it('should suggest optimal pairs from available models', () => {
    const models = [
      new MockChatModel('gpt-4o-mini'),
      new MockChatModel('gpt-4o'),
      new MockChatModel('gpt-3.5-turbo'),
    ];

    const suggestions = suggestCascadePairs(models);

    expect(suggestions.length).toBeGreaterThan(0);

    // Verify all suggestions are valid
    suggestions.forEach(suggestion => {
      expect(suggestion.analysis.valid).toBe(true);
      expect(suggestion.analysis.estimatedSavings).toBeGreaterThan(20);
    });

    // Verify sorting (highest savings first)
    for (let i = 0; i < suggestions.length - 1; i++) {
      expect(suggestions[i].analysis.estimatedSavings)
        .toBeGreaterThanOrEqual(suggestions[i + 1].analysis.estimatedSavings);
    }
  });

  it('should filter out invalid configurations', () => {
    const models = [
      new MockChatModel('gpt-4o'), // expensive
      new MockChatModel('gpt-4o'), // duplicate
      new MockChatModel('gpt-4o-mini'), // cheap
    ];

    const suggestions = suggestCascadePairs(models);

    // All suggestions should be valid
    suggestions.forEach(suggestion => {
      expect(suggestion.analysis.valid).toBe(true);
      expect(suggestion.drafter).not.toBe(suggestion.verifier);
    });
  });

  it('should return empty array when no viable pairs exist', () => {
    const models = [
      new MockChatModel('unknown-1'),
      new MockChatModel('unknown-2'),
    ];

    const suggestions = suggestCascadePairs(models);

    // Should be empty since unknown models have no pricing info
    // and thus estimated savings is 0
    expect(suggestions).toHaveLength(0);
  });

  it('should handle single model', () => {
    const models = [new MockChatModel('gpt-4o-mini')];

    const suggestions = suggestCascadePairs(models);

    expect(suggestions).toHaveLength(0);
  });

  it('should handle empty model list', () => {
    const models: BaseChatModel[] = [];

    const suggestions = suggestCascadePairs(models);

    expect(suggestions).toHaveLength(0);
  });

  it('should identify best pair from mixed providers', () => {
    const models = [
      new MockChatModel('gpt-4o-mini'),
      new MockChatModel('gpt-4o'),
      new MockChatModel('claude-3-5-haiku-20241022'),
      new MockChatModel('claude-3-5-sonnet-20241022'),
    ];

    const suggestions = suggestCascadePairs(models);

    expect(suggestions.length).toBeGreaterThan(0);

    // Best suggestion should have highest savings
    const bestSuggestion = suggestions[0];
    expect(bestSuggestion.analysis.estimatedSavings).toBeGreaterThan(50);
  });
});
