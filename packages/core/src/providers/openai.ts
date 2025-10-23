/**
 * OpenAI provider implementation with automatic environment detection
 *
 * Works in both Node.js (using OpenAI SDK) and browser (using fetch API).
 * Automatically detects the runtime environment and uses the appropriate method.
 */

import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Tool, Message } from '../types';
import type { ModelConfig } from '../config';
import type { StreamChunk } from '../streaming';

// Conditional import for Node.js environment
let OpenAI: any;
try {
  // Only import in Node.js environment
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  if (typeof (globalThis as any).window === 'undefined') {
    OpenAI = require('openai').default;
  }
} catch {
  // SDK not available (browser or missing dependency)
  OpenAI = null;
}

// OpenAI types
type ChatCompletionMessageParam = any; // Simplified for MVP
type ChatCompletionTool = any; // Simplified for MVP

/**
 * OpenAI pricing per 1K tokens (as of December 2024)
 * Source: https://openai.com/api/pricing/
 */
const OPENAI_PRICING: Record<string, { input: number; output: number }> = {
  // GPT-5 series (future/preview - pricing TBD)
  'gpt-5': { input: 0.010, output: 0.030 },
  'gpt-5-turbo': { input: 0.005, output: 0.015 },
  'gpt-5-mini': { input: 0.0003, output: 0.0012 },

  // GPT-4o series (current flagship)
  'gpt-4o': { input: 0.0025, output: 0.010 },
  'gpt-4o-mini': { input: 0.00015, output: 0.0006 },
  'gpt-4o-2024-11-20': { input: 0.0025, output: 0.010 },
  'gpt-4o-2024-08-06': { input: 0.0025, output: 0.010 },
  'gpt-4o-2024-05-13': { input: 0.005, output: 0.015 },

  // GPT-4 series (previous generation)
  'gpt-4-turbo': { input: 0.010, output: 0.030 },
  'gpt-4-turbo-2024-04-09': { input: 0.010, output: 0.030 },
  'gpt-4': { input: 0.030, output: 0.060 },
  'gpt-4-0613': { input: 0.030, output: 0.060 },
  'gpt-4-32k': { input: 0.060, output: 0.120 },

  // GPT-3.5 series (legacy)
  'gpt-3.5-turbo': { input: 0.0005, output: 0.0015 },
  'gpt-3.5-turbo-0125': { input: 0.0005, output: 0.0015 },
  'gpt-3.5-turbo-1106': { input: 0.001, output: 0.002 },
};

/**
 * OpenAI provider with automatic environment detection
 *
 * Automatically uses:
 * - OpenAI SDK in Node.js
 * - Fetch API in browser
 */
export class OpenAIProvider extends BaseProvider {
  readonly name = 'openai';
  private client: any = null;
  private useSDK: boolean;
  private baseUrl: string;

  constructor(config: ModelConfig) {
    super(config);
    const apiKey = this.getApiKey();

    // Detect environment and initialize accordingly
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
    this.useSDK = typeof (globalThis as any).window === 'undefined' && OpenAI !== null;
    this.baseUrl = config.baseUrl || 'https://api.openai.com/v1';

    if (this.useSDK) {
      // Node.js: Use SDK
      this.client = new OpenAI({ apiKey });
    }
    // Browser: Will use fetch in generate()
  }

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    if (this.useSDK) {
      return this.generateWithSDK(request);
    } else {
      return this.generateWithFetch(request);
    }
  }

  /**
   * Stream a completion
   */
  async *stream(request: ProviderRequest): AsyncIterable<StreamChunk> {
    if (this.useSDK) {
      yield* this.streamWithSDK(request);
    } else {
      yield* this.streamWithFetch(request);
    }
  }

  /**
   * Stream using OpenAI SDK (Node.js)
   */
  private async *streamWithSDK(request: ProviderRequest): AsyncIterable<StreamChunk> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const chatMessages = this.convertToChatMessages(messages, request.systemPrompt);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const stream = await this.client.chat.completions.create({
        model: request.model || this.config.name,
        messages: chatMessages,
        max_tokens: request.maxTokens || this.config.maxTokens || 1000,
        temperature: request.temperature ?? this.config.temperature ?? 0.7,
        tools,
        stream: true,
        ...request.extra,
      });

      for await (const chunk of stream) {
        const delta = chunk.choices[0]?.delta;
        if (!delta) continue;

        const content = delta.content || '';
        const done = chunk.choices[0]?.finish_reason !== null;

        yield {
          content,
          done,
          finish_reason: chunk.choices[0]?.finish_reason || undefined,
          raw: chunk,
        };
      }
    } catch (error) {
      throw this.formatError(error);
    }
  }

  /**
   * Stream using fetch API (Browser) with SSE parsing
   */
  private async *streamWithFetch(request: ProviderRequest): AsyncIterable<StreamChunk> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const chatMessages = this.convertToChatMessages(messages, request.systemPrompt);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.getApiKey()}`,
        },
        body: JSON.stringify({
          model: request.model || this.config.name,
          messages: chatMessages,
          max_tokens: request.maxTokens || this.config.maxTokens || 1000,
          temperature: request.temperature ?? this.config.temperature ?? 0.7,
          tools,
          stream: true,
          ...request.extra,
        }),
      });

      if (!response.ok) {
        throw new Error(`OpenAI API error: ${response.status} ${response.statusText}`);
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
   * Generate using OpenAI SDK (Node.js)
   */
  private async generateWithSDK(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const chatMessages = this.convertToChatMessages(messages, request.systemPrompt);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const completion = await this.client.chat.completions.create({
        model: request.model || this.config.name,
        messages: chatMessages,
        max_tokens: request.maxTokens || this.config.maxTokens || 1000,
        temperature: request.temperature ?? this.config.temperature ?? 0.7,
        tools,
        ...request.extra,
      });

      const choice = completion.choices[0];
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

  /**
   * Generate using fetch API (Browser)
   */
  private async generateWithFetch(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const chatMessages = this.convertToChatMessages(messages, request.systemPrompt);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.getApiKey()}`,
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
      // Use gpt-4o-mini as fallback for unknown models
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
  ): ChatCompletionMessageParam[] {
    const chatMessages: ChatCompletionMessageParam[] = [];

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
  private convertTools(tools: Tool[]): ChatCompletionTool[] {
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
