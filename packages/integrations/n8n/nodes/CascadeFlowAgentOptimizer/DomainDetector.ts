export type DomainType =
	| 'CODE'
	| 'MATH'
	| 'DATA'
	| 'MEDICAL'
	| 'LEGAL'
	| 'GENERAL';

export interface DomainDetectionResult {
	domain: DomainType;
	confidence: number;
	keywords: string[];
	reasoning: string;
}

export class DomainDetector {
	private static readonly DOMAIN_KEYWORDS = {
		CODE: {
			veryStrong: ['function', 'class', 'import', 'const', 'let', 'var', 'def', 'async', 'await'],
			strong: ['code', 'programming', 'bug', 'debug', 'compile', 'syntax', 'algorithm', 'api', 'library'],
			moderate: ['software', 'developer', 'application', 'script', 'method', 'parameter', 'variable'],
		},
		MATH: {
			veryStrong: ['equation', 'integral', 'derivative', 'matrix', 'vector', 'theorem', 'proof'],
			strong: ['calculate', 'formula', 'solve', 'mathematics', 'algebra', 'calculus', 'geometry'],
			moderate: ['number', 'sum', 'average', 'percentage', 'ratio', 'probability'],
		},
		DATA: {
			veryStrong: ['dataframe', 'pandas', 'numpy', 'sql', 'query', 'dataset', 'csv', 'json'],
			strong: ['data', 'analysis', 'statistics', 'visualization', 'chart', 'graph', 'database'],
			moderate: ['table', 'column', 'row', 'filter', 'sort', 'aggregate', 'merge'],
		},
		MEDICAL: {
			veryStrong: ['diagnosis', 'treatment', 'patient', 'symptom', 'medication', 'disease'],
			strong: ['medical', 'health', 'clinical', 'doctor', 'hospital', 'therapy'],
			moderate: ['pain', 'fever', 'infection', 'chronic', 'acute'],
		},
		LEGAL: {
			veryStrong: ['contract', 'statute', 'regulation', 'lawsuit', 'plaintiff', 'defendant'],
			strong: ['legal', 'law', 'court', 'attorney', 'clause', 'liability', 'compliance'],
			moderate: ['agreement', 'terms', 'policy', 'rights', 'obligation'],
		},
	};

	static detectDomain(query: string): DomainDetectionResult {
		const lowerQuery = query.toLowerCase();
		const scores: Record<DomainType, number> = {
			CODE: 0,
			MATH: 0,
			DATA: 0,
			MEDICAL: 0,
			LEGAL: 0,
			GENERAL: 0,
		};

		const matchedKeywords: Record<DomainType, string[]> = {
			CODE: [],
			MATH: [],
			DATA: [],
			MEDICAL: [],
			LEGAL: [],
			GENERAL: [],
		};

		for (const [domain, keywords] of Object.entries(this.DOMAIN_KEYWORDS)) {
			for (const keyword of keywords.veryStrong) {
				if (lowerQuery.includes(keyword)) {
					scores[domain as DomainType] += 3.0;
					matchedKeywords[domain as DomainType].push(keyword);
				}
			}

			for (const keyword of keywords.strong) {
				if (lowerQuery.includes(keyword)) {
					scores[domain as DomainType] += 2.0;
					matchedKeywords[domain as DomainType].push(keyword);
				}
			}

			for (const keyword of keywords.moderate) {
				if (lowerQuery.includes(keyword)) {
					scores[domain as DomainType] += 1.0;
					matchedKeywords[domain as DomainType].push(keyword);
				}
			}
		}

		if (this.hasCodePatterns(query)) {
			scores.CODE += 5.0;
			matchedKeywords.CODE.push('code-pattern');
		}

		if (this.hasMathNotation(query)) {
			scores.MATH += 5.0;
			matchedKeywords.MATH.push('math-notation');
		}

		if (this.hasDataPatterns(query)) {
			scores.DATA += 3.0;
			matchedKeywords.DATA.push('data-pattern');
		}

		let maxScore = 0;
		let detectedDomain: DomainType = 'GENERAL';

		for (const [domain, score] of Object.entries(scores)) {
			if (score > maxScore && domain !== 'GENERAL') {
				maxScore = score;
				detectedDomain = domain as DomainType;
			}
		}

		if (maxScore < 2.0) {
			detectedDomain = 'GENERAL';
		}

		const confidence = Math.min(maxScore / 10, 1.0);

		const reasoning = this.generateReasoning(
			detectedDomain,
			matchedKeywords[detectedDomain],
			confidence
		);

		return {
			domain: detectedDomain,
			confidence,
			keywords: matchedKeywords[detectedDomain],
			reasoning,
		};
	}

	private static hasCodePatterns(query: string): boolean {
		const codePatterns = [
			/```[\s\S]*?```/,
			/`[^`]+`/,
			/function\s+\w+\s*\(/,
			/class\s+\w+/,
			/def\s+\w+\s*\(/,
			/import\s+[\w.]+/,
			/from\s+\w+\s+import/,
			/\bconst\s+\w+\s*=/,
			/\blet\s+\w+\s*=/,
			/\bvar\s+\w+\s*=/,
			/->\s*\w+/,
			/=>\s*[{(]/,
		];

		return codePatterns.some(pattern => pattern.test(query));
	}

	private static hasMathNotation(query: string): boolean {
		const mathPatterns = [
			/\b(?:integral|derivative|differential|equation)\b/i,
			/\b(?:matrix|vector|tensor)\b/i,
			/[∫∑∏∂∇∆]/,
			/\b[a-z]\^[0-9]/,
			/√|∞|≤|≥|≠|≈|±/,
			/\bsin\(|cos\(|tan\(|log\(/,
		];

		return mathPatterns.some(pattern => pattern.test(query));
	}

	private static hasDataPatterns(query: string): boolean {
		const dataPatterns = [
			/SELECT\s+.*FROM/i,
			/\bWHERE\b.*\bAND\b/i,
			/\bGROUP\s+BY\b/i,
			/\bJOIN\b.*\bON\b/i,
			/\.csv|\.json|\.xlsx/i,
			/dataframe|pd\.|np\./i,
		];

		return dataPatterns.some(pattern => pattern.test(query));
	}

	private static generateReasoning(
		domain: DomainType,
		keywords: string[],
		confidence: number
	): string {
		if (domain === 'GENERAL') {
			return 'No strong domain indicators detected, classified as general query';
		}

		const keywordList = keywords.length > 0
			? keywords.slice(0, 5).join(', ')
			: 'pattern matching';

		return `Detected ${domain} domain (${(confidence * 100).toFixed(0)}% confidence) based on: ${keywordList}`;
	}

	static shouldUseDomainSpecialist(detection: DomainDetectionResult): boolean {
		return detection.domain !== 'GENERAL' && detection.confidence >= 0.5;
	}

	static getDomainModelRecommendation(domain: DomainType): string | null {
		const recommendations: Record<DomainType, string | null> = {
			CODE: 'deepseek-coder or gpt-4o',
			MATH: 'o3-mini or claude-3-5-sonnet',
			DATA: 'gpt-4o or claude-3-5-sonnet',
			MEDICAL: 'claude-3-opus or gpt-4o',
			LEGAL: 'claude-3-opus or gpt-4o',
			GENERAL: null,
		};

		return recommendations[domain];
	}
}
