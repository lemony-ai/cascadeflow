/**
 * Groq provider implementation
 *
 * Supports: Llama 4, Llama 3.3, Llama 3.1, DeepSeek, Qwen, Mixtral, Mistral
 * Pricing: Pay-as-you-go token pricing (as low as $0.05/million tokens)
 * Note: Groq uses OpenAI-compatible API but does NOT support logprobs
 */

import Groq from 'groq-sdk';
import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Tool, Message } from '../types';
import type { ModelConfig } from '../config';

/**
 * Groq pricing per 1M tokens (October 2025)
 * Source: https://groq.com/pricing
 * Format: [input_rate, output_rate] per 1M tokens
 */
const GROQ_PRICING: Record<string, [number, number]> = {
  // Llama 4 Series
  'llama-4-scout': [0.11, 0.34],
  'llama-4-maverick': [0.20, 0.60],
  'llama-guard-4': [0.20, 0.20],

  // Llama 3.3 Series
  'llama-3.3-70b': [0.59, 0.79],
  'llama3-70b': [0.59, 0.79], // Alias

  // Llama 3.1 Series (most popular)
  'llama-3.1-8b': [0.05, 0.08],
  'llama-3.1-70b': [0.59, 0.79],
  'llama3-8b': [0.05, 0.08], // Alias

  // Llama 3 Series
  'llama-3-8b': [0.05, 0.08],
  'llama-3-70b': [0.59, 0.79],
  'llama3-groq': [0.05, 0.08],

  // DeepSeek Series
  'deepseek-r1': [0.75, 0.99],

  // Qwen Series
  'qwen3-32b': [0.29, 0.59],

  // Mixtral Series
  'mixtral-8x7b': [0.24, 0.24],

  // Mistral Series
  'mistral-saba': [0.79, 0.79],

  // Guard Models
  'llama-guard-3': [0.20, 0.20],

  // OpenAI Models (recommended replacement for deprecated Gemma)
  'openai/gpt-oss-20b': [0.11, 0.34],
};

/**
 * Groq provider for fast inference
 */
export class GroqProvider extends BaseProvider {
  readonly name = 'groq';
  private client: Groq;

  constructor(config: ModelConfig) {
    super(config);
    const apiKey = this.getApiKey();
    this.client = new Groq({ apiKey });
  }

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const groqMessages = this.convertToGroqMessages(messages, request.systemPrompt);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const completion = await this.client.chat.completions.create({
        model: request.model || this.config.name,
        messages: groqMessages,
        max_tokens: request.maxTokens || this.config.maxTokens || 1000,
        temperature: request.temperature ?? this.config.temperature ?? 0.7,
        tools,
        ...request.extra,
      });

      const choice = completion.choices[0];
      if (!choice) {
        throw new Error('No response from Groq');
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
        finish_reason: choice.finish_reason || undefined,
        tool_calls: choice.message.tool_calls?.map((tc) => ({
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

  calculateCost(promptTokens: number, completionTokens: number, model: string): number {
    const modelLower = model.toLowerCase();

    // Find matching model pricing
    let inputRate = 0.05; // Default to Llama 3.1 8B
    let outputRate = 0.08;

    for (const [modelPrefix, [inp, out]] of Object.entries(GROQ_PRICING)) {
      if (modelLower.startsWith(modelPrefix)) {
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
   * Convert generic messages to Groq/OpenAI format
   */
  private convertToGroqMessages(messages: Message[], systemPrompt?: string): any[] {
    const groqMessages: any[] = [];

    if (systemPrompt) {
      groqMessages.push({ role: 'system', content: systemPrompt });
    }

    for (const msg of messages) {
      if (msg.role === 'system') {
        groqMessages.push({ role: 'system', content: msg.content });
      } else if (msg.role === 'user') {
        groqMessages.push({ role: 'user', content: msg.content });
      } else if (msg.role === 'assistant') {
        groqMessages.push({ role: 'assistant', content: msg.content });
      } else if (msg.role === 'tool') {
        groqMessages.push({
          role: 'tool',
          content: msg.content,
          tool_call_id: msg.tool_call_id || '',
        });
      }
    }

    return groqMessages;
  }

  /**
   * Convert generic tools to OpenAI format (Groq uses same format)
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
