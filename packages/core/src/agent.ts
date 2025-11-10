/**
 * cascadeflow Agent - MVP Implementation
 */

import { providerRegistry } from './providers/base';
import { OpenAIProvider } from './providers/openai';
import { AnthropicProvider } from './providers/anthropic';
import { GroqProvider } from './providers/groq';
import { TogetherProvider } from './providers/together';
import { OllamaProvider } from './providers/ollama';
import { HuggingFaceProvider } from './providers/huggingface';
import { VLLMProvider } from './providers/vllm';
import { OpenRouterProvider } from './providers/openrouter';
import type { AgentConfig, ModelConfig } from './config';
import type { CascadeResult } from './result';
import type { Message, Tool } from './types';
import {
  type StreamEvent,
  StreamEventType,
  createStreamEvent,
  type StreamOptions,
} from './streaming';
import {
  QualityValidator,
  DEFAULT_QUALITY_CONFIG as DEFAULT_VALIDATOR_QUALITY_CONFIG,
} from './quality';
import type { QualityConfig as QualityValidatorConfig } from './quality';
import { ComplexityDetector } from './complexity';
import type { QueryComplexity } from './types';

// Register providers
providerRegistry.register('openai', OpenAIProvider);
providerRegistry.register('anthropic', AnthropicProvider);
providerRegistry.register('groq', GroqProvider);
providerRegistry.register('together', TogetherProvider);
providerRegistry.register('ollama', OllamaProvider);
providerRegistry.register('huggingface', HuggingFaceProvider);
providerRegistry.register('vllm', VLLMProvider);
providerRegistry.register('openrouter', OpenRouterProvider);

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
 * cascadeflow Agent - Intelligent AI model cascading
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
  private qualityValidator: QualityValidator;
  private complexityDetector: ComplexityDetector;

  /**
   * Create a new cascadeflow agent
   *
   * The agent automatically cascades queries through multiple AI models,
   * starting with cheaper models and escalating to more expensive ones
   * only when necessary based on quality validation.
   *
   * @param config - Agent configuration with models and quality settings
   *
   * @throws {Error} When no models are provided
   *
   * @example Basic usage
   * ```typescript
   * import { CascadeAgent } from '@cascadeflow/core';
   *
   * const agent = new CascadeAgent({
   *   models: [
   *     { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
   *     { name: 'gpt-4o', provider: 'openai', cost: 0.00625 }
   *   ]
   * });
   * ```
   *
   * @example With presets
   * ```typescript
   * import { CascadeAgent, PRESET_BEST_OVERALL } from '@cascadeflow/core';
   *
   * const agent = new CascadeAgent(PRESET_BEST_OVERALL);
   * ```
   *
   * @example With quality configuration
   * ```typescript
   * const agent = new CascadeAgent({
   *   models: [...],
   *   quality: {
   *     threshold: 0.8,  // Higher = stricter quality checks
   *     requireMinimumTokens: 10
   *   }
   * });
   * ```
   */
  constructor(config: AgentConfig) {
    if (!config.models || config.models.length === 0) {
      throw new Error('At least one model is required');
    }

    // Sort models by cost (cheapest first)
    this.models = [...config.models].sort((a, b) => a.cost - b.cost);

    // Initialize quality validator
    const qualityOptions = config.quality ?? config.cascade?.quality;
    let validatorConfig: Partial<QualityValidatorConfig> | undefined;

    if (qualityOptions) {
      const {
        threshold,
        requireMinimumTokens,
        requireValidation: _requireValidation,
        enableAdaptive: _enableAdaptive,
        ...validatorParams
      } = qualityOptions;

      const validatorCandidate: Partial<QualityValidatorConfig> = validatorParams;

      validatorConfig = {
        ...validatorCandidate,
        minConfidence:
          validatorCandidate.minConfidence ??
          threshold ??
          DEFAULT_VALIDATOR_QUALITY_CONFIG.minConfidence,
        minWordCount:
          validatorCandidate.minWordCount ??
          requireMinimumTokens ??
          DEFAULT_VALIDATOR_QUALITY_CONFIG.minWordCount,
      };
    }

    this.qualityValidator = new QualityValidator(validatorConfig);

    // Initialize complexity detector
    this.complexityDetector = new ComplexityDetector();
  }

  /**
   * Execute a query through the AI model cascade
   *
   * This is the main method for running queries. It automatically:
   * 1. Tries the cheapest model first (draft)
   * 2. Validates the response quality
   * 3. Escalates to better models if quality is insufficient
   * 4. Returns detailed cost and timing metrics
   *
   * @param input - Query as string or message array
   * @param options - Optional configuration for this run
   * @param options.maxTokens - Maximum tokens to generate (default: provider default)
   * @param options.temperature - Temperature 0-2 for randomness (default: provider default)
   * @param options.systemPrompt - System prompt to guide the model
   * @param options.tools - Tools/functions available to the model
   * @param options.forceDirect - Skip cascade and use best model directly
   *
   * @returns Promise resolving to detailed cascade result with content, costs, and metrics
   *
   * @throws {ProviderError} When provider API calls fail
   * @throws {AuthenticationError} When API keys are missing or invalid
   * @throws {RateLimitError} When provider rate limits are exceeded
   * @throws {TimeoutError} When requests timeout
   *
   * @example Simple text query
   * ```typescript
   * const result = await agent.run('What is TypeScript?');
   * console.log(result.content);
   * console.log(`Cost: $${result.totalCost}`);
   * console.log(`Latency: ${result.latencyMs}ms`);
   * ```
   *
   * @example With options
   * ```typescript
   * const result = await agent.run('Explain quantum computing', {
   *   maxTokens: 500,
   *   temperature: 0.7,
   *   systemPrompt: 'You are a physics teacher'
   * });
   * ```
   *
   * @example With conversation history
   * ```typescript
   * const result = await agent.run([
   *   { role: 'user', content: 'What is 2+2?' },
   *   { role: 'assistant', content: '4' },
   *   { role: 'user', content: 'What about 3+3?' }
   * ]);
   * ```
   *
   * @example With tools
   * ```typescript
   * const result = await agent.run('What\'s the weather?', {
   *   tools: [{
   *     name: 'get_weather',
   *     description: 'Get weather for a location',
   *     parameters: { type: 'object', properties: { location: { type: 'string' } } }
   *   }]
   * });
   * ```
   *
   * @example Force direct execution (skip cascade)
   * ```typescript
   * const result = await agent.run('Complex query', {
   *   forceDirect: true  // Always use best model
   * });
   * ```
   *
   * @see {CascadeResult} for result structure
   * @see {RunOptions} for all available options
   */
  private getDefaultMaxTokens(): number {
    // Check first model's provider to determine hosting type
    const firstProvider = this.models[0]?.provider.toLowerCase();

    // Local/self-hosted providers - use conservative default (500 tokens)
    // These are typically slower, especially reasoning models like DeepSeek R1
    if (firstProvider === 'vllm' || firstProvider === 'ollama') {
      return 500;
    }

    // Cloud providers - use standard default (1000 tokens)
    // OpenAI, Anthropic, Groq, etc. are fast enough to handle more tokens
    return 1000;
  }

  async run(input: string | Message[], options: RunOptions = {}): Promise<CascadeResult> {
    const startTime = Date.now();

    // Set default max_tokens based on hosting type if not specified
    // Local providers (vllm, ollama): 500 tokens
    // Cloud providers (openai, anthropic, etc.): 1000 tokens
    const maxTokens = options.maxTokens ?? this.getDefaultMaxTokens();

    // Normalize input to messages
    const messages: Message[] =
      typeof input === 'string' ? [{ role: 'user', content: input }] : input;

    // Extract query text for complexity detection
    const queryText = typeof input === 'string'
      ? input
      : input.map(m => m.content).join('\n');

    // === STEP 1: COMPLEXITY DETECTION (PreRouter) ===
    const complexityResult = this.complexityDetector.detect(queryText);
    const { complexity } = complexityResult;

    // Define which complexities should cascade vs. direct route
    // TRIVIAL/SIMPLE/MODERATE → Cascade (cost optimization)
    // HARD/EXPERT → Direct to best model (quality priority)
    const cascadeComplexities: QueryComplexity[] = [
      'trivial',
      'simple',
      'moderate',
    ];

    const shouldCascade = !options.forceDirect && cascadeComplexities.includes(complexity);

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
    let finalToolCalls: any[] | undefined;

    // === STEP 2: ROUTING DECISION ===
    if (!shouldCascade || this.models.length === 1) {
      // Direct route to best model (most expensive)
      const bestModelConfig = this.models[this.models.length - 1];

      try {
        const provider = providerRegistry.get(bestModelConfig.provider, bestModelConfig);

        const response = await provider.generate({
          messages,
          model: bestModelConfig.name,
          maxTokens: maxTokens,
          temperature: options.temperature,
          systemPrompt: options.systemPrompt,
          tools: options.tools,
        });

        modelUsed = response.model;
        finalContent = response.content;
        finalToolCalls = response.tool_calls;

        // Calculate cost
        if (response.usage) {
          totalCost = provider.calculateCost(
            response.usage.prompt_tokens,
            response.usage.completion_tokens,
            response.model
          );
        }

        const latencyMs = Date.now() - startTime;

        return {
          content: finalContent,
          modelUsed,
          totalCost,
          latencyMs,
          complexity: complexity, // Now returns actual detected complexity
          cascaded: false,
          draftAccepted: false,
          routingStrategy: 'direct',
          reason: `Direct route (${complexity} complexity detected)`,
          toolCalls: finalToolCalls,
          hasToolCalls: !!finalToolCalls && finalToolCalls.length > 0,
          draftModel: undefined,
          draftCost: 0,
          draftLatencyMs: 0,
          verifierModel: undefined,
          verifierCost: 0,
          verifierLatencyMs: 0,
          costSaved: 0,
          savingsPercentage: 0,
        };
      } catch (error) {
        throw new Error(`cascadeflow error: ${error instanceof Error ? error.message : String(error)}`);
      }
    }

    // === STEP 3: CASCADE EXECUTION ===
    // Try draft model (cheapest)
    const draftModelConfig = this.models[0];
    const draftStart = Date.now();
    let draftResponse: any; // Move to wider scope for savings calculation

    try {
      const draftProvider = providerRegistry.get(draftModelConfig.provider, draftModelConfig);

      draftResponse = await draftProvider.generate({
        messages,
        model: draftModelConfig.name,
        maxTokens: maxTokens,
        temperature: options.temperature,
        systemPrompt: options.systemPrompt,
        tools: options.tools,
      });

      draftLatency = Date.now() - draftStart;
      draftModel = draftResponse?.model;
      finalContent = draftResponse?.content || '';
      modelUsed = draftModel || '';
      finalToolCalls = draftResponse.tool_calls;

      // Calculate draft cost
      if (draftResponse.usage) {
        draftCost = draftProvider.calculateCost(
          draftResponse.usage.prompt_tokens,
          draftResponse.usage.completion_tokens,
          draftResponse.model
        );
      }

      // Quality validation using logprobs and heuristics
      const query = typeof input === 'string' ? input : input.map(m => m.content).join('\n');
      const qualityResult = await this.qualityValidator.validate(
        draftResponse.content,
        query,
        draftResponse.logprobs,
        complexity,
        draftModelConfig.qualityThreshold // Per-model threshold override
      );
      const qualityPassed = qualityResult.passed;

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
          maxTokens: maxTokens,
          temperature: options.temperature,
          systemPrompt: options.systemPrompt,
          tools: options.tools,
        });

        verifierLatency = Date.now() - verifierStart;
        verifierModel = verifierResponse.model;
        finalContent = verifierResponse.content;
        modelUsed = verifierModel;
        finalToolCalls = verifierResponse.tool_calls;

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

      // Calculate savings (vs always using most expensive model) - matching Python's approach
      const expensiveModel = this.models[this.models.length - 1];
      const expensiveProvider = providerRegistry.get(expensiveModel.provider, expensiveModel);

      let bigonlyCost = 0;
      let costSaved = 0;

      if (draftAccepted) {
        // Draft accepted - calculate what it would cost if we used expensive model
        // Use actual token counts from draft response
        if (draftResponse.usage) {
          bigonlyCost = expensiveProvider.calculateCost(
            draftResponse.usage.prompt_tokens,
            draftResponse.usage.completion_tokens,
            expensiveModel.name
          );
          costSaved = bigonlyCost - draftCost; // Positive = saved money
        }
      } else {
        // Draft rejected - both models were called
        // Baseline is just the verifier cost (we would have called it anyway)
        bigonlyCost = verifierCost;
        costSaved = -draftCost; // Negative = wasted draft cost
      }

      const savingsPercentage = bigonlyCost > 0
        ? (costSaved / bigonlyCost) * 100
        : 0;

      const latencyMs = Date.now() - startTime;

      return {
        content: finalContent,
        modelUsed,
        totalCost,
        latencyMs,
        complexity: complexity, // Detected complexity from ComplexityDetector
        cascaded,
        draftAccepted,
        routingStrategy: 'cascade', // Always 'cascade' for this path (draft was tried)
        reason: cascaded ? 'Draft quality insufficient, escalated' : 'Draft accepted',
        toolCalls: finalToolCalls,
        hasToolCalls: !!finalToolCalls && finalToolCalls.length > 0,
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
      throw new Error(`cascadeflow error: ${error instanceof Error ? error.message : String(error)}`);
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

    // Set default max_tokens based on hosting type if not specified
    const maxTokens = options.maxTokens ?? this.getDefaultMaxTokens();

    // Normalize input to messages
    const messages: Message[] =
      typeof input === 'string' ? [{ role: 'user', content: input }] : input;

    // Extract query text for complexity detection
    const queryText = typeof input === 'string'
      ? input
      : input.map(m => m.content).join('\n');

    // Detect complexity
    const complexityResult = this.complexityDetector.detect(queryText);
    const { complexity } = complexityResult;

    const cascadeComplexities: QueryComplexity[] = [
      'trivial',
      'simple',
      'moderate',
    ];
    const shouldCascade =
      !options.forceDirect &&
      this.models.length > 1 &&
      cascadeComplexities.includes(complexity);

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
    let finalToolCalls: any[] | undefined;
    let draftToolCalls: any[] | undefined;
    let verifierToolCalls: any[] | undefined;

    const routingStrategy = shouldCascade ? 'cascade' : 'direct';

    // Emit ROUTING event
    yield createStreamEvent(StreamEventType.ROUTING, '', {
      strategy: routingStrategy,
      complexity,
    });

    try {
      if (!shouldCascade) {
        const bestModelConfig = this.models[this.models.length - 1];
        const directProvider = providerRegistry.get(
          bestModelConfig.provider,
          bestModelConfig
        );

        if (!directProvider.stream) {
          // Fallback to non-streaming path
          const result = await this.run(input, {
            maxTokens: maxTokens,
            temperature: options.temperature,
            systemPrompt: options.systemPrompt,
            tools: options.tools,
            forceDirect: true,
          });
          yield createStreamEvent(StreamEventType.CHUNK, result.content, {
            model: result.modelUsed,
            phase: 'direct',
            provider: bestModelConfig.provider,
            streaming_supported: false,
          });
          yield createStreamEvent(StreamEventType.COMPLETE, '', { result });
          return;
        }

        let directContent = '';
        let directToolCalls: any[] | undefined;

        for await (const chunk of directProvider.stream({
          messages,
          model: bestModelConfig.name,
          maxTokens: maxTokens,
          temperature: options.temperature,
          systemPrompt: options.systemPrompt,
          tools: options.tools,
        })) {
          directContent += chunk.content;

          if (chunk.tool_calls) {
            directToolCalls = chunk.tool_calls;
          }

          yield createStreamEvent(StreamEventType.CHUNK, chunk.content, {
            model: bestModelConfig.name,
            phase: 'direct',
            provider: bestModelConfig.provider,
          });

          if (chunk.done) {
            break;
          }
        }

        const latencyMs = Date.now() - startTime;
        const wordCount = directContent.split(/\s+/).length;
        const estimatedTokens = Math.ceil(wordCount * 1.3);
        totalCost = (estimatedTokens / 1000) * bestModelConfig.cost;

        const result: CascadeResult = {
          content: directContent,
          modelUsed: bestModelConfig.name,
          totalCost,
          latencyMs,
          complexity,
          cascaded: false,
          draftAccepted: false,
          routingStrategy: 'direct',
          reason: `Direct route (${complexity} complexity detected)`,
          toolCalls: directToolCalls,
          hasToolCalls: !!directToolCalls && directToolCalls.length > 0,
          draftModel: undefined,
          draftCost: 0,
          draftLatencyMs: 0,
          verifierModel: undefined,
          verifierCost: 0,
          verifierLatencyMs: 0,
          costSaved: 0,
          savingsPercentage: 0,
        };

        yield createStreamEvent(StreamEventType.COMPLETE, '', { result });
        return;
      }

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

      // Stream from draft model, collecting logprobs and tool calls
      const draftLogprobs: number[] = [];
      for await (const chunk of draftProvider.stream({
        messages,
        model: draftModelConfig.name,
        maxTokens: maxTokens,
        temperature: options.temperature,
        systemPrompt: options.systemPrompt,
        tools: options.tools,
      })) {
        draftContent += chunk.content;

        // Collect logprobs if available
        if (chunk.logprob !== undefined) {
          draftLogprobs.push(chunk.logprob);
        }

        // Collect tool calls if available
        if (chunk.tool_calls) {
          draftToolCalls = chunk.tool_calls;
        }

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

      // Quality validation using logprobs and heuristics
      const query = typeof input === 'string' ? input : input.map(m => m.content).join('\n');
      const qualityResult = await this.qualityValidator.validate(
        draftContent,
        query,
        draftLogprobs.length > 0 ? draftLogprobs : undefined,
        complexity,
        draftModelConfig.qualityThreshold // Per-model threshold override
      );
      const qualityPassed = qualityResult.passed;

      draftAccepted = qualityPassed || this.models.length === 1 || options.forceDirect === true;

      // Emit DRAFT_DECISION event with real quality scores
      yield createStreamEvent(StreamEventType.DRAFT_DECISION, '', {
        accepted: draftAccepted,
        score: qualityResult.score,
        confidence: qualityResult.confidence,
        draft_model: draftModel,
        verifier_model: this.models.length > 1 ? this.models[1].name : undefined,
        reason: draftAccepted ? 'quality_passed' : 'quality_failed',
        checks_passed: qualityPassed,
        quality_threshold: this.qualityValidator.getConfig().minConfidence,
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
            reason: qualityResult.reason,
            draft_confidence: qualityResult.confidence,
            quality_threshold: this.qualityValidator.getConfig().minConfidence,
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
            maxTokens: maxTokens,
            temperature: options.temperature,
            systemPrompt: options.systemPrompt,
            tools: options.tools,
          })) {
            verifierContent += chunk.content;

            // Collect tool calls if available
            if (chunk.tool_calls) {
              verifierToolCalls = chunk.tool_calls;
            }

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
            maxTokens: maxTokens,
            temperature: options.temperature,
            systemPrompt: options.systemPrompt,
            tools: options.tools,
          });
          verifierContent = verifierResponse.content;
          verifierToolCalls = verifierResponse.tool_calls;
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
        finalToolCalls = verifierToolCalls;
      } else {
        finalContent = draftContent;
        modelUsed = draftModel;
        finalToolCalls = draftToolCalls;
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
        complexity,
        cascaded,
        draftAccepted,
        routingStrategy: cascaded ? 'cascade' : 'direct',
        reason: cascaded
          ? 'Draft quality insufficient, escalated'
          : 'Draft accepted',
        toolCalls: finalToolCalls,
        hasToolCalls: !!finalToolCalls && finalToolCalls.length > 0,
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
        `cascadeflow streaming error: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  /**
   * Get the list of configured models
   *
   * Returns a copy of the models array sorted by cost (cheapest first).
   * Useful for inspecting the cascade configuration.
   *
   * @returns Array of model configurations (sorted by cost)
   *
   * @example
   * ```typescript
   * const agent = new CascadeAgent(PRESET_BEST_OVERALL);
   * const models = agent.getModels();
   *
   * console.log('Available models:');
   * for (const model of models) {
   *   console.log(`  - ${model.name} (${model.provider}): $${model.cost}/1K tokens`);
   * }
   * ```
   *
   * @example Check draft and verifier models
   * ```typescript
   * const models = agent.getModels();
   * const draftModel = models[0];  // Cheapest (draft)
   * const verifierModel = models[models.length - 1];  // Most expensive (verifier)
   *
   * console.log(`Draft: ${draftModel.name}`);
   * console.log(`Verifier: ${verifierModel.name}`);
   * ```
   */
  getModels(): ModelConfig[] {
    return [...this.models];
  }

  /**
   * Get the number of models in the cascade
   *
   * A count of 1 means no cascading (direct execution only).
   * A count of 2+ enables cascade behavior.
   *
   * @returns Number of configured models
   *
   * @example
   * ```typescript
   * const agent = new CascadeAgent(PRESET_BEST_OVERALL);
   *
   * if (agent.getModelCount() === 1) {
   *   console.log('No cascade - direct execution only');
   * } else {
   *   console.log(`Cascade enabled with ${agent.getModelCount()} models`);
   * }
   * ```
   */
  getModelCount(): number {
    return this.models.length;
  }
}
