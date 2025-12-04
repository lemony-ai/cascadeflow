"""
Dynamic Configuration Manager for CascadeFlow.

Provides thread-safe runtime configuration management with:
- Atomic configuration updates
- Event callbacks for changes
- Section-based configuration
- Validation on update

Example:
    >>> manager = ConfigManager()
    >>>
    >>> # Update configuration
    >>> manager.update(quality_threshold=0.85, enable_cascade=True)
    >>>
    >>> # Get current config
    >>> print(manager.get("quality_threshold"))  # 0.85
    >>>
    >>> # Register change listener
    >>> manager.on_change("quality_threshold", lambda old, new: print(f"{old} -> {new}"))
"""

import copy
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Union

logger = logging.getLogger(__name__)


class ConfigSection(str, Enum):
    """Configuration sections for organized management."""

    MODELS = "models"
    DOMAINS = "domains"
    QUALITY = "quality"
    ROUTING = "routing"
    RESILIENCE = "resilience"
    TELEMETRY = "telemetry"
    SETTINGS = "settings"


@dataclass
class ConfigChangeEvent:
    """Event emitted when configuration changes."""

    key: str
    old_value: Any
    new_value: Any
    section: Optional[ConfigSection] = None
    timestamp: float = field(default_factory=lambda: __import__("time").time())

    def __str__(self) -> str:
        return f"ConfigChange({self.key}: {self.old_value} -> {self.new_value})"


class ConfigManager:
    """
    Thread-safe dynamic configuration manager.

    Features:
    - Atomic configuration updates
    - Change event callbacks
    - Section-based organization
    - Validation hooks
    - Snapshot/restore capability

    Example:
        >>> manager = ConfigManager()
        >>>
        >>> # Set initial config
        >>> manager.set_defaults({
        ...     "quality_threshold": 0.70,
        ...     "enable_cascade": True,
        ...     "max_retries": 3,
        ... })
        >>>
        >>> # Update at runtime
        >>> manager.update(quality_threshold=0.85)
        >>>
        >>> # Listen for changes
        >>> manager.on_change("quality_threshold", callback_fn)
    """

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        auto_reload: bool = False,
    ):
        """
        Initialize configuration manager.

        Args:
            config_path: Optional path to config file for initial load
            auto_reload: Enable automatic file reload (requires ConfigWatcher)
        """
        self._config: dict[str, Any] = {}
        self._defaults: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._callbacks: dict[str, list[Callable[[Any, Any], None]]] = {}
        self._global_callbacks: list[Callable[[ConfigChangeEvent], None]] = []
        self._validators: dict[str, Callable[[Any], bool]] = {}
        self._history: list[ConfigChangeEvent] = []
        self._max_history = 100

        # Load from file if provided
        if config_path:
            self._config_path = Path(config_path)
            self._load_from_file()
        else:
            self._config_path = None

        logger.debug(f"ConfigManager initialized with {len(self._config)} settings")

    def _load_from_file(self) -> None:
        """Load configuration from file."""
        if not self._config_path or not self._config_path.exists():
            return

        try:
            from ..config_loader import load_config

            config = load_config(self._config_path)

            with self._lock:
                # Flatten config for easy access
                self._config = self._flatten_config(config)

            logger.info(f"Loaded config from {self._config_path}")

        except Exception as e:
            logger.warning(f"Failed to load config from {self._config_path}: {e}")

    def _flatten_config(self, config: dict, prefix: str = "") -> dict[str, Any]:
        """Flatten nested config dict for easy key access."""
        result = {}

        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict) and not self._is_model_config(value):
                result.update(self._flatten_config(value, full_key))
            else:
                result[full_key] = value

        return result

    def _is_model_config(self, value: dict) -> bool:
        """Check if dict is a model config (should not be flattened)."""
        return "name" in value and "provider" in value

    # ========================================================================
    # CORE OPERATIONS
    # ========================================================================

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.

        Args:
            key: Configuration key (supports dot notation: "quality.threshold")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        with self._lock:
            return self._config.get(key, self._defaults.get(key, default))

    def set(self, key: str, value: Any, validate: bool = True) -> bool:
        """
        Set configuration value.

        Args:
            key: Configuration key
            value: New value
            validate: Run validator if registered

        Returns:
            True if set successfully, False if validation failed

        Raises:
            ValueError: If validation fails
        """
        # Validate if validator registered
        if validate and key in self._validators:
            if not self._validators[key](value):
                raise ValueError(f"Validation failed for {key}={value}")

        with self._lock:
            old_value = self._config.get(key)

            # Skip if no change
            if old_value == value:
                return True

            # Update config
            self._config[key] = value

            # Create change event
            event = ConfigChangeEvent(
                key=key,
                old_value=old_value,
                new_value=value,
            )

            # Store in history
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history.pop(0)

        # Fire callbacks (outside lock to avoid deadlock)
        self._fire_callbacks(event)

        logger.debug(f"Config updated: {key} = {value}")
        return True

    def update(self, **kwargs) -> dict[str, bool]:
        """
        Update multiple configuration values.

        Args:
            **kwargs: Key-value pairs to update

        Returns:
            Dict mapping keys to success status

        Example:
            >>> manager.update(
            ...     quality_threshold=0.85,
            ...     enable_cascade=True,
            ...     max_retries=5
            ... )
        """
        results = {}
        for key, value in kwargs.items():
            try:
                results[key] = self.set(key, value)
            except ValueError as e:
                logger.error(f"Failed to update {key}: {e}")
                results[key] = False
        return results

    def set_defaults(self, defaults: dict[str, Any]) -> None:
        """
        Set default values (used when key not explicitly set).

        Args:
            defaults: Dict of default key-value pairs
        """
        with self._lock:
            self._defaults.update(defaults)

    def get_all(self) -> dict[str, Any]:
        """Get all configuration as dict."""
        with self._lock:
            result = dict(self._defaults)
            result.update(self._config)
            return result

    def get_section(self, section: Union[str, ConfigSection]) -> dict[str, Any]:
        """
        Get all config values for a section.

        Args:
            section: Section name or ConfigSection enum

        Returns:
            Dict of config values in that section
        """
        prefix = section.value if isinstance(section, ConfigSection) else section
        with self._lock:
            return {k: v for k, v in self._config.items() if k.startswith(prefix)}

    # ========================================================================
    # CHANGE CALLBACKS
    # ========================================================================

    def on_change(
        self,
        key: str,
        callback: Callable[[Any, Any], None],
    ) -> None:
        """
        Register callback for specific key changes.

        Args:
            key: Configuration key to watch
            callback: Function called with (old_value, new_value)

        Example:
            >>> def on_threshold_change(old, new):
            ...     print(f"Threshold: {old} -> {new}")
            >>> manager.on_change("quality_threshold", on_threshold_change)
        """
        if key not in self._callbacks:
            self._callbacks[key] = []
        self._callbacks[key].append(callback)

    def on_any_change(
        self,
        callback: Callable[[ConfigChangeEvent], None],
    ) -> None:
        """
        Register callback for any configuration change.

        Args:
            callback: Function called with ConfigChangeEvent
        """
        self._global_callbacks.append(callback)

    def remove_callback(self, key: str, callback: Callable) -> bool:
        """Remove a specific callback for a key."""
        if key in self._callbacks and callback in self._callbacks[key]:
            self._callbacks[key].remove(callback)
            return True
        return False

    def _fire_callbacks(self, event: ConfigChangeEvent) -> None:
        """Fire all relevant callbacks for a change event."""
        # Key-specific callbacks
        if event.key in self._callbacks:
            for callback in self._callbacks[event.key]:
                try:
                    callback(event.old_value, event.new_value)
                except Exception as e:
                    logger.error(f"Callback error for {event.key}: {e}")

        # Global callbacks
        for callback in self._global_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Global callback error: {e}")

    # ========================================================================
    # VALIDATION
    # ========================================================================

    def register_validator(
        self,
        key: str,
        validator: Callable[[Any], bool],
    ) -> None:
        """
        Register validator for a configuration key.

        Args:
            key: Configuration key
            validator: Function that returns True if value is valid

        Example:
            >>> manager.register_validator(
            ...     "quality_threshold",
            ...     lambda v: 0.0 <= v <= 1.0
            ... )
        """
        self._validators[key] = validator

    # ========================================================================
    # SNAPSHOT / RESTORE
    # ========================================================================

    def snapshot(self) -> dict[str, Any]:
        """
        Create snapshot of current configuration.

        Returns:
            Deep copy of current configuration
        """
        with self._lock:
            return copy.deepcopy(self._config)

    def restore(self, snapshot: dict[str, Any]) -> None:
        """
        Restore configuration from snapshot.

        Args:
            snapshot: Previously captured snapshot
        """
        with self._lock:
            # Fire change events for differences
            for key, new_value in snapshot.items():
                old_value = self._config.get(key)
                if old_value != new_value:
                    self._config[key] = new_value
                    self._fire_callbacks(
                        ConfigChangeEvent(
                            key=key,
                            old_value=old_value,
                            new_value=new_value,
                        )
                    )

            # Remove keys not in snapshot
            for key in list(self._config.keys()):
                if key not in snapshot:
                    del self._config[key]

        logger.info("Configuration restored from snapshot")

    def get_history(self, limit: int = 10) -> list[ConfigChangeEvent]:
        """Get recent configuration change history."""
        with self._lock:
            return list(self._history[-limit:])

    # ========================================================================
    # FILE OPERATIONS
    # ========================================================================

    def reload(self) -> bool:
        """
        Reload configuration from file.

        Returns:
            True if reload successful
        """
        if not self._config_path:
            logger.warning("No config path set, cannot reload")
            return False

        try:
            old_config = self.snapshot()
            self._load_from_file()

            # Fire change events for differences
            for key, new_value in self._config.items():
                old_value = old_config.get(key)
                if old_value != new_value:
                    self._fire_callbacks(
                        ConfigChangeEvent(
                            key=key,
                            old_value=old_value,
                            new_value=new_value,
                        )
                    )

            logger.info(f"Configuration reloaded from {self._config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            return False

    def save(self, path: Optional[Union[str, Path]] = None) -> bool:
        """
        Save current configuration to file.

        Args:
            path: Path to save to (uses original path if not provided)

        Returns:
            True if save successful
        """
        save_path = Path(path) if path else self._config_path

        if not save_path:
            logger.error("No path specified for save")
            return False

        try:
            import yaml

            # Unflatten config
            config = self._unflatten_config(self._config)

            with open(save_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)

            logger.info(f"Configuration saved to {save_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def _unflatten_config(self, flat: dict[str, Any]) -> dict[str, Any]:
        """Convert flattened config back to nested dict."""
        result: dict = {}

        for key, value in flat.items():
            parts = key.split(".")
            current = result

            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            current[parts[-1]] = value

        return result

    def __repr__(self) -> str:
        return f"ConfigManager(keys={len(self._config)}, path={self._config_path})"
