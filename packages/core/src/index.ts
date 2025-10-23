/**
 * CascadeFlow TypeScript Library
 *
 * Smart AI model cascading for cost optimization
 *
 * @example
 * ```typescript
 * import { CascadeAgent, ModelConfig } from '@cascadeflow/core';
 *
 * const agent = new CascadeAgent({
 *   models: [
 *     { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
 *     { name: 'gpt-4o', provider: 'openai', cost: 0.00625 }
 *   ]
 * });
 *
 * const result = await agent.run('What is TypeScript?');
 * console.log(`Cost: $${result.totalCost}, Saved: ${result.savingsPercentage}%`);
 * ```
 */

// Main agent
export { CascadeAgent } from './agent';
export type { RunOptions } from './agent';

// Configuration
export type {
  ModelConfig,
  QualityConfig,
  CascadeConfig,
  AgentConfig,
} from './config';

export {
  validateModelConfig,
  DEFAULT_QUALITY_CONFIG,
  DEFAULT_CASCADE_CONFIG,
} from './config';

// Results
export type { CascadeResult } from './result';
export { resultToObject } from './result';

// Types
export type {
  Provider as ProviderType,
  RoutingStrategy,
  QueryComplexity,
  MessageRole,
  Message,
  Tool,
  ToolCall,
  ProviderResponse,
  CostBreakdown,
  TimingBreakdown,
  QualityValidation,
} from './types';

// Providers
export { providerRegistry } from './providers/base';
export type { Provider, ProviderRequest } from './providers/base';
export { OpenAIProvider } from './providers/openai';
export { AnthropicProvider } from './providers/anthropic';
export { GroqProvider } from './providers/groq';
export { TogetherProvider } from './providers/together';
export { OllamaProvider } from './providers/ollama';
export { HuggingFaceProvider, HuggingFaceEndpointType } from './providers/huggingface';
export { VLLMProvider } from './providers/vllm';

// Version
export const VERSION = '1.0.0';
