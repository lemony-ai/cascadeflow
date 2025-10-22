/**
 * Browser-compatible OpenAI provider
 *
 * This provider uses fetch API instead of OpenAI SDK, making it
 * suitable for browser environments. It requires a backend proxy
 * or edge function to handle API keys securely.
 */

import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Tool, Message } from '../types';
import type { ModelConfig } from '../config';

/**
 * OpenAI pricing per 1K tokens (as of December 2024)
 */
const OPENAI_PRICING: Record<string, { input: number; output: number }> = {
  // GPT-5 series
  'gpt-5': { input: 0.010, output: 0.030 },
  'gpt-5-turbo': { input: 0.005, output: 0.015 },
  'gpt-5-mini': { input: 0.0003, output: 0.0012 },

  // GPT-4o series
  'gpt-4o': { input: 0.0025, output: 0.010 },
  'gpt-4o-mini': { input: 0.00015, output: 0.0006 },
  'gpt-4o-2024-11-20': { input: 0.0025, output: 0.010 },
  'gpt-4o-2024-08-06': { input: 0.0025, output: 0.010 },
  'gpt-4o-2024-05-13': { input: 0.005, output: 0.015 },

  // GPT-4 series
  'gpt-4-turbo': { input: 0.010, output: 0.030 },
  'gpt-4-turbo-2024-04-09': { input: 0.010, output: 0.030 },
  'gpt-4': { input: 0.030, output: 0.060 },
  'gpt-4-0613': { input: 0.030, output: 0.060 },
  'gpt-4-32k': { input: 0.060, output: 0.120 },

  // GPT-3.5 series
  'gpt-3.5-turbo': { input: 0.0005, output: 0.0015 },
  'gpt-3.5-turbo-0125': { input: 0.0005, output: 0.0015 },
  'gpt-3.5-turbo-1106': { input: 0.001, output: 0.002 },
};

interface BrowserOpenAIConfig extends ModelConfig {
  /**
   * Backend API endpoint (e.g., '/api/cascade' or 'https://your-edge-function.com')
   * This endpoint should forward requests to OpenAI API with your API key
   */
  proxyUrl: string;
}

/**
 * Browser-compatible OpenAI provider using fetch API
 *
 * @example
 * ```typescript
 * // With edge function
 * const provider = new BrowserOpenAIProvider({
 *   name: 'gpt-4o-mini',
 *   provider: 'openai',
 *   cost: 0.00015,
 *   proxyUrl: 'https://your-edge-function.vercel.app/api/chat'
 * });
 *
 * // With backend API
 * const provider = new BrowserOpenAIProvider({
 *   name: 'gpt-4o',
 *   provider: 'openai',
 *   cost: 0.00625,
 *   proxyUrl: '/api/cascade'
 * });
 * ```
 */
export class BrowserOpenAIProvider extends BaseProvider {
  readonly name = 'openai';
  private proxyUrl: string;

  constructor(config: BrowserOpenAIConfig) {
    super(config);
    this.proxyUrl = config.proxyUrl;

    if (!this.proxyUrl) {
      throw new Error('Browser provider requires proxyUrl');
    }
  }

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const chatMessages = this.convertToChatMessages(messages, request.systemPrompt);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const response = await fetch(this.proxyUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: request.model || this.config.name,
          messages: chatMessages,
          max_tokens: request.maxTokens || this.config.maxTokens || 1000,
          temperature: request.temperature ?? this.config.temperature ?? 0.7,
          tools,
          ...request.extra,
        }),
      });

      if (!response.ok) {
        throw new Error(`OpenAI API error: ${response.status} ${response.statusText}`);
      }

      const completion: any = await response.json();
      const choice = completion.choices?.[0];

      if (!choice) {
        throw new Error('No response from OpenAI');
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

  calculateCost(promptTokens: number, completionTokens: number, model: string): number {
    const pricing = OPENAI_PRICING[model];
    if (!pricing) {
      // Use gpt-4o-mini as fallback
      const fallback = OPENAI_PRICING['gpt-4o-mini'];
      return (
        (promptTokens / 1000) * fallback.input + (completionTokens / 1000) * fallback.output
      );
    }

    return (promptTokens / 1000) * pricing.input + (completionTokens / 1000) * pricing.output;
  }

  /**
   * Convert generic messages to OpenAI chat format
   */
  private convertToChatMessages(
    messages: Message[],
    systemPrompt?: string
  ): any[] {
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
