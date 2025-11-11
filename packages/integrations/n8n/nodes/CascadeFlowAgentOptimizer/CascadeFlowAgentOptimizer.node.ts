import type {
	IExecuteFunctions,
	INodeExecutionData,
	INodeType,
	INodeTypeDescription,
} from 'n8n-workflow';

import { NodeConnectionType, NodeOperationError } from 'n8n-workflow';
import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { HumanMessage, AIMessage, SystemMessage, BaseMessage } from '@langchain/core/messages';
import { ChatResult } from '@langchain/core/outputs';
import { CostTracker } from './CostTracker';
import { ToolHandler } from './ToolHandler';
import { MemoryManager } from './MemoryManager';
import { ReasoningModelDetector } from './ReasoningModelDetector';
import { ComplexityAnalyzer, ComplexityAnalysis } from './ComplexityAnalyzer';
import { CascadeMetadata, NodeConfig, QualityMetrics, CostTrackingOutput } from './types';

let QualityValidator: any;
let CASCADE_QUALITY_CONFIG: any;
try {
	const cascadeCore = require('@cascadeflow/core');
	QualityValidator = cascadeCore.QualityValidator;
	CASCADE_QUALITY_CONFIG = cascadeCore.CASCADE_QUALITY_CONFIG;
} catch (e) {
	console.warn('⚠️  @cascadeflow/core not available, using simple quality validation');
}

export class CascadeFlowAgentOptimizer implements INodeType {
	description: INodeTypeDescription = {
		displayName: 'CascadeFlow Agent Optimizer',
		name: 'cascadeFlowAgentOptimizer',
		icon: 'file:cascadeflow-agent.svg',
		group: ['transform'],
		version: 1,
		description: 'Cost-optimized AI agent with intelligent model cascading, tool support, and comprehensive cost tracking',
		defaults: {
			name: 'CascadeFlow Agent',
		},
		codex: {
			categories: ['AI'],
			subcategories: {
				AI: ['Agents', 'Language Models', 'Cost Optimization'],
			},
			resources: {
				primaryDocumentation: [
					{
						url: 'https://github.com/lemony-ai/cascadeflow',
					},
				],
			},
		},
		inputs: [
			'main',
			{
				displayName: 'Drafter Model',
				type: 'ai_languageModel' as any,
				required: true,
				maxConnections: 1,
			},
			{
				displayName: 'Verifier Model',
				type: 'ai_languageModel' as any,
				required: true,
				maxConnections: 1,
			},
			{
				displayName: 'Tools',
				type: 'ai_tool' as any,
				required: false,
			},
			{
				displayName: 'Memory',
				type: 'ai_memory' as any,
				required: false,
				maxConnections: 1,
			},
		],
		outputs: [
			'main',
			'main',
		],
		outputNames: ['Response', 'Cost Tracking'],
		properties: [
			{
				displayName: 'Quality Threshold',
				name: 'qualityThreshold',
				type: 'number',
				default: 0.70,
				typeOptions: {
					minValue: 0,
					maxValue: 1,
					numberPrecision: 2,
				},
				description: 'Minimum quality score (0-1) to accept drafter response. Lower = more cost savings, higher = better quality.',
			},
			{
				displayName: 'Routing Strategy',
				name: 'routingStrategy',
				type: 'options',
				options: [
					{
						name: 'Always Cascade',
						value: 'always_cascade',
						description: 'Always try drafter first',
					},
					{
						name: 'Complexity-Based',
						value: 'complexity_based',
						description: 'Route based on query complexity',
					},
				],
				default: 'always_cascade',
				description: 'How to route queries to models',
			},
			{
				displayName: 'Enable Tools',
				name: 'enableTools',
				type: 'boolean',
				default: false,
				description: 'Whether to enable tool calling for agent actions',
			},
			{
				displayName: 'Enable Memory',
				name: 'enableMemory',
				type: 'boolean',
				default: false,
				description: 'Whether to enable conversation memory and context management',
			},
			{
				displayName: 'Enable Cost Tracking Output',
				name: 'enableCostTracking',
				type: 'boolean',
				default: false,
				description: 'Whether to output detailed cost analytics to second output port',
			},
			{
				displayName: 'Cost Budget Limit (USD)',
				name: 'costBudgetLimit',
				type: 'number',
				default: 0,
				description: 'Maximum cost per request in USD (0 = unlimited). Throws error if exceeded.',
			},
			{
				displayName: 'Logging Level',
				name: 'loggingLevel',
				type: 'options',
				options: [
					{ name: 'None', value: 'none' },
					{ name: 'Basic', value: 'basic' },
					{ name: 'Detailed', value: 'detailed' },
					{ name: 'Debug', value: 'debug' },
				],
				default: 'detailed',
				description: 'Level of logging detail',
			},
		],
	};

	async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
		const items = this.getInputData();
		const returnData: INodeExecutionData[] = [];
		const costTrackingData: INodeExecutionData[] = [];

		const config: NodeConfig = {
			qualityThreshold: this.getNodeParameter('qualityThreshold', 0, 0.70) as number,
			routingStrategy: this.getNodeParameter('routingStrategy', 0, 'always_cascade') as any,
			enableDomainRouting: false,
			domainDetectionMethod: 'rule_based',
			enableTools: this.getNodeParameter('enableTools', 0, false) as boolean,
			toolExecutionStrategy: 'always_cascade',
			enableMemory: this.getNodeParameter('enableMemory', 0, false) as boolean,
			enableCostTracking: this.getNodeParameter('enableCostTracking', 0, false) as boolean,
			costBudgetLimit: this.getNodeParameter('costBudgetLimit', 0, 0) as number,
			enableReasoningModels: true,
			reasoningEffort: 'medium',
			enableAdaptiveThreshold: false,
			loggingLevel: this.getNodeParameter('loggingLevel', 0, 'detailed') as any,
		};

		let drafterModel = (await this.getInputConnectionData('ai_languageModel' as any, 0)) as BaseChatModel;
		let verifierModel = (await this.getInputConnectionData('ai_languageModel' as any, 1)) as BaseChatModel;

		if (!drafterModel) {
			throw new NodeOperationError(
				this.getNode(),
				'Drafter model is required. Please connect a Language Model to the Drafter input.'
			);
		}

		if (!verifierModel) {
			throw new NodeOperationError(
				this.getNode(),
				'Verifier model is required. Please connect a Language Model to the Verifier input.'
			);
		}

		const toolHandler = new ToolHandler(config.enableTools);
		const memoryManager = new MemoryManager(config.enableMemory);

		if (config.enableTools) {
			try {
				const n8nTools = (await this.getInputConnectionData('ai_tool' as any, 2)) as any[];
				if (n8nTools) {
					await toolHandler.loadTools(Array.isArray(n8nTools) ? n8nTools : [n8nTools]);
				}
			} catch (error) {
				console.warn('Failed to load tools:', error);
			}
		}

		if (config.enableMemory) {
			try {
				const n8nMemory = await this.getInputConnectionData('ai_memory' as any, 3);
				if (n8nMemory) {
					await memoryManager.loadMemory(n8nMemory);
				}
			} catch (error) {
				console.warn('Failed to load memory:', error);
			}
		}

		if (config.enableReasoningModels) {
			const drafterConfig = ReasoningModelDetector.detectReasoningModel(drafterModel);
			const verifierConfig = ReasoningModelDetector.detectReasoningModel(verifierModel);

			if (drafterConfig.isReasoningModel) {
				console.warn('⚠️  Reasoning model detected as drafter - this is not recommended for cost optimization');
			}

			drafterModel = ReasoningModelDetector.applyReasoningConfig(
				drafterModel,
				drafterConfig,
				config.reasoningEffort
			);

			verifierModel = ReasoningModelDetector.applyReasoningConfig(
				verifierModel,
				verifierConfig,
				config.reasoningEffort
			);
		}

		const costTracker = new CostTracker(true);

		for (let i = 0; i < items.length; i++) {
			try {
				const input = items[i];
				const query = (input.json.query || input.json.input || input.json.chatInput || '') as string;

				if (!query) {
					throw new NodeOperationError(
						this.getNode(),
						`No query provided. Add a 'query', 'input', or 'chatInput' field to the input data.`,
						{ itemIndex: i }
					);
				}

				let messages: BaseMessage[];
				if (config.enableMemory && memoryManager.hasMemory()) {
					messages = memoryManager.getMessagesWithNewQuery(query);
				} else {
					messages = [new HumanMessage(query)];
				}

				let complexityAnalysis: ComplexityAnalysis | undefined;
				if (config.routingStrategy === 'complexity_based') {
					complexityAnalysis = ComplexityAnalyzer.analyzeComplexity(query);
				}

				const result = await executeCascade.call(
					this,
					drafterModel,
					verifierModel,
					messages,
					config,
					costTracker,
					complexityAnalysis,
					toolHandler,
					memoryManager
				);

				if (config.enableMemory) {
					await memoryManager.addUserMessage(query);
					await memoryManager.addAIMessage(result.response);
				}

				returnData.push({
					json: {
						query,
						response: result.response,
						metadata: result.metadata as any,
						...(complexityAnalysis && { complexity: complexityAnalysis }),
					},
					pairedItem: { item: i },
				});

				if (config.enableCostTracking) {
					const costOutput = {
						timestamp: new Date().toISOString(),
						requestId: `req_${Date.now()}_${i}`,
						query,
						response: result.response,
						cost: result.metadata.cost as any,
						quality: result.metadata.quality as any,
						performance: result.metadata.performance as any,
						...(complexityAnalysis && { complexity: complexityAnalysis }),
						metadata: {
							flow: result.metadata.flow,
							modelUsed: result.metadata.cost.modelUsed,
							acceptanceRate: result.metadata.acceptanceRate,
							totalRequests: result.metadata.requestCount,
						},
					};

					costTrackingData.push({
						json: costOutput as any,
						pairedItem: { item: i },
					});
				}

			} catch (error: any) {
				if (this.continueOnFail()) {
					returnData.push({
						json: {
							error: error?.message || 'Unknown error',
						},
						pairedItem: { item: i },
					});
					continue;
				}
				throw error;
			}
		}

		if (config.enableCostTracking) {
			return [returnData, costTrackingData];
		}

		return [returnData, []];
	}
}

async function executeCascade(
	this: IExecuteFunctions,
		drafterModel: BaseChatModel,
		verifierModel: BaseChatModel,
		messages: BaseMessage[],
		config: NodeConfig,
		costTracker: CostTracker,
		complexityAnalysis?: ComplexityAnalysis,
		toolHandler?: ToolHandler,
		memoryManager?: MemoryManager
	): Promise<{ response: string; metadata: CascadeMetadata }> {

		if (complexityAnalysis && config.routingStrategy === 'complexity_based') {
			log.call(this, config, 'detailed', `📊 Complexity Analysis: ${complexityAnalysis.level} (score: ${complexityAnalysis.score})`);
			log.call(this, config, 'detailed', `   ${complexityAnalysis.reasoning}`);

			if (!complexityAnalysis.shouldCascade) {
				log.call(this, config, 'detailed', `⚡ Skipping cascade - routing directly to verifier for ${complexityAnalysis.level} query`);
				return executeDirectVerifier.call(this, verifierModel, messages, config, costTracker, complexityAnalysis);
			}
		}

		const drafterStartTime = Date.now();

		log.call(this, config, 'detailed', `🎯 CascadeFlow: Trying drafter model...`);

		let drafterResult: ChatResult;
		try {
			const drafterResponse = await drafterModel.invoke(messages);
			drafterResult = {
				generations: [{
					text: drafterResponse.content.toString(),
					message: drafterResponse,
				}],
				llmOutput: (drafterResponse as any).response_metadata,
			};
		} catch (error: any) {
			log.call(this, config, 'basic', `❌ Drafter failed: ${error?.message}. Falling back to verifier...`);
			return executeVerifierFallback.call(this, verifierModel, messages, config, costTracker, error?.message || 'Unknown error');
		}

		const drafterLatency = Date.now() - drafterStartTime;
		const responseText = drafterResult.generations[0].text;

		const qualityResult = await validateQuality(responseText, messages, config);

		log.call(this, config, 'detailed', `   📊 Quality: confidence=${qualityResult.confidence.toFixed(2)}, score=${qualityResult.qualityScore.toFixed(2)}`);

		if (qualityResult.passed) {
			const cost = costTracker.calculateCost(
				drafterModel,
				verifierModel,
				messages,
				drafterResult,
				undefined,
				'drafter_accepted'
			);

			checkBudgetLimit.call(this, cost.totalCost, config);

			const stats = costTracker.getStatistics();

			log.call(this, config, 'basic', `✅ DRAFTER ACCEPTED - Cost: $${cost.totalCost.toFixed(6)}, Saved: ${cost.savingsPercentage.toFixed(1)}%`);

			const metadata: CascadeMetadata = {
				flow: 'drafter_accepted',
				cost,
				quality: qualityResult,
				performance: {
					latencyMs: drafterLatency,
					drafterLatencyMs: drafterLatency,
				},
				requestCount: stats.totalRequests,
				acceptanceRate: stats.acceptanceRate,
			};

			return {
				response: responseText,
				metadata,
			};
		}

		log.call(this, config, 'detailed', `⚠️  Quality below threshold. Escalating to verifier...`);
		log.call(this, config, 'detailed', `   Reason: ${qualityResult.reason}`);

		const verifierStartTime = Date.now();
		const verifierResponse = await verifierModel.invoke(messages);
		const verifierLatency = Date.now() - verifierStartTime;

		const verifierResult: ChatResult = {
			generations: [{
				text: verifierResponse.content.toString(),
				message: verifierResponse,
			}],
			llmOutput: (verifierResponse as any).response_metadata,
		};

		const cost = costTracker.calculateCost(
			drafterModel,
			verifierModel,
			messages,
			drafterResult,
			verifierResult,
			'escalated_to_verifier'
		);

		checkBudgetLimit.call(this, cost.totalCost, config);

		const stats = costTracker.getStatistics();
		const totalLatency = drafterLatency + verifierLatency;

		log.call(this, config, 'basic', `⚠️  ESCALATED TO VERIFIER - Total: $${cost.totalCost.toFixed(6)}, Latency: ${totalLatency}ms`);

		const metadata: CascadeMetadata = {
			flow: 'escalated_to_verifier',
			cost,
			quality: qualityResult,
			performance: {
				latencyMs: totalLatency,
				drafterLatencyMs: drafterLatency,
				verifierLatencyMs: verifierLatency,
			},
			requestCount: stats.totalRequests,
			acceptanceRate: stats.acceptanceRate,
		};

		return {
			response: verifierResult.generations[0].text,
			metadata,
		};
}

async function executeDirectVerifier(
	this: IExecuteFunctions,
		verifierModel: BaseChatModel,
		messages: BaseMessage[],
		config: NodeConfig,
		costTracker: CostTracker,
		complexityAnalysis: ComplexityAnalysis
	): Promise<{ response: string; metadata: CascadeMetadata }> {

		log.call(this, config, 'basic', `⚡ Direct routing to verifier (${complexityAnalysis.level} complexity)`);

		const verifierStartTime = Date.now();
		const verifierResponse = await verifierModel.invoke(messages);
		const verifierLatency = Date.now() - verifierStartTime;

		const verifierResult: ChatResult = {
			generations: [{
				text: verifierResponse.content.toString(),
				message: verifierResponse,
			}],
			llmOutput: (verifierResponse as any).response_metadata,
		};

		const cost = costTracker.calculateCost(
			{ modelName: 'skipped-drafter' },
			verifierModel,
			messages,
			undefined,
			verifierResult,
			'escalated_to_verifier'
		);

		checkBudgetLimit.call(this, cost.totalCost, config);

		const stats = costTracker.getStatistics();

		log.call(this, config, 'basic', `✅ Direct verifier completed - Cost: $${cost.totalCost.toFixed(6)}, Latency: ${verifierLatency}ms`);

		const metadata: CascadeMetadata = {
			flow: 'direct_verifier',
			cost,
			quality: {
				confidence: 1.0,
				qualityScore: 1.0,
				validationMethod: 'heuristic',
				passed: true,
				reason: `Direct routing based on ${complexityAnalysis.level} complexity`,
			},
			performance: {
				latencyMs: verifierLatency,
				verifierLatencyMs: verifierLatency,
			},
			requestCount: stats.totalRequests,
			acceptanceRate: stats.acceptanceRate,
		};

		return {
			response: verifierResult.generations[0].text,
			metadata,
		};
}

async function executeVerifierFallback(
	this: IExecuteFunctions,
		verifierModel: BaseChatModel,
		messages: BaseMessage[],
		config: NodeConfig,
		costTracker: CostTracker,
		errorMessage: string
	): Promise<{ response: string; metadata: CascadeMetadata }> {

		log.call(this, config, 'basic', `🔄 Using verifier as fallback...`);

		const verifierStartTime = Date.now();
		const verifierResponse = await verifierModel.invoke(messages);
		const verifierLatency = Date.now() - verifierStartTime;

		const verifierResult: ChatResult = {
			generations: [{
				text: verifierResponse.content.toString(),
				message: verifierResponse,
			}],
			llmOutput: (verifierResponse as any).response_metadata,
		};

		const cost = costTracker.calculateCost(
			{ modelName: 'drafter-failed' },
			verifierModel,
			messages,
			undefined,
			verifierResult,
			'error_fallback'
		);

		checkBudgetLimit.call(this, cost.totalCost, config);

		const stats = costTracker.getStatistics();

		log.call(this, config, 'basic', `✅ Verifier fallback completed - Cost: $${cost.totalCost.toFixed(6)}`);

		const metadata: CascadeMetadata = {
			flow: 'error_fallback',
			cost,
			quality: {
				confidence: 1.0,
				qualityScore: 1.0,
				validationMethod: 'heuristic',
				passed: true,
				reason: 'Verifier fallback due to drafter error',
			},
			performance: {
				latencyMs: verifierLatency,
				verifierLatencyMs: verifierLatency,
			},
			requestCount: stats.totalRequests,
			acceptanceRate: stats.acceptanceRate,
		};

		return {
			response: verifierResult.generations[0].text,
			metadata,
		};
}

async function validateQuality(
		responseText: string,
		messages: BaseMessage[],
		config: NodeConfig
	): Promise<QualityMetrics> {

		if (QualityValidator && CASCADE_QUALITY_CONFIG) {
			try {
				const qualityValidator = new QualityValidator({
					...CASCADE_QUALITY_CONFIG,
					minConfidence: config.qualityThreshold,
				});

				const queryText = messages.map(m => m.content.toString()).join(' ');
				const validationResult = await qualityValidator.validate(responseText, queryText);

				return {
					confidence: validationResult.confidence,
					qualityScore: validationResult.score || validationResult.confidence,
					validationMethod: validationResult.method || 'heuristic',
					alignmentScore: validationResult.details?.alignmentScore,
					passed: validationResult.passed,
					reason: validationResult.reason,
				};
			} catch (error) {
				console.warn('Quality validator error, using simple check:', error);
			}
		}

		return simpleQualityCheck(responseText, config.qualityThreshold);
}

function simpleQualityCheck(responseText: string, threshold: number): QualityMetrics {
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
		const hasUncertainty = uncertaintyMarkers.some(marker =>
			responseText.toLowerCase().includes(marker)
		);

		if (hasUncertainty) {
			confidence -= 0.20;
		}

		const passed = confidence >= threshold;

		return {
			confidence,
			qualityScore: confidence,
			validationMethod: 'heuristic',
			passed,
			reason: passed
				? `Simple check passed (confidence: ${confidence.toFixed(2)} >= ${threshold})`
				: `Simple check failed (confidence: ${confidence.toFixed(2)} < ${threshold})`,
		};
}

function checkBudgetLimit(this: IExecuteFunctions, cost: number, config: NodeConfig) {
		if (config.costBudgetLimit > 0 && cost > config.costBudgetLimit) {
			throw new NodeOperationError(
				this.getNode(),
				`Cost budget exceeded: $${cost.toFixed(6)} > $${config.costBudgetLimit.toFixed(6)}`
			);
		}
}

function log(this: IExecuteFunctions, config: NodeConfig, level: 'basic' | 'detailed' | 'debug', message: string) {
		const levels = { none: 0, basic: 1, detailed: 2, debug: 3 };
		const configLevel = levels[config.loggingLevel];
		const messageLevel = levels[level];

		if (configLevel >= messageLevel) {
			console.log(message);
		}
}
