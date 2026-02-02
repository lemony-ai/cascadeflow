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
 * - MCQ (multiple-choice question) format detection (v10)
 * - Intent classification format detection (v11)
 * - Long context QA format detection (v12)
 * - Function call/tool use format detection (v13)
 * - Long context single-word answer handling (v14)
 *
 * Based on Python alignment_scorer.py v14
 *
 * Key improvements from Python:
 * - Oct 6, 2025 (v1): Word length filter changed from > 3 to > 2 characters
 * - Oct 6, 2025 (v2): Baseline lowered from 0.30 to 0.20 (research-backed)
 * - Oct 6, 2025 (v3): Added trivial query detection for edge cases
 * - Oct 6, 2025 (v4): Dynamic baseline adjustment (0.20 standard, 0.25 trivial)
 * - Oct 7, 2025 (v7.11): Fixed off-topic penalty for short valid answers
 * - Oct 20, 2025 (v7.1): Performance fix - replaced regex with split() (30-50% faster)
 * - Nov 29, 2025 (v9): Added reasoning chain detection for CoT responses
 *   * Detects step-by-step reasoning patterns (math operations, step indicators)
 *   * Gives +0.15 to +0.25 boost for responses with clear reasoning
 *   * Fixes alignment floor triggering on valid CoT responses
 *   * Domain-agnostic - works for math, code, analysis, any multi-step reasoning
 * - Dec 3, 2025 (v10): Added MCQ (multiple-choice question) format detection
 *   * Detects MCQ prompts: "Answer the following multiple-choice question"
 *   * Recognizes valid MCQ responses: single letters A-D, "The answer is B", etc.
 *   * Gives 0.75 alignment score for valid MCQ responses to MCQ prompts
 *   * Fixes alignment floor triggering on MMLU benchmark (was 0.06→0.75)
 * - Dec 7, 2025 (v11): Added intent classification format detection
 *   * Detects intent/category classification prompts with label lists
 *   * Recognizes structured intent responses (Intent:, Category:, Label:)
 *   * Gives 0.72 alignment score for valid classification responses
 * - Jan 7, 2026 (v12): Added long context QA format detection
 *   * Detects long prompts (>300 words) with QA markers or code context
 *   * Gives 0.72 alignment score for valid long context answers
 * - Jan 12, 2026 (v13): Added function call/tool use format detection
 *   * Detects tool schemas, function listings, and call instructions
 *   * Recognizes JSON or structured tool response formats
 *   * Gives 0.72 alignment score for valid function call responses
 * - Jan 12, 2026 (v14): Accepts single-word long context answers (YES/NO/QUORUM)
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

    /** Reasoning chain detection score (v9) */
    reasoningChain?: number;

    /** Whether query is MCQ format (v10) */
    isMcq?: boolean;

    /** Whether response is valid MCQ answer (v10) */
    validMcqResponse?: boolean;

    /** Whether MCQ boost was applied (v10) */
    mcqBoost?: boolean;

    /** Whether query is intent classification format (v11) */
    isClassification?: boolean;

    /** Whether response is valid classification answer (v11) */
    validClassificationResponse?: boolean;

    /** Whether classification boost was applied (v11) */
    classificationBoost?: boolean;

    /** Whether query is long context QA format (v12) */
    isLongContextQa?: boolean;

    /** Whether response is valid long context answer (v12) */
    validLongContextResponse?: boolean;

    /** Whether long context boost was applied (v12) */
    longContextQaBoost?: boolean;

    /** Whether query is function call format (v13) */
    isFunctionCall?: boolean;

    /** Whether response is valid function call answer (v13) */
    validFunctionCallResponse?: boolean;

    /** Whether function call boost was applied (v13) */
    functionCallBoost?: boolean;

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
   * Detect if query is a multiple-choice question (MCQ) format.
   *
   * v10 (Dec 2025): Fixes alignment floor triggering on MMLU benchmark.
   *
   * MCQ prompts typically have:
   * - Explicit MCQ instruction: "Answer the following multiple-choice question"
   * - Choice markers: "A)", "B)", "C)", "D)" or "A.", "B.", "C.", "D."
   * - Answer prompt: "Answer:" at the end
   *
   * @param query - Query text
   * @returns True if query is MCQ format
   */
  private isMcqFormat(query: string): boolean {
    const queryLower = query.toLowerCase();

    // Check for explicit MCQ instructions
    const mcqInstructions = [
      'multiple-choice question',
      'multiple choice question',
      'answer the following question',
      'select the correct answer',
      'choose the correct answer',
      'which of the following',
      'pick the best answer',
    ];
    const hasMcqInstruction = mcqInstructions.some((instr) =>
      queryLower.includes(instr)
    );

    // Check for choice markers (A), B), etc. or A., B., etc.)
    const choicePattern = /\b[A-D][.)]\s/gi;
    const choices = query.match(choicePattern) || [];
    const hasChoices = choices.length >= 2;

    // Check for answer prompt at end
    const trimmedQuery = queryLower.trim();
    const hasAnswerPrompt =
      trimmedQuery.endsWith('answer:') || trimmedQuery.endsWith('answer');

    // MCQ if has instruction + choices, or has choices + answer prompt
    return (hasMcqInstruction && hasChoices) || (hasChoices && hasAnswerPrompt);
  }

  /**
   * Check if response is a valid MCQ answer (A, B, C, or D).
   *
   * v10 (Dec 2025): Recognizes various MCQ response formats.
   *
   * Valid formats:
   * - Single letter: "A", "B", "C", "D"
   * - With explanation: "The answer is B", "B. Because..."
   * - With confidence: "I believe the answer is C"
   *
   * @param response - Response text
   * @returns True if response is a valid MCQ answer
   */
  private isValidMcqResponse(response: string): boolean {
    const responseStripped = response.trim().toUpperCase();

    // Single letter answer
    if (['A', 'B', 'C', 'D'].includes(responseStripped)) {
      return true;
    }

    // Check for letter at start with punctuation
    if (/^[A-D][.)\s]/.test(responseStripped)) {
      return true;
    }

    // Check for common MCQ answer patterns
    const responseLower = response.toLowerCase();
    const mcqAnswerPatterns = [
      /(?:the\s+)?answer\s+is\s+[a-d]/,
      /(?:i\s+)?(?:believe|think)\s+(?:the\s+)?answer\s+is\s+[a-d]/,
      /(?:i\s+)?(?:would\s+)?(?:choose|select|pick)\s+[a-d]/,
      /^[a-d]\s*[.):]/,
      /correct\s+answer\s+is\s+[a-d]/,
      /option\s+[a-d]/,
    ];

    for (const pattern of mcqAnswerPatterns) {
      if (pattern.test(responseLower)) {
        return true;
      }
    }

    return false;
  }

  /**
   * Detect if query is an intent classification prompt.
   *
   * v11 (Dec 2025): Fixes alignment floor triggering on Banking77 benchmark.
   */
  private isIntentClassificationFormat(query: string): boolean {
    const queryLower = query.toLowerCase();

    const classificationInstructions = [
      'classify this',
      'classify the',
      'categorize this',
      'categorize the',
      'identify the intent',
      'determine the intent',
      'what is the intent',
      'which intent',
      'which category',
      'label this',
    ];
    const hasInstruction = classificationInstructions.some((instr) =>
      queryLower.includes(instr)
    );

    const listMarkers = [
      'available intents:',
      'available categories:',
      'intent labels:',
      'category labels:',
      'possible intents:',
      'possible categories:',
      'choose from:',
      'one of the following:',
      'into one of',
    ];
    const hasListMarker = listMarkers.some((marker) => queryLower.includes(marker));

    const outputFormatMarkers = [
      'intent:',
      'category:',
      'label:',
      'format your response',
      'output the exact intent',
      'output the exact category',
    ];
    const hasOutputFormat = outputFormatMarkers.some((marker) =>
      queryLower.includes(marker)
    );

    return hasInstruction && (hasListMarker || hasOutputFormat);
  }

  /**
   * Check if response is a valid intent classification answer.
   *
   * v11 (Dec 2025): Recognizes intent classification response formats.
   */
  private isValidClassificationResponse(response: string): boolean {
    const responseLower = response.toLowerCase();
    const structuredPatterns = [
      /intent:\s*\w+/,
      /category:\s*\w+/,
      /label:\s*\w+/,
      /classification:\s*\w+/,
    ];
    if (structuredPatterns.some((pattern) => pattern.test(responseLower))) {
      return true;
    }

    const classificationPatterns = [
      /(?:the\s+)?intent\s+is\s+\w+/,
      /(?:the\s+)?category\s+is\s+\w+/,
      /(?:i\s+)?(?:classify|categorize)\s+(?:this\s+)?as\s+\w+/,
      /this\s+(?:is|falls\s+under)\s+(?:the\s+)?\w+\s+(?:intent|category)/,
      /belongs\s+to\s+(?:the\s+)?\w+\s+(?:intent|category)/,
    ];
    return classificationPatterns.some((pattern) => pattern.test(responseLower));
  }

  /**
   * Detect if query is a long context QA prompt (document + question).
   *
   * v12 (Jan 2026): Fixes alignment floor triggering on LongBench/BFCL benchmarks.
   */
  private isLongContextQaFormat(query: string): boolean {
    const queryLower = query.toLowerCase();
    const wordCount = query.split(/\s+/).length;
    if (wordCount < 300) {
      return false;
    }

    const qaMarkers = [
      'question:',
      'based on the',
      'according to the',
      'from the text',
      'from the passage',
      'from the document',
      'from the article',
      'in the text',
      'in the passage',
      'answer the following',
      'answer this question',
      'what does the',
      'what is the',
      'who is',
      'who was',
      'when did',
      'where did',
      'how did',
      'why did',
      'summarize',
      'extract',
    ];
    const hasQaMarker = qaMarkers.some((marker) => queryLower.includes(marker));

    const functionMarkers = [
      'function',
      'functions:',
      'api',
      'call the',
      'invoke',
      'parameters',
      'arguments',
      '{"name":',
      '"type":',
      '"description":',
    ];
    const hasFunctionMarker = functionMarkers.some((marker) =>
      queryLower.includes(marker)
    );

    const codeContextMarkers = ['```', 'def ', 'class ', 'import ', 'function ', 'const ', 'let ', 'var '];
    const hasCodeContext = codeContextMarkers.some((marker) => query.includes(marker));

    return hasQaMarker || hasFunctionMarker || hasCodeContext;
  }

  /**
   * Check if response is a valid long context QA answer.
   *
   * v14 (Jan 2026): Accept short factual answers in long context QA tasks.
   */
  private isValidLongContextResponse(response: string, query: string): boolean {
    const responseStripped = response.trim();
    const responseLower = responseStripped.toLowerCase();
    const wordCount = responseStripped.split(/\s+/).length;

    if (wordCount === 0) {
      return false;
    }

    if (wordCount <= 2) {
      const stripped = responseStripped.replace(/[ _-]/g, '');
      if (stripped && /^[a-z0-9]+$/i.test(stripped)) {
        return true;
      }
      if (['yes', 'no', 'true', 'false', 'none', 'unknown', 'n/a'].includes(responseLower)) {
        return true;
      }
      return false;
    }

    const questionLower = query.toLowerCase();
    const queryKeywords = this.extractKeywords(questionLower);
    const responseKeywords = this.extractKeywords(responseLower);
    let matches = 0;
    for (const word of queryKeywords) {
      if (responseKeywords.has(word) || responseLower.includes(word)) {
        matches += 1;
      }
    }
    if (queryKeywords.size > 0 && matches / queryKeywords.size >= 0.15) {
      return true;
    }

    const answerPatterns = [
      'the answer is',
      'the response is',
      'the text says',
      'the passage mentions',
      'it says that',
      'the document indicates',
      'in summary',
      'to summarize',
    ];
    if (answerPatterns.some((pattern) => responseLower.includes(pattern))) {
      return true;
    }

    if (wordCount >= 5) {
      if (responseStripped.toUpperCase() === responseStripped && responseStripped.length > 20) {
        return false;
      }

      const words = responseStripped.split(/\s+/);
      const realWords = words.filter((word) => word.length > 1 && /^[a-z]+$/i.test(word));
      if (realWords.length >= 3) {
        return true;
      }
    }

    return false;
  }

  /**
   * Detect if query is a function call/tool use prompt.
   *
   * v13 (Jan 2026): Fixes alignment floor triggering on BFCL benchmark.
   */
  private isFunctionCallFormat(query: string): boolean {
    const queryLower = query.toLowerCase();

    const functionMarkers = [
      'function',
      'functions:',
      'tool',
      'tools:',
      'api',
      'call the',
      'invoke',
      'execute the',
    ];
    const hasFunctionMarker = functionMarkers.some((marker) =>
      queryLower.includes(marker)
    );

    const schemaPatterns = ['"name":', '"parameters":', '"properties":', '"type":', '"description":', '```json'];
    const hasSchemaPattern = schemaPatterns.some((pattern) => queryLower.includes(pattern.toLowerCase()));

    const plainTextToolPatterns = [
      /^- \w+:/m,
      /\n- \w+:/m,
      /access to the following tools/,
      /available tools:/,
      /you have access to/,
    ];
    const hasPlainTextTools = plainTextToolPatterns.some((pattern) => pattern.test(queryLower));

    const instructionPatterns = [
      'call the function',
      'use the tool',
      'invoke the function',
      'execute the function',
      'make a function call',
      'generate a function call',
      'return a function call',
      'output a function call',
      'should be used',
      'which tool',
      'determine which tool',
      'select the appropriate',
      'choose the right tool',
      'respond with',
      'if a tool should',
    ];
    const hasInstruction = instructionPatterns.some((pattern) => queryLower.includes(pattern));

    const outputFormatMarkers = ['tool:', 'parameters:', 'tool_name:', 'arguments:'];
    const outputMarkerCount = outputFormatMarkers.filter((marker) => queryLower.includes(marker)).length;
    const hasOutputFormat = outputMarkerCount >= 2;

    return hasFunctionMarker && (hasSchemaPattern || hasInstruction || hasPlainTextTools || hasOutputFormat);
  }

  /**
   * Check if response is a valid function call answer.
   *
   * v13.4 (Jan 2026): Enhanced detection for tool response formats.
   */
  private isValidFunctionCallResponse(response: string): boolean {
    const responseLower = response.toLowerCase();

    const noToolPatterns = [
      'no tool is needed',
      'no tool needed',
      'no tool is required',
      'no tool required',
      "doesn't require a tool",
      'does not require a tool',
      "doesn't require any tool",
      'does not require any tool',
      'none of the tools',
      'none of the available tools',
      'no function is needed',
      'no function needed',
      'no function call',
      'no api call',
      'without using any tool',
      'without any tool',
      'can be answered directly',
      'can be answered without',
      "don't need to use",
      'do not need to use',
      'not necessary to use',
      'not necessary to call',
      'no need to call',
      'no need to use',
    ];
    if (noToolPatterns.some((pattern) => responseLower.includes(pattern))) {
      return true;
    }

    const jsonPatterns = ['{"name":', '{"function":', '{"tool":', '"name":', '"function_call":', '"tool_call":'];
    if (jsonPatterns.some((pattern) => response.includes(pattern))) {
      return true;
    }

    if (response.includes('```') && (response.includes('(') || response.includes('{'))) {
      return true;
    }

    const structuredPatterns = ['function:', 'tool:', 'call:'];
    if (structuredPatterns.some((pattern) => responseLower.includes(pattern))) {
      return true;
    }

    const naturalToolPatterns = [
      'i would use',
      'i will use',
      "i'll use",
      'use the',
      'using the',
      'call the',
      'calling the',
      'invoke the',
      'invoking the',
      'recommend using',
      'should use',
      'we can use',
      'we should use',
      'you can use',
      'appropriate tool',
      'correct tool',
      'right tool',
      'best tool',
    ];
    if (naturalToolPatterns.some((pattern) => responseLower.includes(pattern))) {
      return true;
    }

    const commonFunctionNames = [
      'get_weather',
      'calculate',
      'search',
      'create_event',
      'send_email',
      'query_database',
      'get_current_weather',
      'send_message',
      'get_stock_price',
      'book_flight',
      'set_reminder',
      'add_task',
    ];
    if (commonFunctionNames.some((funcName) => responseLower.includes(funcName))) {
      return true;
    }

    const paramPatterns = [
      'parameters:',
      'arguments:',
      'with parameters',
      'with arguments',
      'with the following',
      '"location"',
      '"query"',
      '"expression"',
      '"title"',
      '"to"',
      '"subject"',
    ];
    return paramPatterns.some((pattern) => responseLower.includes(pattern));
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
   * Detect chain-of-thought / step-by-step reasoning patterns in response.
   *
   * v9 (Nov 2025): Fixes alignment floor triggering on valid CoT responses.
   * v9.1 (Nov 2025): Enhanced multi-domain support (code, data, analysis, general)
   * v9.2 (Dec 2025): STRICTER detection to reduce false positives
   *   - Requires STRUCTURAL reasoning evidence (steps, lists, conclusions)
   *   - Domain keywords alone are NOT enough
   *   - Minimum response length required (100 chars)
   *   - Higher thresholds to avoid false positives
   *
   * A response with clear reasoning structure should get a boost because:
   * 1. It shows the model engaged with the problem
   * 2. CoT responses naturally have lower keyword overlap with questions
   * 3. Step-by-step reasoning is a sign of quality, not off-topic drift
   *
   * v9.2 Key Change: Only boost if there's ACTUAL multi-step structure,
   * not just domain-specific keywords.
   *
   * @param response - Response text
   * @returns Boost score 0.0 to 0.25
   */
  private detectReasoningChain(response: string): number {
    const responseLower = response.toLowerCase();

    // v9.2: Require minimum response length for reasoning detection
    // Short responses can't have meaningful reasoning chains
    if (response.length < 100) {
      return 0.0;
    }

    // === PHASE 1: Detect STRUCTURAL reasoning indicators ===
    // These are required for any boost to be applied
    let structuralScore = 0.0;

    // Signal 1: Math/Financial operations (equations with = sign)
    // These ARE structural - showing work step by step
    const equationMatches = response.match(/\d+\s*[+\-*/]\s*\d+\s*=\s*\d+/g) || [];
    const equalsMatches = response.match(/=\s*\$?\d+/g) || [];

    if (equationMatches.length >= 3 || equalsMatches.length >= 3) {
      structuralScore += 0.15;
    } else if (equationMatches.length >= 2 || equalsMatches.length >= 2) {
      structuralScore += 0.1;
    }

    // Signal 2: Step indicators (shows multi-step reasoning)
    const stepIndicators = [
      'first,',
      'then,',
      'next,',
      'finally,',
      'step 1',
      'step 2',
      'second,',
      'third,',
      'after that,',
      "let's calculate",
      "let's find",
      "let's solve",
      'to begin,',
      'initially,',
      'lastly,',
    ];

    let stepCount = 0;
    for (const indicator of stepIndicators) {
      if (responseLower.includes(indicator)) {
        stepCount++;
      }
    }

    if (stepCount >= 3) {
      structuralScore += 0.12;
    } else if (stepCount >= 2) {
      structuralScore += 0.08;
    }

    // Signal 3: Conclusion markers (shows reasoning has a final answer)
    const conclusionMarkers = [
      'therefore,',
      'thus,',
      'hence,',
      'the answer is',
      'the final answer',
      '####',
      'in total,',
      'altogether,',
      'in conclusion,',
      'to summarize,',
      'the result is',
      'this gives us',
      'we conclude',
    ];

    let conclusionCount = 0;
    for (const marker of conclusionMarkers) {
      if (responseLower.includes(marker)) {
        conclusionCount++;
      }
    }

    if (conclusionCount >= 2) {
      structuralScore += 0.08;
    } else if (conclusionCount >= 1) {
      structuralScore += 0.04;
    }

    // Signal 4: Numbered/bulleted lists with 3+ items (shows enumerated steps)
    const numberedList = (response.match(/^\s*\d+[.)]\s/gm) || []).length;
    const bulletList = (response.match(/^\s*[-•*]\s/gm) || []).length;

    if (numberedList >= 3 || bulletList >= 3) {
      structuralScore += 0.08;
    }

    // Signal 5: Code blocks with explanation (shows structured code reasoning)
    // Only count if there's a code block AND explanatory text
    const hasCodeBlock = response.includes('```');
    const hasCodeExplanation = [
      'this code',
      'the function',
      'this function',
      "here's how",
      'this will',
    ].some((phrase) => responseLower.includes(phrase));

    if (hasCodeBlock && hasCodeExplanation) {
      structuralScore += 0.1;
    }

    // v9.2 CRITICAL: Require minimum structural evidence
    // Without this, we get false positives from domain keywords alone
    if (structuralScore < 0.08) {
      return 0.0;
    }

    // === PHASE 2: Add domain-specific bonuses (only if structural evidence exists) ===
    let domainBonus = 0.0;

    // Only add domain bonuses for domains with HEAVY reasoning requirements
    // and ONLY if multiple domain signals are present

    // Math domain bonus (already got credit from equations)
    const mathMarkers = ['calculate', 'compute', 'solve', 'equation', 'formula'];
    if (mathMarkers.filter((m) => responseLower.includes(m)).length >= 2) {
      domainBonus += 0.03;
    }

    // Analysis/comparison domain (requires strong multi-signal evidence)
    const analysisStrong = [
      'on one hand',
      'on the other hand',
      'in contrast',
      'compared to',
      'whereas',
      'advantage',
      'disadvantage',
    ];
    if (analysisStrong.filter((p) => responseLower.includes(p)).length >= 2) {
      domainBonus += 0.03;
    }

    // Scientific reasoning (requires methodology + findings)
    const scienceStructure = [
      'hypothesis',
      'experiment',
      'methodology',
      'conclusion',
      'findings',
    ];
    if (scienceStructure.filter((p) => responseLower.includes(p)).length >= 3) {
      domainBonus += 0.03;
    }

    // Cap total score and return
    const totalScore = structuralScore + domainBonus;
    return Math.min(0.25, totalScore);
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

    // v9: Report reasoning chain detection
    if ((features.reasoningChain || 0) > 0.1) {
      reasons.push('chain-of-thought reasoning detected');
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

    // v10: MCQ format detection - handle before normal scoring
    // MCQ responses (A, B, C, D) to MCQ prompts should get high alignment
    const isMcq = this.isMcqFormat(query);
    const validMcqResponse = isMcq ? this.isValidMcqResponse(response) : false;
    features.isMcq = isMcq;
    features.validMcqResponse = validMcqResponse;

    // v10: If MCQ with valid response, return high alignment score immediately
    if (isMcq && validMcqResponse) {
      // MCQ responses are trivial by nature - single letter answers are expected
      features.isTrivial = true;
      features.baseline = this.BASELINE_TRIVIAL;
      features.mcqBoost = true;
      // Give 0.75 score to valid MCQ responses to avoid alignment floor
      const finalScore = 0.75;

      if (verbose) {
        return {
          alignmentScore: finalScore,
          features,
          reasoning: `Score ${finalScore.toFixed(3)}: MCQ format with valid letter answer`,
          isTrivial: true,
          baselineUsed: this.BASELINE_TRIVIAL,
        };
      }
      return finalScore;
    }

    // v11: Intent classification detection - handle before normal scoring
    const isClassification = this.isIntentClassificationFormat(query);
    const validClassificationResponse = isClassification
      ? this.isValidClassificationResponse(response)
      : false;
    features.isClassification = isClassification;
    features.validClassificationResponse = validClassificationResponse;

    if (isClassification && validClassificationResponse) {
      features.isTrivial = true;
      features.baseline = this.BASELINE_TRIVIAL;
      features.classificationBoost = true;
      const finalScore = 0.72;

      if (verbose) {
        return {
          alignmentScore: finalScore,
          features,
          reasoning: `Score ${finalScore.toFixed(3)}: Classification format with valid intent answer`,
          isTrivial: true,
          baselineUsed: this.BASELINE_TRIVIAL,
        };
      }
      return finalScore;
    }

    // v12: Long context QA detection - handle before normal scoring
    const isLongContextQa = this.isLongContextQaFormat(query);
    const validLongContextResponse = isLongContextQa
      ? this.isValidLongContextResponse(response, query)
      : false;
    features.isLongContextQa = isLongContextQa;
    features.validLongContextResponse = validLongContextResponse;

    if (isLongContextQa && validLongContextResponse) {
      features.isTrivial = false;
      features.baseline = this.BASELINE_STANDARD;
      features.longContextQaBoost = true;
      const finalScore = 0.72;

      if (verbose) {
        return {
          alignmentScore: finalScore,
          features,
          reasoning: `Score ${finalScore.toFixed(3)}: Long context QA format with valid answer`,
          isTrivial: false,
          baselineUsed: this.BASELINE_STANDARD,
        };
      }
      return finalScore;
    }

    // v13: Function call/tool use detection - handle before normal scoring
    const isFunctionCall = this.isFunctionCallFormat(query);
    const validFunctionCallResponse = isFunctionCall
      ? this.isValidFunctionCallResponse(response)
      : false;
    features.isFunctionCall = isFunctionCall;
    features.validFunctionCallResponse = validFunctionCallResponse;

    if (isFunctionCall && validFunctionCallResponse) {
      features.isTrivial = false;
      features.baseline = this.BASELINE_STANDARD;
      features.functionCallBoost = true;
      const finalScore = 0.72;

      if (verbose) {
        return {
          alignmentScore: finalScore,
          features,
          reasoning: `Score ${finalScore.toFixed(3)}: Function call format with valid tool response`,
          isTrivial: false,
          baselineUsed: this.BASELINE_STANDARD,
        };
      }
      return finalScore;
    }

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

    // v9: Reasoning chain detection for CoT responses
    const reasoningScore = this.detectReasoningChain(responseLower);
    features.reasoningChain = reasoningScore;
    score += reasoningScore;

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
