import { DynamicStructuredTool } from '@langchain/core/tools';
import { z } from 'zod';

export interface ToolDefinition {
	name: string;
	description: string;
	schema: any;
	execute: (input: any) => Promise<any>;
}

export class ToolHandler {
	private tools: DynamicStructuredTool[] = [];

	constructor(private enableTools: boolean = false) {}

	async loadTools(n8nTools: any[]): Promise<void> {
		if (!this.enableTools || !n8nTools || n8nTools.length === 0) {
			return;
		}

		for (const n8nTool of n8nTools) {
			try {
				const tool = this.convertN8nToolToLangChain(n8nTool);
				this.tools.push(tool);
			} catch (error) {
				console.warn(`Failed to load tool: ${error}`);
			}
		}
	}

	private convertN8nToolToLangChain(n8nTool: any): DynamicStructuredTool {
		const name = n8nTool.name || 'unknown_tool';
		const description = n8nTool.description || 'No description provided';

		const schema = n8nTool.schema || z.object({
			input: z.string().describe('Tool input'),
		});

		return new DynamicStructuredTool({
			name,
			description,
			schema,
			func: async (input: any) => {
				try {
					if (typeof n8nTool.call === 'function') {
						return await n8nTool.call(input);
					}
					return JSON.stringify(input);
				} catch (error) {
					return `Tool execution failed: ${error}`;
				}
			},
		});
	}

	getTools(): DynamicStructuredTool[] {
		return this.tools;
	}

	hasTools(): boolean {
		return this.tools.length > 0;
	}

	async executeTool(toolName: string, input: any): Promise<string> {
		const tool = this.tools.find(t => t.name === toolName);
		if (!tool) {
			throw new Error(`Tool not found: ${toolName}`);
		}

		try {
			const result = await tool.invoke(input);
			return typeof result === 'string' ? result : JSON.stringify(result);
		} catch (error) {
			throw new Error(`Tool execution failed: ${error}`);
		}
	}

	getToolDefinitions(): ToolDefinition[] {
		return this.tools.map(tool => ({
			name: tool.name,
			description: tool.description,
			schema: tool.schema,
			execute: async (input: any) => tool.invoke(input),
		}));
	}
}
