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
export type {
  RunOptions,
  RunStreamingOptions,
  StreamEventsOptions,
} from './agent';

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

// Batch Processing (v0.2.1+)
export {
  BatchStrategy,
  BatchProcessor,
  BatchProcessingError,
  normalizeBatchConfig,
  DEFAULT_BATCH_CONFIG,
} from './batch';
export type { BatchConfig, BatchResult } from './batch';

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
  QualityConfigFactory,
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

// Production Confidence Estimation (v1.0.1+)
export {
  ProductionConfidenceEstimator,
  PROVIDER_CONFIDENCE_CALIBRATION,
} from './confidence';
export type {
  ConfidenceAnalysis,
  ConfidenceEstimationOptions,
  ProviderCalibration,
} from './confidence';

// Response Analysis (v1.0.1+)
export { ResponseAnalyzer } from './response-analyzer';
export type {
  LengthAnalysis,
  HedgingAnalysis,
  SpecificityAnalysis,
  HallucinationAnalysis,
} from './response-analyzer';

// Types
export type {
  Provider as ProviderType,
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
  // v1.0.1+ Latency & optimization types
  CostSensitivity,
  LatencyProfile,
  OptimizationWeights,
  WorkflowProfile,
} from './types';

// Legacy routing type (kept for backward compatibility, prefer RoutingStrategy enum from routers/base)
export type { RoutingStrategy as LegacyRoutingStrategy } from './types';

// Providers
export { providerRegistry, getAvailableProviders } from './providers/base';
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
  // v1.0.1+ Latency & optimization helpers
  validateOptimizationWeights,
  createOptimizationWeights,
  createLatencyProfile,
  OPTIMIZATION_PRESETS,
  LATENCY_PRESETS,
  getDailyBudget,
  getRequestsPerHour,
  getRequestsPerDay,
  getOptimizationWeights,
  getLatencyProfile,
  // v1.0.1+ Workflow profiles
  createWorkflowProfile,
  applyWorkflowProfile,
  isModelAllowedByWorkflow,
  WORKFLOW_PRESETS,
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

// Metrics Collector (Telemetry)
export { MetricsCollector } from './telemetry/metrics-collector';
export type { MetricsSnapshot } from './telemetry/metrics-collector';

// Callback Manager (Telemetry)
export {
  CallbackManager,
  CallbackEvent,
} from './telemetry/callbacks';
export type {
  CallbackData,
  CallbackFunction,
  CallbackStats,
} from './telemetry/callbacks';

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

// Routers (v1.0.1+)
export {
  Router,
  RouterChain,
  RoutingStrategy,
  RoutingDecisionHelper,
} from './routers/base';
export type { RoutingDecision } from './routers/base';
export { PreRouter, createPreRouter } from './routers/pre-router';
export type { PreRouterConfig, PreRouterStats } from './routers/pre-router';
export { ToolRouter, createToolRouter } from './routers/tool-router';
export type {
  ToolRouterConfig,
  ToolRouterStats,
  ToolFilterResult,
  ToolValidationResult,
  FilterToolCapableModelsOptions,
  SuggestModelsOptions,
} from './routers/tool-router';
export { TierRouter, createTierRouter } from './routers/tier-router';
export type {
  TierAwareRouterConfig,
  TierRouterConfig,
  TierRouterStats,
  TierConstraints,
  FilterModelsOptions,
} from './routers/tier-router';
export { DomainRouter, createDomainRouter, Domain } from './routers/domain-router';
export type {
  DomainKeywords,
  DomainDetectionResult,
  DomainRouterStats,
} from './routers/domain-router';

// Tools (v1.1.0+)
export {
  ToolConfig,
  createTool,
  tool,
  inferJsonType,
  buildParameterSchema,
  ToolExecutor,
  ToolCall,
  ToolResult,
  ToolCallFormat,
  toOpenAIFormat,
  toAnthropicFormat,
  toOllamaFormat,
  toProviderFormat,
  getProviderFormatType,
  ToolValidator,
  formatToolQualityScore,
} from './tools';
export type {
  ToolFunction,
  ToolParameters,
  ToolConfigOptions,
  ToolCallOptions,
  ToolResultOptions,
  ToolQualityScore,
  ComplexityLevel,
} from './tools';

// Version
export const VERSION = '1.0.0';
