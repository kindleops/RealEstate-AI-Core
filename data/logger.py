"""Utilities for persisting agent-specific log entries."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from logger import get_logger

LOGGER = get_logger()

LOG_FILE = Path("logs/score_agent.jsonl")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def append_score_log(
    record_id: str,
    score: Optional[int],
    payload: Dict[str, Any],
    status: str,
    error: Optional[str] = None,
) -> None:
    """Persist a structured log entry for score_agent runs."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent": "score_agent",
        "record_id": record_id,
        "score": score,
        "status": status,
        "error": error,
        "payload": payload,
    }
    try:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError as exc:
        LOGGER.exception("Failed writing score_agent log: %s", exc)


__all__ = ["append_score_log"]
