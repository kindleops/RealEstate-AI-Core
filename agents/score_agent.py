"""Agent that scores property records based on configurable weights."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from logger import get_logger

LOGGER = get_logger()

WEIGHTS_PATH = Path("config/weights.json")


@dataclass
class ScoreAgentConfig:
    weights_path: Path = WEIGHTS_PATH


class ScoreAgent:
    """Compute motivation score and tag for a property."""

    def __init__(self, config: ScoreAgentConfig | None = None) -> None:
        self.config = config or ScoreAgentConfig()
        self.weights = self._load_weights()

    def _load_weights(self) -> Dict[str, Any]:
        if not self.config.weights_path.exists():
            LOGGER.warning("Weights file missing at %s", self.config.weights_path)
            return {"base_score": 0, "fields": {}, "motivation_thresholds": {}}
        with self.config.weights_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save_weights(self) -> None:
        with self.config.weights_path.open("w", encoding="utf-8") as fh:
            json.dump(self.weights, fh, indent=2)

    def score(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        score = float(self.weights.get("base_score", 0))
        details: Dict[str, float] = {}
        fields = self.weights.get("fields", {})

        for key, value in fields.items():
            contribution = self._evaluate_field(key, value, payload)
            if contribution:
                details[key] = contribution
                score += contribution

        score = max(0, min(100, score))
        motivation = self._label(score)
        return {"score": round(score, 2), "motivation": motivation, "contributions": details}

    def _evaluate_field(self, key: str, rule: Any, payload: Dict[str, Any]) -> float:
        value = payload.get(key)
        if isinstance(rule, (int, float)):
            if isinstance(value, bool) and value:
                return float(rule)
            if isinstance(value, (int, float)) and value:
                return float(rule)
            if isinstance(value, str) and value.lower() in {"yes", "true"}:
                return float(rule)
            return 0.0

        if isinstance(rule, dict):
            if "thresholds" in rule:
                return self._evaluate_thresholds(rule["thresholds"], value)
        return 0.0

    @staticmethod
    def _evaluate_thresholds(thresholds: list[Dict[str, Any]], value: Any) -> float:
        if value is None:
            return 0.0
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return 0.0
        best_score = 0.0
        for threshold in thresholds:
            min_value = threshold.get("min")
            max_days = threshold.get("max_days")
            if min_value is not None and numeric_value >= float(min_value):
                best_score = max(best_score, float(threshold.get("score", 0)))
            if max_days is not None and numeric_value <= float(max_days):
                best_score = max(best_score, float(threshold.get("score", 0)))
        return best_score

    def _label(self, score: float) -> str:
        thresholds = self.weights.get("motivation_thresholds", {})
        high = thresholds.get("high", 75)
        medium = thresholds.get("medium", 45)
        if score >= high:
            return "high"
        if score >= medium:
            return "medium"
        return "low"

    def update_weights(self, updates: Dict[str, Any]) -> None:
        self.weights.update(updates)
        self._save_weights()


__all__ = ["ScoreAgent", "ScoreAgentConfig"]
