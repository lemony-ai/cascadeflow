"""
Decision Trace Logger — JSONL decision trace for every OpenClaw request.

Writes one JSON line per request to a decisions.jsonl file so users can
hand the file to Claude for analysis and threshold tuning.

Features:
- Thread-safe (uses a lock)
- Auto-rotates at 50 MB (renames to .1, keeps max 3 files)
- Configurable via CASCADEFLOW_DECISION_LOG env var
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("cascadeflow.openclaw.decision_trace")

_DEFAULT_PATH = "decisions.jsonl"
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
_MAX_BACKUPS = 3

_lock = threading.Lock()
_log_path: Path | None = None
_file_handle = None


def _get_log_path() -> Path:
    """Resolve the log file path from env or default."""
    global _log_path
    if _log_path is None:
        _log_path = Path(os.environ.get("CASCADEFLOW_DECISION_LOG", _DEFAULT_PATH))
    return _log_path


def _rotate_if_needed(path: Path) -> None:
    """Rotate the log file if it exceeds _MAX_FILE_SIZE."""
    global _file_handle
    try:
        if not path.exists():
            return
        if path.stat().st_size < _MAX_FILE_SIZE:
            return
    except OSError:
        return

    # Close current handle before rotating
    if _file_handle is not None:
        try:
            _file_handle.close()
        except OSError:
            pass
        _file_handle = None

    # Shift existing backups: .3 -> deleted, .2 -> .3, .1 -> .2, current -> .1
    for i in range(_MAX_BACKUPS, 0, -1):
        src = path.with_suffix(f".jsonl.{i}") if i > 0 else path
        if i == 0:
            src = path
        else:
            src = Path(f"{path}.{i}")

        if i == _MAX_BACKUPS:
            # Delete oldest backup
            dst = None
        else:
            dst = Path(f"{path}.{i + 1}")

        if src.exists():
            if dst is None:
                try:
                    src.unlink()
                except OSError:
                    pass
            else:
                try:
                    src.rename(dst)
                except OSError:
                    pass

    # Rename current file to .1
    try:
        path.rename(Path(f"{path}.1"))
    except OSError:
        pass


def _get_file_handle(path: Path):
    """Get or open the file handle for writing."""
    global _file_handle
    if _file_handle is None or _file_handle.closed:
        path.parent.mkdir(parents=True, exist_ok=True)
        _file_handle = open(path, "a", encoding="utf-8")
    return _file_handle


def log_decision(trace: dict[str, Any]) -> None:
    """
    Append one JSON line to the decision log.

    Thread-safe. Performs rotation check before each write.

    Args:
        trace: Decision trace dict (will be serialized to JSON).
    """
    with _lock:
        path = _get_log_path()
        try:
            _rotate_if_needed(path)
            fh = _get_file_handle(path)
            line = json.dumps(trace, default=str, separators=(",", ":"))
            fh.write(line + "\n")
            fh.flush()
        except Exception:
            logger.exception("Failed to write decision trace")


def close() -> None:
    """Close the file handle (for graceful shutdown)."""
    global _file_handle
    with _lock:
        if _file_handle is not None:
            try:
                _file_handle.close()
            except OSError:
                pass
            _file_handle = None


__all__ = ["log_decision", "close"]
