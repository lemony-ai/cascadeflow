import { BaseMessage, HumanMessage, AIMessage, SystemMessage } from '@langchain/core/messages';
import { BaseChatMessageHistory } from '@langchain/core/chat_history';

export class MemoryManager {
	private messageHistory: BaseMessage[] = [];
	private n8nMemory: any;

	constructor(private enableMemory: boolean = false) {}

	async loadMemory(n8nMemory: any): Promise<void> {
		if (!this.enableMemory || !n8nMemory) {
			return;
		}

		this.n8nMemory = n8nMemory;

		try {
			if (typeof n8nMemory.getMessages === 'function') {
				this.messageHistory = await n8nMemory.getMessages();
			} else if (n8nMemory.chatHistory) {
				if (typeof n8nMemory.chatHistory.getMessages === 'function') {
					this.messageHistory = await n8nMemory.chatHistory.getMessages();
				}
			}
		} catch (error) {
			console.warn('Failed to load memory:', error);
			this.messageHistory = [];
		}
	}

	async addMessage(message: BaseMessage): Promise<void> {
		if (!this.enableMemory) {
			return;
		}

		this.messageHistory.push(message);

		if (this.n8nMemory) {
			try {
				if (typeof this.n8nMemory.addMessage === 'function') {
					await this.n8nMemory.addMessage(message);
				} else if (this.n8nMemory.chatHistory && typeof this.n8nMemory.chatHistory.addMessage === 'function') {
					await this.n8nMemory.chatHistory.addMessage(message);
				}
			} catch (error) {
				console.warn('Failed to add message to memory:', error);
			}
		}
	}

	async addUserMessage(content: string): Promise<void> {
		await this.addMessage(new HumanMessage(content));
	}

	async addAIMessage(content: string): Promise<void> {
		await this.addMessage(new AIMessage(content));
	}

	getMessages(): BaseMessage[] {
		return [...this.messageHistory];
	}

	getMessagesWithNewQuery(query: string): BaseMessage[] {
		return [...this.messageHistory, new HumanMessage(query)];
	}

	async clear(): Promise<void> {
		this.messageHistory = [];

		if (this.n8nMemory) {
			try {
				if (typeof this.n8nMemory.clear === 'function') {
					await this.n8nMemory.clear();
				} else if (this.n8nMemory.chatHistory && typeof this.n8nMemory.chatHistory.clear === 'function') {
					await this.n8nMemory.chatHistory.clear();
				}
			} catch (error) {
				console.warn('Failed to clear memory:', error);
			}
		}
	}

	hasMemory(): boolean {
		return this.messageHistory.length > 0;
	}

	getMessageCount(): number {
		return this.messageHistory.length;
	}

	getConversationSummary(): string {
		if (this.messageHistory.length === 0) {
			return 'No conversation history';
		}

		const summary = this.messageHistory
			.slice(-5)
			.map(msg => {
				const role = msg._getType();
				const content = msg.content.toString().slice(0, 100);
				return `${role}: ${content}${msg.content.toString().length > 100 ? '...' : ''}`;
			})
			.join('\n');

		return `Last ${Math.min(5, this.messageHistory.length)} messages:\n${summary}`;
	}
}
