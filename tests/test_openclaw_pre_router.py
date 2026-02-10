from cascadeflow.integrations.openclaw.pre_router import (
    classify_openclaw_frame,
    extract_explicit_tags,
)


def test_classify_cron_method():
    hint = classify_openclaw_frame(method="cron.add")
    assert hint is not None
    assert hint.category == "cron"


def test_classify_cron_event():
    hint = classify_openclaw_frame(event="cron")
    assert hint is not None
    assert hint.category == "cron"


def test_classify_heartbeat_method():
    hint = classify_openclaw_frame(method="system-event")
    assert hint is not None
    assert hint.category == "heartbeat"


def test_extract_explicit_tags_nested():
    tags = extract_explicit_tags({"cascadeflow": {"category": "brain"}}, None)
    assert tags == {"category": "brain"}


def test_extract_explicit_tags_dot_notation():
    tags = extract_explicit_tags({"cascadeflow.category": "heartbeat"}, None)
    assert tags == {"category": "heartbeat"}


def test_extract_explicit_tags_legacy_keys():
    tags = extract_explicit_tags({"cascadeflow_profile": "quality"}, None)
    assert tags == {"profile": "quality"}
