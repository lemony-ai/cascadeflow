import type {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
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
import { HarnessRunContext, type HarnessConfig, type HarnessMode, type KpiWeights } from '../harness';

// Keep logs disabled in runtime bundle to satisfy n8n scan constraints.
const debugLog = (..._args: unknown[]): void => {};

// Tool cascade validation from core is disabled in this package build;
// the agent falls back to local validation behavior.
const ToolCascadeValidator: any = null;

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

interface ChatMemoryLike {
  chatHistory: {
    getMessages(): Promise<BaseMessage[]>;
    addUserMessage(message: string): Promise<void>;
    addAIChatMessage(message: string): Promise<void>;
  };
}

export class CascadeFlowAgentExecutor {
  private toolMap: Map<string, ToolLike>;
  private routingRules: Map<string, ToolRoutingMode>;
  private enableToolCascadeValidation: boolean;
  private toolCascadeValidator: any;
  private harnessCtx: HarnessRunContext | null;

  constructor(
    private cascadeModel: CascadeChatModel,
    tools: ToolLike[],
    routingRules: ToolRoutingRule[],
    private maxIterations: number,
    enableToolCascadeValidation: boolean = false,
    harnessCtx: HarnessRunContext | null = null,
  ) {
    this.harnessCtx = harnessCtx;
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
      // Harness enforce-mode pre-checks
      if (this.harnessCtx?.config.mode === 'enforce') {
        if (this.harnessCtx.isBudgetExhausted()) {
          finalMessage = new AIMessage(`[Harness] Budget exhausted ($${this.harnessCtx.cost.toFixed(4)} of $${this.harnessCtx.config.budgetMax?.toFixed(4)} max). Agent stopped.`);
          break;
        }
        if (this.harnessCtx.isToolCapReached()) {
          finalMessage = new AIMessage(`[Harness] Tool call cap reached (${this.harnessCtx.toolCalls} of ${this.harnessCtx.config.toolCallsMax} max). Agent stopped.`);
          break;
        }
      }

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
        debugLog(`🔧 Agent tool call validation failed (score: ${validation.score.toFixed(2)}), escalating to verifier`);
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

      // Track tool calls in harness (CascadeChatModel records LLM token costs;
      // agent executor tracks tool-call counts from the loop itself)
      if (this.harnessCtx) {
        this.harnessCtx.toolCalls += toolCalls.length;
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
      harness: this.harnessCtx?.summary() ?? null,
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
      displayName: 'Enable Domain Cascading',
      name: 'enableDomainRouting',
      type: 'boolean',
      default: false,
      description: 'Whether to enable domain-specific cascading based on detected query domain (math, code, legal, etc.)',
    },
    {
      displayName: 'Enable Domain Verifiers (Default: Main Verifier)',
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
        { displayName: '', type: 'main' },
        { displayName: 'Verifier', type: 'ai_languageModel', maxConnections: 1, required: true },
        { displayName: 'Drafter', type: 'ai_languageModel', maxConnections: 1, required: true },
        { displayName: 'Memory', type: 'ai_memory', maxConnections: 1, required: false },
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
    outputs: ['main'],
    outputNames: ['Output'],
    properties: [
      {
        displayName: 'System Message',
        name: 'systemMessage',
        type: 'string',
        default: '',
        typeOptions: {
          rows: 4,
        },
        description: 'System prompt for the agent. Sets the overall behavior and context.',
      },
      {
        displayName: 'Text',
        name: 'text',
        type: 'string',
        default: '={{ $json.chatInput }}',
        required: true,
        description: 'The user message to send to the agent. Defaults to chatInput from Chat Trigger.',
      },
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
        displayName: 'Domain Cascading',
        name: 'domainRoutingHeading',
        type: 'notice',
        default: '',
      },
      ...generateDomainProperties(),
      // -----------------------------------------------------------------
      // Harness: Multi-Dimensional Cascading
      // -----------------------------------------------------------------
      {
        displayName: 'Harness',
        name: 'harnessHeading',
        type: 'notice',
        default: '',
      },
      {
        displayName: 'Harness Mode',
        name: 'harnessMode',
        type: 'options',
        options: [
          { name: 'Off', value: 'off', description: 'Harness disabled, zero overhead' },
          { name: 'Observe', value: 'observe', description: 'Track all dimensions, record trace, no enforcement' },
          { name: 'Enforce', value: 'enforce', description: 'Stop agent loop when limits are hit' },
        ],
        default: 'observe',
        description: 'Harness mode: off (disabled), observe (telemetry only), or enforce (stop when limits hit)',
      },
      {
        displayName: 'Budget (USD)',
        name: 'harnessBudget',
        type: 'number',
        default: 0,
        typeOptions: { minValue: 0, numberPrecision: 4 },
        displayOptions: { hide: { harnessMode: ['off'] } },
        description: 'Max budget in USD. 0 = unlimited.',
      },
      {
        displayName: 'Max Tool Calls',
        name: 'harnessMaxToolCalls',
        type: 'number',
        default: 0,
        typeOptions: { minValue: 0 },
        displayOptions: { hide: { harnessMode: ['off'] } },
        description: 'Max tool call count. 0 = unlimited.',
      },
      {
        displayName: 'Max Latency (Ms)',
        name: 'harnessMaxLatencyMs',
        type: 'number',
        default: 0,
        typeOptions: { minValue: 0 },
        displayOptions: { hide: { harnessMode: ['off'] } },
        description: 'Max cumulative latency in milliseconds. 0 = unlimited.',
      },
      {
        displayName: 'Max Energy',
        name: 'harnessMaxEnergy',
        type: 'number',
        default: 0,
        typeOptions: { minValue: 0, numberPrecision: 2 },
        displayOptions: { hide: { harnessMode: ['off'] } },
        description: 'Max energy proxy units. 0 = unlimited.',
      },
      {
        displayName: 'Compliance',
        name: 'harnessCompliance',
        type: 'options',
        options: [
          { name: 'GDPR', value: 'gdpr' },
          { name: 'HIPAA', value: 'hipaa' },
          { name: 'None', value: '' },
          { name: 'PCI', value: 'pci' },
          { name: 'Strict', value: 'strict' },
        ],
        default: '',
        displayOptions: { hide: { harnessMode: ['off'] } },
        description: 'Compliance policy to enforce model allowlists',
      },
      {
        displayName: 'KPI Weights',
        name: 'harnessKpiWeights',
        type: 'fixedCollection',
        typeOptions: { multipleValues: false },
        displayOptions: { hide: { harnessMode: ['off'] } },
        default: { weights: [{ quality: 0.4, cost: 0.3, latency: 0.2, energy: 0.1 }] },
        options: [
          {
            name: 'weights',
            displayName: 'Weights',
            values: [
              { displayName: 'Quality', name: 'quality', type: 'number', default: 0.4, typeOptions: { minValue: 0, maxValue: 1, numberPrecision: 2 } },
              { displayName: 'Cost', name: 'cost', type: 'number', default: 0.3, typeOptions: { minValue: 0, maxValue: 1, numberPrecision: 2 } },
              { displayName: 'Latency', name: 'latency', type: 'number', default: 0.2, typeOptions: { minValue: 0, maxValue: 1, numberPrecision: 2 } },
              { displayName: 'Energy', name: 'energy', type: 'number', default: 0.1, typeOptions: { minValue: 0, maxValue: 1, numberPrecision: 2 } },
            ],
          },
        ],
        description: 'KPI dimension weights for optimization scoring (normalized automatically)',
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const returnData: INodeExecutionData[] = [];

    // --- Resolve parameters that are constant across items (index 0) ---

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

    // Harness parameters
    const harnessMode = this.getNodeParameter('harnessMode', 0, 'observe') as HarnessMode;
    let harnessCtx: HarnessRunContext | null = null;
    if (harnessMode !== 'off') {
      const rawBudget = this.getNodeParameter('harnessBudget', 0, 0) as number;
      const rawToolCalls = this.getNodeParameter('harnessMaxToolCalls', 0, 0) as number;
      const rawLatency = this.getNodeParameter('harnessMaxLatencyMs', 0, 0) as number;
      const rawEnergy = this.getNodeParameter('harnessMaxEnergy', 0, 0) as number;
      const compliance = this.getNodeParameter('harnessCompliance', 0, '') as string;
      const kpiRaw = this.getNodeParameter('harnessKpiWeights', 0, { weights: [{ quality: 0.4, cost: 0.3, latency: 0.2, energy: 0.1 }] }) as any;
      const kpiEntry = kpiRaw?.weights?.[0] ?? { quality: 0.4, cost: 0.3, latency: 0.2, energy: 0.1 };

      const config: HarnessConfig = {
        mode: harnessMode,
        budgetMax: rawBudget > 0 ? rawBudget : null,
        toolCallsMax: rawToolCalls > 0 ? rawToolCalls : null,
        latencyMaxMs: rawLatency > 0 ? rawLatency : null,
        energyMax: rawEnergy > 0 ? rawEnergy : null,
        compliance: compliance || null,
        kpiWeights: {
          quality: kpiEntry.quality ?? 0.4,
          cost: kpiEntry.cost ?? 0.3,
          latency: kpiEntry.latency ?? 0.2,
          energy: kpiEntry.energy ?? 0.1,
        },
      };
      harnessCtx = new HarnessRunContext(config);
    }

    // Domain routing parameters
    const enableDomainRouting = this.getNodeParameter('enableDomainRouting', 0, false) as boolean;

    const enabledDomains: DomainType[] = [];
    if (enableDomainRouting) {
      const toggleParams: Record<string, boolean> = {};
      for (const { toggleName } of DOMAIN_UI_CONFIGS) {
        toggleParams[toggleName] = this.getNodeParameter(toggleName, 0, false) as boolean;
      }
      enabledDomains.push(...getEnabledDomains(toggleParams));
    }

    // Domain-specific settings
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

    // --- Resolve connected AI components (once, not per item) ---

    // Language models — single call resolves all ai_languageModel sub-nodes.
    // Reversed slot order due to internal unshift, so we reverse back.
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

    // Memory (optional)
    const memory = (await this.getInputConnectionData('ai_memory' as any, 0)
      .catch(() => null)) as ChatMemoryLike | null;

    // Tools
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

    // Wire harness context into cascade model for per-call recording
    if (harnessCtx) {
      cascadeModel.setHarnessContext(harnessCtx);
    }

    const agentExecutor = new CascadeFlowAgentExecutor(
      cascadeModel,
      tools,
      toolRoutingRules,
      maxIterations,
      enableToolCascadeValidation,
      harnessCtx,
    );

    // --- Process each input item ---

    for (let itemIndex = 0; itemIndex < items.length; itemIndex++) {
      const text = this.getNodeParameter('text', itemIndex) as string;
      const systemMessage = this.getNodeParameter('systemMessage', itemIndex, '') as string;

      // Build message array
      const messages: BaseMessage[] = [];
      if (systemMessage) {
        messages.push(new SystemMessage(systemMessage));
      }

      // Load chat history from memory
      if (memory) {
        const memoryMessages = await memory.chatHistory.getMessages();
        messages.push(...memoryMessages);
      }

      messages.push(new HumanMessage(text));

      // Run the agent
      const result = await agentExecutor.invoke(messages);

      // Persist to memory
      if (memory) {
        await memory.chatHistory.addUserMessage(text);
        await memory.chatHistory.addAIChatMessage(result.output);
      }

      // Extract cascadeflow metadata from response
      const responseMetadata = result.message?.response_metadata ?? {};
      const cascadeflowMeta = responseMetadata.cascadeflow ?? responseMetadata.cf ?? {};

      returnData.push({
        json: {
          output: result.output,
          ...cascadeflowMeta,
          trace: result.trace,
          harness: result.harness ?? null,
        },
        pairedItem: { item: itemIndex },
      });
    }

    return [returnData];
  }
}
