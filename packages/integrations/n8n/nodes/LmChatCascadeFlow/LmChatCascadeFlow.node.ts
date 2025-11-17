import type {
  INodeType,
  INodeTypeDescription,
  ISupplyDataFunctions,
  SupplyData,
} from 'n8n-workflow';

import { NodeConnectionType, NodeOperationError } from 'n8n-workflow';

import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import { BaseMessage } from '@langchain/core/messages';
import { ChatResult, ChatGeneration, ChatGenerationChunk } from '@langchain/core/outputs';

// Quality validation, cost tracking, and routing - optional import, fallback if unavailable
let QualityValidator: any;
let CASCADE_QUALITY_CONFIG: any;
let CostCalculator: any;
let ComplexityDetector: any;
let PreRouter: any;
try {
  const cascadeCore = require('@cascadeflow/core');
  QualityValidator = cascadeCore.QualityValidator;
  CASCADE_QUALITY_CONFIG = cascadeCore.CASCADE_QUALITY_CONFIG;
  CostCalculator = cascadeCore.CostCalculator;
  ComplexityDetector = cascadeCore.ComplexityDetector;
  PreRouter = cascadeCore.PreRouter;
} catch (e) {
  // @cascadeflow/core not available - use simple validation and estimates
  console.warn('⚠️  @cascadeflow/core not available, using fallbacks');
}

/**
 * Custom CascadeChatModel that wraps two models (drafter and verifier)
 * and implements cascading logic with cost tracking
 */
class CascadeChatModel extends BaseChatModel {
  drafterModel: BaseChatModel;
  verifierModelGetter: () => Promise<BaseChatModel>;
  qualityThreshold: number;

  // Cost tracking
  private drafterCost: number = 0;
  private verifierCost: number = 0;
  private drafterCount: number = 0;
  private verifierCount: number = 0;

  // Lazy-loaded verifier
  private verifierModel?: BaseChatModel;

  // Quality validator with CASCADE config (optional)
  private qualityValidator: any;

  // Cost calculator for accurate token-based cost tracking
  private costCalculator: any;

  // Complexity detector for intelligent routing
  private complexityDetector: any;

  // PreRouter for complexity-based direct routing
  private preRouter: any;

  constructor(
    drafterModel: BaseChatModel,
    verifierModelGetter: () => Promise<BaseChatModel>,
    qualityThreshold: number = 0.7,
    useSemanticValidation: boolean = true,
    useAlignmentScoring: boolean = true,
    useComplexityRouting: boolean = true
  ) {
    super({});
    this.drafterModel = drafterModel;
    this.verifierModelGetter = verifierModelGetter;
    this.qualityThreshold = qualityThreshold;

    // Initialize quality validator with CASCADE-optimized config + semantic validation
    if (QualityValidator && CASCADE_QUALITY_CONFIG) {
      try {
        this.qualityValidator = new QualityValidator({
          ...CASCADE_QUALITY_CONFIG,
          minConfidence: qualityThreshold,
          useSemanticValidation,    // Enable semantic ML-based validation
          useAlignmentScoring,       // Enable query-response alignment scoring
          semanticThreshold: 0.5,    // Semantic similarity threshold
        });
        console.log('✅ CascadeFlow quality validator initialized');
        if (useSemanticValidation) {
          console.log('   📊 Semantic validation enabled (requires @cascadeflow/ml)');
        }
        if (useAlignmentScoring) {
          console.log('   🎯 Alignment scoring enabled');
        }
      } catch (e) {
        console.warn('⚠️  Quality validator initialization failed, using simple check');
        this.qualityValidator = null;
      }
    } else {
      this.qualityValidator = null;
    }

    // Initialize cost calculator if available
    if (CostCalculator) {
      try {
        this.costCalculator = new CostCalculator();
        console.log('💰 CascadeFlow cost calculator initialized');
      } catch (e) {
        console.warn('⚠️  Cost calculator initialization failed, using estimates');
        this.costCalculator = null;
      }
    } else {
      this.costCalculator = null;
    }

    // Initialize complexity detector and PreRouter if enabled
    if (useComplexityRouting && ComplexityDetector && PreRouter) {
      try {
        this.complexityDetector = new ComplexityDetector();
        // Note: PreRouter needs model configs, but we only have 2 models in n8n (drafter/verifier)
        // We'll use complexity detection to decide: trivial/simple → drafter, hard/expert → direct verifier
        this.preRouter = null; // Not using full PreRouter since we only have 2 models
        console.log('🧠 CascadeFlow complexity-based routing enabled');
      } catch (e) {
        console.warn('⚠️  Complexity detector initialization failed');
        this.complexityDetector = null;
        this.preRouter = null;
      }
    } else {
      this.complexityDetector = null;
      this.preRouter = null;
    }
  }

  private async getVerifierModel(): Promise<BaseChatModel> {
    if (!this.verifierModel) {
      console.log('   🔄 Loading verifier model from TOP port (labeled "Verifier")...');
      this.verifierModel = await this.verifierModelGetter();
      const verifierInfo = this.getModelInfo(this.verifierModel);
      console.log(`   ✓ Verifier model loaded: ${verifierInfo}`);
    }
    return this.verifierModel;
  }

  /**
   * Helper to get model info string (type and name)
   */
  private getModelInfo(model: BaseChatModel): string {
    const type = typeof model._llmType === 'function' ? model._llmType() : 'unknown';
    const modelName = (model as any).modelName || (model as any).model || 'unknown';
    return `${type} (${modelName})`;
  }

  /**
   * Check if message contains tool calls
   * Tool calls can be in additional_kwargs.tool_calls or additional_kwargs.function_call
   */
  private hasToolCalls(message: BaseMessage): boolean {
    const additionalKwargs = (message as any).additional_kwargs || {};

    // Check for tool_calls array (OpenAI format)
    if (additionalKwargs.tool_calls && Array.isArray(additionalKwargs.tool_calls) && additionalKwargs.tool_calls.length > 0) {
      return true;
    }

    // Check for function_call object (legacy format)
    if (additionalKwargs.function_call && typeof additionalKwargs.function_call === 'object') {
      return true;
    }

    // Check for tool_calls in response_metadata (Anthropic format)
    const responseMetadata = (message as any).response_metadata || {};
    if (responseMetadata.tool_calls && Array.isArray(responseMetadata.tool_calls) && responseMetadata.tool_calls.length > 0) {
      return true;
    }

    return false;
  }

  /**
   * Get count of tool calls in message
   */
  private getToolCallsCount(message: BaseMessage): number {
    const additionalKwargs = (message as any).additional_kwargs || {};
    const responseMetadata = (message as any).response_metadata || {};

    // Count tool_calls array
    if (additionalKwargs.tool_calls && Array.isArray(additionalKwargs.tool_calls)) {
      return additionalKwargs.tool_calls.length;
    }

    // Count function_call (legacy - counts as 1)
    if (additionalKwargs.function_call) {
      return 1;
    }

    // Count Anthropic format tool_calls
    if (responseMetadata.tool_calls && Array.isArray(responseMetadata.tool_calls)) {
      return responseMetadata.tool_calls.length;
    }

    return 0;
  }

  /**
   * Calculate accurate cost from message token usage
   * Falls back to rough estimates if cost calculator unavailable
   */
  private async calculateMessageCost(
    message: BaseMessage,
    model: BaseChatModel
  ): Promise<number> {
    // Extract token usage from response metadata
    const responseMetadata = (message as any).response_metadata || {};
    const tokenUsage = responseMetadata.tokenUsage || responseMetadata.usage || {};

    const inputTokens = tokenUsage.promptTokens || tokenUsage.prompt_tokens || 0;
    const outputTokens = tokenUsage.completionTokens || tokenUsage.completion_tokens || 0;

    // Get model name
    const modelName = (model as any).modelName || (model as any).model || 'unknown';

    // Use cost calculator if available
    if (this.costCalculator && inputTokens > 0) {
      try {
        const cost = await this.costCalculator.calculateCost({
          model: modelName,
          inputTokens,
          outputTokens,
        });
        return cost;
      } catch (e) {
        console.warn(`Cost calculation failed for ${modelName}, using estimate`);
      }
    }

    // Fallback to rough estimates based on model name
    const estimatesPerMillion: Record<string, { input: number; output: number }> = {
      'gpt-4o-mini': { input: 0.15, output: 0.6 },
      'gpt-4o': { input: 5.0, output: 15.0 },
      'gpt-4-turbo': { input: 10.0, output: 30.0 },
      'gpt-4': { input: 30.0, output: 60.0 },
      'gpt-3.5-turbo': { input: 0.5, output: 1.5 },
      'claude-3-5-sonnet': { input: 3.0, output: 15.0 },
      'claude-3-haiku': { input: 0.25, output: 1.25 },
      default: { input: 1.0, output: 2.0 },
    };

    // Find matching estimate
    let estimate = estimatesPerMillion.default;
    for (const [key, value] of Object.entries(estimatesPerMillion)) {
      if (modelName.includes(key)) {
        estimate = value;
        break;
      }
    }

    const cost =
      (inputTokens / 1_000_000) * estimate.input +
      (outputTokens / 1_000_000) * estimate.output;

    return cost;
  }

  /**
   * Simple quality validation fallback (when @cascadeflow/core not available)
   */
  private simpleQualityCheck(responseText: string): { passed: boolean; confidence: number; score: number; reason: string } {
    const wordCount = responseText.split(/\s+/).length;

    // Base confidence on response length and structure
    let confidence = 0.75;

    // Very short responses get lower confidence
    if (wordCount < 5) {
      confidence = 0.50;
    } else if (wordCount < 15) {
      confidence = 0.65;
    } else if (wordCount > 30) {
      confidence = 0.85;
    }

    // Check for uncertainty markers
    const uncertaintyMarkers = ['i don\'t know', 'i\'m not sure', 'unclear', 'uncertain'];
    const hasUncertainty = uncertaintyMarkers.some(marker => responseText.toLowerCase().includes(marker));
    if (hasUncertainty) {
      confidence -= 0.20;
    }

    const passed = confidence >= this.qualityThreshold;
    const reason = passed
      ? `Simple check passed (confidence: ${confidence.toFixed(2)} >= ${this.qualityThreshold})`
      : `Simple check failed (confidence: ${confidence.toFixed(2)} < ${this.qualityThreshold})`;

    return { passed, confidence, score: confidence, reason };
  }

  _llmType(): string {
    return 'cascade';
  }

  async _generate(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): Promise<ChatResult> {
    try {
      // Step 1: Detect query complexity (if enabled)
      const queryText = messages.map(m => m.content.toString()).join(' ');
      let complexity: string | undefined;
      let shouldSkipDrafter = false;

      if (this.complexityDetector) {
        try {
          const complexityResult = await this.complexityDetector.detectComplexity(queryText);
          complexity = complexityResult.level;

          // Skip drafter for hard/expert queries - go directly to verifier
          if (complexity === 'hard' || complexity === 'expert') {
            shouldSkipDrafter = true;
            await runManager?.handleText(`🧠 Complexity: ${complexity} → Routing directly to verifier (skip drafter)\n`);
            console.log(`🧠 Complexity: ${complexity} → Direct verifier route`);
          } else {
            await runManager?.handleText(`🧠 Complexity: ${complexity} → Trying drafter first\n`);
            console.log(`🧠 Complexity: ${complexity} → Drafter route`);
          }
        } catch (e) {
          console.warn('Complexity detection failed, using normal flow');
        }
      }

      // Step 1a: If complexity routing says skip drafter, go directly to verifier
      if (shouldSkipDrafter) {
        const verifierModel = await this.getVerifierModel();
        const verifierInfo = this.getModelInfo(verifierModel);

        await runManager?.handleText(`⚡ Direct route: Using verifier for ${complexity} query\n`);

        const verifierStartTime = Date.now();
        const verifierMessage = await verifierModel.invoke(messages, options);
        const verifierLatency = Date.now() - verifierStartTime;

        this.verifierCount++;

        const verifierCost = await this.calculateMessageCost(verifierMessage, verifierModel);

        const flowLog = `\n┌────────────────────────────────────────────┐\n│  ⚡ FLOW: DIRECT VERIFIER (SMART ROUTE)  │\n└────────────────────────────────────────────┘\n   Query → Complexity Check (${complexity}) → Verifier → Response\n   🧠 Smart routing: Skipped drafter for complex query\n   Model used: ${verifierInfo}\n   Latency: ${verifierLatency}ms\n   💰 Cost: $${verifierCost.toFixed(6)}\n   📊 Stats: ${this.drafterCount} drafter, ${this.verifierCount} verifier\n`;

        await runManager?.handleText(flowLog);
        console.log(flowLog);

        if (!verifierMessage.response_metadata) {
          (verifierMessage as any).response_metadata = {};
        }
        (verifierMessage as any).response_metadata.cascadeflow = {
          flow: 'direct_verifier',
          complexity,
          latency_ms: verifierLatency,
          cost_usd: verifierCost,
          model_used: 'verifier',
          reason: `Query complexity (${complexity}) warranted direct verifier routing`
        };

        return {
          generations: [{
            text: verifierMessage.content.toString(),
            message: verifierMessage,
          }],
        };
      }

      // Step 2: Try the drafter model (normal flow)
      const drafterInfo = this.getModelInfo(this.drafterModel);
      await runManager?.handleText(`🎯 CascadeFlow: Trying drafter model (from BOTTOM port): ${drafterInfo}\n`);
      console.log(`🎯 CascadeFlow: Trying drafter model (from BOTTOM port): ${drafterInfo}`);
      const drafterStartTime = Date.now();
      const drafterMessage = await this.drafterModel.invoke(messages, options);
      const drafterLatency = Date.now() - drafterStartTime;

      this.drafterCount++;

      // Step 2: Check if response contains tool calls
      // Tool calls skip quality validation and pass through directly
      const hasToolCalls = this.hasToolCalls(drafterMessage);

      if (hasToolCalls) {
        const toolCallsCount = this.getToolCallsCount(drafterMessage);
        const toolLog = `   🔧 Tool calls detected (${toolCallsCount}) - bypassing quality check\n`;
        await runManager?.handleText(toolLog);
        console.log(toolLog);

        const flowLog = `\n┌──────────────────────────────────────────┐\n│  🔧 FLOW: TOOL CALLS (DIRECT PASS)      │\n└──────────────────────────────────────────┘\n   Query → Drafter → Tool Calls (${toolCallsCount}) → Response\n   ⚡ Tool calling: Drafter generated tool calls\n   Model used: ${drafterInfo}\n   Latency: ${drafterLatency}ms\n   📊 Stats: ${this.drafterCount} drafter, ${this.verifierCount} verifier\n`;

        await runManager?.handleText(flowLog);
        console.log(flowLog);

        // Add tool call metadata
        if (!drafterMessage.response_metadata) {
          (drafterMessage as any).response_metadata = {};
        }
        (drafterMessage as any).response_metadata.cascadeflow = {
          flow: 'tool_calls_direct',
          has_tool_calls: true,
          tool_calls_count: toolCallsCount,
          latency_ms: drafterLatency,
          model_used: 'drafter'
        };

        return {
          generations: [{
            text: drafterMessage.content.toString(),
            message: drafterMessage,
          }],
        };
      }

      // Step 3: Quality check using CascadeFlow validator (or simple fallback)
      const responseText = drafterMessage.content.toString();

      let validationResult: any;

      if (this.qualityValidator) {
        // Use full CascadeFlow quality validator
        const queryText = messages.map(m => m.content.toString()).join(' ');
        try {
          validationResult = await this.qualityValidator.validate(responseText, queryText);
          const qualityLog = `   📊 Quality validation: confidence=${validationResult.confidence.toFixed(2)}, method=${validationResult.method}\n`;
          await runManager?.handleText(qualityLog);
          console.log(qualityLog);

          if (validationResult.details?.alignmentScore) {
            const alignmentLog = `   🎯 Alignment: ${validationResult.details.alignmentScore.toFixed(2)}\n`;
            await runManager?.handleText(alignmentLog);
            console.log(alignmentLog);
          }
        } catch (e) {
          const errorLog = `   ⚠️  Quality validator error, using simple check: ${e}\n`;
          await runManager?.handleText(errorLog);
          console.warn(errorLog);
          validationResult = this.simpleQualityCheck(responseText);
        }
      } else {
        // Use simple quality check (fallback)
        validationResult = this.simpleQualityCheck(responseText);
        const simpleLog = `   📊 Simple quality check: confidence=${validationResult.confidence.toFixed(2)}\n`;
        await runManager?.handleText(simpleLog);
        console.log(simpleLog);
      }

      // Step 4: If quality is sufficient, return drafter response
      if (validationResult.passed) {
        // Calculate actual cost
        const drafterCost = await this.calculateMessageCost(drafterMessage, this.drafterModel);

        const flowLog = `\n┌─────────────────────────────────────────┐\n│  ✅ FLOW: DRAFTER ACCEPTED (FAST PATH) │\n└─────────────────────────────────────────┘\n   Query → Drafter → Quality Check ✅ → Response\n   ⚡ Fast & Cheap: Used drafter model only\n   Model used: ${drafterInfo}\n   Confidence: ${validationResult.confidence.toFixed(2)} (threshold: ${this.qualityThreshold})\n   Quality score: ${validationResult.score.toFixed(2)}\n   Latency: ${drafterLatency}ms\n   💰 Cost: $${drafterCost.toFixed(6)} (drafter only)\n   📊 Stats: ${this.drafterCount} drafter, ${this.verifierCount} verifier\n`;

        await runManager?.handleText(flowLog);
        console.log(flowLog);

        // Add flow metadata to message for n8n UI visibility (logs only, not in response text)
        if (!drafterMessage.response_metadata) {
          (drafterMessage as any).response_metadata = {};
        }
        (drafterMessage as any).response_metadata.cascadeflow = {
          flow: 'drafter_accepted',
          confidence: validationResult.confidence,
          quality_score: validationResult.score,
          latency_ms: drafterLatency,
          cost_usd: drafterCost,
          model_used: 'drafter'
        };

        return {
          generations: [{
            text: drafterMessage.content.toString(),
            message: drafterMessage,
          }],
        };
      }

      // Step 5: Otherwise, escalate to verifier
      const escalateLog = `\n┌────────────────────────────────────────────────┐\n│  ⚠️  FLOW: ESCALATED TO VERIFIER (SLOW PATH)  │\n└────────────────────────────────────────────────┘\n   Query → Drafter → Quality Check ❌ → Verifier → Response\n   🔄 Escalating: Drafter quality too low, using verifier\n   Confidence: ${validationResult.confidence.toFixed(2)} < ${this.qualityThreshold} (threshold)\n   Reason: ${validationResult.reason}\n   Drafter latency: ${drafterLatency}ms\n   🔄 Loading verifier model...\n`;

      await runManager?.handleText(escalateLog);
      console.log(escalateLog);

      const verifierStartTime = Date.now();
      const verifierModel = await this.getVerifierModel();
      const verifierInfo = this.getModelInfo(verifierModel);
      const verifierMessage = await verifierModel.invoke(messages, options);
      const verifierLatency = Date.now() - verifierStartTime;

      this.verifierCount++;

      // Calculate costs
      const verifierCost = await this.calculateMessageCost(verifierMessage, verifierModel);
      const totalCost = verifierCost; // Drafter cost is wasted in this path

      const totalLatency = drafterLatency + verifierLatency;
      const acceptanceRate = (this.drafterCount / (this.drafterCount + this.verifierCount) * 100).toFixed(1);

      const completionLog = `   ✅ Verifier completed successfully\n   Model used: ${verifierInfo}\n   Verifier latency: ${verifierLatency}ms\n   Total latency: ${totalLatency}ms (drafter: ${drafterLatency}ms + verifier: ${verifierLatency}ms)\n   💰 Cost: $${totalCost.toFixed(6)} (verifier only, drafter attempt wasted)\n   📊 Stats: ${this.drafterCount} drafter (${acceptanceRate}%), ${this.verifierCount} verifier\n`;

      await runManager?.handleText(completionLog);
      console.log(completionLog);

      // Add flow metadata to message for n8n UI visibility (logs only, not in response text)
      if (!verifierMessage.response_metadata) {
        (verifierMessage as any).response_metadata = {};
      }
      (verifierMessage as any).response_metadata.cascadeflow = {
        flow: 'escalated_to_verifier',
        confidence: validationResult.confidence,
        drafter_latency_ms: drafterLatency,
        verifier_latency_ms: verifierLatency,
        total_latency_ms: totalLatency,
        cost_usd: totalCost,
        model_used: 'verifier',
        reason: validationResult.reason
      };

      return {
        generations: [{
          text: verifierMessage.content.toString(),
          message: verifierMessage,
        }],
      };
    } catch (error) {
      // Fallback to verifier on error
      const errorMsg = error instanceof Error ? error.message : String(error);
      const errorLog = `\n┌─────────────────────────────────────────────┐\n│  ❌ FLOW: DRAFTER ERROR - FALLBACK PATH    │\n└─────────────────────────────────────────────┘\n   Query → Drafter ❌ ERROR → Verifier → Response\n   🔄 Fallback: Drafter failed, using verifier as backup\n   Error: ${errorMsg}\n   🔄 Loading verifier model...\n`;

      await runManager?.handleText(errorLog);
      console.log(errorLog);

      const verifierModel = await this.getVerifierModel();
      const verifierInfo = this.getModelInfo(verifierModel);
      const verifierMessage = await verifierModel.invoke(messages, options);
      this.verifierCount++;

      const fallbackCompleteLog = `   ✅ Verifier fallback completed successfully\n   Model used: ${verifierInfo}\n   💰 Cost: Full verifier cost (fallback due to error)\n`;

      await runManager?.handleText(fallbackCompleteLog);
      console.log(fallbackCompleteLog);

      // Add flow metadata to message for n8n UI visibility (logs only, not in response text)
      if (!verifierMessage.response_metadata) {
        (verifierMessage as any).response_metadata = {};
      }
      (verifierMessage as any).response_metadata.cascadeflow = {
        flow: 'error_fallback',
        error: errorMsg,
        cost_savings_percent: 0,
        model_used: 'verifier'
      };

      return {
        generations: [{
          text: verifierMessage.content.toString(),
          message: verifierMessage,
        }],
      };
    }
  }

  /**
   * Streaming implementation for real-time cascade feedback
   * Streams drafter response, then quality checks, then optionally streams verifier
   */
  async *_streamResponseChunks(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): AsyncGenerator<ChatGenerationChunk> {
    try {
      // Step 1: Stream drafter response
      const drafterInfo = this.getModelInfo(this.drafterModel);
      await runManager?.handleText(`🎯 CascadeFlow (Streaming): Trying drafter model: ${drafterInfo}\n`);
      console.log(`🎯 CascadeFlow (Streaming): Trying drafter model: ${drafterInfo}`);

      const drafterStartTime = Date.now();
      let fullDrafterContent = '';
      let lastChunk: ChatGenerationChunk | null = null;

      // Stream all drafter chunks to user in real-time
      const drafterStream = await this.drafterModel.stream(messages, options);

      for await (const chunk of drafterStream) {
        fullDrafterContent += chunk.content;
        // Convert AIMessageChunk to ChatGenerationChunk
        const generationChunk = new ChatGenerationChunk({
          text: chunk.content.toString(),
          message: chunk,
        });
        lastChunk = generationChunk;
        yield generationChunk; // Stream to user immediately
      }

      const drafterLatency = Date.now() - drafterStartTime;
      this.drafterCount++;

      // Step 2: Check for tool calls (after streaming complete)
      if (lastChunk && this.hasToolCalls(lastChunk.message)) {
        const toolCallsCount = this.getToolCallsCount(lastChunk.message);
        const toolLog = `\n🔧 Tool calls detected (${toolCallsCount}) - cascade complete\n`;
        await runManager?.handleText(toolLog);
        console.log(toolLog);
        return; // Done streaming
      }

      // Step 3: Quality check (after streaming complete)
      const queryText = messages.map(m => m.content.toString()).join(' ');

      await runManager?.handleText(`\n📊 Running quality check...\n`);

      let validationResult: any;
      if (this.qualityValidator) {
        try {
          validationResult = await this.qualityValidator.validate(fullDrafterContent, queryText);
          await runManager?.handleText(`   Confidence: ${validationResult.confidence.toFixed(2)} (threshold: ${this.qualityThreshold})\n`);
        } catch (e) {
          validationResult = this.simpleQualityCheck(fullDrafterContent);
        }
      } else {
        validationResult = this.simpleQualityCheck(fullDrafterContent);
      }

      // Step 4: If quality sufficient, we're done
      if (validationResult.passed) {
        await runManager?.handleText(`✅ Quality check passed - cascade complete (drafter accepted)\n`);
        console.log(`✅ Streaming: Drafter accepted (${drafterLatency}ms)`);
        return; // Done streaming
      }

      // Step 5: Quality insufficient - escalate to verifier and stream its response
      await runManager?.handleText(`\n⚠️  Quality check failed - escalating to verifier...\n`);
      console.log(`⚠️  Streaming: Escalating to verifier (confidence ${validationResult.confidence.toFixed(2)} < ${this.qualityThreshold})`);

      const verifierModel = await this.getVerifierModel();
      const verifierInfo = this.getModelInfo(verifierModel);

      await runManager?.handleText(`🔄 Streaming verifier response from ${verifierInfo}...\n`);

      const verifierStartTime = Date.now();
      const verifierStream = await verifierModel.stream(messages, options);

      this.verifierCount++;

      // Stream verifier response
      for await (const chunk of verifierStream) {
        // Convert AIMessageChunk to ChatGenerationChunk
        yield new ChatGenerationChunk({
          text: chunk.content.toString(),
          message: chunk,
        });
      }

      const verifierLatency = Date.now() - verifierStartTime;
      await runManager?.handleText(`\n✅ Verifier streaming complete (${verifierLatency}ms)\n`);
      console.log(`✅ Streaming: Verifier complete (${verifierLatency}ms)`);

    } catch (error) {
      // Fallback to verifier on error
      const errorMsg = error instanceof Error ? error.message : String(error);
      await runManager?.handleText(`\n❌ Drafter error - falling back to verifier: ${errorMsg}\n`);
      console.log(`❌ Streaming: Drafter error, using verifier fallback`);

      const verifierModel = await this.getVerifierModel();
      const verifierStream = await verifierModel.stream(messages, options);

      this.verifierCount++;

      for await (const chunk of verifierStream) {
        // Convert AIMessageChunk to ChatGenerationChunk
        yield new ChatGenerationChunk({
          text: chunk.content.toString(),
          message: chunk,
        });
      }
    }
  }
}

export class LmChatCascadeFlow implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'CascadeFlow',
    name: 'lmChatCascadeFlow',
    icon: 'file:cascadeflow.svg',
    group: ['transform'],
    version: 1,
    description: 'Smart AI model cascading with 40-85% cost savings. Connect two AI models (drafter and verifier) and intelligently cascade between them.',
    defaults: {
      name: 'CascadeFlow',
    },
    codex: {
      categories: ['AI'],
      subcategories: {
        AI: ['Language Models', 'Chat Models'],
      },
      resources: {
        primaryDocumentation: [
          {
            url: 'https://github.com/lemony-ai/cascadeflow',
          },
        ],
      },
    },
    // Sub-node: accepts AI model connections
    // Visual layout: Index 0 = "Verifier" label (top), Index 1 = "Drafter" label (bottom)
    // Actual logic: Index 0 = VERIFIER model (only if needed), Index 1 = DRAFTER model (tried first)
    // User connects: TOP port = verifier model, BOTTOM port = drafter model
    // eslint-disable-next-line n8n-nodes-base/node-class-description-inputs-wrong-regular-node
    inputs: [
      {
        displayName: 'Verifier',
        type: 'ai_languageModel' as any,
        maxConnections: 1,
        required: true,
      },
      {
        displayName: 'Drafter',
        type: 'ai_languageModel' as any,
        maxConnections: 1,
        required: true,
      },
    ],
    // Outputs an AI model that can be connected to Chain nodes
    // eslint-disable-next-line n8n-nodes-base/node-class-description-outputs-wrong
    outputs: ['ai_languageModel' as any],
    outputNames: ['Model'],
    properties: [
      {
        displayName: 'Quality Threshold',
        name: 'qualityThreshold',
        type: 'number',
        default: 0.64,
        typeOptions: {
          minValue: 0,
          maxValue: 1,
          numberPrecision: 2,
        },
        description: 'Minimum quality score (0-1) to accept drafter response. Lower = more cost savings, higher = better quality.',
      },
      {
        displayName: 'Enable Semantic Validation',
        name: 'useSemanticValidation',
        type: 'boolean',
        default: true,
        description: 'Whether to use ML-based semantic similarity validation for better quality detection',
      },
      {
        displayName: 'Enable Alignment Scoring',
        name: 'useAlignmentScoring',
        type: 'boolean',
        default: true,
        description: 'Whether to score query-response alignment for improved validation accuracy',
      },
      {
        displayName: 'Enable Complexity Routing',
        name: 'useComplexityRouting',
        type: 'boolean',
        default: true,
        description: 'Whether to route queries directly to the verifier based on detected complexity',
      },
    ],
  };

  async supplyData(this: ISupplyDataFunctions): Promise<SupplyData> {
    // Get parameters
    const qualityThreshold = this.getNodeParameter('qualityThreshold', 0, 0.64) as number;
    const useSemanticValidation = this.getNodeParameter('useSemanticValidation', 0, true) as boolean;
    const useAlignmentScoring = this.getNodeParameter('useAlignmentScoring', 0, true) as boolean;
    const useComplexityRouting = this.getNodeParameter('useComplexityRouting', 0, true) as boolean;

    // Get the drafter model immediately (at index 1 - bottom port, labeled "Drafter")
    const drafterData = await this.getInputConnectionData('ai_languageModel' as any, 1);
    const drafterModel = (Array.isArray(drafterData) ? drafterData[0] : drafterData) as BaseChatModel;

    if (!drafterModel) {
      throw new NodeOperationError(
        this.getNode(),
        'Drafter model is required. Please connect your DRAFTER model to the BOTTOM port (labeled "Drafter").'
      );
    }

    // Create a lazy loader for the verifier model (only fetched when needed) (at index 0 - top port, labeled "Verifier")
    const verifierModelGetter = async () => {
      const verifierData = await this.getInputConnectionData('ai_languageModel' as any, 0);
      const verifierModel = (Array.isArray(verifierData) ? verifierData[0] : verifierData) as BaseChatModel;

      if (!verifierModel) {
        throw new NodeOperationError(
          this.getNode(),
          'Verifier model is required. Please connect your VERIFIER model to the TOP port (labeled "Verifier").'
        );
      }

      return verifierModel;
    };

    // Debug: Get detailed model info
    const getDrafterInfo = () => {
      const type = typeof drafterModel._llmType === 'function' ? drafterModel._llmType() : 'unknown';
      const modelName = (drafterModel as any).modelName || (drafterModel as any).model || 'unknown';
      return `${type} (${modelName})`;
    };

    console.log('🚀 CascadeFlow initialized');
    console.log(`   PORT MAPPING:`);
    console.log(`   ├─ TOP port (labeled "Verifier") → VERIFIER model: lazy-loaded (will fetch only if needed)`);
    console.log(`   └─ BOTTOM port (labeled "Drafter") → DRAFTER model: ${getDrafterInfo()}`);
    console.log(`   Quality threshold: ${qualityThreshold}`);
    console.log(`   Semantic validation: ${useSemanticValidation ? 'enabled' : 'disabled'}`);
    console.log(`   Alignment scoring: ${useAlignmentScoring ? 'enabled' : 'disabled'}`);
    console.log(`   Complexity routing: ${useComplexityRouting ? 'enabled' : 'disabled'}`);

    // Create and return the cascade model with lazy verifier and advanced features
    const cascadeModel = new CascadeChatModel(
      drafterModel,
      verifierModelGetter,
      qualityThreshold,
      useSemanticValidation,
      useAlignmentScoring,
      useComplexityRouting
    );

    return {
      response: cascadeModel,
    };
  }
}
