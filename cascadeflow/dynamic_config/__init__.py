"""
Dynamic Configuration Management for CascadeFlow.

Provides runtime configuration updates without service restart:
- ConfigManager: Central config management with event system
- ConfigWatcher: File watching for automatic config reload
- Thread-safe configuration updates
- Event callbacks for config changes

Example:
    >>> from cascadeflow.config import ConfigManager, ConfigWatcher
    >>>
    >>> # Create manager with initial config
    >>> manager = ConfigManager(config_path="cascadeflow.yaml")
    >>>
    >>> # Register callback for config changes
    >>> @manager.on_change("quality_threshold")
    ... def on_threshold_change(old, new):
    ...     print(f"Threshold changed: {old} -> {new}")
    >>>
    >>> # Enable file watching for auto-reload
    >>> watcher = ConfigWatcher(manager, interval=5.0)
    >>> watcher.start()
    >>>
    >>> # Manual config update
    >>> manager.update(quality_threshold=0.85)
"""

from .manager import (
    ConfigManager,
    ConfigChangeEvent,
    ConfigSection,
)
from .watcher import (
    ConfigWatcher,
)

__all__ = [
    "ConfigManager",
    "ConfigChangeEvent",
    "ConfigSection",
    "ConfigWatcher",
]
