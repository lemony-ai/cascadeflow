/**
 * Domain Detection for Smart Routing
 *
 * Automatic domain detection to route queries to specialized models based on
 * content (code, medical, legal, general, etc.).
 *
 * Features:
 * - Rule-based keyword matching with weighted scoring
 * - 15 production domains
 * - Confidence scoring
 * - Domain-specific model recommendations
 *
 * Port from Python cascadeflow/routing/domain.py
 *
 * @example
 * ```typescript
 * import { DomainRouter, Domain } from '@cascadeflow/core';
 *
 * const router = new DomainRouter();
 * const result = router.detect("Write a Python function to sort a list");
 * console.log(`Domain: ${result.domain}, Confidence: ${result.confidence}`);
 * // Output: Domain: code, Confidence: 0.95
 * ```
 */

/**
 * Supported domains for query routing (15 production domains)
 */
export enum Domain {
  /** Programming, development, software engineering */
  CODE = 'code',
  /** Data analysis, SQL, analytics */
  DATA = 'data',
  /** Structured data extraction (JSON, XML, forms) */
  STRUCTURED = 'structured',
  /** RAG/search queries, document retrieval */
  RAG = 'rag',
  /** Multi-turn dialogue, chatbot */
  CONVERSATION = 'conversation',
  /** Tool/function calling, external APIs */
  TOOL = 'tool',
  /** Creative writing, content generation */
  CREATIVE = 'creative',
  /** Text summarization, condensing */
  SUMMARY = 'summary',
  /** Language translation */
  TRANSLATION = 'translation',
  /** Mathematical reasoning, calculations */
  MATH = 'math',
  /** Healthcare, medicine (high accuracy required) */
  MEDICAL = 'medical',
  /** Law, contracts, compliance */
  LEGAL = 'legal',
  /** Financial analysis, market research */
  FINANCIAL = 'financial',
  /** Vision + text queries */
  MULTIMODAL = 'multimodal',
  /** General knowledge, factual QA */
  GENERAL = 'general',
}

/**
 * Keywords for domain detection with weighted importance
 */
export interface DomainKeywords {
  /** Highly discriminative keywords (weight: 1.5) */
  veryStrong: string[];
  /** High-confidence keywords (weight: 1.0) */
  strong: string[];
  /** Medium-confidence keywords (weight: 0.7) */
  moderate: string[];
  /** Low-confidence keywords (weight: 0.3) */
  weak: string[];
}

/**
 * Domain detection result
 */
export interface DomainDetectionResult {
  /** Detected domain */
  domain: Domain;
  /** Confidence score (0-1) */
  confidence: number;
  /** Keyword scores by domain */
  scores?: Record<string, number>;
  /** Additional detection metadata (aligned with Python v15) */
  metadata?: {
    /** Length of the input query */
    queryLength: number;
    /** Confidence threshold used */
    threshold: number;
    /** Whether query was detected as multiple-choice */
    isMcq: boolean;
    /** Subject-based domain hint from MCQ parsing */
    subjectHint: string | null;
  };
}

/**
 * Domain router statistics
 */
export interface DomainRouterStats {
  /** Total detections performed */
  totalDetections: number;
  /** Detections by domain */
  byDomain: Record<string, number>;
  /** Average confidence */
  avgConfidence: number;
}

/** MCQ detection patterns - port from Python domain.py */
const MCQ_PATTERNS: RegExp[] = [
  // Standard MCQ formats
  /(?:answer|choose|select)\s+(?:the\s+)?(?:following\s+)?(?:multiple[- ]choice|mcq)/i,
  /provide\s+your\s+answer\s+as\s+(?:a\s+)?(?:single\s+)?letter/i,
  /^(?:question|q)\s*(?:\d+)?[:.]\s*/im,
  // Choice indicators (A. B. C. D. or A) B) C) D))
  /(?:^|\n)\s*[ABCD]\s*[.)]\s+/m,
  // MMLU-style format
  /answer:\s*$/im,
];

/** Subject-to-domain mapping for MCQ (MMLU categories) */
const SUBJECT_DOMAIN_MAP: Record<string, Domain> = {
  // STEM subjects - Math
  math: Domain.MATH,
  algebra: Domain.MATH,
  calculus: Domain.MATH,
  geometry: Domain.MATH,
  statistics: Domain.MATH,
  arithmetic: Domain.MATH,
  mathematics: Domain.MATH,
  // Science subjects
  physics: Domain.GENERAL,
  chemistry: Domain.GENERAL,
  biology: Domain.GENERAL,
  astronomy: Domain.GENERAL,
  science: Domain.GENERAL,
  // Medical subjects
  medicine: Domain.MEDICAL,
  medical: Domain.MEDICAL,
  anatomy: Domain.MEDICAL,
  clinical: Domain.MEDICAL,
  nutrition: Domain.MEDICAL,
  health: Domain.MEDICAL,
  virology: Domain.MEDICAL,
  // Legal subjects
  law: Domain.LEGAL,
  legal: Domain.LEGAL,
  jurisprudence: Domain.LEGAL,
  // Financial subjects
  accounting: Domain.FINANCIAL,
  economics: Domain.FINANCIAL,
  finance: Domain.FINANCIAL,
  business: Domain.FINANCIAL,
  marketing: Domain.FINANCIAL,
  management: Domain.FINANCIAL,
  // Code/CS subjects
  computer: Domain.CODE,
  programming: Domain.CODE,
  machine_learning: Domain.CODE,
  security: Domain.CODE,
};

/** Built-in domain keyword mappings (aligned with Python v15) */
const DOMAIN_KEYWORDS: Record<Domain, DomainKeywords> = {
  [Domain.CODE]: {
    veryStrong: ['async', 'await', 'import', 'def', 'const', 'let', 'npm', 'pip', 'docker', 'kubernetes', 'pytest', 'unittest'],
    strong: ['function', 'class', 'python', 'javascript', 'typescript', 'java', 'code', 'algorithm', 'api', 'debug', 'error', 'exception', 'compile', 'runtime', 'syntax', 'refactor', 'repository'],
    moderate: ['program', 'software', 'implement', 'develop', 'build', 'script', 'test', 'deploy', 'git', 'github', 'lint', 'regex', 'recursion', 'oop', 'frontend', 'backend'],
    weak: [],
  },
  [Domain.DATA]: {
    veryStrong: ['pandas', 'numpy', 'etl', 'warehouse', 'bi', 'correlation'],
    strong: ['sql', 'database', 'query', 'dataframe', 'analysis', 'visualization', 'dataset', 'analytics', 'select', 'regression'],
    moderate: ['data', 'table', 'column', 'join', 'filter', 'aggregate', 'chart', 'graph', 'metrics', 'report', 'pivot', 'group by'],
    weak: [],
  },
  [Domain.STRUCTURED]: {
    veryStrong: ['json', 'xml', 'yaml', 'pydantic', 'schema validation', 'protobuf', 'avro', 'json schema', 'dataclass'],
    strong: ['extract', 'parse', 'schema', 'fields', 'entity', 'structure', 'format', 'convert', 'normalize', 'csv', 'excel', 'spreadsheet', 'serialize', 'deserialize', 'validate', 'attrs'],
    moderate: ['form', 'template', 'transform', 'map', 'property', 'field mapping', 'record', 'document structure', 'nested', 'flatten', 'key-value', 'attribute', 'toml', 'msgpack'],
    weak: [],
  },
  [Domain.RAG]: {
    veryStrong: ['semantic search', 'vector search', 'embedding', 'similar documents'],
    strong: ['search', 'retrieve', 'lookup', 'documentation', 'knowledge base', 'documents', 'corpus', 'index', 'relevance'],
    moderate: ['summarize', 'review', 'analyze', 'compare documents', 'reference', 'citation', 'source', 'context', 'passages'],
    weak: [],
  },
  [Domain.CONVERSATION]: {
    veryStrong: ['remember', 'you said', 'earlier you mentioned', 'back to'],
    strong: ['chat', 'conversation', 'discuss', 'follow-up', 'continue', 'previous', 'earlier', 'dialogue', 'multi-turn'],
    moderate: ['help', 'support', 'assist', 'question', 'clarify', 'explain', 'understand', 'context', 'referring to'],
    weak: [],
  },
  [Domain.TOOL]: {
    veryStrong: ['api call', 'webhook', 'endpoint', 'post', 'get', 'put'],
    strong: ['fetch', 'send', 'create', 'update', 'delete', 'action', 'execute', 'call', 'invoke', 'integration'],
    moderate: ['check', 'verify', 'schedule', 'book', 'order', 'submit', 'run', 'trigger', 'perform', 'external', 'third-party'],
    weak: [],
  },
  [Domain.CREATIVE]: {
    veryStrong: [],
    strong: ['write', 'story', 'poem', 'creative', 'article', 'essay', 'narrative', 'character', 'plot', 'compose', 'draft'],
    moderate: ['describe', 'imagine', 'design', 'generate content', 'marketing', 'copy', 'blog', 'social media'],
    weak: ['create', 'make', 'new'],
  },
  [Domain.SUMMARY]: {
    veryStrong: [],
    strong: ['summarize', 'condense', 'tldr', 'executive summary', 'key points', 'main themes', 'highlights', 'overview'],
    moderate: ['brief', 'abstract', 'essence', 'distill', 'compress', 'shorten', 'extract main'],
    weak: ['short', 'simple', 'quick'],
  },
  [Domain.TRANSLATION]: {
    veryStrong: [],
    strong: ['translate', 'translation', 'convert language', 'localize', 'spanish', 'french', 'german', 'chinese', 'japanese'],
    moderate: ['language', 'multilingual', 'interpret', 'international', 'native language', 'foreign'],
    weak: ['change', 'switch', 'different language'],
  },
  [Domain.MATH]: {
    veryStrong: ['derivative', 'integral', 'theorem', 'proof', 'eigenvalue', 'differential equation', 'matrix multiplication', 'calculus', 'trigonometry', 'logarithm', 'how many did', 'how much does', 'how much in dollars', 'how much money', 'what is the total', 'what percentage'],
    strong: ['calculate', 'equation', 'formula', 'mathematics', 'algebra', 'geometry', 'statistics', 'probability', 'solve', 'vector', 'matrix', 'optimization', 'polynomial', 'how much', 'how many', 'per day', 'per hour', 'per week', 'each day', 'remainder', 'in total', 'altogether'],
    moderate: ['compute', 'graph', 'variable', 'function', 'coefficient', 'expression', 'numeric', 'symbolic', 'scientific notation', 'exponent', 'factorial', 'summation', 'left over', 'start with', 'end up with', 'divided equally', 'split evenly'],
    weak: ['add', 'subtract', 'multiply', 'divide', 'number', 'math', 'show your work', 'step by step', 'calculate', 'equals', 'what is', 'times', 'plus', 'minus'],
  },
  [Domain.MEDICAL]: {
    veryStrong: ['symptoms of', 'diagnosis of', 'treatment for', 'blood test', 'medical advice', 'diabetes', 'hypertension', 'cardiovascular', 'prescription drug'],
    strong: ['diagnosis', 'symptom', 'treatment', 'disease', 'patient', 'medical', 'doctor', 'medication', 'surgery', 'clinical', 'pharmacy', 'prescription', 'healthcare', 'prognosis', 'chronic', 'acute'],
    moderate: ['health', 'pain', 'condition', 'therapy', 'hospital', 'nurse', 'drug', 'dosage', 'protocol', 'interact', 'side effect'],
    weak: ['feel', 'hurt', 'sick', 'ill'],
  },
  [Domain.LEGAL]: {
    veryStrong: [],
    strong: ['law', 'legal', 'contract', 'lawsuit', 'court', 'attorney', 'regulation', 'statute', 'liability', 'plaintiff', 'defendant', 'compliance', 'litigation'],
    moderate: ['rights', 'agreement', 'clause', 'terms', 'policy', 'jurisdiction', 'precedent', 'case law'],
    weak: ['rule', 'requirement', 'must'],
  },
  [Domain.FINANCIAL]: {
    veryStrong: [],
    strong: ['financial', 'investment', 'portfolio', 'risk', 'earnings', 'revenue', 'market', 'stock', 'trading', 'valuation', 'roi', 'profit', 'loss', 'bond', 'bonds', 'equity', 'equities', 'interest rate', 'yield', 'coupon', 'fixed income'],
    moderate: ['analysis', 'forecast', 'budget', 'venture capital', 'asset', 'liability', 'cash flow', 'dividend', 'risk-return', 'rate environment', 'yield curve'],
    weak: ['money', 'cost', 'price', 'pay'],
  },
  [Domain.MULTIMODAL]: {
    veryStrong: [],
    strong: ['image', 'photo', 'picture', 'visual', 'scan', 'ocr', 'chart', 'graph', 'diagram', 'screenshot', 'video'],
    moderate: ['see', 'view', 'look at', 'display', 'caption', 'describe image', 'analyze photo', 'show me the image', 'show the picture'],
    weak: ['this', 'that', 'here'],
  },
  [Domain.GENERAL]: {
    veryStrong: ['what is the capital', 'who invented', 'when was', 'how does', 'explain how', 'tell me about'],
    strong: ['fact', 'history', 'geography', 'science', 'explain', 'describe', 'definition', 'famous', 'country', 'city', 'world'],
    moderate: ['what is', 'who is', 'where is', 'why does', 'information about', 'knowledge', 'encyclopedia', 'trivia'],
    weak: ['simple', 'basic', 'general'],
  },
};

/**
 * Domain router for automatic domain detection
 *
 * Detects query domain using rule-based keyword matching with weighted scoring.
 * 15 production domains covering code, data, creative, medical, legal, and more.
 *
 * @example
 * ```typescript
 * const router = new DomainRouter({ verbose: true });
 *
 * // Detect domain
 * const result = router.detect("Write a Python function to sort a list");
 * console.log(`Domain: ${result.domain}`); // "code"
 * console.log(`Confidence: ${result.confidence}`); // 0.95
 *
 * // Check statistics
 * const stats = router.getStats();
 * console.log(`Code queries: ${stats.byDomain.code}`);
 * ```
 */
export class DomainRouter {
  private verbose: boolean;
  private stats: {
    totalDetections: number;
    byDomain: Record<string, number>;
    confidenceSum: number;
  };

  constructor(config: { verbose?: boolean } = {}) {
    this.verbose = config.verbose ?? false;
    this.stats = {
      totalDetections: 0,
      byDomain: Object.fromEntries(Object.values(Domain).map((d) => [d, 0])),
      confidenceSum: 0,
    };
  }

  /**
   * Detect domain from query
   *
   * Uses rule-based keyword matching with weighted scoring:
   * - Very strong keywords: 1.5 weight
   * - Strong keywords: 1.0 weight
   * - Moderate keywords: 0.7 weight
   * - Weak keywords: 0.3 weight
   *
   * @param query - Query text
   * @returns DomainDetectionResult with domain and confidence
   *
   * @example
   * ```typescript
   * const result = router.detect("SELECT * FROM users WHERE age > 18");
   * console.log(result.domain); // "data"
   * console.log(result.confidence); // 0.87
   * ```
   */
  detect(query: string): DomainDetectionResult {
    // Check for MCQ format and preprocess if detected
    const { isMcq, extractedContent, subjectHint } = this.detectMcqFormat(query);

    // Use extracted content for keyword matching if MCQ detected
    const queryToAnalyze = isMcq ? extractedContent : query;
    const queryLower = queryToAnalyze.toLowerCase();
    const scores: Record<string, number> = {};

    // Calculate scores for each domain
    for (const [domain, keywords] of Object.entries(DOMAIN_KEYWORDS)) {
      let score = 0;

      // Very strong keywords (1.5x weight)
      for (const keyword of keywords.veryStrong) {
        if (queryLower.includes(keyword.toLowerCase())) {
          score += 1.5;
        }
      }

      // Strong keywords (1.0x weight)
      for (const keyword of keywords.strong) {
        if (queryLower.includes(keyword.toLowerCase())) {
          score += 1.0;
        }
      }

      // Moderate keywords (0.7x weight)
      for (const keyword of keywords.moderate) {
        if (queryLower.includes(keyword.toLowerCase())) {
          score += 0.7;
        }
      }

      // Weak keywords (0.3x weight)
      for (const keyword of keywords.weak) {
        if (queryLower.includes(keyword.toLowerCase())) {
          score += 0.3;
        }
      }

      scores[domain] = score;
    }

    // If MCQ detected, apply subject-based domain hint
    if (isMcq && subjectHint) {
      // Boost the hinted domain score
      scores[subjectHint] = Math.max((scores[subjectHint] || 0) + 0.5, 0.8);
    }

    // If MCQ detected, penalize CONVERSATION domain (it's not a conversation)
    if (isMcq) {
      scores[Domain.CONVERSATION] = Math.max(0, (scores[Domain.CONVERSATION] || 0) - 0.5);
    }

    // Find domain with highest score
    let maxScore = 0;
    let detectedDomain = Domain.GENERAL;

    for (const [domain, score] of Object.entries(scores)) {
      if (score > maxScore) {
        maxScore = score;
        detectedDomain = domain as Domain;
      }
    }

    // Calculate confidence (normalized score)
    const confidence = Math.min(maxScore / 5.0, 1.0); // Normalize to 0-1

    // Update statistics
    this.stats.totalDetections++;
    this.stats.byDomain[detectedDomain]++;
    this.stats.confidenceSum += confidence;

    if (this.verbose) {
      console.log(`Domain detected: ${detectedDomain} (confidence: ${confidence.toFixed(2)})${isMcq ? ' [MCQ detected]' : ''}`);
      console.log(`Top scores: ${JSON.stringify(
        Object.entries(scores)
          .sort(([, a], [, b]) => b - a)
          .slice(0, 3)
          .map(([d, s]) => ({ domain: d, score: s.toFixed(2) }))
      )}`);
    }

    return {
      domain: detectedDomain,
      confidence,
      scores,
      metadata: {
        queryLength: query.length,
        threshold: 0,
        isMcq,
        subjectHint: subjectHint ?? null,
      },
    };
  }

  /**
   * Detect if query is a multiple-choice question and extract content.
   *
   * @param query - Original query text
   * @returns Object with isMcq flag, extracted content, and domain hint
   */
  private detectMcqFormat(query: string): {
    isMcq: boolean;
    extractedContent: string;
    subjectHint: Domain | null;
  } {
    const queryLower = query.toLowerCase();

    // Check MCQ patterns
    let isMcq = false;
    for (const pattern of MCQ_PATTERNS) {
      if (pattern.test(query)) {
        isMcq = true;
        break;
      }
    }

    if (!isMcq) {
      return { isMcq: false, extractedContent: query, subjectHint: null };
    }

    // Extract the actual question content (strip MCQ wrapper)
    let extracted = query;

    // Remove common MCQ instruction prefixes
    const prefixesToRemove = [
      /^answer the following multiple[- ]?choice question[.:]?\s*/i,
      /^provide your answer as a single letter[^.]*[.]\s*/i,
      /^choose the (?:best|correct) answer[.:]?\s*/i,
      /^select (?:one|the correct answer)[.:]?\s*/i,
    ];

    for (const prefix of prefixesToRemove) {
      extracted = extracted.replace(prefix, '');
    }

    // Extract content after "Question:" if present
    const questionMatch = extracted.match(/question[:\s]+(.+?)(?=\n[ABCD][.)]\s|\Z)/is);
    if (questionMatch) {
      extracted = questionMatch[1].trim();
    }

    // Remove answer choices (A. B. C. D. lines)
    extracted = extracted.replace(/\n[ABCD][.)]\s+[^\n]+/g, '');
    // Remove trailing "Answer:" prompt
    extracted = extracted.replace(/\s*answer:\s*$/i, '');

    // Try to detect domain from subject keywords in the question
    const subjectHint = this.detectSubjectDomain(queryLower);

    return { isMcq: true, extractedContent: extracted.trim(), subjectHint };
  }

  /**
   * Detect domain hint from subject-related keywords in the query.
   *
   * @param queryLower - Lowercase query text
   * @returns Domain hint if detected, null otherwise
   */
  private detectSubjectDomain(queryLower: string): Domain | null {
    for (const [subjectKeyword, domain] of Object.entries(SUBJECT_DOMAIN_MAP)) {
      if (queryLower.includes(subjectKeyword)) {
        return domain;
      }
    }
    return null;
  }

  /**
   * Get routing statistics
   *
   * @returns DomainRouterStats with detection counts and averages
   *
   * @example
   * ```typescript
   * const stats = router.getStats();
   * console.log(`Total: ${stats.totalDetections}`);
   * console.log(`Code: ${stats.byDomain.code}`);
   * console.log(`Avg confidence: ${stats.avgConfidence.toFixed(2)}`);
   * ```
   */
  getStats(): DomainRouterStats {
    const avgConfidence =
      this.stats.totalDetections > 0
        ? this.stats.confidenceSum / this.stats.totalDetections
        : 0;

    return {
      totalDetections: this.stats.totalDetections,
      byDomain: { ...this.stats.byDomain },
      avgConfidence,
    };
  }

  /**
   * Reset statistics
   *
   * @example
   * ```typescript
   * router.resetStats();
   * console.log(router.getStats().totalDetections); // 0
   * ```
   */
  resetStats(): void {
    this.stats = {
      totalDetections: 0,
      byDomain: Object.fromEntries(Object.values(Domain).map((d) => [d, 0])),
      confidenceSum: 0,
    };

    if (this.verbose) {
      console.log('DomainRouter stats reset');
    }
  }
}

/**
 * Create a DomainRouter instance
 *
 * @param config - Router configuration
 * @returns DomainRouter instance
 *
 * @example
 * ```typescript
 * import { createDomainRouter } from '@cascadeflow/core';
 *
 * const router = createDomainRouter({ verbose: true });
 * const result = router.detect("Translate this to French");
 * ```
 */
export function createDomainRouter(config?: { verbose?: boolean }): DomainRouter {
  return new DomainRouter(config);
}
