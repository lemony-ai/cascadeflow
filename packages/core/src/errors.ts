/**
 * Custom error classes for CascadeFlow
 *
 * Provides strongly-typed errors for better error handling and debugging.
 *
 * @example
 * ```typescript
 * try {
 *   await agent.run(query);
 * } catch (error) {
 *   if (error instanceof ValidationError) {
 *     console.error('Configuration error:', error.field, error.message);
 *   } else if (error instanceof ProviderError) {
 *     console.error('Provider API error:', error.provider, error.statusCode);
 *   }
 * }
 * ```
 */

import type { Provider } from './types';

/**
 * Base error class for all CascadeFlow errors
 */
export class CascadeFlowError extends Error {
  /**
   * Error code for programmatic error handling
   */
  readonly code: string;

  /**
   * Additional context about the error
   */
  readonly context?: Record<string, unknown>;

  constructor(
    message: string,
    code: string,
    context?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'CascadeFlowError';
    this.code = code;
    this.context = context;

    // Maintains proper stack trace in V8 environments
    if (Error.captureStackTrace) {
      Error.captureStackTrace(this, this.constructor);
    }
  }
}

/**
 * Configuration validation error
 *
 * Thrown when model or cascade configuration is invalid.
 *
 * @example
 * ```typescript
 * throw new ConfigurationError(
 *   'Model cost cannot be negative',
 *   'models[0].cost',
 *   { cost: -0.001 }
 * );
 * ```
 */
export class ConfigurationError extends CascadeFlowError {
  /**
   * The configuration field that failed validation
   */
  readonly field: string;

  constructor(
    message: string,
    field: string,
    context?: Record<string, unknown>
  ) {
    super(message, 'CONFIGURATION_ERROR', { ...context, field });
    this.name = 'ConfigurationError';
    this.field = field;
  }
}

/**
 * Provider API error
 *
 * Thrown when a provider API call fails (authentication, rate limits, etc).
 *
 * @example
 * ```typescript
 * throw new ProviderError(
 *   'OpenAI API authentication failed',
 *   'openai',
 *   401,
 *   { endpoint: '/v1/chat/completions' }
 * );
 * ```
 */
export class ProviderError extends CascadeFlowError {
  /**
   * The provider that failed
   */
  readonly provider: Provider;

  /**
   * HTTP status code (if applicable)
   */
  readonly statusCode?: number;

  /**
   * Provider-specific error code (if available)
   */
  readonly providerCode?: string;

  constructor(
    message: string,
    provider: Provider,
    statusCode?: number,
    context?: Record<string, unknown>,
    code: string = 'PROVIDER_ERROR'
  ) {
    super(message, code, {
      ...context,
      provider,
      statusCode,
    });
    this.name = 'ProviderError';
    this.provider = provider;
    this.statusCode = statusCode;
    this.providerCode = context?.providerCode as string | undefined;
  }
}

/**
 * Authentication error
 *
 * Thrown when API key is missing or invalid.
 *
 * @example
 * ```typescript
 * throw new AuthenticationError(
 *   'OpenAI API key not found',
 *   'openai',
 *   'OPENAI_API_KEY'
 * );
 * ```
 */
export class AuthenticationError extends ProviderError {
  /**
   * The environment variable name that should contain the API key
   */
  readonly envVarName: string;

  constructor(
    message: string,
    provider: Provider,
    envVarName: string,
    context?: Record<string, unknown>
  ) {
    super(message, provider, 401, { ...context, envVarName }, 'AUTHENTICATION_ERROR');
    this.name = 'AuthenticationError';
    this.envVarName = envVarName;
  }
}

/**
 * Rate limit error
 *
 * Thrown when a provider's rate limit is exceeded.
 *
 * @example
 * ```typescript
 * throw new RateLimitError(
 *   'OpenAI rate limit exceeded',
 *   'openai',
 *   60,
 *   { requestsPerMinute: 100 }
 * );
 * ```
 */
export class RateLimitError extends ProviderError {
  /**
   * Number of seconds to wait before retrying (if available)
   */
  readonly retryAfter?: number;

  constructor(
    message: string,
    provider: Provider,
    retryAfter?: number,
    context?: Record<string, unknown>
  ) {
    super(message, provider, 429, { ...context, retryAfter }, 'RATE_LIMIT_ERROR');
    this.name = 'RateLimitError';
    this.retryAfter = retryAfter;
  }
}

/**
 * Quality validation error
 *
 * Thrown when quality validation fails or cannot be performed.
 *
 * @example
 * ```typescript
 * throw new QualityValidationError(
 *   'Confidence score below threshold',
 *   0.45,
 *   0.70,
 *   { modelUsed: 'gpt-4o-mini' }
 * );
 * ```
 */
export class QualityValidationError extends CascadeFlowError {
  /**
   * The confidence score that failed validation (if applicable)
   */
  readonly confidence?: number;

  /**
   * The threshold that was not met (if applicable)
   */
  readonly threshold?: number;

  constructor(
    message: string,
    confidence?: number,
    threshold?: number,
    context?: Record<string, unknown>
  ) {
    super(message, 'QUALITY_VALIDATION_ERROR', {
      ...context,
      confidence,
      threshold,
    });
    this.name = 'QualityValidationError';
    this.confidence = confidence;
    this.threshold = threshold;
  }
}

/**
 * Timeout error
 *
 * Thrown when a provider API call or operation times out.
 *
 * @example
 * ```typescript
 * throw new TimeoutError(
 *   'OpenAI API request timed out after 60s',
 *   'openai',
 *   60000,
 *   { endpoint: '/v1/chat/completions' }
 * );
 * ```
 */
export class TimeoutError extends ProviderError {
  /**
   * Timeout duration in milliseconds
   */
  readonly timeoutMs: number;

  constructor(
    message: string,
    provider: Provider,
    timeoutMs: number,
    context?: Record<string, unknown>
  ) {
    super(message, provider, 408, { ...context, timeoutMs }, 'TIMEOUT_ERROR');
    this.name = 'TimeoutError';
    this.timeoutMs = timeoutMs;
  }
}

/**
 * Tool execution error
 *
 * Thrown when a tool call fails during execution.
 *
 * @example
 * ```typescript
 * throw new ToolExecutionError(
 *   'Failed to execute weather tool',
 *   'get_weather',
 *   new Error('API unreachable')
 * );
 * ```
 */
export class ToolExecutionError extends CascadeFlowError {
  /**
   * The name of the tool that failed
   */
  readonly toolName: string;

  /**
   * The original error that caused the failure (if available)
   */
  readonly cause?: Error;

  constructor(
    message: string,
    toolName: string,
    cause?: Error,
    context?: Record<string, unknown>
  ) {
    super(message, 'TOOL_EXECUTION_ERROR', {
      ...context,
      toolName,
      causeMessage: cause?.message,
    });
    this.name = 'ToolExecutionError';
    this.toolName = toolName;
    this.cause = cause;
  }
}

/**
 * Type guard to check if an error is a CascadeFlow error
 *
 * @param error - The error to check
 * @returns True if the error is a CascadeFlowError or subclass
 *
 * @example
 * ```typescript
 * try {
 *   await agent.run(query);
 * } catch (error) {
 *   if (isCascadeFlowError(error)) {
 *     console.error(`CascadeFlow error [${error.code}]:`, error.message);
 *   } else {
 *     console.error('Unknown error:', error);
 *   }
 * }
 * ```
 */
export function isCascadeFlowError(error: unknown): error is CascadeFlowError {
  return error instanceof CascadeFlowError;
}

/**
 * Type guard to check if an error is a provider error
 *
 * @param error - The error to check
 * @returns True if the error is a ProviderError or subclass
 *
 * @example
 * ```typescript
 * try {
 *   await agent.run(query);
 * } catch (error) {
 *   if (isProviderError(error)) {
 *     console.error(`Provider ${error.provider} failed:`, error.message);
 *     if (error.statusCode === 429) {
 *       console.log('Rate limited - try again later');
 *     }
 *   }
 * }
 * ```
 */
export function isProviderError(error: unknown): error is ProviderError {
  return error instanceof ProviderError;
}

/**
 * Type guard to check if an error is a configuration error
 *
 * @param error - The error to check
 * @returns True if the error is a ConfigurationError
 */
export function isConfigurationError(
  error: unknown
): error is ConfigurationError {
  return error instanceof ConfigurationError;
}

/**
 * Type guard to check if an error is an authentication error
 *
 * @param error - The error to check
 * @returns True if the error is an AuthenticationError
 */
export function isAuthenticationError(
  error: unknown
): error is AuthenticationError {
  return error instanceof AuthenticationError;
}

/**
 * Type guard to check if an error is a rate limit error
 *
 * @param error - The error to check
 * @returns True if the error is a RateLimitError
 */
export function isRateLimitError(error: unknown): error is RateLimitError {
  return error instanceof RateLimitError;
}
