import { describe, it, expect } from 'vitest';
import {
  extractTokenUsage,
  calculateQuality,
  extractToolCalls,
  calculateCost,
  calculateSavings,
  createCostMetadata,
} from './utils.js';

describe('extractTokenUsage', () => {
  it('should extract OpenAI format with snake_case', () => {
    const response = {
      llmOutput: {
        tokenUsage: {
          prompt_tokens: 100,
          completion_tokens: 50,
        },
      },
    };

    const result = extractTokenUsage(response);
    expect(result).toEqual({ input: 100, output: 50 });
  });

  it('should extract OpenAI format with camelCase (LangChain)', () => {
    const response = {
      llmOutput: {
        tokenUsage: {
          promptTokens: 100,
          completionTokens: 50,
        },
      },
    };

    const result = extractTokenUsage(response);
    expect(result).toEqual({ input: 100, output: 50 });
  });

  it('should extract Anthropic format', () => {
    const response = {
      llmOutput: {
        tokenUsage: {
          input_tokens: 100,
          output_tokens: 50,
        },
      },
    };

    const result = extractTokenUsage(response);
    expect(result).toEqual({ input: 100, output: 50 });
  });

  it('should handle usage nested under llmOutput.usage', () => {
    const response = {
      llmOutput: {
        usage: {
          promptTokens: 100,
          completionTokens: 50,
        },
      },
    };

    const result = extractTokenUsage(response);
    expect(result).toEqual({ input: 100, output: 50 });
  });

  it('should return zeros for missing token usage', () => {
    const response = {
      llmOutput: {},
    };

    const result = extractTokenUsage(response);
    expect(result).toEqual({ input: 0, output: 0 });
  });

  it('should handle partial token counts', () => {
    const response = {
      llmOutput: {
        tokenUsage: {
          promptTokens: 100,
          // missing completionTokens
        },
      },
    };

    const result = extractTokenUsage(response);
    expect(result).toEqual({ input: 100, output: 0 });
  });
});

describe('calculateQuality', () => {
  it('should return low quality for empty text', () => {
    const response = {
      generations: [
        {
          text: '',
        },
      ],
    };

    const result = calculateQuality(response);
    expect(result).toBe(0.2);
  });

  it('should treat tool calls as high quality (even with empty content)', () => {
    const response = {
      generations: [
        {
          text: '',
          message: {
            content: '',
            tool_calls: [{ name: 'get_weather', args: { location: 'Berlin' } }],
          },
        },
      ],
    };

    expect(extractToolCalls(response)).toHaveLength(1);
    const result = calculateQuality(response);
    expect(result).toBe(1.0);
  });

  it('should return low quality for very short text', () => {
    const response = {
      generations: [
        {
          text: 'Hi',
        },
      ],
    };

    const result = calculateQuality(response);
    expect(result).toBe(0.2);
  });

  it('should calculate quality for simple complete answer', () => {
    const response = {
      generations: [
        {
          text: '2 + 2 equals 4.',
        },
      ],
    };

    const result = calculateQuality(response);
    // Base 0.4 + has punctuation (0.05) + starts capital (0.05) + ends punctuation (0.05) = 0.55
    // Text is only 18 chars, so no length bonuses (need >50 and >200)
    expect(result).toBeGreaterThanOrEqual(0.5);
    expect(result).toBeLessThanOrEqual(0.6);
  });

  it('should calculate quality for complex answer', () => {
    const response = {
      generations: [
        {
          text: 'Quantum entanglement is a fundamental phenomenon in quantum mechanics where two or more particles become interconnected in such a way that the quantum state of each particle cannot be described independently, even when separated by large distances.',
        },
      ],
    };

    const result = calculateQuality(response);
    // Base 0.4 + length>50 (0.1) + length>200 (0.1) + punctuation (0.05) + capital (0.05) + ends (0.05) = 0.75
    expect(result).toBeGreaterThanOrEqual(0.7);
    expect(result).toBeLessThanOrEqual(0.8);
  });

  it('should penalize hedging phrases', () => {
    const response = {
      generations: [
        {
          text: "I don't know the answer to that question.",
        },
      ],
    };

    const result = calculateQuality(response);
    // Base 0.4 + punct (0.05) + capital (0.05) + ends (0.05) - hedge (0.15) = 0.4
    expect(result).toBeLessThanOrEqual(0.5);
  });

  it('should extract text from message.content', () => {
    const response = {
      generations: [
        {
          message: {
            content: 'TypeScript is a typed superset of JavaScript.',
          },
        },
      ],
    };

    const result = calculateQuality(response);
    // Base 0.4 + punct (0.05) + capital (0.05) + ends (0.05) = 0.55 (text is 48 chars, needs >50 for bonus)
    expect(result).toBeGreaterThan(0.5);
    expect(result).toBeLessThan(0.7);
  });

  it('should handle logprobs-based confidence (OpenAI)', () => {
    const response = {
      generations: [
        {
          text: 'Test answer',
          generationInfo: {
            logprobs: {
              content: [
                { token: 'Test', logprob: -0.1 },
                { token: ' answer', logprob: -0.2 },
              ],
            },
          },
        },
      ],
    };

    const result = calculateQuality(response);
    // Should use logprobs instead of heuristics
    expect(result).toBeGreaterThan(0);
    expect(result).toBeLessThanOrEqual(1);
  });

  it('should cap quality at 1.0', () => {
    const response = {
      generations: [
        {
          text: 'A very long and detailed answer that has excellent structure, perfect capitalization, proper punctuation, and comprehensive content that demonstrates high quality throughout the entire response.',
        },
      ],
    };

    const result = calculateQuality(response);
    expect(result).toBeLessThanOrEqual(1.0);
  });

  it('should floor quality at 0.1', () => {
    const response = {
      generations: [
        {
          text: "i don't know i'm not sure i cannot i can't",
        },
      ],
    };

    const result = calculateQuality(response);
    expect(result).toBeGreaterThanOrEqual(0.1);
  });
});

describe('calculateCost', () => {
  it('should calculate cost for GPT-4o-mini', () => {
    const cost = calculateCost('gpt-4o-mini', 100_000, 50_000);
    // Input: (100k / 1M) * 0.150 = 0.015
    // Output: (50k / 1M) * 0.600 = 0.030
    // Total: 0.045
    expect(cost).toBeCloseTo(0.045, 3);
  });

  it('should calculate cost for GPT-4o', () => {
    const cost = calculateCost('gpt-4o', 100_000, 50_000);
    // Input: (100k / 1M) * 2.50 = 0.250
    // Output: (50k / 1M) * 10.00 = 0.500
    // Total: 0.750
    expect(cost).toBeCloseTo(0.750, 3);
  });

  it('should calculate cost for Claude Sonnet', () => {
    const cost = calculateCost('claude-3-5-sonnet-20241022', 100_000, 50_000);
    // Input: (100k / 1M) * 3.00 = 0.300
    // Output: (50k / 1M) * 15.00 = 0.750
    // Total: 1.050
    expect(cost).toBeCloseTo(1.050, 3);
  });

  it('should return 0 for unknown model', () => {
    const cost = calculateCost('unknown-model', 100_000, 50_000);
    expect(cost).toBe(0);
  });

  it('should handle zero tokens', () => {
    const cost = calculateCost('gpt-4o-mini', 0, 0);
    expect(cost).toBe(0);
  });

  it('should calculate cost for small token counts', () => {
    const cost = calculateCost('gpt-4o-mini', 14, 8);
    // Input: (14 / 1M) * 0.150 = 0.0000021
    // Output: (8 / 1M) * 0.600 = 0.0000048
    // Total: 0.0000069
    expect(cost).toBeCloseTo(0.0000069, 7);
  });
});

describe('calculateSavings', () => {
  it('should calculate savings percentage', () => {
    const savings = calculateSavings(0.01, 0.10);
    // Total cost: 0.11
    // Potential cost (verifier only): 0.10
    // Savings: ((0.10 - 0.11) / 0.10) * 100 = -10%
    expect(savings).toBeCloseTo(-10, 1);
  });

  it('should show positive savings when drafter is accepted', () => {
    const savings = calculateSavings(0.01, 0.00);
    // Total cost: 0.01
    // Potential cost: 0.00
    // When verifier cost is 0, it means drafter was accepted, so no savings
    expect(savings).toBe(0);
  });

  it('should return 0 when verifier cost is 0', () => {
    const savings = calculateSavings(0.05, 0);
    expect(savings).toBe(0);
  });

  it('should handle equal costs', () => {
    const savings = calculateSavings(0.05, 0.05);
    // Total: 0.10, Potential: 0.05
    // Savings: ((0.05 - 0.10) / 0.05) * 100 = -100%
    expect(savings).toBeCloseTo(-100, 1);
  });
});

describe('createCostMetadata', () => {
  it('should create metadata for accepted drafter response', () => {
    const drafterResponse = {
      generations: [{ text: '4' }],
      llmOutput: {
        tokenUsage: {
          promptTokens: 14,
          completionTokens: 8,
        },
      },
    };

    const metadata = createCostMetadata(
      drafterResponse,
      null,
      'gpt-4o-mini',
      'gpt-4o',
      true,
      0.8,
      'cascadeflow'
    );

    expect(metadata.drafterTokens).toEqual({ input: 14, output: 8 });
    expect(metadata.verifierTokens).toBeUndefined();
    const expectedVerifierCost = calculateCost('gpt-4o', 14, 8);
    const expectedSavings =
      ((expectedVerifierCost - metadata.drafterCost) / expectedVerifierCost) * 100;

    expect(metadata.drafterCost).toBeCloseTo(0.0000069, 7);
    expect(metadata.verifierCost).toBe(0);
    expect(metadata.totalCost).toBeCloseTo(0.0000069, 7);
    expect(metadata.savingsPercentage).toBeCloseTo(expectedSavings, 5);
    expect(metadata.modelUsed).toBe('drafter');
    expect(metadata.accepted).toBe(true);
    expect(metadata.drafterQuality).toBe(0.8);
  });

  it('should create metadata for rejected drafter response', () => {
    const drafterResponse = {
      generations: [{ text: 'I don\'t know' }],
      llmOutput: {
        tokenUsage: {
          promptTokens: 14,
          completionTokens: 5,
        },
      },
    };

    const verifierResponse = {
      generations: [{ text: 'The answer is 4' }],
      llmOutput: {
        tokenUsage: {
          promptTokens: 14,
          completionTokens: 8,
        },
      },
    };

    const metadata = createCostMetadata(
      drafterResponse,
      verifierResponse,
      'gpt-4o-mini',
      'gpt-4o',
      false,
      0.3,
      'cascadeflow'
    );

    expect(metadata.drafterTokens).toEqual({ input: 14, output: 5 });
    expect(metadata.verifierTokens).toEqual({ input: 14, output: 8 });
    expect(metadata.drafterCost).toBeGreaterThan(0);
    expect(metadata.verifierCost).toBeGreaterThan(0);
    expect(metadata.totalCost).toBeGreaterThan(metadata.drafterCost);
    expect(metadata.modelUsed).toBe('verifier');
    expect(metadata.accepted).toBe(false);
    expect(metadata.drafterQuality).toBe(0.3);
  });

  it('should handle unknown models gracefully', () => {
    const drafterResponse = {
      generations: [{ text: 'Test' }],
      llmOutput: {
        tokenUsage: {
          promptTokens: 10,
          completionTokens: 5,
        },
      },
    };

    const metadata = createCostMetadata(
      drafterResponse,
      null,
      'unknown-model-1',
      'unknown-model-2',
      true,
      0.9
    );

    expect(metadata.drafterCost).toBe(0);
    expect(metadata.verifierCost).toBe(0);
    expect(metadata.totalCost).toBe(0);
  });
});
