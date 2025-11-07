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
    version: 3,
    subtitle: 'AI Model Cascading',
    description: 'Smart AI model cascading with 40-85% cost savings',
    defaults: {
      name: 'CascadeFlow',
    },
    // eslint-disable-next-line n8n-nodes-base/node-class-description-inputs-wrong-regular-node
    inputs: ['main', 'main', 'main'],
    inputNames: ['Chat/Agent Output', 'Drafter Provider', 'Verifier Provider'],
    // eslint-disable-next-line n8n-nodes-base/node-class-description-outputs-wrong
    outputs: ['main', 'main'],
    outputNames: ['Draft Accepted', 'Escalated to Verifier'],
    properties: [
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

      // Split Output by Path
      {
        displayName: 'Split Output by Path',
        name: 'splitOutput',
        type: 'boolean',
        default: false,
        description: 'Whether to split output into two connectors: one for draft-accepted responses, one for escalated responses. Enables visual flow tracking.',
      },

      // Output Options
      {
        displayName: 'Output Format',
        name: 'output',
        type: 'options',
        default: 'contentOnly',
        options: [
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
          {
            name: 'Full Metrics',
            value: 'fullMetrics',
            description: 'Return response + all cascade metrics',
          },
        ],
        description: 'What data to return',
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const returnData: INodeExecutionData[] = [];
    const escalatedData: INodeExecutionData[] = [];

    // Get data from all three inputs
    const inputData = this.getInputData(0); // Input (prompt/query)
    const drafterInputData = this.getInputData(1); // Drafter model
    const verifierInputData = this.getInputData(2); // Verifier model

    // Helper to extract model config from provider node output
    const extractModelConfig = (providerData: INodeExecutionData[], inputName: string): ModelConfig => {
      if (!providerData || providerData.length === 0) {
        throw new NodeOperationError(
          this.getNode(),
          `No data received from ${inputName} input. Please connect a provider node (OpenAI, Anthropic, vLLM, Ollama, etc.).`
        );
      }

      const data = providerData[0].json;

      // Extract model information - handle various provider formats
      // OpenAI, Anthropic, Groq typically use 'model'
      // Some custom providers might use 'modelName' or 'name'
      const modelName = (data.model as string) ||
                       (data.modelName as string) ||
                       (data.name as string) ||
                       (data.model_name as string) ||
                       'gpt-4o-mini';

      // Try to detect provider from various fields
      let providerStr = (data.provider as string) ||
                        (data.providerName as string) ||
                        '';

      // If no explicit provider, try to infer from model name or base_url
      if (!providerStr) {
        if (modelName.includes('gpt') || modelName.includes('o1') || modelName.includes('o3')) {
          providerStr = 'openai';
        } else if (modelName.includes('claude')) {
          providerStr = 'anthropic';
        } else if (modelName.includes('llama') || modelName.includes('mixtral') || modelName.includes('qwen')) {
          // Check for vLLM or Ollama
          const baseUrl = (data.baseUrl as string) || (data.base_url as string) || '';
          if (baseUrl.includes('ollama') || baseUrl.includes('11434')) {
            providerStr = 'ollama';
          } else {
            providerStr = 'vllm';
          }
        } else {
          providerStr = 'openai'; // Default fallback
        }
      }

      // Extract API configuration
      const apiKey = (data.apiKey as string) ||
                     (data.api_key as string) ||
                     (data.token as string) ||
                     '';

      const baseUrl = (data.baseUrl as string) ||
                      (data.base_url as string) ||
                      undefined;

      // Cost estimation - use provided cost or estimate based on provider
      let cost = (data.cost as number) || (data.modelCost as number);
      if (!cost) {
        // Rough estimates per 1K tokens (blended input/output)
        if (providerStr === 'anthropic') {
          cost = modelName.includes('opus') ? 0.03 : 0.006;
        } else if (providerStr === 'openai') {
          if (modelName.includes('o1') || modelName.includes('o3')) cost = 0.03;
          else if (modelName.includes('gpt-4')) cost = 0.006;
          else cost = 0.0004;
        } else {
          cost = 0.001; // Default for local/other providers
        }
      }

      const config: ModelConfig = {
        name: modelName,
        provider: providerStr as any,
        cost,
        apiKey,
      };

      // Add baseUrl if provided (for vLLM, Ollama, custom endpoints)
      if (baseUrl) {
        (config as any).baseUrl = baseUrl;
      }

      return config;
    };

    // Extract model configurations from provider inputs
    const drafterConfig = extractModelConfig(drafterInputData, 'Drafter Model');
    const verifierConfig = extractModelConfig(verifierInputData, 'Verifier Model');

    const modelConfigs: ModelConfig[] = [drafterConfig, verifierConfig];

    // Get split output setting (same for all items)
    const splitOutput = this.getNodeParameter('splitOutput', 0, false) as boolean;

    // Process each input item
    for (let itemIndex = 0; itemIndex < inputData.length; itemIndex++) {
      try {
        // Get parameters
        const qualityThreshold = this.getNodeParameter('qualityThreshold', itemIndex, 0.7) as number;
        const outputMode = this.getNodeParameter('output', itemIndex, 'contentOnly') as string;

        // Extract prompt from input data - support various field names
        const item = inputData[itemIndex].json;
        const prompt = (item.prompt as string) ||
                      (item.message as string) ||
                      (item.query as string) ||
                      (item.text as string) ||
                      (item.input as string) ||
                      JSON.stringify(item);

        if (!prompt || prompt.length === 0) {
          throw new NodeOperationError(
            this.getNode(),
            'No prompt found in input data. Connect a node that provides prompt, message, query, text, or input field.',
            { itemIndex }
          );
        }

        // Extract tools if provided (for function calling)
        const tools = (item.tools as any[]) || undefined;

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
        if (tools) {
          runOptions.tools = tools;
        }

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

          default:
            outputData = result;
        }

        const outputItem = {
          json: outputData,
          pairedItem: { item: itemIndex },
        };

        // Route to appropriate output based on splitOutput setting
        if (splitOutput) {
          if (result.draftAccepted) {
            returnData.push(outputItem);
          } else {
            escalatedData.push(outputItem);
          }
        } else {
          returnData.push(outputItem);
        }

      } catch (error) {
        if (this.continueOnFail()) {
          const errorMessage = error instanceof Error ? error.message : String(error);
          const errorItem = {
            json: {
              error: errorMessage,
            },
            pairedItem: { item: itemIndex },
          };
          // Errors always go to first output
          returnData.push(errorItem);
          continue;
        }
        throw error;
      }
    }

    // Return appropriate outputs based on splitOutput setting
    if (splitOutput) {
      // Split mode: Draft accepted goes to output 0, escalated to output 1
      return [returnData, escalatedData];
    } else {
      // Single output mode: All results go to output 0, output 1 is empty
      return [returnData, []];
    }
  }
}
