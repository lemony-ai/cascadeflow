"""
Configuration File Watcher for CascadeFlow.

Monitors configuration files for changes and triggers automatic reload.

Example:
    >>> from cascadeflow.config import ConfigManager, ConfigWatcher
    >>>
    >>> manager = ConfigManager(config_path="cascadeflow.yaml")
    >>>
    >>> # Start watching for file changes
    >>> watcher = ConfigWatcher(manager, interval=5.0)
    >>> watcher.start()
    >>>
    >>> # File changes are automatically detected and reloaded
    >>> # ...
    >>>
    >>> # Stop watching
    >>> watcher.stop()
"""

import logging
import os
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """
    File watcher for automatic configuration reload.

    Monitors a configuration file for changes and triggers reload
    when modifications are detected. Uses polling for cross-platform
    compatibility.

    Features:
    - Automatic file change detection
    - Configurable polling interval
    - Thread-safe operation
    - Optional debouncing
    - Pre/post reload callbacks

    Example:
        >>> manager = ConfigManager(config_path="cascadeflow.yaml")
        >>> watcher = ConfigWatcher(manager, interval=5.0)
        >>>
        >>> # Optional: Add callbacks
        >>> watcher.on_reload(lambda: print("Config reloaded!"))
        >>>
        >>> # Start watching
        >>> watcher.start()
        >>>
        >>> # Later: stop watching
        >>> watcher.stop()
    """

    def __init__(
        self,
        manager: "ConfigManager",
        interval: float = 5.0,
        debounce: float = 1.0,
    ):
        """
        Initialize file watcher.

        Args:
            manager: ConfigManager to notify on changes
            interval: Polling interval in seconds (default: 5.0)
            debounce: Debounce time to wait after change detected (default: 1.0)
        """
        self.manager = manager
        self.interval = interval
        self.debounce = debounce

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_mtime: Optional[float] = None
        self._last_reload_time: float = 0

        # Callbacks
        self._pre_reload_callbacks: list[Callable[[], None]] = []
        self._post_reload_callbacks: list[Callable[[], None]] = []

        # Get file path from manager
        self._config_path = manager._config_path

        if self._config_path and self._config_path.exists():
            self._last_mtime = self._get_mtime()

        logger.debug(
            f"ConfigWatcher initialized: path={self._config_path}, "
            f"interval={interval}s, debounce={debounce}s"
        )

    def _get_mtime(self) -> Optional[float]:
        """Get file modification time."""
        try:
            if self._config_path and self._config_path.exists():
                return os.path.getmtime(self._config_path)
        except OSError:
            pass
        return None

    def start(self) -> None:
        """
        Start watching for file changes.

        Creates background thread for polling file changes.
        """
        if self._running:
            logger.warning("ConfigWatcher already running")
            return

        if not self._config_path:
            logger.error("No config path to watch")
            return

        self._running = True
        self._stop_event.clear()

        self._thread = threading.Thread(
            target=self._watch_loop,
            name="ConfigWatcher",
            daemon=True,
        )
        self._thread.start()

        logger.info(f"ConfigWatcher started: watching {self._config_path}")

    def stop(self) -> None:
        """
        Stop watching for file changes.

        Gracefully stops the background thread.
        """
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        logger.info("ConfigWatcher stopped")

    def _watch_loop(self) -> None:
        """Main watch loop (runs in background thread)."""
        while self._running and not self._stop_event.is_set():
            try:
                self._check_for_changes()
            except Exception as e:
                logger.error(f"Error in config watcher: {e}")

            # Wait for interval or stop signal
            self._stop_event.wait(self.interval)

    def _check_for_changes(self) -> None:
        """Check if config file has changed."""
        current_mtime = self._get_mtime()

        if current_mtime is None:
            return

        # Check if file was modified
        if self._last_mtime is not None and current_mtime > self._last_mtime:
            # Debounce: wait a bit in case file is still being written
            time.sleep(self.debounce)

            # Re-check mtime after debounce
            final_mtime = self._get_mtime()
            if final_mtime and final_mtime > self._last_mtime:
                self._trigger_reload()
                self._last_mtime = final_mtime

        elif self._last_mtime is None:
            self._last_mtime = current_mtime

    def _trigger_reload(self) -> None:
        """Trigger configuration reload."""
        logger.info(f"Config file changed, reloading: {self._config_path}")

        # Pre-reload callbacks
        for callback in self._pre_reload_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Pre-reload callback error: {e}")

        # Reload configuration
        success = self.manager.reload()

        # Post-reload callbacks
        if success:
            for callback in self._post_reload_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Post-reload callback error: {e}")

            self._last_reload_time = time.time()

    def on_reload(self, callback: Callable[[], None]) -> None:
        """
        Register callback to run after successful reload.

        Args:
            callback: Function to call after reload
        """
        self._post_reload_callbacks.append(callback)

    def on_before_reload(self, callback: Callable[[], None]) -> None:
        """
        Register callback to run before reload.

        Args:
            callback: Function to call before reload
        """
        self._pre_reload_callbacks.append(callback)

    def force_check(self) -> bool:
        """
        Force immediate check for file changes.

        Returns:
            True if file was changed and reloaded
        """
        old_mtime = self._last_mtime
        current_mtime = self._get_mtime()

        if current_mtime and old_mtime and current_mtime > old_mtime:
            self._trigger_reload()
            self._last_mtime = current_mtime
            return True

        return False

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running

    @property
    def last_reload_time(self) -> Optional[float]:
        """Get timestamp of last reload (or None if never reloaded)."""
        return self._last_reload_time if self._last_reload_time > 0 else None

    def __enter__(self) -> "ConfigWatcher":
        """Context manager entry - start watching."""
        self.start()
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit - stop watching."""
        self.stop()

    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        return f"ConfigWatcher({self._config_path}, {status})"
