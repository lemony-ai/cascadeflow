export type ComplexityLevel = 'trivial' | 'simple' | 'moderate' | 'complex' | 'expert';

export interface ComplexityAnalysis {
	level: ComplexityLevel;
	score: number;
	reasoning: string;
	shouldCascade: boolean;
	indicators: {
		technicalTerms: number;
		mathNotation: number;
		codeSnippets: number;
		questionComplexity: number;
		domainSpecific: boolean;
	};
}

export class ComplexityAnalyzer {
	private static TECHNICAL_TERMS = [
		'algorithm', 'complexity', 'optimization', 'architecture', 'implementation',
		'asynchronous', 'concurrency', 'distributed', 'scalability', 'performance',
		'security', 'encryption', 'authentication', 'authorization', 'protocol',
		'framework', 'library', 'dependency', 'compilation', 'interpreter',
		'database', 'transaction', 'normalization', 'indexing', 'query',
		'neural', 'machine learning', 'deep learning', 'gradient', 'backpropagation',
		'quantum', 'statistical', 'probability', 'theorem', 'hypothesis',
	];

	private static MATH_PATTERNS = [
		/\b(?:integral|derivative|differential|equation|matrix|vector|tensor)\b/i,
		/\b(?:polynomial|logarithm|exponential|trigonometric|calculus)\b/i,
		/\b(?:proof|lemma|corollary|axiom|conjecture)\b/i,
		/[∫∑∏∂∇∆]/,
		/\b[a-z]\^[0-9]/,
		/√|∞|≤|≥|≠|≈/,
	];

	private static CODE_PATTERNS = [
		/```[\s\S]*?```/,
		/`[^`]+`/,
		/function\s+\w+\s*\(/,
		/class\s+\w+/,
		/def\s+\w+\s*\(/,
		/import\s+\w+/,
		/from\s+\w+\s+import/,
		/const\s+\w+\s*=/,
		/let\s+\w+\s*=/,
		/var\s+\w+\s*=/,
	];

	static analyzeComplexity(query: string): ComplexityAnalysis {
		const lowerQuery = query.toLowerCase();
		const wordCount = query.split(/\s+/).length;

		const technicalTerms = this.countTechnicalTerms(lowerQuery);
		const mathNotation = this.detectMathNotation(query);
		const codeSnippets = this.detectCodeSnippets(query);
		const questionComplexity = this.analyzeQuestionComplexity(query, wordCount);
		const domainSpecific = this.isDomainSpecific(lowerQuery);

		let score = 0;

		score += Math.min(technicalTerms * 10, 30);
		score += mathNotation ? 25 : 0;
		score += codeSnippets ? 20 : 0;
		score += questionComplexity;
		score += domainSpecific ? 15 : 0;

		score = Math.min(score, 100);

		const level = this.scoreToLevel(score);
		const shouldCascade = this.shouldCascadeForLevel(level);

		return {
			level,
			score,
			reasoning: this.generateReasoning(level, {
				technicalTerms,
				mathNotation,
				codeSnippets,
				questionComplexity,
				domainSpecific,
			}),
			shouldCascade,
			indicators: {
				technicalTerms,
				mathNotation: mathNotation ? 1 : 0,
				codeSnippets: codeSnippets ? 1 : 0,
				questionComplexity,
				domainSpecific,
			},
		};
	}

	private static countTechnicalTerms(query: string): number {
		return this.TECHNICAL_TERMS.filter(term => query.includes(term)).length;
	}

	private static detectMathNotation(query: string): boolean {
		return this.MATH_PATTERNS.some(pattern => pattern.test(query));
	}

	private static detectCodeSnippets(query: string): boolean {
		return this.CODE_PATTERNS.some(pattern => pattern.test(query));
	}

	private static analyzeQuestionComplexity(query: string, wordCount: number): number {
		let complexity = 0;

		if (wordCount > 100) complexity += 20;
		else if (wordCount > 50) complexity += 10;
		else if (wordCount > 20) complexity += 5;

		const multiPart = (query.match(/\?/g) || []).length > 1;
		if (multiPart) complexity += 15;

		const hasConstraints = /\b(?:must|should|need to|have to|require|constraint)\b/i.test(query);
		if (hasConstraints) complexity += 10;

		return complexity;
	}

	private static isDomainSpecific(query: string): boolean {
		const domainKeywords = [
			'medical', 'legal', 'financial', 'scientific', 'engineering',
			'diagnosis', 'treatment', 'contract', 'statute', 'regulation',
			'investment', 'portfolio', 'derivatives', 'research', 'experiment',
		];

		return domainKeywords.some(keyword => query.includes(keyword));
	}

	private static scoreToLevel(score: number): ComplexityLevel {
		if (score >= 80) return 'expert';
		if (score >= 60) return 'complex';
		if (score >= 40) return 'moderate';
		if (score >= 20) return 'simple';
		return 'trivial';
	}

	private static shouldCascadeForLevel(level: ComplexityLevel): boolean {
		return level === 'trivial' || level === 'simple' || level === 'moderate';
	}

	private static generateReasoning(level: ComplexityLevel, indicators: any): string {
		const reasons: string[] = [];

		if (indicators.technicalTerms > 0) {
			reasons.push(`${indicators.technicalTerms} technical term(s)`);
		}
		if (indicators.mathNotation > 0) {
			reasons.push('mathematical notation detected');
		}
		if (indicators.codeSnippets > 0) {
			reasons.push('code snippets present');
		}
		if (indicators.domainSpecific) {
			reasons.push('domain-specific content');
		}

		const reasoningText = reasons.length > 0 ? reasons.join(', ') : 'basic query structure';

		return `Classified as ${level} based on: ${reasoningText}`;
	}

	static recommendStrategy(complexity: ComplexityAnalysis): 'cascade' | 'direct_verifier' {
		if (complexity.level === 'expert' || complexity.level === 'complex') {
			return 'direct_verifier';
		}
		return 'cascade';
	}
}
