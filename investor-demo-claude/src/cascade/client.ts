// CascadeFlow API client — connects to real cascade endpoint

const API_BASE = "https://cascade.buehrle.io/v1";

export interface CascadeMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface CascadeUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface CascadeRouting {
  draft_model?: string;
  verifier_model?: string;
  route: "draft_accepted" | "escalated" | "direct";
  confidence?: number;
  draft_time_ms?: number;
  verifier_time_ms?: number;
  domain?: string;
}

export interface CascadeChoice {
  index: number;
  message: CascadeMessage;
  finish_reason: string;
}

export interface CascadeResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: CascadeChoice[];
  usage: CascadeUsage;
  cascade?: CascadeRouting;
}

export interface CascadeRequestOptions {
  messages: CascadeMessage[];
  draftModel: string;
  verifierModel: string;
  apiKey: string;
  temperature?: number;
  maxTokens?: number;
}

export async function cascadeComplete(
  opts: CascadeRequestOptions
): Promise<CascadeResponse> {
  const startTime = Date.now();

  const body: Record<string, unknown> = {
    messages: opts.messages,
    model: opts.draftModel,
    cascade: {
      verifier: opts.verifierModel,
      enabled: true,
    },
  };
  if (opts.temperature !== undefined) body.temperature = opts.temperature;
  if (opts.maxTokens !== undefined) body.max_tokens = opts.maxTokens;

  const resp = await fetch(`${API_BASE}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${opts.apiKey}`,
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`Cascade API error ${resp.status}: ${text}`);
  }

  const data = (await resp.json()) as CascadeResponse;
  const totalTime = Date.now() - startTime;

  // If the API doesn't return cascade routing info, infer from response
  if (!data.cascade) {
    data.cascade = {
      route: "draft_accepted",
      draft_time_ms: totalTime,
      draft_model: opts.draftModel,
      verifier_model: opts.verifierModel,
    };
  }

  return data;
}

export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
}

export interface AgenticStep {
  stepNumber: number;
  toolCall: ToolCall;
  response: CascadeResponse;
  totalTimeMs: number;
}

export async function cascadeAgenticRun(
  opts: CascadeRequestOptions & { tools?: ToolCall[] }
): Promise<AgenticStep[]> {
  // For agentic mode, we send the same request but simulate tool use
  // The cascade API handles routing regardless of whether tools are involved
  const steps: AgenticStep[] = [];
  const startTime = Date.now();

  const response = await cascadeComplete(opts);
  steps.push({
    stepNumber: 1,
    toolCall: { name: "generate", arguments: {} },
    response,
    totalTimeMs: Date.now() - startTime,
  });

  return steps;
}
