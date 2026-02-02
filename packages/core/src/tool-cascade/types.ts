/**
 * Universal Tool Calling Optimization Strategy Types
 *
 * Shared types for tool call detection, routing, validation, and orchestration.
 */

import type { Message, Tool, ToolCall } from '../types';

export type DetectionLayer = 'explicit' | 'structured' | 'heuristic' | 'fallback';

export interface ToolCallIntent {
  shouldCallTool: boolean;
  confidence: number;
  layers: DetectionLayer[];
  reasons: string[];
  toolHints: string[];
  rawToolCalls?: ToolCall[];
}

export type RiskTier = 'low' | 'medium' | 'high' | 'critical';

export interface ToolRiskProfile {
  toolName: string;
  tier: RiskTier;
  reasons: string[];
}

export type ToolComplexityLevel = 'trivial' | 'simple' | 'moderate' | 'hard' | 'expert';

export interface ToolComplexityAnalysis {
  complexityLevel: ToolComplexityLevel;
  score: number;
  signals?: Record<string, boolean>;
  reasoning?: string[];
}

export interface ToolComplexityAnalyzerLike {
  analyzeToolCall(
    query: string,
    tools: Tool[],
    context?: Record<string, unknown>
  ): ToolComplexityAnalysis;
}

export type ToolRoutingStrategy = 'cascade' | 'direct' | 'skip';

export interface ToolRoutingDecision {
  strategy: ToolRoutingStrategy;
  complexity: ToolComplexityAnalysis;
  risk: RiskTier;
  reasons: string[];
}

export interface ToolCascadeContext {
  query: string;
  tools: Tool[];
  messages?: Message[];
  toolCalls?: ToolCall[];
}

export interface ToolCascadeFeedback {
  attempt: number;
  issues: string[];
  warnings: string[];
  strategy: ToolRoutingStrategy;
}

export type ToolCallGenerator = (
  context: ToolCascadeContext,
  feedback?: ToolCascadeFeedback
) => Promise<ToolCall[]> | ToolCall[];

export interface StructuralValidationResult {
  isValid: boolean;
  score: number;
  issues: string[];
}

export interface SemanticValidationResult {
  isValid: boolean;
  score: number;
  issues: string[];
}

export interface SafetyValidationResult {
  isValid: boolean;
  score: number;
  issues: string[];
  flaggedFields: string[];
}

export interface ValidationResult {
  valid: boolean;
  score: number;
  errors: string[];
  warnings: string[];
  structural: StructuralValidationResult;
  semantic: SemanticValidationResult;
  safety: SafetyValidationResult;
}

export interface ToolCascadeResult {
  accepted: boolean;
  attempts: number;
  intent: ToolCallIntent;
  decision: ToolRoutingDecision;
  validation: ValidationResult;
  toolCalls: ToolCall[];
}

export interface ToolCascadeOptions {
  maxRetries?: number;
  allowUnsafe?: boolean;
  complexityAnalyzer?: ToolComplexityAnalyzerLike;
}
