/**
 * Core type definitions for CascadeFlow TypeScript library
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
 * Provider response (unified format)
 */
export interface ProviderResponse {
  content: string;
  model: string;
  usage?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  finish_reason?: string;
  tool_calls?: ToolCall[];
  logprobs?: number[]; // Log probabilities for confidence scoring
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
