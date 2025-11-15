import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { BaseMessage, AIMessage } from '@langchain/core/messages';
import { ChatResult, ChatGeneration } from '@langchain/core/outputs';
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

    // STEP 4: Inject cost metadata into LangSmith (if enabled and run_manager exists)
    if (this.config.enableCostTracking && runManager) {
      try {
        // Inject metadata via callback metadata
        // LangSmith will automatically capture this in traces
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
