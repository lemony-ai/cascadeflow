/**
 * Tool Execution Example
 *
 * Demonstrates tool calling capabilities with cascadeflow:
 * - Defining custom tools
 * - Tool execution with cascade
 * - Multi-step tool workflows
 * - Error handling in tool calls
 * - Tool result validation
 *
 * Usage: npx tsx examples/nodejs/tool-execution.ts
 */

import { CascadeAgent, type Message, type Tool } from '@cascadeflow/core';
import { safeCalculateExpression } from './safe-math';

// ============================================================================
// Tool Definitions
// ============================================================================

/**
 * Weather tool - simulates weather API
 */
const weatherTool = {
  type: 'function' as const,
  function: {
    name: 'get_weather',
    description: 'Get current weather for a location',
    parameters: {
      type: 'object',
      properties: {
        location: {
          type: 'string',
          description: 'City name or coordinates'
        },
        units: {
          type: 'string',
          enum: ['celsius', 'fahrenheit'],
          description: 'Temperature units'
        }
      },
      required: ['location']
    }
  }
};

/**
 * Calculator tool - performs mathematical operations
 */
const calculatorTool = {
  type: 'function' as const,
  function: {
    name: 'calculate',
    description: 'Perform mathematical calculations',
    parameters: {
      type: 'object',
      properties: {
        expression: {
          type: 'string',
          description: 'Mathematical expression to evaluate (e.g., "2 + 2", "sqrt(16)")'
        }
      },
      required: ['expression']
    }
  }
};

/**
 * Search tool - simulates database search
 */
const searchTool = {
  type: 'function' as const,
  function: {
    name: 'search_database',
    description: 'Search a product database',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query'
        },
        category: {
          type: 'string',
          enum: ['electronics', 'books', 'clothing', 'all'],
          description: 'Product category filter'
        },
        max_results: {
          type: 'number',
          description: 'Maximum number of results to return'
        }
      },
      required: ['query']
    }
  }
};

/**
 * Email tool - simulates sending emails
 */
const emailTool = {
  type: 'function' as const,
  function: {
    name: 'send_email',
    description: 'Send an email to a recipient',
    parameters: {
      type: 'object',
      properties: {
        to: {
          type: 'string',
          description: 'Recipient email address'
        },
        subject: {
          type: 'string',
          description: 'Email subject line'
        },
        body: {
          type: 'string',
          description: 'Email body content'
        }
      },
      required: ['to', 'subject', 'body']
    }
  }
};

// ============================================================================
// Tool Execution Functions
// ============================================================================

/**
 * Execute weather tool
 */
function executeWeatherTool(args: { location: string; units?: string }): string {
  const { location, units = 'celsius' } = args;

  // Simulate weather data
  const temp = units === 'celsius' ? 22 : 72;
  const conditions = ['sunny', 'cloudy', 'rainy', 'partly cloudy'];
  const condition = conditions[Math.floor(Math.random() * conditions.length)];

  return JSON.stringify({
    location,
    temperature: temp,
    units,
    condition,
    humidity: 65,
    wind_speed: 12
  });
}

/**
 * Execute calculator tool
 */
function executeCalculatorTool(args: { expression: string }): string {
  try {
    const result = safeCalculateExpression(args.expression);
    return JSON.stringify({
      expression: args.expression,
      result,
      unit: typeof result === 'number' ? 'number' : 'unknown'
    });
  } catch (error) {
    return JSON.stringify({
      error: 'Calculation failed',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
}

/**
 * Execute search tool
 */
function executeSearchTool(args: { query: string; category?: string; max_results?: number }): string {
  const { query, category = 'all', max_results = 5 } = args;

  // Simulate search results
  const products = [
    { id: 1, name: 'Laptop Pro', category: 'electronics', price: 1299 },
    { id: 2, name: 'TypeScript Book', category: 'books', price: 39 },
    { id: 3, name: 'Wireless Mouse', category: 'electronics', price: 29 },
    { id: 4, name: 'Cotton T-Shirt', category: 'clothing', price: 19 },
    { id: 5, name: 'Programming Guide', category: 'books', price: 49 },
  ];

  let results = products;
  if (category !== 'all') {
    results = results.filter(p => p.category === category);
  }

  // Simple search filter
  results = results.filter(p =>
    p.name.toLowerCase().includes(query.toLowerCase())
  );

  return JSON.stringify({
    query,
    category,
    total_results: results.length,
    results: results.slice(0, max_results)
  });
}

/**
 * Execute email tool
 */
function executeEmailTool(args: { to: string; subject: string; body: string }): string {
  // Simulate email sending
  return JSON.stringify({
    status: 'sent',
    to: args.to,
    subject: args.subject,
    timestamp: new Date().toISOString(),
    message_id: `msg_${Math.random().toString(36).substr(2, 9)}`
  });
}

/**
 * Tool execution dispatcher
 */
function executeToolCall(toolName: string, args: any): string {
  switch (toolName) {
    case 'get_weather':
      return executeWeatherTool(args);
    case 'calculate':
      return executeCalculatorTool(args);
    case 'search_database':
      return executeSearchTool(args);
    case 'send_email':
      return executeEmailTool(args);
    default:
      return JSON.stringify({ error: 'Unknown tool', tool: toolName });
  }
}

// ============================================================================
// Example Scenarios
// ============================================================================

type NormalizedToolCall = {
  id: string;
  name: string;
  arguments: Record<string, any>;
};

type ExecutedToolCall = {
  call: NormalizedToolCall;
  result: string;
};

function parseArgs(raw: string): Record<string, any> {
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

function normalizeToolCall(raw: any, index: number): NormalizedToolCall | null {
  if (!raw || typeof raw !== 'object') return null;
  const fn = raw.function && typeof raw.function === 'object' ? raw.function : {};
  const name = fn.name || raw.name;
  if (!name) return null;
  const args = typeof fn.arguments === 'string' ? parseArgs(fn.arguments) : {};
  return {
    id: raw.id || `call_${index}`,
    name,
    arguments: args,
  };
}

async function runToolConversation(params: {
  agent: CascadeAgent;
  query: string;
  tools: Tool[];
  maxTurns?: number;
}) {
  const { agent, query, tools, maxTurns = 7 } = params;
  const messages: Message[] = [{ role: 'user', content: query }];
  const executed: ExecutedToolCall[] = [];
  let totalCost = 0;
  let modelUsed = '';
  let finalResponse = '';

  for (let turn = 0; turn < maxTurns; turn += 1) {
    const result = await agent.run(messages, {
      tools,
      maxTokens: 250,
      temperature: 0.4,
      maxSteps: maxTurns,
    });

    totalCost += result.totalCost || 0;
    modelUsed = result.modelUsed || modelUsed;
    const content = (result.content || '').trim();
    const rawToolCalls = Array.isArray(result.toolCalls) ? result.toolCalls : [];
    const normalized = rawToolCalls
      .map((raw, i) => normalizeToolCall(raw, executed.length + i))
      .filter((v): v is NormalizedToolCall => Boolean(v));

    if (normalized.length > 0) {
      messages.push({
        role: 'assistant',
        content: content || '',
        tool_calls: normalized.map(call => ({
          id: call.id,
          type: 'function' as const,
          function: {
            name: call.name,
            arguments: JSON.stringify(call.arguments),
          },
        })),
      });

      for (const toolCall of normalized) {
        const toolResult = executeToolCall(toolCall.name, toolCall.arguments);
        executed.push({ call: toolCall, result: toolResult });
        messages.push({
          role: 'tool',
          tool_call_id: toolCall.id,
          name: toolCall.name,
          content: toolResult,
        });
      }
      continue;
    }

    if (content) {
      finalResponse = content;
      break;
    }
  }

  if (!finalResponse) {
    const fallback = await agent.run(messages, {
      tools,
      maxTokens: 200,
      temperature: 0.2,
      maxSteps: 1,
    });
    totalCost += fallback.totalCost || 0;
    modelUsed = fallback.modelUsed || modelUsed;
    finalResponse = (fallback.content || '').trim();
  }

  return {
    modelUsed,
    totalCost,
    finalResponse,
    turns: messages.length,
    executed,
  };
}

async function main() {
  console.log('\n╔═══════════════════════════════════════════════════════════════╗');
  console.log('║         cascadeflow - Tool Execution Examples                ║');
  console.log('╚═══════════════════════════════════════════════════════════════╝\n');

  if (!process.env.OPENAI_API_KEY) {
    console.log('⚠️  OPENAI_API_KEY not found in environment');
    console.log('   Set it in .env file or export OPENAI_API_KEY=your_key');
    console.log('   This example requires OpenAI for tool calling support\n');
    return;
  }

  const agent = new CascadeAgent({
    models: [
      { name: 'gpt-4o-mini', provider: 'openai', cost: 0.00015, supportsTools: true },
      { name: 'gpt-4o', provider: 'openai', cost: 0.00625, supportsTools: true },
    ],
    quality: {
      threshold: 0.7,
    },
  });

  console.log('🔧 Tool calling capabilities:');
  console.log('   • Weather lookups');
  console.log('   • Mathematical calculations');
  console.log('   • Database searches');
  console.log('   • Email sending (simulated)');
  console.log('');

  const scenarios: Array<{ title: string; query: string; tools: Tool[] }> = [
    {
      title: 'Example 1: Single Tool Call (Weather)',
      query: "What's the weather like in San Francisco?",
      tools: [weatherTool],
    },
    {
      title: 'Example 2: Mathematical Calculations',
      query: 'Calculate the square root of 144 and then multiply it by 5',
      tools: [calculatorTool],
    },
    {
      title: 'Example 3: Database Search',
      query: 'Search for electronics products',
      tools: [searchTool],
    },
    {
      title: 'Example 4: Multi-Tool Workflow',
      query: 'Check the weather in New York and send me an email about it',
      tools: [weatherTool, emailTool],
    },
    {
      title: 'Example 5: Error Handling',
      query: 'Calculate the result of dividing by zero: 10 / 0',
      tools: [calculatorTool],
    },
  ];

  let aggregateCost = 0;
  let aggregateCalls = 0;
  let nonEmptyResponses = 0;

  for (const scenario of scenarios) {
    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log(scenario.title);
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

    try {
      const result = await runToolConversation({
        agent,
        query: scenario.query,
        tools: scenario.tools,
      });

      aggregateCost += result.totalCost;
      aggregateCalls += result.executed.length;
      if (result.finalResponse) nonEmptyResponses += 1;

      console.log(`Query: ${scenario.query}`);
      console.log(`Model: ${result.modelUsed}`);
      console.log(`Turns: ${result.turns}`);
      console.log(`🔧 Tool Calls Made: ${result.executed.length}`);

      for (const [index, executed] of result.executed.entries()) {
        console.log(`\n   Call ${index + 1}:`);
        console.log(`   Tool: ${executed.call.name}`);
        console.log(`   Arguments: ${JSON.stringify(executed.call.arguments)}`);
        console.log(`   Result: ${executed.result}`);
      }

      console.log(`\n💬 Response: ${result.finalResponse}`);
      console.log(`💰 Cost: $${result.totalCost.toFixed(6)}`);
    } catch (error) {
      console.error('Error:', error instanceof Error ? error.message : error);
    }
  }

  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('📊 Tool Calling Summary');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  console.log('✅ Demonstrated Features:');
  console.log('   • Single tool calls');
  console.log('   • Multiple sequential tool calls');
  console.log('   • Multi-tool workflows');
  console.log('   • Error handling');
  console.log('   • Closed tool loop continuation');
  console.log('');
  console.log('🎯 Validation Outcomes:');
  console.log(`   • Total tool calls executed: ${aggregateCalls}`);
  console.log(`   • Non-empty final responses: ${nonEmptyResponses}/${scenarios.length}`);
  console.log(`   • Total demo cost: $${aggregateCost.toFixed(6)}`);
  console.log('');
  console.log('📚 Learn More:');
  console.log('   • See streaming-tools.ts for streaming with tools');
  console.log('   • See multi-step-cascade.ts for complex workflows');
  console.log('');
}

// Run examples
main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
