/**
 * CascadeFlow Agent - MVP Implementation
 */

import { providerRegistry } from './providers/base';
import { OpenAIProvider } from './providers/openai';
import { AnthropicProvider } from './providers/anthropic';
import { GroqProvider } from './providers/groq';
import { TogetherProvider } from './providers/together';
import { OllamaProvider } from './providers/ollama';
import { HuggingFaceProvider } from './providers/huggingface';
import { VLLMProvider } from './providers/vllm';
import type { AgentConfig, ModelConfig } from './config';
import type { CascadeResult } from './result';
import type { Message, Tool } from './types';
import {
  type StreamEvent,
  StreamEventType,
  createStreamEvent,
  type StreamOptions,
} from './streaming';

// Register providers
providerRegistry.register('openai', OpenAIProvider);
providerRegistry.register('anthropic', AnthropicProvider);
providerRegistry.register('groq', GroqProvider);
providerRegistry.register('together', TogetherProvider);
providerRegistry.register('ollama', OllamaProvider);
providerRegistry.register('huggingface', HuggingFaceProvider);
providerRegistry.register('vllm', VLLMProvider);

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
   * Stream a query through the cascade
   *
   * Yields StreamEvent objects with real-time progress updates
   *
   * @example
   * ```typescript
   * for await (const event of agent.runStream('What is TypeScript?')) {
   *   if (event.type === StreamEventType.CHUNK) {
   *     process.stdout.write(event.content);
   *   } else if (event.type === StreamEventType.COMPLETE) {
   *     console.log('\nFinal result:', event.data.result);
   *   }
   * }
   * ```
   */
  async *runStream(
    input: string | Message[],
    options: StreamOptions = {}
  ): AsyncIterable<StreamEvent> {
    const startTime = Date.now();

    // Normalize input to messages
    const messages: Message[] =
      typeof input === 'string' ? [{ role: 'user', content: input }] : input;

    // For MVP, use simple cascade logic similar to run()
    let draftCost = 0;
    let verifierCost = 0;
    let totalCost = 0;
    let draftModel: string | undefined;
    let verifierModel: string | undefined;
    let draftLatency = 0;
    let verifierLatency = 0;
    let cascaded = false;
    let draftAccepted = false;
    let draftContent = '';
    let verifierContent = '';
    let finalContent = '';
    let modelUsed = '';

    // Emit ROUTING event
    yield createStreamEvent(StreamEventType.ROUTING, '', {
      strategy: this.models.length > 1 ? 'cascade' : 'direct',
      complexity: 'unknown',
    });

    try {
      // Try draft model (cheapest)
      const draftModelConfig = this.models[0];
      const draftProvider = providerRegistry.get(draftModelConfig.provider, draftModelConfig);

      // Check if provider supports streaming
      if (!draftProvider.stream) {
        // Fallback to non-streaming
        const result = await this.run(input, options as RunOptions);
        yield createStreamEvent(StreamEventType.CHUNK, result.content, {
          model: result.modelUsed,
          phase: 'direct',
          provider: draftModelConfig.provider,
          streaming_supported: false,
        });
        yield createStreamEvent(StreamEventType.COMPLETE, '', { result });
        return;
      }

      const draftStart = Date.now();
      draftModel = draftModelConfig.name;

      // Stream from draft model
      for await (const chunk of draftProvider.stream({
        messages,
        model: draftModelConfig.name,
        maxTokens: options.maxTokens,
        temperature: options.temperature,
        systemPrompt: options.systemPrompt,
        tools: options.tools,
      })) {
        draftContent += chunk.content;

        // Yield CHUNK event
        yield createStreamEvent(StreamEventType.CHUNK, chunk.content, {
          model: draftModel,
          phase: 'draft',
          provider: draftModelConfig.provider,
        });

        if (chunk.done) {
          break;
        }
      }

      draftLatency = Date.now() - draftStart;

      // Estimate draft cost (simplified)
      const wordCount = draftContent.split(/\s+/).length;
      const estimatedTokens = Math.ceil(wordCount * 1.3);
      draftCost = (estimatedTokens / 1000) * draftModelConfig.cost;

      // Simple quality check (MVP heuristic)
      const qualityThreshold = options.qualityThreshold || 10; // minimum word count
      const qualityPassed = wordCount >= qualityThreshold;

      draftAccepted = qualityPassed || this.models.length === 1 || options.forceDirect === true;

      // Emit DRAFT_DECISION event
      yield createStreamEvent(StreamEventType.DRAFT_DECISION, '', {
        accepted: draftAccepted,
        score: qualityPassed ? 0.8 : 0.5,
        confidence: qualityPassed ? 0.75 : 0.6,
        draft_model: draftModel,
        verifier_model: this.models.length > 1 ? this.models[1].name : undefined,
        reason: draftAccepted ? 'quality_passed' : 'quality_failed',
        checks_passed: qualityPassed,
        quality_threshold: qualityThreshold,
      });

      if (!draftAccepted && this.models.length > 1) {
        // Cascade to verifier
        cascaded = true;
        const verifierModelConfig = this.models[1];
        verifierModel = verifierModelConfig.name;

        // Emit SWITCH event
        yield createStreamEvent(
          StreamEventType.SWITCH,
          `⤴ Cascading to ${verifierModel}`,
          {
            from_model: draftModel,
            to_model: verifierModel,
            reason: 'Quality threshold not met',
            draft_confidence: 0.6,
            quality_threshold: qualityThreshold,
          }
        );

        const verifierProvider = providerRegistry.get(
          verifierModelConfig.provider,
          verifierModelConfig
        );

        // Check if verifier supports streaming
        if (verifierProvider.stream) {
          const verifierStart = Date.now();

          // Stream from verifier
          for await (const chunk of verifierProvider.stream({
            messages,
            model: verifierModelConfig.name,
            maxTokens: options.maxTokens,
            temperature: options.temperature,
            systemPrompt: options.systemPrompt,
            tools: options.tools,
          })) {
            verifierContent += chunk.content;

            // Yield CHUNK event
            yield createStreamEvent(StreamEventType.CHUNK, chunk.content, {
              model: verifierModel,
              phase: 'verifier',
              provider: verifierModelConfig.provider,
            });

            if (chunk.done) {
              break;
            }
          }

          verifierLatency = Date.now() - verifierStart;
        } else {
          // Fallback to non-streaming
          const verifierStart = Date.now();
          const verifierResponse = await verifierProvider.generate({
            messages,
            model: verifierModelConfig.name,
            maxTokens: options.maxTokens,
            temperature: options.temperature,
            systemPrompt: options.systemPrompt,
            tools: options.tools,
          });
          verifierContent = verifierResponse.content;
          verifierLatency = Date.now() - verifierStart;

          yield createStreamEvent(StreamEventType.CHUNK, verifierContent, {
            model: verifierModel,
            phase: 'verifier',
            provider: verifierModelConfig.provider,
            streaming_supported: false,
          });
        }

        // Estimate verifier cost
        const verifierWordCount = verifierContent.split(/\s+/).length;
        const verifierEstimatedTokens = Math.ceil(verifierWordCount * 1.3);
        verifierCost = (verifierEstimatedTokens / 1000) * verifierModelConfig.cost;

        finalContent = verifierContent;
        modelUsed = verifierModel;
      } else {
        finalContent = draftContent;
        modelUsed = draftModel;
      }

      totalCost = draftCost + verifierCost;

      // Calculate savings
      const expensiveModel = this.models[this.models.length - 1];
      const estimatedExpensiveCost = expensiveModel.cost * 1.5;
      const costSaved = Math.max(0, estimatedExpensiveCost - totalCost);
      const savingsPercentage =
        estimatedExpensiveCost > 0 ? (costSaved / estimatedExpensiveCost) * 100 : 0;

      const latencyMs = Date.now() - startTime;

      // Build final result
      const result: CascadeResult = {
        content: finalContent,
        modelUsed,
        totalCost,
        latencyMs,
        complexity: 'unknown',
        cascaded,
        draftAccepted,
        routingStrategy: cascaded ? 'cascade' : 'direct',
        reason: cascaded
          ? 'Draft quality insufficient, escalated'
          : 'Draft accepted',
        hasToolCalls: false,
        draftModel,
        draftCost,
        draftLatencyMs: draftLatency,
        verifierModel,
        verifierCost,
        verifierLatencyMs: verifierLatency,
        costSaved,
        savingsPercentage,
      };

      // Emit COMPLETE event
      yield createStreamEvent(StreamEventType.COMPLETE, '', { result });
    } catch (error) {
      // Emit ERROR event
      yield createStreamEvent(
        StreamEventType.ERROR,
        error instanceof Error ? error.message : String(error),
        {
          error: error instanceof Error ? error.message : String(error),
          type: error instanceof Error ? error.constructor.name : 'Error',
        }
      );

      throw new Error(
        `CascadeFlow streaming error: ${error instanceof Error ? error.message : String(error)}`
      );
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
