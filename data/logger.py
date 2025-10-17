"""Utility helpers for structured application logging.

This module provides a light-weight JSON Lines logger that the agents can
reuse to persist analytic events and operational traces.  The implementation
avoids external dependencies so it can run in constrained environments while
still producing machine readable output that downstream dashboards or
analytics notebooks can consume.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class StructuredLogger:
    """Write structured log events to a JSONL file.

    Parameters
    ----------
    name:
        Logical name for the logger; this becomes the filename under the
        ``data/logs`` directory.
    base_path:
        Optional base directory for logs.  Tests can override this to a
        temporary directory without patching environment variables.
    """

    def __init__(self, name: str, base_path: Optional[Path] = None) -> None:
        self.name = name
        self.base_path = base_path or Path("data/logs")
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._file_path = self.base_path / f"{self.name}.jsonl"
        # Multiple threads can attempt to log simultaneously when background
        # agents are involved.  A simple re-entrant lock keeps file writes
        # consistent without introducing heavier dependencies.
        self._lock = threading.RLock()

    def log_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Append an event entry to the log file.

        Parameters
        ----------
        event_type:
            Human readable label describing the event.
        payload:
            Arbitrary JSON-serialisable dictionary with event details.
        """

        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event_type,
            "payload": payload,
        }

        with self._lock:
            with self._file_path.open("a", encoding="utf-8") as fh:
                json.dump(record, fh, ensure_ascii=False)
                fh.write("\n")

    def tail(self, limit: int = 50) -> Dict[str, Any]:
        """Return the most recent ``limit`` records for quick inspection."""

        with self._lock:
            if not self._file_path.exists():
                return []
            with self._file_path.open("r", encoding="utf-8") as fh:
                lines = fh.readlines()[-limit:]
        return [json.loads(line) for line in lines]


def get_logger(name: str) -> StructuredLogger:
    """Convenience factory mirroring the :mod:`logging` API."""

    return StructuredLogger(name)


__all__ = ["StructuredLogger", "get_logger"]

