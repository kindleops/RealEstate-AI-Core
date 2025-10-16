"""Agent that continuously refines scoring weights."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable

from data.logger import get_logger
from utils.prompt_templates import get_template


class LearningLoopAgent:
    def __init__(self, weights_path: Path | None = None) -> None:
        self.logger = get_logger("learning_loop")
        self.weights_path = weights_path or Path("config/weights.json")

    def analyse(self, closed_deals: Iterable[Dict], dead_leads: Iterable[Dict]) -> Dict[str, float]:
        closed_avg = self._average_features(closed_deals)
        dead_avg = self._average_features(dead_leads)
        suggestions = {
            feature: round(closed_avg.get(feature, 0) - dead_avg.get(feature, 0), 3)
            for feature in set(closed_avg) | set(dead_avg)
        }
        self.logger.log_event("learning_loop_analysis", suggestions)
        return suggestions

    def update_weights(self, suggestions: Dict[str, float]) -> Dict[str, float]:
        weights = self._load_weights()
        for feature, delta in suggestions.items():
            weights[feature] = round(max(0.0, weights.get(feature, 0.0) + delta), 3)
        normalised = self._normalise(weights)
        self._save_weights(normalised)
        self.logger.log_event("weights_updated", normalised)
        return normalised

    def generate_summary(self, suggestions: Dict[str, float]) -> str:
        template = get_template("learning_loop")
        body = "\n".join(f"{feature}: {delta:+}" for feature, delta in suggestions.items())
        return f"{template}\n\n{body}"

    # ------------------------------------------------------------------
    def _load_weights(self) -> Dict[str, float]:
        if not self.weights_path.exists():
            return {}
        return json.loads(self.weights_path.read_text(encoding="utf-8"))

    def _save_weights(self, weights: Dict[str, float]) -> None:
        self.weights_path.write_text(json.dumps(weights, indent=2), encoding="utf-8")

    def _average_features(self, records: Iterable[Dict]) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        counts: Dict[str, int] = {}
        for record in records:
            for feature, value in record.get("features", {}).items():
                totals[feature] = totals.get(feature, 0.0) + float(value)
                counts[feature] = counts.get(feature, 0) + 1
        return {
            feature: round(totals[feature] / counts[feature], 3)
            for feature in totals
            if counts[feature]
        }

    def _normalise(self, weights: Dict[str, float]) -> Dict[str, float]:
        total = sum(weights.values())
        if total == 0:
            return weights
        return {feature: round(value / total, 3) for feature, value in weights.items()}


__all__ = ["LearningLoopAgent"]

