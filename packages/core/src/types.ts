/**
 * Core type definitions for cascadeflow TypeScript library
 */

/**
 * Supported AI providers
 */
export type Provider =
  | 'openai'
  | 'anthropic'
  | 'groq'
  | 'ollama'
  | 'huggingface'
  | 'together'
  | 'vllm'
  | 'replicate'
  | 'custom';

/**
 * Routing strategy options
 */
export type RoutingStrategy =
  | 'adaptive'
  | 'cost_first'
  | 'quality_first'
  | 'speed_first'
  | 'semantic';

/**
 * Query complexity levels
 */
export type QueryComplexity = 'simple' | 'moderate' | 'complex' | 'expert';

/**
 * Message role in chat format
 */
export type MessageRole = 'system' | 'user' | 'assistant' | 'tool';

/**
 * Chat message format
 */
export interface Message {
  role: MessageRole;
  content: string;
  name?: string;
  tool_call_id?: string;
}

/**
 * Tool/function definition
 */
export interface Tool {
  type: 'function';
  function: {
    name: string;
    description: string;
    parameters: Record<string, any>;
  };
}

/**
 * Tool call response from model
 */
export interface ToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string; // JSON string
  };
}

/**
 * Reasoning effort level for OpenAI o1/o3 models
 */
export type ReasoningEffort = 'low' | 'medium' | 'high';

/**
 * Thinking configuration for Anthropic extended thinking
 */
export interface ThinkingConfig {
  type: 'enabled';
  budget_tokens: number; // Minimum 1024
}

/**
 * Usage details with reasoning token breakdown
 */
export interface UsageDetails {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  reasoning_tokens?: number; // For OpenAI o1/o3 models
  completion_tokens_details?: {
    reasoning_tokens?: number;
    accepted_prediction_tokens?: number;
    rejected_prediction_tokens?: number;
  };
}

/**
 * Thinking block from Anthropic extended thinking
 */
export interface ThinkingBlock {
  type: 'thinking';
  thinking: string;
  signature?: string;
}

/**
 * Text block from response
 */
export interface TextBlock {
  type: 'text';
  text: string;
}

/**
 * Content block (can be thinking or text)
 */
export type ContentBlock = ThinkingBlock | TextBlock;

/**
 * Reasoning model capabilities and requirements
 * Used for auto-detection and configuration across all providers
 */
export interface ReasoningModelInfo {
  isReasoning: boolean;
  provider: Provider;
  supportsStreaming: boolean;
  supportsTools: boolean;
  supportsSystemMessages: boolean;
  supportsReasoningEffort?: boolean; // OpenAI o1/o3
  supportsExtendedThinking?: boolean; // Anthropic Claude 4.5
  requiresMaxCompletionTokens?: boolean; // OpenAI specific
  requiresThinkingBudget?: boolean; // Anthropic specific
}

/**
 * Provider response (unified format)
 */
export interface ProviderResponse {
  content: string;
  model: string;
  usage?: UsageDetails;
  finish_reason?: string;
  tool_calls?: ToolCall[];
  logprobs?: number[]; // Log probabilities for confidence scoring
  thinking?: string; // Internal reasoning from extended thinking
  content_blocks?: ContentBlock[]; // Structured content with thinking
  raw?: any; // Provider-specific raw response
}

/**
 * Cost breakdown information
 */
export interface CostBreakdown {
  draftCost: number;
  verifierCost: number;
  totalCost: number;
  costSaved: number;
  savingsPercentage: number;
}

/**
 * Timing breakdown information
 */
export interface TimingBreakdown {
  complexityDetectionMs?: number;
  draftGenerationMs?: number;
  qualityVerificationMs?: number;
  verifierGenerationMs?: number;
  cascadeOverheadMs?: number;
  totalMs: number;
}

/**
 * Quality validation result
 */
export interface QualityValidation {
  passed: boolean;
  score: number;
  threshold: number;
  reason?: string;
}

/**
 * Tier levels for user subscriptions (v0.2.1+)
 */
export type TierLevel = 'FREE' | 'STARTER' | 'PRO' | 'BUSINESS' | 'ENTERPRISE';

/**
 * Tier configuration (v0.2.1+)
 */
export interface TierConfig {
  name: string;
  requestsPerHour?: number;
  requestsPerDay?: number;
  dailyBudget?: number;
  maxConcurrentRequests: number;
  enableCaching: boolean;
  enableSpeculative: boolean;
  minQuality: number;
  targetQuality: number;
}

/**
 * User profile for multi-tenant applications (v0.2.1+)
 */
export interface UserProfile {
  userId: string;
  tier: TierConfig;
  customDailyBudget?: number;
  customRequestsPerHour?: number;
  customRequestsPerDay?: number;
  preferredModels?: string[];
  preferredDomains?: string[];
  domainModels?: Record<string, string[]>;
  enableContentModeration?: boolean;
  enablePiiDetection?: boolean;
  metadata?: Record<string, any>;
}

/**
 * Rate limit state (v0.2.1+)
 */
export interface RateLimitState {
  userId: string;
  hourlyRequests: number[];
  dailyRequests: number[];
  dailyCost: number;
  lastReset: Date;
}

/**
 * PII match result (v0.2.1+)
 */
export interface PiiMatch {
  piiType: 'email' | 'phone' | 'ssn' | 'credit_card' | 'ip_address';
  value: string;
  position: [number, number];
}

/**
 * Content moderation result (v0.2.1+)
 */
export interface ModerationResult {
  isSafe: boolean;
  violations: string[];
  categories: string[];
  confidence: number;
}

/**
 * Guardrails check result (v0.2.1+)
 */
export interface GuardrailsCheck {
  isSafe: boolean;
  contentModeration?: ModerationResult;
  piiDetected?: PiiMatch[];
  violations: string[];
}

/**
 * Batch processing strategy (v0.2.1+)
 */
export type BatchStrategy = 'sequential' | 'parallel' | 'adaptive';

/**
 * Batch configuration (v0.2.1+)
 */
export interface BatchConfig {
  strategy: BatchStrategy;
  maxConcurrency?: number;
  stopOnError?: boolean;
  returnPartialResults?: boolean;
}

/**
 * Individual batch item result (v0.2.1+)
 */
export interface BatchItemResult {
  index: number;
  success: boolean;
  result?: any;
  error?: string;
  timingMs: number;
  cost: number;
}
