"""Lightweight environment variable loader for the NextaOS Core project."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

_DEFAULT_ENV_PATH = Path(".env")
_LOADED = False


def load_env(path: Path | None = None, override: bool = False) -> Dict[str, str]:
    """Load environment variables from a .env file if present.

    Args:
        path: Optional path to the .env file. Defaults to project root .env.
        override: When True, existing os.environ values are overwritten.

    Returns:
        Mapping of keys that were set during this call.
    """
    global _LOADED
    env_path = path or _DEFAULT_ENV_PATH
    if not env_path.exists():
        return {}
    if _LOADED and not override:
        return {}

    loaded: Dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
            loaded[key] = value

    _LOADED = True
    return loaded


__all__ = ["load_env"]
