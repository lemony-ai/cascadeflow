/**
 * Cost Calculator for cascadeflow
 *
 * Provides accurate cost tracking and analysis for cascade operations.
 * Matches Python implementation from cascadeflow/telemetry/cost_calculator.py
 *
 * Features:
 * - Calculate costs from CascadeResult
 * - Calculate costs from raw token counts
 * - Token estimation from text
 * - Detailed cost breakdown with metadata
 * - Provider-aware cost calculation
 *
 * @example Basic usage
 * ```typescript
 * import { CostCalculator } from '@cascadeflow/core';
 *
 * const calculator = new CostCalculator();
 * const result = await agent.run('What is TypeScript?');
 *
 * // Calculate from result
 * const breakdown = calculator.calculate(result, 'What is TypeScript?');
 * console.log(`Total cost: $${breakdown.totalCost.toFixed(6)}`);
 * console.log(`Savings: ${breakdown.savingsPercentage.toFixed(1)}%`);
 * ```
 *
 * @example Direct token calculation
 * ```typescript
 * const breakdown = calculator.calculateFromTokens({
 *   draftOutputTokens: 150,
 *   verifierOutputTokens: 0,
 *   queryInputTokens: 20,
 *   draftAccepted: true,
 *   draftModel: 'gpt-4o-mini',
 *   verifierModel: 'gpt-4o',
 * });
 * ```
 */

import type { CascadeResult } from '../result';
import type { CostBreakdown } from '../types';
import { calculateCost } from '../integrations/litellm';

/**
 * Options for direct token-based cost calculation
 */
export interface CostCalculationFromTokensOptions {
  /** Number of output tokens from draft model */
  draftOutputTokens: number;

  /** Number of output tokens from verifier model (0 if not called) */
  verifierOutputTokens: number;

  /** Number of input tokens from query (estimated or measured) */
  queryInputTokens?: number;

  /** Whether draft was accepted */
  draftAccepted: boolean;

  /** Draft model name (for accurate pricing) */
  draftModel: string;

  /** Verifier model name (for accurate pricing) */
  verifierModel: string;

  /** Draft model provider */
  draftProvider?: string;

  /** Verifier model provider */
  verifierProvider?: string;
}

/**
 * Cost Calculator
 *
 * Provides comprehensive cost tracking and analysis for cascade operations.
 * Integrates with LiteLLM for accurate pricing across 100+ models.
 */
export class CostCalculator {
  /**
   * Calculate cost breakdown from a CascadeResult
   *
   * This is the main entry point for cost calculation. It extracts
   * token counts and model information from the result and calculates
   * a detailed cost breakdown.
   *
   * @param result - CascadeResult from agent.run()
   * @param queryText - Original query text (for input token estimation)
   * @returns Detailed cost breakdown
   *
   * @example
   * ```typescript
   * const calculator = new CostCalculator();
   * const result = await agent.run('Explain quantum computing');
   * const breakdown = calculator.calculate(result, 'Explain quantum computing');
   *
   * console.log(`Total: $${breakdown.totalCost.toFixed(6)}`);
   * console.log(`Draft: $${breakdown.draftCost.toFixed(6)}`);
   * console.log(`Verifier: $${breakdown.verifierCost.toFixed(6)}`);
   * console.log(`Saved: $${breakdown.costSaved.toFixed(6)} (${breakdown.savingsPercentage}%)`);
   * ```
   */
  calculate(result: CascadeResult, queryText: string = ''): CostBreakdown {
    // Estimate input tokens if query text provided
    const queryInputTokens = queryText ? CostCalculator.estimateTokens(queryText) : 0;

    if (result.draftAccepted) {
      return this._calculateAcceptedCosts(result, queryInputTokens);
    } else {
      return this._calculateRejectedCosts(result, queryInputTokens);
    }
  }

  /**
   * Calculate cost breakdown from raw token counts
   *
   * Useful when you have token counts but not a full CascadeResult.
   * This provides more control over the calculation.
   *
   * @param options - Token counts and model information
   * @returns Detailed cost breakdown
   *
   * @example
   * ```typescript
   * const calculator = new CostCalculator();
   * const breakdown = calculator.calculateFromTokens({
   *   draftOutputTokens: 150,
   *   verifierOutputTokens: 0,
   *   queryInputTokens: 20,
   *   draftAccepted: true,
   *   draftModel: 'gpt-4o-mini',
   *   verifierModel: 'gpt-4o',
   * });
   * ```
   */
  async calculateFromTokens(
    options: CostCalculationFromTokensOptions
  ): Promise<CostBreakdown> {
    const {
      draftOutputTokens,
      verifierOutputTokens,
      queryInputTokens = 0,
      draftAccepted,
      draftModel,
      verifierModel,
      draftProvider = 'openai',
      verifierProvider = 'openai',
    } = options;

    // Calculate draft cost (input + output)
    const draftInputTokens = queryInputTokens;
    const draftTotalTokens = draftInputTokens + draftOutputTokens;
    const draftCost = await calculateCost({
      model: this._formatModelName(draftModel, draftProvider),
      inputTokens: draftInputTokens,
      outputTokens: draftOutputTokens,
    });

    // Calculate verifier cost if called
    let verifierCost = 0;
    let verifierTotalTokens = 0;
    if (verifierOutputTokens > 0) {
      // Verifier sees: original query + draft response (as context)
      const verifierInputTokens = queryInputTokens + draftOutputTokens;
      verifierTotalTokens = verifierInputTokens + verifierOutputTokens;
      verifierCost = await calculateCost({
        model: this._formatModelName(verifierModel, verifierProvider),
        inputTokens: verifierInputTokens,
        outputTokens: verifierOutputTokens,
      });
    }

    const totalCost = draftCost + verifierCost;
    const totalTokens = draftTotalTokens + verifierTotalTokens;

    // Calculate savings
    let bigonlyCost: number;
    let costSaved: number;

    if (draftAccepted) {
      // Draft accepted - saved verifier cost
      // Bigonly = what it would cost to run verifier on original query
      bigonlyCost = await calculateCost({
        model: this._formatModelName(verifierModel, verifierProvider),
        inputTokens: queryInputTokens,
        outputTokens: draftOutputTokens, // Assume same output length
      });
      costSaved = bigonlyCost - draftCost;
    } else {
      // Draft rejected - both models called
      // Bigonly = just the verifier cost
      bigonlyCost = verifierCost;
      costSaved = -draftCost; // Negative = wasted draft cost
    }

    const savingsPercentage = bigonlyCost > 0
      ? (costSaved / bigonlyCost) * 100
      : 0;

    return {
      draftCost,
      verifierCost,
      totalCost,
      costSaved,
      bigonlyCost,
      savingsPercentage,
      draftTokens: draftTotalTokens,
      verifierTokens: verifierTotalTokens,
      totalTokens,
      wasCascaded: true,
      draftAccepted,
      metadata: {
        draftModel,
        verifierModel,
        draftProvider,
        verifierProvider,
        queryInputTokens,
        draftOutputTokens,
        verifierOutputTokens,
        timestamp: new Date().toISOString(),
      },
    };
  }

  /**
   * Estimate token count from text
   *
   * Uses a simple heuristic: ~1.3 tokens per word
   * This matches the Python implementation.
   *
   * @param text - Text to estimate tokens for
   * @returns Estimated token count
   *
   * @example
   * ```typescript
   * const tokens = CostCalculator.estimateTokens('What is TypeScript?');
   * console.log(`Estimated tokens: ${tokens}`); // ~4
   * ```
   */
  static estimateTokens(text: string): number {
    if (!text || text.trim().length === 0) {
      return 0;
    }

    // Split on whitespace and count words
    const wordCount = text.trim().split(/\s+/).length;

    // Rule of thumb: 1 token ≈ 0.75 words, or 1.3 tokens per word
    return Math.max(1, Math.round(wordCount * 1.3));
  }

  /**
   * Calculate costs when draft was accepted
   *
   * In this case:
   * - Only draft was called
   * - Verifier cost is 0
   * - Savings = (verifier cost - draft cost)
   */
  private _calculateAcceptedCosts(
    result: CascadeResult,
    queryInputTokens: number
  ): CostBreakdown {
    const draftCost = result.draftCost || 0;
    const verifierCost = 0;
    const totalCost = draftCost;

    // Estimate tokens (no usage data from result)
    const draftTokens = queryInputTokens + (result.responseLength || 0) / 4; // Rough estimate
    const verifierTokens = 0;
    const totalTokens = draftTokens;

    // Calculate what it would have cost with just the verifier
    const bigonlyCost = result.costSaved !== undefined
      ? draftCost + result.costSaved
      : draftCost * 3; // Rough fallback: assume 3x cost
    const costSaved = bigonlyCost - draftCost;
    const savingsPercentage = bigonlyCost > 0
      ? (costSaved / bigonlyCost) * 100
      : 0;

    return {
      draftCost,
      verifierCost,
      totalCost,
      costSaved,
      bigonlyCost,
      savingsPercentage,
      draftTokens,
      verifierTokens,
      totalTokens,
      wasCascaded: result.cascaded,
      draftAccepted: true,
      metadata: {
        draftModel: result.draftModel,
        verifierModel: result.verifierModel,
        queryInputTokens,
        complexity: result.complexity,
        qualityScore: result.qualityScore,
        timestamp: new Date().toISOString(),
      },
    };
  }

  /**
   * Calculate costs when draft was rejected
   *
   * In this case:
   * - Both draft and verifier were called
   * - Total cost = draft + verifier
   * - Savings = negative (wasted draft cost)
   */
  private _calculateRejectedCosts(
    result: CascadeResult,
    queryInputTokens: number
  ): CostBreakdown {
    const draftCost = result.draftCost || 0;
    const verifierCost = result.verifierCost || 0;
    const totalCost = draftCost + verifierCost;

    // Estimate tokens
    const draftLength = result.draftResponse?.length || 0;
    const verifierLength = result.verifierResponse?.length || 0;
    const draftTokens = queryInputTokens + draftLength / 4; // Rough estimate
    const verifierTokens = (queryInputTokens + draftLength / 4) + verifierLength / 4;
    const totalTokens = draftTokens + verifierTokens;

    // Bigonly = just verifier (we would have called it anyway)
    const bigonlyCost = verifierCost;
    const costSaved = -draftCost; // Negative = waste
    const savingsPercentage = bigonlyCost > 0
      ? (costSaved / bigonlyCost) * 100
      : 0;

    return {
      draftCost,
      verifierCost,
      totalCost,
      costSaved,
      bigonlyCost,
      savingsPercentage,
      draftTokens,
      verifierTokens,
      totalTokens,
      wasCascaded: result.cascaded,
      draftAccepted: false,
      metadata: {
        draftModel: result.draftModel,
        verifierModel: result.verifierModel,
        queryInputTokens,
        complexity: result.complexity,
        qualityScore: result.qualityScore,
        rejectionReason: result.rejectionReason,
        timestamp: new Date().toISOString(),
      },
    };
  }

  /**
   * Format model name with provider prefix if needed
   *
   * LiteLLM uses prefixes for some providers:
   * - anthropic/ for Claude models
   * - groq/ for Groq models
   * - together_ai/ for Together models
   * - etc.
   */
  private _formatModelName(model: string, provider: string): string {
    // If model already has a prefix, return as-is
    if (model.includes('/')) {
      return model;
    }

    // Add provider prefix for providers that need it
    const needsPrefix = ['anthropic', 'groq', 'together', 'together_ai', 'azure'];
    if (needsPrefix.includes(provider.toLowerCase())) {
      return `${provider}/${model}`;
    }

    return model;
  }
}

/**
 * Convenience function to create a cost calculator and calculate costs
 *
 * @param result - CascadeResult to analyze
 * @param queryText - Original query text
 * @returns Cost breakdown
 *
 * @example
 * ```typescript
 * import { calculateCascadeCost } from '@cascadeflow/core';
 *
 * const result = await agent.run('What is TypeScript?');
 * const breakdown = calculateCascadeCost(result, 'What is TypeScript?');
 * console.log(`Saved: $${breakdown.costSaved.toFixed(6)}`);
 * ```
 */
export function calculateCascadeCost(
  result: CascadeResult,
  queryText: string = ''
): CostBreakdown {
  const calculator = new CostCalculator();
  return calculator.calculate(result, queryText);
}
