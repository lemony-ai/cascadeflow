# TypeScript Package Structure - Scalable Design

## Current Structure (Not Scalable)

```
packages/
├── core/                          # Main TypeScript library
└── n8n-nodes-cascadeflow/         # n8n integration (not organized)
```

**Problems:**
- Flat structure doesn't scale for multiple integrations
- No clear separation between core library and integrations
- Future integrations will clutter the packages directory

---

## Proposed Scalable Structure

```
packages/
├── core/                          # @cascadeflow/core - Main library
│   ├── src/
│   ├── examples/
│   ├── __tests__/
│   └── package.json
│
└── integrations/                  # All third-party integrations
    ├── n8n/                       # n8n-nodes-cascadeflow
    │   ├── nodes/
    │   ├── credentials/
    │   └── package.json
    │
    ├── langchain/                 # @cascadeflow/langchain (future)
    │   ├── src/
    │   └── package.json
    │
    ├── llamaindex/                # @cascadeflow/llamaindex (future)
    │   ├── src/
    │   └── package.json
    │
    ├── vscode/                    # cascadeflow-vscode (future)
    │   ├── src/
    │   └── package.json
    │
    ├── chrome/                    # Chrome extension (future)
    │   ├── src/
    │   └── manifest.json
    │
    └── slack/                     # Slack bot (future)
        ├── src/
        └── package.json
```

---

## Benefits

### 1. **Scalability**
- Easy to add new integrations without cluttering
- Clear organization: core vs integrations
- Each integration is self-contained

### 2. **Developer Experience**
- Clear mental model: "integrations" directory = third-party
- Easy to find specific integrations
- Natural grouping for documentation

### 3. **Maintenance**
- Independent versioning per integration
- Each integration can have its own CI/CD
- Clear ownership boundaries

### 4. **Discovery**
- Users can easily browse available integrations
- Clear what's officially supported
- Easy to contribute new integrations

---

## Package Naming Convention

| Type | Naming | Example |
|------|--------|---------|
| Core Library | `@cascadeflow/core` | Main library |
| Framework Integration | `@cascadeflow/{framework}` | `@cascadeflow/langchain` |
| Platform Integration | `cascadeflow-{platform}` | `cascadeflow-vscode` |
| n8n Nodes | `n8n-nodes-{name}` | `n8n-nodes-cascadeflow` |

---

## Workspace Configuration

**Root `package.json`:**
```json
{
  "name": "cascadeflow-monorepo",
  "private": true,
  "workspaces": [
    "packages/core",
    "packages/integrations/*"
  ],
  "scripts": {
    "build": "pnpm -r --filter './packages/**' build",
    "test": "pnpm -r --filter './packages/**' test",
    "publish:core": "pnpm --filter @cascadeflow/core publish",
    "publish:n8n": "pnpm --filter n8n-nodes-cascadeflow publish"
  }
}
```

---

## Migration Plan

### Step 1: Create New Structure (10 minutes)
```bash
# Create integrations directory
mkdir -p packages/integrations

# Move n8n package
mv packages/n8n-nodes-cascadeflow packages/integrations/n8n

# Update workspace config
# Update package.json workspaces field
```

### Step 2: Update References (5 minutes)
- Update workspace paths in root `package.json`
- Update CI/CD workflows to new paths
- Update documentation references

### Step 3: Test & Verify (10 minutes)
```bash
# Verify workspace detection
pnpm install

# Build all packages
pnpm -r build

# Run tests
pnpm -r test
```

---

## Future Integration Examples

### LangChain Integration (`packages/integrations/langchain/`)
```typescript
// @cascadeflow/langchain
import { CascadeAgent } from '@cascadeflow/core';
import { BaseLanguageModel } from 'langchain/base_language';

export class CascadeLangChainModel extends BaseLanguageModel {
  constructor(agent: CascadeAgent) {
    // Wrap CascadeFlow as LangChain model
  }
}
```

### VSCode Extension (`packages/integrations/vscode/`)
```typescript
// cascadeflow-vscode
import * as vscode from 'vscode';
import { CascadeAgent } from '@cascadeflow/core';

export function activate(context: vscode.ExtensionContext) {
  // AI code completion using CascadeFlow
  // Cost-optimized AI suggestions
}
```

### LlamaIndex Integration (`packages/integrations/llamaindex/`)
```typescript
// @cascadeflow/llamaindex
import { CascadeAgent } from '@cascadeflow/core';
import { BaseLLM } from 'llamaindex';

export class CascadeLlamaIndexLLM extends BaseLLM {
  // LlamaIndex integration
}
```

---

## CI/CD Strategy

### Workflow Structure
```yaml
# .github/workflows/test-integrations.yml
name: Test Integrations

on: [pull_request]

jobs:
  test-n8n:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pnpm --filter n8n-nodes-cascadeflow test

  test-langchain:
    if: exists('packages/integrations/langchain')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pnpm --filter @cascadeflow/langchain test
```

### Publishing Strategy
```yaml
# .github/workflows/publish.yml
name: Publish Packages

on:
  push:
    branches: [main]

jobs:
  detect-changes:
    # Detect which packages changed

  publish-n8n:
    if: n8n package changed
    steps:
      - run: pnpm --filter n8n-nodes-cascadeflow publish

  publish-langchain:
    if: langchain package changed
    steps:
      - run: pnpm --filter @cascadeflow/langchain publish
```

---

## Documentation Structure

```
docs/
├── typescript/
│   ├── README.md
│   ├── core-api.md
│   └── integrations/
│       ├── n8n.md
│       ├── langchain.md
│       ├── llamaindex.md
│       └── vscode.md
└── python/
    └── ...
```

---

## README Structure

**Main README.md:**
```markdown
## 🔌 Integrations

CascadeFlow integrates with popular tools and frameworks:

### Workflow Automation
- **[n8n](./packages/integrations/n8n/)** - No-code workflow automation

### AI Frameworks
- **[LangChain](./packages/integrations/langchain/)** - Coming soon
- **[LlamaIndex](./packages/integrations/llamaindex/)** - Coming soon

### Developer Tools
- **[VSCode](./packages/integrations/vscode/)** - Coming soon

[View all integrations →](./packages/integrations/)
```

---

## Contribution Guidelines

Make it easy for community to add integrations:

**`packages/integrations/README.md`:**
```markdown
# CascadeFlow Integrations

## Adding a New Integration

1. Create directory: `packages/integrations/{name}/`
2. Add package.json with proper naming
3. Implement integration
4. Add tests
5. Update main README
6. Submit PR

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for details.
```

---

## Implementation Checklist

- [ ] Create `packages/integrations/` directory
- [ ] Move n8n package to `packages/integrations/n8n/`
- [ ] Update root `package.json` workspaces
- [ ] Update workflows to use new paths
- [ ] Test workspace resolution
- [ ] Update all documentation
- [ ] Create integrations README
- [ ] Update main README with integrations section

---

## Timeline

**Immediate (v0.1.0):**
- ✅ Restructure existing packages
- ✅ Update workflows
- ✅ Document structure

**Near-term (v0.2.0-0.3.0):**
- [ ] LangChain integration
- [ ] LlamaIndex integration

**Future (v0.4.0+):**
- [ ] VSCode extension
- [ ] Chrome extension
- [ ] Slack bot
- [ ] Discord bot

---

## Recommendation

**✅ IMPLEMENT NOW before 0.1.0 release**

Reasons:
1. Breaking change is acceptable pre-v1.0
2. Sets proper foundation for growth
3. Makes future integrations seamless
4. Professional structure from day 1
5. No migration pain later

**Estimated time:** 30 minutes to restructure + test
