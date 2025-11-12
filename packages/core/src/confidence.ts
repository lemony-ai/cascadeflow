/**
 * Production-Grade Confidence Estimation
 *
 * Multi-signal confidence estimation using:
 * 1. Query difficulty estimation
 * 2. Query-response alignment
 * 3. Logprobs (when available) - Primary signal
 * 4. Semantic quality analysis - Always available
 * 5. Provider calibration - Empirical adjustments
 * 6. Temperature-aware scaling
 *
 * Research-based confidence calculation matching Python implementation.
 *
 * References:
 * - "Teaching Models to Express Their Uncertainty in Words" (OpenAI, 2022)
 * - "Language Models (Mostly) Know What They Know" (Kadavath et al., 2022)
 * - "Calibrating Language Model Probabilities" (Anthropic, 2023)
 * - "Context-Aware Dual-Metric Framework for Confidence Estimation" (2025)
 *
 * @module confidence
 */

import { QueryResponseAlignmentScorer } from './alignment';
import type { ComplexityResult } from './complexity';

/**
 * Provider-specific calibration settings
 *
 * Empirically tuned for each provider based on production data
 */
export interface ProviderCalibration {
  /** Base multiplier for provider (0.8-1.0) */
  baseMultiplier: number;

  /** Whether provider supports logprobs */
  logprobsAvailable: boolean;

  /** Confidence boost/penalty by finish reason */
  finishReasonBoost: Record<string, number>;

  /** Temperature penalty function */
  temperaturePenalty: (temp: number) => number;

  /** Minimum allowed confidence */
  minConfidence: number;

  /** Maximum allowed confidence */
  maxConfidence: number;
}

/**
 * Provider calibration map
 *
 * Tuned based on empirical performance data
 */
export const PROVIDER_CONFIDENCE_CALIBRATION: Record<string, ProviderCalibration> = {
  openai: {
    baseMultiplier: 1.0,
    logprobsAvailable: true,
    finishReasonBoost: {
      stop: 0.05,
      length: -0.1,
    },
    temperaturePenalty: (t) => 0.05 * t,
    minConfidence: 0.3,
    maxConfidence: 0.98,
  },
  anthropic: {
    baseMultiplier: 0.95,
    logprobsAvailable: false,
    finishReasonBoost: {
      end_turn: 0.05,
      max_tokens: -0.1,
    },
    temperaturePenalty: (t) => 0.05 * t,
    minConfidence: 0.3,
    maxConfidence: 0.95,
  },
  groq: {
    baseMultiplier: 0.9,
    logprobsAvailable: false,
    finishReasonBoost: {
      stop: 0.05,
      length: -0.1,
    },
    temperaturePenalty: (t) => 0.08 * t,
    minConfidence: 0.25,
    maxConfidence: 0.92,
  },
  together: {
    baseMultiplier: 1.0,
    logprobsAvailable: true,
    finishReasonBoost: {
      stop: 0.05,
      length: -0.1,
    },
    temperaturePenalty: (t) => 0.05 * t,
    minConfidence: 0.3,
    maxConfidence: 0.98,
  },
  vllm: {
    baseMultiplier: 1.0,
    logprobsAvailable: true,
    finishReasonBoost: {
      stop: 0.05,
      length: -0.1,
    },
    temperaturePenalty: (t) => 0.05 * t,
    minConfidence: 0.3,
    maxConfidence: 0.98,
  },
  ollama: {
    baseMultiplier: 0.85,
    logprobsAvailable: false,
    finishReasonBoost: {
      stop: 0.05,
    },
    temperaturePenalty: (t) => 0.1 * t,
    minConfidence: 0.2,
    maxConfidence: 0.88,
  },
  huggingface: {
    baseMultiplier: 0.9,
    logprobsAvailable: false,
    finishReasonBoost: {
      stop: 0.05,
    },
    temperaturePenalty: (t) => 0.08 * t,
    minConfidence: 0.25,
    maxConfidence: 0.92,
  },
};

/**
 * Confidence analysis result
 *
 * Contains detailed breakdown of confidence calculation
 */
export interface ConfidenceAnalysis {
  /** Final confidence score (0-1) */
  finalConfidence: number;

  /** Confidence from logprobs (if available) */
  logprobsConfidence?: number;

  /** Confidence from semantic analysis */
  semanticConfidence: number;

  /** Confidence after calibration */
  calibratedConfidence: number;

  /** Individual component scores */
  components: Record<string, number>;

  /** Method used for estimation */
  methodUsed:
    | 'logprobs'
    | 'semantic'
    | 'hybrid'
    | 'multi-signal-hybrid'
    | 'multi-signal-semantic';

  /** Query difficulty score (0-1) */
  queryDifficulty?: number;

  /** Alignment score (0-1) */
  alignmentScore?: number;

  /** Whether alignment floor was applied */
  alignmentFloorApplied: boolean;
}

/**
 * Options for confidence estimation
 */
export interface ConfidenceEstimationOptions {
  /** Original query (strongly recommended) */
  query?: string;

  /** Token log probabilities (if available) */
  logprobs?: number[];

  /** Tokens (if available) */
  tokens?: string[];

  /** Sampling temperature */
  temperature?: number;

  /** Completion finish reason */
  finishReason?: string;

  /** Query difficulty/complexity (0-1) */
  queryDifficulty?: number;

  /** Additional metadata */
  metadata?: Record<string, any>;
}

/**
 * Production-grade confidence estimator
 *
 * Implements multi-signal approach with provider calibration,
 * matching Python implementation.
 *
 * Hierarchy (best to worst):
 * 1. Multi-signal with logprobs (query + alignment + semantic + logprobs) - Best
 * 2. Multi-signal semantic (query + alignment + semantic) - Good
 * 3. Hybrid (logprobs + semantic) - Acceptable
 * 4. Semantic only - Fallback
 *
 * @example
 * ```typescript
 * const estimator = new ProductionConfidenceEstimator('openai');
 *
 * const analysis = estimator.estimate(response, {
 *   query: 'What is TypeScript?',
 *   logprobs: [-0.1, -0.2, -0.15],
 *   temperature: 0.7,
 *   queryDifficulty: 0.3
 * });
 *
 * console.log(`Confidence: ${analysis.finalConfidence.toFixed(2)}`);
 * console.log(`Method: ${analysis.methodUsed}`);
 * ```
 */
export class ProductionConfidenceEstimator {
  private provider: string;
  private calibration: ProviderCalibration;
  private alignmentScorer: QueryResponseAlignmentScorer;

  constructor(provider: string = 'openai') {
    this.provider = provider;
    this.calibration =
      PROVIDER_CONFIDENCE_CALIBRATION[provider.toLowerCase()] ??
      PROVIDER_CONFIDENCE_CALIBRATION.openai;

    this.alignmentScorer = new QueryResponseAlignmentScorer();
  }

  /**
   * Estimate confidence using multi-signal approach
   *
   * @param response - Model response text
   * @param options - Estimation options
   * @returns Detailed confidence analysis
   */
  estimate(response: string, options: ConfidenceEstimationOptions = {}): ConfidenceAnalysis {
    const {
      query,
      logprobs,
      tokens,
      temperature = 0.7,
      finishReason,
      queryDifficulty: providedQueryDifficulty,
    } = options;

    const components: Record<string, number> = {};
    let alignmentScore: number | undefined;
    let queryDifficulty: number | undefined = providedQueryDifficulty;

    // 1. Query difficulty (if not provided)
    if (query && queryDifficulty === undefined) {
      queryDifficulty = this.estimateQueryDifficulty(query);
      components.queryDifficulty = queryDifficulty;
    }

    // 2. Primary: Use logprobs if available
    let logprobsConf: number | undefined;
    if (logprobs && logprobs.length > 0) {
      logprobsConf = this.calculateFromLogprobs(logprobs, tokens, response);
      components.logprobs = logprobsConf;
    }

    // 3. Semantic analysis (always compute)
    const semanticConf = this.analyzeSemanticQuality(response, query);
    components.semantic = semanticConf;

    // 4. Query-response alignment
    if (query) {
      alignmentScore = this.alignmentScorer.score(query, response, queryDifficulty ?? 0.5);
      components.alignment = alignmentScore;
    }

    // 5. Combine signals
    let baseConfidence: number;
    let method: ConfidenceAnalysis['methodUsed'];

    if (logprobsConf !== undefined && query && alignmentScore !== undefined) {
      // Full multi-signal (all signals available)
      baseConfidence =
        0.5 * logprobsConf +
        0.2 * semanticConf +
        0.2 * alignmentScore +
        0.1 * (1.0 - (queryDifficulty ?? 0.5));
      method = 'multi-signal-hybrid';
    } else if (logprobsConf !== undefined) {
      // Hybrid: logprobs + semantic (no query info)
      baseConfidence = 0.75 * logprobsConf + 0.25 * semanticConf;
      method = 'hybrid';
    } else if (query && alignmentScore !== undefined) {
      // Semantic + alignment + query (no logprobs)
      baseConfidence =
        0.4 * semanticConf + 0.4 * alignmentScore + 0.2 * (1.0 - (queryDifficulty ?? 0.5));
      method = 'multi-signal-semantic';
    } else {
      // Fallback: Semantic only
      baseConfidence = semanticConf;
      method = 'semantic';
    }

    components.base = baseConfidence;

    // 6. Apply provider calibration
    let calibrated = this.applyCalibration(baseConfidence, temperature, finishReason);
    components.calibrated = calibrated;

    // 7. CRITICAL SAFETY: Alignment floor (prevents off-topic acceptance)
    let alignmentFloorApplied = false;

    if (alignmentScore !== undefined && alignmentScore < 0.25) {
      const originalConfidence = calibrated;

      // Progressive capping based on alignment severity
      if (alignmentScore < 0.15) {
        // Severely off-topic
        calibrated = Math.min(calibrated, 0.3);
        components.alignmentFloorSeverity = 'severe';
      } else if (alignmentScore < 0.2) {
        // Very poor alignment
        calibrated = Math.min(calibrated, 0.35);
        components.alignmentFloorSeverity = 'very_poor';
      } else {
        // Poor alignment (0.2-0.25)
        calibrated = Math.min(calibrated, 0.4);
        components.alignmentFloorSeverity = 'poor';
      }

      if (calibrated < originalConfidence) {
        alignmentFloorApplied = true;
        components.alignmentFloorApplied = true;
        components.alignmentFloorReduction = originalConfidence - calibrated;
      }
    }

    return {
      finalConfidence: calibrated,
      logprobsConfidence: logprobsConf,
      semanticConfidence: semanticConf,
      calibratedConfidence: calibrated,
      components,
      methodUsed: method,
      queryDifficulty,
      alignmentScore,
      alignmentFloorApplied,
    };
  }

  /**
   * Calculate confidence from logprobs
   *
   * Uses multiple methods:
   * 1. Geometric mean (standard)
   * 2. Harmonic mean (reduces outlier impact)
   * 3. Minimum probability (weakest link)
   * 4. Entropy-based (consistency)
   */
  private calculateFromLogprobs(
    logprobs: number[],
    _tokens?: string[],
    _response?: string
  ): number {
    if (!logprobs || logprobs.length === 0) {
      return 0;
    }

    // Convert to probabilities
    const probs = logprobs.map((lp) => Math.exp(lp));

    // Method 1: Geometric mean
    const geometricMean = Math.exp(logprobs.reduce((sum, lp) => sum + lp, 0) / logprobs.length);

    // Method 2: Harmonic mean of top 80% tokens
    const sortedProbs = [...probs].sort((a, b) => b - a);
    const top80Count = Math.max(1, Math.floor(sortedProbs.length * 0.8));
    const top80Probs = sortedProbs.slice(0, top80Count);
    const harmonicMean =
      top80Probs.length / top80Probs.reduce((sum, p) => sum + (p > 0 ? 1 / p : 0), 0);

    // Method 3: Minimum probability
    const minProb = Math.min(...probs);

    // Method 4: Entropy-based consistency
    const entropy = -probs.reduce((sum, p) => sum + (p > 1e-10 ? p * Math.log(p) : 0), 0);
    const maxEntropy = probs.length > 1 ? Math.log(probs.length) : 1.0;
    const normalizedEntropy = 1.0 - Math.min(entropy / maxEntropy, 1.0);

    // Weighted combination
    const confidence =
      0.5 * geometricMean + 0.2 * harmonicMean + 0.15 * minProb + 0.15 * normalizedEntropy;

    return confidence;
  }

  /**
   * Analyze semantic quality with continuous scoring
   *
   * Uses 5 dimensions:
   * 1. Hedging (0.0-0.30)
   * 2. Completeness (0.0-0.25)
   * 3. Specificity (0.0-0.20)
   * 4. Coherence (0.0-0.15)
   * 5. Directness (0.0-0.10)
   *
   * Total range: 0.20-0.95 (continuous distribution)
   */
  private analyzeSemanticQuality(response: string, _query?: string): number {
    if (!response || response.trim().length < 2) {
      return 0.15;
    }

    const responseLower = response.toLowerCase();
    const responseClean = response.trim();
    const scores: Record<string, number> = {};

    // 1. Hedging score (0.0-0.30)
    const strongHedges = [
      "i don't know",
      "i'm not sure",
      'i cannot',
      "i don't have information",
      "i'm unable to",
      'uncertain',
      'unclear about',
    ];

    const moderateHedges = [
      'probably',
      'might be',
      'could be',
      'perhaps',
      'it seems',
      'appears to',
      'may',
      'possibly',
      'likely',
      'i think',
      'i believe',
    ];

    const strongCount = strongHedges.reduce(
      (sum, h) => sum + (responseLower.match(new RegExp(h, 'g'))?.length ?? 0),
      0
    );
    const moderateCount = moderateHedges.reduce(
      (sum, h) => sum + (responseLower.match(new RegExp(h, 'g'))?.length ?? 0),
      0
    );

    const words = responseClean.split(/\s+/);
    const wordCount = words.length;

    const hedgePenalty =
      wordCount > 0
        ? Math.min(0.3, ((strongCount / wordCount) * 100 * 0.05) + ((moderateCount / wordCount) * 100 * 0.02))
        : 0;

    scores.hedging = 0.3 - hedgePenalty;

    // 2. Completeness score (0.0-0.25)
    const charCount = responseClean.length;
    const sentenceCount = (responseClean.match(/[.!?]+/g)?.length ?? 0) || 1;
    const avgSentenceLength = charCount / sentenceCount;

    let completeness: number;
    if (avgSentenceLength < 10) {
      completeness = 0.05;
    } else if (avgSentenceLength < 30) {
      completeness = 0.05 + ((avgSentenceLength - 10) / 20) * 0.1;
    } else if (avgSentenceLength <= 150) {
      completeness = 0.15 + ((150 - avgSentenceLength) / 120) * 0.1;
    } else {
      completeness = 0.15 - ((avgSentenceLength - 150) / 200) * 0.1;
    }

    scores.completeness = Math.max(0, Math.min(0.25, completeness));

    // 3. Specificity score (0.0-0.20)
    let specificity = 0.1; // Base

    if (/\d+/.test(responseClean)) {
      specificity += 0.05;
    }

    const exampleMarkers = ['for example', 'such as', 'for instance', 'like', 'e.g.'];
    if (exampleMarkers.some((marker) => responseLower.includes(marker))) {
      specificity += 0.03;
    }

    const longWords = words.filter((w) => w.length > 8);
    if (longWords.length > 0) {
      specificity += Math.min(0.02, (longWords.length / words.length) * 0.1);
    }

    scores.specificity = Math.min(0.2, specificity);

    // 4. Coherence score (0.0-0.15)
    let coherence = 0.12; // Start high

    const contradictionPatterns: [RegExp, RegExp][] = [
      [/\byes\b/, /\bno\b/],
      [/\btrue\b/, /\bfalse\b/],
      [/\bcorrect\b/, /\bincorrect\b/],
      [/\bcan\b/, /\bcannot\b/],
    ];

    for (const [p1, p2] of contradictionPatterns) {
      if (p1.test(responseLower) && p2.test(responseLower)) {
        coherence -= 0.04;
      }
    }

    if (wordCount > 10) {
      const uniqueRatio = new Set(words).size / words.length;
      if (uniqueRatio < 0.6) {
        coherence -= (0.6 - uniqueRatio) * 0.15;
      }
    }

    scores.coherence = Math.max(0, Math.min(0.15, coherence));

    // 5. Directness score (0.0-0.10)
    let directness = 0.08; // Base

    const evasivePatterns = [
      'it depends',
      "that's a complex question",
      'there are many factors',
      'it varies',
      "there's no simple answer",
    ];

    const evasiveCount = evasivePatterns.filter((p) => responseLower.includes(p)).length;
    directness -= evasiveCount * 0.03;

    scores.directness = Math.max(0, Math.min(0.1, directness));

    // Total score
    const totalScore = Object.values(scores).reduce((sum, s) => sum + s, 0);
    return Math.max(0.2, Math.min(0.95, totalScore));
  }

  /**
   * Apply provider-specific calibration
   */
  private applyCalibration(
    baseConfidence: number,
    temperature: number,
    finishReason?: string
  ): number {
    let confidence = baseConfidence;

    // 1. Provider base multiplier
    confidence *= this.calibration.baseMultiplier;

    // 2. Temperature penalty
    const tempPenalty = this.calibration.temperaturePenalty(temperature);
    confidence -= tempPenalty;

    // 3. Finish reason adjustment
    if (finishReason) {
      const boost = this.calibration.finishReasonBoost[finishReason] ?? 0;
      confidence += boost;
    }

    // 4. Clamp to provider-specific bounds
    confidence = Math.max(
      this.calibration.minConfidence,
      Math.min(this.calibration.maxConfidence, confidence)
    );

    return confidence;
  }

  /**
   * Estimate query difficulty (simplified version)
   *
   * Full implementation would use complexity detector
   */
  private estimateQueryDifficulty(query: string): number {
    // Simplified heuristic-based estimation
    const queryLower = query.toLowerCase();
    let difficulty = 0.5; // Base

    // Question word presence
    const questionWords = ['what', 'how', 'why', 'when', 'where', 'who', 'which'];
    if (questionWords.some((w) => queryLower.includes(w))) {
      difficulty -= 0.1;
    }

    // Length-based
    const wordCount = query.split(/\s+/).length;
    if (wordCount < 5) {
      difficulty -= 0.1;
    } else if (wordCount > 20) {
      difficulty += 0.2;
    }

    // Technical terms
    if (/\b(algorithm|implement|design|architecture|optimization)\b/i.test(query)) {
      difficulty += 0.2;
    }

    return Math.max(0, Math.min(1, difficulty));
  }

  /**
   * Generate human-readable explanation
   */
  explainConfidence(analysis: ConfidenceAnalysis): string {
    const lines: string[] = [
      `Confidence: ${analysis.finalConfidence.toFixed(2)}`,
      `Method: ${analysis.methodUsed}`,
      '',
    ];

    if (analysis.queryDifficulty !== undefined) {
      const category =
        analysis.queryDifficulty < 0.3
          ? 'trivial'
          : analysis.queryDifficulty < 0.5
            ? 'simple'
            : analysis.queryDifficulty < 0.7
              ? 'moderate'
              : 'complex';
      lines.push(`  Query difficulty: ${analysis.queryDifficulty.toFixed(2)} (${category})`);
    }

    if (analysis.logprobsConfidence !== undefined) {
      lines.push(
        `  Logprobs-based: ${analysis.logprobsConfidence.toFixed(2)} (token probability analysis)`
      );
    }

    lines.push(
      `  Semantic quality: ${analysis.semanticConfidence.toFixed(2)} (hedging, consistency, completeness)`
    );

    if (analysis.alignmentScore !== undefined) {
      lines.push(
        `  Query-response alignment: ${analysis.alignmentScore.toFixed(2)} (keyword coverage, length, directness)`
      );

      if (analysis.alignmentFloorApplied) {
        const severity = analysis.components.alignmentFloorSeverity ?? 'unknown';
        const reduction = analysis.components.alignmentFloorReduction ?? 0;
        lines.push(`  ⚠️  SAFETY: Alignment floor applied (${severity} off-topic)`);
        lines.push(`      Confidence capped by ${reduction.toFixed(3)} to prevent garbage acceptance`);
      }
    }

    lines.push(
      `  After calibration: ${analysis.calibratedConfidence.toFixed(2)} (provider-specific adjustments)`
    );

    // Interpretation
    let interpretation: string;
    if (analysis.finalConfidence >= 0.9) {
      interpretation = 'Very high - strong confidence in response';
    } else if (analysis.finalConfidence >= 0.75) {
      interpretation = 'High - good confidence';
    } else if (analysis.finalConfidence >= 0.6) {
      interpretation = 'Moderate - acceptable quality';
    } else if (analysis.finalConfidence >= 0.4) {
      interpretation = 'Low - uncertain response';
    } else {
      interpretation = 'Very low - likely poor quality';
    }

    lines.push(`\n  → ${interpretation}`);

    return lines.join('\n');
  }
}
