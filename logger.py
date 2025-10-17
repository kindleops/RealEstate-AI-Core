"""Application-wide logging utilities."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_LOG_FILE = LOG_DIR / "agent_runs.jsonl"

LOGGER_NAME = "realestate_ai"
_logger = logging.getLogger(LOGGER_NAME)
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    _logger.addHandler(stream_handler)

    file_handler = logging.FileHandler(LOG_DIR / "application.log")
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)


def get_logger() -> logging.Logger:
    """Return the module-level logger instance."""
    return _logger


def log_agent_interaction(agent: str, payload: Dict[str, Any], response: Dict[str, Any]) -> None:
    """Persist an agent interaction as structured JSON and log a summary message."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "agent": agent,
        "input": payload,
        "output": response,
    }
    _logger.info("Agent %s processed payload", agent)
    try:
        with _LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError as exc:
        _logger.exception("Failed to write agent log: %s", exc)
