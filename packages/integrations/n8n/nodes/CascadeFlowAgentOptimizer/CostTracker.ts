import { BaseMessage } from '@langchain/core/messages';
import { ChatResult } from '@langchain/core/outputs';
import { CostMetrics, ModelPricing, DEFAULT_MODEL_PRICING } from './types';

export class CostTracker {
	private totalRequests: number = 0;
	private drafterAccepted: number = 0;
	private verifierUsed: number = 0;
	private totalCost: number = 0;
	private totalSaved: number = 0;

	constructor(private enableTracking: boolean = true) {}

	getModelName(model: any): string {
		return model.modelName || model.model || 'unknown';
	}

	getPricing(modelName: string): ModelPricing {
		const normalized = modelName.toLowerCase();

		for (const [key, pricing] of Object.entries(DEFAULT_MODEL_PRICING)) {
			if (normalized.includes(key.toLowerCase())) {
				return pricing;
			}
		}

		if (normalized.includes('mini') || normalized.includes('haiku') || normalized.includes('3.5')) {
			return DEFAULT_MODEL_PRICING.default_cheap;
		}

		return DEFAULT_MODEL_PRICING.default_expensive;
	}

	estimateTokens(messages: BaseMessage[]): { input: number; output: number } {
		const inputText = messages.map(m => m.content.toString()).join(' ');
		const inputTokens = Math.ceil(inputText.length / 4);

		return {
			input: inputTokens,
			output: 0,
		};
	}

	calculateTokensFromResult(result: ChatResult): { input: number; output: number } {
		const outputText = result.generations[0]?.text || '';
		const outputTokens = Math.ceil(outputText.length / 4);

		const usageMetadata = (result as any).llmOutput?.tokenUsage;

		if (usageMetadata) {
			return {
				input: usageMetadata.promptTokens || usageMetadata.input_tokens || 0,
				output: usageMetadata.completionTokens || usageMetadata.output_tokens || outputTokens,
			};
		}

		return {
			input: 0,
			output: outputTokens,
		};
	}

	calculateCost(
		drafterModel: any,
		verifierModel: any,
		messages: BaseMessage[],
		drafterResult?: ChatResult,
		verifierResult?: ChatResult,
		flow: 'drafter_accepted' | 'escalated_to_verifier' | 'error_fallback' = 'drafter_accepted'
	): CostMetrics {
		if (!this.enableTracking) {
			return this.getEmptyCostMetrics();
		}

		this.totalRequests++;

		const drafterPricing = this.getPricing(this.getModelName(drafterModel));
		const verifierPricing = this.getPricing(this.getModelName(verifierModel));

		let draftCost = 0;
		let verifierCost = 0;
		let totalInputTokens = 0;
		let totalOutputTokens = 0;

		if (drafterResult) {
			const tokens = this.calculateTokensFromResult(drafterResult);
			const estimatedInput = this.estimateTokens(messages);
			const inputTokens = tokens.input || estimatedInput.input;
			const outputTokens = tokens.output;

			draftCost = (inputTokens / 1_000_000) * drafterPricing.inputCostPer1M +
			            (outputTokens / 1_000_000) * drafterPricing.outputCostPer1M;

			totalInputTokens += inputTokens;
			totalOutputTokens += outputTokens;
		}

		if (verifierResult) {
			const tokens = this.calculateTokensFromResult(verifierResult);
			const estimatedInput = this.estimateTokens(messages);
			const inputTokens = tokens.input || estimatedInput.input;
			const outputTokens = tokens.output;

			verifierCost = (inputTokens / 1_000_000) * verifierPricing.inputCostPer1M +
			               (outputTokens / 1_000_000) * verifierPricing.outputCostPer1M;

			totalInputTokens += inputTokens;
			totalOutputTokens += outputTokens;
		}

		const totalCost = draftCost + verifierCost;

		const estimatedVerifierOnlyCost = (() => {
			const estimatedInput = this.estimateTokens(messages);
			const estimatedOutput = verifierResult ?
				this.calculateTokensFromResult(verifierResult).output :
				drafterResult ? this.calculateTokensFromResult(drafterResult).output : 100;

			return (estimatedInput.input / 1_000_000) * verifierPricing.inputCostPer1M +
			       (estimatedOutput / 1_000_000) * verifierPricing.outputCostPer1M;
		})();

		const costSaved = Math.max(0, estimatedVerifierOnlyCost - totalCost);
		const savingsPercentage = estimatedVerifierOnlyCost > 0
			? (costSaved / estimatedVerifierOnlyCost) * 100
			: 0;

		if (flow === 'drafter_accepted') {
			this.drafterAccepted++;
		} else {
			this.verifierUsed++;
		}

		this.totalCost += totalCost;
		this.totalSaved += costSaved;

		return {
			totalCost,
			draftCost,
			verifierCost,
			costSaved,
			savingsPercentage,
			modelUsed: flow === 'drafter_accepted' ? 'drafter' : 'verifier',
			tokensUsed: {
				input: totalInputTokens,
				output: totalOutputTokens,
				total: totalInputTokens + totalOutputTokens,
			},
		};
	}

	getAcceptanceRate(): number {
		if (this.totalRequests === 0) return 0;
		return (this.drafterAccepted / this.totalRequests) * 100;
	}

	getStatistics() {
		return {
			totalRequests: this.totalRequests,
			drafterAccepted: this.drafterAccepted,
			verifierUsed: this.verifierUsed,
			acceptanceRate: this.getAcceptanceRate(),
			totalCost: this.totalCost,
			totalSaved: this.totalSaved,
			averageCostPerRequest: this.totalRequests > 0 ? this.totalCost / this.totalRequests : 0,
			averageSavingsPerRequest: this.totalRequests > 0 ? this.totalSaved / this.totalRequests : 0,
		};
	}

	reset() {
		this.totalRequests = 0;
		this.drafterAccepted = 0;
		this.verifierUsed = 0;
		this.totalCost = 0;
		this.totalSaved = 0;
	}

	private getEmptyCostMetrics(): CostMetrics {
		return {
			totalCost: 0,
			draftCost: 0,
			verifierCost: 0,
			costSaved: 0,
			savingsPercentage: 0,
			modelUsed: 'drafter',
			tokensUsed: {
				input: 0,
				output: 0,
				total: 0,
			},
		};
	}
}
