"""Centralized structured logging utilities for agents."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from logger import get_logger

LOGGER = get_logger()

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

EVENT_LOG = LOG_DIR / "agent_events.jsonl"


def _to_jsonable(value: Any) -> Any:
    """Best-effort conversion to a JSON-serialisable structure."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool, dict, list)):
        return value
    if isinstance(value, tuple):
        return [_to_jsonable(v) for v in value]
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError):
        return str(value)


def _write_log_entry(path: Path, entry: Dict[str, Any]) -> None:
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError as exc:
        LOGGER.exception("Failed to persist agent event log: %s", exc)


def log_agent_event(
    agent: str,
    record_id: Optional[str],
    status: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a structured event for a single record interaction."""
    entry: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agent": agent,
        "record_id": record_id,
        "status": status,
        "payload": _to_jsonable(payload),
        "result": _to_jsonable(result),
        "error": error,
    }
    if details:
        entry["details"] = _to_jsonable(details)
    _write_log_entry(EVENT_LOG, entry)


def log_batch_summary(agent: str, processed: int, success: int, failed: int) -> None:
    """Persist a high-level batch summary entry."""
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agent": agent,
        "event": "batch_summary",
        "processed": processed,
        "success": success,
        "failed": failed,
    }
    _write_log_entry(EVENT_LOG, entry)


def append_score_log(
    record_id: str,
    score: Optional[int],
    payload: Dict[str, Any],
    status: str,
    error: Optional[str] = None,
) -> None:
    """Backward-compatible helper dedicated to the score agent."""
    log_agent_event(
        "score_agent",
        record_id,
        status,
        payload=payload,
        result={"score": score},
        error=error,
    )


__all__ = ["append_score_log", "log_agent_event", "log_batch_summary"]
