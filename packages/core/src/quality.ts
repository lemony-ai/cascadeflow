/**
 * Quality validation and confidence scoring for cascadeflow
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

// ============================================================================
// SEMANTIC QUALITY VALIDATION (ML-BASED)
// ============================================================================

/**
 * Result of semantic quality check
 */
export interface SemanticQualityResult {
  /** Semantic similarity score (0-1) */
  similarity: number;
  /** Whether content is toxic */
  isToxic: boolean;
  /** Toxicity score (0-1, higher = more toxic) */
  toxicityScore: number;
  /** Whether quality check passed */
  passed: boolean;
  /** Optional failure reason */
  reason?: string;
  /** Additional check metadata */
  metadata: Record<string, any>;
}

/**
 * Optional ML-based quality validation using embeddings.
 *
 * Uses @cascadeflow/ml for fast, lightweight semantic similarity checking.
 * Completely optional - gracefully degrades if dependencies not installed.
 */
export class SemanticQualityChecker {
  private embedder: any = null;
  private cache: any = null;
  private available: boolean = false;
  private modelName: string;
  private similarityThreshold: number;
  private toxicityThreshold: number;
  private useCache: boolean;
  private initPromise: Promise<void>;

  /**
   * Initialize semantic quality checker.
   *
   * @param options - Configuration options
   */
  constructor(options: {
    modelName?: string;
    similarityThreshold?: number;
    toxicityThreshold?: number;
    embedder?: any;
    useCache?: boolean;
  } = {}) {
    this.modelName = options.modelName || 'Xenova/bge-small-en-v1.5';
    this.similarityThreshold = options.similarityThreshold ?? 0.5;
    this.toxicityThreshold = options.toxicityThreshold ?? 0.7;
    this.useCache = options.useCache ?? true;

    // Initialize ML (async)
    this.initPromise = this.initializeML(options.embedder);
  }

  /**
   * Initialize ML components (lazy and optional)
   */
  private async initializeML(providedEmbedder?: any): Promise<void> {
    try {
      // Use provided embedder or try to import from @cascadeflow/ml
      if (providedEmbedder) {
        this.embedder = providedEmbedder;
      } else {
        try {
          // @ts-ignore - Dynamic import of optional dependency
          const ml = await import('@cascadeflow/ml');
          this.embedder = new ml.UnifiedEmbeddingService(this.modelName);

          // Create cache if requested
          if (this.useCache && (await this.embedder.isAvailable())) {
            this.cache = new ml.EmbeddingCache(this.embedder);
          }
        } catch (error: any) {
          // ML package not available - graceful degradation
          this.available = false;
          return;
        }
      }

      // Check if embedder is available
      if (this.embedder) {
        this.available = await this.embedder.isAvailable();
      }
    } catch (error: any) {
      this.available = false;
    }
  }

  /**
   * Check if semantic quality checking is available
   */
  async isAvailable(): Promise<boolean> {
    await this.initPromise;
    return this.available;
  }

  /**
   * Check semantic similarity between query and response.
   *
   * Uses cosine similarity of embeddings to measure how well the
   * response aligns with the query semantically.
   *
   * @param query - Original query text
   * @param response - Generated response text
   * @returns Similarity score (0-1, higher = more similar)
   */
  async checkSimilarity(
    query: string,
    response: string
  ): Promise<number> {
    if (!(await this.isAvailable())) {
      throw new Error(
        'Semantic checking not available. Install @cascadeflow/ml'
      );
    }

    // Use cache if available for better performance
    let similarity: number | null;
    if (this.cache) {
      similarity = await this.cache.similarity(query, response);
    } else {
      // Fallback to direct embedder
      similarity = await this.embedder.similarity(query, response);
    }

    return similarity ?? 0.0;
  }

  /**
   * Check if text contains toxic content.
   *
   * Uses keyword-based heuristics. For production, consider using a
   * dedicated toxicity API like Perspective API or OpenAI Moderation.
   *
   * @param text - Text to check
   * @param threshold - Optional custom threshold
   * @returns Tuple of [isToxic, toxicityScore]
   */
  async checkToxicity(
    text: string,
    threshold?: number
  ): Promise<[boolean, number]> {
    if (!(await this.isAvailable())) {
      throw new Error('Semantic checking not available');
    }

    // Simple keyword-based toxicity check
    // For production, use Perspective API or OpenAI Moderation
    const toxicKeywords = [
      'hate',
      'kill',
      'violent',
      'racist',
      'sexist',
      // Add more as needed
    ];

    const textLower = text.toLowerCase();
    const toxicCount = toxicKeywords.reduce(
      (count, keyword) => (textLower.includes(keyword) ? count + 1 : count),
      0
    );

    const toxicityScore = Math.min(1.0, toxicCount * 0.3); // Scale to 0-1
    const isToxic = toxicityScore > (threshold ?? this.toxicityThreshold);

    return [isToxic, toxicityScore];
  }

  /**
   * Run full semantic quality validation.
   *
   * Combines similarity and toxicity checks into single validation.
   *
   * @param query - Original query text
   * @param response - Generated response text
   * @param checkToxicityFlag - Whether to check for toxic content
   * @returns SemanticQualityResult with all check results
   */
  async validate(
    query: string,
    response: string,
    checkToxicityFlag: boolean = true
  ): Promise<SemanticQualityResult> {
    if (!(await this.isAvailable())) {
      return {
        similarity: 0.0,
        isToxic: false,
        toxicityScore: 0.0,
        passed: false,
        reason: 'semantic_checking_unavailable',
        metadata: { available: false },
      };
    }

    // Check similarity
    const similarity = await this.checkSimilarity(query, response);

    // Check toxicity
    let isToxic = false;
    let toxicityScore = 0.0;
    if (checkToxicityFlag) {
      [isToxic, toxicityScore] = await this.checkToxicity(response);
    }

    // Determine if passed
    const passed = similarity >= this.similarityThreshold && !isToxic;

    let reason: string | undefined;
    if (!passed) {
      if (similarity < this.similarityThreshold) {
        reason = `low_similarity (${similarity.toFixed(2)} < ${this.similarityThreshold})`;
      } else if (isToxic) {
        reason = `toxic_content (score: ${toxicityScore.toFixed(2)})`;
      }
    }

    return {
      similarity,
      isToxic,
      toxicityScore,
      passed,
      reason,
      metadata: {
        model: this.modelName,
        similarityThreshold: this.similarityThreshold,
        toxicityThreshold: this.toxicityThreshold,
      },
    };
  }
}

/**
 * Convenience function for one-off semantic quality checks.
 *
 * Creates a checker instance and runs validation. Returns null if
 * semantic checking is not available.
 *
 * @param query - Original query text
 * @param response - Generated response text
 * @param options - Configuration options
 * @returns SemanticQualityResult or null if unavailable
 */
export async function checkSemanticQuality(
  query: string,
  response: string,
  options: {
    similarityThreshold?: number;
    checkToxicity?: boolean;
  } = {}
): Promise<SemanticQualityResult | null> {
  const checker = new SemanticQualityChecker({
    similarityThreshold: options.similarityThreshold,
  });

  if (!(await checker.isAvailable())) {
    return null;
  }

  return checker.validate(query, response, options.checkToxicity ?? true);
}
