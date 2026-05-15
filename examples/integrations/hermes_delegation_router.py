"""
Standalone Hermes Agent delegation-routing example.

This example does not import Hermes. It shows the small adapter shape a local
Hermes wrapper, fork, or upstream PR can use before spawning a delegated child
agent.
"""

from __future__ import annotations

from cascadeflow.integrations.hermes import HermesDelegationRequest, HermesDelegationRouter

ROUTER_CONFIG = {
    "enabled": True,
    "mode": "observe",
    "min_confidence": 0.6,
    "routes": {
        "simple": {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "reasoning_effort": "low",
        },
        "code": {
            "provider": "nous",
            "model": "nous/hermes-4.1",
            "reasoning_effort": "high",
        },
        "research": {
            "provider": "nous",
            "model": "nous/hermes-research",
            "reasoning_effort": "medium",
        },
        "finance": {
            "provider": "anthropic",
            "model": "claude-opus-4.1",
            "reasoning_effort": "high",
        },
    },
}


def route_before_delegate_task(
    *,
    goal: str,
    context: str | None = None,
    toolsets: tuple[str, ...] = (),
    loaded_skills: tuple[str, ...] = (),
    skill_metadata: dict | None = None,
    parent_provider: str | None = None,
    parent_model: str | None = None,
) -> dict:
    """Return a Hermes-safe routing recommendation for a delegated task."""

    router = HermesDelegationRouter.from_dict(ROUTER_CONFIG)
    decision = router.route_delegation(
        HermesDelegationRequest(
            goal=goal,
            context=context,
            toolsets=toolsets,
            loaded_skills=loaded_skills,
            skill_metadata=skill_metadata,
            parent_provider=parent_provider,
            parent_model=parent_model,
        )
    )
    return decision.to_dict()


if __name__ == "__main__":
    coding_decision = route_before_delegate_task(
        goal="Debug the failing pytest regression and propose a patch",
        context="The parent agent is working on a Python API client.",
        toolsets=("terminal", "git"),
        loaded_skills=("python", "debugging"),
        parent_provider="openai",
        parent_model="gpt-4.1-mini",
    )
    print("Coding subagent decision:")
    print(coding_decision)

    skill_decision = route_before_delegate_task(
        goal="Review this indemnity clause for business risk",
        loaded_skills=("contract-review",),
        skill_metadata={
            "cascadeflow": {
                "provider": "anthropic",
                "model": "claude-opus-4.1",
                "reasoning_effort": "high",
                "domain": "legal",
                "topic": "contract-review",
                "confidence": 0.99,
            }
        },
    )
    print("\nSkill-routed subagent decision:")
    print(skill_decision)

