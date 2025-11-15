/**
 * Provider Format Conversion Utilities
 *
 * Handles conversion between different provider tool formats.
 * Each LLM provider has slightly different formats for tools.
 *
 * @example
 * ```typescript
 * import { ToolCallFormat, toProviderFormat } from '@cascadeflow/core';
 *
 * const openaiTool = toProviderFormat('openai', 'get_weather', 'Get weather', schema);
 * const anthropicTool = toProviderFormat('anthropic', 'get_weather', 'Get weather', schema);
 * ```
 */

/**
 * Tool call format by provider
 */
export enum ToolCallFormat {
  /** OpenAI, Groq, Together */
  OPENAI = 'openai',

  /** Claude (Anthropic) */
  ANTHROPIC = 'anthropic',

  /** Ollama */
  OLLAMA = 'ollama',

  /** vLLM */
  VLLM = 'vllm',

  /** HuggingFace Inference */
  HUGGINGFACE = 'huggingface',
}

/**
 * Convert to OpenAI tool format
 *
 * Used by: OpenAI, Groq, Together, vLLM
 *
 * @param name - Tool name
 * @param description - Tool description
 * @param parameters - JSON Schema parameters
 * @returns OpenAI format tool definition
 *
 * @example
 * ```typescript
 * const tool = toOpenAIFormat('get_weather', 'Get weather', {
 *   type: 'object',
 *   properties: { location: { type: 'string' } },
 *   required: ['location']
 * });
 * // Returns: { type: 'function', function: { name: '...', ... } }
 * ```
 */
export function toOpenAIFormat(
  name: string,
  description: string,
  parameters: Record<string, any>
): Record<string, any> {
  return {
    type: 'function',
    function: {
      name,
      description,
      parameters,
    },
  };
}

/**
 * Convert to Anthropic tool format
 *
 * Key difference: Uses 'input_schema' instead of 'parameters'
 *
 * @param name - Tool name
 * @param description - Tool description
 * @param parameters - JSON Schema parameters
 * @returns Anthropic format tool definition
 *
 * @example
 * ```typescript
 * const tool = toAnthropicFormat('get_weather', 'Get weather', schema);
 * // Returns: { name: '...', description: '...', input_schema: {...} }
 * ```
 */
export function toAnthropicFormat(
  name: string,
  description: string,
  parameters: Record<string, any>
): Record<string, any> {
  return {
    name,
    description,
    input_schema: parameters, // Anthropic uses input_schema
  };
}

/**
 * Convert to Ollama tool format (same as OpenAI)
 *
 * @param name - Tool name
 * @param description - Tool description
 * @param parameters - JSON Schema parameters
 * @returns Ollama format tool definition
 */
export function toOllamaFormat(
  name: string,
  description: string,
  parameters: Record<string, any>
): Record<string, any> {
  return toOpenAIFormat(name, description, parameters);
}

/**
 * Convert to provider-specific format
 *
 * @param provider - Provider name (openai, anthropic, ollama, groq, together, vllm)
 * @param name - Tool name
 * @param description - Tool description
 * @param parameters - Tool parameters (JSON schema)
 * @returns Tool schema in provider's expected format
 *
 * @example
 * ```typescript
 * const openaiTool = toProviderFormat('openai', 'search', 'Search web', schema);
 * const claudeTool = toProviderFormat('anthropic', 'search', 'Search web', schema);
 * ```
 */
export function toProviderFormat(
  provider: string,
  name: string,
  description: string,
  parameters: Record<string, any>
): Record<string, any> {
  const providerLower = provider.toLowerCase();

  if (['openai', 'groq', 'together', 'vllm', 'huggingface'].includes(providerLower)) {
    return toOpenAIFormat(name, description, parameters);
  } else if (providerLower === 'anthropic') {
    return toAnthropicFormat(name, description, parameters);
  } else if (providerLower === 'ollama') {
    return toOllamaFormat(name, description, parameters);
  } else {
    // Default to OpenAI format (most common)
    console.warn(`Unknown provider '${provider}', using OpenAI format`);
    return toOpenAIFormat(name, description, parameters);
  }
}

/**
 * Get the format type for a provider
 *
 * @param provider - Provider name
 * @returns ToolCallFormat enum value
 *
 * @example
 * ```typescript
 * const format = getProviderFormatType('openai');
 * // Returns: ToolCallFormat.OPENAI
 * ```
 */
export function getProviderFormatType(provider: string): ToolCallFormat {
  const providerLower = provider.toLowerCase();

  if (['openai', 'groq', 'together', 'vllm', 'huggingface'].includes(providerLower)) {
    return ToolCallFormat.OPENAI;
  } else if (providerLower === 'anthropic') {
    return ToolCallFormat.ANTHROPIC;
  } else if (providerLower === 'ollama') {
    return ToolCallFormat.OLLAMA;
  } else {
    return ToolCallFormat.OPENAI; // Default
  }
}
