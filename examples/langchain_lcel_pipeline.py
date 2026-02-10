"""
LangChain LCEL Pipeline Example (Python)

Demonstrates:
- Prompt -> CascadeFlow -> parser composition (LCEL-style)
- LangSmith tags/metadata passed through CascadeFlow nested runs

Setup:
  export OPENAI_API_KEY="sk-..."
  pip install -U langchain-core langchain-openai
  python examples/langchain_lcel_pipeline.py
"""

import sys
from pathlib import Path

# Allow running directly from a source checkout without `pip install -e .`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from cascadeflow.langchain import CascadeFlow


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY first.")

    drafter = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    verifier = ChatOpenAI(model="gpt-4o", temperature=0.2)

    cascade = CascadeFlow(
        drafter=drafter,
        verifier=verifier,
        quality_threshold=0.7,
        cost_tracking_provider="langsmith",
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a concise engineer."),
            ("human", "{question}"),
        ]
    )

    chain = prompt | cascade | StrOutputParser()

    out = chain.invoke(
        {"question": "List 3 pitfalls when designing agent tool loops."},
        config={
            "tags": ["example", "lcel"],
            "metadata": {"example": "lcel-pipeline"},
        },
    )

    print(out)


if __name__ == "__main__":
    main()
