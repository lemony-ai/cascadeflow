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
import { ChatResult, ChatGeneration } from '@langchain/core/outputs';

// Quality validation - optional import, fallback if unavailable
let QualityValidator: any;
let CASCADE_QUALITY_CONFIG: any;
try {
  const cascadeCore = require('@cascadeflow/core');
  QualityValidator = cascadeCore.QualityValidator;
  CASCADE_QUALITY_CONFIG = cascadeCore.CASCADE_QUALITY_CONFIG;
} catch (e) {
  // @cascadeflow/core not available - use simple validation
  console.warn('⚠️  @cascadeflow/core not available, using simple quality check');
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

  constructor(
    drafterModel: BaseChatModel,
    verifierModelGetter: () => Promise<BaseChatModel>,
    qualityThreshold: number = 0.7
  ) {
    super({});
    this.drafterModel = drafterModel;
    this.verifierModelGetter = verifierModelGetter;
    this.qualityThreshold = qualityThreshold;

    // Initialize quality validator with CASCADE-optimized config (if available)
    if (QualityValidator && CASCADE_QUALITY_CONFIG) {
      try {
        this.qualityValidator = new QualityValidator({
          ...CASCADE_QUALITY_CONFIG,
          minConfidence: qualityThreshold,
        });
        console.log('✅ CascadeFlow quality validator initialized');
      } catch (e) {
        console.warn('⚠️  Quality validator initialization failed, using simple check');
        this.qualityValidator = null;
      }
    } else {
      this.qualityValidator = null;
    }
  }

  private async getVerifierModel(): Promise<BaseChatModel> {
    if (!this.verifierModel) {
      console.log('   🔄 Loading verifier model...');
      this.verifierModel = await this.verifierModelGetter();
    }
    return this.verifierModel;
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
      // Step 1: Try the drafter model
      await runManager?.handleText('🎯 CascadeFlow: Trying drafter model...\n');
      console.log('🎯 CascadeFlow: Trying drafter model...');
      const drafterStartTime = Date.now();
      const drafterMessage = await this.drafterModel.invoke(messages, options);
      const drafterLatency = Date.now() - drafterStartTime;

      this.drafterCount++;

      // Step 2: Quality check using CascadeFlow validator (or simple fallback)
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

      // Step 3: If quality is sufficient, return drafter response
      if (validationResult.passed) {
        // Estimate cost savings
        const estimatedDrafterCost = 0.0001; // $0.0001 per request (rough estimate)
        const estimatedVerifierCost = 0.0016; // $0.0016 per request (rough estimate)
        const savings = ((estimatedVerifierCost - estimatedDrafterCost) / estimatedVerifierCost * 100).toFixed(1);

        const flowLog = `\n┌─────────────────────────────────────────┐\n│  ✅ FLOW: DRAFTER ACCEPTED (FAST PATH) │\n└─────────────────────────────────────────┘\n   Query → Drafter → Quality Check ✅ → Response\n   ⚡ Fast & Cheap: Used drafter model only\n   Confidence: ${validationResult.confidence.toFixed(2)} (threshold: ${this.qualityThreshold})\n   Quality score: ${validationResult.score.toFixed(2)}\n   Latency: ${drafterLatency}ms\n   💰 Cost savings: ~${savings}% (used cheap model)\n   📊 Stats: ${this.drafterCount} drafter, ${this.verifierCount} verifier\n`;

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
          cost_savings_percent: parseFloat(savings),
          model_used: 'drafter'
        };

        return {
          generations: [{
            text: drafterMessage.content.toString(),
            message: drafterMessage,
          }],
        };
      }

      // Step 4: Otherwise, escalate to verifier
      const escalateLog = `\n┌────────────────────────────────────────────────┐\n│  ⚠️  FLOW: ESCALATED TO VERIFIER (SLOW PATH)  │\n└────────────────────────────────────────────────┘\n   Query → Drafter → Quality Check ❌ → Verifier → Response\n   🔄 Escalating: Drafter quality too low, using verifier\n   Confidence: ${validationResult.confidence.toFixed(2)} < ${this.qualityThreshold} (threshold)\n   Reason: ${validationResult.reason}\n   Drafter latency: ${drafterLatency}ms\n   🔄 Loading verifier model...\n`;

      await runManager?.handleText(escalateLog);
      console.log(escalateLog);

      const verifierStartTime = Date.now();
      const verifierModel = await this.getVerifierModel();
      const verifierMessage = await verifierModel.invoke(messages, options);
      const verifierLatency = Date.now() - verifierStartTime;

      this.verifierCount++;

      const totalLatency = drafterLatency + verifierLatency;
      const acceptanceRate = (this.drafterCount / (this.drafterCount + this.verifierCount) * 100).toFixed(1);

      const completionLog = `   ✅ Verifier completed successfully\n   Verifier latency: ${verifierLatency}ms\n   Total latency: ${totalLatency}ms (drafter: ${drafterLatency}ms + verifier: ${verifierLatency}ms)\n   💰 Cost: Full verifier cost (0% savings this request)\n   📊 Stats: ${this.drafterCount} drafter (${acceptanceRate}%), ${this.verifierCount} verifier\n`;

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
        cost_savings_percent: 0,
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
      const verifierMessage = await verifierModel.invoke(messages, options);
      this.verifierCount++;

      const fallbackCompleteLog = `   ✅ Verifier fallback completed successfully\n   💰 Cost: Full verifier cost (fallback due to error)\n`;

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
        default: 0.7,
        typeOptions: {
          minValue: 0,
          maxValue: 1,
          numberPrecision: 2,
        },
        description: 'Minimum quality score (0-1) to accept drafter response. Lower = more cost savings, higher = better quality.',
      },
    ],
  };

  async supplyData(this: ISupplyDataFunctions): Promise<SupplyData> {
    // Get parameters
    const qualityThreshold = this.getNodeParameter('qualityThreshold', 0, 0.7) as number;

    // Get the drafter model immediately (at index 1 - second in inputs array, but fetched first)
    const drafterData = await this.getInputConnectionData('ai_languageModel' as any, 1);
    const drafterModel = (Array.isArray(drafterData) ? drafterData[0] : drafterData) as BaseChatModel;

    if (!drafterModel) {
      throw new NodeOperationError(
        this.getNode(),
        'Drafter model is required. Please connect an AI chat model (OpenAI, Anthropic, Ollama, etc.) to the "Drafter" input.'
      );
    }

    // Create a lazy loader for the verifier model (only fetched when needed) (at index 0)
    const verifierModelGetter = async () => {
      const verifierData = await this.getInputConnectionData('ai_languageModel' as any, 0);
      const verifierModel = (Array.isArray(verifierData) ? verifierData[0] : verifierData) as BaseChatModel;

      if (!verifierModel) {
        throw new NodeOperationError(
          this.getNode(),
          'Verifier model is required. Please connect an AI chat model (OpenAI, Anthropic, Ollama, etc.) to the "Verifier" input.'
        );
      }

      return verifierModel;
    };

    console.log('🚀 CascadeFlow initialized');
    console.log(`   Drafter: ${typeof drafterModel._llmType === 'function' ? drafterModel._llmType() : 'connected'}`);
    console.log(`   Verifier: lazy-loaded (will fetch only if needed)`);
    console.log(`   Quality threshold: ${qualityThreshold}`);

    // Create and return the cascade model with lazy verifier
    const cascadeModel = new CascadeChatModel(
      drafterModel,
      verifierModelGetter,
      qualityThreshold
    );

    return {
      response: cascadeModel,
    };
  }
}
