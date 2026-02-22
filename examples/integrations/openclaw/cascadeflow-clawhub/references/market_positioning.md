# Market Positioning For ClawHub

This note summarizes observed OpenClaw/ClawHub patterns and how to position CascadeFlow for a strong listing.

## What Existing Listings Signal

Observed from public ClawHub skill pages:

- `openclaw` emphasizes broad capability and direct install command.
- `context7` emphasizes practical developer utility and easy install.
- Skill pages are brief; the first value statement and install path carry most of the conversion.

Observed from OpenClaw docs:

- Slash command aliases are a first-class pattern (for example `/model myalias`).
- Users expect provider setup to be copy-paste and reversible.

## Winning Listing Principles

1. Lead with measurable outcome:
- "Reduce cost and latency" should be in title and short description.

2. Highlight OpenClaw-native intelligence:
- Emphasize event/domain understanding (`metadata.method`, `metadata.event`) as a unique capability.
- Explain that operational events and user domains route differently by design.

3. Keep time-to-first-success short:
- One install block.
- One provider config block.
- One command to switch model (`/model cflow`).

4. Remove ambiguity:
- Explicitly mark `/cascade` as optional custom command.
- Explicitly list all 3 presets and when to use each.

5. Build trust:
- Show secure defaults (`auth-token`, localhost bind, stats token).
- Show health/stats/smoke checks.

6. Keep compatibility messaging clear:
- Works as OpenAI-compatible provider transport.
- Works with OpenAI-only, Anthropic-only, and mixed routes.

## Suggested ClawHub Listing Copy

Display name:

- `CascadeFlow: Cost + Latency Reduction`

Short description:

- `Reduce LLM cost and latency with CascadeFlow routing`

One-line value prop:

- `OpenClaw provider with native event/domain understanding and drafter/verifier cascades for lower cost, lower latency, and quality control.`

## Recommended User-Facing Sections

- Quickstart (install + start + provider config)
- Presets (OpenAI-only, Anthropic-only, mixed)
- Commands (`/model cflow`, optional `/cascade`)
- Verification checks (`/health`, `/stats`, chat completion)
- Troubleshooting (streaming, auth, endpoint path)

## Sources

- OpenClaw + ClawHub docs: https://docs.openclaw.bot/guide/clawhub
- OpenClaw slash commands docs: https://docs.openclaw.bot/guide/faq/slash-commands
- ClawHub OpenClaw listing page: https://www.clawhub.ai/s/openclaw
- ClawHub Context7 listing page: https://www.clawhub.ai/s/context7
