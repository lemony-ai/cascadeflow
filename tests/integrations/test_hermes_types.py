"""Edge-case coverage for HermesDelegationRequest / HermesDelegationDecision sanitization."""

import pytest

from cascadeflow.integrations.hermes import (
    HermesDelegationDecision,
    HermesDelegationRequest,
)
from cascadeflow.integrations.hermes.types import (
    VALID_ACTIONS,
    VALID_REASONING_EFFORTS,
    _clean_text,
    _clean_tuple,
)


# --- _clean_text ---


def test_clean_text_strips_newlines_and_control_chars():
    assert _clean_text("hello\nworld\r\nfoo") == "hello world  foo"


def test_clean_text_truncates_with_ellipsis():
    long = "a" * 600
    out = _clean_text(long, max_length=10)
    assert out == "aaaaaaa..."
    assert len(out) == 10


def test_clean_text_handles_none():
    assert _clean_text(None) == ""


def test_clean_text_drops_non_printable():
    assert _clean_text("hi\x00\x07there") == "hithere"


# --- _clean_tuple ---


def test_clean_tuple_handles_string_input():
    assert _clean_tuple("solo") == ("solo",)


def test_clean_tuple_handles_none():
    assert _clean_tuple(None) == ()


def test_clean_tuple_skips_empty_entries():
    assert _clean_tuple(["a", "", None, " ", "b"]) == ("a", "b")


def test_clean_tuple_handles_non_iterable():
    assert _clean_tuple(42) == ()


# --- HermesDelegationRequest ---


def test_request_sanitizes_goal_and_truncates():
    long_goal = "x" * 3000
    req = HermesDelegationRequest(goal=long_goal)
    assert len(req.goal) == 2000
    assert req.goal.endswith("...")


def test_request_defaults_role_to_leaf_when_empty():
    req = HermesDelegationRequest(goal="hi", role="")
    assert req.role == "leaf"


def test_request_normalizes_string_toolset_to_tuple():
    req = HermesDelegationRequest(goal="hi", toolsets="terminal")
    assert req.toolsets == ("terminal",)


def test_text_for_classification_with_empty_extras():
    req = HermesDelegationRequest(goal="just a goal")
    assert req.text_for_classification() == "just a goal"


def test_text_for_classification_excludes_loaded_skills():
    # loaded_skills are parent context for audit, NOT a classification signal —
    # see test_parent_loaded_skills_do_not_override_task_domain in test_hermes_router.py
    req = HermesDelegationRequest(goal="g", loaded_skills=("python", "git"))
    assert req.text_for_classification() == "g"


# --- HermesDelegationDecision ---


def test_decision_normalizes_invalid_action_to_inherit():
    d = HermesDelegationDecision(action="DESTROY_ALL_HUMANS")
    assert d.action == "inherit"
    assert not d.applies


def test_decision_lowercases_action():
    d = HermesDelegationDecision(action="ROUTE")
    assert d.action == "route"
    assert d.applies


def test_decision_strips_invalid_reasoning_effort():
    d = HermesDelegationDecision(action="route", reasoning_effort="ultraturbo")
    assert d.reasoning_effort is None


def test_decision_normalizes_valid_reasoning_effort_casing():
    d = HermesDelegationDecision(action="route", reasoning_effort="HIGH")
    assert d.reasoning_effort == "high"


@pytest.mark.parametrize("effort", sorted(VALID_REASONING_EFFORTS))
def test_decision_accepts_all_valid_reasoning_efforts(effort):
    d = HermesDelegationDecision(action="route", reasoning_effort=effort)
    assert d.reasoning_effort == effort


def test_decision_clamps_confidence_to_unit_interval():
    over = HermesDelegationDecision(confidence=5.0)
    under = HermesDelegationDecision(confidence=-3.0)
    assert over.confidence == 1.0
    assert under.confidence == 0.0


def test_decision_handles_none_confidence():
    d = HermesDelegationDecision(confidence=None)  # type: ignore[arg-type]
    assert d.confidence == 0.0


def test_decision_to_dict_serializes_metadata_copy():
    metadata = {"foo": "bar"}
    d = HermesDelegationDecision(metadata=metadata)
    out = d.to_dict()
    out["metadata"]["foo"] = "MUTATED"
    assert metadata["foo"] == "bar"  # original untouched


def test_decision_to_dict_has_all_documented_keys():
    d = HermesDelegationDecision(action="route", provider="nous", model="hermes-4.1")
    out = d.to_dict()
    expected_keys = {
        "action",
        "provider",
        "model",
        "reasoning_effort",
        "domain",
        "topic",
        "complexity",
        "confidence",
        "reason",
        "source",
        "metadata",
    }
    assert set(out) == expected_keys


def test_decision_applies_property():
    assert HermesDelegationDecision(action="route").applies
    assert not HermesDelegationDecision(action="inherit").applies


def test_valid_actions_includes_both_states():
    assert VALID_ACTIONS == {"inherit", "route"}
