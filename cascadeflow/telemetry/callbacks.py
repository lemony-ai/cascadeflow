"""
Callback system for monitoring and hooks.

Provides hooks for:
- Before/after cascade decisions
- Model selection events
- Completion events
- Error handling

Enhanced with: verbose mode, print_stats, reset_stats, callback_errors tracking
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

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
    data: dict[str, Any]
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

    def __init__(self, verbose: bool = False):
        """
        Initialize callback manager.

        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self.callbacks: dict[CallbackEvent, list[Callable]] = {}
        self.stats = {
            "total_triggers": 0,
            "by_event": dict.fromkeys(CallbackEvent, 0),
            "callback_errors": 0,  # ✨ NEW: Track errors
        }

    def register(self, event: CallbackEvent, callback: Callable[[CallbackData], None]):
        """
        Register a callback for an event.

        Args:
            event: Event type to listen for
            callback: Function to call when event occurs
        """
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)

        if self.verbose:
            logger.info(f"Registered callback for {event.value}")
        else:
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
                if self.verbose:
                    logger.info(f"Unregistered callback for {event.value}")
                else:
                    logger.debug(f"Unregistered callback for {event.value}")
            except ValueError:
                logger.warning(f"Callback not found for {event.value}")

    def trigger(
        self,
        event: CallbackEvent,
        query: str,
        data: dict[str, Any],
        user_tier: Optional[str] = None,
        workflow: Optional[str] = None,
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
            timestamp=time.time(),
        )

        for callback in self.callbacks[event]:
            try:
                callback(callback_data)
            except Exception as e:
                self.stats["callback_errors"] += 1  # ✨ Track errors
                logger.error(f"Callback error for {event.value}: {e}", exc_info=True)

    def clear(self, event: Optional[CallbackEvent] = None):
        """
        Clear callbacks for event or all events.

        Args:
            event: Specific event to clear, or None for all
        """
        if event:
            self.callbacks[event] = []
            if self.verbose:
                logger.info(f"Cleared callbacks for {event.value}")
            else:
                logger.debug(f"Cleared callbacks for {event.value}")
        else:
            self.callbacks = {}
            if self.verbose:
                logger.info("Cleared all callbacks")
            else:
                logger.debug("Cleared all callbacks")

    def get_stats(self) -> dict[str, Any]:
        """Get callback statistics."""
        return {
            **self.stats,
            "registered_events": [
                event.value for event, callbacks in self.callbacks.items() if callbacks
            ],
        }

    # ✨ NEW: Additional methods

    def reset_stats(self) -> None:
        """Reset callback statistics."""
        self.stats = {
            "total_triggers": 0,
            "by_event": dict.fromkeys(CallbackEvent, 0),
            "callback_errors": 0,
        }
        if self.verbose:
            logger.info("Callback stats reset")

    def print_stats(self) -> None:
        """Print formatted callback statistics."""
        stats = self.get_stats()

        print("\n" + "=" * 60)
        print("CALLBACK MANAGER STATISTICS")
        print("=" * 60)
        print(f"Total Triggers:    {stats['total_triggers']}")
        print(f"Callback Errors:   {stats['callback_errors']}")
        print()

        # Filter events with triggers > 0
        active_events = {event: count for event, count in stats["by_event"].items() if count > 0}

        if active_events:
            print("TRIGGERS BY EVENT:")
            for event, count in sorted(active_events.items(), key=lambda x: x[1], reverse=True):
                print(f"  {event.value:30s}: {count:6d}")
            print()

        if stats["registered_events"]:
            print("REGISTERED CALLBACKS:")
            for event in sorted(stats["registered_events"]):
                callback_count = len(self.callbacks.get(CallbackEvent[event.upper()], []))
                print(f"  {event:30s}: {callback_count:3d} callback(s)")

        print("=" * 60 + "\n")


__all__ = [
    "CallbackManager",
    "CallbackEvent",
    "CallbackData",
]
