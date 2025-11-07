import type {
  INodeType,
  INodeTypeDescription,
  ISupplyDataFunctions,
  SupplyData,
} from 'n8n-workflow';

import { NodeConnectionType, NodeOperationError } from 'n8n-workflow';

import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import { BaseMessage, AIMessage } from '@langchain/core/messages';
import { ChatResult, ChatGeneration } from '@langchain/core/outputs';

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
      const drafterResult = await this.drafterModel._generate(messages, options, runManager);
      const drafterMessage = drafterResult.generations[0].message;

      // Step 2: Simple quality check (can be enhanced)
      // For now, we'll just check if the response is substantive
      const responseText = drafterMessage.content.toString();
      const qualityScore = Math.min(responseText.length / 100, 1.0); // Simple heuristic

      // Step 3: If quality is sufficient, return drafter response
      if (qualityScore >= this.qualityThreshold) {
        return drafterResult;
      }

      // Step 4: Otherwise, escalate to verifier
      const verifierResult = await this.verifierModel._generate(messages, options, runManager);
      return verifierResult;
    } catch (error) {
      // Fallback to verifier on error
      return await this.verifierModel._generate(messages, options, runManager);
    }
  }
}

export class LmChatCascadeFlow implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'CascadeFlow Chat Model',
    name: 'lmChatCascadeFlow',
    icon: 'file:cascadeflow.svg',
    group: ['transform'],
    version: 1,
    description: 'Smart AI model cascading with 40-85% cost savings. Connects two chat models (drafter and verifier) and intelligently cascades between them.',
    defaults: {
      name: 'CascadeFlow Chat Model',
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
    // Sub-node: no regular inputs, takes AI model connections
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
    // Outputs an AI model that can be connected to Agent
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
    // Get the quality threshold parameter
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
        'Drafter model is required. Please connect an AI chat model to the "Drafter Model" input.'
      );
    }

    if (!verifierModel) {
      throw new NodeOperationError(
        this.getNode(),
        'Verifier model is required. Please connect an AI chat model to the "Verifier Model" input.'
      );
    }

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
