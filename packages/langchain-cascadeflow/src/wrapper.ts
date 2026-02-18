import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import { BaseMessage, AIMessage, AIMessageChunk, ChatMessage, HumanMessage } from '@langchain/core/messages';
import { ChatResult, ChatGeneration, ChatGenerationChunk } from '@langchain/core/outputs';
import { CallbackManagerForLLMRun } from '@langchain/core/callbacks/manager';
import type { CascadeConfig, CascadeResult } from './types.js';
import { calculateCost, calculateQuality, createCostMetadata, extractTokenUsage, extractToolCalls } from './utils.js';
import { PreRouter } from './routers/pre-router.js';
import { RoutingStrategy } from './routers/base.js';
import type { QueryComplexity } from './complexity.js';
import { getToolRiskRouting } from './tool-risk.js';

type NormalizedToolDef = { name: string; description?: string };

function uniqStrings(items: Array<string | undefined | null>): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const x of items) {
    if (!x) continue;
    if (seen.has(x)) continue;
    seen.add(x);
    out.push(x);
  }
  return out;
}

function mergeTags(existing: any, extra: string[]): string[] {
  const base = Array.isArray(existing) ? existing : [];
  return uniqStrings([...base, ...extra]);
}

function mergeMetadata(existing: any, extra: Record<string, any>): Record<string, any> {
  const base = existing && typeof existing === 'object' ? existing : {};
  // Avoid deep merge surprises; keep CascadeFlow metadata namespaced.
  return { ...base, ...extra };
}

function resolveModelName(model: any, depth = 0): string {
  if (!model || depth > 5) return 'unknown';

  const direct =
    (typeof model.model === 'string' && model.model) ||
    (typeof model.modelName === 'string' && model.modelName);
  if (direct) return direct;

  const lcKwargs = model.lc_kwargs || model.lcKwargs;
  const lc =
    (typeof lcKwargs?.model === 'string' && lcKwargs.model) ||
    (typeof lcKwargs?.modelName === 'string' && lcKwargs.modelName);
  if (lc) return lc;

  // LangChain's bind()/bindTools() returns a RunnableBinding-like wrapper
  // where the underlying chat model is stored in `.bound`.
  if (model.bound) return resolveModelName(model.bound, depth + 1);

  return 'unknown';
}

function normalizeDomainKey(value: any): string | undefined {
  if (typeof value !== 'string') return undefined;
  const normalized = value.trim().toLowerCase();
  return normalized.length > 0 ? normalized : undefined;
}

function normalizeToolDefs(tools: any[]): NormalizedToolDef[] {
  const out: NormalizedToolDef[] = [];
  for (const t of tools || []) {
    if (!t) continue;
    if (typeof t === 'object') {
      // Common LangChain formats:
      // 1) { name, description, parameters }
      // 2) OpenAI tools: { type: 'function', function: { name, description, parameters } }
      const fn = (t.function || t?.lc_kwargs?.function) as any | undefined;
      const name = (t.name || fn?.name || t?.lc_kwargs?.name || t?.lc_kwargs?.tool?.name) as
        | string
        | undefined;
      const description = (t.description || fn?.description || t?.lc_kwargs?.description || t?.description) as
        | string
        | undefined;
      if (name) out.push({ name, description });
      continue;
    }
  }
  return out;
}

function extractToolCallNamesFromCalls(calls: any[]): string[] {
  const names: string[] = [];
  for (const c of calls || []) {
    const direct = c?.name;
    const fn = c?.function?.name;
    if (typeof direct === 'string' && direct) names.push(direct);
    else if (typeof fn === 'string' && fn) names.push(fn);
  }
  return uniqStrings(names);
}

/**
 * CascadeFlow - Transparent wrapper for LangChain chat models
 *
 * Preserves all LangChain model functionality while adding intelligent
 * cascade logic for cost optimization.
 *
 * @example
 * ```typescript
 * const drafter = new ChatOpenAI({ model: 'gpt-4o-mini' });
 * const verifier = new ChatOpenAI({ model: 'gpt-4o' });
 *
 * const cascade = new CascadeFlow({
 *   drafter,
 *   verifier,
 *   qualityThreshold: 0.7
 * });
 *
 * const result = await cascade.invoke("What is TypeScript?");
 * ```
 */
export class CascadeFlow extends BaseChatModel {
  private config: Required<Omit<CascadeConfig, 'preRouter'>> & { preRouter?: PreRouter };
  public drafter: BaseChatModel;
  public verifier: BaseChatModel;

  // Store last cascade result for metadata
  private lastCascadeResult?: CascadeResult;

  // Store bind kwargs to merge during _generate
  private bindKwargs: any = {};

  // PreRouter for complexity-based routing
  private preRouter?: PreRouter;

  // Tracks tools bound via bindTools(). If tools are available, streaming must be tool-safe.
  private boundToolDefs?: NormalizedToolDef[];
  private boundToolDefsByName: Map<string, NormalizedToolDef> = new Map();

  constructor(config: CascadeConfig, bindKwargs: any = {}, internal?: { boundTools?: any[] }) {
    super({});

    this.drafter = config.drafter;
    this.verifier = config.verifier;
    this.bindKwargs = bindKwargs;

    // Set defaults
    this.config = {
      drafter: config.drafter,
      verifier: config.verifier,
      qualityThreshold: config.qualityThreshold ?? 0.7,
      enableCostTracking: config.enableCostTracking ?? true,
      // Default to local pricing for best DX (works without LangSmith).
      // Use 'langsmith' if you want server-side cost computation in LangSmith UI.
      costTrackingProvider: config.costTrackingProvider ?? 'cascadeflow',
      qualityValidator: config.qualityValidator ?? calculateQuality,
      enablePreRouter: config.enablePreRouter ?? true,  // Match Python default
      preRouter: config.preRouter,
      cascadeComplexities: config.cascadeComplexities ?? ['trivial', 'simple', 'moderate'],
      domainPolicies: Object.fromEntries(
        Object.entries(config.domainPolicies || {}).map(([k, v]) => [k.toLowerCase(), v || {}])
      ),
    };

    // Initialize PreRouter if enabled
    if (this.config.enablePreRouter) {
      this.preRouter = this.config.preRouter ?? new PreRouter({
        cascadeComplexities: this.config.cascadeComplexities,
      });
    }

    if (internal?.boundTools) {
      this.boundToolDefs = normalizeToolDefs(internal.boundTools);
      this.boundToolDefsByName = new Map(this.boundToolDefs.map((t) => [t.name, t]));
    }

    // Return a Proxy for method delegation
    return new Proxy(this, {
      get(target, prop, receiver) {
        // Check if method exists on target (CascadeWrapper) first
        if (prop in target || typeof prop === 'symbol') {
          return Reflect.get(target, prop, receiver);
        }

        // Delegate to drafter for unknown methods/properties
        const drafterValue = Reflect.get(target.drafter, prop);

        // If it's a method, bind it to drafter
        if (typeof drafterValue === 'function') {
          return (...args: any[]) => drafterValue.apply(target.drafter, args);
        }

        return drafterValue;
      },

      set(target, prop, value, receiver) {
        // Set on both drafter and verifier to keep them in sync
        if (prop in target.drafter && prop in target.verifier) {
          Reflect.set(target.drafter, prop, value);
          Reflect.set(target.verifier, prop, value);
          return true;
        }

        return Reflect.set(target, prop, value, receiver);
      },
    });
  }

  /**
   * Required LangChain method - returns the LLM type identifier
   */
  _llmType(): string {
    return 'cascadeflow';
  }

  /**
   * Override invoke to add agent metadata to messages
   * The agent role is stored in metadata instead of as a message role
   */
  override async invoke(
    input: BaseMessage[] | string,
    options?: any
  ): Promise<any> {
    // Do not coerce inputs here: LCEL pipelines can pass PromptValue objects and other
    // LangChain-native inputs. Let BaseChatModel handle coercion.
    const enrichedOptions = {
      ...options,
      metadata: {
        ...options?.metadata,
        agent_role: 'cascade_agent',
      },
    };

    return super.invoke(input as any, enrichedOptions);
  }

  /**
   * Core cascade generation logic
   * Implements the speculative execution pattern
   */
  async _generate(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): Promise<ChatResult> {
    const startTime = Date.now();

    // Merge bind kwargs with options
    const mergedOptions = { ...this.bindKwargs, ...options };
    let baseTags = mergeTags((mergedOptions as any).tags, ['cascadeflow']);
    let resolvedDomain = this.resolveDomain(messages, (mergedOptions as any).metadata);
    let effectiveQualityThreshold = this.effectiveQualityThreshold(resolvedDomain);
    let forceVerifierForDomain = this.domainForceVerifier(resolvedDomain);
    let directToVerifierForDomain = this.domainDirectToVerifier(resolvedDomain);
    const baseMetadata = mergeMetadata((mergedOptions as any).metadata, {
      cascadeflow: {
        integration: 'langchain',
        domain: resolvedDomain,
        effective_quality_threshold: effectiveQualityThreshold,
      },
    });
    if (resolvedDomain) {
      baseTags = mergeTags(baseTags, [`cascadeflow:domain=${resolvedDomain}`]);
    }

    // STEP 0: PreRouter - Check if we should bypass cascade
    let useCascade = true;
    let routingDecision: any;
    if (this.preRouter) {
      // Extract query text from messages
      const queryText = messages
        .map((msg) => {
          if (typeof msg.content === 'string') {
            return msg.content;
          } else if (Array.isArray(msg.content)) {
            return msg.content
              .map((part: any) => (typeof part === 'string' ? part : part.text || ''))
              .join(' ');
          }
          return '';
        })
        .join('\n');

      // Route based on complexity
      routingDecision = await this.preRouter.route(queryText);
      useCascade = routingDecision.strategy === RoutingStrategy.CASCADE;
      if (!resolvedDomain) {
        resolvedDomain = this.resolveDomain(messages, (mergedOptions as any).metadata, routingDecision);
        effectiveQualityThreshold = this.effectiveQualityThreshold(resolvedDomain);
        forceVerifierForDomain = this.domainForceVerifier(resolvedDomain);
        directToVerifierForDomain = this.domainDirectToVerifier(resolvedDomain);
        (baseMetadata as any).cascadeflow = {
          ...(baseMetadata as any).cascadeflow,
          domain: resolvedDomain,
          effective_quality_threshold: effectiveQualityThreshold,
        };
        if (resolvedDomain) {
          baseTags = mergeTags(baseTags, [`cascadeflow:domain=${resolvedDomain}`]);
        }
      }

      // If direct routing, skip drafter and go straight to verifier
      if (!useCascade || directToVerifierForDomain) {
        const verifierMessage = await this.verifier.invoke(messages, {
          ...mergedOptions,
          runName: 'cascadeflow:verifier',
          tags: mergeTags(baseTags, ['cascadeflow:direct', 'cascadeflow:verifier', 'verifier']),
          metadata: mergeMetadata(baseMetadata, {
            cascadeflow: {
              ...(baseMetadata as any).cascadeflow,
              decision: 'direct',
              role: 'verifier',
              reason: directToVerifierForDomain ? 'domain_policy_direct' : 'pre_router_direct',
            },
          }),
        });
        const verifierResult: ChatResult = {
          generations: [
            {
              text: typeof verifierMessage.content === 'string'
                ? verifierMessage.content
                : JSON.stringify(verifierMessage.content),
              message: verifierMessage,
            },
          ],
          llmOutput: (verifierMessage as any).response_metadata || {},
        };

        const latencyMs = Date.now() - startTime;
        const verifierModelName = resolveModelName(this.verifier);
        const verifierTokens = extractTokenUsage(verifierResult);
        const verifierCost =
          this.config.costTrackingProvider === 'cascadeflow'
            ? calculateCost(verifierModelName, verifierTokens.input, verifierTokens.output)
            : 0;

        // Store cascade result (direct to verifier)
        this.lastCascadeResult = {
          content: verifierResult.generations[0].text,
          modelUsed: 'verifier',
          drafterQuality: undefined,
          accepted: false,
          drafterCost: 0,
          verifierCost,
          totalCost: verifierCost,
          savingsPercentage: 0,
          latencyMs,
        };

        // Inject metadata if cost tracking enabled
        if (this.config.enableCostTracking) {
          try {
            const metadata = {
              cascade_decision: 'direct',
              model_used: 'verifier',
              routing_reason: directToVerifierForDomain ? 'domain_policy_direct' : routingDecision.reason,
              complexity: routingDecision?.metadata?.complexity,
              domain: resolvedDomain,
              effective_quality_threshold: effectiveQualityThreshold,
            };

            verifierResult.llmOutput = {
              ...verifierResult.llmOutput,
              cascade: metadata,
            };

            if (verifierResult.generations[0]?.message) {
              const message = verifierResult.generations[0].message;
              if ('response_metadata' in message) {
                (message as any).response_metadata = {
                  ...(message as any).response_metadata,
                  cascade: metadata,
                };
              }
              (message as any).llmOutput = {
                ...(message as any).llmOutput,
                cascade: metadata,
              };
            }
          } catch (error) {
            console.warn('Failed to inject cascade metadata:', error);
          }
        }

        return verifierResult;
      }
    }

    if (directToVerifierForDomain) {
      const verifierMessage = await this.verifier.invoke(messages, {
        ...mergedOptions,
        runName: 'cascadeflow:verifier',
        tags: mergeTags(baseTags, [
          'cascadeflow:direct',
          'cascadeflow:verifier',
          'verifier',
          'cascadeflow:reason=domain_policy_direct',
        ]),
        metadata: mergeMetadata(baseMetadata, {
          cascadeflow: {
            ...(baseMetadata as any).cascadeflow,
            decision: 'direct',
            role: 'verifier',
            reason: 'domain_policy_direct',
          },
        }),
      });
      const verifierResult: ChatResult = {
        generations: [
          {
            text: typeof verifierMessage.content === 'string'
              ? verifierMessage.content
              : JSON.stringify(verifierMessage.content),
            message: verifierMessage,
          },
        ],
        llmOutput: (verifierMessage as any).response_metadata || {},
      };
      if (this.config.enableCostTracking) {
        verifierResult.llmOutput = {
          ...verifierResult.llmOutput,
          cascade: {
            cascade_decision: 'direct',
            model_used: 'verifier',
            routing_reason: 'domain_policy_direct',
            domain: resolvedDomain,
            drafter_quality: 0,
            effective_quality_threshold: effectiveQualityThreshold,
          },
        };
      }
      return verifierResult;
    }

    // STEP 1: Execute drafter (cheap, fast model)
    // Use invoke() to ensure LangSmith captures the model trace
    const drafterMessage = await this.drafter.invoke(messages, {
      ...mergedOptions,
      runName: 'cascadeflow:drafter',
      tags: mergeTags(baseTags, ['cascadeflow:drafter', 'drafter']),
      metadata: mergeMetadata(baseMetadata, {
        cascadeflow: { ...(baseMetadata as any).cascadeflow, decision: 'draft', role: 'drafter' },
      }),
    });
    const drafterResult: ChatResult = {
      generations: [
        {
          text: typeof drafterMessage.content === 'string'
            ? drafterMessage.content
            : JSON.stringify(drafterMessage.content),
          message: drafterMessage,
        },
      ],
      llmOutput: (drafterMessage as any).response_metadata || {},
    };

    const drafterToolCalls = extractToolCalls(drafterResult);
    const invokedToolNames = extractToolCallNamesFromCalls(drafterToolCalls);
    const invokedToolDefs: NormalizedToolDef[] = invokedToolNames.map((name) => {
      return this.boundToolDefsByName.get(name) || { name };
    });
    const toolRisk = invokedToolDefs.length > 0 ? getToolRiskRouting(invokedToolDefs) : null;
    const forceVerifierForToolRisk = toolRisk?.useVerifier ?? false;

    const drafterQuality = this.config.qualityValidator
      ? await this.config.qualityValidator(drafterResult)
      : calculateQuality(drafterResult);

    // STEP 2: Check quality threshold + domain policy
    const accepted = forceVerifierForDomain
      ? false
      : (invokedToolNames.length > 0
          ? !forceVerifierForToolRisk
          : drafterQuality >= effectiveQualityThreshold);

    let finalResult: ChatResult;
    let verifierResult: ChatResult | null = null;

    if (accepted) {
      // Quality is sufficient - use drafter response
      finalResult = drafterResult;
    } else {
      // Quality insufficient - execute verifier (expensive, accurate model)
      // Use invoke() to ensure LangSmith captures the model trace
      const verifierDecision =
        forceVerifierForToolRisk ? 'tool_risk' : (forceVerifierForDomain ? 'domain_policy' : 'quality');
      const verifierMessage = await this.verifier.invoke(messages, {
        ...mergedOptions,
        runName: 'cascadeflow:verifier',
        tags: mergeTags(baseTags, [
          'cascadeflow:verifier',
          'verifier',
          'cascadeflow:escalated',
          `cascadeflow:reason=${verifierDecision}`,
          ...(toolRisk?.maxRiskName ? [`cascadeflow:toolrisk=${toolRisk.maxRiskName}`] : []),
        ]),
        metadata: mergeMetadata(baseMetadata, {
          cascadeflow: {
            ...(baseMetadata as any).cascadeflow,
            decision: 'verify',
            role: 'verifier',
            reason: verifierDecision,
            tool_risk: toolRisk || undefined,
            domain_policy: this.domainPolicy(resolvedDomain),
          },
        }),
      });
      const vResult: ChatResult = {
        generations: [
          {
            text: typeof verifierMessage.content === 'string'
              ? verifierMessage.content
              : JSON.stringify(verifierMessage.content),
            message: verifierMessage,
          },
        ],
        llmOutput: (verifierMessage as any).response_metadata || {},
      };
      verifierResult = vResult;
      finalResult = vResult;
    }

    // STEP 3: Calculate costs and metadata
    const latencyMs = Date.now() - startTime;
    const drafterModelName = resolveModelName(this.drafter);
    const verifierModelName = resolveModelName(this.verifier);
    const costMetadata = createCostMetadata(
      drafterResult,
      verifierResult,
      drafterModelName,
      verifierModelName,
      accepted,
      drafterQuality,
      this.config.costTrackingProvider
    );

    const cascadeDecision =
      invokedToolNames.length > 0 && !forceVerifierForDomain
        ? (accepted ? 'tool_call' : 'tool_risk')
        : (accepted ? 'accepted' : (forceVerifierForDomain ? 'domain_policy' : 'quality'));

    // Store cascade result
    this.lastCascadeResult = {
      content: finalResult.generations[0].text,
      modelUsed: accepted ? 'drafter' : 'verifier',
      drafterQuality,
      accepted,
      drafterCost: costMetadata.drafterCost,
      verifierCost: costMetadata.verifierCost,
      totalCost: costMetadata.totalCost,
      savingsPercentage: costMetadata.savingsPercentage,
      latencyMs,
    };

    // STEP 4: Inject cost metadata into llmOutput (if enabled)
    // LangSmith will automatically capture this metadata in traces
    if (this.config.enableCostTracking) {
      try {
        // Inject into llmOutput
        finalResult.llmOutput = {
          ...finalResult.llmOutput,
          cascade: {
            ...costMetadata,
            cascade_decision: cascadeDecision,
            invoked_tools: invokedToolNames.length > 0 ? invokedToolNames : undefined,
            tool_risk: toolRisk || undefined,
            domain: resolvedDomain,
            effective_quality_threshold: effectiveQualityThreshold,
            domain_policy: this.domainPolicy(resolvedDomain),
          },
        };

        // Also inject into message's response_metadata for invoke() results
        if (finalResult.generations[0]?.message) {
          const message = finalResult.generations[0].message;
          if ('response_metadata' in message) {
            (message as any).response_metadata = {
              ...(message as any).response_metadata,
              cascade: finalResult.llmOutput.cascade,
            };
          }
          // Also set as llmOutput property for backward compatibility
          (message as any).llmOutput = {
            ...(message as any).llmOutput,
            cascade: finalResult.llmOutput.cascade,
          };
        }
      } catch (error) {
        console.warn('Failed to inject cascade metadata:', error);
      }
    }

    return finalResult;
  }

  /**
   * Get the last cascade execution result
   */
  getLastCascadeResult(): CascadeResult | undefined {
    return this.lastCascadeResult;
  }

  private resolveDomain(messages: BaseMessage[], metadata: any, routingDecision?: any): string | undefined {
    const cascadeMeta = metadata?.cascadeflow;
    const byCascadeMeta = normalizeDomainKey(cascadeMeta?.domain);
    if (byCascadeMeta) return byCascadeMeta;

    const byDirectMeta = normalizeDomainKey(metadata?.cascadeflow_domain || metadata?.domain);
    if (byDirectMeta) return byDirectMeta;

    const byRoutingMeta = normalizeDomainKey(routingDecision?.metadata?.domain);
    if (byRoutingMeta) return byRoutingMeta;

    const routingDomains = routingDecision?.metadata?.domains;
    if (Array.isArray(routingDomains)) {
      for (const d of routingDomains) {
        const normalized = normalizeDomainKey(d);
        if (normalized) return normalized;
      }
    }

    const detector = (this.preRouter as any)?.detector;
    if (detector && typeof detector.detect === 'function') {
      try {
        const queryText = messages
          .map((msg) => {
            if (typeof msg.content === 'string') return msg.content;
            if (Array.isArray(msg.content)) {
              return msg.content.map((part: any) => (typeof part === 'string' ? part : part.text || '')).join(' ');
            }
            return '';
          })
          .join('\\n');
        const detected = detector.detect(queryText);
        const detectedDomains = detected?.metadata?.domains;
        if (detectedDomains instanceof Set) {
          for (const d of Array.from(detectedDomains).sort()) {
            const normalized = normalizeDomainKey(d);
            if (normalized) return normalized;
          }
        }
        if (Array.isArray(detectedDomains)) {
          for (const d of detectedDomains) {
            const normalized = normalizeDomainKey(d);
            if (normalized) return normalized;
          }
        }
      } catch {
        return undefined;
      }
    }

    return undefined;
  }

  private domainPolicy(domain: string | undefined): Record<string, any> {
    if (!domain) return {};
    return (this.config.domainPolicies as Record<string, any>)[domain] || {};
  }

  private effectiveQualityThreshold(domain: string | undefined): number {
    const raw = this.domainPolicy(domain).qualityThreshold;
    if (typeof raw === 'number' && Number.isFinite(raw)) {
      return Math.max(0, Math.min(1, raw));
    }
    return this.config.qualityThreshold;
  }

  private domainForceVerifier(domain: string | undefined): boolean {
    return Boolean(this.domainPolicy(domain).forceVerifier);
  }

  private domainDirectToVerifier(domain: string | undefined): boolean {
    return Boolean(this.domainPolicy(domain).directToVerifier);
  }

  /**
   * Stream responses with optimistic drafter execution
   *
   * Uses the proven cascade streaming pattern:
   * 1. Stream drafter optimistically (user sees real-time output)
   * 2. Collect chunks and check quality after completion
   * 3. If quality insufficient: show switch message + stream verifier
   *
   * @param messages - Input messages
   * @param options - Streaming options
   * @returns AsyncGenerator yielding chunks
   */
  async *_streamResponseChunks(
    messages: BaseMessage[],
    options: this['ParsedCallOptions'],
    runManager?: CallbackManagerForLLMRun
  ): AsyncGenerator<ChatGenerationChunk> {
    const startTime = Date.now();

    // Merge bind kwargs with options
    const mergedOptions = { ...this.bindKwargs, ...options };
    let baseTags = mergeTags((mergedOptions as any).tags, ['cascadeflow']);
    let resolvedDomain = this.resolveDomain(messages, (mergedOptions as any).metadata);
    let effectiveQualityThreshold = this.effectiveQualityThreshold(resolvedDomain);
    let forceVerifierForDomain = this.domainForceVerifier(resolvedDomain);
    let directToVerifierForDomain = this.domainDirectToVerifier(resolvedDomain);
    const baseMetadata = mergeMetadata((mergedOptions as any).metadata, {
      cascadeflow: {
        integration: 'langchain',
        streaming: true,
        domain: resolvedDomain,
        effective_quality_threshold: effectiveQualityThreshold,
      },
    });
    if (resolvedDomain) {
      baseTags = mergeTags(baseTags, [`cascadeflow:domain=${resolvedDomain}`]);
    }

    // STEP 0: PreRouter - Check if we should bypass cascade
    let useCascade = true;
    let routingDecision: any;
    if (this.preRouter) {
      const queryText = messages
        .map((msg) => {
          if (typeof msg.content === 'string') {
            return msg.content;
          } else if (Array.isArray(msg.content)) {
            return msg.content
              .map((part: any) => (typeof part === 'string' ? part : part.text || ''))
              .join(' ');
          }
          return '';
        })
        .join('\n');

      routingDecision = await this.preRouter.route(queryText);
      useCascade = routingDecision.strategy === RoutingStrategy.CASCADE;
      if (!resolvedDomain) {
        resolvedDomain = this.resolveDomain(messages, (mergedOptions as any).metadata, routingDecision);
        effectiveQualityThreshold = this.effectiveQualityThreshold(resolvedDomain);
        forceVerifierForDomain = this.domainForceVerifier(resolvedDomain);
        directToVerifierForDomain = this.domainDirectToVerifier(resolvedDomain);
        (baseMetadata as any).cascadeflow = {
          ...(baseMetadata as any).cascadeflow,
          domain: resolvedDomain,
          effective_quality_threshold: effectiveQualityThreshold,
        };
        if (resolvedDomain) {
          baseTags = mergeTags(baseTags, [`cascadeflow:domain=${resolvedDomain}`]);
        }
      }

      // If direct routing, stream verifier only
      if (!useCascade || directToVerifierForDomain) {
        for await (const chunk of this.verifier._streamResponseChunks(
          messages,
          {
            ...mergedOptions,
            runName: 'cascadeflow:verifier',
            tags: mergeTags(baseTags, ['cascadeflow:direct', 'cascadeflow:verifier', 'verifier']),
            metadata: mergeMetadata(baseMetadata, {
              cascadeflow: {
                ...(baseMetadata as any).cascadeflow,
                decision: 'direct',
                role: 'verifier',
                reason: directToVerifierForDomain ? 'domain_policy_direct' : 'pre_router_direct',
              },
            }),
          },
          runManager
        )) {
          yield chunk;
        }
        return;
      }
    }

    if (directToVerifierForDomain) {
      for await (const chunk of this.verifier._streamResponseChunks(
        messages,
        {
          ...mergedOptions,
          runName: 'cascadeflow:verifier',
          tags: mergeTags(baseTags, [
            'cascadeflow:direct',
            'cascadeflow:verifier',
            'verifier',
            'cascadeflow:reason=domain_policy_direct',
          ]),
          metadata: mergeMetadata(baseMetadata, {
            cascadeflow: {
              ...(baseMetadata as any).cascadeflow,
              decision: 'direct',
              role: 'verifier',
              reason: 'domain_policy_direct',
            },
          }),
        },
        runManager
      )) {
        yield chunk;
      }
      return;
    }

    const toolsBound = (this.boundToolDefs?.length || 0) > 0;
    const emitSwitchMessage = Boolean((mergedOptions as any)?.metadata?.cascadeflow_emit_switch_message);

    // If tools are bound, streaming must be tool-safe: we cannot optimistically emit tool call deltas
    // and later change the tool call by escalating to a verifier.
    const drafterChunks: ChatGenerationChunk[] = [];
    let drafterContent = '';

    for await (const chunk of this.drafter._streamResponseChunks(messages, {
      ...mergedOptions,
      runName: 'cascadeflow:drafter',
      tags: mergeTags(baseTags, ['cascadeflow:drafter', 'drafter']),
      metadata: mergeMetadata(baseMetadata, {
        cascadeflow: { ...(baseMetadata as any).cascadeflow, decision: 'draft', role: 'drafter' },
      }),
    }, runManager)) {
      drafterChunks.push(chunk);
      const chunkText = typeof chunk.message.content === 'string' ? chunk.message.content : '';
      drafterContent += chunkText;
      if (!toolsBound) {
        // Strip provider-specific chunk metadata to avoid concat warnings when we later stream a verifier.
        yield new ChatGenerationChunk({
          text: chunkText,
          message: new AIMessageChunk({ content: chunkText }),
        });
      }
    }

    // STEP 2: Quality check after drafter completes
    // Avoid `AIMessageChunk.concat` here: some provider chunk metadata fields are not safely mergeable
    // and can emit warnings. For quality scoring we only need the final text (and tool_calls if present).
    const lastMsg: any = drafterChunks[drafterChunks.length - 1]?.message;
    const combinedMessage = new AIMessage({
      content: drafterContent,
      additional_kwargs: lastMsg?.additional_kwargs ?? {},
      tool_calls: lastMsg?.tool_calls ?? [],
      invalid_tool_calls: lastMsg?.invalid_tool_calls ?? [],
      response_metadata: lastMsg?.response_metadata ?? {},
    } as any);

    const drafterResult: ChatResult = {
      generations: [
        {
          text: typeof combinedMessage.content === 'string' ? combinedMessage.content : '',
          message: combinedMessage,
        },
      ],
      llmOutput: {},
    };

    const drafterQuality = this.config.qualityValidator
      ? await this.config.qualityValidator(drafterResult)
      : calculateQuality(drafterResult);

    const drafterToolCalls = extractToolCalls(drafterResult);
    const invokedToolNames = extractToolCallNamesFromCalls(drafterToolCalls);
    const invokedToolDefs: NormalizedToolDef[] = invokedToolNames.map((name) => {
      return this.boundToolDefsByName.get(name) || { name };
    });
    const toolRisk = invokedToolDefs.length > 0 ? getToolRiskRouting(invokedToolDefs) : null;
    const forceVerifierForToolRisk = toolRisk?.useVerifier ?? false;

    const accepted = forceVerifierForDomain
      ? false
      : (invokedToolNames.length > 0
          ? !forceVerifierForToolRisk
          : drafterQuality >= effectiveQualityThreshold);

    // STEP 3: If quality insufficient, cascade to verifier
    if (!accepted) {
      if (emitSwitchMessage && !toolsBound) {
        const { ChatGenerationChunk } = await import('@langchain/core/outputs');
        const { AIMessageChunk } = await import('@langchain/core/messages');
        const verifierModelName = resolveModelName(this.verifier);
        const switchMessage = `\n\n[CascadeFlow] Escalating to ${verifierModelName} (quality: ${drafterQuality.toFixed(2)} < ${effectiveQualityThreshold})\n\n`;
        yield new ChatGenerationChunk({
          text: switchMessage,
          message: new AIMessageChunk({ content: switchMessage }),
        });
      }

      // Stream from verifier
      for await (const chunk of this.verifier._streamResponseChunks(
        messages,
        {
          ...mergedOptions,
          runName: 'cascadeflow:verifier',
          tags: mergeTags(baseTags, [
            'cascadeflow:verifier',
            'verifier',
            'cascadeflow:escalated',
            `cascadeflow:reason=${forceVerifierForToolRisk ? 'tool_risk' : (forceVerifierForDomain ? 'domain_policy' : 'quality')}`,
            ...(toolRisk?.maxRiskName ? [`cascadeflow:toolrisk=${toolRisk.maxRiskName}`] : []),
          ]),
          metadata: mergeMetadata(baseMetadata, {
            cascadeflow: {
              ...(baseMetadata as any).cascadeflow,
              decision: 'verify',
              role: 'verifier',
              reason: forceVerifierForToolRisk ? 'tool_risk' : (forceVerifierForDomain ? 'domain_policy' : 'quality'),
              tool_risk: toolRisk || undefined,
              domain_policy: this.domainPolicy(resolvedDomain),
            },
          }),
        },
        runManager
      )) {
        if (toolsBound) {
          yield chunk;
          continue;
        }

        const chunkText = typeof chunk.message.content === 'string' ? chunk.message.content : '';
        yield new ChatGenerationChunk({
          text: chunkText,
          message: new AIMessageChunk({ content: chunkText }),
        });
      }
      return;
    }

    // Accepted drafter (tool-safe mode: emit buffered chunks only after final decision)
    if (toolsBound) {
      for (const chunk of drafterChunks) {
        yield chunk;
      }
    }

    // Store cascade result (simplified for streaming)
    const latencyMs = Date.now() - startTime;
    this.lastCascadeResult = {
      content: drafterContent,
      modelUsed: accepted ? 'drafter' : 'verifier',
      drafterQuality,
      accepted,
      drafterCost: 0,
      verifierCost: 0,
      totalCost: 0,
      savingsPercentage: accepted ? 50 : 0,
      latencyMs,
    };
  }

  /**
   * Handle chainable methods - bind()
   * Creates a new CascadeFlow with bound parameters
   */
  bind(kwargs: any): CascadeFlow {
    // Merge new kwargs with existing ones
    const mergedKwargs = { ...this.bindKwargs, ...kwargs };

    return new CascadeFlow(
      {
        drafter: this.drafter,
        verifier: this.verifier,
        qualityThreshold: this.config.qualityThreshold,
        enableCostTracking: this.config.enableCostTracking,
        costTrackingProvider: this.config.costTrackingProvider,
        qualityValidator: this.config.qualityValidator,
        enablePreRouter: this.config.enablePreRouter,
        preRouter: this.config.preRouter,
        cascadeComplexities: this.config.cascadeComplexities,
        domainPolicies: this.config.domainPolicies,
      },
      mergedKwargs,
      { boundTools: this.boundToolDefs }
    );
  }

  /**
   * Handle chainable methods - bindTools()
   * Creates a new CascadeFlow with bound tools
   */
  bindTools(tools: any[], kwargs?: any): any {
    if (typeof (this.drafter as any).bindTools !== 'function') {
      throw new Error('Drafter model does not support bindTools()');
    }

    const boundDrafter = (this.drafter as any).bindTools(tools, kwargs);
    const boundVerifier = (this.verifier as any).bindTools(tools, kwargs);

    return new CascadeFlow({
      drafter: boundDrafter,
      verifier: boundVerifier,
      qualityThreshold: this.config.qualityThreshold,
      enableCostTracking: this.config.enableCostTracking,
      costTrackingProvider: this.config.costTrackingProvider,
      qualityValidator: this.config.qualityValidator,
      enablePreRouter: this.config.enablePreRouter,
      preRouter: this.config.preRouter,
      cascadeComplexities: this.config.cascadeComplexities,
      domainPolicies: this.config.domainPolicies,
    }, {}, { boundTools: tools });
  }

  /**
   * Handle chainable methods - withStructuredOutput()
   * Creates a new CascadeFlow with structured output
   */
  withStructuredOutput(outputSchema: any, config?: any): any {
    if (typeof (this.drafter as any).withStructuredOutput !== 'function') {
      throw new Error('Drafter model does not support withStructuredOutput()');
    }

    const boundDrafter = (this.drafter as any).withStructuredOutput(outputSchema, config);
    const boundVerifier = (this.verifier as any).withStructuredOutput(outputSchema, config);

    return new CascadeFlow({
      drafter: boundDrafter,
      verifier: boundVerifier,
      qualityThreshold: this.config.qualityThreshold,
      enableCostTracking: this.config.enableCostTracking,
      costTrackingProvider: this.config.costTrackingProvider,
      qualityValidator: this.config.qualityValidator,
      enablePreRouter: this.config.enablePreRouter,
      preRouter: this.config.preRouter,
      cascadeComplexities: this.config.cascadeComplexities,
      domainPolicies: this.config.domainPolicies,
    }, {}, { boundTools: this.boundToolDefs });
  }
}
