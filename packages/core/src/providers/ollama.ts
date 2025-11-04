/**
 * Ollama provider implementation
 *
 * Supports: Llama 3, Llama 3.1, Llama 3.2, Mistral, CodeLlama, Phi-3, Gemma, Qwen, DeepSeek, and 100+ models
 * Pricing: FREE (local execution, no API costs)
 * Features: Local model serving, privacy-first, tool calling support
 *
 * Ollama is perfect for development, testing, and privacy-sensitive applications
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
  // Variations: deepseek-r1, deepseek-r1:latest, deepseek-r1:8b, deepseek-r1:32b, deepseek-r1:70b
  if (name.includes('deepseek-r1') || name.includes('deepseek_r1')) {
    return {
      isReasoning: true,
      provider: 'ollama',
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
    provider: 'ollama',
    supportsStreaming: true,
    supportsTools: true,
    supportsSystemMessages: true,
    supportsExtendedThinking: false,
    requiresThinkingBudget: false,
  };
}

/**
 * Ollama provider for local LLM serving
 */
export class OllamaProvider extends BaseProvider {
  readonly name = 'ollama';
  private baseUrl: string;
  private timeout: number;

  constructor(config: ModelConfig) {
    super(config);
    this.baseUrl = config.baseUrl || 'http://localhost:11434';
    this.timeout = 300000; // 5 minutes for local inference
  }

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const messages = this.normalizeMessages(request.messages);
      const ollamaMessages = this.convertToOllamaMessages(messages, request.systemPrompt);
      const tools = request.tools ? this.convertTools(request.tools) : undefined;

      // Ollama uses /api/chat endpoint for tool calling
      const response = await fetch(`${this.baseUrl}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: request.model || this.config.name,
          messages: ollamaMessages,
          stream: false,
          options: {
            temperature: request.temperature ?? this.config.temperature ?? 0.7,
            num_predict: request.maxTokens || this.config.maxTokens || 1000,
          },
          tools,
          ...request.extra,
        }),
        signal: AbortSignal.timeout(this.timeout),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ error: response.statusText }));
        throw new Error(`Ollama API error (${response.status}): ${JSON.stringify(error)}`);
      }

      const data = await response.json() as any;
      const message = data.message || {};

      // Parse tool calls if present
      const toolCalls = message.tool_calls?.map((tc: any, idx: number) => ({
        id: `call_${idx}`, // Ollama doesn't provide IDs
        type: 'function' as const,
        function: {
          name: tc.function?.name || '',
          arguments: typeof tc.function?.arguments === 'string'
            ? tc.function.arguments
            : JSON.stringify(tc.function?.arguments || {}),
        },
      }));

      // Estimate tokens (Ollama doesn't return token counts)
      const content = message.content || '';
      const promptTokens = ollamaMessages.reduce(
        (sum, msg) => sum + (msg.content?.length || 0),
        0
      ) / 4;
      const completionTokens = content.length / 4;

      return {
        content,
        model: request.model || this.config.name,
        usage: {
          prompt_tokens: Math.ceil(promptTokens),
          completion_tokens: Math.ceil(completionTokens),
          total_tokens: Math.ceil(promptTokens + completionTokens),
        },
        finish_reason: data.done ? 'stop' : 'incomplete',
        tool_calls: toolCalls,
        raw: data,
      };
    } catch (error) {
      throw this.formatError(error);
    }
  }

  calculateCost(_promptTokens: number, _completionTokens: number, _model: string): number {
    // Ollama is always free (local execution)
    return 0.0;
  }

  /**
   * Convert generic messages to Ollama format
   */
  private convertToOllamaMessages(messages: Message[], systemPrompt?: string): any[] {
    const ollamaMessages: any[] = [];

    if (systemPrompt) {
      ollamaMessages.push({ role: 'system', content: systemPrompt });
    }

    for (const msg of messages) {
      if (msg.role === 'system') {
        ollamaMessages.push({ role: 'system', content: msg.content });
      } else if (msg.role === 'user') {
        ollamaMessages.push({ role: 'user', content: msg.content });
      } else if (msg.role === 'assistant') {
        ollamaMessages.push({ role: 'assistant', content: msg.content });
      } else if (msg.role === 'tool') {
        // Ollama tool result format
        ollamaMessages.push({
          role: 'tool',
          content: msg.content,
        });
      }
    }

    return ollamaMessages;
  }

  /**
   * Convert generic tools to Ollama format (OpenAI-compatible)
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
   * Check if provider is available (Ollama doesn't require API key)
   */
  isAvailable(): boolean {
    return true; // Ollama doesn't require API key
  }

  /**
   * Override getApiKey to not require API key
   */
  protected getApiKey(): string {
    return ''; // Ollama doesn't need API key
  }

  /**
   * List available models from Ollama server
   */
  async listModels(): Promise<string[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/tags`);
      if (!response.ok) {
        throw new Error(`Failed to list models: ${response.statusText}`);
      }
      const data = await response.json() as any;
      return data.models?.map((m: any) => m.name) || [];
    } catch (error) {
      throw new Error(`Failed to list Ollama models: ${error}`);
    }
  }
}
