/**
 * Base provider interface and utilities
 */

import type { Message, Tool, ProviderResponse, HttpConfig } from '../types';
import type { ModelConfig } from '../config';
import type { StreamChunk } from '../streaming';

// Lazy-loaded Node.js modules for enterprise HTTP config
let https: any;
let http: any;
let HttpsProxyAgent: any;
let fs: any;

/**
 * Create HTTP agent options from HttpConfig for SDK clients
 *
 * Supports proxy configuration using https-proxy-agent and custom CA certificates.
 * Auto-detects from environment variables if not explicitly configured:
 * - HTTPS_PROXY, HTTP_PROXY for proxy
 * - SSL_CERT_FILE, REQUESTS_CA_BUNDLE, CURL_CA_BUNDLE for CA bundle
 *
 * @param httpConfig - Optional HttpConfig settings
 * @returns SDK client options including httpAgent if configured
 */
export function getHttpAgentOptions(httpConfig?: HttpConfig): Record<string, any> {
  // Only run in Node.js environment
  // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
  if (typeof (globalThis as any).window !== 'undefined') {
    return {}; // Browser - no httpAgent support
  }

  const options: Record<string, any> = {};

  // Get proxy URL from config or environment
  const proxyUrl =
    httpConfig?.proxy ||
    process.env.HTTPS_PROXY ||
    process.env.https_proxy ||
    process.env.HTTP_PROXY ||
    process.env.http_proxy;

  // Get CA cert path from config or environment
  const caCertPath =
    httpConfig?.caCertPath ||
    process.env.SSL_CERT_FILE ||
    process.env.REQUESTS_CA_BUNDLE ||
    process.env.CURL_CA_BUNDLE;

  // Determine SSL verification setting
  const verifySsl = httpConfig?.verifySsl !== false;

  // Build agent options
  try {
    if (proxyUrl) {
      // Try to load https-proxy-agent for proxy support
      try {
        if (!HttpsProxyAgent) {
          HttpsProxyAgent = require('https-proxy-agent').HttpsProxyAgent;
        }

        const agentOptions: Record<string, any> = {};

        // Add CA certificate if specified
        if (caCertPath) {
          if (!fs) {
            fs = require('fs');
          }
          try {
            agentOptions.ca = fs.readFileSync(caCertPath);
          } catch (e) {
            console.warn(`CascadeFlow: Unable to read CA certificate from ${caCertPath}`);
          }
        }

        // Disable SSL verification if requested
        if (!verifySsl) {
          agentOptions.rejectUnauthorized = false;
        }

        options.httpAgent = new HttpsProxyAgent(proxyUrl, agentOptions);
      } catch (e) {
        console.warn(
          'CascadeFlow: https-proxy-agent not installed. Run `npm install https-proxy-agent` for proxy support.'
        );
      }
    } else if (caCertPath || !verifySsl) {
      // No proxy, but custom CA or SSL settings
      if (!https) {
        https = require('https');
      }

      const agentOptions: Record<string, any> = {};

      if (caCertPath) {
        if (!fs) {
          fs = require('fs');
        }
        try {
          agentOptions.ca = fs.readFileSync(caCertPath);
        } catch (e) {
          console.warn(`CascadeFlow: Unable to read CA certificate from ${caCertPath}`);
        }
      }

      if (!verifySsl) {
        agentOptions.rejectUnauthorized = false;
      }

      options.httpAgent = new https.Agent(agentOptions);
    }
  } catch (e) {
    // Silently ignore errors in browser or when modules not available
  }

  // Add timeout if specified
  if (httpConfig?.timeout) {
    options.timeout = httpConfig.timeout;
  }

  // Add max retries if specified
  if (httpConfig?.maxRetries !== undefined) {
    options.maxRetries = httpConfig.maxRetries;
  }

  return options;
}

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

/**
 * Get available providers based on environment variables
 *
 * Checks which providers have API keys set in the environment
 * and can be initialized.
 *
 * @returns Array of available provider names
 *
 * @example
 * ```typescript
 * const available = getAvailableProviders();
 * // ['openai', 'anthropic'] if those API keys are set
 * ```
 */
export function getAvailableProviders(): string[] {
  const available: string[] = [];
  const providerList = providerRegistry.list();

  for (const providerName of providerList) {
    // Check if API key is available in environment
    const envKey = `${providerName.toUpperCase()}_API_KEY`;
    if (process.env[envKey]) {
      available.push(providerName);
    }
  }

  return available;
}
