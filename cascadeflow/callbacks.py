"""
Callback system for monitoring and hooks.

Provides hooks for:
- Before/after cascade decisions
- Model selection events
- Completion events
- Error handling
"""

from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import logging
import time

logger = logging.getLogger(__name__)


class CallbackEvent(Enum):
    """Types of callback events."""
    QUERY_START = "query_start"
    COMPLEXITY_DETECTED = "complexity_detected"
    MODELS_SCORED = "models_scored"
    STRATEGY_SELECTED = "strategy_selected"
    MODEL_CALL_START = "model_call_start"
    MODEL_CALL_COMPLETE = "model_call_complete"
    MODEL_CALL_ERROR = "model_call_error"
    CASCADE_DECISION = "cascade_decision"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    QUERY_COMPLETE = "query_complete"
    QUERY_ERROR = "query_error"


@dataclass
class CallbackData:
    """Data passed to callbacks."""
    event: CallbackEvent
    query: str
    user_tier: Optional[str]
    workflow: Optional[str]
    data: Dict[str, Any]
    timestamp: float


class CallbackManager:
    """
    Manages callbacks for monitoring and hooks.

    Example:
        >>> def on_cascade(data: CallbackData):
        ...     print(f"Cascade: {data.data['from']} -> {data.data['to']}")

        >>> manager = CallbackManager()
        >>> manager.register(CallbackEvent.CASCADE_DECISION, on_cascade)
        >>>
        >>> # Later, in agent
        >>> manager.trigger(
        ...     CallbackEvent.CASCADE_DECISION,
        ...     query="test",
        ...     data={'from': 'llama3', 'to': 'gpt-4', 'reason': 'Low confidence'}
        ... )
    """

    def __init__(self):
        self.callbacks: Dict[CallbackEvent, List[Callable]] = {}
        self.stats = {
            "total_triggers": 0,
            "by_event": {event: 0 for event in CallbackEvent}
        }

    def register(
            self,
            event: CallbackEvent,
            callback: Callable[[CallbackData], None]
    ):
        """
        Register a callback for an event.

        Args:
            event: Event type to listen for
            callback: Function to call when event occurs
        """
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)
        logger.debug(f"Registered callback for {event.value}")

    def unregister(self, event: CallbackEvent, callback: Callable):
        """
        Unregister a callback.

        Args:
            event: Event type
            callback: Callback function to remove
        """
        if event in self.callbacks:
            try:
                self.callbacks[event].remove(callback)
                logger.debug(f"Unregistered callback for {event.value}")
            except ValueError:
                logger.warning(f"Callback not found for {event.value}")

    def trigger(
            self,
            event: CallbackEvent,
            query: str,
            data: Dict[str, Any],
            user_tier: Optional[str] = None,
            workflow: Optional[str] = None
    ):
        """
        Trigger callbacks for an event.

        Args:
            event: Event type
            query: User query
            data: Event-specific data
            user_tier: User tier name (optional)
            workflow: Workflow name (optional)
        """
        # Always count triggers, even if no callbacks registered
        self.stats["total_triggers"] += 1
        self.stats["by_event"][event] += 1

        if event not in self.callbacks:
            return

        callback_data = CallbackData(
            event=event,
            query=query,
            user_tier=user_tier,
            workflow=workflow,
            data=data,
            timestamp=time.time()
        )

        for callback in self.callbacks[event]:
            try:
                callback(callback_data)
            except Exception as e:
                logger.error(
                    f"Callback error for {event.value}: {e}",
                    exc_info=True
                )

    def clear(self, event: Optional[CallbackEvent] = None):
        """
        Clear callbacks for event or all events.

        Args:
            event: Specific event to clear, or None for all
        """
        if event:
            self.callbacks[event] = []
            logger.debug(f"Cleared callbacks for {event.value}")
        else:
            self.callbacks = {}
            logger.debug("Cleared all callbacks")

    def get_stats(self) -> Dict[str, Any]:
        """Get callback statistics."""
        return {
            **self.stats,
            "registered_events": [
                event.value
                for event, callbacks in self.callbacks.items()
                if callbacks
            ]
        }