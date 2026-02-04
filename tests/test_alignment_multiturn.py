"""Tests for multi-turn alignment detection."""

import pytest

from cascadeflow.quality.alignment_scorer import QueryResponseAlignmentScorer


def test_alignment_multiturn_boost():
    scorer = QueryResponseAlignmentScorer()
    query = "User: What's the weather in Paris?\nAssistant: It's sunny.\nUser: And tomorrow?"
    response = "Tomorrow in Paris is partly cloudy with a high of 18C."

    analysis = scorer.score(query=query, response=response, query_difficulty=0.3, verbose=True)

    assert analysis.features.get("is_multi_turn") is True
    assert analysis.alignment_score == pytest.approx(0.72, abs=0.001)
