import { BaseChatModel } from '@langchain/core/language_models/chat_models';
import {
  AIMessage,
  BaseMessage,
  HumanMessage,
  SystemMessage,
  ToolMessage,
} from '@langchain/core/messages';
import { CascadeFlow } from './wrapper.js';
import type { CascadeConfig } from './types.js';

export type AgentToolHandler = (
  args: Record<string, any>,
  call?: Record<string, any>,
  messages?: BaseMessage[]
) => any | Promise<any>;

export interface CascadeAgentConfig {
  model?: BaseChatModel;
  cascade?: CascadeConfig;
  maxSteps?: number;
  toolHandlers?: Record<string, AgentToolHandler>;
}

export interface CascadeAgentRunOptions {
  systemPrompt?: string;
  maxSteps?: number;
  toolHandlers?: Record<string, AgentToolHandler>;
  invokeOptions?: any;
}

export interface CascadeAgentRunResult {
  message: AIMessage;
  messages: BaseMessage[];
  steps: number;
  status: 'completed' | 'max_steps_reached';
  toolCalls: Array<Record<string, any>>;
}

export class CascadeAgent {
  private model: BaseChatModel;
  private maxSteps: number;
  private toolHandlers: Record<string, AgentToolHandler>;

  constructor(config: CascadeAgentConfig) {
    if (!config.model && !config.cascade) {
      throw new Error("Provide either 'model' or 'cascade' config");
    }

    this.model = config.model || new CascadeFlow(config.cascade as CascadeConfig);
    this.maxSteps = config.maxSteps ?? 8;
    this.toolHandlers = config.toolHandlers || {};
  }

  async run(input: any, options: CascadeAgentRunOptions = {}): Promise<CascadeAgentRunResult> {
    const messages = this.coerceMessages(input, options.systemPrompt);
    const limit = options.maxSteps ?? this.maxSteps;
    const handlers = options.toolHandlers || this.toolHandlers;
    const toolCalls: Array<Record<string, any>> = [];

    for (let step = 1; step <= limit; step++) {
      const response = await this.model.invoke(messages, options.invokeOptions || {});
      const aiMessage = this.coerceAiMessage(response);
      messages.push(aiMessage);

      const calls = this.extractToolCalls(aiMessage);
      if (calls.length === 0) {
        return {
          message: aiMessage,
          messages,
          steps: step,
          status: 'completed',
          toolCalls,
        };
      }

      toolCalls.push(...calls);
      for (let i = 0; i < calls.length; i++) {
        const call = calls[i];
        const toolMessage = await this.executeToolCall(call, handlers, messages, step, i);
        messages.push(toolMessage);
      }
    }

    return {
      message: this.latestAiMessage(messages),
      messages,
      steps: limit,
      status: 'max_steps_reached',
      toolCalls,
    };
  }

  private coerceMessages(input: any, systemPrompt?: string): BaseMessage[] {
    const messages: BaseMessage[] = [];
    if (systemPrompt) {
      messages.push(new SystemMessage(systemPrompt));
    }

    if (typeof input === 'string') {
      messages.push(new HumanMessage(input));
      return messages;
    }

    if (Array.isArray(input)) {
      for (const item of input) {
        messages.push(this.coerceMessage(item));
      }
      return messages;
    }

    if (input instanceof BaseMessage) {
      messages.push(input);
      return messages;
    }

    messages.push(new HumanMessage(String(input)));
    return messages;
  }

  private coerceMessage(input: any): BaseMessage {
    if (input instanceof BaseMessage) return input;

    const role = String(input?.role || 'user');
    const content = input?.content ?? '';

    if (role === 'system') {
      return new SystemMessage(String(content));
    }
    if (role === 'assistant') {
      return new AIMessage({ content: String(content), tool_calls: input?.tool_calls || [] } as any);
    }
    if (role === 'tool') {
      return new ToolMessage({
        content: this.serializeOutput(content),
        tool_call_id: String(input?.tool_call_id || input?.toolCallId || 'tool'),
        name: String(input?.name || 'tool'),
      });
    }

    return new HumanMessage(String(content));
  }

  private coerceAiMessage(response: any): AIMessage {
    if (response instanceof AIMessage) return response;

    if (response instanceof BaseMessage) {
      return new AIMessage({
        content:
          typeof response.content === 'string'
            ? response.content
            : JSON.stringify(response.content),
        additional_kwargs: (response as any).additional_kwargs || {},
        tool_calls: (response as any).tool_calls || [],
        response_metadata: (response as any).response_metadata || {},
      } as any);
    }

    return new AIMessage(String(response ?? ''));
  }

  private extractToolCalls(message: AIMessage): Array<Record<string, any>> {
    const direct = (message as any).tool_calls;
    if (Array.isArray(direct)) {
      return direct.filter((c) => typeof c === 'object' && c);
    }

    const raw = (message as any)?.additional_kwargs?.tool_calls;
    if (!Array.isArray(raw)) return [];

    return raw
      .filter((c) => typeof c === 'object' && c)
      .map((c: any) => {
        const fn = c.function || {};
        const rawArgs = fn.arguments;
        let args: Record<string, any> = {};
        if (typeof rawArgs === 'string') {
          try {
            args = JSON.parse(rawArgs);
          } catch {
            args = { raw: rawArgs };
          }
        } else if (typeof rawArgs === 'object' && rawArgs) {
          args = rawArgs;
        }
        return {
          id: c.id,
          name: c.name || fn.name,
          args,
        };
      });
  }

  private async executeToolCall(
    call: Record<string, any>,
    handlers: Record<string, AgentToolHandler>,
    messages: BaseMessage[],
    step: number,
    index: number
  ): Promise<ToolMessage> {
    const name = String(call.name || 'tool');
    const args = typeof call.args === 'object' && call.args ? call.args : {};
    const toolCallId = String(call.id || `tool_${step}_${index}`);
    const handler = handlers[name];

    if (!handler) {
      return new ToolMessage({
        content: `Tool '${name}' is not available`,
        tool_call_id: toolCallId,
        name,
      });
    }

    try {
      const result = await this.callHandler(handler, args, call, messages);
      return new ToolMessage({
        content: this.serializeOutput(result),
        tool_call_id: toolCallId,
        name,
      });
    } catch (error) {
      return new ToolMessage({
        content: `Tool '${name}' execution failed: ${String((error as Error)?.message || error)}`,
        tool_call_id: toolCallId,
        name,
      });
    }
  }

  private async callHandler(
    handler: AgentToolHandler,
    args: Record<string, any>,
    call: Record<string, any>,
    messages: BaseMessage[]
  ): Promise<any> {
    try {
      return await handler(args, call, messages);
    } catch {
      try {
        return await (handler as any)(args, call);
      } catch {
        try {
          return await (handler as any)(args);
        } catch {
          return await (handler as any)();
        }
      }
    }
  }

  private serializeOutput(value: any): string {
    if (typeof value === 'string') return value;
    if (value == null) return '';
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }

  private latestAiMessage(messages: BaseMessage[]): AIMessage {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i] instanceof AIMessage) {
        return messages[i] as AIMessage;
      }
    }
    return new AIMessage('');
  }
}
