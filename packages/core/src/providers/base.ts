/**
 * Base provider interface and utilities
 */

import type { Message, Tool, ProviderResponse } from '../types';
import type { ModelConfig } from '../config';
import type { StreamChunk } from '../streaming';

/**
 * Request options for provider calls
 */
export interface ProviderRequest {
  /** Input messages or prompt */
  messages: Message[] | string;

  /** Model name */
  model: string;

  /** Maximum tokens to generate */
  maxTokens?: number;

  /** Temperature (0-2) */
  temperature?: number;

  /** System prompt */
  systemPrompt?: string;

  /** Tools/functions available */
  tools?: Tool[];

  /** Whether to stream the response */
  stream?: boolean;

  /** Additional provider-specific options */
  extra?: Record<string, any>;
}

/**
 * Base provider interface that all providers must implement
 */
export interface Provider {
  /**
   * Provider name
   */
  readonly name: string;

  /**
   * Generate a completion
   */
  generate(request: ProviderRequest): Promise<ProviderResponse>;

  /**
   * Stream a completion (optional)
   *
   * Providers that support streaming should implement this method.
   * Returns an async iterator that yields content chunks.
   */
  stream?(request: ProviderRequest): AsyncIterable<StreamChunk>;

  /**
   * Calculate cost for a completion
   */
  calculateCost(promptTokens: number, completionTokens: number, model: string): number;

  /**
   * Check if provider is available (API key set, etc.)
   */
  isAvailable(): boolean;
}

/**
 * Abstract base class for providers
 */
export abstract class BaseProvider implements Provider {
  abstract readonly name: string;

  constructor(protected config: ModelConfig) {
    this.validateConfig(config);
  }

  abstract generate(request: ProviderRequest): Promise<ProviderResponse>;
  abstract calculateCost(promptTokens: number, completionTokens: number, model: string): number;

  isAvailable(): boolean {
    return !!this.config.apiKey || !!process.env[`${this.name.toUpperCase()}_API_KEY`];
  }

  protected validateConfig(config: ModelConfig): void {
    if (!config.name) {
      throw new Error(`${this.name} provider requires model name`);
    }
  }

  /**
   * Get API key from config or environment
   */
  protected getApiKey(): string {
    const key =
      this.config.apiKey || process.env[`${this.name.toUpperCase()}_API_KEY`];

    if (!key) {
      throw new Error(
        `${this.name} API key not found. Set ${this.name.toUpperCase()}_API_KEY environment variable or pass apiKey in config`
      );
    }

    return key;
  }

  /**
   * Get base URL from config or use default
   */
  protected getBaseUrl(defaultUrl: string): string {
    return this.config.baseUrl || defaultUrl;
  }

  /**
   * Normalize messages to array format
   */
  protected normalizeMessages(input: Message[] | string): Message[] {
    if (typeof input === 'string') {
      return [{ role: 'user', content: input }];
    }
    return input;
  }

  /**
   * Format error message
   */
  protected formatError(error: any): Error {
    if (error instanceof Error) {
      return new Error(`${this.name} provider error: ${error.message}`);
    }
    return new Error(`${this.name} provider error: ${String(error)}`);
  }
}

/**
 * Provider registry
 */
export class ProviderRegistry {
  private providers = new Map<string, new (config: ModelConfig) => Provider>();

  register(name: string, provider: new (config: ModelConfig) => Provider): void {
    this.providers.set(name.toLowerCase(), provider);
  }

  get(name: string, config: ModelConfig): Provider {
    const ProviderClass = this.providers.get(name.toLowerCase());
    if (!ProviderClass) {
      throw new Error(`Provider '${name}' not found. Available providers: ${Array.from(this.providers.keys()).join(', ')}`);
    }
    return new ProviderClass(config);
  }

  has(name: string): boolean {
    return this.providers.has(name.toLowerCase());
  }

  list(): string[] {
    return Array.from(this.providers.keys());
  }
}

/**
 * Global provider registry
 */
export const providerRegistry = new ProviderRegistry();
