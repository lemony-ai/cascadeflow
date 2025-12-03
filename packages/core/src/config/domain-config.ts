/**
 * Domain-Specific Cascade Configuration
 *
 * This module provides the DomainConfig class for configuring domain-specific
 * cascade behavior. Each domain (CODE, MEDICAL, GENERAL, etc.) can have its own
 * drafter/verifier models, quality thresholds, and generation parameters.
 *
 * @example
 * ```typescript
 * import { DomainConfig, Domain } from '@cascadeflow/core';
 *
 * const codeConfig: DomainConfig = {
 *   drafter: 'deepseek-coder',
 *   verifier: 'gpt-4o',
 *   threshold: 0.85,
 *   temperature: 0.2,
 *   validationMethod: 'syntax',
 * };
 *
 * const agent = new CascadeAgent({
 *   domainConfigs: {
 *     [Domain.CODE]: codeConfig,
 *   },
 * });
 * ```
 */

import type { ModelConfig } from '../config';
import { Domain } from '../routers/domain-router';
import { ValidationMethod } from '../routers/cascade-pipeline';

/**
 * Validation method types for domain-specific validation.
 */
export type DomainValidationMethod =
  | 'none'
  | 'syntax'
  | 'fact'
  | 'safety'
  | 'quality'
  | 'semantic'
  | 'custom';

/**
 * Domain-specific cascade configuration.
 *
 * Allows fine-grained control over how cascading works for each domain:
 * - Model selection (drafter/verifier)
 * - Quality thresholds
 * - Generation parameters
 * - Fallback behavior
 */
export interface DomainConfig {
  /**
   * Drafter model - the cheaper, faster model that generates initial responses.
   * Can be a model name (string) or full ModelConfig.
   */
  drafter: string | ModelConfig;

  /**
   * Verifier model - the more capable model that validates/regenerates.
   * Can be a model name (string) or full ModelConfig.
   */
  verifier: string | ModelConfig;

  /**
   * Tool-specific drafter model (optional).
   * Falls back to drafter if not specified.
   * Used when tools are provided and domain-aware tool routing is enabled.
   */
  toolDrafter?: string | ModelConfig;

  /**
   * Tool-specific verifier model (optional).
   * Falls back to verifier if not specified.
   * Used when tools are provided and domain-aware tool routing is enabled.
   */
  toolVerifier?: string | ModelConfig;

  /**
   * Quality threshold (0-1) for accepting drafter responses.
   * Higher = stricter validation, more verifier usage.
   * @default 0.70
   */
  threshold?: number;

  /**
   * Validation method for this domain.
   * - 'syntax': Code/JSON syntax validation
   * - 'fact': Fact-checking (medical, legal)
   * - 'safety': Safety/toxicity checking
   * - 'quality': General quality validation
   * - 'semantic': ML-based semantic similarity
   * @default 'quality'
   */
  validationMethod?: DomainValidationMethod;

  /**
   * Temperature for generation (0-2).
   * Lower = more deterministic, higher = more creative.
   * @default 0.7
   */
  temperature?: number;

  /**
   * Maximum tokens to generate.
   * @default 1000
   */
  maxTokens?: number;

  /**
   * Fallback models to try if drafter and verifier both fail.
   */
  fallbackModels?: string[];

  /**
   * Always use verifier, even if drafter passes quality threshold.
   * Useful for high-stakes domains like medical.
   * @default false
   */
  requireVerifier?: boolean;

  /**
   * Enable adaptive threshold learning.
   * System learns optimal thresholds over time.
   * @default true
   */
  adaptiveThreshold?: boolean;

  /**
   * Skip verifier for trivial/simple queries.
   * Uses complexity detection to determine simplicity.
   * @default true
   */
  skipOnSimple?: boolean;

  /**
   * Whether this domain config is enabled.
   * @default true
   */
  enabled?: boolean;

  /**
   * Per-domain complexity handling.
   * Specifies which complexity levels should use cascade (try drafter first).
   * If undefined, defaults to all complexities using cascade.
   * @example ['trivial', 'simple', 'moderate', 'hard'] - EXPERT goes to verifier
   * @example ['trivial', 'simple', 'moderate', 'hard', 'expert'] - All cascade
   */
  cascadeComplexities?: Array<'trivial' | 'simple' | 'moderate' | 'hard' | 'expert'>;

  /**
   * Human-readable description of this configuration.
   */
  description?: string;

  /**
   * Additional metadata for custom use cases.
   */
  metadata?: Record<string, any>;
}

/**
 * Default domain configuration values.
 */
export const DEFAULT_DOMAIN_CONFIG: Required<Omit<DomainConfig, 'drafter' | 'verifier' | 'toolDrafter' | 'toolVerifier' | 'fallbackModels' | 'description' | 'metadata' | 'cascadeComplexities'>> = {
  threshold: 0.70,
  validationMethod: 'quality',
  temperature: 0.7,
  maxTokens: 1000,
  requireVerifier: false,
  adaptiveThreshold: true,
  skipOnSimple: true,
  enabled: true,
};

/**
 * Create a DomainConfig with default values filled in.
 */
export function createDomainConfig(config: DomainConfig): DomainConfig & { drafter: string | ModelConfig; verifier: string | ModelConfig } {
  return {
    drafter: config.drafter,
    verifier: config.verifier,
    toolDrafter: config.toolDrafter, // Optional, falls back to drafter
    toolVerifier: config.toolVerifier, // Optional, falls back to verifier
    threshold: config.threshold ?? DEFAULT_DOMAIN_CONFIG.threshold,
    validationMethod: config.validationMethod ?? DEFAULT_DOMAIN_CONFIG.validationMethod,
    temperature: config.temperature ?? DEFAULT_DOMAIN_CONFIG.temperature,
    maxTokens: config.maxTokens ?? DEFAULT_DOMAIN_CONFIG.maxTokens,
    fallbackModels: config.fallbackModels ?? [],
    requireVerifier: config.requireVerifier ?? DEFAULT_DOMAIN_CONFIG.requireVerifier,
    adaptiveThreshold: config.adaptiveThreshold ?? DEFAULT_DOMAIN_CONFIG.adaptiveThreshold,
    skipOnSimple: config.skipOnSimple ?? DEFAULT_DOMAIN_CONFIG.skipOnSimple,
    enabled: config.enabled ?? DEFAULT_DOMAIN_CONFIG.enabled,
    cascadeComplexities: config.cascadeComplexities, // Optional, can be undefined
    description: config.description ?? '',
    metadata: config.metadata ?? {},
  };
}

/**
 * Validate a DomainConfig and throw if invalid.
 */
export function validateDomainConfig(config: DomainConfig): void {
  if (!config.drafter) {
    throw new Error('DomainConfig: drafter is required');
  }
  if (!config.verifier) {
    throw new Error('DomainConfig: verifier is required');
  }

  if (config.threshold !== undefined) {
    if (config.threshold < 0 || config.threshold > 1) {
      throw new Error(`DomainConfig: threshold must be between 0 and 1, got ${config.threshold}`);
    }
  }

  if (config.temperature !== undefined) {
    if (config.temperature < 0 || config.temperature > 2) {
      throw new Error(`DomainConfig: temperature must be between 0 and 2, got ${config.temperature}`);
    }
  }

  if (config.maxTokens !== undefined) {
    if (config.maxTokens <= 0) {
      throw new Error(`DomainConfig: maxTokens must be positive, got ${config.maxTokens}`);
    }
  }
}

/**
 * Map of domain configs keyed by Domain.
 */
export type DomainConfigMap = Partial<Record<Domain, DomainConfig>>;

/**
 * Built-in domain configurations optimized for common use cases.
 * Updated December 2025 with GPT-5, Claude Opus/Sonnet/Haiku 4.5 models.
 */
export const BUILTIN_DOMAIN_CONFIGS: DomainConfigMap = {
  [Domain.CODE]: {
    drafter: 'deepseek-coder', // DeepSeek Coder - excellent code generation
    verifier: 'claude-opus-4-5-20251101', // Opus 4.5 - best code reasoning
    threshold: 0.85,
    validationMethod: 'syntax',
    temperature: 0.2,
    description: 'Code generation with DeepSeek drafter and Opus 4.5 verification',
  },
  [Domain.MEDICAL]: {
    drafter: 'gpt-5-mini', // GPT-5 Mini - good medical knowledge ($0.25/M)
    verifier: 'claude-opus-4-5-20251101', // Opus 4.5 - best medical reasoning
    threshold: 0.95,
    validationMethod: 'fact',
    temperature: 0.1,
    requireVerifier: true,
    description: 'High-accuracy medical with mandatory Opus 4.5 verification',
  },
  [Domain.LEGAL]: {
    drafter: 'gpt-5-mini', // GPT-5 Mini - good legal knowledge ($0.25/M)
    verifier: 'claude-opus-4-5-20251101', // Opus 4.5 - best legal reasoning
    threshold: 0.90,
    validationMethod: 'fact',
    temperature: 0.2,
    description: 'Legal domain with GPT-5 Mini and Opus 4.5 verification',
  },
  [Domain.FINANCIAL]: {
    drafter: 'gpt-5-mini', // GPT-5 Mini - good financial ($0.25/M)
    verifier: 'gpt-5', // GPT-5 - excellent numerical reasoning
    threshold: 0.85,
    validationMethod: 'quality',
    temperature: 0.3,
    description: 'Financial analysis with GPT-5 Mini drafter and GPT-5 verifier',
  },
  [Domain.DATA]: {
    drafter: 'gpt-5-mini', // GPT-5 Mini - good data analysis ($0.25/M)
    verifier: 'gpt-5', // GPT-5 - excellent data reasoning
    threshold: 0.80,
    validationMethod: 'syntax',
    temperature: 0.3,
    description: 'Data analysis with GPT-5 Mini drafter and GPT-5 syntax validation',
  },
  [Domain.MATH]: {
    drafter: 'gpt-5-mini', // GPT-5 Mini - good math ($0.25/M)
    verifier: 'claude-opus-4-5-20251101', // Opus 4.5 - best mathematical reasoning
    threshold: 0.90,
    validationMethod: 'syntax',
    temperature: 0.1,
    description: 'Math with GPT-5 Mini drafter and Opus 4.5 verification',
  },
  [Domain.STRUCTURED]: {
    drafter: 'gpt-5-mini', // GPT-5 Mini - good structured output ($0.25/M)
    verifier: 'gpt-5', // GPT-5 - excellent JSON/XML
    threshold: 0.75,
    validationMethod: 'syntax',
    temperature: 0.2,
    description: 'Structured extraction with GPT-5 Mini and syntax validation',
  },
  [Domain.CREATIVE]: {
    drafter: 'claude-3-5-haiku-20241022', // Claude Haiku - fast creative
    verifier: 'claude-sonnet-4-5-20250929', // Sonnet 4.5 - quality creative
    threshold: 0.60,
    validationMethod: 'quality',
    temperature: 0.9,
    description: 'Creative writing with Claude Haiku and Sonnet 4.5 verification',
  },
  [Domain.GENERAL]: {
    drafter: 'claude-3-5-haiku-20241022', // Claude Haiku - fast general ($0.25/$1.25/M)
    verifier: 'claude-sonnet-4-5-20250929', // Sonnet 4.5 - quality verification
    threshold: 0.70,
    validationMethod: 'quality',
    temperature: 0.7,
    description: 'General queries with Claude Haiku and Sonnet 4.5 verification',
  },
  [Domain.CONVERSATION]: {
    drafter: 'claude-3-5-haiku-20241022', // Claude Haiku - natural conversation
    verifier: 'gpt-5', // GPT-5 - excellent conversation
    threshold: 0.65,
    validationMethod: 'quality',
    temperature: 0.8,
    description: 'Conversational with Claude Haiku and GPT-5 verification',
  },
  [Domain.TOOL]: {
    drafter: 'gpt-5-mini', // GPT-5 Mini - good tool calling ($0.25/M)
    verifier: 'gpt-5', // GPT-5 - excellent function calling
    threshold: 0.75,
    validationMethod: 'syntax',
    temperature: 0.2,
    description: 'Tool calling with GPT-5 Mini and GPT-5 verification',
  },
  [Domain.RAG]: {
    drafter: 'gpt-5-mini', // GPT-5 Mini - good context handling ($0.25/M)
    verifier: 'claude-opus-4-5-20251101', // Opus 4.5 - best context synthesis
    threshold: 0.80,
    validationMethod: 'quality',
    temperature: 0.3,
    description: 'RAG with GPT-5 Mini and Opus 4.5 context verification',
  },
  [Domain.SUMMARY]: {
    drafter: 'claude-3-5-haiku-20241022', // Claude Haiku - fast summarization
    verifier: 'claude-sonnet-4-5-20250929', // Sonnet 4.5 - quality summaries
    threshold: 0.70,
    validationMethod: 'quality',
    temperature: 0.5,
    description: 'Summarization with Claude Haiku and Sonnet 4.5 verification',
  },
  [Domain.TRANSLATION]: {
    drafter: 'gpt-5-mini', // GPT-5 Mini - good multilingual ($0.25/M)
    verifier: 'gpt-5', // GPT-5 - excellent translation
    threshold: 0.80,
    validationMethod: 'quality',
    temperature: 0.3,
    description: 'Translation with GPT-5 Mini and GPT-5 verification',
  },
  [Domain.MULTIMODAL]: {
    drafter: 'gpt-5-mini', // GPT-5 Mini - vision capable ($0.25/M)
    verifier: 'claude-opus-4-5-20251101', // Opus 4.5 - best multimodal reasoning
    threshold: 0.75,
    validationMethod: 'quality',
    temperature: 0.4,
    description: 'Multimodal with GPT-5 Mini and Opus 4.5 verification',
  },
};

/**
 * Get a built-in domain configuration.
 */
export function getBuiltinDomainConfig(domain: Domain): DomainConfig | undefined {
  return BUILTIN_DOMAIN_CONFIGS[domain];
}

/**
 * Convert ValidationMethod enum to DomainValidationMethod string.
 */
export function validationMethodToDomain(method: ValidationMethod): DomainValidationMethod {
  switch (method) {
    case ValidationMethod.NONE:
      return 'none';
    case ValidationMethod.SYNTAX_CHECK:
      return 'syntax';
    case ValidationMethod.FACT_CHECK:
      return 'fact';
    case ValidationMethod.SAFETY_CHECK:
      return 'safety';
    case ValidationMethod.QUALITY_CHECK:
    case ValidationMethod.FULL_QUALITY:
      return 'quality';
    case ValidationMethod.SEMANTIC:
      return 'semantic';
    case ValidationMethod.CUSTOM:
      return 'custom';
    default:
      return 'quality';
  }
}

/**
 * Convert DomainValidationMethod string to ValidationMethod enum.
 */
export function domainValidationToMethod(validation: DomainValidationMethod): ValidationMethod {
  switch (validation) {
    case 'none':
      return ValidationMethod.NONE;
    case 'syntax':
      return ValidationMethod.SYNTAX_CHECK;
    case 'fact':
      return ValidationMethod.FACT_CHECK;
    case 'safety':
      return ValidationMethod.SAFETY_CHECK;
    case 'quality':
      return ValidationMethod.QUALITY_CHECK;
    case 'semantic':
      return ValidationMethod.SEMANTIC;
    case 'custom':
      return ValidationMethod.CUSTOM;
    default:
      return ValidationMethod.QUALITY_CHECK;
  }
}
