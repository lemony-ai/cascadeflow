/**
 * CascadeFlow Agent - MVP Implementation
 */

import { providerRegistry } from './providers/base';
import { OpenAIProvider } from './providers/openai';
import type { AgentConfig, ModelConfig } from './config';
import type { CascadeResult } from './result';
import type { Message, Tool } from './types';

// Register providers
providerRegistry.register('openai', OpenAIProvider);

/**
 * Run options for agent
 */
export interface RunOptions {
  /** Maximum tokens to generate */
  maxTokens?: number;

  /** Temperature (0-2) */
  temperature?: number;

  /** System prompt */
  systemPrompt?: string;

  /** Tools/functions available */
  tools?: Tool[];

  /** Force direct execution (skip cascade) */
  forceDirect?: boolean;
}

/**
 * CascadeFlow Agent - Intelligent AI model cascading
 *
 * @example
 * ```typescript
 * const agent = new CascadeAgent({
 *   models: [
 *     { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
 *     { name: 'gpt-4o', provider: 'openai', cost: 0.00625 }
 *   ]
 * });
 *
 * const result = await agent.run('What is TypeScript?');
 * console.log(result.content);
 * console.log(`Cost: $${result.totalCost}, Savings: ${result.savingsPercentage}%`);
 * ```
 */
export class CascadeAgent {
  private models: ModelConfig[];

  constructor(config: AgentConfig) {
    if (!config.models || config.models.length === 0) {
      throw new Error('At least one model is required');
    }

    // Sort models by cost (cheapest first)
    this.models = [...config.models].sort((a, b) => a.cost - b.cost);
  }

  /**
   * Run a query through the cascade
   */
  async run(input: string | Message[], options: RunOptions = {}): Promise<CascadeResult> {
    const startTime = Date.now();

    // Normalize input to messages
    const messages: Message[] =
      typeof input === 'string' ? [{ role: 'user', content: input }] : input;

    // For MVP, we'll use simple cascade logic:
    // 1. Try cheapest model first
    // 2. If quality is insufficient, escalate to next model
    // 3. Return result

    let draftCost = 0;
    let verifierCost = 0;
    let totalCost = 0;
    let draftModel: string | undefined;
    let verifierModel: string | undefined;
    let draftLatency = 0;
    let verifierLatency = 0;
    let cascaded = false;
    let draftAccepted = false;
    let finalContent = '';
    let modelUsed = '';

    // Try draft model (cheapest)
    const draftModelConfig = this.models[0];
    const draftStart = Date.now();

    try {
      const draftProvider = providerRegistry.get(draftModelConfig.provider, draftModelConfig);

      const draftResponse = await draftProvider.generate({
        messages,
        model: draftModelConfig.name,
        maxTokens: options.maxTokens,
        temperature: options.temperature,
        systemPrompt: options.systemPrompt,
        tools: options.tools,
      });

      draftLatency = Date.now() - draftStart;
      draftModel = draftResponse.model;
      finalContent = draftResponse.content;
      modelUsed = draftModel;

      // Calculate draft cost
      if (draftResponse.usage) {
        draftCost = draftProvider.calculateCost(
          draftResponse.usage.prompt_tokens,
          draftResponse.usage.completion_tokens,
          draftResponse.model
        );
      }

      // Simple quality check: if response is too short, cascade
      const wordCount = draftResponse.content.split(/\s+/).length;
      const qualityPassed = wordCount >= 10; // Simple heuristic

      if (!qualityPassed && this.models.length > 1 && !options.forceDirect) {
        // Escalate to verifier (next model)
        cascaded = true;
        draftAccepted = false;

        const verifierModelConfig = this.models[1];
        const verifierStart = Date.now();

        const verifierProvider = providerRegistry.get(
          verifierModelConfig.provider,
          verifierModelConfig
        );

        const verifierResponse = await verifierProvider.generate({
          messages,
          model: verifierModelConfig.name,
          maxTokens: options.maxTokens,
          temperature: options.temperature,
          systemPrompt: options.systemPrompt,
          tools: options.tools,
        });

        verifierLatency = Date.now() - verifierStart;
        verifierModel = verifierResponse.model;
        finalContent = verifierResponse.content;
        modelUsed = verifierModel;

        // Calculate verifier cost
        if (verifierResponse.usage) {
          verifierCost = verifierProvider.calculateCost(
            verifierResponse.usage.prompt_tokens,
            verifierResponse.usage.completion_tokens,
            verifierResponse.model
          );
        }
      } else {
        draftAccepted = true;
      }

      totalCost = draftCost + verifierCost;

      // Calculate savings (vs always using most expensive model)
      const expensiveModel = this.models[this.models.length - 1];

      // Estimate cost if we used expensive model only
      const estimatedExpensiveCost = expensiveModel.cost * 1.5; // Simple estimate
      const costSaved = Math.max(0, estimatedExpensiveCost - totalCost);
      const savingsPercentage = estimatedExpensiveCost > 0
        ? (costSaved / estimatedExpensiveCost) * 100
        : 0;

      const latencyMs = Date.now() - startTime;

      return {
        content: finalContent,
        modelUsed,
        totalCost,
        latencyMs,
        complexity: 'unknown', // MVP: no complexity detection yet
        cascaded,
        draftAccepted,
        routingStrategy: cascaded ? 'cascade' : 'direct',
        reason: cascaded ? 'Draft quality insufficient, escalated' : 'Draft accepted',
        hasToolCalls: false, // MVP: no tool calling yet
        draftModel,
        draftCost,
        draftLatencyMs: draftLatency,
        verifierModel,
        verifierCost,
        verifierLatencyMs: verifierLatency,
        costSaved,
        savingsPercentage,
      };
    } catch (error) {
      throw new Error(`CascadeFlow error: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Get available models
   */
  getModels(): ModelConfig[] {
    return [...this.models];
  }

  /**
   * Get model count
   */
  getModelCount(): number {
    return this.models.length;
  }
}
