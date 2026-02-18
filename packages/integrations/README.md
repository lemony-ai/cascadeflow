# cascadeflow Integrations

This directory contains official integrations for cascadeflow with popular platforms, frameworks, and tools.

## Available Integrations

### 🔌 Workflow Automation

#### [n8n](./n8n/) - `@cascadeflow/n8n-nodes-cascadeflow`
No-code workflow automation with cascadeflow's intelligent model cascading. Two nodes:

- **CascadeFlow (Model)** — Language Model sub-node for Chain/LLM nodes
- **CascadeFlow Agent** — Standalone agent with tool calling, memory, and multi-step reasoning

Install: Search "cascadeflow" in n8n Community Nodes | **[Documentation](./n8n/README.md)**

---

### ⚡️ Vercel AI SDK

#### [Vercel AI SDK](./vercel-ai/) - `@cascadeflow/vercel-ai`
Use cascadeflow as a drop-in backend for Vercel AI SDK UI hooks like `useChat` (Next.js App Router), and access the Vercel AI SDK provider ecosystem.

- **Install:** `pnpm add @cascadeflow/core @cascadeflow/vercel-ai ai @ai-sdk/react`
- **Features:** `createChatHandler(...)` (data stream + UI message stream), tool-call streaming, server-side tool loops (`toolExecutor` / `toolHandlers`)
- **Use Cases:** Quickly add cascadeflow routing to existing `useChat` apps
- **[Documentation](./vercel-ai/README.md)**

---

### 💳 Billing & Metering

#### [Paygentic](./paygentic/) - `@cascadeflow/paygentic`
Optional Paygentic integration for usage metering and billing lifecycle helpers.

- **Install:** `pnpm add @cascadeflow/core @cascadeflow/paygentic`
- **Features:** Usage event reporting, deterministic idempotency keys, customer/subscription helper APIs
- **Use Cases:** SaaS billing, usage-based pricing, cost attribution per customer
- **[Documentation](./paygentic/README.md)**

---

## Adding a New Integration

We welcome community contributions! Here's how to add a new integration:

### 1. Choose Your Integration Type

**Framework Integration** (`@cascadeflow/{framework}`)
- For AI frameworks like LangChain, LlamaIndex
- Wraps cascadeflow as a native framework component
- Example: `@cascadeflow/langchain`

**Platform Integration** (`cascadeflow-{platform}`)
- For platforms/tools like VSCode, Chrome
- Standalone application using cascadeflow
- Example: `cascadeflow-vscode`

**Workflow Integration** (special naming)
- For workflow tools like n8n, Zapier
- Follows platform conventions
- Example: `@cascadeflow/n8n-nodes-cascadeflow`

### 2. Create Package Structure

```bash
# Create directory
mkdir packages/integrations/{name}
cd packages/integrations/{name}

# Initialize package
pnpm init

# Add dependencies
pnpm add @cascadeflow/core
```

### 3. Package.json Template

```json
{
  "name": "@cascadeflow/{name}",
  "version": "0.1.0",
  "description": "cascadeflow integration for {platform}",
  "keywords": ["cascadeflow", "{platform}", "ai", "llm"],
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/lemony-ai/cascadeflow.git",
    "directory": "packages/integrations/{name}"
  },
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "files": ["dist"],
  "scripts": {
    "build": "tsc",
    "test": "vitest",
    "lint": "eslint src"
  },
  "dependencies": {
    "@cascadeflow/core": "workspace:*"
  },
  "peerDependencies": {
    "{platform-package}": "*"
  }
}
```

### 4. Implement Integration

Create your integration following the platform's best practices:

```typescript
// src/index.ts
import { CascadeAgent } from '@cascadeflow/core';
import { PlatformBaseClass } from '{platform}';

export class CascadePlatformIntegration extends PlatformBaseClass {
  private agent: CascadeAgent;

  constructor(config: Config) {
    super();
    this.agent = new CascadeAgent(config.models);
  }

  // Implement platform-specific methods
  async method(): Promise<Response> {
    return await this.agent.run(/* ... */);
  }
}
```

### 5. Add Tests

```typescript
// __tests__/integration.test.ts
import { describe, it, expect } from 'vitest';
import { CascadePlatformIntegration } from '../src';

describe('CascadePlatformIntegration', () => {
  it('should integrate with platform', async () => {
    const integration = new CascadePlatformIntegration({/* ... */});
    const result = await integration.method();
    expect(result).toBeDefined();
  });
});
```

### 6. Create Documentation

Create `README.md` with:
- Installation instructions
- Quick start guide
- API reference
- Examples
- Troubleshooting

### 7. Submit Pull Request

1. Test your integration thoroughly
2. Add documentation
3. Update this README with your integration
4. Submit PR with description of the integration

---

## Integration Guidelines

### Code Quality
- ✅ TypeScript with strict mode
- ✅ 80%+ test coverage
- ✅ ESLint + Prettier
- ✅ Type definitions included

### Documentation
- ✅ Comprehensive README
- ✅ Code examples
- ✅ API reference
- ✅ Troubleshooting section

### Compatibility
- ✅ Works with latest @cascadeflow/core
- ✅ Follows semantic versioning
- ✅ Peer dependencies properly declared
- ✅ Browser and Node.js compatibility (where applicable)

### Maintenance
- ✅ Active maintenance commitment
- ✅ Respond to issues promptly
- ✅ Keep dependencies updated
- ✅ Follow security best practices

---

## Publishing

Integrations are published independently to npm:

```bash
# Build
pnpm --filter {package-name} build

# Test
pnpm --filter {package-name} test

# Publish
pnpm --filter {package-name} publish
```

---

## Support

- 💬 [Discord Community](https://discord.gg/lemony-ai)
- 📖 [GitHub Discussions](https://github.com/lemony-ai/cascadeflow/discussions)
- 🐛 [Report Issues](https://github.com/lemony-ai/cascadeflow/issues)

---

## License

All integrations are MIT licensed unless otherwise specified in their individual README.
