/**
 * Deno Runtime Example
 *
 * Demonstrates using cascadeflow with Deno:
 * - Deno-specific imports
 * - Environment variable handling
 * - TypeScript native support
 * - Permission model
 * - Web-standard APIs
 *
 * Usage with Deno:
 *   deno run --allow-net --allow-env deno-example.ts
 *
 * Usage with Node.js (this file works in both!):
 *   npx tsx examples/nodejs/deno-example.ts
 */

// ============================================================================
// Deno vs Node.js Compatibility
// ============================================================================

console.log('\n╔═══════════════════════════════════════════════════════════════╗');
console.log('║           cascadeflow - Deno Runtime Guide                   ║');
console.log('╚═══════════════════════════════════════════════════════════════╝\n');

console.log('🦕 Deno Integration Patterns\n');

// ============================================================================
// Pattern 1: Installation and Imports
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 1: Installation & Imports');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Deno Import (NPM compatibility):');
console.log(`
import { CascadeAgent } from 'npm:@cascadeflow/core';

// Or with version pinning:
import { CascadeAgent } from 'npm:@cascadeflow/core@^1.0.0';
`);

console.log('No installation required - Deno caches dependencies automatically!\n');

// ============================================================================
// Pattern 2: Environment Variables
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 2: Environment Variables');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Deno-specific environment access:');
console.log(`
// Option 1: Deno.env (requires --allow-env permission)
const apiKey = Deno.env.get('OPENAI_API_KEY');

// Option 2: Load from .env file
import { load } from "https://deno.land/std@0.224.0/dotenv/mod.ts";
const env = await load();
const apiKey2 = env.OPENAI_API_KEY;
`);

console.log('Required permissions:');
console.log('   deno run --allow-env --allow-net your-script.ts\n');

// ============================================================================
// Pattern 3: Basic Usage Example
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 3: Basic Deno Script');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Complete example (save as cascadeflow-deno.ts):');
console.log(`
#!/usr/bin/env -S deno run --allow-net --allow-env

import { CascadeAgent } from 'npm:@cascadeflow/core';

// Get API key from environment
const apiKey = Deno.env.get('OPENAI_API_KEY');
if (!apiKey) {
  console.error('Set OPENAI_API_KEY environment variable');
  Deno.exit(1);
}

// Initialize agent
const agent = new CascadeAgent({
  models: [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
      apiKey,
    },
    {
      name: 'gpt-4o',
      provider: 'openai',
      cost: 0.00625,
      apiKey,
    },
  ],
});

// Run query
const result = await agent.run('Explain Deno in one sentence');
console.log(result.content);
console.log(\`Cost: $\${result.totalCost.toFixed(6)}\`);
`);

console.log('Make executable and run:');
console.log('   chmod +x cascadeflow-deno.ts');
console.log('   ./cascadeflow-deno.ts\n');

// ============================================================================
// Pattern 4: Deno Deploy Integration
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 4: Deno Deploy (Edge Functions)');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('HTTP server for Deno Deploy:');
console.log(`
import { CascadeAgent } from 'npm:@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    {
      name: 'gpt-4o-mini',
      provider: 'openai',
      cost: 0.00015,
      apiKey: Deno.env.get('OPENAI_API_KEY'),
    },
  ],
});

Deno.serve(async (req: Request) => {
  if (req.method !== 'POST') {
    return new Response('Method not allowed', { status: 405 });
  }

  try {
    const { query } = await req.json();
    const result = await agent.run(query);

    return new Response(
      JSON.stringify({
        content: result.content,
        cost: result.totalCost,
        model: result.modelUsed,
      }),
      {
        headers: { 'Content-Type': 'application/json' },
      }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
});
`);

console.log('Deploy to Deno Deploy:');
console.log('   1. Push to GitHub');
console.log('   2. Connect at deno.com/deploy');
console.log('   3. Set OPENAI_API_KEY environment variable');
console.log('   4. Deploy!\n');

// ============================================================================
// Pattern 5: Streaming with Deno
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 5: Streaming Responses');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Streaming works natively with Deno:');
console.log(`
import { CascadeAgent, StreamEventType } from 'npm:@cascadeflow/core';

const agent = new CascadeAgent({
  models: [
    { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
  ],
});

// Stream to console
for await (const event of agent.stream('Explain Deno')) {
  if (event.type === StreamEventType.CHUNK) {
    // Deno.stdout.write() for raw output
    await Deno.stdout.write(new TextEncoder().encode(event.content));
  } else if (event.type === StreamEventType.COMPLETE) {
    console.log(\`\\n\\nCost: $\${event.data.result.totalCost}\`);
  }
}
`);

console.log('SSE streaming server:');
console.log(`
Deno.serve(async (req: Request) => {
  const { query } = await req.json();

  const stream = new ReadableStream({
    async start(controller) {
      for await (const event of agent.stream(query)) {
        if (event.type === StreamEventType.CHUNK) {
          const data = \`data: \${JSON.stringify({ chunk: event.content })}\\n\\n\`;
          controller.enqueue(new TextEncoder().encode(data));
        }
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
    },
  });
});
`);

console.log('\n');

// ============================================================================
// Pattern 6: Permission Model
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 6: Deno Permissions');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Required permissions for cascadeflow:');
console.log('');
console.log('--allow-net');
console.log('   Required for API calls to LLM providers');
console.log('   Example: --allow-net=api.openai.com');
console.log('');
console.log('--allow-env');
console.log('   Required for API keys from environment');
console.log('   Example: --allow-env=OPENAI_API_KEY,ANTHROPIC_API_KEY');
console.log('');
console.log('--allow-read (optional)');
console.log('   If loading .env files');
console.log('   Example: --allow-read=.env');
console.log('');

console.log('Minimal permissions example:');
console.log(`
  deno run \\
    --allow-net=api.openai.com,api.anthropic.com \\
    --allow-env=OPENAI_API_KEY,ANTHROPIC_API_KEY \\
    cascadeflow-script.ts
`);

console.log('\n');

// ============================================================================
// Pattern 7: Testing with Deno
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 7: Testing with Deno Test');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Test file (cascadeflow_test.ts):');
console.log(`
import { assertEquals } from "https://deno.land/std@0.224.0/assert/mod.ts";
import { CascadeAgent } from 'npm:@cascadeflow/core';

Deno.test("CascadeAgent initializes correctly", () => {
  const agent = new CascadeAgent({
    models: [
      { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015 },
    ],
  });

  assertEquals(typeof agent.run, 'function');
  assertEquals(typeof agent.stream, 'function');
});

Deno.test("CascadeAgent runs query", async () => {
  const agent = new CascadeAgent({
    models: [
      {
        name: 'gpt-4o-mini',
        provider: 'openai',
        cost: 0.00015,
        apiKey: Deno.env.get('OPENAI_API_KEY'),
      },
    ],
  });

  const result = await agent.run('Say "test"');
  assertEquals(typeof result.content, 'string');
  assertEquals(typeof result.totalCost, 'number');
});
`);

console.log('Run tests:');
console.log('   deno test --allow-net --allow-env\n');

// ============================================================================
// Pattern 8: Configuration File
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('Pattern 8: deno.json Configuration');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('Create deno.json for project configuration:');
console.log(`
{
  "tasks": {
    "start": "deno run --allow-net --allow-env main.ts",
    "dev": "deno run --watch --allow-net --allow-env main.ts",
    "test": "deno test --allow-net --allow-env"
  },
  "imports": {
    "@cascadeflow/core": "npm:@cascadeflow/core@^1.0.0"
  },
  "compilerOptions": {
    "strict": true,
    "lib": ["deno.window"]
  }
}
`);

console.log('Then use with:');
console.log('   deno task start    # Run production');
console.log('   deno task dev      # Development with auto-reload');
console.log('   deno task test     # Run tests\n');

// ============================================================================
// Summary
// ============================================================================

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('📋 Deno Integration Summary');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

console.log('✅ Deno Advantages:');
console.log('   • No package.json or node_modules');
console.log('   • Native TypeScript support (no compilation)');
console.log('   • Secure by default (permission model)');
console.log('   • Web-standard APIs');
console.log('   • Built-in testing');
console.log('   • Edge deployment with Deno Deploy');
console.log('');

console.log('🎯 Key Differences from Node.js:');
console.log('   • Import from "npm:@cascadeflow/core" (not just "@cascadeflow/core")');
console.log('   • Use Deno.env instead of process.env');
console.log('   • Explicit permissions required');
console.log('   • Use Deno.serve() instead of Express/http');
console.log('   • deno.json instead of package.json');
console.log('');

console.log('🚀 Quick Start:');
console.log('   1. Create script: echo "import { CascadeAgent } from \'npm:@cascadeflow/core\';" > app.ts');
console.log('   2. Set API key: export OPENAI_API_KEY=your_key');
console.log('   3. Run: deno run --allow-net --allow-env app.ts');
console.log('');

console.log('📚 Resources:');
console.log('   • Deno Manual: https://deno.land/manual');
console.log('   • Deno Deploy: https://deno.com/deploy');
console.log('   • Deno Standard Library: https://deno.land/std');
console.log('');

console.log('✨ cascadeflow works seamlessly with Deno!');
console.log('   Enjoy TypeScript-first, secure-by-default development.\n');
