"""Utilities for selecting the appropriate model for a given task."""

from __future__ import annotations

from typing import Any, Mapping, Optional

DEFAULT_MODEL_MAP = {
    "sms": "phi3",
    "comps": "mistral",
}

FALLBACK_MODEL = "gpt-4o"
DEFAULT_MAX_INPUT_LENGTH = 4000


def _resolve_task_type(task: Optional[Any]) -> Optional[str]:
    """Extract the task type from dictionaries or objects.

    The selector is intentionally forgiving so tests and runtime code can
    provide a light-weight ``task`` representation (``dict`` or an object with
    a ``type`` attribute).
    """

    if task is None:
        return None

    if isinstance(task, Mapping):
        raw_type = task.get("type")
        return str(raw_type) if raw_type is not None else None

    task_type = getattr(task, "type", None)
    return str(task_type) if task_type is not None else None


def select_model(
    task: Optional[Any],
    input_text: str,
    *,
    max_input_length: int = DEFAULT_MAX_INPUT_LENGTH,
) -> str:
    """Return the best model identifier for the supplied task.

    Args:
        task: A mapping or lightweight object describing the task. The
            selector expects a ``type`` key/attribute.
        input_text: Raw text that will be sent to the model.
        max_input_length: Maximum number of characters allowed before falling
            back to :data:`FALLBACK_MODEL`.

    Returns:
        The identifier of the model that should process the request.
    """

    if len(input_text or "") > max_input_length:
        return FALLBACK_MODEL

    task_type = _resolve_task_type(task)
    if not task_type:
        return FALLBACK_MODEL

    return DEFAULT_MODEL_MAP.get(task_type.lower(), FALLBACK_MODEL)


__all__ = ["select_model", "DEFAULT_MODEL_MAP", "FALLBACK_MODEL", "DEFAULT_MAX_INPUT_LENGTH"]
"""Utilities for selecting between local and cloud models."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from logger import get_logger

LOGGER = get_logger()

CONFIG_PATH = Path("config/models.json")


@dataclass
class ModelChoice:
    name: str
    provider_type: str  # "cloud" or "local"


class ModelSelector:
    """Simple heuristic model selector with adjustable routing ratios."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or CONFIG_PATH
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Dict[str, object]]:
        if not self.config_path.exists():
            LOGGER.warning("Model config not found at %s, using defaults", self.config_path)
            return {
                "cloud": {"providers": [{"name": "gpt-4o", "weight": 1.0}]},
                "local": {"providers": [{"name": "phi3:mini", "weight": 1.0}]},
                "routing": {"cloud_ratio": 0.5, "local_ratio": 0.5},
            }

        with self.config_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as fh:
            json.dump(self._config, fh, indent=2)

    def choose(self, preference: Optional[str] = None) -> ModelChoice:
        """Select a model based on configured routing ratios and optional preference."""
        preference = (preference or "").lower()
        if preference in {"cloud", "local"}:
            provider_type = preference
        else:
            provider_type = self._choose_provider_type()

        provider = self._weighted_choice(self._config.get(provider_type, {}).get("providers", []))
        if provider is None:
            fallback_type = "cloud" if provider_type == "local" else "local"
            provider = self._weighted_choice(
                self._config.get(fallback_type, {}).get("providers", [])
            ) or {"name": "mistral-7b"}
            provider_type = fallback_type
            LOGGER.warning("No providers for %s, falling back to %s", preference, provider_type)

        return ModelChoice(name=provider.get("name", "mistral-7b"), provider_type=provider_type)

    def update_routing(self, cloud_ratio: float | None = None, local_ratio: float | None = None) -> None:
        routing = self._config.setdefault("routing", {})
        if cloud_ratio is not None:
            routing["cloud_ratio"] = cloud_ratio
        if local_ratio is not None:
            routing["local_ratio"] = local_ratio
        self._save_config()

    def _choose_provider_type(self) -> str:
        routing = self._config.get("routing", {})
        cloud_ratio = float(routing.get("cloud_ratio", 0.5))
        local_ratio = float(routing.get("local_ratio", 0.5))
        total = cloud_ratio + local_ratio
        if total <= 0:
            return "local"
        pick = random.random() * total
        if pick < cloud_ratio:
            return "cloud"
        return "local"

    @staticmethod
    def _weighted_choice(options: list[Dict[str, object]]) -> Optional[Dict[str, object]]:
        if not options:
            return None
        total = sum(float(opt.get("weight", 1.0)) for opt in options)
        pick = random.random() * total
        cumulative = 0.0
        for opt in options:
            cumulative += float(opt.get("weight", 1.0))
            if pick <= cumulative:
                return opt
        return options[-1]


__all__ = ["ModelSelector", "ModelChoice"]
