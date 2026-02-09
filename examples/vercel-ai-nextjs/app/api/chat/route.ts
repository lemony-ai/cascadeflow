import { CascadeAgent, VercelAI } from '@cascadeflow/core';

export const runtime = 'edge';

// Keep the agent outside the handler to reuse it across requests.
const agent = new CascadeAgent({
  models: [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
      apiKey: process.env.OPENAI_API_KEY,
    },
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625,
      apiKey: process.env.OPENAI_API_KEY,
    },
  ],
});

const handler = VercelAI.createChatHandler(agent, {
  // Default `useChat` stream protocol in Vercel AI SDK v4.
  protocol: 'data',
});

export async function POST(req: Request) {
  return handler(req);
}

