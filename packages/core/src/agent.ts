/**
 * cascadeflow Agent - MVP Implementation
 */

import { providerRegistry, getAvailableProviders } from './providers/base';
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
import type { Message, Tool, UserProfile, TierLevel } from './types';
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
import { TIER_PRESETS } from './profiles';
import { PreRouter, type PreRouterConfig } from './routers/pre-router';
import { ToolRouter, type ToolRouterConfig } from './routers/tool-router';
import { TierRouter, type TierAwareRouterConfig, type TierRouterConfig } from './routers/tier-router';
import { RoutingStrategy, RoutingDecisionHelper } from './routers/base';

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

  /** User tier name for tier-based model filtering (optional) */
  userTier?: string;
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
  private batchProcessor?: import('./batch').BatchProcessor;
  private preRouter: PreRouter;
  private toolRouter: ToolRouter;
  private tierRouter?: TierRouter;

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

    // Initialize routers
    const verbose = config.cascade?.verbose ?? false;

    // PreRouter: Complexity-based routing decisions
    this.preRouter = new PreRouter({
      complexityDetector: this.complexityDetector,
      enableCascade: true,
      verbose,
    });

    // ToolRouter: Tool capability filtering
    this.toolRouter = new ToolRouter({
      models: this.models,
      verbose,
    });

    // TierRouter: Optional tier-based filtering (initialized if tiers provided)
    // Note: We don't initialize TierRouter here by default since tiers are optional
    // It will be created on-demand if userTier is passed to run()
    this.tierRouter = undefined;
  }

  // ==================== FACTORY METHODS ====================

  /**
   * Create CascadeAgent from environment variables
   *
   * Auto-discovers available providers by checking environment for API keys
   * and creates a sensible default configuration.
   *
   * @param options - Optional configuration overrides
   * @param options.quality - Quality configuration
   * @param options.enableCascade - Enable cascading (default: true)
   * @returns CascadeAgent instance
   *
   * @throws {Error} When no providers are available in environment
   *
   * @example
   * ```typescript
   * // Requires OPENAI_API_KEY and/or ANTHROPIC_API_KEY in environment
   * const agent = CascadeAgent.fromEnv();
   * const result = await agent.run('What is TypeScript?');
   * ```
   */
  static fromEnv(options?: {
    quality?: Partial<QualityValidatorConfig>;
    enableCascade?: boolean;
  }): CascadeAgent {
    const available = getAvailableProviders();

    if (available.length === 0) {
      throw new Error(
        'No providers available. Set API keys in environment (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY)'
      );
    }

    const models: ModelConfig[] = [];

    // Add OpenAI models if available
    if (available.includes('openai')) {
      models.push(
        { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
        { name: 'gpt-3.5-turbo', provider: 'openai', cost: 0.002 },
        { name: 'gpt-4o', provider: 'openai', cost: 0.00625 }
      );
    }

    // Add Anthropic models if available
    if (available.includes('anthropic')) {
      models.push(
        { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
        { name: 'claude-3-5-sonnet-20241022', provider: 'anthropic', cost: 0.003 }
      );
    }

    // Add Groq models if available
    if (available.includes('groq')) {
      models.push({ name: 'llama-3.3-70b-versatile', provider: 'groq', cost: 0.0 });
    }

    if (models.length === 0) {
      throw new Error('No models configured for available providers');
    }

    return new CascadeAgent({
      models,
      quality: options?.quality,
    });
  }

  /**
   * Create CascadeAgent from UserProfile
   *
   * Configures the agent based on a user's profile including tier limits,
   * preferred models, and quality settings.
   *
   * @param profile - UserProfile with tier and preferences
   * @param options - Optional configuration overrides
   * @param options.quality - Quality configuration override
   * @returns CascadeAgent instance configured for the user's tier
   *
   * @throws {Error} When no providers are available in environment
   *
   * @example
   * ```typescript
   * import { createUserProfile, CascadeAgent } from '@cascadeflow/core';
   *
   * const profile = createUserProfile('PRO', 'user-123', {
   *   preferredModels: ['gpt-4o', 'claude-3-5-sonnet-20241022']
   * });
   *
   * const agent = CascadeAgent.fromProfile(profile);
   * const result = await agent.run('What is Python?');
   * ```
   */
  static fromProfile(
    profile: UserProfile,
    options?: {
      quality?: Partial<QualityValidatorConfig>;
    }
  ): CascadeAgent {
    const available = getAvailableProviders();

    if (available.length === 0) {
      throw new Error(
        'No providers available. Set API keys in environment (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY)'
      );
    }

    const models: ModelConfig[] = [];
    const preferredSet = profile.preferredModels
      ? new Set(profile.preferredModels)
      : null;

    // Add OpenAI models if available
    if (available.includes('openai')) {
      const openaiModels: ModelConfig[] = [
        { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
        { name: 'gpt-3.5-turbo', provider: 'openai', cost: 0.002 },
        { name: 'gpt-4o', provider: 'openai', cost: 0.00625 },
      ];

      for (const model of openaiModels) {
        if (!preferredSet || preferredSet.has(model.name)) {
          models.push(model);
        }
      }
    }

    // Add Anthropic models if available
    if (available.includes('anthropic')) {
      const anthropicModels: ModelConfig[] = [
        { name: 'claude-3-5-haiku-20241022', provider: 'anthropic', cost: 0.0008 },
        { name: 'claude-3-5-sonnet-20241022', provider: 'anthropic', cost: 0.003 },
      ];

      for (const model of anthropicModels) {
        if (!preferredSet || preferredSet.has(model.name)) {
          models.push(model);
        }
      }
    }

    // Add Groq models if available
    if (available.includes('groq')) {
      const groqModels: ModelConfig[] = [
        { name: 'llama-3.3-70b-versatile', provider: 'groq', cost: 0.0 },
      ];

      for (const model of groqModels) {
        if (!preferredSet || preferredSet.has(model.name)) {
          models.push(model);
        }
      }
    }

    if (models.length === 0) {
      throw new Error(
        'No models available matching profile preferences. Check preferredModels configuration.'
      );
    }

    // Apply tier quality settings if not overridden
    const qualityConfig = options?.quality ?? {
      minConfidence: profile.tier.minQuality,
    };

    return new CascadeAgent({
      models,
      quality: qualityConfig,
    });
  }

  /**
   * Create CascadeAgent for a specific tier
   *
   * Quick factory method to create an agent configured for a specific
   * subscription tier without creating a full UserProfile.
   *
   * @param tier - Tier level (FREE, STARTER, PRO, BUSINESS, ENTERPRISE)
   * @param options - Optional configuration overrides
   * @param options.quality - Quality configuration override
   * @returns CascadeAgent instance configured for the tier
   *
   * @throws {Error} When no providers are available in environment
   *
   * @example
   * ```typescript
   * const agent = CascadeAgent.forTier('PRO');
   * const result = await agent.run('What is Rust?');
   * ```
   */
  static forTier(
    tier: TierLevel,
    options?: {
      quality?: Partial<QualityValidatorConfig>;
    }
  ): CascadeAgent {
    const tierConfig = TIER_PRESETS[tier];

    const qualityConfig = options?.quality ?? {
      minConfidence: tierConfig.minQuality,
    };

    return CascadeAgent.fromEnv({ quality: qualityConfig });
  }

  // ==================== INSTANCE METHODS ====================

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

    // === STEP 1: MODEL FILTERING ===
    let availableModels = [...this.models]; // Start with all models

    // Step 1a: Filter by tool capability if tools are present
    if (options.tools && options.tools.length > 0) {
      const toolFilterResult = this.toolRouter.filterToolCapableModels({
        tools: options.tools,
        availableModels,
      });

      if (!toolFilterResult.hasCapableModels) {
        throw new Error(
          `No models support tools. Requested tools: ${options.tools.map(t => t.function?.name || 'unknown').join(', ')}`
        );
      }

      availableModels = toolFilterResult.models;
    }

    // Step 1b: Filter by user tier if specified
    if (options.userTier) {
      // For tier filtering, we would need tier configuration
      // For now, we'll skip tier filtering unless tiers are configured
      // This matches the Python implementation where tier filtering is optional
    }

    // === STEP 2: ROUTING DECISION (PreRouter) ===
    const routingContext = {
      tools: options.tools,
      userTier: options.userTier,
      forceDirect: options.forceDirect,
      availableModels: availableModels.length,
    };

    const routingDecision = await this.preRouter.route(queryText, routingContext);
    const { complexity } = this.complexityDetector.detect(queryText);

    // Determine if we should cascade based on routing decision
    const shouldCascade =
      !options.forceDirect &&
      routingDecision.strategy === RoutingStrategy.CASCADE &&
      availableModels.length > 1;

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

    // === STEP 3: EXECUTE BASED ON ROUTING DECISION ===
    if (!shouldCascade || availableModels.length === 1) {
      // Direct route to best model (most expensive) from available models
      const bestModelConfig = availableModels[availableModels.length - 1];

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

    // === STEP 4: CASCADE EXECUTION ===
    // Try draft model (cheapest from available models)
    const draftModelConfig = availableModels[0];
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

      if (!qualityPassed && availableModels.length > 1 && !options.forceDirect) {
        // Escalate to verifier (next model from available models)
        cascaded = true;
        draftAccepted = false;

        const verifierModelConfig = availableModels[1];
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
      const expensiveModel = availableModels[availableModels.length - 1];
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

  /**
   * Process multiple queries in batch
   *
   * Efficient batch processing with:
   * - Concurrency control (max parallel requests)
   * - Per-query timeout and retry logic
   * - Cost tracking across all queries
   * - Quality validation per query
   * - Graceful error handling
   *
   * @param queries - Array of query strings to process
   * @param batchConfig - Batch configuration (optional)
   * @param runOptions - Options passed to each run() call (optional)
   * @returns BatchResult with all results and statistics
   *
   * @example
   * ```typescript
   * const queries = [
   *   'What is TypeScript?',
   *   'What is JavaScript?',
   *   'What is Rust?'
   * ];
   *
   * const result = await agent.runBatch(queries);
   *
   * console.log(`Success: ${result.successCount}/${queries.length}`);
   * console.log(`Total cost: $${result.totalCost.toFixed(4)}`);
   * console.log(`Strategy: ${result.strategyUsed}`);
   *
   * result.results.forEach((r, i) => {
   *   if (r) {
   *     console.log(`Query ${i}: ${r.content.slice(0, 100)}...`);
   *   }
   * });
   * ```
   *
   * @example
   * ```typescript
   * // With custom configuration
   * const config: BatchConfig = {
   *   maxParallel: 5,
   *   timeoutPerQuery: 60,
   *   retryFailed: true,
   *   stopOnError: false
   * };
   *
   * const result = await agent.runBatch(queries, config);
   * ```
   */
  async runBatch(
    queries: string[],
    batchConfig?: import('./batch').BatchConfig,
    runOptions?: RunOptions
  ): Promise<import('./batch').BatchResult> {
    const { BatchProcessor } = await import('./batch');

    // Create batch processor (lazy-loaded)
    if (!this.batchProcessor) {
      this.batchProcessor = new BatchProcessor();
    }

    // Process batch using the processor
    return this.batchProcessor.processBatch(
      queries,
      (query, options) => this.run(query, options),
      batchConfig,
      runOptions
    );
  }

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

    // === STEP 1: MODEL FILTERING ===
    let availableModels = [...this.models]; // Start with all models

    // Step 1a: Filter by tool capability if tools are present
    if (options.tools && options.tools.length > 0) {
      const toolFilterResult = this.toolRouter.filterToolCapableModels({
        tools: options.tools,
        availableModels,
      });

      if (!toolFilterResult.hasCapableModels) {
        throw new Error(
          `No models support tools. Requested tools: ${options.tools.map(t => t.function?.name || 'unknown').join(', ')}`
        );
      }

      availableModels = toolFilterResult.models;
    }

    // Step 1b: Filter by user tier if specified (future enhancement)
    // if (options.userTier) { ... }

    // === STEP 2: ROUTING DECISION ===
    const routingContext = {
      tools: options.tools,
      forceDirect: options.forceDirect,
      availableModels: availableModels.length,
    };

    const routingDecision = await this.preRouter.route(queryText, routingContext);
    const { complexity } = this.complexityDetector.detect(queryText);

    const shouldCascade =
      !options.forceDirect &&
      routingDecision.strategy === RoutingStrategy.CASCADE &&
      availableModels.length > 1;

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
        const bestModelConfig = availableModels[availableModels.length - 1];
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

      // Try draft model (cheapest from available models)
      const draftModelConfig = availableModels[0];
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

      draftAccepted = qualityPassed || availableModels.length === 1 || options.forceDirect === true;

      // Emit DRAFT_DECISION event with real quality scores
      yield createStreamEvent(StreamEventType.DRAFT_DECISION, '', {
        accepted: draftAccepted,
        score: qualityResult.score,
        confidence: qualityResult.confidence,
        draft_model: draftModel,
        verifier_model: availableModels.length > 1 ? availableModels[1].name : undefined,
        reason: draftAccepted ? 'quality_passed' : 'quality_failed',
        checks_passed: qualityPassed,
        quality_threshold: this.qualityValidator.getConfig().minConfidence,
      });

      if (!draftAccepted && availableModels.length > 1) {
        // Cascade to verifier (next model from available models)
        cascaded = true;
        const verifierModelConfig = availableModels[1];
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

  // ========================================================================
  // STREAMING APIS (v0.6+) - High-level streaming methods
  // ========================================================================

  /**
   * Run query with streaming and return complete result
   *
   * This method provides streaming with visual feedback and returns a complete
   * CascadeResult when done. Unlike streamEvents(), this collects all events
   * internally and returns the final result.
   *
   * Key features:
   * - Automatic manager selection (StreamManager vs ToolStreamManager)
   * - Visual feedback (optional pulsing indicator)
   * - Complete result with costs and metadata
   * - Tool support with automatic routing
   *
   * @param query - User query to process
   * @param options - Streaming options
   * @returns Complete CascadeResult with all metadata
   *
   * @example
   * ```typescript
   * const result = await agent.runStreaming('Explain TypeScript', {
   *   maxTokens: 100,
   *   enableVisual: true
   * });
   * console.log(result.content);
   * console.log(`Cost: $${result.totalCost}`);
   * ```
   */
  async runStreaming(
    query: string,
    options: RunStreamingOptions = {}
  ): Promise<CascadeResult> {
    // TODO: Full implementation in future milestone
    // For now, use runStream and collect result
    const events: StreamEvent[] = [];
    for await (const event of this.runStream(query, options)) {
      events.push(event);
    }

    // Extract result from COMPLETE event
    const completeEvent = events.find(e => e.type === StreamEventType.COMPLETE);
    if (completeEvent?.data?.result) {
      return completeEvent.data.result as CascadeResult;
    }

    // Fallback: construct result from events
    const chunks = events
      .filter(e => e.type === StreamEventType.CHUNK)
      .map(e => e.content)
      .join('');

    return {
      content: chunks,
      modelUsed: this.models[0].name,
      totalCost: 0,
      draftCost: 0,
      verifierCost: 0,
      latencyMs: 0,
      draftLatencyMs: 0,
      verifierLatencyMs: 0,
      cascaded: false,
      draftAccepted: true,
      complexity: 'unknown',
      savingsPercentage: 0,
      costSaved: 0,
      routingStrategy: 'direct',
      reason: 'Streaming fallback',
      hasToolCalls: false,
    };
  }

  /**
   * Stream events as async iterator
   *
   * This method yields StreamEvent objects as they occur, allowing fine-grained
   * control over streaming. Use this when you need to process events in real-time.
   *
   * Automatically selects the correct streaming manager:
   * - IF tools provided → ToolStreamManager (handles tool calls)
   * - ELSE → StreamManager (standard text streaming)
   *
   * @param query - User query to process
   * @param options - Streaming options
   * @yields StreamEvent objects with type, content, and data
   *
   * @example
   * ```typescript
   * for await (const event of agent.streamEvents('What is TypeScript?')) {
   *   switch (event.type) {
   *     case StreamEventType.CHUNK:
   *       process.stdout.write(event.content);
   *       break;
   *     case StreamEventType.COMPLETE:
   *       console.log(`\nDone! Cost: $${event.data.result.totalCost}`);
   *       break;
   *   }
   * }
   * ```
   */
  async *streamEvents(
    query: string,
    options: StreamEventsOptions = {}
  ): AsyncIterable<StreamEvent> {
    // TODO: Full implementation with StreamManager/ToolStreamManager in future milestone
    // For now, delegate to existing runStream
    for await (const event of this.runStream(query, options)) {
      yield event;
    }
  }

  /**
   * Stream responses with real-time events (alias for streamEvents)
   *
   * This is a simpler alias for streamEvents() that matches the documented API.
   * Use this method for most streaming needs.
   *
   * @param prompt - User query or prompt
   * @param options - Streaming options
   * @yields StreamEvent objects with incremental content
   *
   * @example
   * ```typescript
   * for await (const event of agent.stream('Tell me a story')) {
   *   if (event.type === StreamEventType.CHUNK) {
   *     process.stdout.write(event.content);
   *   } else if (event.type === StreamEventType.COMPLETE) {
   *     console.log(`\nCost: $${event.data.result?.totalCost || 0}`);
   *   }
   * }
   * ```
   */
  async *stream(
    prompt: string,
    options: StreamOptions = {}
  ): AsyncIterable<StreamEvent> {
    // Simple alias that delegates to streamEvents
    for await (const event of this.streamEvents(prompt, options)) {
      yield event;
    }
  }

  // ==================== ROUTER STATISTICS ====================

  /**
   * Get routing statistics from all routers
   *
   * Returns statistics about routing decisions made by PreRouter, ToolRouter, and TierRouter.
   * Useful for monitoring and debugging routing behavior.
   *
   * @returns Object containing statistics from each router
   *
   * @example
   * ```typescript
   * const agent = new CascadeAgent({ models: [...] });
   *
   * // Run some queries
   * await agent.run('Simple query');
   * await agent.run('Complex query');
   * await agent.run('Query with tools', { tools: [...] });
   *
   * // Get routing statistics
   * const stats = agent.getRouterStats();
   * console.log('PreRouter stats:', stats.preRouter);
   * console.log('ToolRouter stats:', stats.toolRouter);
   * ```
   */
  getRouterStats(): {
    preRouter: Record<string, any>;
    toolRouter: Record<string, any>;
    tierRouter?: Record<string, any>;
  } {
    return {
      preRouter: this.preRouter.getStats(),
      toolRouter: this.toolRouter.getStats(),
      tierRouter: this.tierRouter?.getStats(),
    };
  }

  /**
   * Reset routing statistics for all routers
   *
   * Clears all accumulated statistics from PreRouter, ToolRouter, and TierRouter.
   * Useful for starting fresh measurements or testing.
   *
   * @example
   * ```typescript
   * const agent = new CascadeAgent({ models: [...] });
   *
   * // Run some queries
   * await agent.run('Query 1');
   * await agent.run('Query 2');
   *
   * // Reset stats for new measurement period
   * agent.resetRouterStats();
   *
   * // Run more queries with clean stats
   * await agent.run('Query 3');
   * ```
   */
  resetRouterStats(): void {
    this.preRouter.resetStats();
    this.toolRouter.resetStats();
    this.tierRouter?.resetStats();
  }
}

/**
 * Options for runStreaming method
 */
export interface RunStreamingOptions extends RunOptions {
  /** Enable visual feedback (pulsing indicator) */
  enableVisual?: boolean;

  /** Complexity hint (override detection) */
  complexityHint?: string;

  /** Tool choice strategy */
  toolChoice?: any;
}

/**
 * Options for streamEvents method
 */
export interface StreamEventsOptions extends RunOptions {
  /** Complexity hint (override detection) */
  complexityHint?: string;

  /** Tool choice strategy */
  toolChoice?: any;
}
