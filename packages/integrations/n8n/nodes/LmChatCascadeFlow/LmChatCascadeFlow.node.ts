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

// =============================================================================
// DOMAIN CONSTANTS - All 16 supported domains
// =============================================================================
const DOMAINS = {
  CODE: 'code',
  DATA: 'data',
  STRUCTURED: 'structured',
  RAG: 'rag',
  CONVERSATION: 'conversation',
  TOOL: 'tool',
  CREATIVE: 'creative',
  SUMMARY: 'summary',
  TRANSLATION: 'translation',
  MATH: 'math',
  SCIENCE: 'science',
  MEDICAL: 'medical',
  LEGAL: 'legal',
  FINANCIAL: 'financial',
  MULTIMODAL: 'multimodal',
  GENERAL: 'general',
} as const;

type DomainType = typeof DOMAINS[keyof typeof DOMAINS];

// Domain display names for n8n UI
const DOMAIN_DISPLAY_NAMES: Record<DomainType, string> = {
  code: 'Code',
  data: 'Data Analysis',
  structured: 'Structured Output',
  rag: 'RAG (Retrieval)',
  conversation: 'Conversation',
  tool: 'Tool Calling',
  creative: 'Creative Writing',
  summary: 'Summarization',
  translation: 'Translation',
  math: 'Mathematics',
  science: 'Science',
  medical: 'Medical',
  legal: 'Legal',
  financial: 'Financial',
  multimodal: 'Multimodal',
  general: 'General',
};

// Domain descriptions for n8n UI
const DOMAIN_DESCRIPTIONS: Record<DomainType, string> = {
  code: 'Programming, debugging, code generation',
  data: 'Data analysis, statistics, pandas/SQL',
  structured: 'JSON, XML, structured data extraction',
  rag: 'Retrieval-augmented generation, document Q&A',
  conversation: 'Chat, dialogue, multi-turn conversations',
  tool: 'Function calling, tool use, API interactions',
  creative: 'Creative writing, stories, poetry',
  summary: 'Text summarization, condensing content',
  translation: 'Language translation, multilingual',
  math: 'Mathematical reasoning, calculations, proofs',
  science: 'Scientific knowledge, research, experiments',
  medical: 'Healthcare, medical knowledge, clinical',
  legal: 'Legal documents, contracts, regulations',
  financial: 'Finance, accounting, investment analysis',
  multimodal: 'Images, audio, video understanding',
  general: 'General purpose, fallback domain',
};

// Quality validation, cost tracking, routing, and circuit breaker - optional import
let QualityValidator: any;
let CASCADE_QUALITY_CONFIG: any;
let CostCalculator: any;
let ComplexityDetector: any;
let PreRouter: any;
let DomainDetector: any;
let CircuitBreaker: any;

try {
  const cascadeCore = require('@cascadeflow/core');
  QualityValidator = cascadeCore.QualityValidator;
  CASCADE_QUALITY_CONFIG = cascadeCore.CASCADE_QUALITY_CONFIG;
  CostCalculator = cascadeCore.CostCalculator;
  ComplexityDetector = cascadeCore.ComplexityDetector;
  PreRouter = cascadeCore.PreRouter;
  DomainDetector = cascadeCore.DomainDetector;
  CircuitBreaker = cascadeCore.CircuitBreaker;
} catch (e) {
  // @cascadeflow/core not available - use simple validation and estimates
  console.warn('⚠️  @cascadeflow/core not available, using fallbacks');
}

// =============================================================================
// Domain configuration for each enabled domain
// =============================================================================
interface DomainConfig {
  enabled: boolean;
  threshold: number;
  temperature: number;
  model?: BaseChatModel;
}

/**
 * Custom CascadeChatModel that wraps multiple models (drafter, verifier, and domain-specific)
 * and implements intelligent domain-aware cascading logic with cost tracking
 */
class CascadeChatModel extends BaseChatModel {
  drafterModel: BaseChatModel;
  verifierModelGetter: () => Promise<BaseChatModel>;
  qualityThreshold: number;

  // Domain-specific models and configurations
  private domainModels: Map<DomainType, BaseChatModel | undefined> = new Map();
  private domainConfigs: Map<DomainType, DomainConfig> = new Map();
  private enabledDomains: DomainType[] = [];

  // Cost tracking
  private drafterCost: number = 0;
  private verifierCost: number = 0;
  private domainCosts: Map<DomainType, number> = new Map();
  private drafterCount: number = 0;
  private verifierCount: number = 0;
  private domainCounts: Map<DomainType, number> = new Map();

  // Lazy-loaded verifier
  private verifierModel?: BaseChatModel;

  // Quality validator with CASCADE config (optional)
  private qualityValidator: any;

  // Cost calculator for accurate token-based cost tracking
  private costCalculator: any;

  // Complexity detector for intelligent routing
  private complexityDetector: any;

  // Domain detector for semantic domain routing
  private domainDetector: any;

  // PreRouter for complexity-based direct routing
  private preRouter: any;

  // Circuit breaker for fault tolerance
  private circuitBreaker: any;

  constructor(
    drafterModel: BaseChatModel,
    verifierModelGetter: () => Promise<BaseChatModel>,
    qualityThreshold: number = 0.7,
    useSemanticValidation: boolean = true,
    useAlignmentScoring: boolean = true,
    useComplexityRouting: boolean = true,
    useDomainRouting: boolean = false,
    enabledDomains: DomainType[] = [],
    domainModelGetters: Map<DomainType, () => Promise<BaseChatModel | undefined>> = new Map(),
    domainConfigs: Map<DomainType, DomainConfig> = new Map(),
    useCircuitBreaker: boolean = true
  ) {
    super({});
    this.drafterModel = drafterModel;
    this.verifierModelGetter = verifierModelGetter;
    this.qualityThreshold = qualityThreshold;
    this.enabledDomains = enabledDomains;
    this.domainConfigs = domainConfigs;

    // Store domain model getters for lazy loading
    for (const [domain, getter] of domainModelGetters.entries()) {
      // Lazy load domain models
      this.domainModels.set(domain, undefined);
    }

    // Initialize quality validator with CASCADE-optimized config + semantic validation
    if (QualityValidator && CASCADE_QUALITY_CONFIG) {
      try {
        this.qualityValidator = new QualityValidator({
          ...CASCADE_QUALITY_CONFIG,
          minConfidence: qualityThreshold,
          useSemanticValidation,
          useAlignmentScoring,
          semanticThreshold: 0.5,
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

    // Initialize complexity detector and domain detector
    if (useComplexityRouting && ComplexityDetector) {
      try {
        this.complexityDetector = new ComplexityDetector();
        console.log('🧠 CascadeFlow complexity-based routing enabled');
      } catch (e) {
        console.warn('⚠️  Complexity detector initialization failed');
        this.complexityDetector = null;
      }
    } else {
      this.complexityDetector = null;
    }

    // Initialize domain detector if domain routing is enabled
    if (useDomainRouting && DomainDetector && enabledDomains.length > 0) {
      try {
        this.domainDetector = new DomainDetector({ enabledDomains });
        console.log(`🎯 CascadeFlow domain routing enabled for: ${enabledDomains.join(', ')}`);
      } catch (e) {
        console.warn('⚠️  Domain detector initialization failed');
        this.domainDetector = null;
      }
    } else {
      this.domainDetector = null;
    }

    // Initialize circuit breaker for fault tolerance
    if (useCircuitBreaker && CircuitBreaker) {
      try {
        this.circuitBreaker = new CircuitBreaker({
          failureThreshold: 3,
          recoveryTimeout: 30000, // 30 seconds
          halfOpenMaxCalls: 2,
        });
        console.log('🛡️  CascadeFlow circuit breaker enabled');
      } catch (e) {
        console.warn('⚠️  Circuit breaker initialization failed');
        this.circuitBreaker = null;
      }
    } else {
      this.circuitBreaker = null;
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
   * Get domain-specific model if available, falls back to drafter
   */
  private async getDomainModel(domain: DomainType): Promise<BaseChatModel> {
    const existingModel = this.domainModels.get(domain);
    if (existingModel) {
      return existingModel;
    }
    // Fallback to drafter if no domain-specific model
    return this.drafterModel;
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
   * Detect the domain of a query using semantic detection
   */
  private async detectDomain(queryText: string): Promise<DomainType | null> {
    if (!this.domainDetector || this.enabledDomains.length === 0) {
      return null;
    }

    try {
      const result = await this.domainDetector.detect(queryText);
      if (result && result.domain && this.enabledDomains.includes(result.domain)) {
        console.log(`🎯 Domain detected: ${result.domain} (confidence: ${result.confidence?.toFixed(2) || 'N/A'})`);
        return result.domain;
      }
    } catch (e) {
      console.warn('Domain detection failed, using default routing');
    }
    return null;
  }

  /**
   * Check if message contains tool calls
   */
  private hasToolCalls(message: BaseMessage): boolean {
    const additionalKwargs = (message as any).additional_kwargs || {};

    if (additionalKwargs.tool_calls && Array.isArray(additionalKwargs.tool_calls) && additionalKwargs.tool_calls.length > 0) {
      return true;
    }

    if (additionalKwargs.function_call && typeof additionalKwargs.function_call === 'object') {
      return true;
    }

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

    if (additionalKwargs.tool_calls && Array.isArray(additionalKwargs.tool_calls)) {
      return additionalKwargs.tool_calls.length;
    }

    if (additionalKwargs.function_call) {
      return 1;
    }

    if (responseMetadata.tool_calls && Array.isArray(responseMetadata.tool_calls)) {
      return responseMetadata.tool_calls.length;
    }

    return 0;
  }

  /**
   * Calculate accurate cost from message token usage
   */
  private async calculateMessageCost(
    message: BaseMessage,
    model: BaseChatModel
  ): Promise<number> {
    const responseMetadata = (message as any).response_metadata || {};
    const tokenUsage = responseMetadata.tokenUsage || responseMetadata.usage || {};

    const inputTokens = tokenUsage.promptTokens || tokenUsage.prompt_tokens || 0;
    const outputTokens = tokenUsage.completionTokens || tokenUsage.completion_tokens || 0;

    const modelName = (model as any).modelName || (model as any).model || 'unknown';

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

    let confidence = 0.75;

    if (wordCount < 5) {
      confidence = 0.50;
    } else if (wordCount < 15) {
      confidence = 0.65;
    } else if (wordCount > 30) {
      confidence = 0.85;
    }

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
      const queryText = messages.map(m => m.content.toString()).join(' ');

      // Step 1: Detect domain if domain routing is enabled
      let detectedDomain: DomainType | null = null;
      let domainModel: BaseChatModel | null = null;

      if (this.enabledDomains.length > 0) {
        detectedDomain = await this.detectDomain(queryText);
        if (detectedDomain) {
          const domainConfig = this.domainConfigs.get(detectedDomain);
          if (domainConfig?.model) {
            domainModel = domainConfig.model;
            await runManager?.handleText(`🎯 Domain: ${DOMAIN_DISPLAY_NAMES[detectedDomain]} → Using domain-specific model\n`);
          }
        }
      }

      // Step 2: Detect query complexity
      let complexity: string | undefined;
      let shouldSkipDrafter = false;

      if (this.complexityDetector) {
        try {
          const complexityResult = await this.complexityDetector.detectComplexity(queryText);
          complexity = complexityResult.level;

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

      // Step 3: Execute with circuit breaker protection if available
      const executeWithProtection = async (model: BaseChatModel, modelType: string) => {
        if (this.circuitBreaker) {
          return await this.circuitBreaker.execute(
            modelType,
            async () => await model.invoke(messages, options)
          );
        }
        return await model.invoke(messages, options);
      };

      // Step 3a: If complexity routing says skip drafter, go directly to verifier
      if (shouldSkipDrafter) {
        const verifierModel = await this.getVerifierModel();
        const verifierInfo = this.getModelInfo(verifierModel);

        await runManager?.handleText(`⚡ Direct route: Using verifier for ${complexity} query\n`);

        const verifierStartTime = Date.now();
        const verifierMessage = await executeWithProtection(verifierModel, 'verifier');
        const verifierLatency = Date.now() - verifierStartTime;

        this.verifierCount++;

        const verifierCost = await this.calculateMessageCost(verifierMessage, verifierModel);

        const flowLog = `
┌────────────────────────────────────────────┐
│  ⚡ FLOW: DIRECT VERIFIER (SMART ROUTE)  │
└────────────────────────────────────────────┘
   Query → Complexity Check (${complexity}) → Verifier → Response
   🧠 Smart routing: Skipped drafter for complex query
   Model used: ${verifierInfo}
   Latency: ${verifierLatency}ms
   💰 Cost: $${verifierCost.toFixed(6)}
   📊 Stats: ${this.drafterCount} drafter, ${this.verifierCount} verifier
`;

        await runManager?.handleText(flowLog);
        console.log(flowLog);

        if (!verifierMessage.response_metadata) {
          (verifierMessage as any).response_metadata = {};
        }
        (verifierMessage as any).response_metadata.cascadeflow = {
          flow: 'direct_verifier',
          complexity,
          domain: detectedDomain,
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

      // Step 4: Try domain-specific model first if available
      const modelToUse = domainModel || this.drafterModel;
      const modelType = domainModel ? `domain:${detectedDomain}` : 'drafter';
      const modelInfo = this.getModelInfo(modelToUse);

      await runManager?.handleText(`🎯 CascadeFlow: Trying ${modelType} model: ${modelInfo}\n`);
      console.log(`🎯 CascadeFlow: Trying ${modelType} model: ${modelInfo}`);

      const drafterStartTime = Date.now();
      const drafterMessage = await executeWithProtection(modelToUse, modelType);
      const drafterLatency = Date.now() - drafterStartTime;

      if (domainModel && detectedDomain) {
        this.domainCounts.set(detectedDomain, (this.domainCounts.get(detectedDomain) || 0) + 1);
      } else {
        this.drafterCount++;
      }

      // Step 5: Check if response contains tool calls
      const hasToolCalls = this.hasToolCalls(drafterMessage);

      if (hasToolCalls) {
        const toolCallsCount = this.getToolCallsCount(drafterMessage);
        const toolLog = `   🔧 Tool calls detected (${toolCallsCount}) - bypassing quality check\n`;
        await runManager?.handleText(toolLog);
        console.log(toolLog);

        const flowLog = `
┌──────────────────────────────────────────┐
│  🔧 FLOW: TOOL CALLS (DIRECT PASS)      │
└──────────────────────────────────────────┘
   Query → ${modelType} → Tool Calls (${toolCallsCount}) → Response
   ⚡ Tool calling: ${modelType} generated tool calls
   Model used: ${modelInfo}
   ${detectedDomain ? `Domain: ${DOMAIN_DISPLAY_NAMES[detectedDomain]}` : ''}
   Latency: ${drafterLatency}ms
   📊 Stats: ${this.drafterCount} drafter, ${this.verifierCount} verifier
`;

        await runManager?.handleText(flowLog);
        console.log(flowLog);

        if (!drafterMessage.response_metadata) {
          (drafterMessage as any).response_metadata = {};
        }
        (drafterMessage as any).response_metadata.cascadeflow = {
          flow: 'tool_calls_direct',
          has_tool_calls: true,
          tool_calls_count: toolCallsCount,
          domain: detectedDomain,
          latency_ms: drafterLatency,
          model_used: modelType
        };

        return {
          generations: [{
            text: drafterMessage.content.toString(),
            message: drafterMessage,
          }],
        };
      }

      // Step 6: Quality check with domain-aware threshold
      const responseText = drafterMessage.content.toString();
      const effectiveThreshold = detectedDomain
        ? (this.domainConfigs.get(detectedDomain)?.threshold ?? this.qualityThreshold)
        : this.qualityThreshold;

      let validationResult: any;

      if (this.qualityValidator) {
        try {
          validationResult = await this.qualityValidator.validate(responseText, queryText);
          validationResult.passed = validationResult.confidence >= effectiveThreshold;
          const qualityLog = `   📊 Quality validation: confidence=${validationResult.confidence.toFixed(2)}, threshold=${effectiveThreshold}, method=${validationResult.method}\n`;
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
          validationResult.passed = validationResult.confidence >= effectiveThreshold;
        }
      } else {
        validationResult = this.simpleQualityCheck(responseText);
        validationResult.passed = validationResult.confidence >= effectiveThreshold;
        const simpleLog = `   📊 Simple quality check: confidence=${validationResult.confidence.toFixed(2)}\n`;
        await runManager?.handleText(simpleLog);
        console.log(simpleLog);
      }

      // Step 7: If quality is sufficient, return response
      if (validationResult.passed) {
        const drafterCost = await this.calculateMessageCost(drafterMessage, modelToUse);

        const flowLog = `
┌─────────────────────────────────────────┐
│  ✅ FLOW: ${modelType.toUpperCase()} ACCEPTED (FAST PATH) │
└─────────────────────────────────────────┘
   Query → ${detectedDomain ? `Domain(${detectedDomain}) → ` : ''}${modelType} → Quality Check ✅ → Response
   ⚡ Fast & Cheap: Used ${modelType} model only
   Model used: ${modelInfo}
   ${detectedDomain ? `Domain: ${DOMAIN_DISPLAY_NAMES[detectedDomain]}` : ''}
   Confidence: ${validationResult.confidence.toFixed(2)} (threshold: ${effectiveThreshold})
   Quality score: ${validationResult.score.toFixed(2)}
   Latency: ${drafterLatency}ms
   💰 Cost: $${drafterCost.toFixed(6)} (${modelType} only)
   📊 Stats: ${this.drafterCount} drafter, ${this.verifierCount} verifier, domains: ${JSON.stringify(Object.fromEntries(this.domainCounts))}
`;

        await runManager?.handleText(flowLog);
        console.log(flowLog);

        if (!drafterMessage.response_metadata) {
          (drafterMessage as any).response_metadata = {};
        }
        (drafterMessage as any).response_metadata.cascadeflow = {
          flow: `${modelType}_accepted`,
          confidence: validationResult.confidence,
          quality_score: validationResult.score,
          domain: detectedDomain,
          latency_ms: drafterLatency,
          cost_usd: drafterCost,
          model_used: modelType
        };

        return {
          generations: [{
            text: drafterMessage.content.toString(),
            message: drafterMessage,
          }],
        };
      }

      // Step 8: Otherwise, escalate to verifier
      const escalateLog = `
┌────────────────────────────────────────────────┐
│  ⚠️  FLOW: ESCALATED TO VERIFIER (SLOW PATH)  │
└────────────────────────────────────────────────┘
   Query → ${detectedDomain ? `Domain(${detectedDomain}) → ` : ''}${modelType} → Quality Check ❌ → Verifier → Response
   🔄 Escalating: ${modelType} quality too low, using verifier
   Confidence: ${validationResult.confidence.toFixed(2)} < ${effectiveThreshold} (threshold)
   Reason: ${validationResult.reason}
   ${modelType} latency: ${drafterLatency}ms
   🔄 Loading verifier model...
`;

      await runManager?.handleText(escalateLog);
      console.log(escalateLog);

      const verifierStartTime = Date.now();
      const verifierModel = await this.getVerifierModel();
      const verifierInfo = this.getModelInfo(verifierModel);
      const verifierMessage = await executeWithProtection(verifierModel, 'verifier');
      const verifierLatency = Date.now() - verifierStartTime;

      this.verifierCount++;

      const verifierCost = await this.calculateMessageCost(verifierMessage, verifierModel);
      const totalCost = verifierCost;

      const totalLatency = drafterLatency + verifierLatency;
      const acceptanceRate = (this.drafterCount / (this.drafterCount + this.verifierCount) * 100).toFixed(1);

      const completionLog = `   ✅ Verifier completed successfully
   Model used: ${verifierInfo}
   Verifier latency: ${verifierLatency}ms
   Total latency: ${totalLatency}ms (${modelType}: ${drafterLatency}ms + verifier: ${verifierLatency}ms)
   💰 Cost: $${totalCost.toFixed(6)} (verifier only, ${modelType} attempt wasted)
   📊 Stats: ${this.drafterCount} drafter (${acceptanceRate}%), ${this.verifierCount} verifier
`;

      await runManager?.handleText(completionLog);
      console.log(completionLog);

      if (!verifierMessage.response_metadata) {
        (verifierMessage as any).response_metadata = {};
      }
      (verifierMessage as any).response_metadata.cascadeflow = {
        flow: 'escalated_to_verifier',
        confidence: validationResult.confidence,
        domain: detectedDomain,
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
      // Handle circuit breaker open state
      const errorMsg = error instanceof Error ? error.message : String(error);
      const isCircuitOpen = errorMsg.includes('Circuit breaker') || errorMsg.includes('circuit is open');

      const errorLog = `
┌─────────────────────────────────────────────┐
│  ❌ FLOW: ${isCircuitOpen ? 'CIRCUIT OPEN' : 'DRAFTER ERROR'} - FALLBACK PATH    │
└─────────────────────────────────────────────┘
   Query → Drafter ❌ ${isCircuitOpen ? 'CIRCUIT OPEN' : 'ERROR'} → Verifier → Response
   🔄 Fallback: ${isCircuitOpen ? 'Circuit breaker open' : 'Drafter failed'}, using verifier as backup
   Error: ${errorMsg}
   🔄 Loading verifier model...
`;

      await runManager?.handleText(errorLog);
      console.log(errorLog);

      const verifierModel = await this.getVerifierModel();
      const verifierInfo = this.getModelInfo(verifierModel);
      const verifierMessage = await verifierModel.invoke(messages, options);
      this.verifierCount++;

      const fallbackCompleteLog = `   ✅ Verifier fallback completed successfully
   Model used: ${verifierInfo}
   💰 Cost: Full verifier cost (fallback due to ${isCircuitOpen ? 'circuit open' : 'error'})
`;

      await runManager?.handleText(fallbackCompleteLog);
      console.log(fallbackCompleteLog);

      if (!verifierMessage.response_metadata) {
        (verifierMessage as any).response_metadata = {};
      }
      (verifierMessage as any).response_metadata.cascadeflow = {
        flow: isCircuitOpen ? 'circuit_breaker_fallback' : 'error_fallback',
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
   */
  async *_streamResponseChunks(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): AsyncGenerator<ChatGenerationChunk> {
    try {
      const queryText = messages.map(m => m.content.toString()).join(' ');

      // Detect domain for streaming
      let detectedDomain: DomainType | null = null;
      let modelToUse = this.drafterModel;

      if (this.enabledDomains.length > 0) {
        detectedDomain = await this.detectDomain(queryText);
        if (detectedDomain) {
          const domainConfig = this.domainConfigs.get(detectedDomain);
          if (domainConfig?.model) {
            modelToUse = domainConfig.model;
          }
        }
      }

      const modelInfo = this.getModelInfo(modelToUse);
      const modelType = detectedDomain ? `domain:${detectedDomain}` : 'drafter';

      await runManager?.handleText(`🎯 CascadeFlow (Streaming): Trying ${modelType} model: ${modelInfo}\n`);
      console.log(`🎯 CascadeFlow (Streaming): Trying ${modelType} model: ${modelInfo}`);

      const drafterStartTime = Date.now();
      let fullDrafterContent = '';
      let lastChunk: ChatGenerationChunk | null = null;

      const drafterStream = await modelToUse.stream(messages, options);

      for await (const chunk of drafterStream) {
        fullDrafterContent += chunk.content;
        const generationChunk = new ChatGenerationChunk({
          text: chunk.content.toString(),
          message: chunk,
        });
        lastChunk = generationChunk;
        yield generationChunk;
      }

      const drafterLatency = Date.now() - drafterStartTime;
      this.drafterCount++;

      if (lastChunk && this.hasToolCalls(lastChunk.message)) {
        const toolCallsCount = this.getToolCallsCount(lastChunk.message);
        const toolLog = `\n🔧 Tool calls detected (${toolCallsCount}) - cascade complete\n`;
        await runManager?.handleText(toolLog);
        console.log(toolLog);
        return;
      }

      await runManager?.handleText(`\n📊 Running quality check...\n`);

      const effectiveThreshold = detectedDomain
        ? (this.domainConfigs.get(detectedDomain)?.threshold ?? this.qualityThreshold)
        : this.qualityThreshold;

      let validationResult: any;
      if (this.qualityValidator) {
        try {
          validationResult = await this.qualityValidator.validate(fullDrafterContent, queryText);
          validationResult.passed = validationResult.confidence >= effectiveThreshold;
          await runManager?.handleText(`   Confidence: ${validationResult.confidence.toFixed(2)} (threshold: ${effectiveThreshold})\n`);
        } catch (e) {
          validationResult = this.simpleQualityCheck(fullDrafterContent);
          validationResult.passed = validationResult.confidence >= effectiveThreshold;
        }
      } else {
        validationResult = this.simpleQualityCheck(fullDrafterContent);
        validationResult.passed = validationResult.confidence >= effectiveThreshold;
      }

      if (validationResult.passed) {
        await runManager?.handleText(`✅ Quality check passed - cascade complete (${modelType} accepted)\n`);
        console.log(`✅ Streaming: ${modelType} accepted (${drafterLatency}ms)`);
        return;
      }

      await runManager?.handleText(`\n⚠️  Quality check failed - escalating to verifier...\n`);
      console.log(`⚠️  Streaming: Escalating to verifier (confidence ${validationResult.confidence.toFixed(2)} < ${effectiveThreshold})`);

      const verifierModel = await this.getVerifierModel();
      const verifierInfo = this.getModelInfo(verifierModel);

      await runManager?.handleText(`🔄 Streaming verifier response from ${verifierInfo}...\n`);

      const verifierStartTime = Date.now();
      const verifierStream = await verifierModel.stream(messages, options);

      this.verifierCount++;

      for await (const chunk of verifierStream) {
        yield new ChatGenerationChunk({
          text: chunk.content.toString(),
          message: chunk,
        });
      }

      const verifierLatency = Date.now() - verifierStartTime;
      await runManager?.handleText(`\n✅ Verifier streaming complete (${verifierLatency}ms)\n`);
      console.log(`✅ Streaming: Verifier complete (${verifierLatency}ms)`);

    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      await runManager?.handleText(`\n❌ Drafter error - falling back to verifier: ${errorMsg}\n`);
      console.log(`❌ Streaming: Drafter error, using verifier fallback`);

      const verifierModel = await this.getVerifierModel();
      const verifierStream = await verifierModel.stream(messages, options);

      this.verifierCount++;

      for await (const chunk of verifierStream) {
        yield new ChatGenerationChunk({
          text: chunk.content.toString(),
          message: chunk,
        });
      }
    }
  }
}

// =============================================================================
// Generate dynamic inputs based on enabled domains
// =============================================================================
function generateDomainInputs(enabledDomains: DomainType[]): any[] {
  const baseInputs = [
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
  ];

  // Add domain-specific model inputs for each enabled domain
  for (const domain of enabledDomains) {
    baseInputs.push({
      displayName: `${DOMAIN_DISPLAY_NAMES[domain]} Model`,
      type: 'ai_languageModel' as any,
      maxConnections: 1,
      required: false,
    });
  }

  return baseInputs;
}

// =============================================================================
// Generate domain toggle properties for n8n UI
// =============================================================================
function generateDomainProperties(): any[] {
  const domainOptions = Object.entries(DOMAINS).map(([key, value]) => ({
    name: DOMAIN_DISPLAY_NAMES[value],
    value: value,
    description: DOMAIN_DESCRIPTIONS[value],
  }));

  return [
    {
      displayName: 'Enable Domain Routing',
      name: 'enableDomainRouting',
      type: 'boolean',
      default: false,
      description: 'Whether to enable intelligent routing based on detected query domain (math, code, legal, etc.)',
    },
    {
      displayName: 'Enabled Domains',
      name: 'enabledDomains',
      type: 'multiOptions',
      options: domainOptions,
      default: [],
      displayOptions: {
        show: {
          enableDomainRouting: [true],
        },
      },
      description: 'Select which domains to enable for intelligent routing. Connect domain-specific models for each.',
    },
    {
      displayName: 'Domain-Specific Settings',
      name: 'domainSettings',
      type: 'fixedCollection',
      typeOptions: {
        multipleValues: true,
      },
      displayOptions: {
        show: {
          enableDomainRouting: [true],
        },
      },
      default: {},
      options: [
        {
          name: 'domainConfig',
          displayName: 'Domain Configuration',
          values: [
            {
              displayName: 'Domain',
              name: 'domain',
              type: 'options',
              options: domainOptions,
              default: 'general',
              description: 'Select the domain to configure',
            },
            {
              displayName: 'Quality Threshold',
              name: 'threshold',
              type: 'number',
              default: 0.64,
              typeOptions: {
                minValue: 0,
                maxValue: 1,
                numberPrecision: 2,
              },
              description: 'Quality threshold for this domain (overrides global threshold)',
            },
            {
              displayName: 'Temperature',
              name: 'temperature',
              type: 'number',
              default: 0.7,
              typeOptions: {
                minValue: 0,
                maxValue: 2,
                numberPrecision: 1,
              },
              description: 'Temperature setting for this domain',
            },
          ],
        },
      ],
      description: 'Configure per-domain quality thresholds and temperatures',
    },
  ];
}

export class LmChatCascadeFlow implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'CascadeFlow',
    name: 'lmChatCascadeFlow',
    icon: 'file:cascadeflow.svg',
    group: ['transform'],
    version: 2,
    description: 'Smart AI model cascading with 40-85% cost savings. Supports 16 domains with domain-specific model routing.',
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
    // eslint-disable-next-line n8n-nodes-base/node-class-description-inputs-wrong-regular-node
    inputs: `={{ ((params) => {
      // Always include Verifier and Drafter
      const inputs = [
        {
          displayName: 'Verifier',
          type: 'ai_languageModel',
          maxConnections: 1,
          required: true,
        },
        {
          displayName: 'Drafter',
          type: 'ai_languageModel',
          maxConnections: 1,
          required: true,
        },
      ];

      // Only add domain model inputs if domain routing is enabled
      if (params?.enableDomainRouting) {
        const enabledDomains = params?.enabledDomains || [];
        const domainInputs = {
          code: 'Code Model',
          math: 'Math Model',
          data: 'Data Model',
          creative: 'Creative Model',
          legal: 'Legal Model',
          medical: 'Medical Model',
          financial: 'Financial Model',
          science: 'Science Model',
        };

        for (const [domain, displayName] of Object.entries(domainInputs)) {
          if (enabledDomains.includes(domain)) {
            inputs.push({
              displayName,
              type: 'ai_languageModel',
              maxConnections: 1,
              required: false,
            });
          }
        }
      }

      return inputs;
    })($parameter) }}`,
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
      {
        displayName: 'Enable Circuit Breaker',
        name: 'useCircuitBreaker',
        type: 'boolean',
        default: true,
        description: 'Whether to use circuit breaker for fault tolerance (auto-fallback on repeated failures)',
      },
      // Domain routing settings
      ...generateDomainProperties(),
    ],
  };

  async supplyData(this: ISupplyDataFunctions): Promise<SupplyData> {
    // Get core parameters
    const qualityThreshold = this.getNodeParameter('qualityThreshold', 0, 0.64) as number;
    const useSemanticValidation = this.getNodeParameter('useSemanticValidation', 0, true) as boolean;
    const useAlignmentScoring = this.getNodeParameter('useAlignmentScoring', 0, true) as boolean;
    const useComplexityRouting = this.getNodeParameter('useComplexityRouting', 0, true) as boolean;
    const useCircuitBreaker = this.getNodeParameter('useCircuitBreaker', 0, true) as boolean;

    // Get domain routing parameters
    const enableDomainRouting = this.getNodeParameter('enableDomainRouting', 0, false) as boolean;
    const enabledDomains = enableDomainRouting
      ? (this.getNodeParameter('enabledDomains', 0, []) as DomainType[])
      : [];

    // Get domain-specific settings
    const domainSettingsRaw = this.getNodeParameter('domainSettings', 0, { domainConfig: [] }) as any;
    const domainConfigs = new Map<DomainType, DomainConfig>();

    if (domainSettingsRaw?.domainConfig) {
      for (const config of domainSettingsRaw.domainConfig) {
        domainConfigs.set(config.domain, {
          enabled: enabledDomains.includes(config.domain),
          threshold: config.threshold || qualityThreshold,
          temperature: config.temperature || 0.7,
        });
      }
    }

    // Get the drafter model (index 1 - bottom port, labeled "Drafter")
    const drafterData = await this.getInputConnectionData('ai_languageModel' as any, 1);
    const drafterModel = (Array.isArray(drafterData) ? drafterData[0] : drafterData) as BaseChatModel;

    if (!drafterModel) {
      throw new NodeOperationError(
        this.getNode(),
        'Drafter model is required. Please connect your DRAFTER model to the BOTTOM port (labeled "Drafter").'
      );
    }

    // Create lazy loader for verifier (index 0 - top port, labeled "Verifier")
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

    // Domain input order (same as dynamic inputs template)
    // Only domains in this list can have dedicated model inputs
    const domainInputOrder: DomainType[] = [
      'code', 'math', 'data', 'creative', 'legal', 'medical', 'financial', 'science'
    ];

    // Build dynamic index mapping based on which domains are actually enabled
    // Inputs: 0=Verifier, 1=Drafter, then enabled domains in order
    const domainInputMap = new Map<DomainType, number>();
    let inputIndex = 2; // Start after Verifier (0) and Drafter (1)

    for (const domain of domainInputOrder) {
      if (enabledDomains.includes(domain)) {
        domainInputMap.set(domain, inputIndex);
        inputIndex++;
      }
    }

    // Create domain model getters for enabled domains
    const domainModelGetters = new Map<DomainType, () => Promise<BaseChatModel | undefined>>();

    for (const domain of enabledDomains) {
      const domainIndex = domainInputMap.get(domain);
      if (domainIndex !== undefined) {
        domainModelGetters.set(domain, async () => {
          try {
            const domainData = await this.getInputConnectionData('ai_languageModel' as any, domainIndex);
            const domainModel = (Array.isArray(domainData) ? domainData[0] : domainData) as BaseChatModel;
            if (domainModel) {
              // Store in domain config
              const config = domainConfigs.get(domain) || {
                enabled: true,
                threshold: qualityThreshold,
                temperature: 0.7,
              };
              config.model = domainModel;
              domainConfigs.set(domain, config);
              return domainModel;
            }
          } catch (e) {
            console.log(`No ${domain} model connected, using drafter as fallback`);
          }
          return undefined;
        });
      }
    }

    // Eagerly load domain models
    for (const [domain, getter] of domainModelGetters.entries()) {
      await getter();
    }

    // Debug info
    const getDrafterInfo = () => {
      const type = typeof drafterModel._llmType === 'function' ? drafterModel._llmType() : 'unknown';
      const modelName = (drafterModel as any).modelName || (drafterModel as any).model || 'unknown';
      return `${type} (${modelName})`;
    };

    console.log('🚀 CascadeFlow v2 initialized');
    console.log(`   PORT MAPPING:`);
    console.log(`   ├─ TOP port (labeled "Verifier") → VERIFIER model: lazy-loaded`);
    console.log(`   └─ BOTTOM port (labeled "Drafter") → DRAFTER model: ${getDrafterInfo()}`);
    console.log(`   Quality threshold: ${qualityThreshold}`);
    console.log(`   Semantic validation: ${useSemanticValidation ? 'enabled' : 'disabled'}`);
    console.log(`   Alignment scoring: ${useAlignmentScoring ? 'enabled' : 'disabled'}`);
    console.log(`   Complexity routing: ${useComplexityRouting ? 'enabled' : 'disabled'}`);
    console.log(`   Circuit breaker: ${useCircuitBreaker ? 'enabled' : 'disabled'}`);
    console.log(`   Domain routing: ${enableDomainRouting ? 'enabled' : 'disabled'}`);
    if (enabledDomains.length > 0) {
      console.log(`   Enabled domains: ${enabledDomains.join(', ')}`);
    }

    // Create and return the cascade model
    const cascadeModel = new CascadeChatModel(
      drafterModel,
      verifierModelGetter,
      qualityThreshold,
      useSemanticValidation,
      useAlignmentScoring,
      useComplexityRouting,
      enableDomainRouting,
      enabledDomains,
      domainModelGetters,
      domainConfigs,
      useCircuitBreaker
    );

    return {
      response: cascadeModel,
    };
  }
}
