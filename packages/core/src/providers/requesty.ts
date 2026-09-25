/**
 * Requesty provider implementation
 *
 * Requesty is an LLM gateway that gives unified access to hundreds of models
 * from multiple providers through a single OpenAI-compatible endpoint.
 * Regional endpoints are available (e.g. EU: https://router.eu.requesty.ai/v1).
 *
 * @see https://docs.requesty.ai
 */

import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Tool, Message } from '../types';
import type { ModelConfig } from '../config';
import type { StreamChunk } from '../streaming';

/**
 * Requesty pricing per 1M tokens (sample of popular models)
 *
 * Fetch latest pricing from: https://router.requesty.ai/v1/models
 */
const REQUESTY_PRICING: Record<string, { input: number; output: number }> = {
  // OpenAI Models
  'openai/gpt-4o-mini': { input: 0.15, output: 0.6 },
  'openai/gpt-4o': { input: 2.5, output: 10.0 },
  'openai/gpt-5-mini': { input: 0.25, output: 2.0 },
  'openai/gpt-5': { input: 1.25, output: 10.0 },

  // Anthropic Models
  'anthropic/claude-haiku-4-5': { input: 1.0, output: 5.0 },
  'anthropic/claude-sonnet-4-5': { input: 3.0, output: 15.0 },
  'anthropic/claude-opus-4-5': { input: 5.0, output: 25.0 },

  // Google Models
  'google/gemini-2.5-flash': { input: 0.3, output: 2.5 },
  'google/gemini-2.5-pro': { input: 1.25, output: 10.0 },

  // DeepSeek Models
  'deepseek/deepseek-chat': { input: 0.14, output: 0.28 },

  // xAI Models
  'xai/grok-4-fast': { input: 0.2, output: 0.5 },
};

/**
 * Requesty provider with OpenAI-compatible API
 *
 * Supports:
 * - Models from multiple providers through one API key
 * - Streaming
 * - Tool calling
 * - Dynamic model discovery
 */
export class RequestyProvider extends BaseProvider {
  readonly name = 'requesty';
  private baseUrl: string;
  private modelCache?: Map<string, any>;
  private lastCacheFetch: number = 0;
  private readonly CACHE_TTL = 3600000; // 1 hour

  constructor(config: ModelConfig) {
    super(config);
    this.baseUrl = config.baseUrl || 'https://router.requesty.ai/v1';
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
          // Optional attribution headers
          'HTTP-Referer': 'https://github.com/lemony-ai/cascadeflow',
          'X-Title': 'CascadeFlow',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Requesty API error: ${response.status} ${response.statusText} - ${errorText}`);
      }

      const completion: any = await response.json();
      const choice = completion.choices?.[0];

      if (!choice) {
        throw new Error('No response from Requesty');
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
   * Stream a completion from Requesty
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
        throw new Error(`Requesty API error: ${response.status} ${response.statusText} - ${errorText}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      // Parse SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      const toolCallsByIndex = new Map<number, { id: string; name: string; argsText: string }>();

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

              if (Array.isArray(delta.tool_calls)) {
                for (const toolDelta of delta.tool_calls) {
                  const idx = typeof toolDelta?.index === 'number' ? toolDelta.index : 0;
                  const prev = toolCallsByIndex.get(idx) ?? {
                    id: toolDelta?.id || `call_${idx}`,
                    name: toolDelta?.function?.name || 'unknown',
                    argsText: '',
                  };
                  toolCallsByIndex.set(idx, {
                    id: toolDelta?.id || prev.id,
                    name: toolDelta?.function?.name || prev.name,
                    argsText:
                      typeof toolDelta?.function?.arguments === 'string'
                        ? prev.argsText + toolDelta.function.arguments
                        : prev.argsText,
                  });
                }
              }

              yield {
                content,
                done: isFinished,
                finish_reason: parsed.choices[0]?.finish_reason || undefined,
                tool_calls:
                  Array.isArray(delta.tool_calls) && toolCallsByIndex.size > 0
                    ? Array.from(toolCallsByIndex.values()).map((tc) => ({
                        id: tc.id,
                        type: 'function',
                        function: { name: tc.name, arguments: tc.argsText },
                      }))
                    : undefined,
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
   * Calculate cost based on Requesty pricing
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
    let pricing = REQUESTY_PRICING[modelLower];

    // Try prefix matching for versioned models
    if (!pricing) {
      for (const [key, value] of Object.entries(REQUESTY_PRICING)) {
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

    // Requesty pricing is per 1M tokens
    const inputCost = (promptTokens / 1_000_000) * pricing.input;
    const outputCost = (completionTokens / 1_000_000) * pricing.output;

    return inputCost + outputCost;
  }

  /**
   * Fetch available models from Requesty API
   *
   * Managed policies (curated, e.g. `claude-sonnet-4-5`) come first, followed
   * by the full `vendor/model` catalog. Results are cached for 1 hour to avoid
   * excessive API calls.
   *
   * @returns Array of model information
   * @see https://router.requesty.ai/v1/models/managed
   * @see https://router.requesty.ai/v1/models
   */
  async fetchAvailableModels(): Promise<any[]> {
    const now = Date.now();

    // Return cached data if still valid
    if (this.modelCache && now - this.lastCacheFetch < this.CACHE_TTL) {
      return Array.from(this.modelCache.values());
    }

    const merged = new Map<string, any>();

    for (const path of ['/models/managed', '/models']) {
      try {
        const response = await fetch(`${this.baseUrl}${path}`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch models: ${response.status} ${response.statusText}`);
        }

        const data: any = await response.json();
        for (const model of data.data || []) {
          if (model?.id && !merged.has(model.id)) {
            merged.set(model.id, model);
          }
        }
      } catch (error) {
        // If one list fails, keep the other (don't break the provider)
        console.warn(`Failed to fetch Requesty models from ${path}:`, error);
      }
    }

    if (merged.size === 0) {
      return [];
    }

    // Cache the results
    this.modelCache = merged;
    this.lastCacheFetch = now;

    return Array.from(merged.values());
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

    if (typeof model?.input_price !== 'number' || typeof model?.output_price !== 'number') {
      return null;
    }

    return {
      input: model.input_price * 1_000_000, // Convert per-token price to per 1M tokens
      output: model.output_price * 1_000_000,
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
        const assistantMsg: any = { role: 'assistant', content: msg.content };
        if (msg.tool_calls && msg.tool_calls.length > 0) {
          assistantMsg.tool_calls = msg.tool_calls;
        }
        chatMessages.push(assistantMsg);
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
