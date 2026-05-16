"""Coverage tests for HermesTaskClassifier — exercise real domain/complexity paths."""

import pytest

from cascadeflow.integrations.hermes import (
    HermesDelegationRequest,
    HermesTaskClassifier,
)
from cascadeflow.integrations.hermes.classifier import (
    DOMAIN_KEYWORDS,
    HIGH_STAKES_DOMAINS,
    TOOLSET_DOMAIN_HINTS,
)


def _req(goal, **kw):
    return HermesDelegationRequest(goal=goal, **kw)


@pytest.fixture
def classifier():
    return HermesTaskClassifier()


@pytest.mark.parametrize(
    ("domain", "goal"),
    [
        ("debugging", "Investigate the failing test traceback and find the root cause"),
        ("code", "Implement a TypeScript API client with unit tests for the schema"),
        ("research", "Research and summarize recent web sources on the market"),
        ("data", "Run SQL against the postgres warehouse and build a dashboard with metrics"),
        ("creative", "Write headline copy and brand script for the design"),
        ("ops", "Deploy the kubernetes workflow and review CI logs for the incident"),
        ("legal", "Review the contract for privacy compliance and terms"),
        ("medical", "Summarize the patient diagnosis and treatment options"),
        ("finance", "Reconcile the invoice and calculate the tax on revenue"),
    ],
)
def test_each_domain_keyword_set_classifies(classifier, domain, goal):
    cls = classifier.classify(_req(goal))
    assert cls.domain == domain
    assert cls.confidence > 0.5


def test_no_keywords_falls_back_to_general(classifier):
    cls = classifier.classify(_req("hello there my friend"))
    # generic chitchat with simple/trivial complexity → mapped to "simple"
    assert cls.domain in {"general", "simple"}


def test_simple_complexity_remaps_general_to_simple(classifier):
    cls = classifier.classify(_req("hi"))
    assert cls.domain == "simple"
    assert cls.reason == "simple_complexity"
    assert cls.topic is None


def test_topic_set_for_non_simple_domain(classifier):
    cls = classifier.classify(_req("Refactor this python schema to add unit tests"))
    assert cls.domain == "code"
    assert cls.topic == "code"


def test_toolset_hints_boost_domain(classifier):
    # No code keywords in goal, but git toolset hints to code
    cls = classifier.classify(_req("Please assist with this task", toolsets=("git",)))
    assert cls.domain == "code"


def test_browser_toolset_hints_to_research(classifier):
    cls = classifier.classify(_req("Look this up for me", toolsets=("browser",)))
    assert cls.domain == "research"


def test_high_stakes_domains_are_detected(classifier):
    for domain in HIGH_STAKES_DOMAINS:
        keyword = next(iter(DOMAIN_KEYWORDS[domain]))
        cls = classifier.classify(_req(f"Help with {keyword} matters"))
        assert cls.domain == domain
        assert cls.domain in HIGH_STAKES_DOMAINS


def test_keyword_hits_increase_confidence(classifier):
    one_hit = classifier.classify(_req("review the contract"))
    many_hits = classifier.classify(
        _req("review the contract for legal compliance and privacy terms under the law")
    )
    assert many_hits.confidence >= one_hit.confidence
    assert many_hits.confidence <= 0.95  # capped


def test_confidence_clamped_to_unit_interval(classifier):
    # Stack every keyword for one domain; confidence must still <= 1.0
    keywords = " ".join(DOMAIN_KEYWORDS["code"])
    cls = classifier.classify(_req(keywords))
    assert 0.0 <= cls.confidence <= 1.0


def test_text_for_classification_includes_context(classifier):
    # Goal is empty of signal; debugging keywords live only in context
    cls = classifier.classify(
        _req(
            "vague goal",
            context="Find the bug and debug the regression to identify root cause",
        )
    )
    assert cls.domain == "debugging"


def test_classifier_handles_failing_complexity_detector():
    class Boom:
        def detect(self, text):
            raise RuntimeError("boom")

    classifier = HermesTaskClassifier(complexity_detector=Boom())
    cls = classifier.classify(_req("Implement the python schema"))
    # falls back to moderate complexity rather than crashing
    assert cls.complexity == "moderate"
    assert cls.domain == "code"


def test_toolset_domain_hints_table_is_consistent():
    # Every hinted domain must exist in DOMAIN_KEYWORDS (otherwise routing breaks)
    for hinted_domain in TOOLSET_DOMAIN_HINTS.values():
        assert (
            hinted_domain in DOMAIN_KEYWORDS
        ), f"toolset hint points to unknown domain {hinted_domain!r}"
