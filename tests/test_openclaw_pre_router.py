from cascadeflow.integrations.openclaw.pre_router import classify_openclaw_frame


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
