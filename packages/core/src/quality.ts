/**
 * Quality validation and confidence scoring for CascadeFlow
 *
 * Based on Python quality validation with TypeScript patterns
 */

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
  };
}

/**
 * Quality configuration
 */
export interface QualityConfig {
  /** Minimum confidence threshold (0-1) */
  minConfidence: number;

  /** Minimum word count */
  minWordCount: number;

  /** Enable logprobs-based scoring */
  useLogprobs: boolean;

  /** Fallback to heuristic if logprobs unavailable */
  fallbackToHeuristic: boolean;

  /** Strict mode (fail on any warning signs) */
  strictMode: boolean;
}

/**
 * Default quality configuration
 */
export const DEFAULT_QUALITY_CONFIG: QualityConfig = {
  minConfidence: 0.7,
  minWordCount: 10,
  useLogprobs: true,
  fallbackToHeuristic: true,
  strictMode: false,
};

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

  constructor(config: Partial<QualityConfig> = {}) {
    this.config = { ...DEFAULT_QUALITY_CONFIG, ...config };
  }

  /**
   * Validate response quality
   *
   * @param content - Generated content
   * @param query - Original query
   * @param logprobs - Log probabilities (if available)
   * @returns Quality validation result
   */
  validate(
    content: string,
    query: string,
    logprobs?: number[]
  ): QualityResult {
    // Step 1: Calculate confidence
    let confidence: number;
    let method: 'logprobs' | 'heuristic' | 'hybrid';
    let avgLogprob: number | undefined;
    let minLogprob: number | undefined;

    if (this.config.useLogprobs && logprobs && logprobs.length > 0) {
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

    // Step 4: Calculate overall quality score
    let score = confidence;

    // Penalize for short content
    if (!lengthOk) {
      score *= 0.8;
    }

    // Penalize for uncertainty markers (in strict mode)
    if (this.config.strictMode && uncertaintyMarkers.length > 0) {
      score *= Math.max(0.5, 1 - uncertaintyMarkers.length * 0.1);
    }

    // Step 5: Determine pass/fail
    const passed = score >= this.config.minConfidence && lengthOk;

    // Step 6: Generate reason
    let reason: string;
    if (passed) {
      reason = `Quality check passed (score: ${score.toFixed(2)}, confidence: ${confidence.toFixed(2)})`;
    } else if (!lengthOk) {
      reason = `Content too short (${wordCount} words, minimum: ${this.config.minWordCount})`;
    } else {
      reason = `Confidence too low (${confidence.toFixed(2)}, minimum: ${this.config.minConfidence})`;
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
      },
    };
  }

  /**
   * Update configuration
   */
  updateConfig(config: Partial<QualityConfig>): void {
    this.config = { ...this.config, ...config };
  }

  /**
   * Get current configuration
   */
  getConfig(): QualityConfig {
    return { ...this.config };
  }
}
