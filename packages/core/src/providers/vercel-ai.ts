/**
 * Vercel AI SDK provider implementation
 *
 * Enables cascadeflow to use the Vercel AI SDK provider ecosystem with a
 * unified provider interface.
 */

import { BaseProvider, type ProviderRequest } from './base';
import type { ProviderResponse, Message, UsageDetails } from '../types';
import type { ModelConfig } from '../config';
import type { StreamChunk } from '../streaming';

export interface VercelAISDKProviderSpec {
  packageName: string;
  exportName: string;
  createExportName?: string;
  apiKeyEnv?: string;
  baseUrlEnv?: string;
  requiresApiKey?: boolean;
  supportsBaseUrl?: boolean;
}

export const VERCEL_AI_PROVIDER_SPECS: Record<string, VercelAISDKProviderSpec> = {
  openai: {
    packageName: '@ai-sdk/openai',
    exportName: 'openai',
    createExportName: 'createOpenAI',
    apiKeyEnv: 'OPENAI_API_KEY',
    baseUrlEnv: 'OPENAI_BASE_URL',
    requiresApiKey: true,
    supportsBaseUrl: true,
  },
  anthropic: {
    packageName: '@ai-sdk/anthropic',
    exportName: 'anthropic',
    createExportName: 'createAnthropic',
    apiKeyEnv: 'ANTHROPIC_API_KEY',
    requiresApiKey: true,
  },
  azure: {
    packageName: '@ai-sdk/azure',
    exportName: 'azure',
    createExportName: 'createAzure',
    apiKeyEnv: 'AZURE_OPENAI_API_KEY',
    baseUrlEnv: 'AZURE_OPENAI_ENDPOINT',
    requiresApiKey: true,
    supportsBaseUrl: true,
  },
  google: {
    packageName: '@ai-sdk/google',
    exportName: 'google',
    createExportName: 'createGoogleGenerativeAI',
    apiKeyEnv: 'GOOGLE_API_KEY',
    requiresApiKey: true,
  },
  mistral: {
    packageName: '@ai-sdk/mistral',
    exportName: 'mistral',
    createExportName: 'createMistral',
    apiKeyEnv: 'MISTRAL_API_KEY',
    requiresApiKey: true,
  },
  cohere: {
    packageName: '@ai-sdk/cohere',
    exportName: 'cohere',
    createExportName: 'createCohere',
    apiKeyEnv: 'COHERE_API_KEY',
    requiresApiKey: true,
  },
  groq: {
    packageName: '@ai-sdk/groq',
    exportName: 'groq',
    createExportName: 'createGroq',
    apiKeyEnv: 'GROQ_API_KEY',
    requiresApiKey: true,
  },
  together: {
    packageName: '@ai-sdk/togetherai',
    exportName: 'togetherai',
    createExportName: 'createTogetherAI',
    apiKeyEnv: 'TOGETHER_API_KEY',
    requiresApiKey: true,
  },
  openrouter: {
    packageName: '@ai-sdk/openrouter',
    exportName: 'openrouter',
    createExportName: 'createOpenRouter',
    apiKeyEnv: 'OPENROUTER_API_KEY',
    requiresApiKey: true,
  },
  perplexity: {
    packageName: '@ai-sdk/perplexity',
    exportName: 'perplexity',
    createExportName: 'createPerplexity',
    apiKeyEnv: 'PERPLEXITY_API_KEY',
    requiresApiKey: true,
  },
  xai: {
    packageName: '@ai-sdk/xai',
    exportName: 'xai',
    createExportName: 'createXAI',
    apiKeyEnv: 'XAI_API_KEY',
    requiresApiKey: true,
  },
  fireworks: {
    packageName: '@ai-sdk/fireworks',
    exportName: 'fireworks',
    createExportName: 'createFireworks',
    apiKeyEnv: 'FIREWORKS_API_KEY',
    requiresApiKey: true,
  },
  bedrock: {
    packageName: '@ai-sdk/bedrock',
    exportName: 'bedrock',
    createExportName: 'createBedrock',
    requiresApiKey: false,
  },
  replicate: {
    packageName: '@ai-sdk/replicate',
    exportName: 'replicate',
    createExportName: 'createReplicate',
    apiKeyEnv: 'REPLICATE_API_TOKEN',
    requiresApiKey: true,
  },
  deepseek: {
    packageName: '@ai-sdk/deepseek',
    exportName: 'deepseek',
    createExportName: 'createDeepSeek',
    apiKeyEnv: 'DEEPSEEK_API_KEY',
    requiresApiKey: true,
  },
  ollama: {
    packageName: '@ai-sdk/ollama',
    exportName: 'ollama',
    createExportName: 'createOllama',
    requiresApiKey: false,
    supportsBaseUrl: true,
  },
  cerebras: {
    packageName: '@ai-sdk/cerebras',
    exportName: 'cerebras',
    createExportName: 'createCerebras',
    apiKeyEnv: 'CEREBRAS_API_KEY',
    requiresApiKey: true,
  },
};

export const VERCEL_AI_PROVIDER_NAMES = Object.freeze(Object.keys(VERCEL_AI_PROVIDER_SPECS));

export function getVercelAiProviderNames(): string[] {
  return [...VERCEL_AI_PROVIDER_NAMES];
}

function resolveSpec(providerName: string): VercelAISDKProviderSpec {
  const spec = VERCEL_AI_PROVIDER_SPECS[providerName.toLowerCase()];
  if (!spec) {
    throw new Error(
      `Vercel AI SDK provider '${providerName}' is not supported. Available: ${VERCEL_AI_PROVIDER_NAMES.join(', ')}`
    );
  }
  return spec;
}

function resolveApiKey(spec: VercelAISDKProviderSpec, config: ModelConfig): string | undefined {
  if (config.apiKey) {
    return config.apiKey;
  }
  if (spec.apiKeyEnv) {
    return process.env[spec.apiKeyEnv];
  }
  return undefined;
}

function resolveBaseUrl(spec: VercelAISDKProviderSpec, config: ModelConfig): string | undefined {
  if (!spec.supportsBaseUrl) {
    return undefined;
  }
  return config.baseUrl || (spec.baseUrlEnv ? process.env[spec.baseUrlEnv] : undefined);
}

function buildUsage(usage?: { promptTokens?: number; completionTokens?: number; totalTokens?: number }): UsageDetails | undefined {
  if (!usage) {
    return undefined;
  }
  return {
    prompt_tokens: usage.promptTokens ?? 0,
    completion_tokens: usage.completionTokens ?? 0,
    total_tokens: usage.totalTokens ?? 0,
  };
}

function buildMessages(messages: Message[], systemPrompt?: string): Message[] {
  if (!systemPrompt) {
    return messages;
  }
  return [{ role: 'system', content: systemPrompt }, ...messages];
}

export class VercelAISDKProvider extends BaseProvider {
  readonly name: string;
  private providerSpec: VercelAISDKProviderSpec;
  private factoryOverride?: (model: string) => any;

  constructor(config: ModelConfig) {
    super(config);
    this.name = config.provider;
    this.providerSpec = resolveSpec(config.provider);
    this.factoryOverride = config.extra?.vercelProviderFactory as ((model: string) => any) | undefined;
  }

  isAvailable(): boolean {
    if (this.providerSpec.requiresApiKey === false) {
      return true;
    }
    return !!resolveApiKey(this.providerSpec, this.config);
  }

  async generate(request: ProviderRequest): Promise<ProviderResponse> {
    const modelFactory = await this.loadModelFactory();
    const { generateText } = await import('ai');
    const messages = buildMessages(this.normalizeMessages(request.messages), request.systemPrompt);

    const result = await generateText({
      model: modelFactory(request.model),
      messages,
      maxTokens: request.maxTokens,
      temperature: request.temperature,
      ...(request.extra?.aiSdkOptions ?? {}),
    });

    return {
      content: result.text ?? '',
      model: request.model,
      usage: buildUsage(result.usage),
      finish_reason: result.finishReason,
      raw: result,
    };
  }

  async *stream(request: ProviderRequest): AsyncIterable<StreamChunk> {
    const modelFactory = await this.loadModelFactory();
    const { streamText } = await import('ai');
    const messages = buildMessages(this.normalizeMessages(request.messages), request.systemPrompt);

    const result = await streamText({
      model: modelFactory(request.model),
      messages,
      maxTokens: request.maxTokens,
      temperature: request.temperature,
      ...(request.extra?.aiSdkOptions ?? {}),
    });

    for await (const chunk of result.textStream) {
      yield { content: chunk };
    }

    const usage = result.usage ? await result.usage : undefined;
    const finishReason = await Promise.resolve(result.finishReason);
    yield {
      content: '',
      done: true,
      usage: usage
        ? {
            prompt_tokens: usage.promptTokens ?? 0,
            completion_tokens: usage.completionTokens ?? 0,
            total_tokens: usage.totalTokens ?? 0,
          }
        : undefined,
      finish_reason: finishReason,
      raw: result,
    };
  }

  calculateCost(promptTokens: number, completionTokens: number, _model: string): number {
    const inputRate = this.config.cost ?? 0;
    const outputRate = (this.config.extra?.outputCost as number | undefined) ?? inputRate;

    const inputCost = (promptTokens / 1_000_000) * inputRate;
    const outputCost = (completionTokens / 1_000_000) * outputRate;

    return inputCost + outputCost;
  }

  private async loadModelFactory(): Promise<(model: string) => any> {
    if (this.factoryOverride) {
      return this.factoryOverride;
    }

    const spec = this.providerSpec;
    const module = await import(spec.packageName);
    const baseFactory = module[spec.exportName] ?? module.default;

    if (!baseFactory) {
      throw new Error(`Vercel AI SDK provider '${spec.packageName}' does not export '${spec.exportName}'.`);
    }

    if (!spec.createExportName) {
      return baseFactory;
    }

    const hasCustomConfig =
      this.config.apiKey ||
      this.config.baseUrl ||
      this.config.extra?.vercelProviderOptions ||
      this.config.extra?.vercelProviderHeaders;

    if (!hasCustomConfig) {
      return baseFactory;
    }

    const createFactory = module[spec.createExportName];
    if (!createFactory) {
      return baseFactory;
    }

    const apiKey = resolveApiKey(spec, this.config);
    if (spec.requiresApiKey && !apiKey) {
      throw new Error(
        `${this.name} API key not found. Set ${spec.apiKeyEnv ?? `${this.name.toUpperCase()}_API_KEY`} or pass apiKey.`
      );
    }

    const baseUrl = resolveBaseUrl(spec, this.config);
    const options = {
      apiKey,
      baseURL: baseUrl,
      baseUrl,
      ...(this.config.extra?.vercelProviderHeaders
        ? { headers: this.config.extra?.vercelProviderHeaders }
        : {}),
      ...(this.config.extra?.vercelProviderOptions ?? {}),
    };

    return createFactory(options);
  }
}
