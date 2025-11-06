/**
 * Tests for OpenRouter provider
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { OpenRouterProvider } from '../providers/openrouter';
import type { ModelConfig } from '../config';

// Mock fetch globally
global.fetch = vi.fn();

describe('OpenRouter Provider', () => {
  let mockConfig: ModelConfig;

  beforeEach(() => {
    mockConfig = {
      name: 'openai/gpt-4o-mini',
      provider: 'openrouter',
      apiKey: 'sk-or-test-key',
      cost: 0.00015,
    };
    vi.clearAllMocks();
  });

  describe('Provider Initialization', () => {
    it('should create provider with valid config', () => {
      const provider = new OpenRouterProvider(mockConfig);
      expect(provider).toBeDefined();
      expect(provider.name).toBe('openrouter');
    });

    it('should accept custom base URL', () => {
      const customConfig = { ...mockConfig, baseUrl: 'https://custom.openrouter.ai/api/v1' };
      const provider = new OpenRouterProvider(customConfig);
      expect(provider).toBeDefined();
    });

    it('should be available when API key is provided', () => {
      const provider = new OpenRouterProvider(mockConfig);
      expect(provider.isAvailable()).toBe(true);
    });
  });

  describe('Cost Calculation', () => {
    it('should calculate cost for gpt-4o correctly', () => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: 'openai/gpt-4o' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'openai/gpt-4o');

      // Input: 1M tokens at $2.50/1M = $2.50
      // Output: 1M tokens at $10.00/1M = $10.00
      // Total: $12.50
      expect(cost).toBeCloseTo(12.50, 2);
    });

    it('should calculate cost for claude-opus-4 correctly', () => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: 'anthropic/claude-opus-4' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'anthropic/claude-opus-4');

      // Input: 1M tokens at $15/1M = $15.00
      // Output: 1M tokens at $75/1M = $75.00
      // Total: $90.00
      expect(cost).toBeCloseTo(90.0, 2);
    });

    it('should calculate cost for claude-4.5-sonnet correctly', () => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: 'anthropic/claude-4.5-sonnet-20250929' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'anthropic/claude-4.5-sonnet-20250929');

      // Input: 1M tokens at $3/1M = $3.00
      // Output: 1M tokens at $15/1M = $15.00
      // Total: $18.00
      expect(cost).toBeCloseTo(18.0, 2);
    });

    it('should calculate cost for gemini-2.5-flash correctly', () => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: 'google/gemini-2.5-flash' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'google/gemini-2.5-flash');

      // Input: 1M tokens at $0.15/1M = $0.15
      // Output: 1M tokens at $0.60/1M = $0.60
      // Total: $0.75
      expect(cost).toBeCloseTo(0.75, 2);
    });

    it('should calculate cost for llama-3.1-8b correctly', () => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: 'meta-llama/llama-3.1-8b-instruct' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'meta-llama/llama-3.1-8b-instruct');

      // Input: 1M tokens at $0.05/1M = $0.05
      // Output: 1M tokens at $0.05/1M = $0.05
      // Total: $0.10
      expect(cost).toBeCloseTo(0.10, 2);
    });

    it('should return zero cost for free models', () => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: 'deepseek/deepseek-chat' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'deepseek/deepseek-chat');

      // Free model
      expect(cost).toBe(0);
    });

    it('should handle unknown models with fallback pricing', () => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: 'unknown/model' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'unknown/model');

      // Should fallback to gpt-4o-mini pricing ($0.15/$0.60)
      expect(cost).toBeCloseTo(0.75, 2);
    });

    it('should handle case-insensitive model names', () => {
      const provider = new OpenRouterProvider(mockConfig);
      const cost1 = provider.calculateCost(1_000_000, 1_000_000, 'openai/gpt-4o');
      const cost2 = provider.calculateCost(1_000_000, 1_000_000, 'OpenAI/GPT-4O');

      expect(cost1).toBeCloseTo(cost2, 6);
    });
  });

  describe('Generate Method', () => {
    it('should make correct API request', async () => {
      const mockResponse = {
        choices: [
          {
            message: {
              content: 'Test response',
              role: 'assistant',
            },
            finish_reason: 'stop',
          },
        ],
        model: 'openai/gpt-4o-mini',
        usage: {
          prompt_tokens: 10,
          completion_tokens: 20,
          total_tokens: 30,
        },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const provider = new OpenRouterProvider(mockConfig);
      const result = await provider.generate({
        messages: [{ role: 'user', content: 'Hello' }],
        model: 'openai/gpt-4o-mini',
      });

      expect(result.content).toBe('Test response');
      expect(result.model).toBe('openai/gpt-4o-mini');
      expect(result.usage?.prompt_tokens).toBe(10);
      expect(result.usage?.completion_tokens).toBe(20);

      // Verify fetch was called with correct parameters
      expect(global.fetch).toHaveBeenCalledWith(
        'https://openrouter.ai/api/v1/chat/completions',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            Authorization: 'Bearer sk-or-test-key',
            'HTTP-Referer': 'https://github.com/lemony-ai/cascadeflow',
            'X-Title': 'CascadeFlow',
          }),
        })
      );
    });

    it('should handle API errors gracefully', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        text: async () => 'Invalid API key',
      });

      const provider = new OpenRouterProvider(mockConfig);

      await expect(
        provider.generate({
          messages: [{ role: 'user', content: 'Hello' }],
          model: 'openai/gpt-4o-mini',
        })
      ).rejects.toThrow();
    });

    it('should support tool calling', async () => {
      const mockResponse = {
        choices: [
          {
            message: {
              content: null,
              role: 'assistant',
              tool_calls: [
                {
                  id: 'call_123',
                  type: 'function',
                  function: {
                    name: 'get_weather',
                    arguments: '{"location": "San Francisco"}',
                  },
                },
              ],
            },
            finish_reason: 'tool_calls',
          },
        ],
        model: 'openai/gpt-4o-mini',
        usage: {
          prompt_tokens: 50,
          completion_tokens: 20,
          total_tokens: 70,
        },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const provider = new OpenRouterProvider(mockConfig);
      const result = await provider.generate({
        messages: [{ role: 'user', content: 'What is the weather in SF?' }],
        model: 'openai/gpt-4o-mini',
        tools: [
          {
            type: 'function',
            function: {
              name: 'get_weather',
              description: 'Get weather for a location',
              parameters: {
                type: 'object',
                properties: {
                  location: { type: 'string' },
                },
              },
            },
          },
        ],
      });

      expect(result.tool_calls).toBeDefined();
      expect(result.tool_calls?.length).toBe(1);
      expect(result.tool_calls?.[0].function.name).toBe('get_weather');
    });

    it('should include system prompt in messages', async () => {
      const mockResponse = {
        choices: [{ message: { content: 'Response', role: 'assistant' }, finish_reason: 'stop' }],
        model: 'openai/gpt-4o-mini',
        usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const provider = new OpenRouterProvider(mockConfig);
      await provider.generate({
        messages: [{ role: 'user', content: 'Hello' }],
        model: 'openai/gpt-4o-mini',
        systemPrompt: 'You are a helpful assistant',
      });

      const fetchCall = (global.fetch as any).mock.calls[0];
      const requestBody = JSON.parse(fetchCall[1].body);

      expect(requestBody.messages[0].role).toBe('system');
      expect(requestBody.messages[0].content).toBe('You are a helpful assistant');
    });
  });

  describe('Streaming', () => {
    it('should support streaming responses', async () => {
      const mockStream = `data: {"choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{"content":" world"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n`;

      const encoder = new TextEncoder();
      const mockReader = {
        read: vi
          .fn()
          .mockResolvedValueOnce({ done: false, value: encoder.encode(mockStream) })
          .mockResolvedValueOnce({ done: true, value: undefined }),
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      });

      const provider = new OpenRouterProvider(mockConfig);
      const chunks: string[] = [];

      for await (const chunk of provider.stream!({
        messages: [{ role: 'user', content: 'Hello' }],
        model: 'openai/gpt-4o-mini',
      })) {
        chunks.push(chunk.content);
      }

      expect(chunks).toContain('Hello');
      expect(chunks).toContain(' world');
    });
  });

  describe('Model Discovery', () => {
    it('should fetch available models from API', async () => {
      const mockModels = {
        data: [
          {
            id: 'openai/gpt-4o',
            name: 'GPT-4o',
            pricing: {
              prompt: '0.0000025',
              completion: '0.00001',
            },
            context_length: 128000,
          },
          {
            id: 'anthropic/claude-opus-4',
            name: 'Claude Opus 4',
            pricing: {
              prompt: '0.000015',
              completion: '0.000075',
            },
            context_length: 200000,
          },
        ],
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockModels,
      });

      const provider = new OpenRouterProvider(mockConfig);
      const models = await provider.fetchAvailableModels();

      expect(models).toHaveLength(2);
      expect(models[0].id).toBe('openai/gpt-4o');
      expect(models[1].id).toBe('anthropic/claude-opus-4');
    });

    it('should cache model list for 1 hour', async () => {
      const mockModels = {
        data: [{ id: 'openai/gpt-4o', pricing: { prompt: '0.0000025', completion: '0.00001' } }],
      };

      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => mockModels,
      });

      const provider = new OpenRouterProvider(mockConfig);

      // First call should fetch
      await provider.fetchAvailableModels();
      expect(global.fetch).toHaveBeenCalledTimes(1);

      // Second call should use cache
      await provider.fetchAvailableModels();
      expect(global.fetch).toHaveBeenCalledTimes(1); // Still 1, not 2
    });

    it('should get pricing for specific model', async () => {
      const mockModels = {
        data: [
          {
            id: 'openai/gpt-4o',
            pricing: {
              prompt: '0.0000025',
              completion: '0.00001',
            },
          },
        ],
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockModels,
      });

      const provider = new OpenRouterProvider(mockConfig);
      const pricing = await provider.getModelPricing('openai/gpt-4o');

      expect(pricing).toBeDefined();
      expect(pricing?.input).toBe(2.5); // 0.0000025 * 1M
      expect(pricing?.output).toBe(10.0); // 0.00001 * 1M
    });

    it('should return null for unknown model pricing', async () => {
      const mockModels = {
        data: [],
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockModels,
      });

      const provider = new OpenRouterProvider(mockConfig);
      const pricing = await provider.getModelPricing('unknown/model');

      expect(pricing).toBeNull();
    });

    it('should handle model fetch errors gracefully', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Network error'));

      const provider = new OpenRouterProvider(mockConfig);
      const models = await provider.fetchAvailableModels();

      // Should return empty array on error, not throw
      expect(models).toEqual([]);
    });
  });

  describe('Top 2025 Models', () => {
    it('should have pricing for Grok Code Fast', () => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: 'x-ai/grok-code-fast-1' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'x-ai/grok-code-fast-1');
      expect(cost).toBe(0); // Free
    });

    it('should have pricing for DeepSeek Coder V2', () => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: 'deepseek/deepseek-coder-v2' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'deepseek/deepseek-coder-v2');
      expect(cost).toBeCloseTo(1.37, 2); // $0.27 + $1.10
    });

    it('should have pricing for MiniMax M2', () => {
      const provider = new OpenRouterProvider({ ...mockConfig, name: 'minimax/minimax-m2' });
      const cost = provider.calculateCost(1_000_000, 1_000_000, 'minimax/minimax-m2');
      expect(cost).toBeCloseTo(0.2, 2); // $0.10 + $0.10
    });
  });
});
