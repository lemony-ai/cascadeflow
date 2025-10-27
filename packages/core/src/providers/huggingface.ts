/**
 * HuggingFace provider implementation
 *
 * Supports three endpoint types:
 * 1. Serverless Inference API (free tier) - UNRELIABLE, NO TOOLS
 * 2. Inference Endpoints (paid, dedicated) - RELIABLE, TOOLS MAYBE
 * 3. Inference Providers (pay-per-use) - RELIABLE, TOOLS YES
 *
 * Pricing: Varies by endpoint type
 * Features: Multiple endpoint options, limited tool calling support
 *
 * Note: Serverless API is notoriously unreliable. Consider using Groq or Together AI instead.
 */

import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Tool, Message } from '../types';
import type { ModelConfig } from '../config';

/**
 * HuggingFace endpoint types
 */
export enum HuggingFaceEndpointType {
  SERVERLESS = 'serverless',
  INFERENCE_ENDPOINT = 'inference_endpoint',
  INFERENCE_PROVIDERS = 'inference_providers',
}

/**
 * HuggingFace provider for multiple inference options
 */
export class HuggingFaceProvider extends BaseProvider {
  readonly name = 'huggingface';
  private baseUrl: string;
  private endpointType: HuggingFaceEndpointType;

  constructor(config: ModelConfig) {
    super(config);

    // Detect endpoint type from base URL
    this.endpointType = this.detectEndpointType(config.baseUrl);
    this.baseUrl = this.getHFBaseUrl(config.baseUrl);
  }

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    try {
      const apiKey = this.getApiKey();
      const messages = this.normalizeMessages(request.messages);

      // Check if tools are requested with unsupported endpoint
      if (request.tools && this.endpointType === HuggingFaceEndpointType.SERVERLESS) {
        throw new Error(
          'Tool calling is NOT supported on HuggingFace Serverless API. ' +
          'Use Inference Providers or Inference Endpoints instead.'
        );
      }

      // Build request based on endpoint type
      if (this.endpointType === HuggingFaceEndpointType.SERVERLESS) {
        return await this.generateServerless(request, apiKey);
      } else {
        return await this.generateOpenAICompatible(request, messages, apiKey);
      }
    } catch (error) {
      throw this.formatError(error);
    }
  }

  /**
   * Generate using Serverless Inference API (free tier)
   */
  private async generateServerless(
    request: ProviderRequest,
    apiKey: string
  ): Promise<ProviderResponse> {
    const messages = this.normalizeMessages(request.messages);
    let prompt = messages.map((m) => m.content).join('\n');

    if (request.systemPrompt) {
      prompt = `${request.systemPrompt}\n\n${prompt}`;
    }

    const response = await fetch(`${this.baseUrl}/models/${request.model || this.config.name}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        inputs: prompt,
        parameters: {
          max_new_tokens: request.maxTokens || this.config.maxTokens || 512,
          temperature: request.temperature ?? this.config.temperature ?? 0.7,
          return_full_text: false,
        },
        options: {
          wait_for_model: true,
          use_cache: false,
        },
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(`HuggingFace API error (${response.status}): ${JSON.stringify(error)}`);
    }

    const data = await response.json() as any;
    const content = Array.isArray(data) ? data[0]?.generated_text : data?.generated_text || '';

    // Estimate tokens
    const promptTokens = Math.ceil(prompt.length / 4);
    const completionTokens = Math.ceil(content.length / 4);

    return {
      content,
      model: request.model || this.config.name,
      usage: {
        prompt_tokens: promptTokens,
        completion_tokens: completionTokens,
        total_tokens: promptTokens + completionTokens,
      },
      finish_reason: 'stop',
      raw: data,
    };
  }

  /**
   * Generate using OpenAI-compatible endpoints (Inference Endpoints & Providers)
   */
  private async generateOpenAICompatible(
    request: ProviderRequest,
    messages: Message[],
    apiKey: string
  ): Promise<ProviderResponse> {
    const hfMessages = this.convertToHuggingFaceMessages(messages, request.systemPrompt);
    const tools = request.tools ? this.convertTools(request.tools) : undefined;

    const url = this.endpointType === HuggingFaceEndpointType.INFERENCE_ENDPOINT
      ? `${this.baseUrl}/v1/chat/completions`
      : `${this.baseUrl}/chat/completions`;

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: request.model || this.config.name,
        messages: hfMessages,
        max_tokens: request.maxTokens || this.config.maxTokens || 512,
        temperature: request.temperature ?? this.config.temperature ?? 0.7,
        tools,
        ...request.extra,
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(`HuggingFace API error (${response.status}): ${JSON.stringify(error)}`);
    }

    const data = await response.json() as any;
    const choice = data.choices?.[0];

    if (!choice) {
      throw new Error('No response from HuggingFace');
    }

    return {
      content: choice.message?.content || '',
      model: data.model || request.model || this.config.name,
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
  }

  calculateCost(promptTokens: number, completionTokens: number, _model: string): number {
    const totalTokens = promptTokens + completionTokens;

    if (this.endpointType === HuggingFaceEndpointType.SERVERLESS) {
      // Free tier (with rate limits)
      return 0.0;
    } else if (this.endpointType === HuggingFaceEndpointType.INFERENCE_ENDPOINT) {
      // Paid by hour ($0.60-$4/hour), not by token
      return 0.0;
    } else {
      // Inference Providers: rough estimate (varies by provider)
      return (totalTokens / 1_000_000) * 1.0; // ~$1 per million tokens estimate
    }
  }

  /**
   * Convert generic messages to HuggingFace/OpenAI format
   */
  private convertToHuggingFaceMessages(messages: Message[], systemPrompt?: string): any[] {
    const hfMessages: any[] = [];

    if (systemPrompt) {
      hfMessages.push({ role: 'system', content: systemPrompt });
    }

    for (const msg of messages) {
      if (msg.role === 'system') {
        hfMessages.push({ role: 'system', content: msg.content });
      } else if (msg.role === 'user') {
        hfMessages.push({ role: 'user', content: msg.content });
      } else if (msg.role === 'assistant') {
        hfMessages.push({ role: 'assistant', content: msg.content });
      } else if (msg.role === 'tool') {
        hfMessages.push({
          role: 'tool',
          content: msg.content,
          tool_call_id: msg.tool_call_id || '',
        });
      }
    }

    return hfMessages;
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

  /**
   * Detect endpoint type from base URL
   */
  private detectEndpointType(baseUrl?: string): HuggingFaceEndpointType {
    if (!baseUrl) {
      return HuggingFaceEndpointType.SERVERLESS;
    }

    if (baseUrl.includes('endpoints.huggingface.cloud')) {
      if (baseUrl.includes('/provider/')) {
        return HuggingFaceEndpointType.INFERENCE_PROVIDERS;
      } else {
        return HuggingFaceEndpointType.INFERENCE_ENDPOINT;
      }
    }

    return HuggingFaceEndpointType.SERVERLESS;
  }

  /**
   * Get base URL for endpoint type
   *
   * Note: Migrated from deprecated api-inference.huggingface.co (deprecated Jan 2025)
   * to new router.huggingface.co endpoint as per HuggingFace migration notice.
   */
  private getHFBaseUrl(customUrl?: string): string {
    if (customUrl) {
      return customUrl;
    }
    // New endpoint as of November 2025 (old api-inference.huggingface.co deprecated)
    return 'https://router.huggingface.co/hf-inference';
  }

  /**
   * Override getApiKey to use HF_TOKEN
   */
  protected getApiKey(): string {
    const key = this.config.apiKey || process.env['HF_TOKEN'] || process.env['HUGGINGFACE_API_KEY'];

    if (!key) {
      throw new Error(
        'HuggingFace API token not found. Set HF_TOKEN environment variable or pass apiKey in config'
      );
    }

    return key;
  }

  /**
   * Create serverless instance (convenience method)
   */
  static serverless(config: Omit<ModelConfig, 'provider'>): HuggingFaceProvider {
    return new HuggingFaceProvider({
      ...config,
      provider: 'huggingface',
    });
  }

  /**
   * Create inference endpoint instance (convenience method)
   */
  static inferenceEndpoint(
    config: Omit<ModelConfig, 'provider'> & { endpointUrl: string }
  ): HuggingFaceProvider {
    return new HuggingFaceProvider({
      ...config,
      provider: 'huggingface',
      baseUrl: config.endpointUrl,
    });
  }

  /**
   * Create inference providers instance (convenience method)
   */
  static inferenceProviders(
    config: Omit<ModelConfig, 'provider'> & { providerName: string }
  ): HuggingFaceProvider {
    return new HuggingFaceProvider({
      ...config,
      provider: 'huggingface',
      baseUrl: `https://api.endpoints.huggingface.cloud/v2/provider/${config.providerName}`,
    });
  }
}
