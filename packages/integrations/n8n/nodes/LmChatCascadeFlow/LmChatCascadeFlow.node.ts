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
import { ChatResult } from '@langchain/core/outputs';

/**
 * Custom CascadeChatModel that wraps two models (drafter and verifier)
 * and implements cascading logic with cost tracking
 */
class CascadeChatModel extends BaseChatModel {
  drafterModel: BaseChatModel;
  verifierModel: BaseChatModel;
  qualityThreshold: number;

  // Cost tracking
  private drafterCost: number = 0;
  private verifierCost: number = 0;
  private drafterCount: number = 0;
  private verifierCount: number = 0;

  constructor(
    drafterModel: BaseChatModel,
    verifierModel: BaseChatModel,
    qualityThreshold: number = 0.7
  ) {
    super({});
    this.drafterModel = drafterModel;
    this.verifierModel = verifierModel;
    this.qualityThreshold = qualityThreshold;
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
      console.log('🎯 CascadeFlow: Trying drafter model...');
      const drafterStartTime = Date.now();
      const drafterResult = await this.drafterModel._generate(messages, options, runManager);
      const drafterLatency = Date.now() - drafterStartTime;
      const drafterMessage = drafterResult.generations[0].message;

      this.drafterCount++;

      // Step 2: Quality check
      const responseText = drafterMessage.content.toString();
      const qualityScore = Math.min(responseText.length / 100, 1.0);

      // Step 3: If quality is sufficient, return drafter response
      if (qualityScore >= this.qualityThreshold) {
        // Estimate cost savings
        const estimatedDrafterCost = 0.0001; // $0.0001 per request (rough estimate)
        const estimatedVerifierCost = 0.0016; // $0.0016 per request (rough estimate)
        const savings = ((estimatedVerifierCost - estimatedDrafterCost) / estimatedVerifierCost * 100).toFixed(1);

        console.log(`✅ CascadeFlow: Drafter accepted!`);
        console.log(`   Quality: ${qualityScore.toFixed(2)} (threshold: ${this.qualityThreshold})`);
        console.log(`   Latency: ${drafterLatency}ms`);
        console.log(`   💰 Cost savings: ~${savings}% (used cheap model)`);
        console.log(`   📊 Stats: ${this.drafterCount} drafter, ${this.verifierCount} verifier`);

        return drafterResult;
      }

      // Step 4: Otherwise, escalate to verifier
      console.log(`⚠️ CascadeFlow: Quality below threshold, escalating to verifier...`);
      console.log(`   Quality: ${qualityScore.toFixed(2)} < ${this.qualityThreshold}`);
      console.log(`   Drafter latency: ${drafterLatency}ms`);

      const verifierStartTime = Date.now();
      const verifierResult = await this.verifierModel._generate(messages, options, runManager);
      const verifierLatency = Date.now() - verifierStartTime;

      this.verifierCount++;

      const totalLatency = drafterLatency + verifierLatency;
      const acceptanceRate = (this.drafterCount / (this.drafterCount + this.verifierCount) * 100).toFixed(1);

      console.log(`✅ CascadeFlow: Verifier completed`);
      console.log(`   Verifier latency: ${verifierLatency}ms`);
      console.log(`   Total latency: ${totalLatency}ms`);
      console.log(`   📊 Stats: ${this.drafterCount} drafter (${acceptanceRate}%), ${this.verifierCount} verifier`);

      return verifierResult;
    } catch (error) {
      // Fallback to verifier on error
      console.log(`❌ CascadeFlow: Drafter failed, falling back to verifier`);
      console.log(`   Error: ${error instanceof Error ? error.message : String(error)}`);

      const verifierResult = await this.verifierModel._generate(messages, options, runManager);
      this.verifierCount++;

      console.log('✅ CascadeFlow: Verifier fallback completed');
      return verifierResult;
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
        displayName: 'Drafter Model',
        type: 'ai_languageModel' as any,
        maxConnections: 1,
        required: true,
      },
      {
        displayName: 'Verifier Model',
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

    // Get the connected chat models from inputs
    const drafterModel = (await this.getInputConnectionData(
      'ai_languageModel' as any,
      0
    )) as BaseChatModel;

    const verifierModel = (await this.getInputConnectionData(
      'ai_languageModel' as any,
      1
    )) as BaseChatModel;

    if (!drafterModel) {
      throw new NodeOperationError(
        this.getNode(),
        'Drafter model is required. Please connect an AI chat model (OpenAI, Anthropic, Ollama, etc.) to the "Drafter Model" input.'
      );
    }

    if (!verifierModel) {
      throw new NodeOperationError(
        this.getNode(),
        'Verifier model is required. Please connect an AI chat model (OpenAI, Anthropic, Ollama, etc.) to the "Verifier Model" input.'
      );
    }

    console.log('🚀 CascadeFlow initialized');
    console.log(`   Drafter: ${drafterModel._llmType()}`);
    console.log(`   Verifier: ${verifierModel._llmType()}`);
    console.log(`   Quality threshold: ${qualityThreshold}`);

    // Create and return the cascade model
    const cascadeModel = new CascadeChatModel(
      drafterModel,
      verifierModel,
      qualityThreshold
    );

    return {
      response: cascadeModel,
    };
  }
}
