import {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
  NodeOperationError,
} from 'n8n-workflow';

import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

export class CascadeFlow implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'CascadeFlow',
    name: 'cascadeFlow',
    icon: 'file:cascadeflow.svg',
    group: ['transform'],
    version: 2,
    subtitle: 'AI Model Cascading',
    description: 'Smart AI model cascading with 40-85% cost savings',
    defaults: {
      name: 'CascadeFlow',
    },
    // eslint-disable-next-line n8n-nodes-base/node-class-description-inputs-wrong-regular-node
    inputs: ['main', 'main'],
    inputNames: ['Drafter Model', 'Verifier Model'],
    outputs: ['main'],
    credentials: [
      {
        name: 'cascadeFlowApi',
        required: true,
      },
    ],
    properties: [
      // Input message
      {
        displayName: 'Prompt',
        name: 'prompt',
        type: 'string',
        default: '',
        required: true,
        typeOptions: {
          rows: 4,
        },
        description: 'The message or query to send to AI models',
        placeholder: 'What is the capital of France?',
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

      // Output Options
      {
        displayName: 'Output',
        name: 'output',
        type: 'options',
        default: 'fullMetrics',
        options: [
          {
            name: 'Full Metrics',
            value: 'fullMetrics',
            description: 'Return response + all cascade metrics',
          },
          {
            name: 'Content Only',
            value: 'contentOnly',
            description: 'Return only the AI response text',
          },
          {
            name: 'Metrics Summary',
            value: 'metricsSummary',
            description: 'Return response + key metrics (cost, savings, model)',
          },
        ],
        description: 'What data to return',
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const returnData: INodeExecutionData[] = [];

    // Get data from both inputs
    const drafterInputData = this.getInputData(0); // Drafter model input
    const verifierInputData = this.getInputData(1); // Verifier model input

    // Get credentials
    const credentials = await this.getCredentials('cascadeFlowApi');

    // Helper to get API key for provider
    const getApiKeyForProvider = (creds: any, provider: string): string => {
      const keyMap: Record<string, string> = {
        openai: 'openaiApiKey',
        anthropic: 'anthropicApiKey',
        groq: 'groqApiKey',
        together: 'togetherApiKey',
        huggingface: 'huggingfaceApiKey',
      };

      const keyName = keyMap[provider];
      if (!keyName) {
        return '';
      }

      return (creds[keyName] as string) || '';
    };

    // Helper to extract model config from input data
    const extractModelConfig = (inputData: INodeExecutionData[], inputName: string): ModelConfig => {
      if (!inputData || inputData.length === 0) {
        throw new NodeOperationError(
          this.getNode(),
          `No data received from ${inputName} input. Please connect an OpenAI or other provider node.`
        );
      }

      const data = inputData[0].json;

      // Try to extract model information from the input
      // This works with OpenAI node output and similar provider nodes
      const modelName = (data.model as string) || (data.modelName as string) || 'gpt-4o-mini';
      const providerStr = (data.provider as string) || 'openai';
      const cost = (data.cost as number) || (data.modelCost as number) || 0.001;

      return {
        name: modelName,
        provider: providerStr as any,
        cost,
        apiKey: getApiKeyForProvider(credentials, providerStr),
      };
    };

    // Extract model configurations from inputs
    const drafterConfig = extractModelConfig(drafterInputData, 'Drafter');
    const verifierConfig = extractModelConfig(verifierInputData, 'Verifier');

    const modelConfigs: ModelConfig[] = [drafterConfig, verifierConfig];

    for (let itemIndex = 0; itemIndex < drafterInputData.length; itemIndex++) {
      try {
        // Get parameters
        const prompt = this.getNodeParameter('prompt', itemIndex) as string;
        const qualityThreshold = this.getNodeParameter('qualityThreshold', itemIndex, 0.7) as number;
        const outputMode = this.getNodeParameter('output', itemIndex, 'fullMetrics') as string;

        // Create CascadeAgent
        const agent = new CascadeAgent({
          models: modelConfigs,
          quality: {
            threshold: qualityThreshold,
            requireMinimumTokens: 10,
          },
        });

        // Prepare run options
        const runOptions: any = {};


        // Execute cascade
        const result = await agent.run(prompt, runOptions);

        // Format output based on outputMode
        let outputData: any;

        switch (outputMode) {
          case 'contentOnly':
            outputData = {
              content: result.content,
              toolCalls: result.toolCalls,
            };
            break;

          case 'metricsSummary':
            outputData = {
              content: result.content,
              toolCalls: result.toolCalls,
              modelUsed: result.modelUsed,
              totalCost: result.totalCost,
              savingsPercentage: result.savingsPercentage,
              cascaded: result.cascaded,
              draftAccepted: result.draftAccepted,
              latencyMs: result.latencyMs,
            };
            break;

          case 'fullMetrics':
          default:
            outputData = {
              ...result,
              // Add n8n-friendly summary
              summary: {
                saved: `${result.savingsPercentage?.toFixed(1)}%`,
                cost: `$${result.totalCost.toFixed(6)}`,
                model: result.modelUsed,
                speed: `${result.latencyMs}ms`,
                status: result.draftAccepted ? '✅ Draft accepted' : '⚠️ Escalated to verifier',
              },
            };
            break;
        }

        returnData.push({
          json: outputData,
          pairedItem: { item: itemIndex },
        });

      } catch (error) {
        if (this.continueOnFail()) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          returnData.push({
            json: {
              error: errorMessage,
            },
            pairedItem: { item: itemIndex },
          });
          continue;
        }
        throw error;
      }
    }

    return [returnData];
  }
}
