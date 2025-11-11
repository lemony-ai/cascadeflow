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
import { DomainRouter, DomainModels } from './DomainRouter';
import { DomainDetectionResult } from './DomainDetector';
import { ResponseCache } from './ResponseCache';
import { SessionAnalytics } from './SessionAnalytics';
import { TokenCounter } from './TokenCounter';
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
	private static responseCache: ResponseCache | null = null;
	private static sessionAnalytics: SessionAnalytics | null = null;

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
			{
				displayName: 'Domain: Code',
				type: 'ai_languageModel' as any,
				required: false,
				maxConnections: 1,
			},
			{
				displayName: 'Domain: Math',
				type: 'ai_languageModel' as any,
				required: false,
				maxConnections: 1,
			},
			{
				displayName: 'Domain: Data',
				type: 'ai_languageModel' as any,
				required: false,
				maxConnections: 1,
			},
			{
				displayName: 'Domain: Medical',
				type: 'ai_languageModel' as any,
				required: false,
				maxConnections: 1,
			},
			{
				displayName: 'Domain: Legal',
				type: 'ai_languageModel' as any,
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
					{
						name: 'Domain-Aware',
						value: 'domain_aware',
						description: 'Route based on domain detection',
					},
				],
				default: 'always_cascade',
				description: 'How to route queries to models',
			},
			{
				displayName: 'Enable Domain Routing',
				name: 'enableDomainRouting',
				type: 'boolean',
				default: false,
				description: 'Whether to enable domain-specific model routing',
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
				displayName: 'Enable Response Caching',
				name: 'enableResponseCaching',
				type: 'boolean',
				default: false,
				description: 'Cache responses to reduce costs for repeated queries',
			},
			{
				displayName: 'Cache TTL (Minutes)',
				name: 'cacheTTLMinutes',
				type: 'number',
				default: 60,
				displayOptions: {
					show: {
						enableResponseCaching: [true],
					},
				},
				description: 'How long to cache responses before they expire',
			},
			{
				displayName: 'Cache Max Entries',
				name: 'cacheMaxEntries',
				type: 'number',
				default: 100,
				displayOptions: {
					show: {
						enableResponseCaching: [true],
					},
				},
				description: 'Maximum number of cached responses to store',
			},
			{
				displayName: 'Enable Session Analytics',
				name: 'enableSessionAnalytics',
				type: 'boolean',
				default: false,
				description: 'Track performance trends and provide optimization recommendations',
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
			enableDomainRouting: this.getNodeParameter('enableDomainRouting', 0, false) as boolean,
			domainDetectionMethod: 'rule_based',
			enableTools: this.getNodeParameter('enableTools', 0, false) as boolean,
			toolExecutionStrategy: 'always_cascade',
			enableMemory: this.getNodeParameter('enableMemory', 0, false) as boolean,
			enableCostTracking: this.getNodeParameter('enableCostTracking', 0, false) as boolean,
			costBudgetLimit: this.getNodeParameter('costBudgetLimit', 0, 0) as number,
			enableReasoningModels: true,
			reasoningEffort: 'medium',
			enableAdaptiveThreshold: false,
			enableResponseCaching: this.getNodeParameter('enableResponseCaching', 0, false) as boolean,
			cacheTTLMinutes: this.getNodeParameter('cacheTTLMinutes', 0, 60) as number,
			cacheMaxEntries: this.getNodeParameter('cacheMaxEntries', 0, 100) as number,
			enableSessionAnalytics: this.getNodeParameter('enableSessionAnalytics', 0, false) as boolean,
			loggingLevel: this.getNodeParameter('loggingLevel', 0, 'detailed') as any,
		};

		if (config.enableResponseCaching && !CascadeFlowAgentOptimizer.responseCache) {
			CascadeFlowAgentOptimizer.responseCache = new ResponseCache({
				enabled: true,
				maxEntries: config.cacheMaxEntries,
				ttlMs: config.cacheTTLMinutes * 60 * 1000,
				similarityThreshold: 0.85,
			});
		}

		if (config.enableSessionAnalytics && !CascadeFlowAgentOptimizer.sessionAnalytics) {
			CascadeFlowAgentOptimizer.sessionAnalytics = new SessionAnalytics();
		}

		const responseCache = CascadeFlowAgentOptimizer.responseCache;
		const sessionAnalytics = CascadeFlowAgentOptimizer.sessionAnalytics;

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

		const domainModels: DomainModels = {};
		if (config.enableDomainRouting) {
			try {
				const codeModel = await this.getInputConnectionData('ai_languageModel' as any, 4);
				if (codeModel) domainModels.code = codeModel as BaseChatModel;

				const mathModel = await this.getInputConnectionData('ai_languageModel' as any, 5);
				if (mathModel) domainModels.math = mathModel as BaseChatModel;

				const dataModel = await this.getInputConnectionData('ai_languageModel' as any, 6);
				if (dataModel) domainModels.data = dataModel as BaseChatModel;

				const medicalModel = await this.getInputConnectionData('ai_languageModel' as any, 7);
				if (medicalModel) domainModels.medical = medicalModel as BaseChatModel;

				const legalModel = await this.getInputConnectionData('ai_languageModel' as any, 8);
				if (legalModel) domainModels.legal = legalModel as BaseChatModel;
			} catch (error) {
				console.warn('Failed to load domain models:', error);
			}
		}

		const domainRouter = new DomainRouter(domainModels);

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

				if (config.enableResponseCaching && responseCache) {
					const cached = responseCache.get(query);
					if (cached) {
						log.call(this, config, 'basic', `💾 CACHE HIT - Returning cached response`);

						returnData.push({
							json: {
								query,
								response: cached.response,
								metadata: { ...cached.metadata, fromCache: true } as any,
							},
							pairedItem: { item: i },
						});

						if (config.enableCostTracking) {
							const cacheStats = responseCache.getStats();
							const costOutput = {
								timestamp: new Date().toISOString(),
								requestId: `req_${Date.now()}_${i}`,
								query,
								response: cached.response,
								cost: { ...cached.metadata.cost, fromCache: true } as any,
								quality: cached.metadata.quality as any,
								performance: cached.metadata.performance as any,
								metadata: {
									flow: 'cached',
									modelUsed: 'cache',
									cacheHits: cached.hits,
									cacheStats: cacheStats as any,
								},
							};
							costTrackingData.push({
								json: costOutput as any,
								pairedItem: { item: i },
							});
						}

						continue;
					}

					const similar = responseCache.findSimilar(query);
					if (similar && similar.query !== query) {
						log.call(this, config, 'detailed', `💡 Found similar cached query (${(0.85 * 100).toFixed(0)}% match)`);
					}
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

				let domainDetection: DomainDetectionResult | undefined;
				if (config.enableDomainRouting || config.routingStrategy === 'domain_aware') {
					const routing = domainRouter.route(query);
					domainDetection = routing.detection;
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
					memoryManager,
					domainRouter,
					domainDetection
				);

				if (config.enableMemory) {
					await memoryManager.addUserMessage(query);
					await memoryManager.addAIMessage(result.response);
				}

				if (config.enableResponseCaching && responseCache) {
					responseCache.set(query, result.response, result.metadata);
					log.call(this, config, 'debug', `💾 Response cached for future queries`);
				}

				if (config.enableSessionAnalytics && sessionAnalytics) {
					sessionAnalytics.addRequest(
						result.metadata.flow,
						result.metadata.cost,
						result.metadata.quality,
						result.metadata.performance,
						domainDetection?.domain,
						complexityAnalysis?.level
					);
				}

				returnData.push({
					json: {
						query,
						response: result.response,
						metadata: result.metadata as any,
						...(complexityAnalysis && { complexity: complexityAnalysis }),
						...(domainDetection && { domain: domainDetection }),
					},
					pairedItem: { item: i },
				});

				if (config.enableCostTracking) {
					const costOutput: any = {
						timestamp: new Date().toISOString(),
						requestId: `req_${Date.now()}_${i}`,
						query,
						response: result.response,
						cost: result.metadata.cost as any,
						quality: result.metadata.quality as any,
						performance: result.metadata.performance as any,
						...(complexityAnalysis && { complexity: complexityAnalysis }),
						...(domainDetection && { domain: domainDetection }),
						metadata: {
							flow: result.metadata.flow,
							modelUsed: result.metadata.cost.modelUsed,
							acceptanceRate: result.metadata.acceptanceRate,
							totalRequests: result.metadata.requestCount,
						},
					};

					if (config.enableResponseCaching && responseCache) {
						const cacheStats = responseCache.getStats();
						costOutput.cacheStats = {
							hitRate: cacheStats.hitRate,
							totalHits: cacheStats.totalHits,
							totalMisses: cacheStats.totalMisses,
							entriesCount: cacheStats.totalEntries,
							costSaved: cacheStats.costSaved,
						};
					}

					if (config.enableSessionAnalytics && sessionAnalytics) {
						const sessionStats = sessionAnalytics.getStats();
						const trends = sessionAnalytics.analyzeTrends();
						costOutput.sessionStats = {
							totalRequests: sessionStats.totalRequests,
							totalCost: sessionStats.totalCost,
							totalSavings: sessionStats.totalSavings,
							averageQuality: sessionStats.averageQuality,
							averageLatency: sessionStats.averageLatency,
							acceptanceRate: sessionStats.acceptanceRate,
							trends: {
								cost: trends.costTrend,
								quality: trends.qualityTrend,
								acceptance: trends.acceptanceRateTrend,
								recommendations: trends.recommendations,
							},
						};
					}

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
		memoryManager?: MemoryManager,
		domainRouter?: DomainRouter,
		domainDetection?: DomainDetectionResult
	): Promise<{ response: string; metadata: CascadeMetadata }> {

		if (domainRouter && domainDetection && (config.enableDomainRouting || config.routingStrategy === 'domain_aware')) {
			const queryText = messages.map(m => m.content.toString()).join(' ');
			const routing = domainRouter.route(queryText);

			log.call(this, config, 'detailed', `🎯 Domain Detection: ${routing.domain} (${(routing.detection.confidence * 100).toFixed(0)}% confidence)`);
			log.call(this, config, 'detailed', `   ${routing.reasoning}`);

			if (routing.useDomainSpecialist && routing.domainModel) {
				log.call(this, config, 'detailed', `⚡ Routing to ${routing.domain} specialist model`);
				return executeDomainSpecialist.call(
					this,
					routing.domainModel,
					verifierModel,
					messages,
					config,
					costTracker,
					routing.domain,
					routing.detection
				);
			}
		}

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

async function executeDomainSpecialist(
	this: IExecuteFunctions,
		domainModel: BaseChatModel,
		verifierModel: BaseChatModel,
		messages: BaseMessage[],
		config: NodeConfig,
		costTracker: CostTracker,
		domain: string,
		detection: DomainDetectionResult
	): Promise<{ response: string; metadata: CascadeMetadata }> {

		log.call(this, config, 'basic', `🎯 Using ${domain} domain specialist model`);
		log.call(this, config, 'detailed', `   Confidence: ${(detection.confidence * 100).toFixed(0)}%, Keywords: ${detection.keywords.slice(0, 3).join(', ')}`);

		const domainStartTime = Date.now();
		const domainResponse = await domainModel.invoke(messages);
		const domainLatency = Date.now() - domainStartTime;

		const domainResult: ChatResult = {
			generations: [{
				text: domainResponse.content.toString(),
				message: domainResponse,
			}],
			llmOutput: (domainResponse as any).response_metadata,
		};

		const responseText = domainResult.generations[0].text;

		const qualityResult = await validateQuality(responseText, messages, config);

		log.call(this, config, 'detailed', `   📊 Quality: confidence=${qualityResult.confidence.toFixed(2)}, score=${qualityResult.qualityScore.toFixed(2)}`);

		if (qualityResult.passed) {
			const cost = costTracker.calculateCost(
				domainModel,
				verifierModel,
				messages,
				domainResult,
				undefined,
				'drafter_accepted'
			);

			checkBudgetLimit.call(this, cost.totalCost, config);

			const stats = costTracker.getStatistics();

			log.call(this, config, 'basic', `✅ DOMAIN SPECIALIST ACCEPTED - Cost: $${cost.totalCost.toFixed(6)}`);

			const metadata: CascadeMetadata = {
				flow: 'domain_specialist',
				cost: {
					...cost,
					modelUsed: 'domain_specialist',
				},
				quality: qualityResult,
				performance: {
					latencyMs: domainLatency,
					domainSpecialistLatencyMs: domainLatency,
				},
				requestCount: stats.totalRequests,
				acceptanceRate: stats.acceptanceRate,
				domainInfo: {
					domain,
					confidence: detection.confidence,
					keywords: detection.keywords,
					reasoning: detection.reasoning,
				},
			};

			return {
				response: responseText,
				metadata,
			};
		}

		log.call(this, config, 'detailed', `⚠️  Domain specialist quality below threshold. Escalating to verifier...`);
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
			domainModel,
			verifierModel,
			messages,
			domainResult,
			verifierResult,
			'escalated_to_verifier'
		);

		checkBudgetLimit.call(this, cost.totalCost, config);

		const stats = costTracker.getStatistics();
		const totalLatency = domainLatency + verifierLatency;

		log.call(this, config, 'basic', `⚠️  ESCALATED TO VERIFIER - Total: $${cost.totalCost.toFixed(6)}, Latency: ${totalLatency}ms`);

		const metadata: CascadeMetadata = {
			flow: 'domain_specialist_escalated',
			cost: {
				...cost,
				modelUsed: 'verifier',
			},
			quality: qualityResult,
			performance: {
				latencyMs: totalLatency,
				domainSpecialistLatencyMs: domainLatency,
				verifierLatencyMs: verifierLatency,
			},
			requestCount: stats.totalRequests,
			acceptanceRate: stats.acceptanceRate,
			domainInfo: {
				domain,
				confidence: detection.confidence,
				keywords: detection.keywords,
				reasoning: detection.reasoning,
			},
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
