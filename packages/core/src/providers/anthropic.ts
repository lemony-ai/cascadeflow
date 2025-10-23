/**
 * Anthropic Claude provider implementation
 *
 * Supports: Claude 4, Claude 3.7, Claude 3.5, Claude 3
 *
 * Note: Anthropic does not support logprobs natively
 */

import Anthropic from '@anthropic-ai/sdk';
import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Tool, Message } from '../types';
import type { ModelConfig } from '../config';

/**
 * Anthropic pricing per 1M tokens (October 2025)
 * Source: https://docs.claude.com/en/docs/about-claude/pricing
 *
 * Format: Blended rate (50% input, 50% output)
 */
const ANTHROPIC_PRICING: Record<string, number> = {
  // Claude 4 Series
  'claude-opus-4.1': 45.0, // $15 in + $75 out = $45 blended
  'claude-opus-4': 45.0, // $15 in + $75 out = $45 blended
  'claude-sonnet-4.5': 9.0, // $3 in + $15 out = $9 blended
  'claude-sonnet-4': 9.0, // $3 in + $15 out = $9 blended

  // Claude 3.7 Series
  'claude-sonnet-3.7': 9.0, // $3 in + $15 out = $9 blended

  // Claude 3.5 Series
  'claude-3-5-sonnet': 9.0, // $3 in + $15 out = $9 blended
  'claude-sonnet-3-5': 9.0, // Alternative naming
  'claude-3-5-haiku': 3.0, // $1 in + $5 out = $3 blended
  'claude-haiku-3-5': 3.0, // Alternative naming

  // Claude 3 Series
  'claude-3-opus': 45.0, // $15 in + $75 out = $45 blended
  'claude-3-sonnet': 9.0, // $3 in + $15 out = $9 blended
  'claude-3-haiku': 0.75, // $0.25 in + $1.25 out = $0.75 blended
};

/**
 * Anthropic provider for Claude models
 */
export class AnthropicProvider extends BaseProvider {
  readonly name = 'anthropic';
  private client: Anthropic;

  constructor(config: ModelConfig) {
    super(config);
    const apiKey = this.getApiKey();
    this.client = new Anthropic({ apiKey });
  }

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const anthropicMessages = this.convertToAnthropicMessages(messages);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const completion = await this.client.messages.create({
        model: request.model || this.config.name,
        max_tokens: request.maxTokens || this.config.maxTokens || 1000,
        temperature: request.temperature ?? this.config.temperature ?? 0.7,
        messages: anthropicMessages,
        system: request.systemPrompt,
        tools,
        ...request.extra,
      });

      // Extract text content
      const textContent = completion.content
        .filter((block) => block.type === 'text')
        .map((block) => ('text' in block ? block.text : ''))
        .join('');

      // Extract tool calls
      const toolCalls = completion.content
        .filter((block) => block.type === 'tool_use')
        .map((block) => {
          if (block.type === 'tool_use') {
            return {
              id: block.id,
              type: 'function' as const,
              function: {
                name: block.name,
                arguments: JSON.stringify(block.input),
              },
            };
          }
          return null;
        })
        .filter((tc): tc is NonNullable<typeof tc> => tc !== null);

      return {
        content: textContent,
        model: completion.model,
        usage: {
          prompt_tokens: completion.usage.input_tokens,
          completion_tokens: completion.usage.output_tokens,
          total_tokens: completion.usage.input_tokens + completion.usage.output_tokens,
        },
        finish_reason: completion.stop_reason || undefined,
        tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
        raw: completion,
      };
    } catch (error) {
      throw this.formatError(error);
    }
  }

  calculateCost(promptTokens: number, completionTokens: number, model: string): number {
    const totalTokens = promptTokens + completionTokens;
    const modelLower = model.toLowerCase();

    // Find matching rate (try prefix match)
    for (const [modelPrefix, rate] of Object.entries(ANTHROPIC_PRICING)) {
      if (modelLower.includes(modelPrefix)) {
        return (totalTokens / 1_000_000) * rate;
      }
    }

    // Default to Sonnet pricing if unknown
    return (totalTokens / 1_000_000) * 9.0;
  }

  /**
   * Convert generic messages to Anthropic format
   */
  private convertToAnthropicMessages(messages: Message[]): any[] {
    const anthropicMessages: any[] = [];

    for (const msg of messages) {
      // Skip system messages (handled separately in systemPrompt)
      if (msg.role === 'system') {
        continue;
      }

      if (msg.role === 'user') {
        anthropicMessages.push({
          role: 'user',
          content: msg.content,
        });
      } else if (msg.role === 'assistant') {
        anthropicMessages.push({
          role: 'assistant',
          content: msg.content,
        });
      } else if (msg.role === 'tool') {
        // Anthropic format for tool results
        anthropicMessages.push({
          role: 'user',
          content: [
            {
              type: 'tool_result',
              tool_use_id: msg.tool_call_id || '',
              content: msg.content,
            },
          ],
        });
      }
    }

    return anthropicMessages;
  }

  /**
   * Convert generic tools to Anthropic format
   */
  private convertTools(tools: Tool[]): any[] {
    return tools.map((tool) => ({
      name: tool.function.name,
      description: tool.function.description,
      input_schema: tool.function.parameters,
    }));
  }
}
