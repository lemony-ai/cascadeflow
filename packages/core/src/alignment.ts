/**
 * Query-Response Alignment Scorer for cascadeflow - TypeScript Port
 *
 * Production-optimized alignment scoring for multi-signal confidence estimation.
 *
 * Features:
 * - Keyword extraction with smart filtering (numbers, abbreviations, standard words)
 * - Overlap calculation with synonym matching
 * - Production-calibrated baselines (0.20 standard, 0.25 trivial)
 * - Alignment floor (0.15) for off-topic detection
 * - Trivial query detection for edge cases
 * - Bidirectional keyword matching for short answers
 *
 * Based on Python alignment_scorer.py v7.11
 *
 * Key improvements from Python:
 * - Oct 6, 2025 (v1): Word length filter changed from > 3 to > 2 characters
 * - Oct 6, 2025 (v2): Baseline lowered from 0.30 to 0.20 (research-backed)
 * - Oct 6, 2025 (v3): Added trivial query detection for edge cases
 * - Oct 6, 2025 (v4): Dynamic baseline adjustment (0.20 standard, 0.25 trivial)
 * - Oct 7, 2025 (v7.11): Fixed off-topic penalty for short valid answers
 * - Oct 20, 2025 (v7.1): Performance fix - replaced regex with split() (30-50% faster)
 *
 * @example
 * ```typescript
 * const scorer = new QueryResponseAlignmentScorer();
 *
 * // Simple scoring
 * const score = scorer.score("What is 2+2?", "4");
 * console.log(score); // ~0.65+
 *
 * // Verbose scoring with analysis
 * const analysis = scorer.score("What is AI?", "Artificial Intelligence", 0.3, true);
 * console.log(analysis.alignmentScore);
 * console.log(analysis.reasoning);
 * ```
 */

/**
 * Detailed alignment analysis with production metrics
 */
export interface AlignmentAnalysis {
  /** Alignment score (0-1) */
  alignmentScore: number;

  /** Feature scores breakdown */
  features: {
    /** Baseline score used */
    baseline?: number;

    /** Keyword coverage score */
    keywordCoverage?: number;

    /** Important words coverage score */
    importantCoverage?: number;

    /** Length appropriateness score */
    lengthAppropriateness?: number;

    /** Directness score */
    directness?: number;

    /** Explanation depth score */
    explanationDepth?: number;

    /** Answer pattern score */
    answerPattern?: number;

    /** Whether query is trivial */
    isTrivial?: boolean;

    /** Whether trivial boost applied */
    trivialBoost?: boolean;

    /** Whether off-topic penalty applied */
    offTopicPenalty?: boolean;
  };

  /** Human-readable reasoning */
  reasoning: string;

  /** Whether query is trivial */
  isTrivial: boolean;

  /** Baseline used for scoring */
  baselineUsed: number;
}

/**
 * Synonym mappings for keyword matching
 */
interface SynonymMap {
  [key: string]: string[];
}

/**
 * Production-calibrated alignment scorer for multi-signal confidence estimation.
 *
 * v7.11: Fixed off-topic penalty bug for short valid answers
 * - Recognizes short responses with keywords as valid
 * - No longer marks "4" for "2+2" as off-topic
 * - Bidirectional keyword checking for trivial queries
 */
export class QueryResponseAlignmentScorer {
  // Production constants
  private readonly BASELINE_STANDARD = 0.20;
  private readonly BASELINE_TRIVIAL = 0.25;
  private readonly OFF_TOPIC_CAP = 0.15;

  // Stopwords to filter out
  private readonly stopwords: Set<string> = new Set([
    'the',
    'is',
    'a',
    'an',
    'and',
    'or',
    'but',
    'in',
    'on',
    'at',
    'to',
    'for',
    'of',
    'with',
    'by',
    'from',
    'as',
    'what',
    'how',
    'why',
    'when',
    'where',
    'who',
    'which',
    'do',
    'does',
    'did',
    'can',
    'could',
    'would',
    'should',
  ]);

  // Common abbreviations to keep
  private readonly abbreviations: Set<string> = new Set([
    'ai',
    'ml',
    'nlp',
    'llm',
    'gpt',
    'api',
    'sql',
    'nosql',
    'aws',
    'gcp',
    'azure',
    'cpu',
    'gpu',
    'ram',
    'ssd',
    'hdd',
    'html',
    'css',
    'js',
    'xml',
    'json',
    'yaml',
    'csv',
    'http',
    'https',
    'tcp',
    'udp',
    'ip',
    'dns',
    'ssh',
    'ftp',
    'url',
    'uri',
    'urn',
    'ui',
    'ux',
    'db',
    'ci',
    'cd',
    'ide',
    'sdk',
    'jdk',
    'npm',
    'pip',
    'git',
    'svn',
    'ios',
    'macos',
    'os',
    'vm',
    'vps',
    'cdn',
    'ssl',
    'tls',
    'orm',
    'mvc',
    'mvvm',
    'pdf',
    'rtf',
    'docx',
    'xlsx',
    'ner',
    'pos',
    'ocr',
    'cv',
    'dl',
    'rl',
    'gan',
  ]);

  // Synonym mappings for better keyword matching
  private readonly synonyms: SynonymMap = {
    python: ['py', 'programming language'],
    javascript: ['js', 'ecmascript', 'script'],
    compare: ['comparison', 'versus', 'vs', 'difference', 'differ'],
    api: ['interface', 'endpoint', 'application programming interface'],
    algorithm: ['algo', 'method', 'approach', 'procedure'],
    function: ['func', 'method', 'routine'],
    database: ['db', 'data store', 'storage'],
    implement: ['implementation', 'build', 'create', 'develop'],
  };

  /**
   * Extract keywords from text using production-optimized approach.
   *
   * v7.1 CRITICAL FIX: Reliable keyword extraction using .split().
   * Replaced failing regex with simple, fast, and reliable approach.
   *
   * Handles:
   * - Single digits: "4", "7", "9"
   * - Multi-digit: "42", "100", "3.14"
   * - Math expressions: "2+2", "5-3", "10*2"
   * - Abbreviations: "AI", "ML", "API", "SQL"
   * - Standard words: "sky", "code", "blue", "python"
   * - Punctuation: strips cleanly from edges
   *
   * @param text - Text to extract keywords from
   * @returns Set of extracted keywords
   */
  private extractKeywords(text: string): Set<string> {
    // Split on whitespace - simple, fast, reliable
    const words = text.toLowerCase().split(/\s+/);
    const keywords = new Set<string>();

    for (const w of words) {
      // Strip common punctuation from edges only (keeps internal like 2+2, A.I.)
      const wClean = w.replace(/^[.,!?;:"'()[\]{}]+|[.,!?;:"'()[\]{}]+$/g, '');

      // Skip empty or stopwords
      if (!wClean || this.stopwords.has(wClean)) {
        continue;
      }

      // RULE 1: Keep ANY token containing digits
      // Handles: 4, 42, 2+2, 3.14, v1.0, etc.
      if (/\d/.test(wClean)) {
        keywords.add(wClean);
        continue;
      }

      // RULE 2: Keep common abbreviations (2-3 chars)
      // Handles: AI, ML, API, SQL, CSS, etc.
      if (this.abbreviations.has(wClean)) {
        keywords.add(wClean);
        continue;
      }

      // RULE 3: Standard length filter for other words
      // Keeps words > 2 chars: sky, code, run, blue, etc.
      if (wClean.length > 2) {
        keywords.add(wClean);
      }
    }

    return keywords;
  }

  /**
   * Detect trivial queries needing special handling.
   *
   * @param query - Query text
   * @param response - Response text
   * @returns True if query is trivial
   */
  private isTrivialQuery(query: string, response: string): boolean {
    const responseLen = response.split(/\s+/).length;
    const queryLen = query.split(/\s+/).length;

    if (responseLen <= 3 && queryLen <= 10) {
      const trivialPatterns = [
        'what is',
        'who is',
        'when',
        'where',
        'how many',
        'how much',
        'which',
        'calculate',
        'compute',
        'equals',
        'sum',
        'add',
        'subtract',
        'multiply',
        'divide',
        'capital',
        'color',
        'colour',
      ];

      const queryLower = query.toLowerCase();
      return trivialPatterns.some((pattern) => queryLower.includes(pattern));
    }

    return false;
  }

  /**
   * Analyze keyword coverage with enhanced bidirectional matching.
   *
   * v7.11 QUICK FIX: Bidirectional keyword matching for short valid answers.
   * Fixes bug where "4" for "2+2" was marked as off-topic.
   *
   * @param queryLower - Lowercased query text
   * @param responseLower - Lowercased response text
   * @returns Tuple of [coverage score, has keywords]
   */
  private analyzeKeywordCoverageEnhanced(
    queryLower: string,
    responseLower: string
  ): [number, boolean] {
    const queryWords = this.extractKeywords(queryLower);
    const responseWords = this.extractKeywords(responseLower);

    if (queryWords.size === 0) {
      return [0.0, true];
    }

    let matches = 0;

    // Forward matching: query keywords in response
    for (const word of queryWords) {
      if (responseWords.has(word) || responseLower.includes(word)) {
        matches += 1;
      } else if (word in this.synonyms) {
        const synonymMatch = this.synonyms[word].some((syn) =>
          responseLower.includes(syn)
        );
        if (synonymMatch) {
          matches += 0.8;
        }
      }
    }

    // v7.11 FIX: Backward matching for short responses
    // If response is very short (1-3 words) and has valid keywords, it's acceptable
    const responseWordCount = responseLower.split(/\s+/).length;
    if (responseWordCount <= 3 && responseWords.size > 0) {
      // Short response with keywords = valid answer (like "4" for "2+2")
      matches = Math.max(matches, 0.5); // Give at least partial credit
    }

    const coverageRatio = queryWords.size > 0 ? matches / queryWords.size : 0;

    // v7.11 FIX: has_keywords should be True if we have ANY keywords
    // This prevents off-topic penalty for short valid answers
    const hasKeywords =
      matches > 0 || (responseWords.size > 0 && responseWordCount <= 3);

    // Coverage scoring
    if (coverageRatio >= 0.7) {
      return [0.3, true];
    } else if (coverageRatio >= 0.5) {
      return [0.2, true];
    } else if (coverageRatio >= 0.3) {
      return [0.1, true];
    } else if (coverageRatio >= 0.1) {
      return [0.0, hasKeywords];
    } else {
      // v7.11 FIX: Don't penalize if we have keywords
      if (hasKeywords) {
        return [0.0, true]; // Has keywords, just poor coverage
      } else {
        return [-0.1, false]; // Actually off-topic
      }
    }
  }

  /**
   * Analyze important words (capitalized, long, or with numbers).
   *
   * @param query - Query text
   * @param response - Response text
   * @returns Important words coverage score
   */
  private analyzeImportantWords(query: string, response: string): number {
    const important: string[] = [];
    const words = query.split(/\s+/);

    const excludeSet = new Set([
      'What',
      'How',
      'When',
      'Where',
      'Who',
      'Why',
      'Which',
      'Can',
      'Could',
      'Should',
      'Would',
    ]);

    for (const word of words) {
      if (
        word &&
        word[0] === word[0].toUpperCase() &&
        word[0] !== word[0].toLowerCase() &&
        !excludeSet.has(word)
      ) {
        important.push(word.toLowerCase());
      } else if (word.length > 8) {
        important.push(word.toLowerCase());
      } else if (/\d/.test(word)) {
        const cleanWord = word.replace(/[^\w+-]/g, '').toLowerCase();
        important.push(cleanWord);
      }
    }

    if (important.length === 0) {
      return 0.0;
    }

    const responseLower = response.toLowerCase();
    const covered = important.filter((w) => responseLower.includes(w)).length;
    const ratio = covered / important.length;

    if (ratio >= 0.7) {
      return 0.1;
    } else if (ratio >= 0.5) {
      return 0.07;
    } else if (ratio >= 0.3) {
      return 0.05;
    } else if (ratio > 0) {
      return 0.02;
    }

    return 0.0;
  }

  /**
   * Analyze length appropriateness based on query difficulty.
   *
   * @param queryDifficulty - Query difficulty (0-1)
   * @param responseLower - Lowercased response text
   * @param isTrivial - Whether query is trivial
   * @returns Length appropriateness score
   */
  private analyzeLengthAppropriatenessEnhanced(
    queryDifficulty: number,
    responseLower: string,
    isTrivial: boolean = false
  ): number {
    const responseLength = responseLower.length;

    if (isTrivial) {
      if (responseLength <= 10) return 0.2;
      if (responseLength <= 30) return 0.15;
      if (responseLength <= 50) return 0.1;
      return 0.05;
    }

    let expectedMin: number;
    let expectedMax: number;
    let optimalMin: number;
    let optimalMax: number;

    if (queryDifficulty < 0.3) {
      expectedMin = 5;
      expectedMax = 100;
      optimalMin = 10;
      optimalMax = 50;
    } else if (queryDifficulty < 0.5) {
      expectedMin = 20;
      expectedMax = 250;
      optimalMin = 40;
      optimalMax = 150;
    } else if (queryDifficulty < 0.7) {
      expectedMin = 50;
      expectedMax = 500;
      optimalMin = 100;
      optimalMax = 300;
    } else {
      expectedMin = 100;
      expectedMax = 800;
      optimalMin = 150;
      optimalMax = 500;
    }

    if (responseLength >= optimalMin && responseLength <= optimalMax) {
      return 0.2;
    }
    if (responseLength >= expectedMin && responseLength <= expectedMax) {
      return 0.1;
    }
    if (responseLength < expectedMin) {
      const ratio = responseLength / expectedMin;
      if (ratio < 0.3) return -0.15;
      if (ratio < 0.6) return -0.1;
      return -0.05;
    }
    if (responseLength > expectedMax * 1.5) {
      return -0.05;
    }

    return 0.05;
  }

  /**
   * Analyze directness of response.
   *
   * @param _queryLower - Lowercased query text (unused but kept for signature compatibility)
   * @param responseLower - Lowercased response text
   * @param queryDifficulty - Query difficulty (0-1)
   * @returns Directness score
   */
  private analyzeDirectness(
    _queryLower: string,
    responseLower: string,
    queryDifficulty: number
  ): number {
    if (queryDifficulty >= 0.5) {
      return 0.0;
    }

    const sentences = responseLower.split('.');
    if (sentences.length === 0) {
      return 0.0;
    }

    const firstSentence = sentences[0].trim();

    if (firstSentence.length < 40) return 0.15;
    if (firstSentence.length < 80) return 0.1;
    if (firstSentence.length < 150) return 0.05;

    return 0.0;
  }

  /**
   * Analyze explanation depth based on explanation markers.
   *
   * @param responseLower - Lowercased response text
   * @param queryDifficulty - Query difficulty (0-1)
   * @returns Explanation depth score
   */
  private analyzeExplanationDepthCalibrated(
    responseLower: string,
    queryDifficulty: number
  ): number {
    if (queryDifficulty < 0.6) {
      return 0.0;
    }

    const explanationMarkers = [
      'because',
      'therefore',
      'thus',
      'however',
      'although',
      'for example',
      'for instance',
      'specifically',
      'in other words',
      'that is',
      'namely',
      'moreover',
      'furthermore',
      'additionally',
      'consequently',
      'as a result',
      'this means',
      'in fact',
      'nevertheless',
      'nonetheless',
      'accordingly',
      'hence',
    ];

    const markerCount = explanationMarkers.filter((marker) =>
      responseLower.includes(marker)
    ).length;

    if (markerCount >= 4) return 0.2;
    if (markerCount >= 3) return 0.15;
    if (markerCount >= 2) return 0.1;
    if (markerCount >= 1) return 0.05;

    return 0.0;
  }

  /**
   * Detect if response matches question type pattern.
   *
   * @param query - Query text
   * @param response - Response text
   * @returns Answer pattern score
   */
  private detectAnswerPattern(query: string, response: string): number {
    let score = 0.0;

    if (query.startsWith('what is') || query.startsWith('what are')) {
      const patterns = ['is', 'are', 'refers to', 'means', 'defined as'];
      if (patterns.some((p) => response.includes(p))) {
        score += 0.08;
      }
    } else if (query.startsWith('how') || query.includes('how to')) {
      const patterns = ['first', 'then', 'steps', 'process', 'can', 'by', 'using'];
      if (patterns.some((p) => response.includes(p))) {
        score += 0.08;
      }
    } else if (query.startsWith('why')) {
      const patterns = ['because', 'due to', 'reason', 'since', 'as', 'causes'];
      if (patterns.some((p) => response.includes(p))) {
        score += 0.08;
      }
    } else if (query.startsWith('when')) {
      const patterns = ['in', 'during', 'year', 'time', 'date'];
      if (patterns.some((p) => response.includes(p))) {
        score += 0.08;
      }
    } else if (query.includes('compare') || query.includes('difference')) {
      const patterns = ['while', 'whereas', 'but', 'however', 'unlike', 'different'];
      if (patterns.some((p) => response.includes(p))) {
        score += 0.08;
      }
    }

    // Penalize uncertainty
    const uncertainPhrases = ["i don't know", "i'm not sure", 'unclear', 'uncertain'];
    if (uncertainPhrases.some((p) => response.includes(p))) {
      score -= 0.05;
    }

    return Math.max(0.0, score);
  }

  /**
   * Generate human-readable reasoning from features.
   *
   * @param features - Feature scores
   * @param finalScore - Final alignment score
   * @returns Human-readable reasoning
   */
  private generateReasoning(
    features: AlignmentAnalysis['features'],
    finalScore: number
  ): string {
    const reasons: string[] = [];

    if (features.isTrivial) {
      reasons.push('trivial query');
    }

    if (features.trivialBoost) {
      reasons.push('factual answer boost (+15%)');
    }

    if (features.offTopicPenalty) {
      reasons.push('OFF-TOPIC (capped)');
    }

    const coverage = features.keywordCoverage || 0;
    if (coverage > 0.2) {
      reasons.push('excellent coverage');
    } else if (coverage > 0.1) {
      reasons.push('good coverage');
    } else if (coverage < 0) {
      reasons.push('poor coverage');
    }

    const important = features.importantCoverage || 0;
    if (important > 0.07) {
      reasons.push('key terms present');
    }

    const length = features.lengthAppropriateness || 0;
    if (length > 0.15) {
      reasons.push('optimal length');
    } else if (length > 0.05) {
      reasons.push('appropriate length');
    } else if (length < -0.05) {
      reasons.push('length mismatch');
    }

    if ((features.directness || 0) > 0.1) {
      reasons.push('direct answer');
    }

    if ((features.explanationDepth || 0) > 0.1) {
      reasons.push('good depth');
    }

    if ((features.answerPattern || 0) > 0.05) {
      reasons.push('matches question type');
    }

    if (reasons.length === 0) {
      reasons.push('standard alignment');
    }

    const baseline = features.baseline || 0.2;
    return `Score ${finalScore.toFixed(3)} (baseline=${baseline.toFixed(2)}): ${reasons.join(', ')}`;
  }

  /**
   * Calculate alignment score with production-optimized calibration.
   *
   * @param query - Query text
   * @param response - Response text
   * @param queryDifficulty - Query difficulty (0-1, default: 0.5)
   * @param verbose - Return detailed analysis (default: false)
   * @returns Alignment score (0-1) or AlignmentAnalysis if verbose
   */
  score(query: string, response: string): number;
  score(
    query: string,
    response: string,
    queryDifficulty: number
  ): number;
  score(
    query: string,
    response: string,
    queryDifficulty: number,
    verbose: true
  ): AlignmentAnalysis;
  score(
    query: string,
    response: string,
    queryDifficulty: number,
    verbose: false
  ): number;
  score(
    query: string,
    response: string,
    queryDifficulty: number = 0.5,
    verbose: boolean = false
  ): number | AlignmentAnalysis {
    // Handle empty inputs
    if (!query || !response) {
      const result: AlignmentAnalysis = {
        alignmentScore: 0.0,
        features: {},
        reasoning: 'Empty query or response',
        isTrivial: false,
        baselineUsed: 0.0,
      };
      return verbose ? result : 0.0;
    }

    const features: AlignmentAnalysis['features'] = {};
    const queryLower = query.toLowerCase().trim();
    const responseLower = response.toLowerCase().trim();

    // Check if trivial
    const isTrivial = this.isTrivialQuery(query, response);
    features.isTrivial = isTrivial;

    // Set baseline
    let score: number;
    let baselineUsed: number;

    if (isTrivial) {
      score = this.BASELINE_TRIVIAL;
      baselineUsed = this.BASELINE_TRIVIAL;
    } else {
      score = this.BASELINE_STANDARD;
      baselineUsed = this.BASELINE_STANDARD;
    }

    features.baseline = baselineUsed;

    // Keyword coverage
    const [coverageScore, hasKeywords] = this.analyzeKeywordCoverageEnhanced(
      queryLower,
      responseLower
    );
    features.keywordCoverage = coverageScore;
    score += coverageScore;

    // Important words
    const importanceScore = this.analyzeImportantWords(query, response);
    features.importantCoverage = importanceScore;
    score += importanceScore;

    // Length appropriateness
    const lengthScore = this.analyzeLengthAppropriatenessEnhanced(
      queryDifficulty,
      responseLower,
      isTrivial
    );
    features.lengthAppropriateness = lengthScore;
    score += lengthScore;

    // Directness
    const directnessScore = this.analyzeDirectness(
      queryLower,
      responseLower,
      queryDifficulty
    );
    features.directness = directnessScore;
    score += directnessScore;

    // Explanation depth
    const depthScore = this.analyzeExplanationDepthCalibrated(
      responseLower,
      queryDifficulty
    );
    features.explanationDepth = depthScore;
    score += depthScore;

    // Answer pattern
    const patternScore = this.detectAnswerPattern(queryLower, responseLower);
    features.answerPattern = patternScore;
    score += patternScore;

    // v7.11 FIX: Only apply off-topic penalty if truly off-topic
    // Don't penalize short valid answers that have keywords
    if (!hasKeywords && queryLower.split(/\s+/).length > 2) {
      score = Math.min(score * 0.6, this.OFF_TOPIC_CAP);
      features.offTopicPenalty = true;
    }

    // Trivial boost
    if (isTrivial && hasKeywords && coverageScore > 0) {
      score *= 1.15;
      features.trivialBoost = true;
    }

    // Clamp to [0, 1]
    const finalScore = Math.max(0.0, Math.min(1.0, score));

    if (verbose) {
      return {
        alignmentScore: finalScore,
        features,
        reasoning: this.generateReasoning(features, finalScore),
        isTrivial,
        baselineUsed,
      };
    }

    return finalScore;
  }
}
