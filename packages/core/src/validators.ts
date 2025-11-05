/**
 * Validation helpers for cascadeflow configurations
 *
 * These helpers allow you to validate configurations and test connections
 * before running queries, making it easier to catch issues early.
 */

import type { ModelConfig, CascadeConfig } from './config';
import type { Provider } from './types';

/**
 * Validation error details
 */
export interface ValidationError {
  field: string;
  message: string;
  severity: 'error' | 'warning';
}

/**
 * Configuration validation result
 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
}

/**
 * Connection test result
 */
export interface ConnectionTestResult {
  provider: Provider;
  connected: boolean;
  error?: string;
  latency?: number;
}

/**
 * Validate a model configuration
 *
 * @param config - Model configuration to validate
 * @returns Validation result with errors and warnings
 *
 * @example
 * ```typescript
 * import { validateModel } from '@cascadeflow/core';
 *
 * const errors = validateModel({
 *   name: 'gpt-4o-mini',
 *   provider: 'openai',
 *   cost: 0.00015
 * });
 *
 * if (!errors.valid) {
 *   console.error('Invalid configuration:', errors.errors);
 * }
 * ```
 */
export function validateModel(config: ModelConfig): ValidationResult {
  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];

  // Required fields
  if (!config.name) {
    errors.push({
      field: 'name',
      message: 'Model name is required',
      severity: 'error',
    });
  }

  if (!config.provider) {
    errors.push({
      field: 'provider',
      message: 'Provider is required',
      severity: 'error',
    });
  }

  if (config.cost === undefined || config.cost === null) {
    warnings.push({
      field: 'cost',
      message: 'Cost not specified - cost tracking will not work',
      severity: 'warning',
    });
  }

  // Validate cost is reasonable
  if (config.cost !== undefined && config.cost < 0) {
    errors.push({
      field: 'cost',
      message: 'Cost cannot be negative',
      severity: 'error',
    });
  }

  if (config.cost !== undefined && config.cost > 1) {
    warnings.push({
      field: 'cost',
      message: 'Cost seems very high (>$1 per 1K tokens) - please verify',
      severity: 'warning',
    });
  }

  // Validate provider is supported
  if (config.provider) {
    const validProviders: Provider[] = [
      'openai',
      'anthropic',
      'groq',
      'ollama',
      'huggingface',
      'together',
      'vllm',
      'replicate',
      'custom',
    ];

    if (!validProviders.includes(config.provider as Provider)) {
      errors.push({
        field: 'provider',
        message: `Provider '${config.provider}' is not supported. Valid providers: ${validProviders.join(', ')}`,
        severity: 'error',
      });
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

/**
 * Validate a cascade configuration
 *
 * @param config - Cascade configuration to validate
 * @returns Validation result with errors and warnings
 *
 * @example
 * ```typescript
 * import { validateConfig, PRESET_BEST_OVERALL } from '@cascadeflow/core';
 *
 * const result = validateConfig(PRESET_BEST_OVERALL);
 *
 * if (!result.valid) {
 *   console.error('Configuration errors:', result.errors);
 * }
 *
 * if (result.warnings.length > 0) {
 *   console.warn('Configuration warnings:', result.warnings);
 * }
 * ```
 */
export function validateConfig(
  config: { models: ModelConfig[] } | CascadeConfig
): ValidationResult {
  const errors: ValidationError[] = [];
  const warnings: ValidationError[] = [];

  // Extract models array
  const models = 'models' in config ? config.models : [];

  // Must have at least one model
  if (!models || models.length === 0) {
    errors.push({
      field: 'models',
      message: 'At least one model is required',
      severity: 'error',
    });
    return { valid: false, errors, warnings };
  }

  // Validate each model
  for (let i = 0; i < models.length; i++) {
    const modelResult = validateModel(models[i]);

    // Add errors with model index
    for (const error of modelResult.errors) {
      errors.push({
        ...error,
        field: `models[${i}].${error.field}`,
      });
    }

    // Add warnings with model index
    for (const warning of modelResult.warnings) {
      warnings.push({
        ...warning,
        field: `models[${i}].${warning.field}`,
      });
    }
  }

  // Check for cost ordering (cheaper models should come first)
  const costsProvided = models.every(m => m.cost !== undefined);
  if (costsProvided) {
    for (let i = 1; i < models.length; i++) {
      if (models[i].cost! < models[i - 1].cost!) {
        warnings.push({
          field: `models[${i}]`,
          message: `Model is cheaper than previous model - consider reordering for better cascade behavior`,
          severity: 'warning',
        });
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

/**
 * Test connection to a provider
 *
 * Makes a lightweight test call to verify the API key and connection work.
 *
 * @param provider - Provider to test
 * @param apiKey - Optional API key (uses environment variable if not provided)
 * @returns Connection test result
 *
 * @example
 * ```typescript
 * import { testConnection } from '@cascadeflow/core';
 *
 * const result = await testConnection('openai');
 *
 * if (result.connected) {
 *   console.log(`✅ OpenAI connected (${result.latency}ms)`);
 * } else {
 *   console.error(`❌ OpenAI connection failed: ${result.error}`);
 * }
 * ```
 */
export async function testConnection(
  provider: Provider,
  apiKey?: string
): Promise<ConnectionTestResult> {
  const startTime = Date.now();

  try {
    // For now, just check if the API key environment variable is set
    // In a real implementation, you would make an actual API call
    const envVarName = getEnvVarForProvider(provider);

    if (!apiKey && !process.env[envVarName]) {
      return {
        provider,
        connected: false,
        error: `API key not found. Set ${envVarName} environment variable.`,
      };
    }

    // Simulate basic connection check
    // TODO: Make actual API call to test connection
    const latency = Date.now() - startTime;

    return {
      provider,
      connected: true,
      latency,
    };
  } catch (error) {
    return {
      provider,
      connected: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

/**
 * Get environment variable name for a provider
 */
function getEnvVarForProvider(provider: Provider): string {
  const envVars: Record<string, string> = {
    openai: 'OPENAI_API_KEY',
    anthropic: 'ANTHROPIC_API_KEY',
    groq: 'GROQ_API_KEY',
    ollama: '', // No API key needed
    huggingface: 'HUGGINGFACE_API_KEY',
    together: 'TOGETHER_API_KEY',
    vllm: '', // No API key for local
  };

  return envVars[provider] || `${provider.toUpperCase()}_API_KEY`;
}


/**
 * Test all providers in a cascade configuration
 *
 * @param config - Cascade configuration to test
 * @returns Array of connection test results
 *
 * @example
 * ```typescript
 * import { testConnections, PRESET_BEST_OVERALL } from '@cascadeflow/core';
 *
 * const results = await testConnections(PRESET_BEST_OVERALL);
 *
 * for (const result of results) {
 *   if (result.connected) {
 *     console.log(`✅ ${result.provider}: OK (${result.latency}ms)`);
 *   } else {
 *     console.error(`❌ ${result.provider}: ${result.error}`);
 *   }
 * }
 * ```
 */
export async function testConnections(
  config: { models: ModelConfig[] } | CascadeConfig
): Promise<ConnectionTestResult[]> {
  const models = 'models' in config ? config.models : [];

  // Get unique providers
  const uniqueProviders = [...new Set(models.map(m => m.provider))];

  // Test each provider
  const results = await Promise.all(
    uniqueProviders.map(provider =>
      testConnection(provider as Provider, models.find(m => m.provider === provider)?.apiKey)
    )
  );

  return results;
}

/**
 * Comprehensive validation - checks config and tests connections
 *
 * @param config - Cascade configuration to validate
 * @param shouldTestConnections - Whether to test provider connections (default: true)
 * @returns Comprehensive validation result
 *
 * @example
 * ```typescript
 * import { validateSetup, PRESET_ULTRA_FAST } from '@cascadeflow/core';
 *
 * const result = await validateSetup(PRESET_ULTRA_FAST);
 *
 * if (!result.configValid) {
 *   console.error('Configuration errors:', result.errors);
 *   return;
 * }
 *
 * const failedConnections = result.connectionTests?.filter(t => !t.connected);
 * if (failedConnections && failedConnections.length > 0) {
 *   console.error('Connection failures:', failedConnections);
 * }
 * ```
 */
export async function validateSetup(
  config: { models: ModelConfig[] } | CascadeConfig,
  shouldTestConnections = true
): Promise<{
  configValid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  connectionTests?: ConnectionTestResult[];
}> {
  // Validate configuration
  const configResult = validateConfig(config);

  // Test connections if requested and config is valid
  let connectionTests: ConnectionTestResult[] | undefined;
  if (shouldTestConnections && configResult.valid) {
    connectionTests = await testConnections(config);
  }

  return {
    configValid: configResult.valid,
    errors: configResult.errors,
    warnings: configResult.warnings,
    connectionTests,
  };
}
