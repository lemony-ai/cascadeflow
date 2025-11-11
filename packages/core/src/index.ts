/**
 * cascadeflow TypeScript Library
 *
 * Smart AI model cascading for cost optimization
 *
 * @example
 * ```typescript
 * import { CascadeAgent, ModelConfig } from '@cascadeflow/core';
 *
 * // Recommended: Claude Haiku + GPT-5
 * const agent = new CascadeAgent({
 *   models: [
 *     { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
 *     { name: 'gpt-5', provider: 'openai', cost: 0.00125 }
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

// Streaming
export {
  StreamEventType,
  createStreamEvent,
  isChunkEvent,
  isCompleteEvent,
  isErrorEvent,
  collectStream,
  collectResult,
} from './streaming';
export type {
  StreamEvent,
  StreamEventData,
  StreamChunk,
  StreamOptions,
} from './streaming';

// Quality validation
export {
  QualityValidator,
  calculateConfidenceFromLogprobs,
  estimateConfidenceFromContent,
  DEFAULT_QUALITY_CONFIG as DEFAULT_QUALITY_VALIDATOR_CONFIG,
  CASCADE_QUALITY_CONFIG,
} from './quality';
export type {
  QualityResult,
  QualityConfig as QualityValidatorConfig,
} from './quality';

// Semantic quality validation (ML-based)
export { SemanticQualityChecker } from './quality-semantic';
export type { SemanticQualityResult } from './quality-semantic';

// Alignment scoring
export { QueryResponseAlignmentScorer } from './alignment';
export type { AlignmentAnalysis } from './alignment';

// Complexity detection
export {
  ComplexityDetector,
} from './complexity';
export type {
  ComplexityResult,
} from './complexity';

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
  // v0.2.1+ Multi-tenant types
  TierLevel,
  TierConfig,
  UserProfile,
  RateLimitState,
  PiiMatch,
  ModerationResult,
  GuardrailsCheck,
  BatchStrategy,
  BatchConfig,
  BatchItemResult,
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
export { OpenRouterProvider } from './providers/openrouter';

// Presets
export {
  PRESET_BEST_OVERALL,
  PRESET_ULTRA_FAST,
  PRESET_ULTRA_CHEAP,
  PRESET_OPENAI_ONLY,
  PRESET_ANTHROPIC_ONLY,
  PRESET_FREE_LOCAL,
  PRESETS,
  createPreset,
} from './presets';
export type {
  QualityMode,
  PerformanceMode,
  PresetConfig,
  PresetName,
} from './presets';

// Validators (v0.1.2)
export {
  validateModel,
  validateConfig,
  testConnection,
  testConnections,
  validateSetup,
} from './validators';
export type {
  ValidationError,
  ValidationResult,
  ConnectionTestResult,
} from './validators';

// Error classes (v0.1.2)
export {
  cascadeflowError,
  ConfigurationError,
  ProviderError,
  AuthenticationError,
  RateLimitError,
  QualityValidationError,
  TimeoutError,
  ToolExecutionError,
  iscascadeflowError,
  isProviderError,
  isConfigurationError,
  isAuthenticationError,
  isRateLimitError,
} from './errors';

// User Profiles (v0.2.1+)
export {
  TIER_PRESETS,
  createUserProfile,
  UserProfileManager,
  serializeProfile,
  deserializeProfile,
} from './profiles';

// Rate Limiting (v0.2.1+)
export { RateLimiter } from './rate-limiter';
export { RateLimitError as RateLimitErrorV2 } from './rate-limiter';

// Guardrails (v0.2.1+)
export {
  ContentModerator,
  PiiDetector,
  GuardrailsManager,
  GuardrailViolation,
} from './guardrails';

// LiteLLM Integration
export {
  LiteLLMCostProvider,
  SUPPORTED_PROVIDERS,
  validateProvider,
  getProviderInfo,
  getModelCost,
  calculateCost,
} from './integrations/litellm';
export type {
  ProviderInfo,
  ModelPricing,
  CostCalculationOptions,
} from './integrations/litellm';

// Cost Calculator (Telemetry)
export {
  CostCalculator,
  calculateCascadeCost,
} from './telemetry/cost-calculator';
export type {
  CostCalculationFromTokensOptions,
} from './telemetry/cost-calculator';

// Retry Manager
export {
  RetryManager,
  ErrorType,
  DEFAULT_RETRY_CONFIG,
  createRetryManager,
} from './retry-manager';
export type {
  RetryConfig,
  RetryMetrics,
  RetryMetricsSummary,
} from './retry-manager';

// Response Cache
export {
  ResponseCache,
  createResponseCache,
} from './response-cache';
export type {
  CacheStats,
  ResponseCacheConfig,
  CacheSetOptions,
  CacheGetOptions,
} from './response-cache';

// Version
export const VERSION = '1.0.0';
