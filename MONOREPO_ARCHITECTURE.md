# CascadeFlow Monorepo Architecture

**Date**: October 22, 2025
**Status**: Proposed Architecture
**Inspiration**: mcp-use, Vercel, Nx best practices

---

## 🎯 Goals

1. **Scalable**: Support multiple languages (Python, TypeScript, Rust)
2. **State-of-the-art**: Modern monorepo tooling and patterns
3. **Best DX**: Easy to navigate, develop, and contribute
4. **Minimal Disruption**: Don't break existing Python users
5. **Clear Separation**: Libraries vs Integrations vs Examples

---

## 📁 Proposed Structure

```
cascadeflow/                                   # Root monorepo
│
├── libraries/                                 # Core libraries by language
│   │
│   ├── python/                               # Python core library
│   │   ├── cascadeflow/                      # Main package (MOVED from root)
│   │   │   ├── core/
│   │   │   ├── providers/
│   │   │   ├── quality/
│   │   │   ├── routing/
│   │   │   ├── telemetry/
│   │   │   ├── tools/
│   │   │   └── ...
│   │   ├── tests/
│   │   ├── examples/
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   └── CHANGELOG.md
│   │
│   └── typescript/                           # TypeScript/JavaScript ecosystem
│       ├── package.json                      # Workspace root
│       ├── pnpm-workspace.yaml               # pnpm workspaces config
│       ├── turbo.json                        # Turborepo config
│       │
│       └── packages/
│           │
│           ├── core/                         # @cascadeflow/core
│           │   ├── src/
│           │   │   ├── agent.ts
│           │   │   ├── config.ts
│           │   │   ├── providers/
│           │   │   │   ├── base.ts
│           │   │   │   ├── openai.ts
│           │   │   │   ├── anthropic.ts
│           │   │   │   ├── groq.ts
│           │   │   │   └── ...
│           │   │   ├── quality/
│           │   │   │   ├── confidence.ts
│           │   │   │   └── validator.ts
│           │   │   ├── routing/
│           │   │   ├── telemetry/
│           │   │   │   ├── tracker.ts
│           │   │   │   └── metrics.ts
│           │   │   └── index.ts
│           │   ├── tests/
│           │   ├── package.json
│           │   ├── tsconfig.json
│           │   ├── README.md
│           │   └── CHANGELOG.md
│           │
│           └── types/                        # @cascadeflow/types
│               ├── src/
│               │   ├── agent.ts              # Agent types
│               │   ├── provider.ts           # Provider types
│               │   ├── result.ts             # Result types
│               │   └── index.ts
│               ├── package.json
│               └── tsconfig.json
│
├── integrations/                             # Third-party integrations
│   │
│   ├── n8n/                                  # n8n-nodes-cascadeflow
│   │   ├── nodes/
│   │   │   └── CascadeFlow/
│   │   │       ├── CascadeFlow.node.ts
│   │   │       ├── CascadeFlow.node.json
│   │   │       └── descriptions/
│   │   ├── credentials/
│   │   │   └── CascadeFlowApi.credentials.ts
│   │   ├── icons/
│   │   ├── tests/
│   │   ├── package.json
│   │   ├── README.md
│   │   └── docs/
│   │
│   ├── langchain-python/                     # cascadeflow-langchain (Python)
│   │   ├── cascadeflow_langchain/
│   │   │   ├── __init__.py
│   │   │   ├── llm.py
│   │   │   ├── chat_model.py
│   │   │   └── callbacks.py
│   │   ├── tests/
│   │   ├── examples/
│   │   ├── pyproject.toml
│   │   └── README.md
│   │
│   ├── langchain-js/                         # @cascadeflow/langchain (TypeScript)
│   │   ├── src/
│   │   │   ├── llm.ts
│   │   │   ├── chat-model.ts
│   │   │   └── index.ts
│   │   ├── package.json
│   │   └── README.md
│   │
│   ├── llamaindex/                           # cascadeflow-llamaindex (Python)
│   │   └── ...
│   │
│   ├── vercel-ai-sdk/                        # @cascadeflow/ai (TypeScript)
│   │   └── ...
│   │
│   └── haystack/                             # cascadeflow-haystack (Python)
│       └── ...
│
├── examples/                                  # Example applications
│   ├── python/
│   │   ├── basic_usage.py
│   │   ├── fastapi_integration.py
│   │   ├── edge_device.py
│   │   └── ...
│   ├── typescript/
│   │   ├── nextjs-app/
│   │   ├── cloudflare-worker/
│   │   └── basic-usage.ts
│   └── integrations/
│       ├── n8n-workflows/
│       ├── langchain-examples/
│       └── ...
│
├── docs/                                      # Documentation
│   ├── guides/
│   ├── api/
│   │   ├── python/
│   │   └── typescript/
│   ├── integrations/
│   └── README.md
│
├── tools/                                     # Development tools
│   ├── scripts/
│   │   ├── build-all.sh
│   │   ├── test-all.sh
│   │   └── publish.sh
│   └── configs/
│
├── .github/                                   # GitHub workflows
│   └── workflows/
│       ├── test-python.yml
│       ├── test-typescript.yml
│       ├── publish-python.yml
│       ├── publish-typescript.yml
│       └── publish-integrations.yml
│
├── README.md                                  # Root README
├── CONTRIBUTING.md
├── LICENSE
├── STRUCTURE.md
└── MONOREPO_ARCHITECTURE.md                  # This file
```

---

## 🔑 Key Architectural Decisions

### 1. **Libraries vs Integrations Separation**

| Directory | Purpose | Examples |
|-----------|---------|----------|
| `libraries/` | Core CascadeFlow implementations in different languages | Python, TypeScript, Rust |
| `integrations/` | Third-party platform integrations that USE the libraries | n8n, LangChain, LlamaIndex |

**Why this works:**
- Clear dependency graph: Integrations depend on libraries
- Libraries are self-contained, versioned independently
- Easy to add new languages (libraries/rust/) or integrations (integrations/autogen/)
- Mirrors successful projects (mcp-use, Vercel, Nx)

---

### 2. **Language-Specific Organization**

Each language has its own directory under `libraries/`:

```
libraries/
  python/          # Python ecosystem (pip, pytest, black)
  typescript/      # JS/TS ecosystem (npm/pnpm, vitest, prettier)
  rust/            # Future: Rust ecosystem (cargo, clippy)
```

**Benefits:**
- Language-specific tooling doesn't conflict
- Different build/test/publish workflows
- Teams can specialize by language
- Clear ownership boundaries

---

### 3. **TypeScript Monorepo with Workspaces**

Using **pnpm workspaces + Turborepo** (state-of-the-art):

```yaml
# libraries/typescript/pnpm-workspace.yaml
packages:
  - 'packages/*'
```

```json
// libraries/typescript/turbo.json
{
  "pipeline": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**"]
    },
    "test": {
      "dependsOn": ["build"]
    }
  }
}
```

**Why pnpm + Turborepo?**
- ✅ **pnpm**: Fastest package manager, disk-efficient, used by Vercel
- ✅ **Turborepo**: Intelligent caching, parallel builds, remote caching
- ✅ **Industry standard**: Vercel, Nx, Prisma all use this stack
- ✅ **Best DX**: Fast installs, fast builds, minimal config

---

### 4. **Shared TypeScript Packages**

```
libraries/typescript/packages/
  core/           # @cascadeflow/core - Main library
  types/          # @cascadeflow/types - Shared types
```

Then integrations import:
```typescript
// integrations/n8n/nodes/CascadeFlow.node.ts
import { CascadeAgent, ModelConfig } from '@cascadeflow/core';
import type { CascadeResult } from '@cascadeflow/types';
```

**Benefits:**
- Type safety across all integrations
- Shared logic (metrics, cost tracking)
- No code duplication
- Easy to maintain

---

### 5. **Independent Versioning**

Each package has its own version:

```
libraries/python/              → cascadeflow==0.2.0 (PyPI)
libraries/typescript/core/     → @cascadeflow/core@1.0.0 (npm)
integrations/n8n/              → n8n-nodes-cascadeflow@1.0.0 (npm)
integrations/langchain-python/ → cascadeflow-langchain@0.1.0 (PyPI)
```

**Why independent versioning?**
- Libraries evolve at different rates
- Breaking changes in one don't block others
- Clear semver for each package
- Users can choose versions per integration

---

## 🚀 Migration Plan (Minimal Disruption)

### Phase 1: Add Structure (Don't Move Existing)

**Keep current Python package at root** (don't break existing users):

```diff
cascadeflow/                    # Existing Python package (STAYS)
├── core/
├── providers/
└── ...
+ libraries/                     # NEW
+   └── typescript/              # NEW TypeScript library
+ integrations/                  # NEW
+   └── n8n/                     # NEW n8n integration
```

**Rationale:**
- Existing Python users see NO changes
- `pip install cascadeflow` still works
- No broken imports
- We add NEW structure alongside

---

### Phase 2: Gradual Python Migration (Optional)

**Later**, when ready to fully adopt monorepo:

1. **Move Python package:**
   ```bash
   git mv cascadeflow/ libraries/python/cascadeflow/
   git mv tests/ libraries/python/tests/
   git mv examples/ libraries/python/examples/
   git mv pyproject.toml libraries/python/pyproject.toml
   ```

2. **Update root README:**
   - Point to libraries/python/README.md for Python docs
   - Add overview of monorepo structure

3. **Add root package.json** (for entire monorepo):
   ```json
   {
     "name": "cascadeflow-monorepo",
     "private": true,
     "workspaces": [
       "libraries/typescript/packages/*",
       "integrations/n8n"
     ]
   }
   ```

4. **Update CI/CD:**
   - Separate workflows for Python vs TypeScript vs integrations
   - Publish to PyPI from `libraries/python/`
   - Publish to npm from `libraries/typescript/packages/*/`

---

## 🛠️ Tooling Stack

### Python (Existing)
- **Package Manager**: pip
- **Build**: setuptools
- **Testing**: pytest
- **Linting**: ruff, black
- **Type Checking**: mypy

### TypeScript (New)
- **Package Manager**: pnpm (fastest)
- **Build Tool**: Turborepo (caching + parallelization)
- **Testing**: Vitest (fast, modern)
- **Linting**: ESLint + Prettier
- **Type Checking**: TypeScript strict mode
- **Bundler**: tsup (fast, zero-config)

### Monorepo Tools
- **pnpm workspaces**: Manage TS packages
- **Turborepo**: Build orchestration
- **Changesets**: Version management + changelogs
- **GitHub Actions**: CI/CD for all packages

---

## 📦 Package Naming Convention

### Python Packages (PyPI)

| Package | Name | Purpose |
|---------|------|---------|
| Core library | `cascadeflow` | Main Python package |
| LangChain integration | `cascadeflow-langchain` | LangChain wrapper |
| LlamaIndex integration | `cascadeflow-llamaindex` | LlamaIndex wrapper |

### TypeScript Packages (npm)

| Package | Name | Purpose |
|---------|------|---------|
| Core library | `@cascadeflow/core` | Main TypeScript package |
| Shared types | `@cascadeflow/types` | TypeScript types |
| LangChain integration | `@cascadeflow/langchain` | LangChain.js wrapper |
| Vercel AI SDK | `@cascadeflow/ai` | Vercel AI SDK integration |

### n8n Packages (npm)

| Package | Name | Purpose |
|---------|------|---------|
| n8n node | `n8n-nodes-cascadeflow` | n8n community node |

**Naming Rules:**
- Python: `cascadeflow-*` (PyPI convention)
- TypeScript: `@cascadeflow/*` (npm scoped packages)
- n8n: `n8n-nodes-*` (n8n requirement)

---

## 🔄 Dependency Graph

```
┌─────────────────────────────────────────────────┐
│                  Applications                   │
│  (User's Next.js app, n8n workflow, etc.)      │
└─────────────────────┬───────────────────────────┘
                      │
                      │ uses
                      ▼
┌─────────────────────────────────────────────────┐
│                  Integrations                   │
│  - n8n-nodes-cascadeflow                       │
│  - @cascadeflow/langchain                      │
│  - cascadeflow-langchain (Python)              │
└─────────────────────┬───────────────────────────┘
                      │
                      │ depends on
                      ▼
┌─────────────────────────────────────────────────┐
│               Core Libraries                    │
│  - @cascadeflow/core (TypeScript)              │
│  - cascadeflow (Python)                        │
└─────────────────────────────────────────────────┘
```

**Key principle**: Dependencies flow DOWN, never UP
- Applications depend on integrations
- Integrations depend on libraries
- Libraries are self-contained

---

## 🎨 Developer Experience

### Cloning and Setup

```bash
# Clone repository
git clone https://github.com/lemony-ai/cascadeflow.git
cd cascadeflow

# Install Python dependencies
cd libraries/python
pip install -e ".[dev]"
pytest

# Install TypeScript dependencies
cd ../typescript
pnpm install
pnpm build
pnpm test

# Work on n8n integration
cd ../../integrations/n8n
pnpm dev
```

### Development Workflow

**For Python developers:**
```bash
cd libraries/python
# Work on Python code
pytest tests/
```

**For TypeScript developers:**
```bash
cd libraries/typescript
# Build all packages
pnpm build

# Run all tests
pnpm test

# Watch mode
pnpm dev
```

**For integration developers:**
```bash
cd integrations/n8n
# Automatically rebuilds when @cascadeflow/core changes
pnpm dev
```

### Publishing Workflow

**Python:**
```bash
cd libraries/python
python -m build
twine upload dist/*
```

**TypeScript:**
```bash
cd libraries/typescript
pnpm changeset version  # Updates versions
pnpm build
pnpm publish -r         # Publishes all changed packages
```

**n8n:**
```bash
cd integrations/n8n
pnpm version 1.0.0
pnpm publish
```

---

## 📊 Comparison: Old vs New Structure

### Before (Current)

```
cascadeflow/
├── cascadeflow/          # Python package
├── examples/
├── tests/
├── docs/
└── pyproject.toml
```

**Issues:**
- ❌ No clear place for TypeScript library
- ❌ No separation of libraries vs integrations
- ❌ Hard to add new languages
- ❌ Mixing concerns (Python-specific at root)

---

### After (Proposed)

```
cascadeflow/
├── libraries/
│   ├── python/
│   └── typescript/
├── integrations/
│   ├── n8n/
│   ├── langchain-python/
│   └── langchain-js/
├── examples/
├── docs/
└── tools/
```

**Benefits:**
- ✅ Clear separation: libraries vs integrations
- ✅ Easy to add languages (libraries/rust/)
- ✅ Easy to add integrations (integrations/autogen/)
- ✅ Modern monorepo best practices
- ✅ Scalable to 10+ packages
- ✅ Industry-standard structure

---

## 🎯 Immediate Next Steps

### Step 1: Create Structure (No Migration Yet)

```bash
# Add new directories alongside existing code
mkdir -p libraries/typescript/packages/{core,types}
mkdir -p integrations/{n8n,langchain-python,langchain-js}
mkdir -p tools/scripts
```

### Step 2: Initialize TypeScript Workspace

```bash
cd libraries/typescript
pnpm init
pnpm add -D -w turbo
# Create pnpm-workspace.yaml and turbo.json
```

### Step 3: Create @cascadeflow/core Package

```bash
cd packages/core
pnpm init
# Set name to "@cascadeflow/core"
# Add TypeScript, build tools
```

### Step 4: Start Building

```bash
# Implement TypeScript library (feature parity with Python)
# Test locally
# Publish to npm
```

---

## 🎓 References

**Similar projects using this structure:**
- **mcp-use**: https://github.com/mcp-use/mcp-use
- **Vercel**: Turborepo, pnpm workspaces
- **Nx**: Monorepo tooling
- **Prisma**: Python + TypeScript libraries

**Tooling documentation:**
- **pnpm workspaces**: https://pnpm.io/workspaces
- **Turborepo**: https://turbo.build/repo/docs
- **Changesets**: https://github.com/changesets/changesets

---

## ✅ Decision Matrix

| Aspect | Option 1: Flat Structure | Option 2: libraries/ Structure | **Decision** |
|--------|-------------------------|-------------------------------|-------------|
| **Scalability** | ❌ Hard to add languages | ✅ Easy to add languages | ✅ **libraries/** |
| **Clarity** | ❌ Mixed concerns | ✅ Clear separation | ✅ **libraries/** |
| **DX** | ⚠️ Confusing for new contributors | ✅ Intuitive structure | ✅ **libraries/** |
| **Industry Standard** | ❌ Not common | ✅ Used by Vercel, Nx, mcp-use | ✅ **libraries/** |
| **Migration Effort** | ✅ No migration | ⚠️ Requires migration | ✅ **Gradual migration** |

**Final Decision: Use `libraries/` + `integrations/` structure**

---

## 📝 Summary

**Architecture:**
```
cascadeflow/
├── libraries/        # Core implementations by language
├── integrations/     # Third-party integrations
├── examples/         # Example applications
├── docs/            # Documentation
└── tools/           # Build scripts
```

**Benefits:**
- 🎯 Scalable to unlimited languages and integrations
- 🚀 State-of-the-art monorepo tooling (pnpm + Turborepo)
- ✨ Best developer experience
- 🏗️ Industry-standard structure
- 📦 Independent versioning per package

**Next Actions:**
1. ✅ Save current work to git
2. ✅ Create `libraries/` and `integrations/` directories
3. ✅ Initialize TypeScript workspace
4. ✅ Build @cascadeflow/core
5. ✅ Build n8n integration

Ready to execute! 🚀
