"""
LangGraph Multi-Agent Example (Python, optional)

Demonstrates (conceptually):
- Multi-agent / graph orchestration with cascadeflow
- Tool binding + high-risk verifier policy

Notes:
- Requires optional dependency: `pip install langgraph`
- This file is an example only; it is not required for cascadeflow core usage.

Setup:
  export OPENAI_API_KEY="sk-..."
  pip install -U langchain-core langchain-openai langgraph
  python examples/langchain_langgraph_multi_agent.py
"""

import os

from langchain_openai import ChatOpenAI

from cascadeflow.langchain import CascadeFlow


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY first.")

    # Optional: import only when used.
    from langgraph.graph import END, StateGraph  # type: ignore

    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    verifier = ChatOpenAI(model="gpt-4o", temperature=0.2)

    base = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.7,
        cost_tracking_provider="langsmith",
    )

    tools = [
        {
            "name": "get_weather",
            "description": "Read-only: get the current weather for a location.",
            "parameters": {
                "type": "object",
                "properties": {"location": {"type": "string"}},
                "required": ["location"],
            },
        },
        {
            "name": "delete_user",
            "description": "HIGH RISK: permanently deletes a user account (irreversible).",
            "parameters": {
                "type": "object",
                "properties": {"user_id": {"type": "string"}},
                "required": ["user_id"],
            },
        },
    ]

    cascade = base.bind_tools(tools)

    def planner(state: dict) -> dict:
        msg = cascade.invoke(
            state["input"],
            config={
                "tags": ["example", "langgraph", "planner"],
                "metadata": {"example": "langgraph-multi-agent", "agent": "planner"},
            },
        )
        return {**state, "result": msg.content}

    graph = StateGraph(dict)
    graph.add_node("planner", planner)
    graph.set_entry_point("planner")
    graph.add_edge("planner", END)

    app = graph.compile()
    out = app.invoke(
        {
            "input": "Plan steps to fetch weather for Berlin. If any destructive action is needed, propose it but do not execute."
        }
    )

    print(out.get("result"))


if __name__ == "__main__":
    main()
