/**
 * Multi-Step Cascade Pipelines for Domain-Specific Optimization
 *
 * This module provides domain-specific cascade pipelines that execute multiple
 * steps with validation at each stage. Each domain can have a custom pipeline
 * optimized for its specific requirements.
 *
 * Key Features:
 * - Multi-step execution with validation
 * - Domain-specific strategies (CODE, MEDICAL, GENERAL, etc.)
 * - Step-level quality checks
 * - Automatic fallback to more capable models
 * - Cost tracking per step
 *
 * @example
 * ```typescript
 * import {
 *   DomainCascadeStrategy,
 *   CascadeStep,
 *   ValidationMethod,
 *   getStrategyForDomain,
 * } from '@cascadeflow/core';
 * import { Domain } from '@cascadeflow/core';
 *
 * // Get built-in CODE domain strategy
 * const codeStrategy = getStrategyForDomain(Domain.CODE);
 *
 * // Or define custom strategy
 * const customStrategy: DomainCascadeStrategy = {
 *   domain: Domain.CODE,
 *   steps: [
 *     {
 *       name: 'draft',
 *       model: 'deepseek-coder',
 *       provider: 'deepseek',
 *       validation: ValidationMethod.SYNTAX_CHECK,
 *       qualityThreshold: 0.7,
 *     },
 *     {
 *       name: 'verify',
 *       model: 'gpt-4o',
 *       provider: 'openai',
 *       validation: ValidationMethod.FULL_QUALITY,
 *       qualityThreshold: 0.85,
 *       fallbackOnly: true,
 *     },
 *   ],
 *   description: 'Cost-optimized code generation',
 *   enabled: true,
 * };
 * ```
 */

import { Domain } from './domain-router';

// ============================================================================
// ENUMS
// ============================================================================

/**
 * Validation methods for cascade steps.
 *
 * Determines how to validate the output of each cascade step.
 */
export enum ValidationMethod {
  /** No validation (always pass) */
  NONE = 'none',
  /** Code syntax validation */
  SYNTAX_CHECK = 'syntax_check',
  /** Medical/legal fact checking */
  FACT_CHECK = 'fact_check',
  /** Safety/toxicity checking */
  SAFETY_CHECK = 'safety_check',
  /** General quality validation */
  QUALITY_CHECK = 'quality_check',
  /** Comprehensive quality check */
  FULL_QUALITY = 'full_quality',
  /** ML-based semantic similarity validation (optional) */
  SEMANTIC = 'semantic',
  /** Custom validation function */
  CUSTOM = 'custom',
}

/**
 * Execution status of a cascade step.
 */
export enum StepStatus {
  /** Step not yet executed */
  PENDING = 'pending',
  /** Step currently executing */
  RUNNING = 'running',
  /** Step completed successfully */
  SUCCESS = 'success',
  /** Step failed quality validation */
  FAILED_QUALITY = 'failed_quality',
  /** Step failed with error */
  FAILED_ERROR = 'failed_error',
  /** Step was skipped */
  SKIPPED = 'skipped',
}

// ============================================================================
// INTERFACES
// ============================================================================

/**
 * A single step in a multi-step cascade pipeline.
 *
 * Each step defines:
 * - Which model to use
 * - How to validate the output
 * - What quality threshold to meet
 * - Whether it's a fallback-only step
 */
export interface CascadeStep {
  /** Step name (e.g., "draft", "verify", "safety_check") */
  name: string;
  /** Model to use for this step */
  model: string;
  /** Provider name (e.g., "openai", "deepseek") */
  provider: string;
  /** Validation method to apply */
  validation?: ValidationMethod;
  /** Minimum quality score (0-1) */
  qualityThreshold?: number;
  /** Only execute if previous steps failed */
  fallbackOnly?: boolean;
  /** Maximum tokens for generation */
  maxTokens?: number;
  /** Temperature for generation */
  temperature?: number;
  /** Additional step configuration */
  metadata?: Record<string, any>;
}

/**
 * Result of executing a single cascade step.
 */
export interface StepResult {
  /** Name of the step executed */
  stepName: string;
  /** Execution status */
  status: StepStatus;
  /** Generated response (if successful) */
  response?: string;
  /** Quality validation score */
  qualityScore: number;
  /** Cost of this step */
  cost: number;
  /** Latency in milliseconds */
  latencyMs: number;
  /** Tokens used */
  tokensUsed: number;
  /** Detailed validation results */
  validationDetails?: Record<string, any>;
  /** Error message (if failed) */
  error?: string;
  /** Additional result data */
  metadata?: Record<string, any>;
}

/**
 * Domain-specific cascade pipeline strategy.
 *
 * Defines the complete multi-step pipeline for a domain, including:
 * - Ordered list of steps to execute
 * - Validation methods at each step
 * - Fallback logic
 */
export interface DomainCascadeStrategy {
  /** Domain this strategy applies to */
  domain: Domain;
  /** Ordered list of cascade steps */
  steps: CascadeStep[];
  /** Human-readable description */
  description?: string;
  /** Whether this strategy is enabled */
  enabled?: boolean;
  /** Additional strategy configuration */
  metadata?: Record<string, any>;
}

/**
 * Result of executing a complete multi-step cascade pipeline.
 */
export interface CascadeExecutionResult {
  /** Whether pipeline completed successfully */
  success: boolean;
  /** Domain that was executed */
  domain: Domain;
  /** Strategy name */
  strategyUsed: string;
  /** Final response from pipeline */
  finalResponse: string;
  /** List of step results */
  stepsExecuted: StepResult[];
  /** Total cost across all steps */
  totalCost: number;
  /** Total latency */
  totalLatencyMs: number;
  /** Total tokens used */
  totalTokens: number;
  /** Final quality score */
  qualityScore: number;
  /** Whether fallback steps were used */
  fallbackUsed: boolean;
  /** Additional execution data */
  metadata?: Record<string, any>;
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Create a cascade step with default values.
 */
export function createCascadeStep(config: CascadeStep): CascadeStep {
  return {
    validation: ValidationMethod.QUALITY_CHECK,
    qualityThreshold: 0.7,
    fallbackOnly: false,
    maxTokens: 1000,
    temperature: 0.7,
    metadata: {},
    ...config,
  };
}

/**
 * Get step by name from a strategy.
 */
export function getStepByName(
  strategy: DomainCascadeStrategy,
  stepName: string
): CascadeStep | undefined {
  return strategy.steps.find((step) => step.name === stepName);
}

/**
 * Get all fallback-only steps from a strategy.
 */
export function getFallbackSteps(strategy: DomainCascadeStrategy): CascadeStep[] {
  return strategy.steps.filter((step) => step.fallbackOnly);
}

/**
 * Get step result by name from execution result.
 */
export function getStepResult(
  result: CascadeExecutionResult,
  stepName: string
): StepResult | undefined {
  return result.stepsExecuted.find((r) => r.stepName === stepName);
}

/**
 * Get cost breakdown by step from execution result.
 */
export function getCostBreakdown(result: CascadeExecutionResult): Record<string, number> {
  const breakdown: Record<string, number> = {};
  for (const stepResult of result.stepsExecuted) {
    breakdown[stepResult.stepName] = stepResult.cost;
  }
  return breakdown;
}

/**
 * Get all successful steps from execution result.
 */
export function getSuccessfulSteps(result: CascadeExecutionResult): StepResult[] {
  return result.stepsExecuted.filter((r) => r.status === StepStatus.SUCCESS);
}

// ============================================================================
// BUILT-IN STRATEGIES
// ============================================================================

/**
 * Get CODE domain cascade strategy.
 *
 * Pipeline:
 * 1. Deepseek-Coder (draft) → syntax check
 * 2. GPT-4o (verify, fallback) → full quality check
 *
 * Returns 95% cost savings vs direct GPT-4.
 */
export function getCodeStrategy(): DomainCascadeStrategy {
  return {
    domain: Domain.CODE,
    description: 'Cost-optimized code generation with syntax validation',
    enabled: true,
    steps: [
      createCascadeStep({
        name: 'draft',
        model: 'deepseek-coder',
        provider: 'deepseek',
        validation: ValidationMethod.SYNTAX_CHECK,
        qualityThreshold: 0.7,
        fallbackOnly: false,
        temperature: 0.3,
        metadata: { stepType: 'draft', optimizedFor: 'code' },
      }),
      createCascadeStep({
        name: 'verify',
        model: 'gpt-4o',
        provider: 'openai',
        validation: ValidationMethod.FULL_QUALITY,
        qualityThreshold: 0.85,
        fallbackOnly: true,
        temperature: 0.3,
        metadata: { stepType: 'verify', expensive: true },
      }),
    ],
  };
}

/**
 * Get MEDICAL domain cascade strategy.
 *
 * Pipeline:
 * 1. GPT-4o-mini (draft) → fact check
 * 2. GPT-4 (verify, fallback) → safety check
 *
 * Returns high-quality medical responses with safety validation.
 */
export function getMedicalStrategy(): DomainCascadeStrategy {
  return {
    domain: Domain.MEDICAL,
    description: 'Medical AI with fact-checking and safety validation',
    enabled: true,
    steps: [
      createCascadeStep({
        name: 'draft',
        model: 'gpt-4o-mini',
        provider: 'openai',
        validation: ValidationMethod.FACT_CHECK,
        qualityThreshold: 0.75,
        fallbackOnly: false,
        temperature: 0.2,
        metadata: { stepType: 'draft', domain: 'medical' },
      }),
      createCascadeStep({
        name: 'verify',
        model: 'gpt-4',
        provider: 'openai',
        validation: ValidationMethod.SAFETY_CHECK,
        qualityThreshold: 0.9,
        fallbackOnly: true,
        temperature: 0.2,
        metadata: { stepType: 'verify', safetyCritical: true },
      }),
    ],
  };
}

/**
 * Get GENERAL domain cascade strategy.
 *
 * Pipeline:
 * 1. Groq Llama 70B (draft) → quality check
 * 2. GPT-4o (verify, fallback) → full quality check
 *
 * Returns 98% cost savings vs direct GPT-4 with 2x speed.
 */
export function getGeneralStrategy(): DomainCascadeStrategy {
  return {
    domain: Domain.GENERAL,
    description: 'Fast general-purpose queries with quality validation',
    enabled: true,
    steps: [
      createCascadeStep({
        name: 'draft',
        model: 'llama-3.1-70b-versatile',
        provider: 'groq',
        validation: ValidationMethod.QUALITY_CHECK,
        qualityThreshold: 0.7,
        fallbackOnly: false,
        temperature: 0.7,
        metadata: { stepType: 'draft', fast: true },
      }),
      createCascadeStep({
        name: 'verify',
        model: 'gpt-4o',
        provider: 'openai',
        validation: ValidationMethod.FULL_QUALITY,
        qualityThreshold: 0.85,
        fallbackOnly: true,
        temperature: 0.7,
        metadata: { stepType: 'verify' },
      }),
    ],
  };
}

/**
 * Get DATA domain cascade strategy.
 *
 * Pipeline:
 * 1. GPT-4o-mini (draft) → data validation
 * 2. GPT-4o (verify, fallback) → full quality check
 *
 * Optimized for data analysis and SQL queries.
 */
export function getDataStrategy(): DomainCascadeStrategy {
  return {
    domain: Domain.DATA,
    description: 'Data analysis and SQL generation with validation',
    enabled: true,
    steps: [
      createCascadeStep({
        name: 'draft',
        model: 'gpt-4o-mini',
        provider: 'openai',
        validation: ValidationMethod.QUALITY_CHECK,
        qualityThreshold: 0.75,
        fallbackOnly: false,
        temperature: 0.3,
        metadata: { stepType: 'draft', domain: 'data' },
      }),
      createCascadeStep({
        name: 'verify',
        model: 'gpt-4o',
        provider: 'openai',
        validation: ValidationMethod.FULL_QUALITY,
        qualityThreshold: 0.85,
        fallbackOnly: true,
        temperature: 0.3,
        metadata: { stepType: 'verify' },
      }),
    ],
  };
}

/**
 * Get MATH domain cascade strategy.
 *
 * Pipeline:
 * 1. GPT-4o-mini (draft) → syntax check (mathematical notation)
 * 2. GPT-4o (verify, fallback) → full quality check
 *
 * Returns 85-90% cost savings vs direct GPT-4.
 * Optimized for accurate calculations and proofs.
 */
export function getMathStrategy(): DomainCascadeStrategy {
  return {
    domain: Domain.MATH,
    description: 'Mathematical reasoning with calculation validation',
    enabled: true,
    steps: [
      createCascadeStep({
        name: 'draft',
        model: 'gpt-4o-mini',
        provider: 'openai',
        validation: ValidationMethod.SYNTAX_CHECK,
        qualityThreshold: 0.75,
        fallbackOnly: false,
        temperature: 0.2,
        metadata: { stepType: 'draft', domain: 'math' },
      }),
      createCascadeStep({
        name: 'verify',
        model: 'gpt-4o',
        provider: 'openai',
        validation: ValidationMethod.FULL_QUALITY,
        qualityThreshold: 0.9,
        fallbackOnly: true,
        temperature: 0.1,
        metadata: { stepType: 'verify', precision: 'high' },
      }),
    ],
  };
}

/**
 * Get STRUCTURED domain cascade strategy.
 *
 * Pipeline:
 * 1. GPT-4o-mini (draft) → syntax check (JSON/XML validation)
 * 2. GPT-4o (verify, fallback) → quality check
 *
 * Returns 90-95% cost savings vs direct GPT-4.
 * Optimized for data extraction and format conversion.
 */
export function getStructuredStrategy(): DomainCascadeStrategy {
  return {
    domain: Domain.STRUCTURED,
    description: 'Structured data extraction with format validation',
    enabled: true,
    steps: [
      createCascadeStep({
        name: 'draft',
        model: 'gpt-4o-mini',
        provider: 'openai',
        validation: ValidationMethod.SYNTAX_CHECK,
        qualityThreshold: 0.7,
        fallbackOnly: false,
        temperature: 0.3,
        metadata: { stepType: 'draft', domain: 'structured', jsonMode: true },
      }),
      createCascadeStep({
        name: 'verify',
        model: 'gpt-4o',
        provider: 'openai',
        validation: ValidationMethod.QUALITY_CHECK,
        qualityThreshold: 0.85,
        fallbackOnly: true,
        temperature: 0.2,
        metadata: { stepType: 'verify', schemaValidation: true },
      }),
    ],
  };
}

// ============================================================================
// STRATEGY REGISTRY
// ============================================================================

/**
 * Built-in strategy factory functions by domain.
 */
export const BUILT_IN_STRATEGIES: Record<Domain, () => DomainCascadeStrategy> = {
  [Domain.CODE]: getCodeStrategy,
  [Domain.MEDICAL]: getMedicalStrategy,
  [Domain.GENERAL]: getGeneralStrategy,
  [Domain.DATA]: getDataStrategy,
  [Domain.MATH]: getMathStrategy,
  [Domain.STRUCTURED]: getStructuredStrategy,
  // Domains without specific strategies fall back to GENERAL
  [Domain.LEGAL]: getGeneralStrategy,
  [Domain.FINANCIAL]: getGeneralStrategy,
  [Domain.CREATIVE]: getGeneralStrategy,
  [Domain.CONVERSATION]: getGeneralStrategy,
  [Domain.RAG]: getGeneralStrategy,
  [Domain.TOOL]: getGeneralStrategy,
  [Domain.SUMMARY]: getGeneralStrategy,
  [Domain.TRANSLATION]: getGeneralStrategy,
  [Domain.MULTIMODAL]: getGeneralStrategy,
};

/**
 * Get built-in strategy for a domain.
 *
 * @param domain - Domain to get strategy for
 * @returns DomainCascadeStrategy if available, undefined otherwise
 */
export function getStrategyForDomain(domain: Domain): DomainCascadeStrategy | undefined {
  const strategyFn = BUILT_IN_STRATEGIES[domain];
  if (strategyFn) {
    return strategyFn();
  }
  return undefined;
}

/**
 * List domains with built-in strategies.
 *
 * @returns List of domains with strategies
 */
export function listAvailableStrategies(): Domain[] {
  return Object.keys(BUILT_IN_STRATEGIES) as Domain[];
}
