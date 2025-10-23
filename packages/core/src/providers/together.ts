/**
 * Together AI provider implementation
 *
 * Supports: Llama 4, Llama 3.3, Llama 3.1, DeepSeek, Qwen, Mixtral, and many more
 * Pricing: Pay-per-token pricing (competitive rates)
 * Features: OpenAI-compatible API, full tool calling support
 *
 * Together AI offers 100+ optimized open-source models with fast inference
 */

import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Tool, Message } from '../types';
import type { ModelConfig } from '../config';

/**
 * Together AI pricing per 1M tokens (October 2025)
 * Source: https://www.together.ai/pricing
 * Format: [input_rate, output_rate] per 1M tokens
 */
const TOGETHER_PRICING: Record<string, [number, number]> = {
  // Llama 4 Series
  'llama-4-maverick': [0.27, 0.85],
  'llama-4-scout': [0.18, 0.59],

  // Llama 3.3 Series
  'llama-3.3-70b': [0.59, 0.79],
  'llama3.3-70b': [0.59, 0.79],

  // Llama 3.1 Series (most popular)
  'llama-3.1-405b': [3.5, 3.5],
  'llama-3.1-70b': [0.59, 0.79],
  'llama-3.1-8b': [0.05, 0.08],
  'llama3.1-405b': [3.5, 3.5],
  'llama3.1-70b': [0.59, 0.79],
  'llama3.1-8b': [0.05, 0.08],

  // Llama 3.2 Series
  'llama-3.2-90b': [1.2, 1.2],
  'llama-3.2-11b': [0.18, 0.18],
  'llama-3.2-8b': [0.1, 0.1],
  'llama-3.2-3b': [0.06, 0.06],
  'llama-3.2-1b': [0.06, 0.06],

  // Llama 3 Series
  'llama-3-70b': [0.59, 0.79],
  'llama-3-8b': [0.05, 0.08],
  'llama3-70b': [0.59, 0.79],
  'llama3-8b': [0.05, 0.08],

  // DeepSeek Series
  'deepseek-r1-distill-llama-70b': [2.0, 2.0],
  'deepseek-r1-distill-qwen-14b': [1.6, 1.6],
  'deepseek-r1-distill-qwen-1.5b': [0.18, 0.18],
  'deepseek-r1-throughput': [0.55, 2.19],
  'deepseek-r1': [3.0, 7.0],
  'deepseek-v3': [1.25, 1.25],

  // Qwen Series
  'qwen3-235b': [0.2, 0.6],
  'qwen3-coder-480b': [2.0, 2.0],
  'qwen2.5-72b': [1.2, 1.2],
  'qwen2.5-coder-32b': [0.8, 0.8],
  'qwen2.5-14b': [0.8, 0.8],
  'qwen2.5-7b': [0.3, 0.3],
  'qwq-32b': [1.2, 1.2],

  // Kimi Series
  'kimi-k2': [1.0, 3.0],

  // Mixtral Series
  'mixtral-8x7b': [0.6, 0.6],
  'mistral-saba': [0.79, 0.79],
};

/**
 * Together AI provider for fast inference of open-source models
 */
export class TogetherProvider extends BaseProvider {
  readonly name = 'together';
  private baseUrl = 'https://api.together.xyz/v1';

  constructor(config: ModelConfig) {
    super(config);
  }

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const apiKey = this.getApiKey();
      const messages = this.normalizeMessages(request.messages);
      const togetherMessages = this.convertToTogetherMessages(messages, request.systemPrompt);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model: request.model || this.config.name,
          messages: togetherMessages,
          max_tokens: request.maxTokens || this.config.maxTokens || 1000,
          temperature: request.temperature ?? this.config.temperature ?? 0.7,
          tools,
          ...request.extra,
        }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: response.statusText }));
        throw new Error(`Together AI API error (${response.status}): ${JSON.stringify(error)}`);
      }

      const data = await response.json() as any;
      const choice = data.choices?.[0];

      if (!choice) {
        throw new Error('No response from Together AI');
      }

      return {
        content: choice.message?.content || '',
        model: data.model,
        usage: data.usage
          ? {
              prompt_tokens: data.usage.prompt_tokens,
              completion_tokens: data.usage.completion_tokens,
              total_tokens: data.usage.total_tokens,
            }
          : undefined,
        finish_reason: choice.finish_reason || undefined,
        tool_calls: choice.message?.tool_calls?.map((tc: any) => ({
          id: tc.id,
          type: 'function' as const,
          function: {
            name: tc.function.name,
            arguments: tc.function.arguments,
          },
        })),
        raw: data,
      };
    } catch (error) {
      throw this.formatError(error);
    }
  }

  calculateCost(promptTokens: number, completionTokens: number, model: string): number {
    const modelLower = model.toLowerCase();

    // Find matching model pricing
    let inputRate = 0.2; // Default fallback
    let outputRate = 0.2;

    for (const [modelPrefix, [inp, out]] of Object.entries(TOGETHER_PRICING)) {
      if (modelLower.includes(modelPrefix)) {
        inputRate = inp;
        outputRate = out;
        break;
      }
    }

    // Calculate cost with split pricing
    const inputCost = (promptTokens / 1_000_000) * inputRate;
    const outputCost = (completionTokens / 1_000_000) * outputRate;

    return inputCost + outputCost;
  }

  /**
   * Convert generic messages to Together AI/OpenAI format
   */
  private convertToTogetherMessages(messages: Message[], systemPrompt?: string): any[] {
    const togetherMessages: any[] = [];

    if (systemPrompt) {
      togetherMessages.push({ role: 'system', content: systemPrompt });
    }

    for (const msg of messages) {
      if (msg.role === 'system') {
        togetherMessages.push({ role: 'system', content: msg.content });
      } else if (msg.role === 'user') {
        togetherMessages.push({ role: 'user', content: msg.content });
      } else if (msg.role === 'assistant') {
        togetherMessages.push({ role: 'assistant', content: msg.content });
      } else if (msg.role === 'tool') {
        togetherMessages.push({
          role: 'tool',
          content: msg.content,
          tool_call_id: msg.tool_call_id || '',
        });
      }
    }

    return togetherMessages;
  }

  /**
   * Convert generic tools to OpenAI format (Together AI uses same format)
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
