"""Helpers for loading configuration data from disk."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


CONFIG_ROOT = Path(__file__).resolve().parents[1] / "config"


@lru_cache(maxsize=1)
def _load_weights() -> Dict[str, Any]:
    """Load and cache the weights configuration file."""

    weights_path = CONFIG_ROOT / "weights.json"
    if not weights_path.exists():
        return {}
    with weights_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_weights(agent_key: str) -> Dict[str, Any]:
    """Retrieve a weight configuration dictionary for a given agent."""

    return _load_weights().get(agent_key, {})
