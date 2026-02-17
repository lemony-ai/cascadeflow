import type {
  INodeType,
  INodeTypeDescription,
  ISupplyDataFunctions,
  SupplyData,
} from 'n8n-workflow';

import { NodeOperationError } from 'n8n-workflow';

import type { BaseMessage } from '@langchain/core/messages';
import { AIMessage, HumanMessage, SystemMessage, ToolMessage } from '@langchain/core/messages';
import type { BaseChatModel } from '@langchain/core/language_models/chat_models';

import { CascadeChatModel } from '../LmChatCascadeFlow/LmChatCascadeFlow.node';
import {
  DEFAULT_COMPLEXITY_THRESHOLDS,
  DOMAIN_DISPLAY_NAMES,
  DOMAIN_UI_CONFIGS,
  DOMAINS,
  DOMAIN_DESCRIPTIONS,
  type DomainType,
  getEnabledDomains,
} from '../LmChatCascadeFlow/config';

// Tool cascade validator - optional import
let ToolCascadeValidator: any;
try {
  const cascadeCore = require('@cascadeflow/core');
  ToolCascadeValidator = cascadeCore.ToolCascadeValidator;
} catch (e) {
  // @cascadeflow/core not available
}

type ToolRoutingMode = 'cascade' | 'verifier';

export interface ToolRoutingRule {
  toolName: string;
  routing: ToolRoutingMode;
}

interface ToolCallInfo {
  id: string;
  name: string;
  args: Record<string, any>;
}

export interface ToolLike {
  name?: string;
  description?: string;
  invoke?: (args: any) => Promise<any>;
  call?: (args: any) => Promise<any>;
  run?: (args: any) => Promise<any>;
}

export class CascadeFlowAgentExecutor {
  private toolMap: Map<string, ToolLike>;
  private routingRules: Map<string, ToolRoutingMode>;
  private enableToolCascadeValidation: boolean;
  private toolCascadeValidator: any;

  constructor(
    private cascadeModel: CascadeChatModel,
    tools: ToolLike[],
    routingRules: ToolRoutingRule[],
    private maxIterations: number,
    enableToolCascadeValidation: boolean = false,
  ) {
    this.toolMap = new Map(
      tools.filter((tool) => tool?.name).map((tool) => [tool.name as string, tool])
    );
    this.routingRules = new Map(routingRules.map((rule) => [rule.toolName, rule.routing]));

    this.enableToolCascadeValidation = enableToolCascadeValidation;
    if (enableToolCascadeValidation && ToolCascadeValidator) {
      try {
        this.toolCascadeValidator = new ToolCascadeValidator();
      } catch {
        this.toolCascadeValidator = null;
      }
    } else {
      this.toolCascadeValidator = null;
    }
  }

  private normalizeMessages(input: any): BaseMessage[] {
    const isBaseMessage = (value: any): value is BaseMessage => {
      return (
        value &&
        typeof value === 'object' &&
        typeof value._getType === 'function' &&
        'content' in value
      );
    };

    const coerceMessage = (value: any): BaseMessage => {
      if (isBaseMessage(value)) {
        return value;
      }

      if (typeof value === 'string') {
        return new HumanMessage(value);
      }

      if (!value || typeof value !== 'object') {
        return new HumanMessage(JSON.stringify(value ?? null));
      }

      const role = (value.role ?? value.type ?? '').toString().toLowerCase();
      const content = value.content ?? value.text ?? '';

      if (role === 'system') {
        return new SystemMessage(content);
      }
      if (role === 'assistant' || role === 'ai') {
        return new AIMessage(content);
      }
      if (role === 'tool') {
        const toolCallId =
          value.tool_call_id ??
          value.toolCallId ??
          value.tool_callId ??
          value.id ??
          'tool';
        return new ToolMessage({
          content: typeof content === 'string' ? content : JSON.stringify(content),
          tool_call_id: String(toolCallId),
        });
      }

      // Default: treat as user/human.
      return new HumanMessage(content);
    };

    const normalizeList = (values: any[]): BaseMessage[] => values.map(coerceMessage);

    if (Array.isArray(input)) {
      return normalizeList(input);
    }

    if (typeof input === 'string') {
      return [new HumanMessage(input)];
    }

    if (input?.messages && Array.isArray(input.messages)) {
      return normalizeList(input.messages);
    }

    if (input?.chatHistory && Array.isArray(input.chatHistory)) {
      const history = normalizeList(input.chatHistory);
      if (typeof input.input === 'string') {
        return [...history, new HumanMessage(input.input)];
      }
      return history;
    }

    if (typeof input?.input === 'string') {
      return [new HumanMessage(input.input)];
    }

    return [new HumanMessage(JSON.stringify(input ?? null))];
  }

  private extractToolCalls(message: BaseMessage): ToolCallInfo[] {
    const additionalKwargs = (message as any).additional_kwargs || {};
    const responseMetadata = (message as any).response_metadata || {};
    const toolCalls = additionalKwargs.tool_calls || responseMetadata.tool_calls;

    if (Array.isArray(toolCalls)) {
      return toolCalls
        .map((toolCall: any) => {
          const args = toolCall?.function?.arguments ?? toolCall?.arguments ?? '{}';
          let parsedArgs: Record<string, any> = {};
          try {
            parsedArgs = typeof args === 'string' ? JSON.parse(args) : args;
          } catch {
            parsedArgs = { raw: args };
          }
          return {
            id: toolCall?.id ?? toolCall?.function?.name ?? `tool_${Date.now()}`,
            name: toolCall?.function?.name ?? toolCall?.name,
            args: parsedArgs,
          } as ToolCallInfo;
        })
        .filter((call: ToolCallInfo) => Boolean(call.name));
    }

    if (additionalKwargs.function_call) {
      const functionCall = additionalKwargs.function_call;
      let parsedArgs: Record<string, any> = {};
      try {
        parsedArgs = functionCall.arguments ? JSON.parse(functionCall.arguments) : {};
      } catch {
        parsedArgs = { raw: functionCall.arguments };
      }
      return [
        {
          id: functionCall.name ?? `tool_${Date.now()}`,
          name: functionCall.name,
          args: parsedArgs,
        },
      ];
    }

    return [];
  }

  private async executeTool(call: ToolCallInfo): Promise<string> {
    const tool = this.toolMap.get(call.name);
    if (!tool) {
      return `Tool '${call.name}' not found`;
    }

    if (tool.invoke) {
      return JSON.stringify(await tool.invoke(call.args));
    }

    if (tool.call) {
      return JSON.stringify(await tool.call(call.args));
    }

    if (tool.run) {
      return JSON.stringify(await tool.run(call.args));
    }

    return `Tool '${call.name}' has no callable method`;
  }

  private resolveRouting(toolCalls: ToolCallInfo[]): ToolRoutingMode {
    for (const call of toolCalls) {
      const routing = this.routingRules.get(call.name);
      if (routing === 'verifier') {
        return 'verifier';
      }
    }
    return 'cascade';
  }

  /**
   * Validate tool calls using ToolCascadeValidator.
   * Returns { valid, score, errors } or null if unavailable.
   */
  private validateToolCalls(toolCalls: ToolCallInfo[]): { valid: boolean; score: number; errors: string[] } | null {
    if (!this.enableToolCascadeValidation || !this.toolCascadeValidator) {
      return null;
    }

    try {
      const normalized = toolCalls.map((tc) => ({
        id: tc.id,
        name: tc.name,
        arguments: tc.args,
      }));
      const result = this.toolCascadeValidator.validate(normalized, []);
      return {
        valid: result.valid,
        score: result.score,
        errors: result.errors || [],
      };
    } catch {
      return null;
    }
  }

  private buildTraceEntry(message: BaseMessage, toolCalls: ToolCallInfo[] = []) {
    const responseMetadata = (message as any).response_metadata || {};
    const cf = responseMetadata.cf || {};
    const cascadeflow = responseMetadata.cascadeflow || {};

    return {
      model_used: cf.model_used ?? cascadeflow.model_used ?? 'unknown',
      domain: cf.domain ?? cascadeflow.domain ?? null,
      confidence: cf.confidence ?? cascadeflow.confidence ?? null,
      complexity: cf.complexity ?? cascadeflow.complexity ?? null,
      costs: cf.costs ?? null,
      savings: cf.savings ?? null,
      flow: cascadeflow.flow ?? null,
      reason: cascadeflow.reason ?? null,
      tool_calls: toolCalls.map((call) => call.name),
    };
  }

  async invoke(input: any, options?: any): Promise<any> {
    const messages = this.normalizeMessages(input);
    const trace: any[] = [];
    let currentMessages = [...messages];
    let finalMessage: BaseMessage | null = null;
    let iterations = 0;

    while (iterations < this.maxIterations) {
      const message = await this.cascadeModel.invoke(currentMessages, options);
      const toolCalls = this.extractToolCalls(message);
      trace.push(this.buildTraceEntry(message, toolCalls));

      if (toolCalls.length === 0) {
        finalMessage = message;
        break;
      }

      // Validate tool calls if enabled
      const validation = this.validateToolCalls(toolCalls);
      if (validation && !validation.valid) {
        console.log(`🔧 Agent tool call validation failed (score: ${validation.score.toFixed(2)}), escalating to verifier`);
        const verifierMessage = await this.cascadeModel.invokeVerifierDirect(currentMessages, options);
        const verifierToolCalls = this.extractToolCalls(verifierMessage);
        trace.push({
          ...this.buildTraceEntry(verifierMessage, verifierToolCalls),
          tool_validation_failed: true,
          tool_validation_score: validation.score,
          tool_validation_errors: validation.errors,
        });

        if (verifierToolCalls.length === 0) {
          finalMessage = verifierMessage;
          break;
        }

        // Use verifier's tool calls instead
        currentMessages = [...currentMessages, verifierMessage];
        for (const call of verifierToolCalls) {
          const toolResult = await this.executeTool(call);
          currentMessages.push(
            new ToolMessage({
              content: toolResult,
              tool_call_id: call.id,
            })
          );
        }
        iterations += 1;
        continue;
      }

      const routing = this.resolveRouting(toolCalls);
      currentMessages = [...currentMessages, message];

      for (const call of toolCalls) {
        const toolResult = await this.executeTool(call);
        currentMessages.push(
          new ToolMessage({
            content: toolResult,
            tool_call_id: call.id,
          })
        );
      }

      if (routing === 'verifier') {
        const verifierMessage = await this.cascadeModel.invokeVerifierDirect(currentMessages, options);
        trace.push(this.buildTraceEntry(verifierMessage));
        finalMessage = verifierMessage;
        break;
      }

      iterations += 1;
    }

    if (!finalMessage) {
      finalMessage = new AIMessage('Agent did not produce a final response.');
    }

    if (!(finalMessage as any).response_metadata) {
      (finalMessage as any).response_metadata = {};
    }

    (finalMessage as any).response_metadata.cf = {
      ...((finalMessage as any).response_metadata.cf || {}),
      trace,
    };

    return {
      output: finalMessage.content.toString(),
      message: finalMessage,
      trace,
    };
  }

  async *stream(input: any, options?: any): AsyncGenerator<any> {
    const messages = this.normalizeMessages(input);

    // For tool-driven execution we currently return a single final response.
    if (this.toolMap.size > 0) {
      yield await this.invoke(messages, options);
      return;
    }

    const stream = await this.cascadeModel.stream(messages, options);
    for await (const chunk of stream) {
      yield chunk;
    }
  }
}

// =============================================================================
// Generate domain toggle properties for n8n UI (reused from LmChatCascadeFlow)
// =============================================================================
function generateDomainProperties(): any[] {
  const domainOptions = Object.entries(DOMAINS).map(([_key, value]) => ({
    name: DOMAIN_DISPLAY_NAMES[value],
    value: value,
    description: DOMAIN_DESCRIPTIONS[value],
  }));

  const domainToggleProperties: any[] = [];
  for (const { domain, toggleName } of DOMAIN_UI_CONFIGS) {
    const displayName = DOMAIN_DISPLAY_NAMES[domain];
    domainToggleProperties.push({
      displayName: `Enable ${displayName} Domain`,
      name: toggleName,
      type: 'boolean',
      default: false,
      displayOptions: { show: { enableDomainRouting: [true] } },
      description: `Whether to enable ${DOMAIN_DESCRIPTIONS[domain]}. When enabled, adds a "${displayName}" input port.`,
    });
  }

  return [
    {
      displayName: 'Enable Domain Routing',
      name: 'enableDomainRouting',
      type: 'boolean',
      default: false,
      description: 'Whether to enable intelligent routing based on detected query domain (math, code, legal, etc.)',
    },
    {
      displayName: 'Enable Domain Verifiers',
      name: 'enableDomainVerifiers',
      type: 'boolean',
      default: false,
      displayOptions: { show: { enableDomainRouting: [true] } },
      description: 'Whether to add a domain-specific verifier port for each enabled domain. Connect a model to override the global verifier for that domain.',
    },
    {
      displayName: 'Enable the domains you want to route to. Each enabled domain adds a model input port on the node.',
      name: 'domainsNotice',
      type: 'notice',
      default: '',
      displayOptions: { show: { enableDomainRouting: [true] } },
    },
    ...domainToggleProperties,
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
              default: 0.4,
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

export class CascadeFlowAgent implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'CascadeFlow Agent',
    name: 'cascadeFlowAgent',
    icon: 'file:cascadeflow.svg',
    group: ['transform'],
    version: 2,
    description:
      'CascadeFlow AI Agent with drafter/verifier orchestration, tool routing, domain routing, and trace metadata.',
    defaults: {
      name: 'CascadeFlow Agent',
    },
    codex: {
      categories: ['AI'],
      subcategories: {
        AI: ['Agents'],
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
      const inputs = [
        { displayName: 'Verifier', type: 'ai_languageModel', maxConnections: 1, required: true },
        { displayName: 'Drafter', type: 'ai_languageModel', maxConnections: 1, required: true },
        { displayName: 'Tools', type: 'ai_tool', maxConnections: 99, required: false },
      ];

      if (params?.enableDomainRouting) {
        const dv = !!params?.enableDomainVerifiers;
        const domains = [
          { t: 'enableCodeDomain', l: 'Code' },
          { t: 'enableDataDomain', l: 'Data' },
          { t: 'enableStructuredDomain', l: 'Struct.' },
          { t: 'enableRagDomain', l: 'RAG' },
          { t: 'enableConversationDomain', l: 'Conv.' },
          { t: 'enableToolDomain', l: 'Tool' },
          { t: 'enableCreativeDomain', l: 'Creative' },
          { t: 'enableSummaryDomain', l: 'Summary' },
          { t: 'enableTranslationDomain', l: 'Transl.' },
          { t: 'enableMathDomain', l: 'Math' },
          { t: 'enableScienceDomain', l: 'Science' },
          { t: 'enableMedicalDomain', l: 'Medical' },
          { t: 'enableLegalDomain', l: 'Legal' },
          { t: 'enableFinancialDomain', l: 'Finance' },
          { t: 'enableMultimodalDomain', l: 'Multi.' },
          { t: 'enableGeneralDomain', l: 'General' },
        ];
        for (const d of domains) {
          if (params?.[d.t]) {
            inputs.push({ displayName: d.l, type: 'ai_languageModel', maxConnections: 1, required: false });
            if (dv) {
              inputs.push({ displayName: d.l + ' V.', type: 'ai_languageModel', maxConnections: 1, required: false });
            }
          }
        }
      }

      return inputs;
    })($parameter) }}`,
    // eslint-disable-next-line n8n-nodes-base/node-class-description-outputs-wrong
    outputs: ['ai_agent' as any],
    outputNames: ['Agent'],
    properties: [
      {
        displayName: 'Quality Threshold',
        name: 'qualityThreshold',
        type: 'number',
        default: 0.4,
        typeOptions: {
          minValue: 0,
          maxValue: 1,
          numberPrecision: 2,
        },
        description: 'Minimum quality score (0-1) to accept drafter response',
      },
      {
        displayName: 'Use Complexity Thresholds',
        name: 'useComplexityThresholds',
        type: 'boolean',
        default: true,
        description:
          'Whether to use per-complexity confidence thresholds (trivial → expert)',
      },
      {
        displayName: 'Trivial Threshold',
        name: 'trivialThreshold',
        type: 'number',
        default: 0.25,
        displayOptions: { show: { useComplexityThresholds: [true] } },
        typeOptions: {
          minValue: 0,
          maxValue: 1,
          numberPrecision: 2,
        },
        description: 'Minimum confidence for trivial queries',
      },
      {
        displayName: 'Simple Threshold',
        name: 'simpleThreshold',
        type: 'number',
        default: 0.4,
        displayOptions: { show: { useComplexityThresholds: [true] } },
        typeOptions: {
          minValue: 0,
          maxValue: 1,
          numberPrecision: 2,
        },
        description: 'Minimum confidence for simple queries',
      },
      {
        displayName: 'Moderate Threshold',
        name: 'moderateThreshold',
        type: 'number',
        default: 0.55,
        displayOptions: { show: { useComplexityThresholds: [true] } },
        typeOptions: {
          minValue: 0,
          maxValue: 1,
          numberPrecision: 2,
        },
        description: 'Minimum confidence for moderate queries',
      },
      {
        displayName: 'Hard Threshold',
        name: 'hardThreshold',
        type: 'number',
        default: 0.7,
        displayOptions: { show: { useComplexityThresholds: [true] } },
        typeOptions: {
          minValue: 0,
          maxValue: 1,
          numberPrecision: 2,
        },
        description: 'Minimum confidence for hard queries',
      },
      {
        displayName: 'Expert Threshold',
        name: 'expertThreshold',
        type: 'number',
        default: 0.8,
        displayOptions: { show: { useComplexityThresholds: [true] } },
        typeOptions: {
          minValue: 0,
          maxValue: 1,
          numberPrecision: 2,
        },
        description: 'Minimum confidence for expert queries',
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
        description: 'Whether to route complex queries directly to the verifier',
      },
      {
        displayName: 'Enable Tool Call Validation',
        name: 'enableToolCascadeValidation',
        type: 'boolean',
        default: true,
        description: 'Whether to validate drafter tool calls (JSON syntax, schema, safety) before executing them. When validation fails, tool calls are re-generated by the verifier.',
      },
      {
        displayName: 'Max Tool Iterations',
        name: 'maxIterations',
        type: 'number',
        default: 3,
        typeOptions: {
          minValue: 1,
          maxValue: 10,
        },
        description: 'Maximum number of tool-call iterations before returning',
      },
      {
        displayName: 'Tool Routing Rules',
        name: 'toolRoutingRules',
        type: 'fixedCollection',
        typeOptions: {
          multipleValues: true,
        },
        default: {},
        options: [
          {
            name: 'rule',
            displayName: 'Routing Rule',
            values: [
              {
                displayName: 'Tool Name',
                name: 'toolName',
                type: 'string',
                default: '',
              },
              {
                displayName: 'Routing',
                name: 'routing',
                type: 'options',
                options: [
                  {
                    name: 'Cascade (Default)',
                    value: 'cascade',
                  },
                  {
                    name: 'Verifier',
                    value: 'verifier',
                  },
                ],
                default: 'cascade',
              },
            ],
          },
        ],
        description: 'Override routing for specific tools (e.g., force verifier after tool call)',
      },
      {
        displayName: 'Domain Routing',
        name: 'domainRoutingHeading',
        type: 'notice',
        default: '',
      },
      ...generateDomainProperties(),
    ],
  };

  async supplyData(this: ISupplyDataFunctions): Promise<SupplyData> {
    const qualityThreshold = this.getNodeParameter('qualityThreshold', 0, 0.4) as number;
    const useAlignmentScoring = this.getNodeParameter('useAlignmentScoring', 0, true) as boolean;
    const useComplexityRouting = this.getNodeParameter('useComplexityRouting', 0, true) as boolean;
    const useComplexityThresholds = this.getNodeParameter('useComplexityThresholds', 0, true) as boolean;
    const enableToolCascadeValidation = this.getNodeParameter('enableToolCascadeValidation', 0, false) as boolean;
    const maxIterations = this.getNodeParameter('maxIterations', 0, 3) as number;

    const confidenceThresholds = useComplexityThresholds
      ? {
          trivial: this.getNodeParameter('trivialThreshold', 0, DEFAULT_COMPLEXITY_THRESHOLDS.trivial) as number,
          simple: this.getNodeParameter('simpleThreshold', 0, DEFAULT_COMPLEXITY_THRESHOLDS.simple) as number,
          moderate: this.getNodeParameter('moderateThreshold', 0, DEFAULT_COMPLEXITY_THRESHOLDS.moderate) as number,
          hard: this.getNodeParameter('hardThreshold', 0, DEFAULT_COMPLEXITY_THRESHOLDS.hard) as number,
          expert: this.getNodeParameter('expertThreshold', 0, DEFAULT_COMPLEXITY_THRESHOLDS.expert) as number,
        }
      : undefined;

    const toolRoutingRaw = this.getNodeParameter('toolRoutingRules', 0, { rule: [] }) as any;
    const toolRoutingRules = (toolRoutingRaw?.rule ?? []) as ToolRoutingRule[];

    // Get domain routing parameters
    const enableDomainRouting = this.getNodeParameter('enableDomainRouting', 0, false) as boolean;

    const enabledDomains: DomainType[] = [];
    if (enableDomainRouting) {
      const toggleParams: Record<string, boolean> = {};
      for (const { toggleName } of DOMAIN_UI_CONFIGS) {
        toggleParams[toggleName] = this.getNodeParameter(toggleName, 0, false) as boolean;
      }
      enabledDomains.push(...getEnabledDomains(toggleParams));
    }

    // Get domain-specific settings
    const domainSettingsRaw = this.getNodeParameter('domainSettings', 0, { domainConfig: [] }) as any;
    interface DomainConfig {
      enabled: boolean;
      threshold: number;
      temperature: number;
    }
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

    // Resolve ALL connected language models in a single getInputConnectionData call.
    // n8n resolves ALL sub-nodes of the given connectionType (the 2nd param is a
    // data-item index, NOT a port selector). The returned array is in reversed slot
    // order due to internal unshift, so we reverse it back. This matches the
    // built-in AI Agent node pattern (getChatModel in ToolsAgent/common.ts).
    const allModelData = await this.getInputConnectionData('ai_languageModel' as any, 0);
    const allModels = Array.isArray(allModelData)
      ? ([...allModelData].reverse() as BaseChatModel[])
      : [allModelData as BaseChatModel];

    // Port order after reverse: 0=Verifier, 1=Drafter, 2+=domain models/verifiers
    const resolvedVerifier = allModels[0];
    if (!resolvedVerifier) {
      throw new NodeOperationError(
        this.getNode(),
        'Verifier model is required. Please connect your VERIFIER model to the Verifier port.'
      );
    }
    const verifierModelGetter = async () => resolvedVerifier;

    const resolvedDrafter = allModels[1];
    if (!resolvedDrafter) {
      throw new NodeOperationError(
        this.getNode(),
        'Drafter model is required. Please connect your DRAFTER model to the Drafter port.'
      );
    }
    const drafterModelGetter = async () => resolvedDrafter;

    // Tools use a separate connectionType so they have their own single call
    const toolsData = await this.getInputConnectionData('ai_tool' as any, 0).catch(() => [] as any);
    const tools = (Array.isArray(toolsData) ? toolsData : toolsData ? [toolsData] : []) as ToolLike[];

    // Domain models and domain verifiers occupy indices 2+ in slot definition order
    const domainModelGetters = new Map<DomainType, () => Promise<BaseChatModel | undefined>>();
    const domainVerifierGetters = new Map<DomainType, () => Promise<BaseChatModel | undefined>>();

    const enableDomainVerifiers = this.getNodeParameter('enableDomainVerifiers', 0, false) as boolean;
    let nextModelIndex = 2; // After Verifier (0) and Drafter (1)
    for (const { domain } of DOMAIN_UI_CONFIGS) {
      if (!enabledDomains.includes(domain)) continue;

      const model = allModels[nextModelIndex++] as BaseChatModel | undefined;
      domainModelGetters.set(domain, async () => model || undefined);

      if (enableDomainVerifiers) {
        const verifierModel = allModels[nextModelIndex++] as BaseChatModel | undefined;
        domainVerifierGetters.set(domain, async () => verifierModel || undefined);
      }
    }

    // Keep semantic validation off in n8n to avoid OOM / heavy model loads.
    const useSemanticValidation = false;

    const cascadeModel = new CascadeChatModel(
      drafterModelGetter,
      verifierModelGetter,
      qualityThreshold,
      useSemanticValidation,
      useAlignmentScoring,
      useComplexityRouting,
      useComplexityThresholds,
      enableDomainRouting,
      enabledDomains,
      domainModelGetters,
      domainConfigs,
      confidenceThresholds,
      false, // enableToolCallValidation handled by the agent executor
      domainVerifierGetters,
    );

    const agentExecutor = new CascadeFlowAgentExecutor(
      cascadeModel,
      tools,
      toolRoutingRules,
      maxIterations,
      enableToolCascadeValidation,
    );

    return {
      response: agentExecutor,
    };
  }
}
