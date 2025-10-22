/**
 * Vercel Edge Function for CascadeFlow
 *
 * This edge function runs globally on Vercel's network for low-latency AI inference.
 *
 * Deploy: vercel deploy
 * Test locally: vercel dev
 */

import { CascadeAgent } from '@cascadeflow/core';

export const config = {
  runtime: 'edge',
};

export default async function handler(req: Request) {
  // Only allow POST requests
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  try {
    const { query, options } = await req.json();

    if (!query || typeof query !== 'string') {
      return new Response('Invalid query', { status: 400 });
    }

    // Create cascade agent
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

    // Run cascade
    const result = await agent.run(query, options);

    // Return result
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*', // Adjust for production
      },
    });
  } catch (error: any) {
    console.error('Edge function error:', error);
    return new Response(
      JSON.stringify({
        error: error.message || 'Internal server error',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}
