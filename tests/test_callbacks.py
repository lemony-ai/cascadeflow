"""Test suite for callback system."""

import pytest

from cascadeflow.telemetry.callbacks import CallbackData, CallbackEvent, CallbackManager


class TestCallbackManager:
    """Test callback manager."""

    def test_register_callback(self):
        manager = CallbackManager()
        called = []

        def callback(data: CallbackData):
            called.append(data.event)

        manager.register(CallbackEvent.QUERY_START, callback)
        manager.trigger(CallbackEvent.QUERY_START, query="test", data={})

        assert CallbackEvent.QUERY_START in called

    def test_multiple_callbacks(self):
        manager = CallbackManager()
        calls = []

        def callback1(data: CallbackData):
            calls.append("callback1")

        def callback2(data: CallbackData):
            calls.append("callback2")

        manager.register(CallbackEvent.QUERY_START, callback1)
        manager.register(CallbackEvent.QUERY_START, callback2)

        manager.trigger(CallbackEvent.QUERY_START, query="test", data={})

        assert len(calls) == 2
        assert "callback1" in calls
        assert "callback2" in calls

    def test_unregister_callback(self):
        manager = CallbackManager()
        called = []

        def callback(data: CallbackData):
            called.append(True)

        manager.register(CallbackEvent.QUERY_START, callback)
        manager.unregister(CallbackEvent.QUERY_START, callback)

        manager.trigger(CallbackEvent.QUERY_START, query="test", data={})

        assert len(called) == 0

    def test_callback_data(self):
        manager = CallbackManager()
        captured_data = []

        def callback(data: CallbackData):
            captured_data.append(data)

        manager.register(CallbackEvent.COMPLEXITY_DETECTED, callback)

        manager.trigger(
            CallbackEvent.COMPLEXITY_DETECTED,
            query="test query",
            data={"complexity": "moderate"},
            user_tier="premium",
            workflow="production",
        )

        assert len(captured_data) == 1
        data = captured_data[0]
        assert data.event == CallbackEvent.COMPLEXITY_DETECTED
        assert data.query == "test query"
        assert data.user_tier == "premium"
        assert data.workflow == "production"
        assert data.data["complexity"] == "moderate"
        assert data.timestamp > 0

    def test_error_handling(self):
        manager = CallbackManager()

        def bad_callback(data: CallbackData):
            raise ValueError("Test error")

        def good_callback(data: CallbackData):
            pass

        manager.register(CallbackEvent.QUERY_START, bad_callback)
        manager.register(CallbackEvent.QUERY_START, good_callback)

        # Should not raise, just log error
        manager.trigger(CallbackEvent.QUERY_START, query="test", data={})

    def test_clear_specific_event(self):
        manager = CallbackManager()

        def callback(data: CallbackData):
            pass

        manager.register(CallbackEvent.QUERY_START, callback)
        manager.register(CallbackEvent.QUERY_COMPLETE, callback)

        manager.clear(CallbackEvent.QUERY_START)

        assert len(manager.callbacks.get(CallbackEvent.QUERY_START, [])) == 0
        assert len(manager.callbacks.get(CallbackEvent.QUERY_COMPLETE, [])) == 1

    def test_clear_all_events(self):
        manager = CallbackManager()

        def callback(data: CallbackData):
            pass

        manager.register(CallbackEvent.QUERY_START, callback)
        manager.register(CallbackEvent.QUERY_COMPLETE, callback)

        manager.clear()

        assert len(manager.callbacks) == 0

    def test_stats(self):
        manager = CallbackManager()

        def callback(data: CallbackData):
            pass

        manager.register(CallbackEvent.QUERY_START, callback)

        manager.trigger(CallbackEvent.QUERY_START, query="test1", data={})
        manager.trigger(CallbackEvent.QUERY_START, query="test2", data={})
        manager.trigger(CallbackEvent.QUERY_COMPLETE, query="test3", data={})

        stats = manager.get_stats()
        assert stats["total_triggers"] == 3
        assert stats["by_event"][CallbackEvent.QUERY_START] == 2
        assert stats["by_event"][CallbackEvent.QUERY_COMPLETE] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
