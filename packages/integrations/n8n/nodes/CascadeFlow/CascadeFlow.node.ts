import {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
  NodeOperationError,
} from 'n8n-workflow';

import { CascadeAgent, ModelConfig } from '@cascadeflow/core';

export class cascadeflow implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'cascadeflow',
    name: 'cascadeFlow',
    icon: 'file:cascadeflow.svg',
    group: ['transform'],
    version: 1,
    subtitle: '={{$parameter["operation"]}}',
    description: 'Smart AI model cascading with 40-85% cost savings',
    defaults: {
      name: 'cascadeflow',
    },
    inputs: ['main'],
    outputs: ['main'],
    credentials: [
      {
        name: 'cascadeFlowApi',
        required: true,
      },
    ],
    properties: [
      {
        displayName: 'Operation',
        name: 'operation',
        type: 'options',
        noDataExpression: true,
        options: [
          {
            name: 'Generate Text',
            value: 'generateText',
            description: 'Generate AI response with cascading',
            action: 'Generate text with cascading',
          },
          {
            name: 'Generate with Tools',
            value: 'generateWithTools',
            description: 'Generate AI response with tool calling',
            action: 'Generate with tool calling',
          },
        ],
        default: 'generateText',
      },

      // Input message
      {
        displayName: 'Message',
        name: 'message',
        type: 'string',
        default: '',
        required: true,
        typeOptions: {
          rows: 4,
        },
        description: 'The message or query to send to AI',
        placeholder: 'What is the capital of France?',
      },

      // Model Configuration
      {
        displayName: 'Models Configuration',
        name: 'modelsConfig',
        type: 'fixedCollection',
        typeOptions: {
          multipleValues: false,
        },
        default: {},
        options: [
          {
            name: 'models',
            displayName: 'Models',
            values: [
											{
												displayName: 'Draft Model Cost',
												name: 'draftCost',
												type: 'number',
												default: 0.000375,
												description: 'Cost per 1K tokens (blended)',
											},
											{
												displayName: 'Draft Model Name',
												name: 'draftModel',
												type: 'string',
												default: 'gpt-4o-mini',
												description: 'Model name for draft generation',
												placeholder: 'gpt-4o-mini',
											},
											{
												displayName: 'Draft Model Provider',
												name: 'draftProvider',
												type: 'options',
												default: 'openai',
												options: [
													{
														name: 'Anthropic',
														value: 'anthropic',
													},
													{
														name: 'Groq',
														value: 'groq',
													},
													{
														name: 'Ollama (Local)',
														value: 'ollama',
													},
													{
														name: 'OpenAI',
														value: 'openai',
													},
													{
														name: 'Together AI',
														value: 'together',
													},
												],
												description: 'Provider for the cheap draft model',
											},
											{
												displayName: 'Verifier Model Cost',
												name: 'verifierCost',
												type: 'number',
												default: 0.00625,
												description: 'Cost per 1K tokens (blended)',
											},
											{
												displayName: 'Verifier Model Name',
												name: 'verifierModel',
												type: 'string',
												default: 'gpt-4o',
												description: 'Model name for verification',
												placeholder: 'gpt-4o',
											},
											{
												displayName: 'Verifier Model Provider',
												name: 'verifierProvider',
												type: 'options',
												default: 'openai',
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
												description: 'Provider for the expensive verifier model',
											},
									],
          },
        ],
      },

      // Quality Configuration
      {
        displayName: 'Quality Settings',
        name: 'qualitySettings',
        type: 'fixedCollection',
        typeOptions: {
          multipleValues: false,
        },
        default: {},
        options: [
          {
            name: 'quality',
            displayName: 'Quality',
            values: [
              {
                displayName: 'Quality Threshold',
                name: 'threshold',
                type: 'number',
                default: 0.7,
                typeOptions: {
                  minValue: 0,
                  maxValue: 1,
                  numberPrecision: 2,
                },
                description: 'Minimum quality score to accept draft (0-1)',
              },
              {
                displayName: 'Require Minimum Tokens',
                name: 'requireMinimumTokens',
                type: 'number',
                default: 10,
                typeOptions: {
                  minValue: 0,
                },
                description: 'Minimum response length in tokens',
              },
            ],
          },
        ],
      },

      // Advanced Options
      {
        displayName: 'Advanced Options',
        name: 'advancedOptions',
        type: 'collection',
        default: {},
        placeholder: 'Add Option',
        options: [
          {
            displayName: 'Max Tokens',
            name: 'maxTokens',
            type: 'number',
            default: 1000,
            description: 'Maximum tokens to generate',
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
            description: 'Sampling temperature (0-2)',
          },
          {
            displayName: 'System Prompt',
            name: 'systemPrompt',
            type: 'string',
            default: '',
            typeOptions: {
              rows: 3,
            },
            description: 'Optional system prompt',
          },
        ],
      },

      // Tool Calling (for generateWithTools operation)
      {
        displayName: 'Tools',
        name: 'tools',
        type: 'json',
        displayOptions: {
          show: {
            operation: ['generateWithTools'],
          },
        },
        default: '[]',
        description: 'Tools in OpenAI format (JSON array)',
        placeholder: '[{"type": "function", "function": {"name": "get_weather", ...}}]',
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
    const items = this.getInputData();
    const returnData: INodeExecutionData[] = [];

    // Get credentials
    const credentials = await this.getCredentials('cascadeFlowApi');

    // Helper to get API key for provider (moved inside execute for proper 'this' context)
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

    for (let itemIndex = 0; itemIndex < items.length; itemIndex++) {
      try {
        // Get parameters
        const operation = this.getNodeParameter('operation', itemIndex) as string;
        const message = this.getNodeParameter('message', itemIndex) as string;
        const modelsConfig = this.getNodeParameter('modelsConfig', itemIndex, {}) as any;
        const qualitySettings = this.getNodeParameter('qualitySettings', itemIndex, {}) as any;
        const advancedOptions = this.getNodeParameter('advancedOptions', itemIndex, {}) as any;
        const outputMode = this.getNodeParameter('output', itemIndex, 'fullMetrics') as string;

        // Extract model configuration
        const models = modelsConfig.models || {};
        const quality = qualitySettings.quality || {};

        // Build model configs
        const modelConfigs: ModelConfig[] = [
          // Draft model
          {
            name: models.draftModel || 'gpt-4o-mini',
            provider: models.draftProvider || 'openai',
            cost: models.draftCost || 0.000375,
            apiKey: getApiKeyForProvider(credentials, models.draftProvider || 'openai'),
          },
          // Verifier model
          {
            name: models.verifierModel || 'gpt-4o',
            provider: models.verifierProvider || 'openai',
            cost: models.verifierCost || 0.00625,
            apiKey: getApiKeyForProvider(credentials, models.verifierProvider || 'openai'),
          },
        ];

        // Create CascadeAgent
        const agent = new CascadeAgent({
          models: modelConfigs,
          quality: {
            threshold: quality.threshold || 0.7,
            requireMinimumTokens: quality.requireMinimumTokens || 10,
          },
        });

        // Prepare run options
        const runOptions: any = {
          maxTokens: advancedOptions.maxTokens,
          temperature: advancedOptions.temperature,
          systemPrompt: advancedOptions.systemPrompt,
        };

        // Add tools if generateWithTools operation
        if (operation === 'generateWithTools') {
          const toolsJson = this.getNodeParameter('tools', itemIndex, '[]') as string;
          try {
            runOptions.tools = JSON.parse(toolsJson);
          } catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            throw new NodeOperationError(
              this.getNode(),
              `Invalid tools JSON: ${errorMessage}`,
              { itemIndex }
            );
          }
        }

        // Execute cascade
        const result = await agent.run(message, runOptions);

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
