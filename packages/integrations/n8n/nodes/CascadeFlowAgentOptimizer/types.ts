export interface CostMetrics {
	totalCost: number;
	draftCost: number;
	verifierCost: number;
	costSaved: number;
	savingsPercentage: number;
	modelUsed: 'drafter' | 'verifier' | 'domain_specialist';
	tokensUsed: {
		input: number;
		output: number;
		total: number;
	};
}

export interface QualityMetrics {
	confidence: number;
	qualityScore: number;
	validationMethod: 'heuristic' | 'logprobs' | 'semantic';
	alignmentScore?: number;
	passed: boolean;
	reason?: string;
}

export interface PerformanceMetrics {
	latencyMs: number;
	drafterLatencyMs?: number;
	verifierLatencyMs?: number;
}

export interface CascadeMetadata {
	flow: 'drafter_accepted' | 'escalated_to_verifier' | 'error_fallback' | 'direct_verifier' | 'domain_specialist';
	cost: CostMetrics;
	quality: QualityMetrics;
	performance: PerformanceMetrics;
	requestCount: number;
	acceptanceRate: number;
}

export interface CostTrackingOutput {
	timestamp: string;
	requestId: string;
	query: string;
	response: string;
	cost: CostMetrics;
	quality: QualityMetrics;
	performance: PerformanceMetrics;
	metadata: {
		flow: string;
		modelUsed: string;
		acceptanceRate: number;
		totalRequests: number;
	};
}

export type RoutingStrategy = 'always_cascade' | 'complexity_based' | 'domain_aware' | 'adaptive';

export type DomainDetectionMethod = 'rule_based' | 'ml_semantic' | 'hybrid';

export type ToolExecutionStrategy = 'always_cascade' | 'complexity_based' | 'direct_verifier';

export type LoggingLevel = 'none' | 'basic' | 'detailed' | 'debug';

export interface NodeConfig {
	qualityThreshold: number;
	routingStrategy: RoutingStrategy;
	enableDomainRouting: boolean;
	domainDetectionMethod: DomainDetectionMethod;
	enableTools: boolean;
	toolExecutionStrategy: ToolExecutionStrategy;
	enableMemory: boolean;
	enableCostTracking: boolean;
	costBudgetLimit: number;
	enableReasoningModels: boolean;
	reasoningEffort: 'low' | 'medium' | 'high';
	enableAdaptiveThreshold: boolean;
	loggingLevel: LoggingLevel;
}

export interface ModelPricing {
	inputCostPer1M: number;
	outputCostPer1M: number;
}

export const DEFAULT_MODEL_PRICING: Record<string, ModelPricing> = {
	// OpenAI
	'gpt-4o': { inputCostPer1M: 2.50, outputCostPer1M: 10.00 },
	'gpt-4o-mini': { inputCostPer1M: 0.150, outputCostPer1M: 0.600 },
	'gpt-4-turbo': { inputCostPer1M: 10.00, outputCostPer1M: 30.00 },
	'gpt-4': { inputCostPer1M: 30.00, outputCostPer1M: 60.00 },
	'gpt-3.5-turbo': { inputCostPer1M: 0.50, outputCostPer1M: 1.50 },
	'o1': { inputCostPer1M: 15.00, outputCostPer1M: 60.00 },
	'o1-mini': { inputCostPer1M: 3.00, outputCostPer1M: 12.00 },
	'o3-mini': { inputCostPer1M: 1.10, outputCostPer1M: 4.40 },

	// Anthropic
	'claude-3-5-sonnet-20241022': { inputCostPer1M: 3.00, outputCostPer1M: 15.00 },
	'claude-3-5-haiku-20241022': { inputCostPer1M: 0.80, outputCostPer1M: 4.00 },
	'claude-3-opus-20240229': { inputCostPer1M: 15.00, outputCostPer1M: 75.00 },
	'claude-3-sonnet-20240229': { inputCostPer1M: 3.00, outputCostPer1M: 15.00 },
	'claude-3-haiku-20240307': { inputCostPer1M: 0.25, outputCostPer1M: 1.25 },

	// Fallback estimates for unknown models
	default_cheap: { inputCostPer1M: 0.50, outputCostPer1M: 1.50 },
	default_expensive: { inputCostPer1M: 5.00, outputCostPer1M: 15.00 },
};
