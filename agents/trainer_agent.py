"""Trainer agent that refines scoring weights based on deal outcomes."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence

from data.airtable_client import AirtableError, create_record, get_records
from data.airtable_schema import MODEL_LOGS_TABLE, PROPERTIES_TABLE, PropertyDealStatus
from data.logger import log_agent_event
from logger import get_logger
from utils.model_selector import ModelSelector

LOGGER = get_logger()


@dataclass
class TrainerAgentConfig:
    weights_path: Path = Path("config/weights.json")
    properties_table: str = PROPERTIES_TABLE.name()
    model_log_table: str = MODEL_LOGS_TABLE.name()
    motivation_field: str = PROPERTIES_TABLE.field_name("MOTIVATION_SCORE")
    status_field: str = PROPERTIES_TABLE.field_name("DEAL_STATUS")
    closed_statuses: Sequence[str] = (
        PropertyDealStatus.CLOSED.value,
        PropertyDealStatus.SOLD.value,
    )
    learning_rate: float = 0.05


class TrainerAgent:
    """Analyze deal outcomes and update configuration weights."""

    def __init__(self, config: TrainerAgentConfig | None = None, model_selector: Optional[ModelSelector] = None) -> None:
        self.config = config or TrainerAgentConfig()
        self.model_selector = model_selector or ModelSelector()

    def analyze(self) -> Dict[str, Any]:
        records = self._fetch_property_records()
        if not records:
            return {"processed": 0, "message": "No records available for training."}

        motivation_scores, closed_scores = self._extract_scores(records)
        if not motivation_scores:
            return {"processed": len(records), "message": "No motivation scores found."}

        avg_score = mean(motivation_scores)
        avg_closed = mean(closed_scores) if closed_scores else 0.0
        adjustment = self._calculate_adjustment(avg_score, avg_closed)

        weights_before = self._load_weights()
        weights_after = self._apply_adjustment(weights_before, adjustment)
        if weights_after != weights_before:
            self._save_weights(weights_after)
            self._log_model_adjustment(weights_before, weights_after, avg_closed, avg_score)

        self._rebalance_model_routing(avg_closed)

        summary = {
            "processed": len(records),
            "closed_count": len(closed_scores),
            "average_score": round(avg_score, 2),
            "average_closed_score": round(avg_closed, 2),
            "adjustment": round(adjustment, 4),
        }

        log_agent_event("trainer_agent", None, "success", details=summary)
        return summary

    # ------------------------------------------------------------------
    # Data handling

    def _fetch_property_records(self) -> List[Dict[str, Any]]:
        try:
            return get_records(self.config.properties_table)
        except AirtableError as exc:
            LOGGER.exception("Failed to fetch property records: %s", exc)
            log_agent_event("trainer_agent", None, "error", error=str(exc))
            return []

    def _extract_scores(self, records: List[Dict[str, Any]]) -> tuple[List[float], List[float]]:
        all_scores: List[float] = []
        closed_scores: List[float] = []
        for record in records:
            fields = record.get("fields", {})
            raw_score = fields.get(self.config.motivation_field)
            if raw_score in (None, ""):
                continue
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                continue
            all_scores.append(score)
            status = str(fields.get(self.config.status_field, ""))
            if status in self.config.closed_statuses:
                closed_scores.append(score)
        return all_scores, closed_scores

    # ------------------------------------------------------------------
    # Weight adjustment logic

    def _calculate_adjustment(self, avg_score: float, avg_closed: float) -> float:
        if avg_score == 0:
            return 0.0
        difference = avg_closed - avg_score
        return max(-0.1, min(0.1, (difference / 100.0) * self.config.learning_rate))

    def _load_weights(self) -> Dict[str, Any]:
        if not self.config.weights_path.exists():
            LOGGER.warning("Weights file missing at %s", self.config.weights_path)
            return {}
        with self.config.weights_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _apply_adjustment(self, weights: Dict[str, Any], delta: float) -> Dict[str, Any]:
        if delta == 0 or "score_agent" not in weights:
            return weights

        updated = json.loads(json.dumps(weights))  # deep copy
        score_weights = updated.setdefault("score_agent", {})
        base_score = float(score_weights.get("base_score", 0))
        score_weights["base_score"] = round(max(0.0, base_score * (1 + delta)), 2)

        fields = score_weights.get("fields", {})
        for key, value in list(fields.items()):
            if isinstance(value, (int, float)):
                new_value = max(0.0, value * (1 + delta))
                fields[key] = round(new_value, 2)
        score_weights["fields"] = fields
        return updated

    def _save_weights(self, weights: Dict[str, Any]) -> None:
        self.config.weights_path.write_text(json.dumps(weights, indent=2), encoding="utf-8")
        LOGGER.info("Updated weights written to %s", self.config.weights_path)

    def _log_model_adjustment(
        self,
        before: Dict[str, Any],
        after: Dict[str, Any],
        avg_closed: float,
        avg_score: float,
    ) -> None:
        summary = (
            f"Adjusted score_agent weights. Avg closed score={avg_closed:.2f}, "
            f"overall avg={avg_score:.2f}."
        )
        try:
            fields = {
                MODEL_LOGS_TABLE.field_name("AGENT"): "trainer_agent",
                MODEL_LOGS_TABLE.field_name("SUMMARY"): summary,
                MODEL_LOGS_TABLE.field_name("BEFORE"): json.dumps(before.get("score_agent", {})),
                MODEL_LOGS_TABLE.field_name("AFTER"): json.dumps(after.get("score_agent", {})),
            }
            create_record(self.config.model_log_table, fields)
        except AirtableError as exc:
            LOGGER.exception("Failed to log model adjustment: %s", exc)

    # ------------------------------------------------------------------
    # Model routing

    def _rebalance_model_routing(self, avg_closed_score: float) -> None:
        try:
            if avg_closed_score >= 80:
                self.model_selector.update_routing(local_ratio=0.7, cloud_ratio=0.3)
            elif avg_closed_score <= 60:
                self.model_selector.update_routing(local_ratio=0.4, cloud_ratio=0.6)
        except Exception as exc:  # pragma: no cover - defensive fallback
            LOGGER.exception("Failed to update model routing: %s", exc)


__all__ = ["TrainerAgent", "TrainerAgentConfig"]
