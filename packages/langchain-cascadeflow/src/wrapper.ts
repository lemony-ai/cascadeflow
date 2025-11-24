import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { BaseMessage, AIMessage, ChatMessage, HumanMessage } from '@langchain/core/messages';
import { ChatResult, ChatGeneration, ChatGenerationChunk } from '@langchain/core/outputs';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import type { CascadeConfig, CascadeResult } from './types.js';
import { calculateQuality, createCostMetadata } from './utils.js';
import { PreRouter } from './routers/pre-router.js';
import { RoutingStrategy } from './routers/base.js';
import type { QueryComplexity } from './complexity.js';

/**
 * CascadeFlow - Transparent wrapper for LangChain chat models
 *
 * Preserves all LangChain model functionality while adding intelligent
 * cascade logic for cost optimization.
 *
 * @example
 * ```typescript
 * const drafter = new ChatOpenAI({ model: 'gpt-4o-mini' });
 * const verifier = new ChatOpenAI({ model: 'gpt-4o' });
 *
 * const cascade = new CascadeFlow({
 *   drafter,
 *   verifier,
 *   qualityThreshold: 0.7
 * });
 *
 * const result = await cascade.invoke("What is TypeScript?");
 * ```
 */
export class CascadeFlow extends BaseChatModel {
  private config: Required<Omit<CascadeConfig, 'preRouter'>> & { preRouter?: PreRouter };
  public drafter: BaseChatModel;
  public verifier: BaseChatModel;

  // Store last cascade result for metadata
  private lastCascadeResult?: CascadeResult;

  // Store bind kwargs to merge during _generate
  private bindKwargs: any = {};

  // PreRouter for complexity-based routing
  private preRouter?: PreRouter;

  constructor(config: CascadeConfig, bindKwargs: any = {}) {
    super({});

    this.drafter = config.drafter;
    this.verifier = config.verifier;
    this.bindKwargs = bindKwargs;

    // Set defaults
    this.config = {
      drafter: config.drafter,
      verifier: config.verifier,
      qualityThreshold: config.qualityThreshold ?? 0.7,
      enableCostTracking: config.enableCostTracking ?? true,
      costTrackingProvider: config.costTrackingProvider ?? 'langsmith',
      qualityValidator: config.qualityValidator ?? calculateQuality,
      enablePreRouter: config.enablePreRouter ?? true,  // Match Python default
      preRouter: config.preRouter,
      cascadeComplexities: config.cascadeComplexities ?? ['trivial', 'simple', 'moderate'],
    };

    // Initialize PreRouter if enabled
    if (this.config.enablePreRouter) {
      this.preRouter = this.config.preRouter ?? new PreRouter({
        cascadeComplexities: this.config.cascadeComplexities,
      });
    }

    // Return a Proxy for method delegation
    return new Proxy(this, {
      get(target, prop, receiver) {
        // Check if method exists on target (CascadeWrapper) first
        if (prop in target || typeof prop === 'symbol') {
          return Reflect.get(target, prop, receiver);
        }

        // Delegate to drafter for unknown methods/properties
        const drafterValue = Reflect.get(target.drafter, prop);

        // If it's a method, bind it to drafter
        if (typeof drafterValue === 'function') {
          return (...args: any[]) => drafterValue.apply(target.drafter, args);
        }

        return drafterValue;
      },

      set(target, prop, value, receiver) {
        // Set on both drafter and verifier to keep them in sync
        if (prop in target.drafter && prop in target.verifier) {
          Reflect.set(target.drafter, prop, value);
          Reflect.set(target.verifier, prop, value);
          return true;
        }

        return Reflect.set(target, prop, value, receiver);
      },
    });
  }

  /**
   * Required LangChain method - returns the LLM type identifier
   */
  _llmType(): string {
    return 'cascadeflow';
  }

  /**
   * Override invoke to add agent metadata to messages
   * The agent role is stored in metadata instead of as a message role
   */
  override async invoke(
    input: BaseMessage[] | string,
    options?: any
  ): Promise<any> {
    // Convert string input to HumanMessage (standard LangChain approach)
    // We'll add agent metadata in the options instead
    let processedInput: BaseMessage[];

    if (typeof input === 'string') {
      processedInput = [new HumanMessage({ content: input })];
    } else if (Array.isArray(input)) {
      processedInput = input;
    } else {
      // Single message object
      processedInput = [input as BaseMessage];
    }

    // Add agent role to metadata in options
    const enrichedOptions = {
      ...options,
      metadata: {
        ...options?.metadata,
        agent_role: 'cascade_agent',
      },
    };

    return super.invoke(processedInput, enrichedOptions);
  }

  /**
   * Core cascade generation logic
   * Implements the speculative execution pattern
   */
  async _generate(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): Promise<ChatResult> {
    const startTime = Date.now();

    // Merge bind kwargs with options
    const mergedOptions = { ...this.bindKwargs, ...options };

    // STEP 0: PreRouter - Check if we should bypass cascade
    let useCascade = true;
    if (this.preRouter) {
      // Extract query text from messages
      const queryText = messages
        .map((msg) => {
          if (typeof msg.content === 'string') {
            return msg.content;
          } else if (Array.isArray(msg.content)) {
            return msg.content
              .map((part: any) => (typeof part === 'string' ? part : part.text || ''))
              .join(' ');
          }
          return '';
        })
        .join('\n');

      // Route based on complexity
      const routingDecision = await this.preRouter.route(queryText);
      useCascade = routingDecision.strategy === RoutingStrategy.CASCADE;

      // If direct routing, skip drafter and go straight to verifier
      if (!useCascade) {
        const verifierMessage = await this.verifier.invoke(messages, mergedOptions);
        const verifierResult: ChatResult = {
          generations: [
            {
              text: typeof verifierMessage.content === 'string'
                ? verifierMessage.content
                : JSON.stringify(verifierMessage.content),
              message: verifierMessage,
            },
          ],
          llmOutput: (verifierMessage as any).response_metadata || {},
        };

        const latencyMs = Date.now() - startTime;
        const verifierModelName = (this.verifier as any).model || (this.verifier as any).modelName ||
          (typeof this.verifier._llmType === 'function' ? this.verifier._llmType() : 'unknown');

        // Store cascade result (direct to verifier)
        this.lastCascadeResult = {
          content: verifierResult.generations[0].text,
          modelUsed: 'verifier',
          drafterQuality: undefined,
          accepted: false,
          drafterCost: 0,
          verifierCost: 0, // LangSmith will calculate this
          totalCost: 0,
          savingsPercentage: 0,
          latencyMs,
        };

        // Inject metadata if cost tracking enabled
        if (this.config.enableCostTracking) {
          try {
            const metadata = {
              cascade_decision: 'direct',
              model_used: 'verifier',
              routing_reason: routingDecision.reason,
              complexity: routingDecision.metadata.complexity,
            };

            verifierResult.llmOutput = {
              ...verifierResult.llmOutput,
              cascade: metadata,
            };

            if (verifierResult.generations[0]?.message) {
              const message = verifierResult.generations[0].message;
              if ('response_metadata' in message) {
                (message as any).response_metadata = {
                  ...(message as any).response_metadata,
                  cascade: metadata,
                };
              }
              (message as any).llmOutput = {
                ...(message as any).llmOutput,
                cascade: metadata,
              };
            }
          } catch (error) {
            console.warn('Failed to inject cascade metadata:', error);
          }
        }

        return verifierResult;
      }
    }

    // STEP 1: Execute drafter (cheap, fast model)
    // Use invoke() to ensure LangSmith captures the model trace
    const drafterMessage = await this.drafter.invoke(messages, mergedOptions);
    const drafterResult: ChatResult = {
      generations: [
        {
          text: typeof drafterMessage.content === 'string'
            ? drafterMessage.content
            : JSON.stringify(drafterMessage.content),
          message: drafterMessage,
        },
      ],
      llmOutput: (drafterMessage as any).response_metadata || {},
    };

    const drafterQuality = this.config.qualityValidator
      ? await this.config.qualityValidator(drafterResult)
      : calculateQuality(drafterResult);

    // STEP 2: Check quality threshold
    const accepted = drafterQuality >= this.config.qualityThreshold;

    let finalResult: ChatResult;
    let verifierResult: ChatResult | null = null;

    if (accepted) {
      // Quality is sufficient - use drafter response
      finalResult = drafterResult;
    } else {
      // Quality insufficient - execute verifier (expensive, accurate model)
      // Use invoke() to ensure LangSmith captures the model trace
      const verifierMessage = await this.verifier.invoke(messages, mergedOptions);
      const vResult: ChatResult = {
        generations: [
          {
            text: typeof verifierMessage.content === 'string'
              ? verifierMessage.content
              : JSON.stringify(verifierMessage.content),
            message: verifierMessage,
          },
        ],
        llmOutput: (verifierMessage as any).response_metadata || {},
      };
      verifierResult = vResult;
      finalResult = vResult;
    }

    // STEP 3: Calculate costs and metadata
    const latencyMs = Date.now() - startTime;
    const drafterModelName = (this.drafter as any).model || (this.drafter as any).modelName ||
      (typeof this.drafter._llmType === 'function' ? this.drafter._llmType() : 'unknown');
    const verifierModelName = (this.verifier as any).model || (this.verifier as any).modelName ||
      (typeof this.verifier._llmType === 'function' ? this.verifier._llmType() : 'unknown');
    const costMetadata = createCostMetadata(
      drafterResult,
      verifierResult,
      drafterModelName,
      verifierModelName,
      accepted,
      drafterQuality,
      this.config.costTrackingProvider
    );

    // Store cascade result
    this.lastCascadeResult = {
      content: finalResult.generations[0].text,
      modelUsed: accepted ? 'drafter' : 'verifier',
      drafterQuality,
      accepted,
      drafterCost: costMetadata.drafterCost,
      verifierCost: costMetadata.verifierCost,
      totalCost: costMetadata.totalCost,
      savingsPercentage: costMetadata.savingsPercentage,
      latencyMs,
    };

    // STEP 4: Inject cost metadata into llmOutput (if enabled)
    // LangSmith will automatically capture this metadata in traces
    if (this.config.enableCostTracking) {
      try {
        // Inject into llmOutput
        finalResult.llmOutput = {
          ...finalResult.llmOutput,
          cascade: costMetadata,
        };

        // Also inject into message's response_metadata for invoke() results
        if (finalResult.generations[0]?.message) {
          const message = finalResult.generations[0].message;
          if ('response_metadata' in message) {
            (message as any).response_metadata = {
              ...(message as any).response_metadata,
              cascade: costMetadata,
            };
          }
          // Also set as llmOutput property for backward compatibility
          (message as any).llmOutput = {
            ...(message as any).llmOutput,
            cascade: costMetadata,
          };
        }
      } catch (error) {
        console.warn('Failed to inject cascade metadata:', error);
      }
    }

    return finalResult;
  }

  /**
   * Get the last cascade execution result
   */
  getLastCascadeResult(): CascadeResult | undefined {
    return this.lastCascadeResult;
  }

  /**
   * Stream responses with optimistic drafter execution
   *
   * Uses the proven cascade streaming pattern:
   * 1. Stream drafter optimistically (user sees real-time output)
   * 2. Collect chunks and check quality after completion
   * 3. If quality insufficient: show switch message + stream verifier
   *
   * @param messages - Input messages
   * @param options - Streaming options
   * @returns AsyncGenerator yielding chunks
   */
  override async *_streamResponseChunks(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): AsyncGenerator<ChatGenerationChunk> {
    const startTime = Date.now();

    // Merge bind kwargs with options
    const mergedOptions = { ...this.bindKwargs, ...options };

    // STEP 0: PreRouter - Check if we should bypass cascade
    let useCascade = true;
    if (this.preRouter) {
      const queryText = messages
        .map((msg) => {
          if (typeof msg.content === 'string') {
            return msg.content;
          } else if (Array.isArray(msg.content)) {
            return msg.content
              .map((part: any) => (typeof part === 'string' ? part : part.text || ''))
              .join(' ');
          }
          return '';
        })
        .join('\n');

      const routingDecision = await this.preRouter.route(queryText);
      useCascade = routingDecision.strategy === RoutingStrategy.CASCADE;

      // If direct routing, stream verifier only
      if (!useCascade) {
        for await (const chunk of this.verifier._streamResponseChunks(
          messages,
          mergedOptions,
          runManager
        )) {
          yield chunk;
        }
        return;
      }
    }

    // STEP 1: Stream drafter optimistically
    const drafterChunks: ChatGenerationChunk[] = [];
    let drafterContent = '';

    // Stream from drafter in real-time
    for await (const chunk of this.drafter._streamResponseChunks(
      messages,
      mergedOptions,
      runManager
    )) {
      drafterChunks.push(chunk);

      // Extract text content from chunk
      const chunkText = typeof chunk.message.content === 'string'
        ? chunk.message.content
        : '';
      drafterContent += chunkText;

      // Yield chunk immediately for real-time streaming
      yield chunk;
    }

    // STEP 2: Quality check after drafter completes
    const drafterResult: ChatResult = {
      generations: drafterChunks.map(chunk => ({
        text: typeof chunk.message.content === 'string' ? chunk.message.content : '',
        message: chunk.message,
      })),
      llmOutput: {},
    };

    const drafterQuality = this.config.qualityValidator
      ? await this.config.qualityValidator(drafterResult)
      : calculateQuality(drafterResult);

    const accepted = drafterQuality >= this.config.qualityThreshold;

    // STEP 3: If quality insufficient, cascade to verifier
    if (!accepted) {
      // Import ChatGenerationChunk and AIMessageChunk for switch message
      const { ChatGenerationChunk } = await import('@langchain/core/outputs');
      const { AIMessageChunk } = await import('@langchain/core/messages');

      // Emit switch notification
      const verifierModelName = (this.verifier as any).model ||
        (this.verifier as any).modelName || 'verifier';
      const switchMessage = `\n\n⤴ Cascading to ${verifierModelName} (quality: ${drafterQuality.toFixed(2)} < ${this.config.qualityThreshold})\n\n`;

      yield new ChatGenerationChunk({
        text: switchMessage,
        message: new AIMessageChunk({ content: switchMessage }),
      });

      // Stream from verifier
      for await (const chunk of this.verifier._streamResponseChunks(
        messages,
        mergedOptions,
        runManager
      )) {
        yield chunk;
      }
    }

    // Store cascade result (simplified for streaming)
    const latencyMs = Date.now() - startTime;
    this.lastCascadeResult = {
      content: drafterContent,
      modelUsed: accepted ? 'drafter' : 'verifier',
      drafterQuality,
      accepted,
      drafterCost: 0,
      verifierCost: 0,
      totalCost: 0,
      savingsPercentage: accepted ? 50 : 0,
      latencyMs,
    };
  }

  /**
   * Handle chainable methods - bind()
   * Creates a new CascadeFlow with bound parameters
   */
  override bind(kwargs: any): CascadeFlow {
    // Merge new kwargs with existing ones
    const mergedKwargs = { ...this.bindKwargs, ...kwargs };

    return new CascadeFlow(
      {
        drafter: this.drafter,
        verifier: this.verifier,
        qualityThreshold: this.config.qualityThreshold,
        enableCostTracking: this.config.enableCostTracking,
        costTrackingProvider: this.config.costTrackingProvider,
        qualityValidator: this.config.qualityValidator,
        enablePreRouter: this.config.enablePreRouter,
        preRouter: this.config.preRouter,
        cascadeComplexities: this.config.cascadeComplexities,
      },
      mergedKwargs
    );
  }

  /**
   * Handle chainable methods - bindTools()
   * Creates a new CascadeFlow with bound tools
   */
  bindTools(tools: any[], kwargs?: any): any {
    if (typeof (this.drafter as any).bindTools !== 'function') {
      throw new Error('Drafter model does not support bindTools()');
    }

    const boundDrafter = (this.drafter as any).bindTools(tools, kwargs);
    const boundVerifier = (this.verifier as any).bindTools(tools, kwargs);

    return new CascadeFlow({
      drafter: boundDrafter,
      verifier: boundVerifier,
      qualityThreshold: this.config.qualityThreshold,
      enableCostTracking: this.config.enableCostTracking,
      costTrackingProvider: this.config.costTrackingProvider,
      qualityValidator: this.config.qualityValidator,
      enablePreRouter: this.config.enablePreRouter,
      preRouter: this.config.preRouter,
      cascadeComplexities: this.config.cascadeComplexities,
    });
  }

  /**
   * Handle chainable methods - withStructuredOutput()
   * Creates a new CascadeFlow with structured output
   */
  withStructuredOutput(outputSchema: any, config?: any): any {
    if (typeof (this.drafter as any).withStructuredOutput !== 'function') {
      throw new Error('Drafter model does not support withStructuredOutput()');
    }

    const boundDrafter = (this.drafter as any).withStructuredOutput(outputSchema, config);
    const boundVerifier = (this.verifier as any).withStructuredOutput(outputSchema, config);

    return new CascadeFlow({
      drafter: boundDrafter,
      verifier: boundVerifier,
      qualityThreshold: this.config.qualityThreshold,
      enableCostTracking: this.config.enableCostTracking,
      costTrackingProvider: this.config.costTrackingProvider,
      qualityValidator: this.config.qualityValidator,
      enablePreRouter: this.config.enablePreRouter,
      preRouter: this.config.preRouter,
      cascadeComplexities: this.config.cascadeComplexities,
    });
  }
}
