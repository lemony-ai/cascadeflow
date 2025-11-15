/**
 * Response Analyzer for Quality Assessment
 *
 * Analyzes response characteristics for quality assessment:
 * - Length appropriateness
 * - Hedging detection (uncertainty markers)
 * - Specificity analysis (vague vs concrete)
 * - Hallucination detection (suspicious patterns)
 *
 * @module response-analyzer
 */

import type { QueryComplexity } from './types';

/**
 * Length analysis result
 */
export interface LengthAnalysis {
  /** Word count */
  wordCount: number;

  /** Character count */
  charCount: number;

  /** Whether length is appropriate */
  appropriate: boolean;

  /** Whether response is too short */
  tooShort: boolean;

  /** Whether response is too long */
  tooLong: boolean;

  /** Expected word count range (min, max) */
  expectedRange: [number, number];
}

/**
 * Hedging detection result
 */
export interface HedgingAnalysis {
  /** Ratio of hedging phrases per sentence */
  ratio: number;

  /** Count of hedging phrases */
  count: number;

  /** Whether severe uncertainty markers present */
  severe: boolean;

  /** Whether hedging is acceptable */
  acceptable: boolean;
}

/**
 * Specificity analysis result
 */
export interface SpecificityAnalysis {
  /** Overall specificity score (0-1) */
  score: number;

  /** Whether response contains numbers */
  hasNumbers: boolean;

  /** Whether response contains examples */
  hasExamples: boolean;

  /** Ratio of vague words */
  vaguenessRatio: number;

  /** Whether meets minimum requirement for complexity */
  meetsRequirement: boolean;

  /** Minimum required score */
  minRequired: number;
}

/**
 * Hallucination detection result
 */
export interface HallucinationAnalysis {
  /** Number of suspicious patterns found */
  suspiciousPatterns: number;

  /** Whether contradictions detected */
  hasContradiction: boolean;

  /** Risk level: low, medium, high */
  riskLevel: 'low' | 'medium' | 'high';
}

/**
 * Response Analyzer
 *
 * Analyzes response characteristics including hedging, specificity,
 * length appropriateness, and hallucination indicators.
 *
 * @example
 * ```typescript
 * const analyzer = new ResponseAnalyzer();
 *
 * const hedging = analyzer.detectHedging(response);
 * console.log(`Hedging ratio: ${hedging.ratio}`);
 *
 * const hallucinations = analyzer.detectHallucinations(response);
 * console.log(`Risk: ${hallucinations.riskLevel}`);
 * ```
 */
export class ResponseAnalyzer {
  /**
   * Hedging phrases that indicate uncertainty
   */
  static readonly HEDGING_PHRASES = [
    'might',
    'may',
    'could',
    'possibly',
    'perhaps',
    'maybe',
    'likely',
    'probably',
    'generally',
    'usually',
    'typically',
    'often',
    'sometimes',
    'can be',
    'tends to',
    'seems to',
    'appears to',
    'suggests',
    'indicates',
    'implies',
    'i think',
    'i believe',
    'in my opinion',
    'arguably',
    'somewhat',
    'rather',
    'relatively',
    'fairly',
    'quite',
    'to some extent',
    'in some cases',
    'it depends',
  ] as const;

  /**
   * Strong uncertainty markers (worse than hedging)
   */
  static readonly UNCERTAINTY_MARKERS = [
    "i don't know",
    "i'm not sure",
    'i cannot',
    "i can't",
    'unclear',
    'uncertain',
    'not confident',
    'no information',
    "don't have",
    'unable to',
    'cannot provide',
    'insufficient',
    'i apologize',
    "i'm sorry",
    'unfortunately',
    'not able to',
    'beyond my knowledge',
    'outside my expertise',
  ] as const;

  /**
   * Hallucination indicator patterns
   */
  static readonly HALLUCINATION_PATTERNS = [
    /according to (studies|research|experts) (show|suggest|indicate)/i,
    /it is (well-known|widely accepted|commonly understood) that/i,
    /\b(always|never|all|none|every|no)\b.*\b(always|never|all|none|every|no)\b/i,
    /(exactly|precisely) \d+\.?\d*%/i,
    /(scientists|researchers|experts) (agree|confirm|prove)/i,
  ] as const;

  /**
   * Analyze if length is appropriate for complexity
   *
   * @param content - Response content
   * @param complexity - Query complexity level
   * @returns Length analysis
   */
  analyzeLength(content: string, complexity: QueryComplexity): LengthAnalysis {
    const words = content.split(/\s+/).filter((w) => w.length > 0);
    const wordCount = words.length;
    const charCount = content.length;

    // Expected ranges by complexity
    const expectedRanges: Record<QueryComplexity, [number, number]> = {
      trivial: [1, 50], // "4" to brief sentence
      simple: [5, 150], // Few sentences
      moderate: [15, 300], // Paragraph or two
      hard: [30, 600], // Multiple paragraphs
      expert: [50, 1000], // Comprehensive
    };

    const [minExpected, maxExpected] = expectedRanges[complexity] ?? [10, 100];

    const appropriate = wordCount >= minExpected && wordCount <= maxExpected * 3;
    const tooShort = wordCount < minExpected * 0.5;
    const tooLong = wordCount > maxExpected * 4;

    return {
      wordCount,
      charCount,
      appropriate,
      tooShort,
      tooLong,
      expectedRange: [minExpected, maxExpected],
    };
  }

  /**
   * Detect hedging language that indicates uncertainty
   *
   * @param content - Response content
   * @returns Hedging analysis
   */
  detectHedging(content: string): HedgingAnalysis {
    const contentLower = content.toLowerCase();
    const sentences = content
      .split(/[.!?]+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 0);

    if (sentences.length === 0) {
      return {
        ratio: 0.0,
        count: 0,
        severe: false,
        acceptable: true,
      };
    }

    // Count hedging phrases
    const hedgingCount = ResponseAnalyzer.HEDGING_PHRASES.reduce((count, phrase) => {
      return count + (contentLower.includes(phrase) ? 1 : 0);
    }, 0);

    // Check for severe uncertainty markers
    const hasSevere = ResponseAnalyzer.UNCERTAINTY_MARKERS.some((marker) =>
      contentLower.includes(marker)
    );

    const hedgingRatio = hedgingCount / sentences.length;
    const acceptable = hedgingRatio <= 0.3 && !hasSevere;

    return {
      ratio: hedgingRatio,
      count: hedgingCount,
      severe: hasSevere,
      acceptable,
    };
  }

  /**
   * Analyze how specific vs vague the response is
   *
   * @param content - Response content
   * @param complexity - Query complexity level
   * @returns Specificity analysis
   */
  analyzeSpecificity(content: string, complexity: QueryComplexity): SpecificityAnalysis {
    const contentLower = content.toLowerCase();
    const words = content.split(/\s+/).filter((w) => w.length > 0);

    // Check for specificity indicators
    const hasNumbers = /\d+/.test(content);
    const hasExamples = ['example', 'for instance', 'such as', 'e.g.'].some((word) =>
      contentLower.includes(word)
    );
    const hasQuotes = content.includes('"') || content.includes("'");
    const hasReferences = ['according to', 'research', 'study', 'source'].some((word) =>
      contentLower.includes(word)
    );
    // Technical terms (CamelCase)
    const hasTechnicalTerms = /\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b/.test(content);

    // Check for vague phrases
    const vaguePhrases = [
      'thing',
      'stuff',
      'something',
      'various',
      'many',
      'some',
      'several',
      'often',
      'usually',
    ];

    const vaguenessCount = vaguePhrases.reduce((count, phrase) => {
      return count + (contentLower.includes(phrase) ? 1 : 0);
    }, 0);

    const vaguenessRatio = words.length > 0 ? vaguenessCount / words.length : 0;

    // Calculate specificity score
    const specificityScore =
      (hasNumbers ? 0.2 : 0) +
      (hasExamples ? 0.2 : 0) +
      (hasQuotes ? 0.15 : 0) +
      (hasReferences ? 0.15 : 0) +
      (hasTechnicalTerms ? 0.15 : 0) +
      Math.max(0, 0.15 - vaguenessRatio);

    // Minimum required by complexity
    const minRequiredMap: Record<QueryComplexity, number> = {
      trivial: 0.0, // No specificity needed
      simple: 0.2,
      moderate: 0.3,
      hard: 0.4,
      expert: 0.5,
    };

    const minRequired = minRequiredMap[complexity] ?? 0.3;
    const meetsRequirement = specificityScore >= minRequired;

    return {
      score: specificityScore,
      hasNumbers,
      hasExamples,
      vaguenessRatio,
      meetsRequirement,
      minRequired,
    };
  }

  /**
   * Detect potential hallucination patterns
   *
   * @param content - Response content
   * @returns Hallucination analysis
   */
  detectHallucinations(content: string): HallucinationAnalysis {
    // Check for suspicious patterns
    let suspiciousPatterns = 0;

    for (const pattern of ResponseAnalyzer.HALLUCINATION_PATTERNS) {
      if (pattern.test(content)) {
        suspiciousPatterns++;
      }
    }

    // Check for contradictions
    const hasContradiction =
      /(however|but|although|though|yet).*\b(not|no|never)\b/i.test(content);

    // Determine risk level
    let riskLevel: 'low' | 'medium' | 'high';
    if (suspiciousPatterns >= 2) {
      riskLevel = 'high';
    } else if (suspiciousPatterns === 1) {
      riskLevel = 'medium';
    } else {
      riskLevel = 'low';
    }

    return {
      suspiciousPatterns,
      hasContradiction,
      riskLevel,
    };
  }

  /**
   * Comprehensive analysis of response
   *
   * @param content - Response content
   * @param complexity - Query complexity level
   * @returns All analysis results
   */
  analyze(
    content: string,
    complexity: QueryComplexity = 'moderate'
  ): {
    length: LengthAnalysis;
    hedging: HedgingAnalysis;
    specificity: SpecificityAnalysis;
    hallucinations: HallucinationAnalysis;
  } {
    return {
      length: this.analyzeLength(content, complexity),
      hedging: this.detectHedging(content),
      specificity: this.analyzeSpecificity(content, complexity),
      hallucinations: this.detectHallucinations(content),
    };
  }
}
