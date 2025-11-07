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
import { ChatOpenAI } from '@langchain/openai';
import { ChatAnthropic } from '@langchain/anthropic';

/**
 * Custom CascadeChatModel that wraps two models (drafter and verifier)
 * and implements cascading logic
 */
class CascadeChatModel extends BaseChatModel {
  drafterModel: BaseChatModel;
  verifierModel: BaseChatModel;
  qualityThreshold: number;

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

      // Step 2: Simple quality check (can be enhanced)
      // For now, we'll just check if the response is substantive
      const responseText = drafterMessage.content.toString();
      const qualityScore = Math.min(responseText.length / 100, 1.0); // Simple heuristic

      // Step 3: If quality is sufficient, return drafter response
      if (qualityScore >= this.qualityThreshold) {
        console.log(`✅ CascadeFlow: Drafter accepted (quality: ${qualityScore.toFixed(2)}, latency: ${drafterLatency}ms)`);
        return drafterResult;
      }

      // Step 4: Otherwise, escalate to verifier
      console.log(`⚠️ CascadeFlow: Escalating to verifier (quality: ${qualityScore.toFixed(2)} < threshold: ${this.qualityThreshold})`);
      const verifierStartTime = Date.now();
      const verifierResult = await this.verifierModel._generate(messages, options, runManager);
      const verifierLatency = Date.now() - verifierStartTime;
      console.log(`✅ CascadeFlow: Verifier completed (latency: ${verifierLatency}ms, total: ${drafterLatency + verifierLatency}ms)`);
      return verifierResult;
    } catch (error) {
      // Fallback to verifier on error
      console.log(`❌ CascadeFlow: Drafter failed, falling back to verifier. Error: ${error instanceof Error ? error.message : String(error)}`);
      const verifierResult = await this.verifierModel._generate(messages, options, runManager);
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
    description: 'Smart AI model cascading with 40-85% cost savings. Configure two models (drafter and verifier) and intelligently cascade between them.',
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
    // Sub-node: no inputs
    // eslint-disable-next-line n8n-nodes-base/node-class-description-inputs-wrong-regular-node
    inputs: [],
    // Outputs an AI model that can be connected to Agent
    // eslint-disable-next-line n8n-nodes-base/node-class-description-outputs-wrong
    outputs: ['ai_languageModel' as any],
    outputNames: ['Model'],
    credentials: [
      {
        name: 'cascadeFlowApi',
        required: true,
      },
    ],
    properties: [
      // Drafter Model Configuration
      {
        displayName: 'Drafter Model',
        name: 'drafterModel',
        type: 'string',
        default: 'gpt-4o-mini',
        required: true,
        description: 'The cheaper model to try first (e.g., gpt-4o-mini, claude-3-5-haiku-20241022)',
        placeholder: 'gpt-4o-mini',
      },
      {
        displayName: 'Drafter Provider',
        name: 'drafterProvider',
        type: 'options',
        default: 'openai',
        required: true,
        options: [
          {
            name: 'OpenAI',
            value: 'openai',
          },
          {
            name: 'Anthropic',
            value: 'anthropic',
          },
          {
            name: 'Groq',
            value: 'groq',
          },
          {
            name: 'Together AI',
            value: 'together',
          },
        ],
        description: 'Provider for the drafter model',
      },

      // Verifier Model Configuration
      {
        displayName: 'Verifier Model',
        name: 'verifierModel',
        type: 'string',
        default: 'gpt-4o',
        required: true,
        description: 'The quality model to escalate to if needed (e.g., gpt-4o, claude-3-5-sonnet-20241022)',
        placeholder: 'gpt-4o',
      },
      {
        displayName: 'Verifier Provider',
        name: 'verifierProvider',
        type: 'options',
        default: 'openai',
        required: true,
        options: [
          {
            name: 'OpenAI',
            value: 'openai',
          },
          {
            name: 'Anthropic',
            value: 'anthropic',
          },
          {
            name: 'Groq',
            value: 'groq',
          },
          {
            name: 'Together AI',
            value: 'together',
          },
        ],
        description: 'Provider for the verifier model',
      },

      // Quality Threshold
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
    // Get credentials
    const credentials = await this.getCredentials('cascadeFlowApi');

    // Get parameters
    const drafterModelName = this.getNodeParameter('drafterModel', 0) as string;
    const drafterProvider = this.getNodeParameter('drafterProvider', 0) as string;
    const verifierModelName = this.getNodeParameter('verifierModel', 0) as string;
    const verifierProvider = this.getNodeParameter('verifierProvider', 0) as string;
    const qualityThreshold = this.getNodeParameter('qualityThreshold', 0, 0.7) as number;

    // Helper to create model based on provider
    const createModel = (provider: string, modelName: string): BaseChatModel => {
      const keyMap: Record<string, string> = {
        openai: 'openaiApiKey',
        anthropic: 'anthropicApiKey',
        groq: 'groqApiKey',
        together: 'togetherApiKey',
      };

      const keyName = keyMap[provider];
      const apiKey = credentials[keyName] as string;

      if (!apiKey) {
        throw new NodeOperationError(
          this.getNode(),
          `API key for ${provider} not found in credentials. Please configure the CascadeFlow API credentials.`
        );
      }

      switch (provider) {
        case 'openai':
        case 'groq':
        case 'together':
          return new ChatOpenAI({
            modelName,
            apiKey,
            configuration: provider === 'groq' ? {
              baseURL: 'https://api.groq.com/openai/v1',
            } : provider === 'together' ? {
              baseURL: 'https://api.together.xyz/v1',
            } : undefined,
          });

        case 'anthropic':
          return new ChatAnthropic({
            modelName,
            apiKey,
          });

        default:
          throw new NodeOperationError(
            this.getNode(),
            `Unsupported provider: ${provider}`
          );
      }
    };

    // Create drafter and verifier models
    const drafterModel = createModel(drafterProvider, drafterModelName);
    const verifierModel = createModel(verifierProvider, verifierModelName);

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
