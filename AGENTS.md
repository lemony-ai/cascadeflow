# AGENTS.md - cascadeflow Development Guidelines

> ⚠️ **BRANDING: Always use lowercase "cascadeflow"** — not CascadeFlow or CASCADEFLOW.

## Mandatory Development Workflow

**EVERY feature or bug fix MUST follow this flow:**

```
PLAN → PLAN REVIEW → BUILD → TEST → REVIEW → COMMIT
```

### 1. PLAN
- Create plan document or structured response
- Identify: scope, approach, files to modify
- List 6-10 action items
- Include test strategy
- **Do NOT start coding until plan is reviewed**

### 2. PLAN REVIEW
- Present plan to user
- Wait for explicit approval ("go", "approved", "lgtm")
- Revise if user has feedback
- **Do NOT proceed without approval**

### 3. BUILD
- Implement per approved plan
- **Commit early and often** — every logical unit of work
- **Push frequently** — visible progress on GitHub
- Small, focused changes
- Follow coding standards below
- Stay within scope

**Commit frequency rule:**
- After each file change that works → commit
- After each function/feature complete → commit + push
- Never have >30 mins of uncommitted work
- Use descriptive commit messages for traceability

### 4. TEST
- Run: `pytest` (Python) / `npm test` (TypeScript)
- Add tests for new functionality
- **All tests MUST pass**

### 5. REVIEW
- Self-review all changes
- Present diff summary
- Check: types, errors, docs, breaking changes

### 6. COMMIT
- Only after user approval
- Format: `feat:`, `fix:`, `docs:`, `chore:`
- **Never push to main**
- Create PR for Sascha to review

---

## Project Structure

```
cascadeflow/
├── cascadeflow/          # Python package
│   ├── agent.py          # Main orchestrator
│   ├── core/             # Cascade execution
│   ├── routing/          # Domain + tool routing
│   ├── quality/          # Quality validation (alignment scorer here!)
│   ├── providers/        # LLM providers
│   └── tools/            # Tool calling
├── packages/
│   └── core/             # TypeScript @cascadeflow/core
├── tests/                # Python tests
├── examples/             # Usage examples
└── docs/                 # Documentation
```

## Coding Standards

### Python
- Type hints required
- Docstrings for public APIs
- Black formatting
- Ruff linting

### TypeScript
- Strict mode enabled
- JSDoc for exports
- ESLint + Prettier

## Git Rules

1. **Never push to main** - Sascha releases
2. **Never merge PRs** - Sascha approves
3. **Never release** - Reserved for Sascha
4. Branch naming: `feat/[name]` or `fix/[name]`
5. PR titles: `feat: Add X` or `fix: Resolve Y`
6. **Commit often** - Traceable, visible progress
7. **Push often** - GitHub should always reflect current state
8. **Max 30 mins uncommitted work** - If it works, commit it
9. **NO Co-authored-by** - Never add Co-authored-by trailers
10. **NO AI attribution** - No "created by Codex/Claude/AI" in commits
11. **Author = saschabuehrle** - All commits appear as Sascha's work only

## Key Files

| File | Purpose |
|------|---------|
| `cascadeflow/quality/alignment_scorer.py` | Query-response alignment (KEEP IN SYNC with TS) |
| `packages/core/src/alignment.ts` | TS alignment scorer (currently v10, Python is v13+) |
| `cascadeflow/quality/confidence.py` | Confidence estimation |
| `cascadeflow/agent.py` | Main agent orchestrator |

## Current Priority

- **TS alignment scorer needs v11-v14 updates** from Python
- **Proxy feature** needs integration from `feature/routing-proxy-mvp`
