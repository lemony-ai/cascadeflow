/**
 * Quality validation and confidence scoring for cascadeflow
 *
 * Based on Python quality validation with TypeScript patterns
 */

import type { QueryComplexity } from './types';
import { QueryResponseAlignmentScorer } from './alignment';
import { ProductionConfidenceEstimator, type ConfidenceAnalysis } from './confidence';
import { ComplexityDetector } from './complexity';
// SemanticQualityChecker is imported dynamically to avoid loading @cascadeflow/ml dependencies
// when they're not needed (fixes n8n crash issue)

/**
 * Quality validation result
 */
export interface QualityResult {
  /** Whether quality check passed */
  passed: boolean;

  /** Overall quality score (0-1) */
  score: number;

  /** Confidence score from logprobs (0-1) */
  confidence: number;

  /** Method used for scoring */
  method: 'logprobs' | 'heuristic' | 'hybrid';

  /** Reason for pass/fail */
  reason: string;

  /** Additional details */
  details?: {
    /** Average logprob */
    avgLogprob?: number;

    /** Minimum logprob */
    minLogprob?: number;

    /** Content length check */
    lengthOk?: boolean;

    /** Word count */
    wordCount?: number;

    /** Uncertainty markers found */
    uncertaintyMarkers?: string[];

    /** Alignment score (0-1) from AlignmentScorer */
    alignmentScore?: number;

    /** Alignment reasoning */
    alignmentReasoning?: string;

    /** Semantic similarity score (0-1) from ML embeddings */
    semanticSimilarity?: number;
  };
}

/**
 * Quality configuration
 */
export interface QualityConfig {
  /** Minimum confidence threshold (0-1) - fallback if confidenceThresholds not provided */
  minConfidence: number;

  /** Adaptive confidence thresholds by complexity (overrides minConfidence) */
  confidenceThresholds?: {
    trivial?: number;
    simple?: number;
    moderate?: number;
    hard?: number;
    expert?: number;
  };

  /** Minimum word count */
  minWordCount: number;

  /** Enable logprobs-based scoring */
  useLogprobs: boolean;

  /** Fallback to heuristic if logprobs unavailable */
  fallbackToHeuristic: boolean;

  /** Strict mode (fail on any warning signs) */
  strictMode: boolean;

  /** Enable alignment scoring (query-response alignment check) */
  useAlignmentScoring: boolean;

  /** Minimum alignment score (0-1, default: 0.15 - alignment floor) */
  minAlignmentScore: number;

  /** Enable ML-based semantic validation (requires @cascadeflow/ml) */
  useSemanticValidation?: boolean;

  /** Minimum semantic similarity score (0-1, default: 0.5) */
  semanticThreshold?: number;

  /** Enable production-grade confidence estimation (multi-signal approach) */
  useProductionConfidence?: boolean;

  /** Provider name for production confidence calibration (e.g., 'openai', 'anthropic') */
  provider?: string;
}

/**
 * Default quality configuration (production-grade)
 */
export const DEFAULT_QUALITY_CONFIG: QualityConfig = {
  minConfidence: 0.7,
  minWordCount: 10,
  useLogprobs: true,
  fallbackToHeuristic: true,
  strictMode: false,
  useAlignmentScoring: true,
  minAlignmentScore: 0.15, // Alignment floor from Python
};

/**
 * CASCADE-OPTIMIZED configuration (matches Python for_cascade())
 *
 * Research-backed thresholds for optimal cascade performance.
 * Target: 50-60% acceptance rate, 94-96% quality
 *
 * Use this for speculative cascade systems with draft + verifier.
 */
export const CASCADE_QUALITY_CONFIG: QualityConfig = {
  minConfidence: 0.40,  // Much lower than production (0.7)
  minWordCount: 5,      // Relaxed from 10
  useLogprobs: true,
  fallbackToHeuristic: true,
  strictMode: false,
  useAlignmentScoring: true,
  minAlignmentScore: 0.15, // Alignment floor
  useSemanticValidation: false, // Disable ML validation for cascade (not needed, saves deps)
};

/**
 * Quality configuration factory methods
 *
 * Provides preset configurations for different use cases:
 * - `forProduction()`: Balanced quality (98%, 30-40% acceptance)
 * - `forDevelopment()`: More lenient (95%, 40-50% acceptance)
 * - `strict()`: High quality bar (99%+, 15-25% acceptance)
 * - `forCascade()`: CASCADE-optimized (95%, 50-60% acceptance)
 */
export class QualityConfigFactory {
  /**
   * Production configuration - balanced quality
   *
   * Target: 98% quality, ~30-40% acceptance
   * Use case: High-quality applications, research, quality-critical systems
   *
   * @example
   * ```typescript
   * const validator = new QualityValidator(QualityConfigFactory.forProduction());
   * ```
   */
  static forProduction(): QualityConfig {
    return {
      minConfidence: 0.73, // Default fallback
      confidenceThresholds: {
        trivial: 0.60,
        simple: 0.68,
        moderate: 0.73,
        hard: 0.83,
        expert: 0.88,
      },
      minWordCount: 10,
      useLogprobs: true,
      fallbackToHeuristic: true,
      strictMode: false,
      useAlignmentScoring: true,
      minAlignmentScore: 0.15,
      useSemanticValidation: false,
    };
  }

  /**
   * Development configuration - more lenient
   *
   * Target: 95% quality, ~40-50% acceptance
   * Use case: Testing, debugging, iterative development
   *
   * @example
   * ```typescript
   * const validator = new QualityValidator(QualityConfigFactory.forDevelopment());
   * ```
   */
  static forDevelopment(): QualityConfig {
    return {
      minConfidence: 0.70, // Default fallback
      confidenceThresholds: {
        trivial: 0.50,
        simple: 0.60,
        moderate: 0.70,
        hard: 0.75,
        expert: 0.80,
      },
      minWordCount: 8,
      useLogprobs: true,
      fallbackToHeuristic: true,
      strictMode: false,
      useAlignmentScoring: true,
      minAlignmentScore: 0.15,
      useSemanticValidation: false,
    };
  }

  /**
   * Strict configuration - high quality bar
   *
   * Target: 99%+ quality, ~15-25% acceptance
   * Use case: Mission-critical, customer-facing, zero-tolerance systems
   *
   * @example
   * ```typescript
   * const validator = new QualityValidator(QualityConfigFactory.strict());
   * ```
   */
  static strict(): QualityConfig {
    return {
      minConfidence: 0.85, // Default fallback
      confidenceThresholds: {
        trivial: 0.70,
        simple: 0.80,
        moderate: 0.85,
        hard: 0.90,
        expert: 0.95,
      },
      minWordCount: 15,
      useLogprobs: true,
      fallbackToHeuristic: true,
      strictMode: true,
      useAlignmentScoring: true,
      minAlignmentScore: 0.20, // Higher alignment floor for strict mode
      useSemanticValidation: true, // Enable ML validation for strictest quality
      semanticThreshold: 0.6, // Higher threshold for semantic similarity
      useProductionConfidence: true, // Enable production-grade multi-signal confidence
    };
  }

  /**
   * CASCADE-OPTIMIZED configuration
   *
   * Research-backed thresholds for optimal cascade performance.
   *
   * Target Metrics:
   * - Acceptance rate: 50-60% (optimal for cascade)
   * - Quality: 94-96% (acceptable trade-off from 98%)
   * - Cost savings: 50-60%
   * - Speedup: 1.8-2.1x
   *
   * Research Basis:
   * - SmartSpec (2024): "Target 40-70% acceptance for optimal cost/quality"
   * - Medusa (2024): "50-80% acceptance with temperature-aware thresholds"
   * - HiSpec (2024): "Relaxed gates achieve 60-80% acceptance, 94% quality"
   *
   * When to use:
   * ✓ Speculative cascade systems (draft + verifier)
   * ✓ Cost optimization priority (50%+ savings)
   * ✓ Speed optimization priority (2x+ speedup)
   * ✓ High-throughput systems (1000+ queries/sec)
   *
   * When NOT to use:
   * ✗ Customer-facing quality-critical apps (use forProduction)
   * ✗ Zero-tolerance error systems (use strict)
   *
   * @example
   * ```typescript
   * const validator = new QualityValidator(QualityConfigFactory.forCascade());
   * ```
   */
  static forCascade(): QualityConfig {
    return {
      minConfidence: 0.55, // Default fallback
      confidenceThresholds: {
        trivial: 0.25, // High acceptance for simple facts
        simple: 0.40,  // Good acceptance for basic queries
        moderate: 0.55, // Balanced quality/speed
        hard: 0.70,    // Selective acceptance
        expert: 0.80,  // Very selective
      },
      minWordCount: 5, // Relaxed minimum length
      useLogprobs: true,
      fallbackToHeuristic: true,
      strictMode: false,
      useAlignmentScoring: true,
      minAlignmentScore: 0.15, // Standard alignment floor
      useSemanticValidation: false, // Disabled for cascade speed
    };
  }

  /**
   * Permissive configuration - very lenient
   *
   * Target: 90% quality, ~60-70% acceptance
   * Use case: Rapid prototyping, brainstorming, creative tasks
   *
   * @example
   * ```typescript
   * const validator = new QualityValidator(QualityConfigFactory.permissive());
   * ```
   */
  static permissive(): QualityConfig {
    return {
      minConfidence: 0.50, // Default fallback
      confidenceThresholds: {
        trivial: 0.30,
        simple: 0.40,
        moderate: 0.50,
        hard: 0.60,
        expert: 0.70,
      },
      minWordCount: 3,
      useLogprobs: true,
      fallbackToHeuristic: true,
      strictMode: false,
      useAlignmentScoring: true,
      minAlignmentScore: 0.10, // More lenient alignment
      useSemanticValidation: false,
    };
  }
}

/**
 * Uncertainty markers that indicate low confidence
 */
const UNCERTAINTY_MARKERS = [
  "i'm not sure",
  "i don't know",
  'i cannot',
  'i am unable',
  'maybe',
  'possibly',
  'perhaps',
  'unclear',
  'uncertain',
  'cannot determine',
  'insufficient information',
  'not enough',
  'unsure',
  'doubt',
];

/**
 * Calculate confidence score from logprobs
 *
 * Converts average log probability to a confidence score (0-1)
 *
 * @param logprobs - Array of log probabilities
 * @returns Confidence score (0-1)
 */
export function calculateConfidenceFromLogprobs(logprobs: number[]): number {
  if (!logprobs || logprobs.length === 0) {
    return 0;
  }

  // Calculate average logprob
  const avgLogprob = logprobs.reduce((sum, lp) => sum + lp, 0) / logprobs.length;

  // Convert to probability (exp of logprob)
  // Note: logprobs are typically negative (e.g., -0.5, -2.0)
  const avgProb = Math.exp(avgLogprob);

  // Clamp to [0, 1] range
  return Math.max(0, Math.min(1, avgProb));
}

/**
 * Estimate confidence from content heuristics
 *
 * Uses various heuristics when logprobs aren't available:
 * - Response length
 * - Presence of uncertainty markers
 * - Content structure
 *
 * @param content - Generated content
 * @param query - Original query
 * @returns Estimated confidence score (0-1)
 */
export function estimateConfidenceFromContent(
  content: string,
  _query: string
): number {
  let confidence = 0.75; // Base confidence

  const contentLower = content.toLowerCase();
  const words = content.split(/\s+/);
  const wordCount = words.length;

  // Check for uncertainty markers
  const foundMarkers: string[] = [];
  for (const marker of UNCERTAINTY_MARKERS) {
    if (contentLower.includes(marker)) {
      foundMarkers.push(marker);
      confidence -= 0.1; // Reduce confidence for each marker
    }
  }

  // Very short responses might be uncertain
  if (wordCount < 10) {
    confidence -= 0.15;
  } else if (wordCount < 20) {
    confidence -= 0.05;
  }

  // Longer, structured responses suggest confidence
  if (wordCount > 50) {
    confidence += 0.05;
  }

  // Multiple paragraphs suggest well-thought response
  const paragraphs = content.split('\n\n').filter((p) => p.trim().length > 0);
  if (paragraphs.length >= 2) {
    confidence += 0.05;
  }

  // Clamp to reasonable range [0.5, 0.95]
  // We never go below 0.5 for heuristic (too unreliable)
  // We never go above 0.95 for heuristic (not as reliable as logprobs)
  return Math.max(0.5, Math.min(0.95, confidence));
}

/**
 * Quality validator
 *
 * Validates response quality using logprobs and/or heuristics
 */
export class QualityValidator {
  private config: QualityConfig;
  private alignmentScorer: QueryResponseAlignmentScorer | null = null;
  private semanticChecker: any = null; // Lazy-loaded to avoid @cascadeflow/ml dependency
  private semanticCheckerInitialized: boolean = false;
  private productionConfidenceEstimator: ProductionConfidenceEstimator | null = null;
  private complexityDetector: ComplexityDetector | null = null;

  constructor(config: Partial<QualityConfig> = {}) {
    this.config = { ...DEFAULT_QUALITY_CONFIG, ...config };

    // Validate minConfidence
    if (this.config.minConfidence < 0 || this.config.minConfidence > 1) {
      throw new Error(`minConfidence must be between 0 and 1, got ${this.config.minConfidence}`);
    }

    // Validate confidenceThresholds if provided
    if (this.config.confidenceThresholds) {
      const thresholds = this.config.confidenceThresholds;
      for (const [level, value] of Object.entries(thresholds)) {
        if (value !== undefined && (value < 0 || value > 1)) {
          throw new Error(`confidenceThresholds.${level} must be between 0 and 1, got ${value}`);
        }
      }
    }

    // Initialize alignment scorer if enabled
    if (this.config.useAlignmentScoring) {
      this.alignmentScorer = new QueryResponseAlignmentScorer();
    }

    // Initialize semantic checker immediately if explicitly enabled
    // This allows model pre-loading to avoid latency on first validation
    // Note: Only loads if useSemanticValidation is true (not undefined)
    if (this.config.useSemanticValidation === true) {
      this.initSemanticChecker();
    }

    // Initialize production confidence estimator if enabled
    if (this.config.useProductionConfidence === true) {
      const provider = this.config.provider || 'openai';
      this.productionConfidenceEstimator = new ProductionConfidenceEstimator(provider);
      this.complexityDetector = new ComplexityDetector();
    }
  }

  /**
   * Initialize semantic quality checker (dynamic import to avoid static @cascadeflow/ml dependency)
   * Called at construction time to allow model pre-loading
   */
  private async initSemanticChecker(): Promise<void> {
    if (this.semanticCheckerInitialized) {
      return;
    }

    this.semanticCheckerInitialized = true;

    try {
      const { SemanticQualityChecker } = await import('./quality-semantic');
      this.semanticChecker = new SemanticQualityChecker(
        this.config.semanticThreshold || 0.5
      );
    } catch (e: any) {
      // Semantic validation dependencies not available - gracefully degrade
      if (e?.code !== 'ERR_MODULE_NOT_FOUND' && !e?.message?.includes('Cannot find module')) {
        console.warn(
          'SemanticQualityChecker not available (install @cascadeflow/ml for ML-based validation)'
        );
      }
      this.semanticChecker = null;
    }
  }

  /**
   * Get the appropriate confidence threshold for given complexity level
   *
   * @param complexity - Query complexity level
   * @returns Confidence threshold to use (0-1)
   */
  private getThresholdForComplexity(complexity?: QueryComplexity): number {
    // If no complexity provided, use default
    if (!complexity) {
      return this.config.minConfidence;
    }

    // If confidenceThresholds configured, use complexity-specific threshold
    if (this.config.confidenceThresholds) {
      const thresholds = this.config.confidenceThresholds;

      // Get threshold for specific complexity, fallback to default
      switch (complexity) {
        case 'trivial':
          return thresholds.trivial ?? this.config.minConfidence;
        case 'simple':
          return thresholds.simple ?? this.config.minConfidence;
        case 'moderate':
          return thresholds.moderate ?? this.config.minConfidence;
        case 'hard':
          return thresholds.hard ?? this.config.minConfidence;
        case 'expert':
          return thresholds.expert ?? this.config.minConfidence;
        default: {
          // TypeScript will catch this if we add new complexity levels
          const _exhaustiveCheck: never = complexity;
          console.warn(`Unknown complexity level: ${_exhaustiveCheck}, using default threshold`);
          return this.config.minConfidence;
        }
      }
    }

    // Fallback to default threshold
    return this.config.minConfidence;
  }

  /**
   * Validate response quality
   *
   * @param content - Generated content
   * @param query - Original query
   * @param logprobs - Log probabilities (if available)
   * @param complexity - Query complexity level (for adaptive thresholds)
   * @param thresholdOverride - Per-model threshold override (takes precedence over complexity-based thresholds)
   * @returns Quality validation result
   */
  async validate(
    content: string,
    query: string,
    logprobs?: number[],
    complexity?: QueryComplexity,
    thresholdOverride?: number
  ): Promise<QualityResult> {
    // Step 1: Calculate confidence
    let confidence: number;
    let method: 'logprobs' | 'heuristic' | 'hybrid';
    let avgLogprob: number | undefined;
    let minLogprob: number | undefined;
    let productionAnalysis: ConfidenceAnalysis | undefined;

    // Use production confidence estimator if enabled (most sophisticated)
    if (this.config.useProductionConfidence && this.productionConfidenceEstimator) {
      // Get query difficulty from complexity if available
      let queryDifficulty: number | undefined;
      if (complexity && this.complexityDetector) {
        const complexityMap: Record<QueryComplexity, number> = {
          trivial: 0.1,
          simple: 0.3,
          moderate: 0.5,
          hard: 0.7,
          expert: 0.9,
        };
        queryDifficulty = complexityMap[complexity];
      }

      productionAnalysis = this.productionConfidenceEstimator.estimate(content, {
        query,
        logprobs,
        queryDifficulty,
      });

      confidence = productionAnalysis.finalConfidence;
      method = productionAnalysis.methodUsed as 'logprobs' | 'heuristic' | 'hybrid';

      if (logprobs && logprobs.length > 0) {
        avgLogprob = logprobs.reduce((sum, lp) => sum + lp, 0) / logprobs.length;
        minLogprob = Math.min(...logprobs);
      }
    } else if (this.config.useLogprobs && logprobs && logprobs.length > 0) {
      // Use logprobs for confidence
      confidence = calculateConfidenceFromLogprobs(logprobs);
      method = 'logprobs';

      avgLogprob =
        logprobs.reduce((sum, lp) => sum + lp, 0) / logprobs.length;
      minLogprob = Math.min(...logprobs);

      // If heuristic fallback is enabled, blend with heuristic
      if (this.config.fallbackToHeuristic) {
        const heuristicConfidence = estimateConfidenceFromContent(
          content,
          query
        );
        // Weighted average: 70% logprobs, 30% heuristic
        confidence = confidence * 0.7 + heuristicConfidence * 0.3;
        method = 'hybrid';
      }
    } else if (this.config.fallbackToHeuristic) {
      // Fallback to heuristic
      confidence = estimateConfidenceFromContent(content, query);
      method = 'heuristic';
    } else {
      // No scoring method available
      return {
        passed: false,
        score: 0,
        confidence: 0,
        method: 'heuristic',
        reason: 'No quality scoring method available',
      };
    }

    // Step 2: Check content length
    const words = content.split(/\s+/);
    const wordCount = words.length;
    const lengthOk = wordCount >= this.config.minWordCount;

    // Step 3: Check for uncertainty markers (for details)
    const contentLower = content.toLowerCase();
    const uncertaintyMarkers: string[] = [];
    for (const marker of UNCERTAINTY_MARKERS) {
      if (contentLower.includes(marker)) {
        uncertaintyMarkers.push(marker);
      }
    }

    // Step 4: Calculate alignment score
    let alignmentScore: number | undefined;
    let alignmentReasoning: string | undefined;
    let alignmentPassed = true;

    if (this.config.useAlignmentScoring && this.alignmentScorer) {
      const analysis = this.alignmentScorer.score(query, content, 0.5, true);
      alignmentScore = analysis.alignmentScore;
      alignmentReasoning = analysis.reasoning;

      // Check if alignment passes floor threshold (0.15)
      alignmentPassed = alignmentScore >= this.config.minAlignmentScore;
    }

    // Step 4.5: ML semantic validation (optional)
    let semanticSimilarity: number | undefined;
    let semanticPassed = true;

    if (this.config.useSemanticValidation) {
      // Ensure semantic checker is initialized (should be done in constructor, but await completion)
      await this.initSemanticChecker();

      if (this.semanticChecker) {
        const isAvailable = await this.semanticChecker.isAvailable();

        if (isAvailable) {
          const semanticResult = await this.semanticChecker.checkSimilarity(query, content);
          semanticSimilarity = semanticResult.similarity;
          semanticPassed = semanticResult.passed;
        }
      }
    }

    // Step 5: Calculate overall quality score
    let score = confidence;

    // Penalize for short content
    if (!lengthOk) {
      score *= 0.8;
    }

    // Penalize for uncertainty markers (in strict mode)
    if (this.config.strictMode && uncertaintyMarkers.length > 0) {
      score *= Math.max(0.5, 1 - uncertaintyMarkers.length * 0.1);
    }

    // Apply alignment floor if enabled (matches Python behavior)
    if (
      this.config.useAlignmentScoring &&
      alignmentScore !== undefined &&
      !alignmentPassed
    ) {
      // If alignment is below floor, cap the score at the floor
      score = Math.min(score, this.config.minAlignmentScore);
    }

    // Step 6: Determine pass/fail using threshold (per-model override or complexity-aware)
    const effectiveThreshold = thresholdOverride ?? this.getThresholdForComplexity(complexity);
    const passed =
      score >= effectiveThreshold &&
      lengthOk &&
      alignmentPassed &&
      semanticPassed;

    // Step 7: Generate reason
    let reason: string;
    if (passed) {
      reason = `Quality check passed (score: ${score.toFixed(2)}, confidence: ${confidence.toFixed(2)}, threshold: ${effectiveThreshold.toFixed(2)})`;
      if (complexity) {
        reason += `, complexity: ${complexity}`;
      }
      if (alignmentScore !== undefined) {
        reason += `, alignment: ${alignmentScore.toFixed(2)}`;
      }
      if (semanticSimilarity !== undefined) {
        reason += `, semantic: ${semanticSimilarity.toFixed(2)}`;
      }
    } else if (!lengthOk) {
      reason = `Content too short (${wordCount} words, minimum: ${this.config.minWordCount})`;
    } else if (!semanticPassed && semanticSimilarity !== undefined) {
      reason = `Semantic similarity too low (${semanticSimilarity.toFixed(2)}, minimum: ${this.config.semanticThreshold || 0.5})`;
    } else if (!alignmentPassed && alignmentScore !== undefined) {
      reason = `Alignment too low (${alignmentScore.toFixed(2)}, minimum: ${this.config.minAlignmentScore})`;
    } else {
      reason = `Confidence too low (${confidence.toFixed(2)}, threshold: ${effectiveThreshold.toFixed(2)} for ${complexity || 'unknown'} complexity)`;
    }

    return {
      passed,
      score,
      confidence,
      method,
      reason,
      details: {
        avgLogprob,
        minLogprob,
        lengthOk,
        wordCount,
        uncertaintyMarkers:
          uncertaintyMarkers.length > 0 ? uncertaintyMarkers : undefined,
        alignmentScore,
        alignmentReasoning,
        semanticSimilarity,
        // Include production analysis if used
        productionConfidence: productionAnalysis
          ? {
              methodUsed: productionAnalysis.methodUsed,
              components: productionAnalysis.components,
              alignmentFloorApplied: productionAnalysis.alignmentFloorApplied,
              queryDifficulty: productionAnalysis.queryDifficulty,
            }
          : undefined,
      },
    };
  }

  /**
   * Update configuration
   */
  updateConfig(config: Partial<QualityConfig>): void {
    this.config = { ...this.config, ...config };

    // Re-initialize alignment scorer if config changed
    if (this.config.useAlignmentScoring && !this.alignmentScorer) {
      this.alignmentScorer = new QueryResponseAlignmentScorer();
    } else if (!this.config.useAlignmentScoring) {
      this.alignmentScorer = null;
    }
  }

  /**
   * Get current configuration
   */
  getConfig(): QualityConfig {
    return { ...this.config };
  }

  // ==========================================
  // Static Factory Methods
  // ==========================================

  /**
   * Create a production-grade quality validator
   *
   * Target: 98% quality, ~30-40% acceptance
   * Use case: High-quality applications, research, quality-critical systems
   *
   * @example
   * ```typescript
   * const validator = QualityValidator.forProduction();
   * const result = await validator.validate(content, query, logprobs);
   * ```
   */
  static forProduction(): QualityValidator {
    return new QualityValidator(QualityConfigFactory.forProduction());
  }

  /**
   * Create a development-friendly quality validator
   *
   * Target: 95% quality, ~40-50% acceptance
   * Use case: Testing, debugging, iterative development
   *
   * @example
   * ```typescript
   * const validator = QualityValidator.forDevelopment();
   * const result = await validator.validate(content, query);
   * ```
   */
  static forDevelopment(): QualityValidator {
    return new QualityValidator(QualityConfigFactory.forDevelopment());
  }

  /**
   * Create a strict quality validator with high quality bar
   *
   * Target: 99%+ quality, ~15-25% acceptance
   * Use case: Mission-critical, customer-facing, zero-tolerance systems
   *
   * @example
   * ```typescript
   * const validator = QualityValidator.strict();
   * const result = await validator.validate(content, query, logprobs);
   * ```
   */
  static strict(): QualityValidator {
    return new QualityValidator(QualityConfigFactory.strict());
  }

  /**
   * Create a CASCADE-optimized quality validator
   *
   * Research-backed thresholds for optimal cascade performance.
   *
   * Target Metrics:
   * - Acceptance rate: 50-60% (optimal for cascade)
   * - Quality: 94-96% (acceptable trade-off from 98%)
   * - Cost savings: 50-60%
   * - Speedup: 1.8-2.1x
   *
   * When to use:
   * ✓ Speculative cascade systems (draft + verifier)
   * ✓ Cost optimization priority (50%+ savings)
   * ✓ Speed optimization priority (2x+ speedup)
   *
   * @example
   * ```typescript
   * const validator = QualityValidator.forCascade();
   * const result = await validator.validate(draftContent, query);
   * ```
   */
  static forCascade(): QualityValidator {
    return new QualityValidator(QualityConfigFactory.forCascade());
  }

  /**
   * Create a permissive quality validator
   *
   * Target: 90% quality, ~60-70% acceptance
   * Use case: Rapid prototyping, brainstorming, creative tasks
   *
   * @example
   * ```typescript
   * const validator = QualityValidator.permissive();
   * const result = await validator.validate(content, query);
   * ```
   */
  static permissive(): QualityValidator {
    return new QualityValidator(QualityConfigFactory.permissive());
  }
}

