# OpenClaw Integration Strategy (Plan)

## Goals
- **Winning DX:** fastest possible onboarding for OpenClaw users with minimal config.
- **Winning UX:** clear savings and latency improvements with zero surprises.
- **Lean core:** OpenClaw integration remains optional and isolated from default Cascadeflow flow.
- **Low overhead:** pre-routing decisions must add minimal latency.

## Non-Goals (v1)
- No cost caps or budget enforcement at launch.
- No breaking changes to existing Cascadeflow routing APIs.

## Design Principles
- **One-minute start:** set `drafter` + `verifier` and it works.
- **Progressive disclosure:** domain/channel routing is opt-in and additive.
- **Deterministic where possible:** predictable OpenClaw-native routes pre-routed.
- **Dynamic where needed:** Cascadeflow domain/complexity routing handles the rest.
- **Separation of concerns:** OpenClaw integration stays in its own module + skill.

## Integration Choice (OpenClaw-side)
**Recommended:** Cascadeflow provider + optional OpenClaw skill (hybrid).
- Provider handles all OpenClaw LLM calls via Cascadeflow.
- Skill provides explicit tagging and quick UI enablement for domain channels.

## Architecture Overview

### 1) OpenClaw Pre-Router (Opt-in)
**Purpose:** ultra-low-latency routing for predictable OpenClaw-native events.
- Uses method/payload hints only (no extra model call).
- Applies when OpenClaw integration is enabled.
- Explicit tags from the OpenClaw skill always override classifier decisions.

### 2) Cascadeflow Rule Engine (Replaces policy)
**Purpose:** centralized routing rules for tiers, KPIs, and domain-aware routing.
- Replaces policy feature; no legacy policy code retained.
- Centralizes: user tiers, profiles, budgets/limits (future), domain routing, KPI gates.
- Rules are backward compatible with existing config keys.

### 3) Cascadeflow Core Routing
**Purpose:** handle dynamic or ambiguous requests.
- Domain detection, tool complexity, cascade verification, and fallback logic.

## OpenClaw User Flow (Winning DX)
1) **Install Cascadeflow provider** in OpenClaw.
2) **Set two models:** `drafter` + `verifier`.
3) Optional: add `failover` channel.
4) Optional: add OpenClaw-native or Cascadeflow domain channels when ready (via Cascadeflow config).

The default path always works with only `drafter` + `verifier`.

## Channel Model Setup (Cascadeflow-side)
**Required**
- `drafter` (fast/cheap)
- `verifier` (quality)

**Optional**
- `failover` (backup provider/model)
  - If not set: fallback = `drafter`, then `verifier`

**Optional OpenClaw-native channels (opt-in)**
- `heartbeat`, `cron`, `voice`, `image_understanding`, `web_search`, `brain`, `coding`, `content`

**Optional Cascadeflow domains (opt-in)**
- `code`, `data`, `structured`, `rag`, `conversation`, `tool`, `creative`, `summary`,
  `translation`, `math`, `medical`, `legal`, `financial`, `multimodal`, `general`

## Routing Rules (Source of Truth)
### OpenClaw-native routes
- **Explicit tags:** from OpenClaw skill.
- **Classifier:** pre-router uses method/payload hints (no model call).
- **If no match:** cascadeflow domain/complexity routing.
 - **Channel mapping:** OpenClaw categories map to channel names (optional) so users can
  route trivial system events (e.g., heartbeat/cron) to a smaller model than the drafter.

### Cascadeflow domains
- **Auto-detected** by Cascadeflow domain routing.
- Explicit tags are optional and only needed to force a specific domain.

## Rule Engine v1
**Inputs**
- Domain + confidence
- Complexity + tool call profile
- User tier / profile / KPI flags
- OpenClaw tags (if present)

**Outputs**
- `routing_strategy`: `direct`, `cascade`, or `cascade_if_low_confidence`
- `preferred_channel`: optional channel override
- `reason`: decision trace for debugging

**Migration Targets**
- Move user tiers + profile selection into Rule Engine.
- Move domain routing decision logic into Rule Engine.
- Keep actual domain detection and model selection in core routing.

## Savings/Accuracy Targets (Acceptance Criteria)
For any OpenClaw use case with routing enabled:
- **Savings target:** >= 60%
- **Accuracy target:** >= 90%

If unmet:
- Investigate, engineer, and propose a validated solution before launch.

## OpenClaw Skill (First-touch DX)
**Purpose:** fastest setup, explicit tags, and optional domain/channel routing.
- Provide guidance for quickstart and optional domain routes.
- Provide explicit tags for OpenClaw-native routes.
- Explain how to enable the OpenClaw pre-router classifier.
- Keep skill doc lean and aligned with OpenClaw docs format.

## DX Risks & Mitigations
- **Too many surfaces (tiers/profiles/rules):**
  - Mitigation: a single quickstart path and progressive disclosure.
- **Ambiguous domain tags:**
  - Mitigation: explicit tag guidance + classifier overrides.

## Implementation Plan

### Phase 0 — Discovery
- Confirm OpenClaw protocol schema and event taxonomy.
- Validate where skill tagging hooks exist.
- Confirm OpenClaw “browser” behavior (content fetch vs. analysis).

#### Discovery findings (2026-02-04)
- **Protocol source of truth:** TypeBox schemas live in `src/gateway/protocol/schema.ts`; AJV validators in `src/gateway/protocol/index.ts`; server methods in `src/gateway/server.ts`. The generated JSON Schema is `dist/protocol.schema.json`; docs note the raw schema is usually published at `raw.githubusercontent.com/openclaw/openclaw/main/dist/protocol.schema.json` (verify availability). citeturn3view0turn8search1
- **Gateway frames:** Request/response/event frames are the canonical transport shape; connect is the first request. citeturn2view0
- **Skills + ClawHub:** Skills are folders with `SKILL.md` (plus supporting files), loaded from `<workspace>/skills` and `~/.openclaw/skills` with workspace precedence. ClawHub is the public registry; CLI installs into `./skills` by default. citeturn0search0turn0search1
- **Browser behavior:** The OpenClaw browser is an agent‑controlled, isolated Chromium profile with deterministic tab control, snapshots/screenshots, and action execution. Internally it uses CDP and Playwright for advanced actions. This is more than content fetch; treat browser workloads as potentially complex unless a deterministic fetch‑only path is confirmed. citeturn6search0

### Phase 1 — Rule Engine v1
- Add RuleEngine + RuleDecision types.
- Migrate tiers/profiles/domain routing decisions to RuleEngine.
- Keep backwards compatibility with existing config.

### Phase 2 — OpenClaw Pre-Router
- Implement method/payload-based classifier.
- Respect explicit tags from OpenClaw skill.
- Provide opt-in config to enable/disable classifier.
 - Map OpenClaw category → channel when no channel is provided.

### Phase 3 — Provider + Skill
- **No OpenClaw code changes required**: users configure a custom provider in OpenClaw
  to route LLM calls to Cascadeflow.
- OpenClaw skill for explicit tags and guidance.
- Failover channel support and docs.
 - Optional Cascadeflow config file to map OpenClaw categories → dedicated channel models.

### Phase 4 — Validation
- E2E OpenClaw tests (latency, savings, accuracy).
- Must meet acceptance criteria; if not, block launch and iterate.
 - Verify heartbeat/cron routing hits dedicated channels when configured.

## Open Questions
- How OpenClaw exposes skill tagging and routing metadata (docs confirm skills are injected into prompts; explicit tag surface still to confirm). citeturn0search1
- Exact OpenClaw native categories and their stability (validate against schema + server methods list).
- Whether the published `dist/protocol.schema.json` exists on GitHub or is only available in releases (docs suggest a raw link but availability may vary). citeturn3view0turn8search1
- Any OpenClaw constraints around provider/skill execution on Pi vs Mac mini.
