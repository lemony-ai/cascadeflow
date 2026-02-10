/**
 * vLLM provider implementation
 *
 * Supports: Any model compatible with vLLM server
 * Pricing: FREE (self-hosted, no API costs)
 * Features: OpenAI-compatible API, tool calling support, high-performance inference
 *
 * vLLM provides:
 * - PagedAttention for efficient memory usage
 * - Continuous batching for high throughput
 * - 24x faster than standard serving
 * - Full logprobs support
 * - Tool/function calling support
 */

import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Tool, Message, ReasoningModelInfo } from '../types';
import type { ModelConfig } from '../config';

/**
 * Detect if model is DeepSeek-R1 reasoning model
 *
 * @param modelName - Model name to check
 * @returns Model capabilities
 */
export function getReasoningModelInfo(modelName: string): ReasoningModelInfo {
  const name = modelName.toLowerCase();

  // DeepSeek-R1 - Chain-of-thought reasoning model
  // Variations: deepseek-r1, deepseek-r1-distill, etc.
  if (name.includes('deepseek-r1') || name.includes('deepseek_r1')) {
    return {
      isReasoning: true,
      provider: 'vllm',
      supportsStreaming: true,
      supportsTools: true,
      supportsSystemMessages: true,
      supportsExtendedThinking: false,
      requiresThinkingBudget: false,
    };
  }

  // Standard models (no reasoning)
  return {
    isReasoning: false,
    provider: 'vllm',
    supportsStreaming: true,
    supportsTools: true,
    supportsSystemMessages: true,
    supportsExtendedThinking: false,
    requiresThinkingBudget: false,
  };
}

/**
 * vLLM provider for high-performance local inference
 */
export class VLLMProvider extends BaseProvider {
  readonly name = 'vllm';
  private baseUrl: string;
  private timeout: number;

  constructor(config: ModelConfig) {
    super(config);
    this.baseUrl = config.baseUrl || process.env['VLLM_BASE_URL'] || 'http://localhost:8000/v1';
    this.timeout = 300000; // 5 minutes for large models (reasoning models like DeepSeek R1 need more time)
  }

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const vllmMessages = this.convertToVLLMMessages(messages, request.systemPrompt);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      const apiKey = this.config.apiKey || process.env['VLLM_API_KEY'] || '';
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
      }

      const response = await fetch(`${this.baseUrl}/chat/completions`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          model: request.model || this.config.name,
          messages: vllmMessages,
          max_tokens: request.maxTokens || this.config.maxTokens || 1000,
          temperature: request.temperature ?? this.config.temperature ?? 0.7,
          tools,
          ...request.extra,
        }),
        signal: AbortSignal.timeout(this.timeout),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: response.statusText }));
        throw new Error(`vLLM API error (${response.status}): ${JSON.stringify(error)}`);
      }

      const data = await response.json() as any;
      const choice = data.choices?.[0];

      if (!choice) {
        throw new Error('No response from vLLM');
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

  calculateCost(_promptTokens: number, _completionTokens: number, _model: string): number {
    // vLLM is self-hosted, so use user-defined cost from config or default to 0
    return this.config.cost || 0.0;
  }

  /**
   * Convert generic messages to vLLM/OpenAI format
   */
  private convertToVLLMMessages(messages: Message[], systemPrompt?: string): any[] {
    const vllmMessages: any[] = [];

    if (systemPrompt) {
      vllmMessages.push({ role: 'system', content: systemPrompt });
    }

    for (const msg of messages) {
      if (msg.role === 'system') {
        vllmMessages.push({ role: 'system', content: msg.content });
      } else if (msg.role === 'user') {
        vllmMessages.push({ role: 'user', content: msg.content });
      } else if (msg.role === 'assistant') {
        const assistantMsg: any = { role: 'assistant', content: msg.content };
        if (msg.tool_calls && msg.tool_calls.length > 0) {
          assistantMsg.tool_calls = msg.tool_calls;
        }
        vllmMessages.push(assistantMsg);
      } else if (msg.role === 'tool') {
        vllmMessages.push({
          role: 'tool',
          content: msg.content,
          tool_call_id: msg.tool_call_id || '',
        });
      }
    }

    return vllmMessages;
  }

  /**
   * Convert generic tools to OpenAI format (vLLM uses same format)
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

  /**
   * Check if provider is available (vLLM doesn't always require API key)
   */
  isAvailable(): boolean {
    return true; // vLLM may or may not require API key depending on setup
  }

  /**
   * Override getApiKey to make it optional
   */
  protected getApiKey(): string {
    // API key is optional for vLLM
    return this.config.apiKey || process.env['VLLM_API_KEY'] || '';
  }

  /**
   * List available models from vLLM server
   */
  async listModels(): Promise<string[]> {
    try {
      const apiKey = this.getApiKey();
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
      }

      const response = await fetch(`${this.baseUrl}/models`, {
        headers,
      });

      if (!response.ok) {
        throw new Error(`Failed to list models: ${response.statusText}`);
      }

      const data = await response.json() as any;
      return data.data?.map((m: any) => m.id) || [];
    } catch (error) {
      throw new Error(`Failed to list vLLM models: ${error}`);
    }
  }
}
