/**
 * OpenAI provider implementation with automatic environment detection
 *
 * Works in both Node.js (using OpenAI SDK) and browser (using fetch API).
 * Automatically detects the runtime environment and uses the appropriate method.
 */

import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Tool, Message, ReasoningModelInfo } from '../types';
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
 * OpenAI pricing per 1K tokens (as of January 2025)
 * Source: https://openai.com/api/pricing/
 */
const OPENAI_PRICING: Record<string, { input: number; output: number }> = {
  // GPT-5 series (current flagship - released August 2025)
  // 50% cheaper input than GPT-4o, superior performance on coding, reasoning, math
  'gpt-5': { input: 0.00125, output: 0.010 },
  'gpt-5-mini': { input: 0.00025, output: 0.002 },
  'gpt-5-nano': { input: 0.00005, output: 0.0004 },
  'gpt-5-chat-latest': { input: 0.00125, output: 0.010 },

  // GPT-4o series (previous flagship)
  'gpt-4o': { input: 0.0025, output: 0.010 },
  'gpt-4o-mini': { input: 0.00015, output: 0.0006 },
  'gpt-4o-2024-11-20': { input: 0.0025, output: 0.010 },
  'gpt-4o-2024-08-06': { input: 0.0025, output: 0.010 },
  'gpt-4o-2024-05-13': { input: 0.005, output: 0.015 },

  // O1 series (reasoning models)
  'o1-preview': { input: 0.015, output: 0.060 },
  'o1-mini': { input: 0.003, output: 0.012 },
  'o1': { input: 0.015, output: 0.060 }, // o1-2024-12-17
  'o1-2024-12-17': { input: 0.015, output: 0.060 },

  // O3 series (reasoning models - future)
  'o3-mini': { input: 0.001, output: 0.005 },

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
 * Detect if model is a reasoning model and get its capabilities
 *
 * @param modelName - Model name to check
 * @returns Model capabilities
 */
export function getReasoningModelInfo(modelName: string): ReasoningModelInfo {
  const name = modelName.toLowerCase();

  // O1 preview/mini (original reasoning models)
  if (name.includes('o1-preview') || name.includes('o1-mini')) {
    return {
      isReasoning: true,
      provider: 'openai',
      supportsStreaming: true,
      supportsTools: false,
      supportsSystemMessages: false,
      supportsReasoningEffort: false,
      requiresMaxCompletionTokens: false,
    };
  }

  // O1 (2024-12-17) - more capable
  if (name.includes('o1-2024-12-17') || (name === 'o1')) {
    return {
      isReasoning: true,
      provider: 'openai',
      supportsStreaming: false, // Not supported
      supportsTools: false,
      supportsSystemMessages: false,
      supportsReasoningEffort: true,
      requiresMaxCompletionTokens: true,
    };
  }

  // O3-mini (future reasoning model)
  if (name.includes('o3-mini')) {
    return {
      isReasoning: true,
      provider: 'openai',
      supportsStreaming: true,
      supportsTools: true,
      supportsSystemMessages: false,
      supportsReasoningEffort: true,
      requiresMaxCompletionTokens: true,
    };
  }

  // Not a reasoning model
  return {
    isReasoning: false,
    provider: 'openai',
    supportsStreaming: true,
    supportsTools: true,
    supportsSystemMessages: true,
    supportsReasoningEffort: false,
    requiresMaxCompletionTokens: false,
  };
}

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

      const modelName = request.model || this.config.name;
      // GPT-5 series doesn't support logprobs yet (as of January 2025)
      const supportsLogprobs = !modelName.startsWith('gpt-5');
      const isGpt5 = modelName.startsWith('gpt-5');
      const maxTokens = request.maxTokens || this.config.maxTokens || 1000;

      const streamConfig: any = {
        model: modelName,
        messages: chatMessages,
        tools,
        stream: true,
        ...request.extra,
      };

      // GPT-5 only supports temperature=1 (default), doesn't allow custom values
      if (!isGpt5) {
        streamConfig.temperature = request.temperature ?? this.config.temperature ?? 0.7;
      }

      // GPT-5 uses max_completion_tokens instead of max_tokens
      if (isGpt5) {
        streamConfig.max_completion_tokens = maxTokens;
      } else {
        streamConfig.max_tokens = maxTokens;
      }

      if (supportsLogprobs) {
        streamConfig.logprobs = true;
        streamConfig.top_logprobs = 1;
      }

      const stream = await this.client.chat.completions.create(streamConfig);

      for await (const chunk of stream) {
        const delta = chunk.choices[0]?.delta;
        if (!delta) continue;

        const content = delta.content || '';
        const done = chunk.choices[0]?.finish_reason !== null;

        // Extract logprob for this chunk if available
        let logprob: number | undefined;
        if (chunk.choices[0]?.logprobs?.content && chunk.choices[0].logprobs.content.length > 0) {
          const firstToken = chunk.choices[0].logprobs.content[0];
          if (firstToken && firstToken.logprob !== null) {
            logprob = firstToken.logprob;
          }
        }

        yield {
          content,
          done,
          finish_reason: chunk.choices[0]?.finish_reason || undefined,
          logprob,
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

      const modelName = request.model || this.config.name;
      // GPT-5 series doesn't support logprobs yet (as of January 2025)
      const supportsLogprobs = !modelName.startsWith('gpt-5');
      const isGpt5 = modelName.startsWith('gpt-5');
      const maxTokens = request.maxTokens || this.config.maxTokens || 1000;

      const requestBody: any = {
        model: modelName,
        messages: chatMessages,
        tools,
        stream: true,
        ...request.extra,
      };

      // GPT-5 only supports temperature=1 (default), doesn't allow custom values
      if (!isGpt5) {
        requestBody.temperature = request.temperature ?? this.config.temperature ?? 0.7;
      }

      // GPT-5 uses max_completion_tokens instead of max_tokens
      if (isGpt5) {
        requestBody.max_completion_tokens = maxTokens;
      } else {
        requestBody.max_tokens = maxTokens;
      }

      if (supportsLogprobs) {
        requestBody.logprobs = true;
        requestBody.top_logprobs = 1;
      }

      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.getApiKey()}`,
        },
        body: JSON.stringify(requestBody),
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

              // Extract logprob for this chunk if available
              let logprob: number | undefined;
              if (parsed.choices[0]?.logprobs?.content && parsed.choices[0].logprobs.content.length > 0) {
                const firstToken = parsed.choices[0].logprobs.content[0];
                if (firstToken && firstToken.logprob !== null) {
                  logprob = firstToken.logprob;
                }
              }

              yield {
                content,
                done: isFinished,
                finish_reason: parsed.choices[0]?.finish_reason || undefined,
                logprob,
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
      const modelName = request.model || this.config.name;

      // Auto-detect reasoning model capabilities
      const modelInfo = getReasoningModelInfo(modelName);

      // Convert messages based on model capabilities
      const chatMessages = this.convertToChatMessages(
        messages,
        modelInfo.supportsSystemMessages ? request.systemPrompt : undefined
      );

      // If system prompt provided but not supported, prepend to first user message
      if (!modelInfo.supportsSystemMessages && request.systemPrompt) {
        for (let i = 0; i < chatMessages.length; i++) {
          if (chatMessages[i].role === 'user') {
            chatMessages[i].content = `${request.systemPrompt}\n\n${chatMessages[i].content}`;
            break;
          }
        }
      }

      // Don't pass tools if not supported (reasoning models)
      const tools = modelInfo.supportsTools && request.tools
        ? this.convertTools(request.tools)
        : undefined;

      // GPT-5 series doesn't support logprobs yet (as of January 2025)
      const supportsLogprobs = !modelName.startsWith('gpt-5') && !modelInfo.isReasoning;
      const isGpt5 = modelName.startsWith('gpt-5');
      const maxTokens = request.maxTokens || this.config.maxTokens || 1000;

      const completionConfig: any = {
        model: modelName,
        messages: chatMessages,
        tools,
        ...request.extra,
      };

      // GPT-5 only supports temperature=1 (default), doesn't allow custom values
      if (!isGpt5 && !modelInfo.isReasoning) {
        completionConfig.temperature = request.temperature ?? this.config.temperature ?? 0.7;
      }

      // Reasoning models and GPT-5 use max_completion_tokens
      if (isGpt5 || modelInfo.requiresMaxCompletionTokens) {
        completionConfig.max_completion_tokens = maxTokens;
      } else {
        completionConfig.max_tokens = maxTokens;
      }

      // Add reasoning_effort if supported and provided
      if (modelInfo.supportsReasoningEffort && request.extra?.reasoning_effort) {
        completionConfig.reasoning_effort = request.extra.reasoning_effort;
      }

      if (supportsLogprobs) {
        completionConfig.logprobs = true;
        completionConfig.top_logprobs = 1;
      }

      const completion = await this.client.chat.completions.create(completionConfig);

      const choice = completion.choices[0];
      if (!choice) {
        throw new Error('No response from OpenAI');
      }

      // Extract logprobs if available
      let logprobs: number[] | undefined;
      if (choice.logprobs && choice.logprobs.content) {
        logprobs = choice.logprobs.content
          .filter((item: any) => item && item.logprob !== null)
          .map((item: any) => item.logprob);
      }

      // Extract reasoning tokens if available
      const usage = completion.usage
        ? {
            prompt_tokens: completion.usage.prompt_tokens,
            completion_tokens: completion.usage.completion_tokens,
            total_tokens: completion.usage.total_tokens,
            reasoning_tokens: completion.usage.completion_tokens_details?.reasoning_tokens,
            completion_tokens_details: completion.usage.completion_tokens_details,
          }
        : undefined;

      return {
        content: choice.message.content || '',
        model: completion.model,
        usage,
        finish_reason: choice.finish_reason,
        tool_calls: choice.message.tool_calls?.map((tc: any) => ({
          id: tc.id,
          type: 'function',
          function: {
            name: tc.function.name,
            arguments: tc.function.arguments,
          },
        })),
        logprobs,
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

      const modelName = request.model || this.config.name;
      // GPT-5 series doesn't support logprobs yet (as of January 2025)
      const supportsLogprobs = !modelName.startsWith('gpt-5');
      const isGpt5 = modelName.startsWith('gpt-5');
      const maxTokens = request.maxTokens || this.config.maxTokens || 1000;

      const requestBody: any = {
        model: modelName,
        messages: chatMessages,
        tools,
        ...request.extra,
      };

      // GPT-5 only supports temperature=1 (default), doesn't allow custom values
      if (!isGpt5) {
        requestBody.temperature = request.temperature ?? this.config.temperature ?? 0.7;
      }

      // GPT-5 uses max_completion_tokens instead of max_tokens
      if (isGpt5) {
        requestBody.max_completion_tokens = maxTokens;
      } else {
        requestBody.max_tokens = maxTokens;
      }

      if (supportsLogprobs) {
        requestBody.logprobs = true;
        requestBody.top_logprobs = 1;
      }

      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${this.getApiKey()}`,
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        throw new Error(`OpenAI API error: ${response.status} ${response.statusText}`);
      }

      const completion: any = await response.json();
      const choice = completion.choices?.[0];

      if (!choice) {
        throw new Error('No response from OpenAI');
      }

      // Extract logprobs if available
      let logprobs: number[] | undefined;
      if (choice.logprobs && choice.logprobs.content) {
        logprobs = choice.logprobs.content
          .filter((item: any) => item && item.logprob !== null)
          .map((item: any) => item.logprob);
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
        logprobs,
        raw: completion,
      };
    } catch (error) {
      throw this.formatError(error);
    }
  }

  /**
   * Calculate cost including reasoning tokens
   *
   * @param promptTokens - Input tokens
   * @param completionTokens - Output tokens (includes reasoning tokens for o1/o3)
   * @param model - Model name
   * @param reasoningTokens - Reasoning tokens (optional, already included in completionTokens)
   * @returns Cost in USD
   */
  calculateCost(
    promptTokens: number,
    completionTokens: number,
    model: string,
    _reasoningTokens?: number
  ): number {
    // Normalize model name to lowercase for case-insensitive matching
    const modelLower = model.toLowerCase();

    // Find model-specific pricing (exact match, case-insensitive)
    let pricing = OPENAI_PRICING[modelLower];

    // Try prefix matching for versioned models
    if (!pricing) {
      for (const [key, value] of Object.entries(OPENAI_PRICING)) {
        if (modelLower.startsWith(key)) {
          pricing = value;
          break;
        }
      }
    }

    // Fallback to gpt-4o-mini for unknown models
    if (!pricing) {
      pricing = OPENAI_PRICING['gpt-4o-mini'];
    }

    // Note: For o1/o3 models, reasoning tokens are already included in completion_tokens
    // from the API, so we don't need to add them separately. The API returns:
    // - completion_tokens: total output tokens (including reasoning)
    // - completion_tokens_details.reasoning_tokens: breakdown of reasoning portion
    const inputCost = (promptTokens / 1000) * pricing.input;
    const outputCost = (completionTokens / 1000) * pricing.output;

    return inputCost + outputCost;
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
