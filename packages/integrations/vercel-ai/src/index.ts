import type { CascadeAgent } from '@cascadeflow/core';
import { VercelAI } from '@cascadeflow/core';
import type { Tool } from '@cascadeflow/core';

export type VercelAIStreamProtocol = 'data' | 'text';

export interface VercelAIChatHandlerOptions {
  protocol?: VercelAIStreamProtocol;
  stream?: boolean;
  systemPrompt?: string;
  maxTokens?: number;
  temperature?: number;
  tools?: Tool[];
  extra?: Record<string, any>;
}

export const createChatHandler = (
  agent: CascadeAgent,
  options: VercelAIChatHandlerOptions = {}
) => VercelAI.createChatHandler(agent, options);

export const createCompletionHandler = (
  agent: CascadeAgent,
  options: VercelAIChatHandlerOptions = {}
) => VercelAI.createCompletionHandler(agent, options);

// Re-export the full namespace for advanced consumers (provider adapters, registries, etc.).
export { VercelAI };

