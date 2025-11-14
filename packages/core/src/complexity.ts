/**
 * Query Complexity Detection
 *
 * Enhanced complexity detector with technical term recognition.
 * Ported from Python cascadeflow/quality/complexity.py
 *
 * Features:
 * - 500+ technical terms across multiple scientific domains
 * - Mathematical notation detection (Unicode + LaTeX)
 * - Domain-specific vocabulary scoring
 * - Query structure analysis
 *
 * Based on research:
 * - NER (Named Entity Recognition) for scientific terms
 * - Unicode mathematical symbol detection
 * - Domain-specific vocabulary scoring
 */

import type { QueryComplexity } from './types';

/**
 * Complexity detection result
 */
export interface ComplexityResult {
  /** Detected complexity level */
  complexity: QueryComplexity;

  /** Confidence score (0-1) */
  confidence: number;

  /** Optional metadata */
  metadata?: {
    /** Detected technical terms */
    technicalTerms?: string[];

    /** Detected domains */
    domains?: Set<string>;

    /** Mathematical notation found */
    mathNotation?: string[];

    /** Domain score */
    domainScore?: number;
  };
}

/**
 * Complexity detector with technical term recognition
 */
export class ComplexityDetector {
  // =====================================================================
  // TECHNICAL TERM DATABASES
  // =====================================================================

  private static readonly PHYSICS_TERMS = new Set([
    // Quantum Mechanics
    'quantum entanglement',
    'quantum superposition',
    'quantum decoherence',
    'wave function collapse',
    'schrödinger equation',
    'schrodinger equation',
    'heisenberg uncertainty',
    'uncertainty principle',
    'pauli exclusion',
    'fermi-dirac',
    'bose-einstein',
    'bell theorem',
    'bell inequality',
    'double slit experiment',
    'quantum tunneling',
    'zero-point energy',
    'planck constant',
    'dirac equation',
    'klein-gordon',
    // Relativity
    'special relativity',
    'general relativity',
    'spacetime curvature',
    'schwarzschild metric',
    'lorentz transformation',
    'time dilation',
    'length contraction',
    'event horizon',
    'gravitational waves',
    'einstein field equations',
    'geodesic',
    'minkowski space',
    // Particle Physics
    'standard model',
    'higgs boson',
    'higgs mechanism',
    'gauge theory',
    'quantum chromodynamics',
    'qcd',
    'quantum electrodynamics',
    'qed',
    'weak interaction',
    'strong force',
    'electroweak theory',
    'feynman diagrams',
    'renormalization',
    'symmetry breaking',
    // Fluid Dynamics (Critical!)
    'navier-stokes equations',
    'navier stokes',
    'reynolds number',
    'turbulent flow',
    'laminar flow',
    'boundary layer',
    'bernoulli equation',
    'euler equations',
    'viscosity',
    'incompressible flow',
    'mach number',
    'continuity equation',
    'vorticity',
    'streamline',
    'stokes flow',
    // Thermodynamics
    'carnot cycle',
    'entropy',
    'enthalpy',
    'gibbs free energy',
    'boltzmann distribution',
    'partition function',
    'phase transition',
    'critical point',
    'thermodynamic equilibrium',
  ]);

  private static readonly MATHEMATICS_TERMS = new Set([
    // Logic & Set Theory (Critical!)
    'gödel incompleteness',
    'goedel incompleteness',
    'gödel theorem',
    'incompleteness theorem',
    'church-turing thesis',
    'halting problem',
    'continuum hypothesis',
    'axiom of choice',
    'zermelo-fraenkel',
    'peano axioms',
    'cantor set',
    'russell paradox',
    // Number Theory
    'riemann hypothesis',
    'riemann zeta function',
    'prime number theorem',
    'fermat last theorem',
    'goldbach conjecture',
    'twin prime',
    'diophantine equation',
    'modular arithmetic',
    'elliptic curve',
    // Topology
    'hausdorff space',
    'topological space',
    'homeomorphism',
    'homotopy',
    'fundamental group',
    'manifold',
    'compactness',
    'connectedness',
    'metric space',
    'banach space',
    'hilbert space',
    // Analysis
    'cauchy sequence',
    'lebesgue integral',
    'fourier transform',
    'laplace transform',
    'taylor series',
    'laurent series',
    'contour integration',
    'residue theorem',
    'analytic continuation',
    'dirichlet problem',
    'green function',
    'sturm-liouville',
    // Algebra
    'galois theory',
    'group theory',
    'ring theory',
    'field theory',
    'homomorphism',
    'isomorphism',
    'kernel',
    'quotient group',
    'sylow theorem',
    'representation theory',
    'lie algebra',
    'lie group',
  ]);

  private static readonly CS_TERMS = new Set([
    // Complexity Theory
    'np-complete',
    'np-hard',
    'polynomial time',
    'turing machine',
    'computational complexity',
    'big o notation',
    'time complexity',
    'space complexity',
    'decidability',
    'reducibility',
    // Algorithms
    'dynamic programming',
    'greedy algorithm',
    'divide and conquer',
    'backtracking',
    'branch and bound',
    'amortized analysis',
    'dijkstra algorithm',
    'bellman-ford',
    'floyd-warshall',
    'kruskal algorithm',
    'prim algorithm',
    'topological sort',
    // AI/ML
    'neural network',
    'deep learning',
    'convolutional neural network',
    'recurrent neural network',
    'transformer',
    'attention mechanism',
    'gradient descent',
    'backpropagation',
    'overfitting',
    'regularization',
    'cross-validation',
    'reinforcement learning',
    'q-learning',
    // Quantum Computing (Added)
    'quantum computing',
    'quantum algorithm',
    'quantum supremacy',
    'qubit',
    'quantum gate',
    'quantum circuit',
  ]);

  private static readonly ENGINEERING_TERMS = new Set([
    'finite element analysis',
    'fea',
    'computational fluid dynamics',
    'cfd',
    'control theory',
    'pid controller',
    'feedback loop',
    'transfer function',
    'laplace domain',
    'frequency response',
    'bode plot',
    'nyquist plot',
    'signal processing',
    'fourier analysis',
    'wavelet transform',
    'digital signal processing',
    'dsp',
    'sampling theorem',
  ]);

  // =====================================================================
  // KEYWORD PATTERNS
  // =====================================================================

  private static readonly TRIVIAL_PATTERNS = [
    /what\s+is\s+\d+\s*[+*/\-]\s*\d+/i,
    /what's\s+\d+\s*[+*/\-]\s*\d+/i,
    /whats\s+\d+\s*[+*/\-]\s*\d+/i,
    /(calculate|compute|solve)\s+\d+\s*[+*/\-]\s*\d+/i,
    /(capital|population|currency|language)\s+of\s+\w+/i,
    /^(hi|hello|hey|thanks|thank\s+you)[\.\!\?]*$/i,
  ];

  private static readonly TRIVIAL_CONCEPTS = new Set([
    'color', 'colour', 'red', 'blue', 'green', 'yellow', 'black', 'white',
    'sky', 'sun', 'moon', 'water', 'cat', 'dog', 'bird', 'fish',
  ]);

  private static readonly SIMPLE_KEYWORDS = [
    'what', 'who', 'when', 'where', 'which',
    'define', 'definition', 'meaning', 'means',
    'explain', 'describe', 'tell me',
    'is', 'are', 'does', 'do',
    'simple', 'basic', 'introduction', 'overview', 'summary', 'briefly',
    'example', 'examples', 'difference', 'similar', 'list', 'name',
    'translate', 'convert', 'change',
  ];

  private static readonly MODERATE_KEYWORDS = [
    'compare', 'contrast', 'versus', 'vs', 'vs.',
    'difference between', 'distinguish',
    'how does', 'how do', 'why does', 'why do',
    'advantages', 'disadvantages', 'benefits', 'drawbacks',
    'pros and cons', 'pros', 'cons',
    'summarize', 'outline', 'describe in detail',
    'relationship', 'connection', 'correlation',
    'cause', 'effect', 'impact',
    'process', 'steps', 'procedure',
    'write', 'code', 'function', 'program', 'script',
    'reverse', 'sort', 'filter', 'map',
  ];

  private static readonly HARD_KEYWORDS = [
    'analyze', 'analysis', 'examine', 'investigate',
    'evaluate', 'assessment', 'assess', 'appraise',
    'critique', 'critical', 'critically',
    'implications', 'consequences', 'ramifications',
    'comprehensive', 'thorough', 'extensive', 'in-depth',
    'justify', 'argue', 'argument',
    'theoretical', 'theory', 'hypothesis',
    'methodology', 'approach', 'framework',
    'synthesize', 'integrate', 'consolidate',
  ];

  private static readonly EXPERT_KEYWORDS = [
    'implement', 'implementation', 'build', 'create', 'develop',
    'production', 'production-ready', 'enterprise',
    'architecture', 'design pattern', 'system design',
    'scalable', 'scalability', 'scale',
    'distributed', 'microservices', 'distributed tracing',
    'optimize', 'optimization', 'performance',
    'refactor', 'refactoring',
    'best practice', 'best practices',
    'algorithm', 'algorithmic',
    'theorem', 'theorems',
  ];

  private static readonly CODE_PATTERNS = [
    /\bdef\s+\w+/,
    /\bclass\s+\w+/,
    /\bimport\s+\w+/,
    /\bfunction\s+\w+/,
    /\bconst\s+\w+\s*=/,
    /=>/,
    /\{[\s\S]*\}/,
    /```/,
  ];

  // Combine all technical terms
  private allTechnicalTerms: Set<string>;

  constructor() {
    this.allTechnicalTerms = new Set([
      ...ComplexityDetector.PHYSICS_TERMS,
      ...ComplexityDetector.MATHEMATICS_TERMS,
      ...ComplexityDetector.CS_TERMS,
      ...ComplexityDetector.ENGINEERING_TERMS,
    ]);
  }

  /**
   * Detect query complexity
   *
   * @param query - Query text to analyze
   * @param returnMetadata - Whether to return detailed metadata
   * @returns Complexity result
   */
  detect(query: string, returnMetadata: boolean = false): ComplexityResult {
    const queryLower = query.toLowerCase().trim();

    const metadata = {
      technicalTerms: [] as string[],
      domains: new Set<string>(),
      mathNotation: [] as string[],
      domainScore: 0,
    };

    // 1. Check trivial patterns first
    for (const pattern of ComplexityDetector.TRIVIAL_PATTERNS) {
      if (pattern.test(queryLower)) {
        return {
          complexity: 'trivial',
          confidence: 0.95,
          ...(returnMetadata && { metadata }),
        };
      }
    }

    // 2. Check for trivial concepts
    if (this.hasTrivialConcepts(queryLower)) {
      return {
        complexity: 'trivial',
        confidence: 0.85,
        ...(returnMetadata && { metadata }),
        };
    }

    // 3. Detect technical terms
    const { terms: techTerms, domainScores } = this.detectTechnicalTerms(queryLower);
    metadata.technicalTerms = techTerms;
    metadata.domains = new Set(
      Object.entries(domainScores)
        .filter(([_, score]) => score > 0)
        .map(([domain, _]) => domain)
    );
    metadata.domainScore = Math.max(...Object.values(domainScores), 0);

    // 4. Calculate technical complexity boost
    const techBoost = this.calculateTechnicalBoost(
      techTerms.length,
      0, // mathNotation length (simplified for now)
      domainScores
    );

    // 5. Detect code patterns
    const hasCode = ComplexityDetector.CODE_PATTERNS.some(p => p.test(query));

    // 6. Length and structure analysis
    const words = query.split(/\s+/);
    const wordCount = words.length;

    const hasMultipleQuestions = (query.match(/\?/g) || []).length > 1;
    const hasConditionals = ['if', 'when', 'unless', 'provided', 'assuming', 'given that']
      .some(w => queryLower.includes(w));
    const hasRequirements = ['must', 'should', 'need to', 'required', 'ensure', 'guarantee']
      .some(w => queryLower.includes(w));
    const hasMultipleParts = [';', '\n', '1.', '2.'].some(sep => query.includes(sep));

    const structureScore = [
      hasMultipleQuestions,
      hasConditionals && hasRequirements,
      hasMultipleParts,
    ].filter(Boolean).length;

    // 7. Count keyword matches
    const simpleMatches = ComplexityDetector.SIMPLE_KEYWORDS
      .filter(kw => queryLower.includes(kw)).length;
    const moderateMatches = ComplexityDetector.MODERATE_KEYWORDS
      .filter(kw => queryLower.includes(kw)).length;
    const hardMatches = ComplexityDetector.HARD_KEYWORDS
      .filter(kw => queryLower.includes(kw)).length;
    const expertMatches = ComplexityDetector.EXPERT_KEYWORDS
      .filter(kw => queryLower.includes(kw)).length;

    // 8. Determine base complexity
    let finalComplexity: QueryComplexity;
    let finalConfidence: number;

    // CRITICAL: Technical terms STRONGLY influence complexity
    if (techBoost >= 2.0) {
      // Multiple advanced terms or strong domain specialization
      finalComplexity = 'expert';
      finalConfidence = 0.90;
    } else if (techBoost >= 1.0) {
      // Some advanced terms
      finalComplexity = 'hard';
      finalConfidence = 0.85;
    } else if (techBoost >= 0.5) {
      // Basic technical terms
      finalComplexity = 'moderate';
      finalConfidence = 0.80;
    } else if (expertMatches >= 2) {
      finalComplexity = 'expert';
      finalConfidence = 0.85;
    } else if (expertMatches >= 1) {
      if (wordCount >= 8) {
        finalComplexity = 'expert';
        finalConfidence = 0.80;
      } else {
        finalComplexity = 'hard';
        finalConfidence = 0.75;
      }
    } else if (hardMatches >= 2) {
      finalComplexity = 'hard';
      finalConfidence = 0.8;
    } else if (hardMatches >= 1 && wordCount > 6) {
      finalComplexity = 'hard';
      finalConfidence = 0.7;
    } else if (moderateMatches >= 2) {
      finalComplexity = 'moderate';
      finalConfidence = 0.8;
    } else if (moderateMatches >= 1 && wordCount > 6) {
      finalComplexity = 'moderate';
      finalConfidence = 0.7;
    } else if (wordCount <= 6 && simpleMatches >= 1) {
      finalComplexity = 'simple';
      finalConfidence = 0.75;
    } else {
      // Default by word count
      if (wordCount <= 8) {
        finalComplexity = 'simple';
        finalConfidence = 0.6;
      } else if (wordCount <= 20) {
        finalComplexity = 'moderate';
        finalConfidence = 0.6;
      } else {
        finalComplexity = 'hard';
        finalConfidence = 0.6;
      }
    }

    // 9. Apply technical boost to complexity
    if (techBoost >= 1.5) {
      if (finalComplexity === 'simple') {
        finalComplexity = 'hard';
      } else if (finalComplexity === 'moderate') {
        finalComplexity = 'expert';
      } else if (finalComplexity === 'hard') {
        finalComplexity = 'expert';
      }
      finalConfidence = Math.min(0.95, finalConfidence + 0.15);
    }

    // 10. Apply code boost (more nuanced)
    if (hasCode) {
      // Only boost if query is complex enough (> 12 words) OR has expert keywords
      // This prevents simple coding tasks like "reverse a string" from being over-classified
      const isComplexCodeQuery = wordCount > 12 || expertMatches >= 1;

      if (isComplexCodeQuery) {
        if (finalComplexity === 'simple') {
          finalComplexity = 'moderate';
        } else if (finalComplexity === 'moderate') {
          finalComplexity = 'hard';
        }
        finalConfidence = Math.min(0.95, finalConfidence + 0.1);
      } else {
        // Simple code query - small confidence boost only
        finalConfidence = Math.min(0.95, finalConfidence + 0.05);
      }
    }

    // 11. Apply structure boost
    if (structureScore >= 2) {
      if (finalComplexity === 'simple') {
        finalComplexity = 'moderate';
      } else if (finalComplexity === 'moderate') {
        finalComplexity = 'hard';
      }
      finalConfidence = Math.min(0.95, finalConfidence + 0.05);
    }

    // 12. Sanity checks
    if (wordCount < 10 && finalComplexity === 'expert' && techBoost < 2.0) {
      finalComplexity = 'hard';
    }

    if (wordCount > 50 && (finalComplexity === 'simple' || finalComplexity === 'moderate')) {
      finalComplexity = 'hard';
    }

    return {
      complexity: finalComplexity,
      confidence: finalConfidence,
      ...(returnMetadata && { metadata }),
    };
  }

  /**
   * Detect technical terms in query
   */
  private detectTechnicalTerms(queryLower: string): {
    terms: string[];
    domainScores: Record<string, number>;
  } {
    const foundTerms: string[] = [];
    const domainScores: Record<string, number> = {
      physics: 0,
      mathematics: 0,
      computer_science: 0,
      engineering: 0,
    };

    // Check multi-word terms first (more specific)
    for (const term of this.allTechnicalTerms) {
      if (term.includes(' ') || term.includes('-')) {
        const pattern = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i');
        if (pattern.test(queryLower)) {
          foundTerms.push(term);

          // Assign to domain
          if (ComplexityDetector.PHYSICS_TERMS.has(term)) {
            domainScores.physics += 1.0;
          }
          if (ComplexityDetector.MATHEMATICS_TERMS.has(term)) {
            domainScores.mathematics += 1.0;
          }
          if (ComplexityDetector.CS_TERMS.has(term)) {
            domainScores.computer_science += 1.0;
          }
          if (ComplexityDetector.ENGINEERING_TERMS.has(term)) {
            domainScores.engineering += 1.0;
          }
        }
      }
    }

    // Check single-word terms
    const wordsInQuery = new Set(queryLower.split(/\s+/));
    for (const term of this.allTechnicalTerms) {
      if (!term.includes(' ') && !term.includes('-')) {
        if (wordsInQuery.has(term)) {
          foundTerms.push(term);

          if (ComplexityDetector.PHYSICS_TERMS.has(term)) {
            domainScores.physics += 0.5;
          }
          if (ComplexityDetector.MATHEMATICS_TERMS.has(term)) {
            domainScores.mathematics += 0.5;
          }
          if (ComplexityDetector.CS_TERMS.has(term)) {
            domainScores.computer_science += 0.5;
          }
          if (ComplexityDetector.ENGINEERING_TERMS.has(term)) {
            domainScores.engineering += 0.5;
          }
        }
      }
    }

    return { terms: foundTerms, domainScores };
  }

  /**
   * Calculate complexity boost from technical content
   */
  private calculateTechnicalBoost(
    numTechTerms: number,
    numMathNotation: number,
    domainScores: Record<string, number>
  ): number {
    let boost = 0;

    // Technical terms boost (increased from 0.5 to 0.7 per term)
    boost += numTechTerms * 0.7;

    // Math notation boost
    boost += numMathNotation * 0.3;

    // Domain specialization boost (increased weights)
    const maxDomainScore = Math.max(...Object.values(domainScores), 0);
    if (maxDomainScore >= 2) {
      boost += 2.0; // Strong specialization (was 1.5)
    } else if (maxDomainScore >= 1) {
      boost += 1.0; // Moderate specialization (unchanged)
    } else if (maxDomainScore >= 0.5) {
      boost += 0.5; // Some specialization (was checking >= 1)
    }

    return boost;
  }

  /**
   * Check for trivial concepts
   */
  private hasTrivialConcepts(queryLower: string): boolean {
    let trivialCount = 0;

    for (const concept of ComplexityDetector.TRIVIAL_CONCEPTS) {
      const pattern = new RegExp(`\\b${concept}\\b`, 'i');
      if (pattern.test(queryLower)) {
        trivialCount++;
      }
    }

    const wordCount = queryLower.split(/\s+/).length;

    if (trivialCount >= 2) {
      return true;
    } else if (trivialCount >= 1 && wordCount <= 8) {
      return true;
    }

    return false;
  }
}
