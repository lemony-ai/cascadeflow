# CascadeFlow Hermes Agent Integration

Optional delegation router for Hermes Agent subagents.

Hermes owns provider credentials, base URLs, fallback chains, and API modes.
CascadeFlow returns an auditable recommendation before Hermes spawns a child
agent.

```python
from cascadeflow.integrations.hermes import (
    HermesDelegationRequest,
    HermesDelegationRouter,
)

router = HermesDelegationRouter.from_dict({
    "enabled": True,
    "mode": "observe",
    "routes": {
        "simple": {"provider": "openai", "model": "gpt-4.1-mini", "reasoning_effort": "low"},
        "code": {"provider": "nous", "model": "nous/hermes-4.1", "reasoning_effort": "high"},
    },
})

decision = router.route_delegation(HermesDelegationRequest(
    goal="Debug the failing unit test and propose a patch",
    toolsets=("terminal", "git"),
    loaded_skills=("python", "debugging"),
))
```

The integration supports:

- per-skill model and reasoning profiles through skill metadata
- task-complexity routing for simple versus hard delegated tasks
- topic-aware routing for code, research, data, creative, ops, legal, medical, and finance work
- observe mode for dry-run rollout
- structured decision audit fields
- inherit fallbacks for disabled config, low confidence, errors, and unconfigured high-stakes domains

