import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { BaseMessage, AIMessage, AIMessageChunk } from '@langchain/core/messages';
import { ChatResult, ChatGeneration, ChatGenerationChunk } from '@langchain/core/outputs';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import type { CascadeConfig, CascadeResult } from './types.js';
import { calculateQuality, createCostMetadata } from './utils.js';

/**
 * CascadeWrapper - Transparent wrapper for LangChain chat models
 *
 * Preserves all LangChain model functionality while adding intelligent
 * cascade logic for cost optimization.
 *
 * @example
 * ```typescript
 * const drafter = new ChatOpenAI({ model: 'gpt-4o-mini' });
 * const verifier = new ChatOpenAI({ model: 'gpt-4o' });
 *
 * const cascade = new CascadeWrapper({
 *   drafter,
 *   verifier,
 *   qualityThreshold: 0.7
 * });
 *
 * const result = await cascade.invoke("What is TypeScript?");
 * ```
 */
export class CascadeWrapper extends BaseChatModel {
  private config: Required<CascadeConfig>;
  public drafter: BaseChatModel;
  public verifier: BaseChatModel;

  // Store last cascade result for metadata
  private lastCascadeResult?: CascadeResult;

  // Store bind kwargs to merge during _generate
  private bindKwargs: any = {};

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
      qualityValidator: config.qualityValidator ?? calculateQuality,
    };

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
    return 'cascade-wrapper';
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

    // STEP 1: Execute drafter (cheap, fast model)
    const drafterResult = await this.drafter._generate(messages, mergedOptions, runManager);
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
      verifierResult = await this.verifier._generate(messages, mergedOptions, runManager);
      finalResult = verifierResult;
    }

    // STEP 3: Calculate costs and metadata
    const latencyMs = Date.now() - startTime;
    const drafterModelName = (this.drafter as any).model || (this.drafter as any).modelName || this.drafter._llmType();
    const verifierModelName = (this.verifier as any).model || (this.verifier as any).modelName || this.verifier._llmType();
    const costMetadata = createCostMetadata(
      drafterResult,
      verifierResult,
      drafterModelName,
      verifierModelName,
      accepted,
      drafterQuality
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
        finalResult.llmOutput = {
          ...finalResult.llmOutput,
          cascade: costMetadata,
        };
      } catch (error) {
        console.warn('Failed to inject cascade metadata:', error);
      }
    }

    return finalResult;
  }

  /**
   * Pre-routing complexity detection for streaming
   * Analyzes message complexity to determine which model to use upfront
   *
   * @param messages - Input messages to analyze
   * @returns 'drafter' for simple queries, 'verifier' for complex queries
   */
  private _selectModelPreRoute(messages: BaseMessage[]): 'drafter' | 'verifier' {
    // Analyze the last user message for complexity indicators
    const lastMessage = messages[messages.length - 1];
    const content = typeof lastMessage.content === 'string'
      ? lastMessage.content
      : JSON.stringify(lastMessage.content);

    // Complexity heuristics
    const wordCount = content.split(/\s+/).length;
    const hasCodeBlock = /```/.test(content);
    const hasMultipleQuestions = (content.match(/\?/g) || []).length > 1;
    const hasComplexKeywords = /\b(analyze|compare|explain in detail|comprehensive|complex|advanced|technical)\b/i.test(content);
    const hasMultiStep = /\b(first|then|next|finally|step|steps)\b/i.test(content);
    const isLongContext = messages.length > 5;

    // Calculate complexity score (0-1)
    let complexityScore = 0;

    if (wordCount > 50) complexityScore += 0.25;
    if (wordCount > 100) complexityScore += 0.25;
    if (hasCodeBlock) complexityScore += 0.4; // Code blocks are complex
    if (hasMultipleQuestions) complexityScore += 0.3; // Multiple questions need more thought
    if (hasComplexKeywords) complexityScore += 0.4; // Strong indicator of complexity
    if (hasMultiStep) complexityScore += 0.3; // Multi-step requires planning
    if (isLongContext) complexityScore += 0.4; // Long context needs verifier

    // Route to verifier if complexity exceeds threshold
    // Use a lower threshold (0.35) for pre-routing to catch borderline cases
    const COMPLEXITY_THRESHOLD = 0.35;
    return complexityScore >= COMPLEXITY_THRESHOLD ? 'verifier' : 'drafter';
  }

  /**
   * Streaming support with pre-routing
   * Analyzes query complexity upfront and streams from the appropriate model
   */
  async *_streamResponseChunks(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): AsyncGenerator<ChatGenerationChunk> {
    const startTime = Date.now();

    // Merge bind kwargs with options
    const mergedOptions = { ...this.bindKwargs, ...options };

    // STEP 1: Pre-route based on complexity
    const selectedModel = this._selectModelPreRoute(messages);
    const model = selectedModel === 'drafter' ? this.drafter : this.verifier;

    // STEP 2: Stream from selected model
    const chunks: ChatGenerationChunk[] = [];

    try {
      // Call the underlying model's _streamResponseChunks directly
      for await (const chunk of model._streamResponseChunks(messages, mergedOptions, runManager)) {
        // Collect chunks for metadata
        chunks.push(chunk);

        // Yield chunk to caller
        yield chunk;
      }
    } catch (error) {
      // If streaming fails, fall back to non-streaming
      console.warn(`Streaming failed for ${selectedModel}, falling back to non-streaming:`, error);

      const result = await model._generate(messages, mergedOptions, runManager);

      // Convert result to single chunk and yield
      if (result.generations[0]) {
        const chunk = new ChatGenerationChunk({
          text: result.generations[0].text,
          message: new AIMessageChunk(result.generations[0].text),
        });
        chunks.push(chunk);
        yield chunk;
      }
    }

    // STEP 3: Store metadata after streaming completes
    const latencyMs = Date.now() - startTime;
    const drafterModelName = (this.drafter as any).model || (this.drafter as any).modelName || this.drafter._llmType();
    const verifierModelName = (this.verifier as any).model || (this.verifier as any).modelName || this.verifier._llmType();

    // Create minimal metadata for streaming
    // We don't have quality scores or cost data during streaming
    this.lastCascadeResult = {
      content: chunks.map(c => c.text).join(''),
      modelUsed: selectedModel,
      drafterQuality: selectedModel === 'drafter' ? 1.0 : 0.0, // Assumed based on pre-routing
      accepted: selectedModel === 'drafter',
      drafterCost: 0, // Not available during streaming
      verifierCost: 0,
      totalCost: 0,
      savingsPercentage: 0,
      latencyMs,
      streaming: true,
      preRouted: true,
    };
  }

  /**
   * Get the last cascade execution result
   */
  getLastCascadeResult(): CascadeResult | undefined {
    return this.lastCascadeResult;
  }

  /**
   * Handle chainable methods - bind()
   * Creates a new CascadeWrapper with bound parameters
   */
  override bind(kwargs: any): CascadeWrapper {
    // Merge new kwargs with existing ones
    const mergedKwargs = { ...this.bindKwargs, ...kwargs };

    return new CascadeWrapper(
      {
        drafter: this.drafter,
        verifier: this.verifier,
        qualityThreshold: this.config.qualityThreshold,
        enableCostTracking: this.config.enableCostTracking,
        qualityValidator: this.config.qualityValidator,
      },
      mergedKwargs
    );
  }

  /**
   * Handle chainable methods - bindTools()
   * Creates a new CascadeWrapper with bound tools
   */
  bindTools(tools: any[], kwargs?: any): any {
    if (typeof (this.drafter as any).bindTools !== 'function') {
      throw new Error('Drafter model does not support bindTools()');
    }

    const boundDrafter = (this.drafter as any).bindTools(tools, kwargs);
    const boundVerifier = (this.verifier as any).bindTools(tools, kwargs);

    return new CascadeWrapper({
      drafter: boundDrafter,
      verifier: boundVerifier,
      qualityThreshold: this.config.qualityThreshold,
      enableCostTracking: this.config.enableCostTracking,
      qualityValidator: this.config.qualityValidator,
    });
  }

  /**
   * Handle chainable methods - withStructuredOutput()
   * Creates a new CascadeWrapper with structured output
   */
  withStructuredOutput(outputSchema: any, config?: any): any {
    if (typeof (this.drafter as any).withStructuredOutput !== 'function') {
      throw new Error('Drafter model does not support withStructuredOutput()');
    }

    const boundDrafter = (this.drafter as any).withStructuredOutput(outputSchema, config);
    const boundVerifier = (this.verifier as any).withStructuredOutput(outputSchema, config);

    return new CascadeWrapper({
      drafter: boundDrafter,
      verifier: boundVerifier,
      qualityThreshold: this.config.qualityThreshold,
      enableCostTracking: this.config.enableCostTracking,
      qualityValidator: this.config.qualityValidator,
    });
  }
}
