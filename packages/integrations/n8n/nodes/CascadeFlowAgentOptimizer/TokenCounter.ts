import { BaseMessage } from '@langchain/core/messages';
import { ChatResult } from '@langchain/core/outputs';

export interface TokenUsage {
	inputTokens: number;
	outputTokens: number;
	totalTokens: number;
	thinkingTokens?: number;
	cachingTokens?: number;
}

export interface DetailedTokenBreakdown {
	messages: TokenUsage;
	draft?: TokenUsage;
	verification?: TokenUsage;
	total: TokenUsage;
	estimationMethod: 'metadata' | 'tiktoken' | 'heuristic';
}

export class TokenCounter {
	static countMessageTokens(messages: BaseMessage[]): number {
		const totalText = messages.map(m => m.content.toString()).join('');
		return this.estimateTokens(totalText);
	}

	static extractTokenUsage(result: ChatResult, fallbackText?: string): TokenUsage {
		const metadata = (result as any).llmOutput || {};

		if (metadata.tokenUsage) {
			return {
				inputTokens: metadata.tokenUsage.promptTokens || metadata.tokenUsage.input_tokens || 0,
				outputTokens: metadata.tokenUsage.completionTokens || metadata.tokenUsage.output_tokens || 0,
				totalTokens: metadata.tokenUsage.totalTokens || metadata.tokenUsage.total_tokens || 0,
				thinkingTokens: metadata.tokenUsage.reasoning_tokens || metadata.tokenUsage.thinking_tokens,
				cachingTokens: metadata.tokenUsage.cache_read_tokens || metadata.tokenUsage.cache_creation_tokens,
			};
		}

		if (metadata.usage) {
			return {
				inputTokens: metadata.usage.prompt_tokens || metadata.usage.input_tokens || 0,
				outputTokens: metadata.usage.completion_tokens || metadata.usage.output_tokens || 0,
				totalTokens: metadata.usage.total_tokens || 0,
				thinkingTokens: metadata.usage.reasoning_tokens || metadata.usage.thinking_tokens,
				cachingTokens: metadata.usage.cache_read_tokens || metadata.usage.cache_creation_tokens,
			};
		}

		const outputText = fallbackText || result.generations[0]?.text || '';
		const estimatedOutputTokens = this.estimateTokens(outputText);

		return {
			inputTokens: 0,
			outputTokens: estimatedOutputTokens,
			totalTokens: estimatedOutputTokens,
			estimationMethod: 'heuristic',
		} as any;
	}

	static estimateTokens(text: string): number {
		if (!text) return 0;

		const charCount = text.length;
		let tokenEstimate = charCount / 4;

		const codeBlockCount = (text.match(/```/g) || []).length / 2;
		tokenEstimate += codeBlockCount * 2;

		const specialChars = (text.match(/[{}[\]().,;:!?]/g) || []).length;
		tokenEstimate += specialChars * 0.5;

		return Math.ceil(tokenEstimate);
	}

	static createDetailedBreakdown(
		messages: BaseMessage[],
		drafterResult?: ChatResult,
		verifierResult?: ChatResult,
		domainResult?: ChatResult
	): DetailedTokenBreakdown {
		const messageTokens = this.countMessageTokens(messages);

		const messagesUsage: TokenUsage = {
			inputTokens: messageTokens,
			outputTokens: 0,
			totalTokens: messageTokens,
		};

		let draftUsage: TokenUsage | undefined;
		if (drafterResult) {
			draftUsage = this.extractTokenUsage(drafterResult, drafterResult.generations[0]?.text);
		}

		let verificationUsage: TokenUsage | undefined;
		if (verifierResult) {
			verificationUsage = this.extractTokenUsage(verifierResult, verifierResult.generations[0]?.text);
		}

		if (domainResult) {
			draftUsage = this.extractTokenUsage(domainResult, domainResult.generations[0]?.text);
		}

		const totalInputTokens =
			messagesUsage.inputTokens +
			(draftUsage?.inputTokens || 0) +
			(verificationUsage?.inputTokens || 0);

		const totalOutputTokens =
			(draftUsage?.outputTokens || 0) +
			(verificationUsage?.outputTokens || 0);

		const totalThinkingTokens =
			(draftUsage?.thinkingTokens || 0) +
			(verificationUsage?.thinkingTokens || 0);

		const totalCachingTokens =
			(draftUsage?.cachingTokens || 0) +
			(verificationUsage?.cachingTokens || 0);

		const estimationMethod =
			(draftUsage as any)?.estimationMethod === 'metadata' ||
			(verificationUsage as any)?.estimationMethod === 'metadata'
				? 'metadata'
				: 'heuristic';

		return {
			messages: messagesUsage,
			draft: draftUsage,
			verification: verificationUsage,
			total: {
				inputTokens: totalInputTokens,
				outputTokens: totalOutputTokens,
				totalTokens: totalInputTokens + totalOutputTokens,
				thinkingTokens: totalThinkingTokens > 0 ? totalThinkingTokens : undefined,
				cachingTokens: totalCachingTokens > 0 ? totalCachingTokens : undefined,
			},
			estimationMethod,
		};
	}

	static formatTokenUsage(usage: TokenUsage): string {
		let output = `${usage.inputTokens} in + ${usage.outputTokens} out = ${usage.totalTokens} total`;

		if (usage.thinkingTokens) {
			output += ` (${usage.thinkingTokens} thinking)`;
		}

		if (usage.cachingTokens) {
			output += ` (${usage.cachingTokens} cached)`;
		}

		return output;
	}

	static compareTokenUsage(
		cascadeUsage: TokenUsage,
		directVerifierUsage: TokenUsage
	): {
		tokensSaved: number;
		savingsPercentage: number;
		wasMoreEfficient: boolean;
	} {
		const tokensSaved = directVerifierUsage.totalTokens - cascadeUsage.totalTokens;
		const savingsPercentage = (tokensSaved / directVerifierUsage.totalTokens) * 100;

		return {
			tokensSaved,
			savingsPercentage,
			wasMoreEfficient: tokensSaved > 0,
		};
	}
}
