/**
 * OpenRouter provider implementation
 *
 * OpenRouter provides unified access to 400+ AI models from multiple providers
 * through a single API endpoint. It's OpenAI-compatible and supports all major
 * models from OpenAI, Anthropic, Google, Meta, Mistral, X.AI, and more.
 *
 * @see https://openrouter.ai/docs
 */

import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Tool, Message } from '../types';
import type { ModelConfig } from '../config';
import type { StreamChunk } from '../streaming';

/**
 * OpenRouter pricing per 1M tokens (sample of popular models as of 2025)
 *
 * Note: OpenRouter has 400+ models with dynamic pricing.
 * Fetch latest pricing from: https://openrouter.ai/api/v1/models
 *
 * @see https://openrouter.ai/models
 */
const OPENROUTER_PRICING: Record<string, { input: number; output: number }> = {
  // X.AI Models (Top Used - 53.1% of traffic)
  'x-ai/grok-code-fast-1': { input: 0, output: 0 }, // Free tier
  'x-ai/grok-beta': { input: 5.0, output: 15.0 },

  // Anthropic Models (Top Performer for Coding)
  'anthropic/claude-opus-4': { input: 15.0, output: 75.0 }, // Best coding model
  'anthropic/claude-sonnet-4': { input: 3.0, output: 15.0 },
  'anthropic/claude-4.5-sonnet-20250929': { input: 3.0, output: 15.0 },
  'anthropic/claude-3.5-sonnet': { input: 3.0, output: 15.0 },
  'anthropic/claude-3-haiku': { input: 0.25, output: 1.25 },

  // OpenAI Models
  'openai/gpt-4o': { input: 2.5, output: 10.0 },
  'openai/gpt-4o-mini': { input: 0.15, output: 0.6 },
  'openai/gpt-5': { input: 1.25, output: 10.0 },
  'openai/gpt-5-mini': { input: 0.25, output: 2.0 },
  'openai/o1': { input: 15.0, output: 60.0 },
  'openai/o1-mini': { input: 3.0, output: 12.0 },

  // Google Models (19.2% market share)
  'google/gemini-2.5-flash': { input: 0.15, output: 0.6 }, // 1M context
  'google/gemini-2.5-pro': { input: 1.25, output: 5.0 },
  'google/gemini-pro-1.5': { input: 1.25, output: 5.0 },

  // Meta Models
  'meta-llama/llama-3.1-405b-instruct': { input: 1.0, output: 1.0 },
  'meta-llama/llama-3.1-70b-instruct': { input: 0.35, output: 0.4 },
  'meta-llama/llama-3.1-8b-instruct': { input: 0.05, output: 0.05 },
  'meta-llama/llama-4-maverick': { input: 1.5, output: 1.5 }, // 400B params

  // DeepSeek Models (Great Value)
  'deepseek/deepseek-chat': { input: 0, output: 0 }, // Free
  'deepseek/deepseek-coder-v2': { input: 0.27, output: 1.1 }, // Nearly as good as premium

  // Mistral Models
  'mistralai/mistral-large': { input: 2.0, output: 6.0 },
  'mistralai/mistral-small-3.1': { input: 0, output: 0 }, // Free, 96K context
  'mistralai/devstral-small': { input: 0, output: 0 }, // Free

  // MiniMax Models
  'minimax/minimax-m2': { input: 0.1, output: 0.1 }, // 11.0% of traffic
};

/**
 * OpenRouter provider with OpenAI-compatible API
 *
 * Supports all OpenRouter features:
 * - 400+ models from multiple providers
 * - Streaming
 * - Tool calling
 * - Automatic fallbacks
 * - Dynamic model discovery
 */
export class OpenRouterProvider extends BaseProvider {
  readonly name = 'openrouter';
  private baseUrl: string;
  private modelCache?: Map<string, any>;
  private lastCacheFetch: number = 0;
  private readonly CACHE_TTL = 3600000; // 1 hour

  constructor(config: ModelConfig) {
    super(config);
    this.baseUrl = config.baseUrl || 'https://openrouter.ai/api/v1';
  }

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const apiKey = this.getApiKey();
      const messages = this.normalizeMessages(request.messages);
      const chatMessages = this.convertToChatMessages(messages, request.systemPrompt);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const modelName = request.model || this.config.name;
      const maxTokens = request.maxTokens || this.config.maxTokens || 1000;

      const requestBody: any = {
        model: modelName,
        messages: chatMessages,
        max_tokens: maxTokens,
        temperature: request.temperature ?? this.config.temperature ?? 0.7,
        ...request.extra,
      };

      // Add tools if provided
      if (tools && tools.length > 0) {
        requestBody.tools = tools;
      }

      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey}`,
          // Optional headers for leaderboard rankings
          'HTTP-Referer': 'https://github.com/lemony-ai/cascadeflow',
          'X-Title': 'CascadeFlow',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`OpenRouter API error: ${response.status} ${response.statusText} - ${errorText}`);
      }

      const completion: any = await response.json();
      const choice = completion.choices?.[0];

      if (!choice) {
        throw new Error('No response from OpenRouter');
      }

      return {
        content: choice.message.content || '',
        model: completion.model,
        usage: completion.usage
          ? {
              prompt_tokens: completion.usage.prompt_tokens,
              completion_tokens: completion.usage.completion_tokens,
              total_tokens: completion.usage.total_tokens,
            }
          : undefined,
        finish_reason: choice.finish_reason,
        tool_calls: choice.message.tool_calls?.map((tc: any) => ({
          id: tc.id,
          type: 'function',
          function: {
            name: tc.function.name,
            arguments: tc.function.arguments,
          },
        })),
        raw: completion,
      };
    } catch (error) {
      throw this.formatError(error);
    }
  }

  /**
   * Stream a completion from OpenRouter
   */
  async *stream(request: ProviderRequest): AsyncIterable<StreamChunk> {
    try {
      const apiKey = this.getApiKey();
      const messages = this.normalizeMessages(request.messages);
      const chatMessages = this.convertToChatMessages(messages, request.systemPrompt);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const modelName = request.model || this.config.name;
      const maxTokens = request.maxTokens || this.config.maxTokens || 1000;

      const requestBody: any = {
        model: modelName,
        messages: chatMessages,
        max_tokens: maxTokens,
        temperature: request.temperature ?? this.config.temperature ?? 0.7,
        stream: true,
        ...request.extra,
      };

      // Add tools if provided
      if (tools && tools.length > 0) {
        requestBody.tools = tools;
      }

      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${apiKey}`,
          'HTTP-Referer': 'https://github.com/lemony-ai/cascadeflow',
          'X-Title': 'CascadeFlow',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`OpenRouter API error: ${response.status} ${response.statusText} - ${errorText}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      // Parse SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim() || line.startsWith(':')) continue;

          if (line.startsWith('data: ')) {
            const data = line.slice(6);

            if (data === '[DONE]') {
              return;
            }

            try {
              const parsed = JSON.parse(data);
              const delta = parsed.choices?.[0]?.delta;
              if (!delta) continue;

              const content = delta.content || '';
              const isFinished = parsed.choices[0]?.finish_reason !== null;

              yield {
                content,
                done: isFinished,
                finish_reason: parsed.choices[0]?.finish_reason || undefined,
                raw: parsed,
              };
            } catch (e) {
              // Skip invalid JSON
              continue;
            }
          }
        }
      }
    } catch (error) {
      throw this.formatError(error);
    }
  }

  /**
   * Calculate cost based on OpenRouter pricing
   *
   * Note: Pricing is per 1M tokens, not per 1K tokens like some providers.
   *
   * @param promptTokens - Input tokens
   * @param completionTokens - Output tokens
   * @param model - Model name in provider/model format
   * @returns Cost in USD
   */
  calculateCost(promptTokens: number, completionTokens: number, model: string): number {
    // Normalize model name to lowercase
    const modelLower = model.toLowerCase();

    // Try exact match first
    let pricing = OPENROUTER_PRICING[modelLower];

    // Try prefix matching for versioned models
    if (!pricing) {
      for (const [key, value] of Object.entries(OPENROUTER_PRICING)) {
        if (modelLower.startsWith(key)) {
          pricing = value;
          break;
        }
      }
    }

    // Fallback to a reasonable default (gpt-4o-mini equivalent)
    if (!pricing) {
      pricing = { input: 0.15, output: 0.6 };
    }

    // OpenRouter pricing is per 1M tokens
    const inputCost = (promptTokens / 1_000_000) * pricing.input;
    const outputCost = (completionTokens / 1_000_000) * pricing.output;

    return inputCost + outputCost;
  }

  /**
   * Fetch available models from OpenRouter API
   *
   * This method fetches the live model list with current pricing.
   * Results are cached for 1 hour to avoid excessive API calls.
   *
   * @returns Array of model information
   * @see https://openrouter.ai/api/v1/models
   */
  async fetchAvailableModels(): Promise<any[]> {
    const now = Date.now();

    // Return cached data if still valid
    if (this.modelCache && now - this.lastCacheFetch < this.CACHE_TTL) {
      return Array.from(this.modelCache.values());
    }

    try {
      const response = await fetch(`${this.baseUrl}/models`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch models: ${response.status} ${response.statusText}`);
      }

      const data: any = await response.json();
      const models = data.data || [];

      // Cache the results
      this.modelCache = new Map(models.map((m: any) => [m.id, m]));
      this.lastCacheFetch = now;

      return models;
    } catch (error) {
      // If fetch fails, return empty array (don't break the provider)
      console.warn('Failed to fetch OpenRouter models:', error);
      return [];
    }
  }

  /**
   * Get pricing for a specific model from the API
   *
   * @param modelId - Model ID in provider/model format
   * @returns Pricing information or null if not found
   */
  async getModelPricing(modelId: string): Promise<{ input: number; output: number } | null> {
    const models = await this.fetchAvailableModels();
    const model = models.find((m) => m.id === modelId);

    if (!model?.pricing) {
      return null;
    }

    return {
      input: parseFloat(model.pricing.prompt) * 1_000_000, // Convert to per 1M tokens
      output: parseFloat(model.pricing.completion) * 1_000_000,
    };
  }

  /**
   * Convert generic messages to OpenAI chat format
   */
  private convertToChatMessages(messages: Message[], systemPrompt?: string): any[] {
    const chatMessages: any[] = [];

    if (systemPrompt) {
      chatMessages.push({ role: 'system', content: systemPrompt });
    }

    for (const msg of messages) {
      if (msg.role === 'system') {
        chatMessages.push({ role: 'system', content: msg.content });
      } else if (msg.role === 'user') {
        chatMessages.push({ role: 'user', content: msg.content });
      } else if (msg.role === 'assistant') {
        chatMessages.push({ role: 'assistant', content: msg.content });
      } else if (msg.role === 'tool') {
        chatMessages.push({
          role: 'tool',
          content: msg.content,
          tool_call_id: msg.tool_call_id || '',
        });
      }
    }

    return chatMessages;
  }

  /**
   * Convert generic tools to OpenAI format
   */
  private convertTools(tools: Tool[]): any[] {
    return tools.map((tool) => ({
      type: 'function',
      function: {
        name: tool.function.name,
        description: tool.function.description,
        parameters: tool.function.parameters,
      },
    }));
  }
}
