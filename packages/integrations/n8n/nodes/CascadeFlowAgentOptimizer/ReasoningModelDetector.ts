import { BaseChatModel } from '@langchain/core/language_models/chat_models';

export interface ReasoningModelConfig {
	isReasoningModel: boolean;
	modelType: 'openai_o1' | 'openai_o3' | 'anthropic_extended_thinking' | 'deepseek_r1' | 'standard';
	supportsSystemMessages: boolean;
	reasoningEffort?: 'low' | 'medium' | 'high';
	budgetTokens?: number;
	trackThinkingTokens: boolean;
}

export class ReasoningModelDetector {
	private static REASONING_MODEL_PATTERNS = {
		openai_o1: ['o1-preview', 'o1-mini', 'o1-2024', 'o1-', 'o1'],
		openai_o3: ['o3-mini', 'o3-2024', 'o3-', 'o3'],
		anthropic_extended_thinking: ['claude-3-7', 'claude-3.7'],
		deepseek_r1: ['deepseek-r1', 'deepseek-reasoner'],
	};

	static detectReasoningModel(model: BaseChatModel): ReasoningModelConfig {
		const modelName = this.getModelName(model).toLowerCase();

		if (this.matchesPattern(modelName, this.REASONING_MODEL_PATTERNS.openai_o1)) {
			return {
				isReasoningModel: true,
				modelType: 'openai_o1',
				supportsSystemMessages: false,
				trackThinkingTokens: true,
			};
		}

		if (this.matchesPattern(modelName, this.REASONING_MODEL_PATTERNS.openai_o3)) {
			return {
				isReasoningModel: true,
				modelType: 'openai_o3',
				supportsSystemMessages: false,
				trackThinkingTokens: true,
			};
		}

		if (this.matchesPattern(modelName, this.REASONING_MODEL_PATTERNS.anthropic_extended_thinking)) {
			return {
				isReasoningModel: true,
				modelType: 'anthropic_extended_thinking',
				supportsSystemMessages: true,
				trackThinkingTokens: true,
			};
		}

		if (this.matchesPattern(modelName, this.REASONING_MODEL_PATTERNS.deepseek_r1)) {
			return {
				isReasoningModel: true,
				modelType: 'deepseek_r1',
				supportsSystemMessages: true,
				trackThinkingTokens: true,
			};
		}

		return {
			isReasoningModel: false,
			modelType: 'standard',
			supportsSystemMessages: true,
			trackThinkingTokens: false,
		};
	}

	private static matchesPattern(modelName: string, patterns: string[]): boolean {
		return patterns.some(pattern => modelName.includes(pattern.toLowerCase()));
	}

	private static getModelName(model: any): string {
		return model.modelName || model.model || model._modelName || 'unknown';
	}

	static applyReasoningConfig(
		model: BaseChatModel,
		config: ReasoningModelConfig,
		userReasoningEffort?: 'low' | 'medium' | 'high',
		userBudgetTokens?: number
	): BaseChatModel {
		if (!config.isReasoningModel) {
			return model;
		}

		const modelWithConfig = { ...model } as any;

		if (config.modelType === 'openai_o1' || config.modelType === 'openai_o3') {
			if (userReasoningEffort) {
				modelWithConfig.reasoning_effort = userReasoningEffort;
			}
		}

		if (config.modelType === 'anthropic_extended_thinking') {
			if (userBudgetTokens) {
				modelWithConfig.thinking = {
					type: 'enabled',
					budget_tokens: userBudgetTokens,
				};
			}
		}

		return modelWithConfig as BaseChatModel;
	}

	static shouldNeverUseDrafter(model: BaseChatModel): boolean {
		const config = this.detectReasoningModel(model);
		return config.isReasoningModel;
	}

	static getReasoningEffortRecommendation(queryComplexity: 'simple' | 'moderate' | 'complex' | 'expert'): 'low' | 'medium' | 'high' {
		switch (queryComplexity) {
			case 'simple':
			case 'moderate':
				return 'low';
			case 'complex':
				return 'medium';
			case 'expert':
				return 'high';
			default:
				return 'medium';
		}
	}
}
